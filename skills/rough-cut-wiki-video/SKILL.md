---
name: rough-cut-wiki-video
description: Create an editable instructional-video rough cut from Markdown Wiki instructions plus MP4/MOV footage. Use for Wiki-guided 3D-printing tutorials, speech-cue trimming, sparse filename ordering, Wiki-derived captions, SRT/FCPXML export, review reports, or native encrypted Jianying 10/11 drafts on Windows, including fixing drafts that do not appear on the Jianying homepage.
---

# Wiki Video Rough Cut

Turn pasted procedure text and a footage folder into a non-destructive rough-cut package. Prefer local speech evidence, fall back to filenames, preserve every take, and use the Wiki—not improvised narration—as the factual source for captions.

## Workflow

1. Ask for the footage directory and pasted Wiki body. Do not fetch a URL unless the user explicitly asks. Save pasted text to a UTF-8 Markdown file without rewriting it.
2. Locate this skill directory from the loaded `SKILL.md`; never assume a `.codex`, `.claude`, or `.cursor` path.
3. Run the capability check:

   ```powershell
   python scripts/roughcut.py doctor
   ```

4. Run analysis. Use `auto` unless the user requests filename-only processing. In auto mode, extract the audio track first, transcribe with word timestamps, and test whether the spoken label is related to a Wiki step before considering the filename:

   ```powershell
   python scripts/roughcut.py run --media "E:\footage" --wiki "E:\job\wiki.md" --output "E:\job\output" --mode auto --preview
   ```

5. Inspect `review.md`, `edit-plan.json`, representative evidence, and warnings. Improve `wiki-steps.json` or `edit-plan.json` only when the footage/Wiki evidence supports the change. Never invent quantities, parts, directions, or safety claims.
6. Re-run exporters after a manual plan change (currently use `run` for a full rebuild). Keep ambiguous or conflicting footage and mark it `待确认`; never silently drop input media.
7. On Windows, create a native Jianying 10/11 project from `edit-plan.json` with the `jianying10` command. First omit `--user-data` and validate in a staging directory. Before adding `--user-data` to register the real project, require Jianying to be fully closed. The exporter must encrypt both draft JSON files with the newest valid local `videoeditor.dll`, back up `root_meta_info.json`, and register a matching homepage entry. Never replace an existing draft unless the user explicitly authorizes it.

## Evidence Rules

Use this priority: user corrections; Wiki-related post-start spoken label; meaningful filename and part number; Wiki order/OCR/visual context for review only. A camera filename such as `DJI_0001` is not a label. If speech is empty or unrelated to every Wiki step, try the filename. If neither provides Wiki-related evidence, stop instead of guessing and ask the user to record a spoken step label or rename the file. Preserve repeated takes and order explicit parts before recording time. Put other unmatched material at the timeline end and list unshot Wiki steps only in the report.

Start cues are `321开始`, `三二一开始`, `321走`, or isolated `开始`/`走`. End cues are isolated `OK`, `过`, `可以`, `好了`, or `结束`. Do not trim phrase-internal words such as `可以安装` or `开始拆卸`. File end is a valid take ending.

## Captions and Outputs

Create formal captions from Wiki facts, lightly polishing syntax for natural reading. Keep names, counts, tool sizes, directions, and warnings. Use two independently removable tracks: `文档字幕` and exact text `待确认`. Keep original audio and original 4K files untouched.

The output contract and JSON field definitions are in [schemas.md](references/schemas.md). Read [usage.md](references/usage.md) for platform/setup details and [jianying10.md](references/jianying10.md) before registering a Jianying project. When helping with capture conventions, read [shooting-guide.md](references/shooting-guide.md), [filename-guide.md](references/filename-guide.md), and [wiki-format.md](references/wiki-format.md).

## Failure Handling

Use only the multilingual faster-whisper `small` model. Do not substitute `tiny`. If `small` is missing or incomplete, stop speech analysis and show the one-command `scripts/download-model.ps1` or `scripts/download-model.sh` repair. For other recognition or OCR failures, preserve all media, use remaining evidence, and record the fallback in `review.md`. If FFmpeg is absent, still emit the plan, SRT, FCPXML, and draft candidate; omit the preview. If Jianying encryption or registration fails, preserve the staging draft, diagnostics, SRT, FCPXML, and `edit-plan.json`; never replace, downgrade, or uninstall the user's Jianying automatically.
