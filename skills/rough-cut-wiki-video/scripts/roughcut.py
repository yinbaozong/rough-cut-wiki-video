#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from roughcut import __version__
from roughcut.core import MissingTakeEvidenceError
from roughcut.pipeline import run_project
from roughcut.media import MissingWhisperModelError, find_binary, resolve_whisper_model
from roughcut.jianying10 import export_jianying10


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
    jy = sub.add_parser("jianying10", help="Build a native encrypted Jianying 10/11 draft")
    jy.add_argument("--plan", required=True, type=Path)
    jy.add_argument("--drafts", required=True, type=Path)
    jy.add_argument("--name", required=True)
    jy.add_argument("--install-dir", type=Path, help="Version directory or JianyingPro root; auto-detected when omitted")
    jy.add_argument("--user-data", type=Path, help="Register the new draft in Jianying's root metadata")
    jy.add_argument("--allow-replace", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        capabilities = {"python": sys.version.split()[0], "ffmpeg": find_binary("ffmpeg"), "ffprobe": find_binary("ffprobe")}
        try:
            import faster_whisper  # noqa: F401
            capabilities["faster_whisper"] = True
        except ImportError:
            capabilities["faster_whisper"] = False
        try:
            import rapidocr  # noqa: F401
            capabilities["rapidocr"] = True
        except ImportError:
            capabilities["rapidocr"] = False
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
    try:
        plan = run_project(args.media, args.wiki, args.output, args.mode, not args.no_probe, args.model, args.preview, args.corrections, args.reuse_takes)
    except MissingTakeEvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output.resolve()), "segments": len(plan["segments"]), "warnings": plan["warnings"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
