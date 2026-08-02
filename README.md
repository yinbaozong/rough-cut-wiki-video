# rough-cut-wiki-video

[English](README.md) | [简体中文](README.zh-CN.md)

[![Tests](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml/badge.svg)](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml)

`rough-cut-wiki-video` is a portable Agent Skill that turns a folder of MP4/MOV footage and an ordered procedure into an editable tutorial-video rough cut. It works across step-by-step content such as assembly and repair, crafts, cooking, product demonstrations, workplace procedures, training, unboxing, and other practical how-to videos. It is not tied to 3D printing or any single subject.

The Skill analyzes spoken take markers, short spoken step labels, filenames, procedure order, optional OCR, and media timing. It keeps the original 4K files untouched and produces an edit plan, editable captions, SRT, FCPXML, a review preview, and—on Windows—a native encrypted Jianying/CapCut China desktop draft with real source cut points.

## Contents

- [What it produces](#what-it-produces)
- [Supported platforms](#supported-platforms)
- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [How to record footage](#how-to-record-footage)
- [How to provide the procedure](#how-to-provide-the-procedure)
- [Matching and edit rules](#matching-and-edit-rules)
- [Jianying 10/11 editable drafts](#jianying-1011-editable-drafts)
- [Final Cut Pro workflow](#final-cut-pro-workflow)
- [Speech model](#speech-model)
- [Command reference](#command-reference)
- [Output reference](#output-reference)
- [Troubleshooting](#troubleshooting)
- [Privacy, safety, and limitations](#privacy-safety-and-limitations)
- [Development](#development)

## What it produces

- Removes spoken start markers such as `三二一开始`, `321开始`, `321走`, and an isolated `开始`.
- Removes isolated end markers such as `OK`, `过`, `可以`, `好了`, and `结束`.
- Does not confuse normal phrases such as `开始拆卸` or `可以安装` with take markers.
- Splits multiple takes recorded in one file.
- Can split adjacent procedure steps when the speaker says `下一步，移除支架`.
- Matches short labels such as `安装侧板` or `移除支架` to more detailed written steps.
- Orders clips by procedure step, explicit part number, and recording time.
- Keeps repeated takes instead of silently choosing one.
- Generates polished teaching captions from the supplied procedure, not from casual spoken wording.
- Creates separate `文档字幕` and `待确认` text tracks.
- Keeps unmatched footage at the end and reports missing procedure steps.
- Preserves the original audio and references the original MP4/MOV files.

## Supported platforms

| Platform | Analysis | SRT | FCPXML | Review preview | Native Jianying draft |
| --- | --- | --- | --- | --- | --- |
| Windows | Yes | Yes | Yes | Yes | Yes, Jianying 10/11 |
| macOS | Yes | Yes | Yes | Yes | Experimental only; use FCPXML for Final Cut Pro |
| Linux | Yes | Yes | Yes | Yes | No desktop integration |

The Skill format is shared by Codex, Claude Code, OpenCode, and Cursor. The scripts do not assume a `.codex`, `.claude`, or `.cursor` installation path.

## Installation

### 1. Install the Skill for your agents

Node.js 18+ is required for the cross-agent installer.

```powershell
npx skills add https://github.com/yinbaozong/rough-cut-wiki-video `
  --skill rough-cut-wiki-video `
  --agent codex claude-code opencode cursor `
  --global --copy --yes
```

The shared installation is normally placed in `~/.agents/skills/rough-cut-wiki-video`. Agent-specific directories may also be created by the installer.

### 2. Install runtime dependencies

Windows full setup:

```powershell
cd "$HOME\.agents\skills\rough-cut-wiki-video"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Profile full
```

macOS/Linux full setup:

```bash
cd ~/.agents/skills/rough-cut-wiki-video
chmod +x scripts/setup.sh scripts/download-model.sh
./scripts/setup.sh full
```

The full profile installs:

- `faster-whisper` for local multilingual speech recognition;
- the multilingual `small` speech model;
- `RapidOCR` and ONNX Runtime for optional frame text evidence;
- the pinned high-version `pyJianYingDraft` fork used for Jianying encryption and registration;
- FFmpeg/ffprobe detection. On Windows, the script prints a `winget` command if FFmpeg is missing.

Use `-Profile core` or `./scripts/setup.sh core` only when you deliberately want filename-only processing without speech recognition.

### 3. Verify the installation

```powershell
.\.venv\Scripts\python.exe .\scripts\roughcut.py doctor --json
```

## Quick start

The most convenient workflow is to ask your agent:

```text
Use rough-cut-wiki-video.
Footage: E:\My tutorial footage
Procedure:
Step 1: Open the cover carefully and keep the cable clear.
Step 2: Press the latch and remove the old module vertically.
Step 3: Align the replacement module, insert it gently, and close the latch.
Create an editable rough cut and a Jianying draft.
```

You can paste the ordered steps directly into the conversation, as above. A local plain-text or Markdown file is also accepted:

```text
Use rough-cut-wiki-video.
Footage: E:\My tutorial footage
Procedure file: E:\My tutorial footage\steps.txt
Create an editable rough cut and a Jianying draft.
```

You can also run the analyzer directly:

```powershell
$Skill = "$HOME\.agents\skills\rough-cut-wiki-video"
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" run `
  --media "E:\My shoot\footage" `
  --wiki "E:\My tutorial footage\steps.txt" `
  --output "E:\My shoot\rough-cut-output" `
  --mode auto `
  --preview
```

When text is pasted into the conversation, the agent saves it unchanged as UTF-8 `wiki-source.md` inside the job before running the command. Direct CLI use still accepts a file through `--wiki`; that file may be `.txt`, `.md`, or another UTF-8 text export. Web scraping is not required.

## How it works

The automatic pipeline is intentionally evidence-driven:

1. **Read the procedure:** accept steps pasted into the conversation or loaded from a UTF-8 text/Markdown file, then parse the ordered filmed actions, names, quantities, directions, and step-specific cautions.
2. **Probe every media file:** use ffprobe to record duration, audio presence, frame size, and stream information. Every discovered MP4/MOV must enter the plan or an actionable report.
3. **Extract audio first:** in `auto` mode, FFmpeg creates a temporary mono 16 kHz WAV track. The original video is never changed.
4. **Transcribe locally:** faster-whisper `small` produces multilingual word timestamps. Start/end markers define source cut points and the short post-start phrase becomes the spoken step label.
5. **Check procedure relevance:** the spoken label is scored against every written step. Empty speech, filler, or speech unrelated to the procedure is rejected as matching evidence.
6. **Use the filename only when needed:** if no procedure-related spoken label exists, parse the filename for an action, object, sequence, and part number, then score that label against the procedure.
7. **Keep unmarked footage for review:** if neither speech nor filename relates to the procedure, do not guess and do not rename the source file. Keep the full clip at the end of the timeline, label it `待确认（无报幕且无有效文件名）— original-name`, and explain the reason in `review.md`.
8. **Build the timeline:** select source in/out ranges, order clips by procedure step and part number, preserve repeated takes, and add review markers for conflicts.
9. **Write captions and exports:** generate procedure-grounded captions, SRT, FCPXML, JSON checkpoints, and an optional review preview.
10. **Create editor-native projects:** Final Cut Pro uses FCPXML. Windows Jianying uses a separate encrypted-draft and homepage-registration stage.

This design prevents a silent but dangerous failure mode: arranging unlabeled footage purely because it happened to be recorded near a written step.

## How to record footage

### Recommended take format

Say one short line before the action:

```text
三二一开始，安装侧板，第1段
```

Perform the action. After it is complete, pause for about half a second and say:

```text
OK
```

For a continuation:

```text
三二一开始，安装侧板，第2段
```

Stopping the camera without an end marker is valid; the file end becomes the take end.

### Changing steps inside one recording

If one file contains two adjacent actions, say a short transition before the next action:

```text
下一步，移除支架
```

### What to say

Use only the procedure-level action name and an optional part number:

- `安装背板，第1段`
- `搅拌面糊`
- `折叠纸张，第2段`
- `包装产品`

You do not need to narrate every hand movement. The Skill expands the final caption from the supplied procedure.

### What to avoid

- Do not talk about unrelated topics between the start marker and the action label.
- Do not use several possible step names in one label.
- Do not say an end marker in the middle of an explanation as an isolated word.
- Avoid long self-corrections such as “this is probably the side panel—no, maybe the rear panel.” Stop and record a new take instead.
- Do not rely on `DJI_0001`, `C0001`, or timestamp-only camera filenames as labels.

### Filename backup mode

If speech recognition is unavailable or you prefer silent recording, rename files approximately like this:

```text
010_准备面糊_01.mov
010_准备面糊_02.mov
020_倒入模具_01.mp4
```

The label can be short. The agent matches it semantically to the detailed written step. Explicit part numbers are sorted before recording time.

## How to provide the procedure

The procedure—whether pasted into the conversation or supplied as a file—is the factual source for captions. Spoken labels are evidence for matching only.

### Recommended structure

```text
Step 1: Remove the retaining screw, then carefully lift the cover without pulling the cable.
Step 2: Open the latch and remove the old module vertically.
Step 3: Align the replacement module, place it gently, and close the latch.
Step 4: Reinstall and tighten the retaining screw.
```

Chinese markers such as `步骤一`, `步骤二`, and `步骤三`, or a normal numbered list such as `1.`, `2.`, and `3.`, work equally well.

### Procedure rules

- Include only actions that were filmed and should appear on the timeline.
- Write the steps in the intended viewing order: Step 1, Step 2, Step 3, and so on.
- Keep one main action per numbered step. Several tightly coupled motions may stay together.
- State useful names, quantities, directions, and cautions in the step where they matter.
- You do not need separate tools, preparation, background, introduction, or theory sections when those items were not filmed. They are not timeline steps.
- Put an essential warning into the relevant action, for example: “carefully lift the cover without pulling the cable.”
- If a tutorial has alternative paths, provide only the path shown in this footage, or clearly label each filmed branch.
- Avoid references such as “do this” or “install it” when the part name can be stated.
- Do not add unsupported marketing claims or safety conclusions.
- Paste plain text directly, or provide a UTF-8 `.txt`, `.md`, or exported Wiki text file. Chinese paths and content are supported.

The agent may improve sentence flow for reading, but it must not invent objects, ingredients, parts, counts, values, directions, or safety claims that are absent from the supplied procedure.

## Matching and edit rules

Evidence priority:

1. User-provided corrections.
2. Wiki-related spoken labels after a start marker.
3. Meaningful filenames and explicit part numbers, only when speech is empty or unrelated.
4. Wiki order, OCR, visual context, and neighboring steps for review support—not as a substitute when both speech and filename are unusable.

Timeline behavior:

- Clips are ordered by Wiki step.
- All repeated takes are retained.
- `第1段`, `第2段`, `01`, `02`, and similar suffixes control order within a step.
- Ambiguous boundaries receive a `待确认` marker.
- Filename/speech conflicts are reported instead of silently hidden.
- Unmatched media is appended to the timeline.
- Unrecorded Wiki steps appear in `review.md`; no fake placeholder clip is inserted.

## Jianying 10/11 editable drafts

Copying an arbitrary folder into the Jianying drafts directory is not sufficient. Current Jianying versions require:

1. a native `draft_content.json` timeline;
2. a matching `draft_meta_info.json` project ID;
3. encryption produced by the locally installed `videoeditor.dll`;
4. a homepage entry in `root_meta_info.json` with the correct draft path and ID.

This Skill implements all four requirements. It also handles an updater removing an older version folder: if the requested DLL is missing, it searches sibling version directories and selects the newest valid installation.

The current implementation has been validated with Jianying `10.6.0.14057` and `11.1.0.14287`. Other 10.x/11.x builds are handled on a best-effort basis by using that installation's own DLL. Future major versions may change the private draft format and require a Skill update.

### Safe two-stage workflow

Generate an encrypted staging draft without touching the homepage index:

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" jianying10 `
  --plan "E:\My shoot\rough-cut-output\edit-plan.json" `
  --drafts "E:\My shoot\jianying-staging" `
  --name "Compatibility test"
```

Then save your work and fully exit Jianying. Register the final project:

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" jianying10 `
  --plan "E:\My shoot\rough-cut-output\edit-plan.json" `
  --drafts "D:\software\JianyingPro Drafts" `
  --name "Wiki rough cut" `
  --user-data "$env:LOCALAPPDATA\JianyingPro\User Data"
```

Use `--install-dir "D:\software\JianyingPro"` only when automatic discovery cannot locate a custom installation.

Safety behavior:

- Registration is refused while `JianyingPro.exe` is running.
- The homepage index is backed up to `.roughcut-backups` before registration.
- Staging uses an isolated temporary User Data tree and cannot leak a card into the real homepage.
- Existing draft names are not overwritten unless `--allow-replace` is explicitly supplied.
- Original videos and existing projects are never modified.

## Final Cut Pro workflow

Final Cut Pro uses the portable `timeline.fcpxml` output and does not need Jianying encryption or homepage registration.

1. Run the normal analysis command and keep the original MP4/MOV files in their original locations.
2. In Final Cut Pro, choose **File → Import → XML**.
3. Select `timeline.fcpxml` from the output directory.
4. Open the imported event/project named `Wiki Rough Cut`.
5. Review source cut points and reconnect media if the source folder was moved after analysis.
6. Edit or delete the `文档字幕` and `待确认` title lanes independently.
7. Optionally import `wiki-subtitles.srt` through your preferred caption workflow when you need caption roles rather than title clips.

FCPXML references the original media. It does not contain a rendered copy, so moving or renaming source files after generation can require relinking. The 720p `review-preview.mp4` is for review only and should not replace the editable XML timeline.

## Speech model

Only the multilingual `faster-whisper small` model is supported. A lower-quality tiny fallback is intentionally not included.

Recognition accuracy is not a fixed percentage. It depends heavily on microphone distance, background noise, speech volume, accent, and domain terms. For this Skill, the important measurement is whether a short spoken label selects the correct procedure step—not whether every casual word is transcribed perfectly. Before paying for a cloud API, test 10–20 representative clips with the local model, including several quiet, noisy, muffled, and terminology-heavy examples.

If local recognition is weak, first shorten the label, speak it immediately after the start cue, move the microphone closer, and use a meaningful filename as independent evidence. For difficult dialects or specialist vocabulary, a cloud ASR service with hotwords or prompt context can be added later. See [speech-recognition.md](skills/rough-cut-wiki-video/references/speech-recognition.md) for the evaluation and cloud decision guide.

Full setup downloads the model once into:

```text
skills/rough-cut-wiki-video/assets/models/faster-whisper-small/
```

If it is missing or incomplete, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download-model.ps1
```

Official model page: [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)

The model is not committed to Git because it is roughly 486 MB and contains a file larger than GitHub's normal 100 MiB file limit. The one-command installer downloads it from the official source and verifies the required files.

## Command reference

### Capability report

```powershell
python scripts/roughcut.py doctor --json
```

### Analyze and export

```text
roughcut.py run
  --media PATH
  --wiki PROCEDURE_FILE
  --output PATH
  [--mode auto|filename]
  [--model small]
  [--preview]
  [--corrections corrections.json]
  [--reuse-takes]
  [--no-probe]
```

`auto` uses speech and falls back to other evidence for ordinary recognition failures. A missing `small` model is a setup error and prints the one-command repair instruction. `filename` skips speech and keeps the full duration of each file.

### Generate/register Jianying

```text
roughcut.py jianying10
  --plan edit-plan.json
  --drafts DRAFT_ROOT
  --name PROJECT_NAME
  [--install-dir JIANYING_VERSION_OR_ROOT]
  [--user-data JIANYING_USER_DATA]
  [--allow-replace]
```

Omit `--user-data` for staging. Add it only after Jianying has fully exited.

## Output reference

```text
output/
├── wiki-source.md
├── wiki-steps.json
├── takes.json
├── edit-plan.json
├── review.md
├── wiki-subtitles.srt
├── review-subtitles.srt
├── timeline.fcpxml
└── review-preview.mp4
```

- `wiki-source.md`: exact saved procedure input, whether it was pasted or loaded from a file.
- `wiki-steps.json`: normalized action steps and caption facts.
- `takes.json`: media probes, labels, timestamps, OCR evidence, and warnings.
- `edit-plan.json`: application-independent source ranges, ordering, captions, and match status.
- `review.md`: missing steps, ambiguous clips, fallbacks, and timeline summary.
- `wiki-subtitles.srt`: formal procedure-derived captions.
- `review-subtitles.srt`: `待确认` markers.
- `timeline.fcpxml`: editable interchange for Final Cut Pro and compatible editors.
- `review-preview.mp4`: optional 720p review render; not the editable master.

The analysis command deliberately does not create a folder named `jianying-draft`; a plaintext look-alike is easy to copy incorrectly and will not appear on current Jianying homepages. Use the separate `jianying10` command to create a real encrypted and registered project.

## Troubleshooting

### The Jianying project does not appear

- Confirm you registered with `--user-data`, not only copied the staging folder.
- Confirm `root_meta_info.json` contains the project path.
- Fully exit and reopen Jianying.
- Do not copy the outer analysis output directory into the drafts directory.

### The project card appears but does not open

- Check that `draft_content.json` and `draft_meta_info.json` were encrypted with the DLL from the currently installed Jianying.
- Pass the installation root with `--install-dir`; the tool will select the newest version subfolder.
- Keep the diagnostic output and restore the index backup if necessary.

### The speech model is missing

Run `scripts/download-model.ps1` or `scripts/download-model.sh`. Do not substitute `tiny`; it is intentionally unsupported for this workflow.

### Speech labels are wrong

- Use a shorter label immediately after the start marker.
- Rename the file with an approximate action name and part number.
- Add a corrections JSON file for authoritative overrides.
- Keep the Wiki's part terminology consistent with the spoken label.

### No audio or filename-only workflow

Use `--mode filename`. The entire source file is retained because spoken cut markers are unavailable.

### FFmpeg is missing

Windows:

```powershell
winget install --id Gyan.FFmpeg -e
```

Analysis can still produce a plan without FFmpeg when probing is disabled, but media timing and previews will be limited.

## Privacy, safety, and limitations

- Speech recognition and OCR run locally.
- No specific cloud model API is required.
- Original MP4/MOV files are read-only inputs.
- The tool performs a rough cut, not final editorial judgment.
- Visual-only actions with neither procedure-related speech nor a meaningful filename remain in the export at the timeline end, use a `待确认` marker, and are listed as unmarked footage in `review.md`; original files are never renamed.
- Jianying's private draft format can change; always keep SRT, FCPXML, and `edit-plan.json` as portable fallbacks.
- Review captions, safety statements, quantities, and installation directions before publishing.

## Development

Run tests:

```powershell
.\skills\rough-cut-wiki-video\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Validate the Skill package:

```powershell
python "$HOME\.codex\skills\.system\skill-creator\scripts\quick_validate.py" `
  .\skills\rough-cut-wiki-video
```

The repository is licensed under MIT. Third-party packages and models retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
