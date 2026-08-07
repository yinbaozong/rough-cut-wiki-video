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


# Whisper drifts between Traditional and Simplified output within one session, so
# a Traditional take silently fails keyword matching against a Simplified wiki.
# Covers the assembly/electronics/instructional vocabulary this skill sees; it is
# deliberately not a general converter.
_TRADITIONAL_TO_SIMPLIFIED = str.maketrans({
    # Assembly, fasteners, enclosure parts
    "裝": "装", "殼": "壳", "蓋": "盖", "絲": "丝", "鎖": "锁", "緊": "紧", "鬆": "松",
    "擰": "拧", "側": "侧", "邊": "边", "內": "内", "預": "预", "對": "对", "準": "准",
    "塊": "块", "釘": "钉", "鉗": "钳", "鑽": "钻", "鋸": "锯", "錘": "锤", "鍵": "键",
    "鈕": "钮", "針": "针", "鏈": "链", "軌": "轨", "輛": "辆", "頂": "顶", "縫": "缝",
    # Mechanism, drive, sensing
    "齒": "齿", "輪": "轮", "軸": "轴", "傳": "传", "測": "测", "調": "调", "節": "节",
    "檢": "检", "確": "确", "認": "认", "顯": "显", "風": "风", "熱": "热", "噴": "喷",
    "擠": "挤", "壓": "压", "縮": "缩", "導": "导", "膠": "胶", "帶": "带", "條": "条",
    "鋼": "钢", "鐵": "铁", "鋁": "铝", "銅": "铜", "鏽": "锈", "潔": "洁", "淨": "净",
    "滾": "滚", "溝": "沟", "濾": "滤", "盤": "盘", "穩": "稳", "鋒": "锋", "驅": "驱",
    "驗": "验", "輸": "输", "運": "运", "載": "载", "較": "较", "輔": "辅", "適": "适",
    # Electrical and imaging
    "電": "电", "線": "线", "機": "机", "連": "连", "頭": "头", "進": "进", "組": "组",
    "開": "开", "關": "关", "動": "动", "門": "门", "閉": "闭", "韌": "韧",
    "鏡": "镜", "視": "视", "頻": "频", "錄": "录", "製": "制", "螢": "萤", "腦": "脑",
    # High-frequency spoken Chinese
    "們": "们", "個": "个", "來": "来", "這": "这", "時": "时", "間": "间", "後": "后",
    "會": "会", "將": "将", "當": "当", "麼": "么", "與": "与", "從": "从", "給": "给",
    "讓": "让", "說": "说", "聽": "听", "見": "见", "覺": "觉", "點": "点", "區": "区",
    "並": "并", "為": "为", "還": "还", "無": "无", "發": "发", "現": "现", "實": "实",
    "體": "体", "樣": "样", "種": "种", "類": "类", "統": "统", "網": "网", "絡": "络",
    "資": "资", "訊": "讯", "號": "号", "標": "标", "籤": "签", "誌": "志", "圖": "图",
    "單": "单", "雙": "双", "層": "层", "級": "级", "別": "别", "規": "规", "長": "长",
    "寬": "宽", "輕": "轻", "強": "强", "軟": "软", "乾": "干", "濕": "湿", "舊": "旧",
    "壞": "坏", "錯": "错", "誤": "误", "問": "问", "題": "题", "決": "决", "處": "处",
    "數": "数", "轉": "转", "順": "顺", "鐘": "钟", "繼": "继", "續": "续", "終": "终",
    "結": "结", "斷": "断", "總": "总", "聲": "声", "聯": "联", "舉": "举", "術": "术",
    "補": "补", "計": "计", "設": "设", "試": "试", "詳": "详", "誰": "谁", "談": "谈",
    "請": "请", "謝": "谢", "證": "证", "貼": "贴", "選": "选", "遠": "远", "頁": "页",
    "項": "项", "須": "须", "領": "领", "顆": "颗", "願": "愿", "顧": "顾", "飛": "飞",
    "應": "应", "該": "该", "產": "产", "備": "备", "護": "护", "維": "维", "細": "细",
    "純": "纯", "紅": "红", "綠": "绿", "藍": "蓝", "黃": "黄", "衝": "冲", "擊": "击",
    "餘": "余", "齊": "齐", "龍": "龙", "廢": "废", "廠": "厂", "簡": "简", "積": "积",
    "礙": "碍", "識": "识", "記": "记", "許": "许", "評": "评", "觀": "观", "親": "亲",
    "難": "难", "隨": "随", "險": "险", "隱": "隐", "際": "际", "陣": "阵", "陰": "阴",
    "陽": "阳", "雲": "云", "靈": "灵", "髒": "脏", "鮮": "鲜", "鹽": "盐", "麥": "麦",
    "黨": "党", "豐": "丰", "臨": "临", "藝": "艺", "藥": "药", "醫": "医", "療": "疗",
    "書": "书", "紙": "纸", "筆": "笔", "畫": "画", "寫": "写", "讀": "读", "語": "语",
    "詞": "词", "話": "话", "講": "讲", "論": "论", "議": "议", "學": "学", "習": "习",
    "訓": "训", "練": "练", "課": "课", "員": "员", "師": "师", "業": "业", "務": "务",
    "職": "职", "辦": "办", "衛": "卫", "臟": "脏", "腳": "脚", "髮": "发", "膚": "肤",
})


def to_simplified(text: str) -> str:
    return text.translate(_TRADITIONAL_TO_SIMPLIFIED)


def _clean(text: str) -> str:
    return to_simplified(unicodedata.normalize("NFKC", text).strip())


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


def terms_from_steps(steps: list[dict]) -> list[str]:
    """Repair vocabulary taken from the procedure itself.

    A user glossary describes the whole product line, so it often lacks the exact
    wording of the step being filmed: on real footage the misheard 抵扣布丁螺丝
    could only be recovered from the procedure's own 底壳固定螺丝. Matching cares
    about step vocabulary, which makes the steps the more relevant source.
    """
    terms: dict[str, None] = {}
    for step in steps:
        for chunk in re.split(r"[，,。；;、\s]+", step.get("wiki_text", "")):
            chunk = re.sub(r"[^\u4e00-\u9fff]", "", chunk)
            if len(chunk) >= 3:
                terms.setdefault(chunk, None)
            # Also index the object without its leading verb so that "移除底壳固定
            # 螺丝" can repair a take that only garbled "底壳固定螺丝".
            stripped = chunk
            while len(stripped) > 3 and stripped[0] in ACTION_HINTS:
                stripped = stripped[1:]
            if len(stripped) >= 3:
                terms.setdefault(stripped, None)
    return list(terms)


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


MATCH_THRESHOLD = 0.34


def _shared(label: str, step: dict) -> tuple[int, int, int]:
    a = set(_keywords(label))
    b = set(step.get("keywords") or _keywords(step["wiki_text"]))
    return len(a & b), len(a), len(b)


def _score(label: str, step: dict) -> float:
    overlap, size_a, size_b = _shared(label, step)
    if not size_a or not size_b:
        return 0.0
    return overlap / max(1, min(size_a, size_b))


def best_match(label: str | None, steps: list[dict]) -> tuple[float, dict | None]:
    """Pick the step sharing the most terms, not merely the best ratio.

    A short step like "安装底壳" scores a perfect ratio against "安装底壳固定螺丝"
    because the take contains all of it, which would steal takes from the more
    specific "安装底壳固定螺丝并预锁紧". Ranking qualified steps by absolute shared
    terms keeps the specific step ahead.
    """
    if not label or not steps:
        return 0.0, None
    ranked = [(_score(label, step), _shared(label, step)[0], step) for step in steps]
    qualified = [item for item in ranked if item[0] >= MATCH_THRESHOLD] or ranked
    qualified.sort(key=lambda item: (item[1], item[0]), reverse=True)
    score, _overlap, step = qualified[0]
    return score, step


def build_edit_plan(steps: list[dict], takes: list[dict]) -> dict:
    segments = []
    matched = set()
    unmarked_files = []

    def best_match_local(label: str | None) -> tuple[float, dict | None]:
        return best_match(label, steps)

    for source_index, take in enumerate(takes):
        evidence = parse_filename(Path(take["source_file"]))
        forced = next((candidate for candidate in steps if candidate["id"] == take.get("manual_step_id")), None)
        manual_score, manual_step = best_match_local(take.get("manual_label"))
        voice_score, voice_step = best_match_local(take.get("spoken_label"))
        filename_score, filename_step = best_match_local(evidence["label"])
        ocr_score, ocr_step = best_match_local(take.get("ocr_text"))
        threshold = MATCH_THRESHOLD

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
