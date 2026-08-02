from __future__ import annotations

import re
import unicodedata
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
CAMERA_NAMES = re.compile(r"^(?:DJI|C|GH|GOPR|GX|MVI)[_-]?\d+$", re.I)
CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
START_RE = re.compile(r"^(?:3\s*2\s*1|三\s*二\s*一|321)?\s*(?:开始|走)$", re.I)
END_RE = re.compile(r"^(?:ok|过|可以|好了|结束)$", re.I)
ACTION_HINTS = "安装拆卸移除取下连接插入拧紧松开调整校准打开关闭放置固定撕下拔出更换清洁检查"
STEP_LABEL_PATTERN = r"(?:步骤\s*(?:\d+|[一二三四五六七八九十]+)|step\s*\d+)"
EXPLICIT_STEP_PATTERN = rf"(?:\d+[.)、]|{STEP_LABEL_PATTERN}\s*[:：.,，]?)"


def _clean(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def parse_filename(path: Path) -> dict:
    stem = _clean(path.stem)
    if CAMERA_NAMES.fullmatch(stem) or re.fullmatch(r"微信视频\d{4}-\d{2}-\d{2}_\d{6}_\d+", stem):
        return {"label": None, "part_number": None, "sequence_number": None}
    sequence = None
    m = re.match(r"^(\d{2,4})[_ -]+", stem)
    if m:
        sequence = int(m.group(1))
        stem = stem[m.end():]
    part = None
    patterns = [
        r"[_ -]*(?:第)?(\d+)(?:段|部分|条|take)?$",
        r"[_ -]*(?:第)?([一二三四五六七八九十])(?:段|部分)?$",
    ]
    for pattern in patterns:
        m = re.search(pattern, stem, re.I)
        if m:
            raw = m.group(1)
            part = int(raw) if raw.isdigit() else CN_DIGITS.get(raw)
            stem = stem[:m.start()]
            break
    label = re.sub(r"[_ -]+", " ", stem).strip() or None
    return {"label": label, "part_number": part, "sequence_number": sequence}


def parse_wiki(text: str) -> list[dict]:
    """Conservatively extract ordered action steps from pasted Markdown/plain text."""
    candidates: list[str] = []
    in_table_header = False
    text = re.sub(rf"(?={STEP_LABEL_PATTERN}\s*[:：,，.]?)", "\n", text, flags=re.I)
    for raw in text.splitlines():
        line = _clean(raw)
        if not line or line.startswith("#") or re.fullmatch(r"[|:\- ]+", line):
            continue
        explicit_step = bool(re.match(rf"^\s*{EXPLICIT_STEP_PATTERN}", line, re.I))
        line = re.sub(rf"^\s*(?:{EXPLICIT_STEP_PATTERN}|[-*+]\s+)\s*", "", line, flags=re.I)
        if not line:
            continue
        # Avoid promoting tool lists and generic warnings to timeline steps.
        if re.match(r"^(?:注意|警告|提示|准备|工具|所需物品)[:：]", line):
            continue
        if explicit_step or any(ch in line for ch in ACTION_HINTS):
            candidates.append(line)
    return [
        {
            "id": f"step-{i:03d}", "order": i, "branch": None,
            "wiki_text": line, "caption_text": _caption_text(line),
            "keywords": _keywords(line), "notes": [],
        }
        for i, line in enumerate(candidates, 1)
    ]


def _caption_text(line: str) -> str:
    polished = line.replace(",", "，").replace(":", "：").strip()
    polished = polished.rstrip("，；;。 ")
    return polished + "。"


def _keywords(text: str) -> list[str]:
    cleaned = re.sub(r"[\W_\d]+", "", _clean(text), flags=re.UNICODE)
    stop = set("然后接着并将把的了请先再用与和至到进行")
    grams = {cleaned[i:i + 2] for i in range(max(0, len(cleaned) - 1))}
    grams.update(ch for ch in cleaned if ch not in stop and ch in ACTION_HINTS)
    return sorted(g for g in grams if g)


def _score(label: str, step: dict) -> float:
    a = set(_keywords(label))
    b = set(step.get("keywords") or _keywords(step["wiki_text"]))
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return overlap / max(1, min(len(a), len(b)))


def build_edit_plan(steps: list[dict], takes: list[dict]) -> dict:
    segments = []
    matched = set()
    unmarked_files = []

    def best_match(label: str | None) -> tuple[float, dict | None]:
        if not label:
            return 0.0, None
        ranked = sorted(((_score(label, step), step) for step in steps), key=lambda x: x[0], reverse=True)
        return ranked[0] if ranked else (0.0, None)

    for source_index, take in enumerate(takes):
        evidence = parse_filename(Path(take["source_file"]))
        forced = next((candidate for candidate in steps if candidate["id"] == take.get("manual_step_id")), None)
        manual_score, manual_step = best_match(take.get("manual_label"))
        voice_score, voice_step = best_match(take.get("spoken_label"))
        filename_score, filename_step = best_match(evidence["label"])
        ocr_score, ocr_step = best_match(take.get("ocr_text"))
        threshold = 0.34

        selected_source = None
        if forced:
            score, step, selected_source = 1.0, forced, "manual"
        elif manual_step and manual_score >= threshold:
            score, step, selected_source = manual_score, manual_step, "manual"
        elif voice_step and voice_score >= threshold:
            score, step, selected_source = voice_score, voice_step, "spoken"
        elif filename_step and filename_score >= threshold:
            score, step, selected_source = filename_score, filename_step, "filename"
        else:
            score, step = 0.0, None

        needs_user_input = step is None
        conflict = bool(
            selected_source == "spoken"
            and filename_step and filename_score >= threshold
            and filename_step["id"] != step["id"]
        )
        status = "ambiguous" if conflict else ("matched" if step else "unmatched")
        original_name = Path(take["source_file"]).name
        if step:
            review_reason = None
        elif not take.get("spoken_label") and not evidence["label"]:
            review_reason = "无报幕且无有效文件名"
        elif not take.get("spoken_label"):
            review_reason = "无报幕，文件名无法匹配教程步骤"
        elif not evidence["label"]:
            review_reason = "报幕无法匹配教程步骤，且无有效文件名"
        else:
            review_reason = "报幕和文件名均无法匹配教程步骤"
        if needs_user_input:
            unmarked_files.append(original_name)
        if step:
            matched.add(step["id"])
        duration = float(take.get("duration", 0.0))
        segments.append({
            "id": f"segment-{source_index + 1:03d}",
            "source_file": str(take["source_file"]),
            "source_in": float(take.get("in", 0.0)),
            "source_out": float(take.get("out", duration)),
            "wiki_step_id": step["id"] if step else None,
            "wiki_order": step["order"] if step else 999999,
            "part_number": evidence["part_number"],
            "status": status,
            "display_name": original_name if step else f"待确认（{review_reason}）— {original_name}",
            "confidence": round(score, 3),
            "captions": [step["caption_text"]] if step else ["未识别到对应步骤"],
            "review_caption": [] if status == "matched" else ["待确认"],
            "evidence": {
                "selected_source": selected_source,
                "filename_label": evidence["label"],
                "spoken_label": take.get("spoken_label"),
                "voice_wiki_score": round(voice_score, 3),
                "filename_wiki_score": round(filename_score, 3),
                "ocr_wiki_score": round(ocr_score, 3),
                "ocr_suggested_step_id": ocr_step["id"] if ocr_step and ocr_score >= threshold else None,
                "conflict": conflict,
                "needs_user_input": needs_user_input,
                "review_reason": review_reason,
            },
            "source_index": source_index,
        })
    segments.sort(key=lambda x: (x["wiki_order"], x["part_number"] is None, x["part_number"] or 0, x["source_index"]))
    return {
        "schema_version": "1.0",
        "segments": segments,
        "missing_step_ids": [s["id"] for s in steps if s["id"] not in matched],
        "action_required_files": unmarked_files.copy(),
        "unmarked_files": unmarked_files,
    }


def segment_transcript(words: list[dict], duration: float) -> list[dict]:
    """Split word-timestamp transcript into takes using isolated spoken cues."""
    if not words:
        return [{"in": 0.0, "out": duration, "spoken_label": None, "end_reason": "no_speech"}]
    collapsed, index = [], 0
    while index < len(words):
        if index + 1 < len(words):
            first = _clean(str(words[index]["word"])).strip("，。！？,.!? ")
            second = _clean(str(words[index + 1]["word"])).strip("，。！？,.!? ")
            combined = first + second
            gap = float(words[index + 1]["start"]) - float(words[index]["end"])
            if END_RE.fullmatch(combined) and gap <= 0.5:
                collapsed.append({"start": words[index]["start"], "end": words[index + 1]["end"], "word": combined})
                index += 2
                continue
        collapsed.append(words[index]); index += 1
    words = collapsed
    takes = []
    start = 0.0
    content: list[str] = []
    active = False
    for item in words:
        word = _clean(str(item["word"])).strip("，。！？,.!? ")
        if START_RE.fullmatch(word):
            if active and content:
                takes.append({"in": start, "out": float(item["start"]), "spoken_label": "".join(content), "end_reason": "next_start"})
            start, content, active = float(item["end"]), [], True
        elif active and END_RE.fullmatch(word):
            takes.append({"in": start, "out": float(item["start"]), "spoken_label": "".join(content), "end_reason": "spoken_cue"})
            active, content = False, []
        elif active and word.startswith("下一步"):
            if content:
                takes.append({"in": start, "out": float(item["start"]), "spoken_label": "".join(content), "end_reason": "next_step"})
            start, content = float(item["start"]), [word.removeprefix("下一步")],
        elif active:
            content.append(word)
    if active:
        takes.append({"in": start, "out": duration, "spoken_label": "".join(content), "end_reason": "file_end"})
    if not takes and words:
        return [{"in": 0.0, "out": duration, "spoken_label": "".join(_clean(str(x["word"])) for x in words), "end_reason": "file_end"}]
    return takes
