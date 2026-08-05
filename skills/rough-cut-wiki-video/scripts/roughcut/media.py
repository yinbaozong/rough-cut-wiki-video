from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from .core import VIDEO_EXTENSIONS, segment_transcript
from .lexicon import repair


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


DEFAULT_LANGUAGE = "zh"
DEFAULT_WORKERS = 6
# Measured on a 12-logical-core CPU: batch 2 beat batch 8, and both beat sequential.
DEFAULT_BATCH_SIZE = 2
# Takes here run 10 to 40 seconds, so the 30-second default pads most of them.
DEFAULT_CHUNK_LENGTH = 10
_FALLBACK_METADATA = {"duration": 1.0, "has_audio": False, "video": {}}


def default_cpu_threads() -> int:
    """Skip efficiency cores on hybrid CPUs; they hold back the whole batch."""
    logical = os.cpu_count() or 4
    return max(1, logical * 2 // 3)


@lru_cache(maxsize=1)
def _load_pipeline(model_path: str, cpu_threads: int):
    """Load once per process; reloading per file dominated the previous runtime."""
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    model = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    return BatchedInferencePipeline(model=model)


def extract_audio_track(path: Path, target: Path) -> Path:
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to extract the audio track")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)],
        check=True, capture_output=True,
    )
    return target


def _transcribe_audio(
    pipeline,
    audio: Path,
    language: str = DEFAULT_LANGUAGE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
) -> list[dict]:
    # Pinning the language avoids auto-detection mistaking a short, noisy cue for
    # another language and returning transcript text in it; it also measured
    # roughly twice as fast as letting detection run.
    # beam_size stays at the library default: dropping to greedy decoding turned
    # "移除底壳" into "一处地壳" for barely any time saved.
    segments, _info = pipeline.transcribe(
        str(audio),
        language=language or None,
        word_timestamps=True,
        vad_filter=True,
        batch_size=batch_size,
        chunk_length=chunk_length,
    )
    words = []
    for segment in segments:
        for word in segment.words or []:
            words.append({"start": word.start, "end": word.end, "word": word.word})
    return words


def transcribe(
    path: Path,
    model_name: str = "small",
    *,
    language: str = DEFAULT_LANGUAGE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    cpu_threads: int | None = None,
) -> list[dict]:
    try:
        import faster_whisper  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc
    threads = cpu_threads if cpu_threads else default_cpu_threads()
    pipeline = _load_pipeline(resolve_whisper_model(model_name), threads)
    with tempfile.TemporaryDirectory(prefix="roughcut-audio-") as folder:
        audio = extract_audio_track(path, Path(folder) / "audio.wav")
        return _transcribe_audio(pipeline, audio, language, batch_size, chunk_length)


def _probe_many(paths: list[Path], probe_media: bool, workers: int) -> tuple[dict[Path, dict], list[str]]:
    if not probe_media:
        return {path: dict(_FALLBACK_METADATA) for path in paths}, []

    def probe_one(path: Path):
        try:
            return path, probe(path), None
        except Exception as exc:
            note = f"媒体探测失败，保留素材并按文件名处理：{path.name}: {exc}"
            return path, dict(_FALLBACK_METADATA), note

    metadata: dict[Path, dict] = {}
    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, meta, note in pool.map(probe_one, paths):
            metadata[path] = meta
            if note:
                warnings.append(note)
    return metadata, warnings


def _extract_many(paths: list[Path], folder: Path, workers: int) -> tuple[dict[Path, Path], list[str]]:
    """Decode audio concurrently; reading 4K files off a share is I/O bound."""

    def extract_one(item: tuple[int, Path]):
        index, path = item
        try:
            return path, extract_audio_track(path, folder / f"{index:04d}.wav"), None
        except Exception as exc:
            return path, None, f"音轨提取失败，回退文件名模式：{path.name}: {exc}"

    audio: dict[Path, Path] = {}
    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, track, note in pool.map(extract_one, enumerate(paths)):
            if track is not None:
                audio[path] = track
            if note:
                warnings.append(note)
    return audio, warnings


def analyze_batch(
    paths: list[Path],
    mode: str = "auto",
    probe_media: bool = True,
    model_name: str = "small",
    *,
    language: str = DEFAULT_LANGUAGE,
    workers: int = DEFAULT_WORKERS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    cpu_threads: int | None = None,
    terms: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """Probe and transcribe a whole shoot, keeping the caller's file order."""
    paths = [Path(path) for path in paths]
    workers = max(1, workers)
    metadata, warnings = _probe_many(paths, probe_media, workers)
    voiced = [path for path in paths if mode != "filename" and metadata[path].get("has_audio")]
    takes: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="roughcut-audio-") as folder:
        audio: dict[Path, Path] = {}
        if voiced:
            audio, notes = _extract_many(voiced, Path(folder), workers)
            warnings.extend(notes)
        pipeline = None
        if audio:
            threads = cpu_threads if cpu_threads else default_cpu_threads()
            try:
                pipeline = _load_pipeline(resolve_whisper_model(model_name), threads)
            except MissingWhisperModelError:
                raise
            except Exception as exc:
                warnings.append(f"语音识别不可用，全部素材回退文件名模式：{exc}")
        for path in paths:
            base = {"source_file": str(path.resolve()), **metadata[path]}
            track = audio.get(path)
            if pipeline is None or track is None:
                takes.append(base)
                continue
            try:
                words = _transcribe_audio(pipeline, track, language, batch_size, chunk_length)
            except Exception as exc:
                warnings.append(f"语音识别失败，回退文件名模式：{path.name}: {exc}")
                takes.append(base)
                continue
            for item in segment_transcript(words, metadata[path]["duration"]):
                takes.append(_apply_lexicon({**base, **item, "transcript_words": words}, terms))
    return takes, warnings


def _apply_lexicon(take: dict, terms: list[str] | None) -> dict:
    if not terms:
        return take
    repaired, changes = repair(take.get("spoken_label"), terms)
    if changes:
        take["spoken_label_raw"] = take.get("spoken_label")
        take["spoken_label"] = repaired
        take["lexicon_repairs"] = changes
    return take


def analyze_file(
    path: Path,
    mode: str,
    probe_media: bool = True,
    model_name: str = "small",
    *,
    language: str = DEFAULT_LANGUAGE,
    terms: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    return analyze_batch(
        [path], mode, probe_media, model_name,
        language=language, workers=1, terms=terms,
    )
