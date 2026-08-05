from __future__ import annotations

import json
from pathlib import Path

from .core import build_edit_plan, parse_wiki
from .exporters import render_preview, write_fcpxml, write_srt
from .lexicon import load_terms
from .media import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_LENGTH,
    DEFAULT_LANGUAGE,
    DEFAULT_WORKERS,
    analyze_batch,
    default_cpu_threads,
    discover_media,
)


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


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
    terms = load_terms(lexicon_file)
    if lexicon_file and not terms:
        warnings.append(f"词库不可用或没有长度达标的词条，已跳过术语纠错：{lexicon_file}")
    if reuse_takes and (output / "takes.json").exists():
        takes = json.loads((output / "takes.json").read_text(encoding="utf-8"))
    else:
        takes, notes = analyze_batch(
            discover_media(media_dir), mode, probe_media, model_name,
            language=language, workers=workers, batch_size=batch_size,
            chunk_length=chunk_length, cpu_threads=cpu_threads, terms=terms,
        )
        warnings.extend(notes)
    if corrections_file:
        corrections = json.loads(Path(corrections_file).read_text(encoding="utf-8-sig"))
        for take in takes:
            correction = corrections.get(Path(take["source_file"]).name, {})
            take.update(correction)
    _write_json(output / "takes.json", takes)
    plan = build_edit_plan(steps, takes)
    plan["mode_requested"] = mode
    plan["corrections_file"] = str(Path(corrections_file).resolve()) if corrections_file else None
    plan["recognition"] = {
        "language": language, "model": model_name,
        "workers": workers, "batch_size": batch_size,
        "chunk_length": chunk_length,
        "cpu_threads": cpu_threads or default_cpu_threads(),
        "lexicon_file": str(Path(lexicon_file).resolve()) if lexicon_file else None,
        "lexicon_terms": len(terms),
    }
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
        f"- 素材片段：{len(plan['segments'])}",
        f"- 待确认/未匹配：{sum(s['status'] != 'matched' for s in plan['segments'])}",
        f"- 未拍摄教程步骤：{', '.join(plan['missing_step_ids']) or '无'}",
        f"- 识别设置：语言 {language}，模型 {model_name}，并发 {workers}，批大小 {batch_size}，分块 {chunk_length}s，词库词条 {len(terms)}",
        "", "## 警告", "",
    ]
    lines += [f"- {w}" for w in warnings] or ["- 无"]
    repairs = [
        (Path(take["source_file"]).name, take["lexicon_repairs"], take.get("spoken_label_raw"), take.get("spoken_label"))
        for take in takes if take.get("lexicon_repairs")
    ]
    if repairs:
        lines += ["", "## 词库纠错", "", "以下报幕文本按词库术语做了替换，请核对是否符合实际操作：", ""]
        for name, changes, raw, fixed in repairs:
            detail = "；".join(f"{c['found']} → {c['corrected']}（{c['score']}）" for c in changes)
            lines.append(f"- `{name}`：{raw} → {fixed}（{detail}）")
    if plan["unmarked_files"]:
        lines += ["", "## 无标记素材", ""]
        lines += [
            f"- `{Path(s['source_file']).name}`：{s['evidence']['review_reason']}；原文件未改名，已放在时间线末尾并标记 `待确认`。"
            for s in plan["segments"] if s["status"] == "unmatched"
        ]
    lines += ["", "## 时间轴", ""] + [f"- {i + 1}. `{Path(s['source_file']).name}` → {s['wiki_step_id'] or '未匹配'} ({s['status']}, {s['confidence']:.2f})" for i, s in enumerate(plan["segments"])]
    (output / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan
