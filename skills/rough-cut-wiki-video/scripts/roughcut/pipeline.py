from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .core import MATCH_THRESHOLD, best_match, build_edit_plan, parse_wiki, terms_from_steps
from .exporters import render_preview, write_fcpxml, write_srt
from .lexicon import load_terms, pinyin_available, propose
from .media import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_LENGTH,
    DEFAULT_LANGUAGE,
    DEFAULT_WORKERS,
    analyze_batch,
    default_cpu_threads,
    discover_media,
)

REVIEW_FILE = "lexicon-review.json"
# Takes already matched this confidently have nothing worth reviewing; on real
# footage this is what keeps the reviewed band down to the few unclear takes.
DEFAULT_REVIEW_CONFIDENCE = 0.70
# Keep the review list short enough to judge; suggestions are rank-ordered.
MAX_PROPOSALS_PER_TAKE = 5
REVIEW_INSTRUCTIONS = (
    "Layer 2 of glossary repair. Each proposal was found by character and pinyin "
    "similarity, which cannot tell a real mishearing from a phonetically similar but "
    "wrong term, so nothing here is applied automatically. For each entry set "
    "\"decision\" to \"accept\" or \"reject\" by checking whether resulting_step_text "
    "describes what the take actually shows; leave \"pending\" if unsure. Then re-run "
    "the same command with --reuse-takes to apply the accepted repairs in seconds."
)


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _take_key(take: dict) -> str:
    return f"{Path(take['source_file']).name}#{float(take.get('in', 0.0)):.2f}"


def _proposal_key(item: dict) -> tuple[str, str, str] | None:
    key = (item.get("take"), item.get("found"), item.get("suggested"))
    return key if all(key) else None


def _load_prior(path: Path) -> dict[tuple[str, str, str], dict]:
    """Previous proposals with their verdicts, so review work is never discarded."""
    if not path.is_file():
        return {}
    try:
        stored = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    prior = {}
    for item in stored.get("proposals", []):
        key = _proposal_key(item)
        if key:
            prior[key] = item
    return prior


def _apply_decisions(takes: list[dict], decisions: dict) -> list[str]:
    """Rewrite accepted spans, working from the pre-review text every time.

    Rebuilding from the original keeps a verdict reversible: flipping an entry back
    to reject on a later run restores the transcript instead of leaving the earlier
    substitution baked in. Plain string replacement also avoids offset drift.
    """
    notes = []
    accepted = [key for key, verdict in decisions.items() if verdict == "accept"]
    for take in takes:
        key = _take_key(take)
        baseline = take.get("spoken_label_before_review", take.get("spoken_label"))
        if not baseline:
            continue
        label, history = baseline, []
        for take_id, found, suggested in accepted:
            if take_id != key or found not in label:
                continue
            label = label.replace(found, suggested, 1)
            history.append({"found": found, "corrected": suggested})
        if history:
            take["spoken_label_before_review"] = baseline
            take["spoken_label"] = label
            take["lexicon_accepted"] = history
            notes.extend(f"{key}：{item['found']} → {item['corrected']}" for item in history)
        else:
            take.pop("spoken_label_before_review", None)
            take.pop("lexicon_accepted", None)
            take["spoken_label"] = baseline
    return notes


def _collect_proposals(
    plan: dict, takes: list[dict], steps: list[dict],
    procedure_terms: list[str], glossary_terms: list[str],
    prior: dict, confidence: float,
) -> list[dict]:
    """Suggest repairs only where the match is weak enough for one to matter.

    The procedure goes first and a glossary suggestion covering the same span is
    dropped. Both fired on the same misheard 抵扣布丁螺丝 in real footage: the
    procedure proposed the correct 底壳固定螺丝 at 0.839 by pronunciation, while the
    glossary proposed 进气口 at 0.875 — a higher score for a term that appears
    nowhere in the procedure and so cannot match any step. Ordering by source also
    stops glossary noise from consuming the per-take cap before the procedure is
    considered at all.

    Already-decided entries are carried over even when they no longer regenerate:
    an accepted repair removes the misheard span it was found by, so dropping it
    here would silently revert the repair on the next run.
    """
    proposals = []
    for segment in plan["segments"]:
        if segment["status"] == "matched" and segment["confidence"] >= confidence:
            continue
        take = takes[segment["source_index"]]
        # Propose against the pre-review text so accepted spans stay reviewable.
        label = take.get("spoken_label_before_review") or take.get("spoken_label")
        if not label:
            continue
        key = _take_key(take)
        found_for_take = []
        claimed: list[tuple[int, int]] = []
        ranked = [
            (suggestion, source)
            for source, terms in (("procedure", procedure_terms), ("glossary", glossary_terms))
            for suggestion in propose(label, terms)
        ]
        for suggestion, source in ranked:
            start = label.find(suggestion["found"])
            end = start + len(suggestion["found"])
            if source == "glossary" and any(start < stop and begin < end for begin, stop in claimed):
                continue
            repaired = label.replace(suggestion["found"], suggestion["suggested"], 1)
            score, step = best_match(repaired, steps)
            resulting = step["id"] if step and score >= MATCH_THRESHOLD else None
            # A repair landing on the same step cannot change the cut, so it is noise
            # however plausible it looks.
            if resulting == segment["wiki_step_id"]:
                continue
            if source == "procedure":
                claimed.append((start, end))
            entry = {
                "take": key,
                "source_file": Path(take["source_file"]).name,
                "spoken_label": label,
                "source": source,
                **suggestion,
                "preview": repaired,
                "current_step": segment["wiki_step_id"],
                "current_confidence": segment["confidence"],
                "resulting_step": resulting,
                "resulting_confidence": round(score, 3),
                "resulting_step_text": step["wiki_text"] if step and resulting else None,
                "decision": "pending",
            }
            previous = prior.get(_proposal_key(entry))
            if previous:
                entry["decision"] = previous.get("decision", "pending")
                if previous.get("decision_note"):
                    entry["decision_note"] = previous["decision_note"]
            found_for_take.append(entry)
            if len(found_for_take) >= MAX_PROPOSALS_PER_TAKE:
                break
        proposals.extend(found_for_take)
    fresh = {_proposal_key(item) for item in proposals}
    carried = [
        item for key, item in prior.items()
        if key not in fresh and item.get("decision") in ("accept", "reject")
    ]
    return proposals + carried


def run_project(
    media_dir: Path,
    wiki_file: Path,
    output: Path,
    mode: str = "auto",
    probe_media: bool = True,
    model_name: str = "small",
    preview: bool = False,
    corrections_file: Path | None = None,
    reuse_takes: bool = False,
    *,
    language: str = DEFAULT_LANGUAGE,
    workers: int = DEFAULT_WORKERS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    cpu_threads: int | None = None,
    lexicon_file: Path | None = None,
    review_confidence: float = DEFAULT_REVIEW_CONFIDENCE,
) -> dict:
    media_dir, wiki_file, output = Path(media_dir), Path(wiki_file), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    wiki_text = wiki_file.read_text(encoding="utf-8-sig")
    (output / "wiki-source.md").write_text(wiki_text, encoding="utf-8")
    steps = parse_wiki(wiki_text)
    if not steps:
        raise ValueError("教程内容中未识别到操作步骤；请使用“步骤一、步骤二、步骤三”或有序编号。")
    _write_json(output / "wiki-steps.json", steps)
    takes, warnings = [], []
    glossary_terms = load_terms(lexicon_file)
    if lexicon_file and not glossary_terms:
        warnings.append(f"词库不可用或没有长度达标的词条，已跳过词库纠错：{lexicon_file}")
    elif not lexicon_file:
        warnings.append(
            "未提供用户词库，这不影响运行：术语纠错的主要词汇来自教程步骤原文，"
            "因为报幕念的通常就是原文。词库只是补充，用于原文里简写或未出现的术语。"
        )
    # The narration is the procedure read aloud, so the procedure's own wording is the
    # primary vocabulary and the glossary only supplements it.
    procedure_terms = terms_from_steps(steps)
    vocabulary = list(dict.fromkeys(procedure_terms + glossary_terms))
    if reuse_takes and (output / "takes.json").exists():
        takes = json.loads((output / "takes.json").read_text(encoding="utf-8"))
    else:
        takes, notes = analyze_batch(
            discover_media(media_dir), mode, probe_media, model_name,
            language=language, workers=workers, batch_size=batch_size,
            chunk_length=chunk_length, cpu_threads=cpu_threads, terms=vocabulary,
        )
        warnings.extend(notes)
    if corrections_file:
        corrections = json.loads(Path(corrections_file).read_text(encoding="utf-8-sig"))
        for take in takes:
            correction = corrections.get(Path(take["source_file"]).name, {})
            take.update(correction)
    review_path = output / REVIEW_FILE
    prior = _load_prior(review_path)
    decisions = {key: item.get("decision", "pending") for key, item in prior.items()}
    confirmed = _apply_decisions(takes, decisions)
    _write_json(output / "takes.json", takes)
    plan = build_edit_plan(steps, takes)
    plan["skill_version"] = __version__
    plan["mode_requested"] = mode
    plan["corrections_file"] = str(Path(corrections_file).resolve()) if corrections_file else None
    proposals = _collect_proposals(
        plan, takes, steps, procedure_terms, glossary_terms, prior, review_confidence,
    )
    pending = [item for item in proposals if item["decision"] == "pending"]
    _write_json(review_path, {
        "schema_version": "1.0",
        "instructions": REVIEW_INSTRUCTIONS,
        "pinyin_available": pinyin_available(),
        "review_confidence": review_confidence,
        "procedure_terms": len(procedure_terms),
        "glossary_terms": len(glossary_terms),
        "pending": len(pending),
        "accepted_applied": len(confirmed),
        "proposals": proposals,
    })
    plan["recognition"] = {
        "language": language, "model": model_name,
        "workers": workers, "batch_size": batch_size,
        "chunk_length": chunk_length,
        "cpu_threads": cpu_threads or default_cpu_threads(),
        "lexicon_file": str(Path(lexicon_file).resolve()) if lexicon_file else None,
        "procedure_terms": len(procedure_terms),
        "glossary_terms": len(glossary_terms),
        "vocabulary_terms": len(vocabulary),
        "pinyin_available": pinyin_available(),
    }
    plan["lexicon_review"] = {
        "file": str(review_path.resolve()),
        "pending": len(pending),
        "accepted_applied": len(confirmed),
    }
    if confirmed:
        warnings.append(f"已应用 {len(confirmed)} 条人工确认的词库纠错：{'；'.join(confirmed)}")
    if pending:
        warnings.append(
            f"有 {len(pending)} 条术语纠错待确认，尚未应用。请在 {REVIEW_FILE} 中把 decision "
            f"改为 accept 或 reject，然后加 --reuse-takes 重跑以生效。"
        )
    if vocabulary and not pinyin_available():
        warnings.append(
            "未安装 pypinyin：自动纠错已停用（只比字形无法区分“冷端风扇”和“热端风扇”，"
            "误改风险高于收益），同音错字也无法被发现。请重新运行 setup 脚本安装。"
        )
    plan["warnings"] = warnings
    if plan["unmarked_files"]:
        names = ", ".join(plan["unmarked_files"])
        warnings.append(
            f"以下素材没有可用的报幕或文件名证据，已完整保留在时间线末尾并标记待确认：{names}。"
        )
    _write_json(output / "edit-plan.json", plan)
    write_srt(plan, output / "wiki-subtitles.srt")
    write_srt(plan, output / "review-subtitles.srt", review=True)
    write_fcpxml(plan, output / "timeline.fcpxml")
    if preview:
        warning = render_preview(plan, output / "review-preview.mp4")
        if warning: warnings.append(warning)
    lines = [
        "# 粗剪审核报告", "",
        f"- Skill 版本：{__version__}",
        f"- 素材片段：{len(plan['segments'])}",
        f"- 待确认/未匹配：{sum(s['status'] != 'matched' for s in plan['segments'])}",
        f"- 未拍摄教程步骤：{', '.join(plan['missing_step_ids']) or '无'}",
        f"- 识别设置：语言 {language}，模型 {model_name}，并发 {workers}，批大小 {batch_size}，分块 {chunk_length}s",
        f"- 纠错词汇：步骤原文 {len(procedure_terms)} 条（主）＋用户词库 {len(glossary_terms)} 条（补充）",
        f"- 术语纠错：拼音比对 {'开启' if pinyin_available() else '未安装'}，待确认 {len(pending)}，已确认应用 {len(confirmed)}",
        "", "## 警告", "",
    ]
    lines += [f"- {w}" for w in warnings] or ["- 无"]
    repairs = [
        (Path(take["source_file"]).name, take["lexicon_repairs"], take.get("spoken_label_raw"), take.get("spoken_label"))
        for take in takes if take.get("lexicon_repairs")
    ]
    if repairs:
        lines += [
            "", "## 术语纠错（已自动应用）", "",
            "以下报幕文本被替换为已知术语。自动层只改写与已知正确术语不重叠、"
            "且改动字发音相近的片段，请仍核对是否符合实际操作：", "",
        ]
        for name, changes, raw, fixed in repairs:
            detail = "；".join(f"{c['found']} → {c['corrected']}（{c['score']}）" for c in changes)
            lines.append(f"- `{name}`：{raw} → {fixed}（{detail}）")
    if confirmed:
        lines += ["", "## 术语纠错（人工已确认）", ""]
        lines += [f"- {note}" for note in confirmed]
    if pending:
        lines += [
            "", "## 待确认的术语纠错", "",
            f"以下 {len(pending)} 条由字形和拼音相似度提出，**尚未应用**。同音错字的字形相似度可能为 0，"
            f"而发音相近的错误术语分数又可能更高，因此必须结合步骤原文判断。来源标记 `步骤原文` 的可信度"
            f"通常高于 `词库`：只有教程里出现过的说法才可能匹配到步骤。"
            f"在 `{REVIEW_FILE}` 中把 decision 改成 accept 或 reject，再加 `--reuse-takes` 重跑即可生效。", "",
        ]
        for item in pending:
            target = item["resulting_step_text"] or "无匹配"
            origin = "步骤原文" if item.get("source") == "procedure" else "词库"
            lines.append(
                f"- `{item['source_file']}`（{origin}）：{item['found']} → {item['suggested']}"
                f"（字形 {item['char_score']}，拼音 {item['pinyin_score']}）"
                f"；{item['spoken_label']} → {item['preview']}"
                f"；步骤 {item['current_step'] or '未匹配'} → {item['resulting_step'] or '未匹配'}（{target}）"
            )
    if plan["unmarked_files"]:
        lines += ["", "## 无标记素材", ""]
        lines += [
            f"- `{Path(s['source_file']).name}`：{s['evidence']['review_reason']}；原文件未改名，已放在时间线末尾并标记 `待确认`。"
            for s in plan["segments"] if s["status"] == "unmatched"
        ]
    lines += ["", "## 时间轴", ""] + [f"- {i + 1}. `{Path(s['source_file']).name}` → {s['wiki_step_id'] or '未匹配'} ({s['status']}, {s['confidence']:.2f})" for i, s in enumerate(plan["segments"])]
    (output / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan
