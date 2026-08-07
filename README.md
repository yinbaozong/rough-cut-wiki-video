# rough-cut-wiki-video

[English](README.md) | [简体中文](README.zh-CN.md)

[![Check](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml/badge.svg)](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml)

`rough-cut-wiki-video` is a portable Agent Skill that turns a folder of MP4/MOV footage and an ordered procedure into an editable tutorial-video rough cut. It works across step-by-step content such as assembly and repair, crafts, cooking, product demonstrations, workplace procedures, training, unboxing, and other practical how-to videos. It is not tied to 3D printing or any single subject.

The Skill analyzes spoken take markers, short spoken step labels, filenames, procedure order, and media timing. Speech is pinned to Simplified Chinese by default. Term repair runs after recognition in two layers: a conservative automatic pass, plus a pronunciation-aware pass that proposes homophone fixes for review rather than applying them. Frame extraction and OCR are disabled by design. It keeps the original 4K files untouched and produces an edit plan, editable captions, SRT, FCPXML, a review preview, and—on Windows—a native encrypted Jianying/CapCut China desktop draft with real source cut points.

## Contents

- [What it produces](#what-it-produces)
- [Supported platforms](#supported-platforms)
- [Installation](#installation)
- [Quick start](#quick-start)
- [One-command job script](#one-command-job-script)
- [How it works](#how-it-works)
- [Repository layout and algorithms](#repository-layout-and-algorithms)
- [How to record footage](#how-to-record-footage)
- [How to provide the procedure](#how-to-provide-the-procedure)
- [Optional inputs: glossary and corrections](#optional-inputs-glossary-and-corrections)
- [Two-layer term repair](#two-layer-term-repair)
- [Matching and edit rules](#matching-and-edit-rules)
- [Jianying 10/11 editable drafts](#jianying-1011-editable-drafts)
- [Final Cut Pro workflow](#final-cut-pro-workflow)
- [Speech model](#speech-model)
- [Command reference](#command-reference)
- [Output reference](#output-reference)
- [Troubleshooting](#troubleshooting)
- [Privacy, safety, and limitations](#privacy-safety-and-limitations)
- [License](#license)

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
- ONNX Runtime as a speech-runtime dependency;
- `pypinyin` for pronunciation comparison during term repair; pure Python, no compiled dependency;
- the pinned high-version `pyJianYingDraft` fork used for Jianying encryption and registration;
- FFmpeg/ffprobe detection. On Windows, the script prints a `winget` command if FFmpeg is missing.

Frame OCR was removed: it dominated runtime without changing match decisions.

Use `-Profile core` or `./scripts/setup.sh core` only when you deliberately want filename-only processing without speech recognition.

### 3. Verify the installation

```powershell
.\.venv\Scripts\python.exe .\scripts\roughcut.py doctor --json
```

A healthy report shows `ffmpeg`/`ffprobe` found, `faster_whisper` importable, the `small` model present, `pyJianYingDraft` importable, `frame_ocr: disabled`, and `pinyin_repair: True`.

### 4. First-run checklist

Do these once per machine, in this order:

1. Install the Skill and run the `full` setup profile above.
2. Make FFmpeg reachable. `winget install --id Gyan.FFmpeg -e`, or drop a portable build somewhere and pass `-FfmpegBin` to the job script so nothing is added to your PATH permanently.
3. Confirm `doctor` reports the `small` model as present. If it is missing, run `scripts/download-model.ps1`.
4. Windows only, and only if you want native drafts: install Jianying/CapCut China 10.x or 11.x normally and launch it once so it creates `%LOCALAPPDATA%\JianyingPro\User Data` and its drafts folder. Note where drafts live, typically `D:\Software\JianyingPro Drafts`.
5. Run one job with `-NoDraft` first and read `review.md`. This confirms recognition and matching before anything touches Jianying.
6. Run the same job without `-NoDraft`. The first draft triggers one staging validation, because no fingerprint has been recorded yet. Later runs skip it until Jianying or the writer library changes.

No Jianying account, license key, or online activation is involved. "Registering" here means writing an entry into Jianying's own local homepage index; see [Jianying 10/11 editable drafts](#jianying-1011-editable-drafts) for exactly what is written.

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

## One-command job script

`scripts/run-job.ps1` chains analysis, staging validation, and draft registration so a repeat shoot needs one line instead of three commands. It is Windows-only and must stay UTF-8 **with BOM**, otherwise Windows PowerShell 5.1 mis-parses the Chinese strings inside it.

```powershell
& "$Skill\scripts\run-job.ps1" -JobName tray-disassembly `
  -Media '\\nas\footage\tray' `
  -WikiText '移除底壳固定螺丝，取出底壳，安装底壳预锁紧固定螺丝，全部螺丝安装完成后再最终锁紧。' `
  -JobRoot 'D:\roughcut\jobs' `
  -Lexicon 'D:\roughcut\glossary.txt' `
  -FfmpegBin 'D:\roughcut\tools\ffmpeg\bin'
```

What it does, in order:

1. Creates `<JobRoot>\<JobName>\` with an `output\` subfolder, and prepends `-FfmpegBin` to `PATH` for this process only.
2. Materializes the procedure. `-WikiFile` is copied in as `wiki.md`; `-WikiText` is split on Chinese and ASCII commas, semicolons, and full stops into a numbered list, with the untouched original kept as a comment header. An existing `wiki.md` in the job folder is reused if neither is supplied.
3. Runs `roughcut.py run` with the recognition tuning flags, plus `--lexicon` and `--corrections` when those files exist. Prints the elapsed analysis time.
4. Stops here if `-NoDraft` is set, so you can read `review.md` before committing to a draft.
5. Stops if any term repair is still undecided, because the timeline can still move and a draft built now would be wasted. `-SkipLexiconReview` overrides this.
6. Compares the current Jianying fingerprint against `<JobRoot>\.roughcut-state\jianying-fingerprint.json`. On a mismatch, or with `-ForceStaging`, it builds a throwaway staging draft in the job folder, deletes it on success, and records the new fingerprint. A staging failure aborts before the homepage index is touched.
7. Refuses to continue while `JianyingPro.exe` is running, then registers the real draft named `<JobName>-roughcut` unless `-DraftName` overrides it.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `-JobName` | required | Job folder name and default draft name |
| `-Media` | required | Footage folder; UNC paths are supported |
| `-WikiText` / `-WikiFile` | one of them | Procedure as pasted text or as a file |
| `-JobRoot` | `.\jobs` | Where job folders and the fingerprint state live |
| `-Lexicon` | none | Glossary for post-recognition repair |
| `-Drafts` | `D:\Software\JianyingPro Drafts` | Jianying drafts root |
| `-UserData` | `%LOCALAPPDATA%\JianyingPro\User Data` | Homepage index location |
| `-FfmpegBin` | none | Prepend a portable FFmpeg to `PATH` for this run |
| `-Workers` | `6` | Parallel probe and audio-extraction workers |
| `-BatchSize` / `-ChunkLength` / `-CpuThreads` | `2` / `10` / auto | Recognition throughput tuning |
| `-ReuseTakes` | off | Reuse `takes.json` and skip recognition entirely |
| `-NoDraft` | off | Stop after analysis |
| `-ForceStaging` | off | Validate encoding even when the fingerprint matches |
| `-SkipLexiconReview` | off | Build the draft even with undecided term repairs |

Re-running a job after editing `wiki.md` or `corrections.json` is cheap with `-ReuseTakes`: recognition is the slow part, and matching plus export takes seconds.

## How it works

The automatic pipeline is intentionally evidence-driven:

1. **Read the procedure:** accept steps pasted into the conversation or loaded from a UTF-8 text/Markdown file, then parse the ordered filmed actions, names, quantities, directions, and step-specific cautions.
2. **Probe every media file:** use ffprobe to record duration, audio presence, frame size, and stream information. Every discovered MP4/MOV must enter the plan or an actionable report.
3. **Extract audio in parallel:** in `auto` mode, FFmpeg creates temporary mono 16 kHz WAV tracks concurrently. The original video is never changed.
4. **Transcribe locally:** faster-whisper `small` produces word timestamps with language pinned to `zh` by default. Start/end markers define source cut points and the short post-start phrase becomes the spoken step label.
5. **Check procedure relevance:** the spoken label is scored against every written step. Empty speech, filler, or speech unrelated to the procedure is rejected as matching evidence. Weakly matched takes get pronunciation-aware repair proposals for review instead of a silent rewrite.
6. **Use the filename only when needed:** if no procedure-related spoken label exists, parse the filename for an action, object, sequence, and part number, then score that label against the procedure.
7. **Keep unmarked footage for review:** if neither speech nor filename relates to the procedure, do not guess and do not rename the source file. Keep the full clip at the end of the timeline, set its edit-plan/FCPXML display label to `待确认（无报幕且无有效文件名）— original-name`, add the `待确认` review text track, and explain the reason in `review.md`.
8. **Build the timeline:** select source in/out ranges, order clips by procedure step and part number, preserve repeated takes, and add review markers for conflicts.
9. **Write captions and exports:** generate procedure-grounded captions, SRT, FCPXML, JSON checkpoints, and an optional review preview.
10. **Create editor-native projects:** Final Cut Pro uses FCPXML. Windows Jianying uses a separate encrypted-draft and homepage-registration stage.

This design prevents a silent but dangerous failure mode: arranging unlabeled footage purely because it happened to be recorded near a written step.

## Repository layout and algorithms

```text
skills/rough-cut-wiki-video/
├── SKILL.md
├── agents/openai.yaml
├── assets/*.schema.json
├── assets/models/faster-whisper-small/   (downloaded, not in Git)
├── references/*.md
└── scripts/
    ├── roughcut.py
    ├── run-job.ps1
    ├── setup.ps1 / setup.sh
    ├── download-model.ps1 / .sh
    └── roughcut/
        ├── core.py
        ├── media.py
        ├── lexicon.py
        ├── exporters.py
        ├── pipeline.py
        └── jianying10.py
```

### Skill definition and docs

| File | Role |
| --- | --- |
| `SKILL.md` | The only file the agent reads to decide whether and how to use this Skill. Holds the trigger description, the workflow it must follow, and the rules it must not break. |
| `agents/openai.yaml` | Agent metadata for installers that expect a manifest. |
| `assets/*.schema.json` | JSON Schemas for a wiki step, a take's evidence, and an edit segment. Useful for validating output or building your own consumer. |
| `references/*.md` | Deep-dive docs loaded on demand: `usage.md` for every flag, `schemas.md` for field-level output structure, `jianying10.md` for draft internals, `filename-guide.md`, `shooting-guide.md`, and `speech-recognition.md`. |

### Scripts

`roughcut.py` is the CLI front end with three subcommands: `doctor` reports environment capability, `run` performs analysis and export, and `fingerprint` prints the Jianying/writer signature. It only parses arguments and delegates.

`pipeline.py` orchestrates one `run`: read the procedure, batch-analyze media, apply corrections, build the plan, then write every output file. It is the place to look for what gets written and in what order.

`media.py` handles everything that touches media or the speech model.

- Discovery walks the folder for `.mp4`, `.mov`, `.m4v`, `.avi`, `.mkv`.
- `ffprobe` reads duration, audio presence, and stream info. A file that cannot be probed falls back to placeholder metadata and a warning rather than aborting the batch.
- Audio extraction runs FFmpeg concurrently through a thread pool into temporary mono 16 kHz WAVs. This is pure I/O wait, so parallelism helps a lot; on a 16-file batch it cut extraction from about 93 s to 16 s.
- Transcription loads the model exactly once via `lru_cache` and wraps it in faster-whisper's `BatchedInferencePipeline`. Language is pinned to `zh`, VAD filtering is on, and word timestamps are requested. `beam_size` deliberately stays at the library default: greedy decoding turned `移除底壳` into `一处地壳` for almost no time saved.
- Recognition remains the dominant cost. It is roughly a fixed per-file overhead on CPU, so total time scales with file count more than with total duration.

`core.py` holds the text logic and no I/O.

- Traditional characters are folded to Simplified through a 265-entry translation table before any comparison, because Whisper freely emits `裝`/`殼`/`絲` while the procedure is written in Simplified.
- Take segmentation scans word timestamps for start markers (`三二一开始`, `321走`, a bare `开始`) and isolated end markers (`OK`, `过`, `可以`, `好了`, `结束`). Matching is anchored to a whole utterance, so `开始拆卸` and `可以安装` are not mistaken for markers. The short phrase right after a start marker becomes the spoken step label.
- Filename parsing extracts a sequence number, action label, and part number, and rejects camera defaults such as `DJI_0001` or `C0001` as meaningless.
- Matching scores a label against a step with character bigrams plus single action characters, minus a small stop list. The score is `overlap / min(len(a), len(b))` with a `0.34` threshold. Qualified steps are then ranked by **absolute shared-term count** before score, which is what stops a short step like `安装底壳` from stealing a take that belongs to `安装底壳固定螺丝并预锁紧` — the short step would otherwise win on ratio alone because the take contains all of it.

`lexicon.py` repairs recognized terms after transcription, in two layers described under [Two-layer term repair](#two-layer-term-repair). Layer 1 compares characters and applies automatically; layer 2 adds pronunciation and only proposes. Both slide windows of length *n−1*, *n*, and *n+1* and score with `difflib.SequenceMatcher`, and neither ever inserts or deletes text, so a wrong glossary cannot lengthen a caption. Running after decoding is deliberate: Whisper's `hotwords` truncate silently at 223 tokens, so a real glossary cannot be passed that way, whereas post-repair has no size ceiling and costs milliseconds.

`exporters.py` writes `wiki-subtitles.srt`, `review-subtitles.srt`, `timeline.fcpxml`, and the optional 720p preview render. FCPXML references original media by path and carries `文档字幕` and `待确认` as separate title lanes.

`jianying10.py` builds the native draft. It discovers the installation from the registry uninstall keys, falling back to parsing `UninstallString` when `InstallLocation` is empty, and picks the newest valid version folder when an updater has removed the one you named. `fingerprint()` hashes the registry version, install path, `videoeditor.dll` size and mtime, and the writer library version — that is the value gating staging validation. Draft creation writes a real timeline, matches the project ID across `draft_content.json` and `draft_meta_info.json`, encrypts through the local DLL, backs up `root_meta_info.json`, and adds the homepage entry.

### Why a local DLL is involved

Jianying 10/11 no longer stores drafts as plaintext JSON; `draft_content.json` is encrypted. `videoeditor.dll` inside your Jianying installation is a signed 63 MB Windows binary that exports the encrypt/decrypt routines. The writer library loads it with `ctypes.WinDLL`, marshals MSVC `std::string` structures, and calls those exports in an isolated subprocess by default. Nothing is reverse-engineered or reimplemented, and no key is shipped — the Skill borrows your own installation's code, which is why the draft always matches your exact Jianying build and why a version change is worth revalidating.

### Setup and helper scripts

`setup.ps1` / `setup.sh` create `.venv` and install dependencies. The `full` profile adds faster-whisper, ONNX Runtime, the pinned `pyJianYingDraft` fork, and the `small` model; `core` gives filename-only processing with no speech recognition. `download-model.ps1` / `.sh` fetch and verify the model separately, since it is about 486 MB and exceeds GitHub's per-file limit. `run-job.ps1` is the end-to-end wrapper described above.

### Files not in Git

`assets/models/faster-whisper-small/` and `.venv/` are created by setup. Job folders, `.roughcut-state/`, and `.roughcut-backups/` are runtime data and belong outside the repository.

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

## Optional inputs: glossary and corrections

Both are optional, hand-written, and never generated by the pipeline. Neither is required for a normal run.

### Glossary (`--lexicon`)

A plain UTF-8 text file, one term per line. Reusable across every job, so it is worth maintaining long-term.

```text
热端风扇
底壳固定螺丝
挤出机组件
```

Terms shorter than three characters and lines without Chinese characters are ignored, because short fuzzy hits are more often coincidence than a real correction. A large glossary is safe: cost is linear in term count and stays in the millisecond range.

A glossary is not the only repair vocabulary, and not the leading one: **the procedure's own wording takes priority**. A glossary describes a whole product line, so it frequently lacks the exact phrase being filmed. On real footage a cue misheard as 抵扣布丁螺丝 could only be recovered from the procedure's own 底壳固定螺丝, which was absent from all 530 glossary entries. Repair therefore still works with no glossary at all.

### Corrections (`--corrections`)

A JSON file keyed by source filename, used as the highest-priority evidence when recognition simply cannot be salvaged for one clip. It is per-job and disposable — once that footage is cut, the file has no further use and should not be carried into the next job.

```json
{
  "C9451.MP4": {
    "manual_step_id": "step-005",
    "manual_label": "再次锁紧底壳固定螺丝"
  }
}
```

`manual_step_id` pins the clip to a step outright. `manual_label` supplies a replacement label that goes through normal scoring. `run-job.ps1` picks up `corrections.json` from the job folder automatically when present.

Reach for it only after the cheaper fixes: re-record a shorter label, rename the file with a meaningful action name, or add the misheard term to the glossary. A correction fixes exactly one clip in one job; a glossary entry fixes that term everywhere, forever.

## Two-layer term repair

Chinese cue-recognition errors are overwhelmingly homophones, and that single fact drives the whole design.

### Why character similarity is not enough

Character distance is blind to homophones. On the real errors, the overlap is literally zero:

| Span → term | Character | Pinyin | Reality |
| --- | --- | --- | --- |
| 抵扣布丁 → 底壳固定 | 0.00 | 0.76 | should be fixed |
| 顶核 → 底壳 | 0.00 | 0.60 | should be fixed |
| 半动 → 安装 | 0.00 | 0.53 | should be fixed |
| 热端风扇 → 冷端风扇 | 0.75 | 0.87 | must never be changed |
| 紧抵扣 → 进气口 | 0.00 | 0.88 | must never be changed |

### Why pronunciation similarity is not enough either

Look at the last two rows. The semantically opposite pair 热端风扇/冷端风扇 (hot-end vs cold-end fan) scores 0.87, higher than the correct repair 抵扣布丁 → 底壳固定 at 0.76. **No threshold separates them.** Applying by score alone would eventually rewrite "hot end" as "cold end" and invert the caption's meaning.

Pronunciation is therefore good at *finding* candidates and incapable of *deciding* them.

### How the layers divide the work

**Layer 1 (Python, automatic)** applies only repairs that are already close character-for-character, at 0.75 (0.85 for three-character terms). That band is safe unattended.

**Layer 2 (agent review, never automatic)** adds pronunciation comparison for recall and writes its findings to `lexicon-review.json` for a decision. The reviewer has what a score cannot: the procedure text and its meaning. It sees immediately that the steps say 底壳固定螺丝 and never mention 底座锁定螺丝, and that a cue saying 再次锁紧 (tighten again) cannot possibly be 移除 (remove).

Only takes matched below `--review-confidence` (0.70) produce proposals, since a confidently matched take has nothing worth changing, and proposals that land on the same step are dropped because they cannot alter the cut. On the real 12-take shoot those two filters reduced the review to 3 takes and 5 candidates.

### What it actually recovered

Real take C9451 was heard as `再次锁紧抵扣布丁螺丝1`, matched no step at all, and could only be parked at the end of the timeline as `待确认`. Layer 2 offered three candidates:

| Suggestion | Pinyin | Resulting step | Confidence |
| --- | --- | --- | --- |
| 抵扣布丁螺丝 → 底壳固定螺丝 | 0.84 | step-004 安装底壳固定螺丝并预锁紧 | 0.75 |
| 抵扣布丁螺丝 → 底座锁定螺丝 | 0.79 | step-004 | 0.46 |
| 紧抵扣布丁螺丝 → 移除底壳固定螺丝 | 0.72 | step-001 移除底壳固定螺丝 | **1.00** |

Note the third: it reaches a perfect 1.00, higher than the correct answer's 0.75. **Picking by score picks wrong.** The cue explicitly says 再次锁紧, so 移除 is semantically impossible — precisely the judgement that requires reading the procedure. Accepting the first entry turned this clip from unmatched into a correct match.

### The confirmation loop

```powershell
# 1. After analysis, set every decision to accept or reject in
#    <output>\lexicon-review.json, optionally with a decision_note.
# 2. Re-run with --reuse-takes; recognition is skipped, so this takes seconds.
```

Two properties matter:

- **Reversible.** Repairs are re-applied from the pre-review text on every run, so flipping an entry back to `reject` restores the original transcript and leaves no residue.
- **Decisions persist.** A decided proposal is kept in the file even when it no longer regenerates. Without that, accepting a repair removes the misheard span it was found by, and the next run would silently revert it.

`run-job.ps1` stops before building a draft while proposals are undecided, because the timeline can still move and the draft would be wasted. Use `-SkipLexiconReview` to override. Without `pypinyin` installed, repair degrades to character comparison only and says so in `review.md`.

## Matching and edit rules

Evidence priority:

1. User-provided corrections.
2. Wiki-related spoken labels after a start marker.
3. Meaningful filenames and explicit part numbers, only when speech is empty or unrelated.
4. Wiki order and neighboring steps for review support—not as a substitute when both speech and filename are unusable. Frame OCR is disabled. When several steps qualify, prefer the one sharing more terms so a short step cannot steal a more specific take.

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

Staging is only needed when Jianying or the writer library changes. Check the fingerprint first:

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" fingerprint
```

If the fingerprint is unchanged, register directly. Otherwise generate an encrypted staging draft without touching the homepage index:

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

### What registration actually does

"Registration" is entirely local. There is no account, license, or network call. Adding `--user-data` makes the tool:

1. Create `<drafts>\<name>\` containing `draft_content.json` (the timeline), `draft_meta_info.json` (project ID and media references), and the auxiliary files Jianying expects.
2. Encrypt both JSON files by calling `videoeditor.dll` from your installed Jianying, so the bytes match what that exact build can read.
3. Copy `<user-data>\...\root_meta_info.json` into `<drafts>\.roughcut-backups` before modifying it.
4. Append an entry to that index with the draft's path, project ID, name, and timestamps. This index is what Jianying's homepage lists — a folder that is not in it stays invisible no matter how correct its contents are.

Without `--user-data`, steps 1 and 2 still happen but 3 and 4 do not, which is exactly what makes staging safe.

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

Speech defaults to `--language zh`. Auto-detection is slower and can misread short, noisy cues as other languages. Pass `--language ""` only when the footage is not Chinese. Traditional characters in the transcript are normalized to Simplified for matching.

If local recognition is weak, first shorten the label, speak it immediately after the start cue, move the microphone closer, and use a meaningful filename as independent evidence. Pass `--lexicon` with one term per line for conservative post-recognition repair; do not use Whisper `hotwords`, which silently truncate at 223 tokens. Homophone errors are invisible to character comparison and are handled by the reviewed pinyin layer in [Two-layer term repair](#two-layer-term-repair). For difficult dialects or specialist vocabulary, a cloud ASR service can still be evaluated later. See [speech-recognition.md](skills/rough-cut-wiki-video/references/speech-recognition.md).

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
  [--language zh]
  [--workers 6]
  [--batch-size 2]
  [--chunk-length 10]
  [--cpu-threads N]
  [--lexicon glossary.txt]
  [--review-confidence 0.70]
  [--preview]
  [--corrections corrections.json]
  [--reuse-takes]
  [--no-probe]
```

`auto` uses speech and falls back to other evidence for ordinary recognition failures. A missing `small` model is a setup error and prints the one-command repair instruction. `filename` skips speech and keeps the full duration of each file. Neither mode extracts frames for OCR.

### Fingerprint Jianying/writer signature

```text
roughcut.py fingerprint
  [--install-dir PATH]
  [--drafts DRAFT_ROOT]
```

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

A full job tree looks like this. Only `output/` is produced by the `run` command; the rest is either your input or state written by the job script.

```text
jobs/<JobName>/
├── wiki.md              input, hand-written or generated from -WikiText
├── corrections.json     input, optional, per-job and disposable
└── output/
    ├── wiki-source.md
    ├── wiki-steps.json
    ├── takes.json
    ├── edit-plan.json
    ├── review.md
    ├── lexicon-review.json
    ├── wiki-subtitles.srt
    ├── review-subtitles.srt
    ├── timeline.fcpxml
    └── review-preview.mp4
jobs/.roughcut-state/
└── jianying-fingerprint.json   state, keep
```

### Read these

- `review.md`: the first thing to open. Missing steps, `待确认` clips, evidence fallbacks, pending and applied term repairs, and a timeline summary.
- `lexicon-review.json`: term repairs awaiting a decision; they take effect only after you decide and re-run. See [Two-layer term repair](#two-layer-term-repair). Verdicts are stored here, so keep the file for the duration of the job.
- `review-preview.mp4`: optional 720p render for a fast visual sanity check. Not an editable master.

### Keep these

- `edit-plan.json`: the portable source of truth — source in/out ranges, ordering, captions, and match status. Everything else can be regenerated from it, and it outlives any Jianying format change.
- `timeline.fcpxml`: editable interchange for Final Cut Pro and compatible editors.
- `wiki-subtitles.srt`: formal procedure-derived captions.
- `jianying-fingerprint.json`: records the validated Jianying signature. Deleting it only costs one extra staging validation.

### Intermediate, safe to delete

- `wiki-source.md`: the procedure input saved verbatim, kept for traceability.
- `wiki-steps.json`: normalized steps and caption facts.
- `takes.json`: per-file probes, labels, timestamps, glossary repairs, and warnings. Worth keeping if you plan to re-run with `--reuse-takes`, since it is what lets you skip recognition.
- `review-subtitles.srt`: `待确认` markers only; drop it once the review pass is done.

### Cleaned up automatically

Temporary WAV tracks are deleted after recognition. A staging draft is deleted as soon as validation passes. `root_meta_info.json` backups accumulate in `<drafts>\.roughcut-backups` and can be pruned once drafts open correctly.

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

- Speech recognition runs locally; frame OCR is not used.
- No specific cloud model API is required.
- Original MP4/MOV files are read-only inputs.
- The tool performs a rough cut, not final editorial judgment.
- Visual-only actions with neither procedure-related speech nor a meaningful filename remain in the export at the timeline end, use a `待确认` marker, and are listed as unmarked footage in `review.md`; original files are never renamed.
- Jianying's private draft format can change; always keep SRT, FCPXML, and `edit-plan.json` as portable fallbacks.
- Review captions, safety statements, quantities, and installation directions before publishing.

## License

The repository is licensed under MIT. Third-party packages and models retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
