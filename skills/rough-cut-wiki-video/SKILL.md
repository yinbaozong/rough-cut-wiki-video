---
name: rough-cut-wiki-video
description: Create editable rough cuts for any step-by-step tutorial from MP4/MOV footage plus pasted procedure text or a text/Markdown guide. Use for how-to videos, assembly or repair, crafts, cooking, product demonstrations, workplace procedures, training, unboxing, speech-cue trimming, filename ordering, procedure-grounded captions, SRT/FCPXML export, review reports, or native encrypted Jianying 10/11 drafts on Windows, including fixing drafts that do not appear on the Jianying homepage.
---

# Wiki Video Rough Cut

Turn an ordered procedure and a footage folder into a non-destructive tutorial rough-cut package. Accept procedure text pasted into the conversation or a local UTF-8 text/Markdown file. Prefer local speech evidence, fall back to filenames, preserve every take, and use the supplied procedure—not improvised narration—as the factual source for captions.

## Workflow

1. Ask for the footage directory and ordered procedure. Accept either text pasted directly into the conversation or a local UTF-8 text/Markdown file; never require an `.md` file when pasted text is available. Do not fetch a URL unless the user explicitly asks. Save pasted text unchanged as the job's `wiki-source.md` before invoking the CLI.
2. Treat only ordered, filmed actions as timeline steps. Do not ask the user to add tool lists, preparation sections, background, or theory that was not filmed. Prefer `Step 1/2/3`, `步骤一/二/三`, or a numbered list. Keep essential cautions inside the action where they apply.
3. Locate this skill directory from the loaded `SKILL.md`; never assume a `.codex`, `.claude`, or `.cursor` path.
4. Run the capability check:

   ```powershell
   python scripts/roughcut.py doctor
   ```

5. Run analysis. Use `auto` unless the user requests filename-only processing. In auto mode, extract the audio track first, transcribe with word timestamps, and test whether the spoken label is related to a procedure step before considering the filename:

   ```powershell
   python scripts/roughcut.py run --media "E:\footage" --wiki "E:\job\wiki.md" --output "E:\job\output" --mode auto --preview
   ```

6. Inspect `review.md`, `edit-plan.json`, representative evidence, and warnings. Improve `wiki-steps.json` or `edit-plan.json` only when the footage/procedure evidence supports the change. Never invent quantities, objects, ingredients, parts, directions, or safety claims.
7. Re-run exporters after a manual plan change (currently use `run` for a full rebuild). Keep ambiguous or conflicting footage and mark it `待确认`; never silently drop input media.
8. On Windows, create a native Jianying 10/11 project from `edit-plan.json` with the `jianying10` command. First omit `--user-data` and validate in a staging directory. Before adding `--user-data` to register the real project, require Jianying to be fully closed. The exporter must encrypt both draft JSON files with the newest valid local `videoeditor.dll`, back up `root_meta_info.json`, and register a matching homepage entry. Never replace an existing draft unless the user explicitly authorizes it.

## Evidence Rules

Use this priority: user corrections; procedure-related post-start spoken label; meaningful filename and part number; procedure order/OCR/visual context for review only. A camera filename such as `DJI_0001` is not a label. If speech is empty or unrelated to every procedure step, try the filename. If neither provides procedure-related evidence, never guess and never rename the original media: preserve the whole clip at the timeline end, set `status: unmatched`, use edit-plan/FCPXML display name `待确认（reason）— original-name`, add exact review-track text `待确认` to editor exports, and explain the missing evidence in `review.md`. Continue exporting the other footage. Preserve repeated takes and order explicit parts before recording time. List unshot procedure steps only in the report.

Start cues are `321开始`, `三二一开始`, `321走`, or isolated `开始`/`走`. End cues are isolated `OK`, `过`, `可以`, `好了`, or `结束`. Do not trim phrase-internal words such as `可以安装` or `开始拆卸`. File end is a valid take ending.

## Captions and Outputs

Create formal captions from the supplied procedure, lightly polishing syntax for natural reading. Keep names, counts, directions, and warnings stated in the steps. Use two independently removable tracks: `文档字幕` and exact text `待确认`. Keep original audio and original 4K files untouched.

The output contract and JSON field definitions are in [schemas.md](references/schemas.md). Read [usage.md](references/usage.md) for platform/setup details and [jianying10.md](references/jianying10.md) before registering a Jianying project. When helping with capture conventions, read [shooting-guide.md](references/shooting-guide.md), [filename-guide.md](references/filename-guide.md), and [wiki-format.md](references/wiki-format.md). When evaluating local recognition or considering a cloud ASR provider, read [speech-recognition.md](references/speech-recognition.md) and test representative user audio before recommending payment.

## Failure Handling

Use only the multilingual faster-whisper `small` model. Do not substitute `tiny`. If `small` is missing or incomplete, stop speech analysis and show the one-command `scripts/download-model.ps1` or `scripts/download-model.sh` repair. For other recognition or OCR failures, preserve all media, use remaining evidence, and record the fallback in `review.md`. If FFmpeg is absent, still emit the plan, SRT, FCPXML, and draft candidate; omit the preview. If Jianying encryption or registration fails, preserve the staging draft, diagnostics, SRT, FCPXML, and `edit-plan.json`; never replace, downgrade, or uninstall the user's Jianying automatically.
