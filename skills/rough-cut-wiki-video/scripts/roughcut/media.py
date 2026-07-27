from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .core import VIDEO_EXTENSIONS, segment_transcript


_MODEL_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")


class MissingWhisperModelError(RuntimeError):
    pass


def _cached_whisper_model(name: str) -> str | None:
    try:
        from faster_whisper.utils import download_model
        return download_model(name, local_files_only=True)
    except Exception:
        return None


def resolve_whisper_model(
    model_name: str,
    *,
    skill_root: Path | None = None,
    cached_model=None,
) -> str:
    skill_root = Path(skill_root) if skill_root else Path(__file__).resolve().parents[2]
    if model_name != "small":
        raise ValueError("Only the multilingual faster-whisper small model is supported")
    bundled = skill_root / "assets" / "models" / "faster-whisper-small"
    bundled_ready = all((bundled / name).is_file() for name in _MODEL_FILES)
    cache_lookup = cached_model or _cached_whisper_model
    if bundled_ready:
        return str(bundled.resolve())
    cached_small = cache_lookup("small")
    if cached_small:
        return str(cached_small)
    repair = skill_root / "scripts" / "download-model.ps1"
    raise MissingWhisperModelError(
        "The multilingual faster-whisper small model is missing. Run: "
        f'powershell -ExecutionPolicy Bypass -File "{repair}". '
        "Official model: https://huggingface.co/Systran/faster-whisper-small"
    )


def find_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        matches = sorted(root.glob(f"Gyan.FFmpeg*/**/{name}.exe")) if root.exists() else []
        if matches:
            return str(matches[-1])
    return None


def discover_media(folder: Path) -> list[Path]:
    return sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS), key=lambda p: (p.stat().st_mtime, p.name))


def probe(path: Path) -> dict:
    command = find_binary("ffprobe")
    if not command:
        raise RuntimeError("ffprobe is not installed")
    result = subprocess.run(
        [command, "-v", "error", "-show_entries", "format=duration:stream=index,codec_type,width,height,r_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    return {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "video": next((s for s in streams if s.get("codec_type") == "video"), {}),
    }


def transcribe(path: Path, model_name: str = "small") -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to extract the audio track")
    model = WhisperModel(resolve_whisper_model(model_name), device="cpu", compute_type="int8")
    with tempfile.TemporaryDirectory(prefix="roughcut-audio-") as folder:
        audio = Path(folder) / "audio.wav"
        subprocess.run(
            [ffmpeg, "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)],
            check=True, capture_output=True,
        )
        segments, _info = model.transcribe(str(audio), vad_filter=True, word_timestamps=True)
        words = []
        for segment in segments:
            for word in segment.words or []:
                words.append({"start": word.start, "end": word.end, "word": word.word})
        return words


def read_representative_text(path: Path, duration: float) -> str:
    """OCR one representative frame; callers treat failure as optional evidence loss."""
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed")
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError("rapidocr is not installed") from exc
    with tempfile.TemporaryDirectory(prefix="roughcut-ocr-") as folder:
        frame = Path(folder) / "frame.jpg"
        subprocess.run([ffmpeg, "-y", "-ss", str(max(0.0, duration / 2)), "-i", str(path), "-frames:v", "1", "-vf", "scale=-2:720", str(frame)], check=True, capture_output=True)
        result = RapidOCR()(str(frame))
        texts = getattr(result, "txts", None)
        if texts is None and isinstance(result, tuple) and result and result[0]:
            texts = [item[1] for item in result[0]]
        return " ".join(texts or [])


def analyze_file(path: Path, mode: str, probe_media: bool = True, model_name: str = "small") -> tuple[list[dict], list[str]]:
    warnings = []
    metadata = {"duration": 1.0, "has_audio": False, "video": {}}
    if probe_media:
        try:
            metadata = probe(path)
        except Exception as exc:
            warnings.append(f"媒体探测失败，保留素材并按文件名处理：{path.name}: {exc}")
    base = {"source_file": str(path.resolve()), **metadata}
    if mode == "filename" or not metadata.get("has_audio"):
        return [base], warnings
    try:
        words = transcribe(path, model_name)
        try:
            base["ocr_text"] = read_representative_text(path, metadata["duration"])
        except Exception as exc:
            warnings.append(f"OCR 可选证据不可用：{path.name}: {exc}")
        detected = segment_transcript(words, metadata["duration"])
        return [{**base, **item, "transcript_words": words} for item in detected], warnings
    except MissingWhisperModelError:
        raise
    except Exception as exc:
        warnings.append(f"语音识别不可用，自动回退文件名模式：{path.name}: {exc}")
        return [base], warnings
