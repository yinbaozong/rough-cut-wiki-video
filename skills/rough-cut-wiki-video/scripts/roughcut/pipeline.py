from __future__ import annotations

import json
from pathlib import Path

from .core import MissingTakeEvidenceError, build_edit_plan, parse_wiki
from .exporters import render_preview, write_fcpxml, write_srt
from .media import analyze_file, discover_media


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_project(media_dir: Path, wiki_file: Path, output: Path, mode: str = "auto", probe_media: bool = True, model_name: str = "small", preview: bool = False, corrections_file: Path | None = None, reuse_takes: bool = False) -> dict:
    media_dir, wiki_file, output = Path(media_dir), Path(wiki_file), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    wiki_text = wiki_file.read_text(encoding="utf-8-sig")
    (output / "wiki-source.md").write_text(wiki_text, encoding="utf-8")
    steps = parse_wiki(wiki_text)
    if not steps:
        raise ValueError("教程内容中未识别到操作步骤；请使用“步骤一、步骤二、步骤三”或有序编号。")
    _write_json(output / "wiki-steps.json", steps)
    takes, warnings = [], []
    if reuse_takes and (output / "takes.json").exists():
        takes = json.loads((output / "takes.json").read_text(encoding="utf-8"))
    else:
        for media in discover_media(media_dir):
            found, notes = analyze_file(media, mode, probe_media, model_name)
            takes.extend(found); warnings.extend(notes)
    if corrections_file:
        corrections = json.loads(Path(corrections_file).read_text(encoding="utf-8-sig"))
        for take in takes:
            correction = corrections.get(Path(take["source_file"]).name, {})
            take.update(correction)
    _write_json(output / "takes.json", takes)
    plan = build_edit_plan(steps, takes)
    plan["mode_requested"] = mode
    plan["corrections_file"] = str(Path(corrections_file).resolve()) if corrections_file else None
    plan["warnings"] = warnings
    _write_json(output / "edit-plan.json", plan)
    if plan["action_required_files"]:
        names = ", ".join(plan["action_required_files"])
        message = (
            "无法从语音或文件名判断这些素材对应的教程步骤："
            f"{names}。请重新录制带有步骤口播的素材，或把文件重命名为动作名称后重试。"
            " / No Wiki-related speech or filename was found. Record a spoken step label or rename the file."
        )
        warnings.append(message)
        _write_json(output / "edit-plan.json", plan)
        (output / "review.md").write_text(
            "# 粗剪审核报告\n\n## 需要用户处理\n\n- " + message + "\n",
            encoding="utf-8",
        )
        raise MissingTakeEvidenceError(message)
    write_srt(plan, output / "wiki-subtitles.srt")
    write_srt(plan, output / "review-subtitles.srt", review=True)
    write_fcpxml(plan, output / "timeline.fcpxml")
    if preview:
        warning = render_preview(plan, output / "review-preview.mp4")
        if warning: warnings.append(warning)
    lines = ["# 粗剪审核报告", "", f"- 素材片段：{len(plan['segments'])}", f"- 待确认/未匹配：{sum(s['status'] != 'matched' for s in plan['segments'])}", f"- 未拍摄教程步骤：{', '.join(plan['missing_step_ids']) or '无'}", "", "## 警告", ""]
    lines += [f"- {w}" for w in warnings] or ["- 无"]
    lines += ["", "## 时间轴", ""] + [f"- {i + 1}. `{Path(s['source_file']).name}` → {s['wiki_step_id'] or '未匹配'} ({s['status']}, {s['confidence']:.2f})" for i, s in enumerate(plan["segments"])]
    (output / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan
