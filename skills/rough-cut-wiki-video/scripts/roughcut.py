#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from roughcut import __version__
from roughcut.lexicon import pinyin_available
from roughcut.pipeline import DEFAULT_REVIEW_CONFIDENCE, run_project
from roughcut.media import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_LENGTH,
    DEFAULT_LANGUAGE,
    DEFAULT_WORKERS,
    MissingWhisperModelError,
    default_cpu_threads,
    find_binary,
    resolve_whisper_model,
)

DEFAULT_CPU_THREADS = default_cpu_threads()
from roughcut.jianying10 import export_jianying10, fingerprint as jianying_fingerprint


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a Wiki-guided editable video rough cut.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Report optional local capabilities")
    doctor.add_argument("--json", action="store_true")
    run = sub.add_parser("run", help="Analyze footage and write an editable project")
    run.add_argument("--media", required=True, type=Path)
    run.add_argument("--wiki", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--mode", choices=("auto", "filename"), default="auto")
    run.add_argument("--model", choices=("small",), default="small", help="multilingual faster-whisper small")
    run.add_argument("--no-probe", action="store_true")
    run.add_argument("--preview", action="store_true")
    run.add_argument("--corrections", type=Path, help="JSON map from source filename to manual evidence overrides")
    run.add_argument("--reuse-takes", action="store_true", help="Reuse output/takes.json instead of retranscribing")
    run.add_argument("--language", default=DEFAULT_LANGUAGE, help="Pinned speech language; empty string re-enables auto-detection")
    run.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel probe/audio-extraction workers")
    run.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="faster-whisper batched inference size")
    run.add_argument("--chunk-length", type=int, default=DEFAULT_CHUNK_LENGTH, help="Seconds per inference chunk; short takes waste less at 10")
    run.add_argument("--cpu-threads", type=int, help=f"CTranslate2 CPU threads; defaults to {DEFAULT_CPU_THREADS}")
    run.add_argument("--lexicon", type=Path, help="Glossary file, one term per line, used to repair recognized terms")
    run.add_argument(
        "--review-confidence", type=float, default=DEFAULT_REVIEW_CONFIDENCE,
        help=f"Propose term repairs only for takes matched below this confidence (default {DEFAULT_REVIEW_CONFIDENCE})",
    )
    jy = sub.add_parser("jianying10", help="Build a native encrypted Jianying 10/11 draft")
    jy.add_argument("--plan", required=True, type=Path)
    jy.add_argument("--drafts", required=True, type=Path)
    jy.add_argument("--name", required=True)
    jy.add_argument("--install-dir", type=Path, help="Version directory or JianyingPro root; auto-detected when omitted")
    jy.add_argument("--user-data", type=Path, help="Register the new draft in Jianying's root metadata")
    jy.add_argument("--allow-replace", action="store_true")
    fp = sub.add_parser("fingerprint", help="Print the Jianying/writer signature that gates staging validation")
    fp.add_argument("--install-dir", type=Path)
    fp.add_argument("--drafts", type=Path)
    args = parser.parse_args(argv)
    if args.command == "fingerprint":
        print(json.dumps(jianying_fingerprint(args.install_dir, draft_root=args.drafts), ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        capabilities = {
            "skill_version": __version__,
            "python": sys.version.split()[0],
            "ffmpeg": find_binary("ffmpeg"),
            "ffprobe": find_binary("ffprobe"),
        }
        try:
            import faster_whisper  # noqa: F401
            capabilities["faster_whisper"] = True
        except ImportError:
            capabilities["faster_whisper"] = False
        capabilities["frame_ocr"] = "disabled"
        capabilities["pinyin_repair"] = pinyin_available()
        try:
            capabilities["whisper_small_model"] = resolve_whisper_model("small")
        except MissingWhisperModelError:
            capabilities["whisper_small_model"] = False
        print(json.dumps(capabilities, ensure_ascii=False, indent=2) if args.json else "\n".join(f"{k}: {v or 'missing'}" for k, v in capabilities.items()))
        return 0
    if args.command == "jianying10":
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
        draft_dir = export_jianying10(
            plan, args.drafts, args.name,
            user_data=args.user_data, jy_install_dir=args.install_dir,
            encrypt=True, allow_replace=args.allow_replace,
        )
        print(json.dumps({"draft_dir": str(draft_dir), "registered": bool(args.user_data)}, ensure_ascii=False, indent=2))
        return 0
    plan = run_project(
        args.media, args.wiki, args.output, args.mode, not args.no_probe, args.model,
        args.preview, args.corrections, args.reuse_takes,
        language=args.language, workers=args.workers,
        batch_size=args.batch_size, chunk_length=args.chunk_length,
        cpu_threads=args.cpu_threads, lexicon_file=args.lexicon,
        review_confidence=args.review_confidence,
    )
    print(json.dumps({
        "skill_version": __version__,
        "output": str(args.output.resolve()),
        "segments": len(plan["segments"]),
        "recognition": plan["recognition"],
        "lexicon_review": plan["lexicon_review"],
        "warnings": plan["warnings"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
