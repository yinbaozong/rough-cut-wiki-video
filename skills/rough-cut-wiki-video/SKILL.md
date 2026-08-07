---
name: rough-cut-wiki-video
description: Create editable rough cuts for any step-by-step tutorial from MP4/MOV footage plus pasted procedure text or a text/Markdown guide. Use for how-to videos, assembly or repair, crafts, cooking, product demonstrations, workplace procedures, training, unboxing, speech-cue trimming, filename ordering, procedure-grounded captions, SRT/FCPXML export, review reports, or native encrypted Jianying 10/11 drafts on Windows, including fixing drafts that do not appear on the Jianying homepage.
---

# Wiki Video Rough Cut

Turn an ordered procedure and a footage folder into a non-destructive tutorial rough-cut package. Accept procedure text pasted into the conversation or a local UTF-8 text/Markdown file. Prefer local speech evidence, fall back to filenames, preserve every take, and use the supplied procedure—not improvised narration—as the factual source for captions.

## Workflow

1. Ask for the footage directory and ordered procedure. Also ask whether the user has a UTF-8 glossary with one term per line. Explain once that a glossary is optional and secondary: term repair works mainly from the procedure's own wording, since the narration is usually the procedure read aloud, and a glossary helps only with wording the procedure omits or abbreviates. Do not imply that a missing glossary degrades the run, and do not push for a larger one — a bigger glossary also adds more phonetically similar wrong candidates. Accept either text pasted directly into the conversation or a local UTF-8 text/Markdown file; never require an `.md` file when pasted text is available. Do not fetch a URL unless the user explicitly asks. Save pasted text unchanged as the job's `wiki-source.md` before invoking the CLI.
2. Treat only ordered, filmed actions as timeline steps. Do not ask the user to add tool lists, preparation sections, background, or theory that was not filmed. Prefer `Step 1/2/3`, `步骤一/二/三`, or a numbered list. Keep essential cautions inside the action where they apply.
3. Locate this skill directory from the loaded `SKILL.md`; never assume a `.codex`, `.claude`, or `.cursor` path.
4. Report the installed Skill version to the user, then run the capability check:

   ```powershell
   python scripts/roughcut.py --version
   python scripts/roughcut.py doctor
   ```

   The same version is recorded in `edit-plan.json` and `review.md`, so a later result can always be traced to the code that produced it.

5. Run analysis. Use `auto` unless the user requests filename-only processing. In auto mode, extract every audio track in parallel, transcribe with word timestamps, and test whether the spoken label is related to a procedure step before considering the filename:

   ```powershell
   python scripts/roughcut.py run --media "E:\footage" --wiki "E:\job\wiki.md" --output "E:\job\output" --mode auto --lexicon "E:\glossary.txt"
   ```

   Speech language is pinned to `zh` by default. Auto-detection measured about twice as slow and misread short, noisy cues as other languages, returning transcript text in them. Pass `--language ""` only when the footage really is not Chinese. Traditional output is normalized to Simplified so it can match a Simplified procedure.

   On Windows the repeatable wrapper is `scripts/run-job.ps1`, which pins PATH, output layout, the glossary, and the staging gate. Re-run with `-ReuseTakes` after editing the procedure or corrections: it recomputes matching from `takes.json` in seconds instead of re-transcribing.

6. Resolve pending term repairs before judging the timeline. Open `lexicon-review.json` and decide every entry whose `decision` is `pending`, then re-run the same command with `--reuse-takes`:

   ```powershell
   python scripts/roughcut.py run --media "E:\footage" --wiki "E:\job\wiki.md" --output "E:\job\output" --reuse-takes --lexicon "E:\glossary.txt"
   ```

   This is the second layer of glossary repair and it is your job, not the script's. Set `decision` to `accept` only when `suggested` is the wording the procedure actually uses and `resulting_step_text` describes what that take plausibly shows; otherwise `reject`, and leave `pending` when genuinely unsure. Record the reason in `decision_note`. Never accept an entry merely because it has the highest `pinyin_score` or the highest `resulting_confidence`: on real footage the take `再次锁紧抵扣布丁螺丝` offered `移除底壳固定螺丝` at confidence 1.00, which is impossible for a take that says 再次锁紧, while the correct `底壳固定螺丝` only reached 0.75. Verdicts are reversible, so flipping an entry later restores the original transcript.

7. Inspect `review.md`, `edit-plan.json`, representative evidence, and warnings. Improve `wiki-steps.json` or `edit-plan.json` only when the footage/procedure evidence supports the change. Never invent quantities, objects, ingredients, parts, directions, or safety claims.
8. Re-run exporters after a manual plan change (currently use `run` for a full rebuild). Keep ambiguous or conflicting footage and mark it `待确认`; never silently drop input media.
9. On Windows, create a native Jianying 10/11 project from `edit-plan.json` with the `jianying10` command. Validate in a staging directory (omit `--user-data`) only when `roughcut.py fingerprint` differs from the recorded signature; encoding breaks only when Jianying or the writer library changes, so staging every run wastes time. Before adding `--user-data` to register the real project, require Jianying to be fully closed. The exporter must encrypt both draft JSON files with the newest valid local `videoeditor.dll`, back up `root_meta_info.json`, and register a matching homepage entry. Never replace an existing draft unless the user explicitly authorizes it.

## Evidence Rules

Use this priority: user corrections; procedure-related post-start spoken label; meaningful filename and part number; procedure order and recording time for review only. Frame extraction and OCR are disabled by design: never decode video frames for evidence, because it dominated runtime without changing match decisions.

When several steps qualify, choose the one sharing the most terms with the take rather than the highest ratio. A short step such as `安装底壳` otherwise scores a perfect ratio against the take `安装底壳固定螺丝`, stealing footage from the more specific `安装底壳固定螺丝并预锁紧`.

Term repair runs after transcription instead of biasing the decoder, and it has two layers. Never route a glossary through `hotwords`: faster-whisper truncates hotwords at 223 tokens, so a real glossary loses everything past its first few entries.

The automatic layer only replaces spans that are already close character-for-character, keeps the model's original text in `spoken_label_raw`, and lists every substitution in `review.md`. Because it applies unattended, it also refuses to touch a span overlapping a term the text already spells correctly, and requires the characters it would change to sound alike. Both guards are load-bearing: a real 530-term glossary containing 77 pairs of near-identical terms otherwise rewrote `更换冷端风扇` into its opposite `更换热端风扇`, and flipped `安装底壳固定螺丝` to `移除底壳固定螺丝`, which sends a take to the wrong step. Pronunciation is what separates them, since `山`/`扇` are the same syllable while `冷`/`热` share nothing, even though both differ by exactly one character. Without `pypinyin` this layer is disabled entirely rather than run unguarded.

The reviewed layer adds pronunciation comparison and never applies anything on its own. It exists because the two similarity measures fail in opposite directions: Chinese recognition errors are mostly homophones, so `抵扣布丁` for `底壳固定` scores 0.00 on characters yet 0.76 on pinyin, while the semantically opposite `热端风扇`/`冷端风扇` reaches 0.87 on pinyin. No threshold separates a real mishearing from a wrong term that merely sounds similar, which is exactly the judgement an agent holding the procedure text can make and a score cannot. Proposals are therefore written to `lexicon-review.json` for a decision, and only takes matched below `--review-confidence` (0.70) are examined, since a confidently matched take has nothing worth changing. This layer stays permissive on purpose, guards included, because you can reject a bad suggestion but cannot recover one never offered.

The repair vocabulary is the procedure's own wording plus the optional `--lexicon` glossary, and the procedure leads because the narration is usually the procedure read aloud. Proposals carry a `source` of `procedure` or `glossary`, procedure first, and a glossary proposal covering the same span is dropped. On real footage both fired on the same misheard `抵扣布丁螺丝`: the procedure proposed the correct `底壳固定螺丝` at 0.839 by pronunciation while the glossary proposed `进气口` at 0.875 — a higher score for a term appearing nowhere in the procedure, so it can never match a step. Prefer `procedure` proposals when judging. Terms shorter than three characters are never used, because short fuzzy hits are usually coincidence. A camera filename such as `DJI_0001` is not a label. If speech is empty or unrelated to every procedure step, try the filename. If neither provides procedure-related evidence, never guess and never rename the original media: preserve the whole clip at the timeline end, set `status: unmatched`, use edit-plan/FCPXML display name `待确认（reason）— original-name`, add exact review-track text `待确认` to editor exports, and explain the missing evidence in `review.md`. Continue exporting the other footage. Preserve repeated takes and order explicit parts before recording time. List unshot procedure steps only in the report.

Start cues are `321开始`, `三二一开始`, `321走`, or isolated `开始`/`走`. End cues are isolated `OK`, `过`, `可以`, `好了`, or `结束`. Do not trim phrase-internal words such as `可以安装` or `开始拆卸`. File end is a valid take ending.

## Captions and Outputs

Create formal captions from the supplied procedure, lightly polishing syntax for natural reading. Keep names, counts, directions, and warnings stated in the steps. Use two independently removable tracks: `文档字幕` and exact text `待确认`. Keep original audio and original 4K files untouched.

The output contract and JSON field definitions are in [schemas.md](references/schemas.md). Read [usage.md](references/usage.md) for platform/setup details and [jianying10.md](references/jianying10.md) before registering a Jianying project. When helping with capture conventions, read [shooting-guide.md](references/shooting-guide.md), [filename-guide.md](references/filename-guide.md), and [wiki-format.md](references/wiki-format.md). When evaluating local recognition or considering a cloud ASR provider, read [speech-recognition.md](references/speech-recognition.md) and test representative user audio before recommending payment.

## Failure Handling

Use only the multilingual faster-whisper `small` model. Do not substitute `tiny`. If `small` is missing or incomplete, stop speech analysis and show the one-command `scripts/download-model.ps1` or `scripts/download-model.sh` repair. For other recognition failures, preserve all media, use remaining evidence, and record the fallback in `review.md`. If FFmpeg is absent, still emit the plan, SRT, FCPXML, and draft candidate; omit the preview. If Jianying encryption or registration fails, preserve the staging draft, diagnostics, SRT, FCPXML, and `edit-plan.json`; never replace, downgrade, or uninstall the user's Jianying automatically.
