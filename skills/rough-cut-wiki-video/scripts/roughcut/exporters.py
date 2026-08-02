from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, ElementTree

from .media import find_binary


def _srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000); m, ms = divmod(ms, 60_000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(plan: dict, target: Path, review: bool = False) -> None:
    blocks, cursor, index = [], 0.0, 1
    for seg in plan["segments"]:
        duration = max(0.1, seg["source_out"] - seg["source_in"])
        texts = seg["review_caption"] if review else seg["captions"]
        for i, value in enumerate(texts):
            start = cursor + duration * i / len(texts)
            end = cursor + duration * (i + 1) / len(texts)
            blocks.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{value}\n")
            index += 1
        cursor += duration
    target.write_text("\n".join(blocks), encoding="utf-8-sig")


def write_fcpxml(plan: dict, target: Path) -> None:
    root = Element("fcpxml", version="1.10")
    resources = SubElement(root, "resources")
    SubElement(resources, "format", id="r1", name="FFVideoFormatRateUndefined", width="3840", height="2160")
    for i, seg in enumerate(plan["segments"], 2):
        uri = "file:///" + quote(Path(seg["source_file"]).resolve().as_posix(), safe="/:" )
        SubElement(resources, "asset", id=f"r{i}", name=Path(seg["source_file"]).name, src=uri, start="0s", duration=f"{seg['source_out']}s", hasVideo="1", hasAudio="1")
    library = SubElement(root, "library")
    event = SubElement(library, "event", name="Wiki Rough Cut")
    project = SubElement(event, "project", name="Wiki Rough Cut")
    sequence = SubElement(project, "sequence", format="r1", tcStart="0s", tcFormat="NDF")
    spine = SubElement(sequence, "spine")
    cursor = 0.0
    for i, seg in enumerate(plan["segments"], 2):
        duration = max(0.1, seg["source_out"] - seg["source_in"])
        clip = SubElement(spine, "asset-clip", name=seg.get("display_name") or Path(seg["source_file"]).name, ref=f"r{i}", offset=f"{cursor}s", start=f"{seg['source_in']}s", duration=f"{duration}s")
        if seg["captions"]:
            title = SubElement(clip, "title", name="文档字幕", lane="1", offset="0s", duration=f"{duration}s")
            SubElement(title, "text").text = " ".join(seg["captions"])
        if seg["review_caption"]:
            title = SubElement(clip, "title", name="待确认", lane="2", offset="0s", duration=f"{duration}s")
            SubElement(title, "text").text = "待确认"
        cursor += duration
    ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def render_preview(plan: dict, target: Path) -> str | None:
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg or not plan["segments"]:
        return "FFmpeg 不可用，未生成审核预览。"
    command = [ffmpeg, "-y"]
    filters, inputs = [], []
    for index, seg in enumerate(plan["segments"]):
        command.extend(["-ss", str(seg["source_in"]), "-t", str(max(0.1, seg["source_out"] - seg["source_in"])), "-i", str(Path(seg["source_file"]).resolve())])
        filters.extend([f"[{index}:v]scale=-2:720,setsar=1[v{index}]", f"[{index}:a]aresample=async=1[a{index}]"])
        inputs.append(f"[v{index}][a{index}]")
    filters.append("".join(inputs) + f"concat=n={len(inputs)}:v=1:a=1[v][a]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(target)])
    try:
        subprocess.run(command, check=True, capture_output=True)
        return None
    except Exception as exc:
        return f"审核预览生成失败：{exc}"
