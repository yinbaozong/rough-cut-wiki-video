import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).parents[1] / "skills" / "rough-cut-wiki-video"
sys.path.insert(0, str(SKILL / "scripts"))

from roughcut.core import (  # noqa: E402
    MissingTakeEvidenceError,
    build_edit_plan,
    parse_filename,
    parse_wiki,
    segment_transcript,
)
from roughcut.pipeline import run_project  # noqa: E402
from roughcut.media import MissingWhisperModelError, resolve_whisper_model  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_small_model_uses_bundled_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            skill_root = Path(folder)
            bundled = skill_root / "assets" / "models" / "faster-whisper-small"
            bundled.mkdir(parents=True)
            for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
                (bundled / name).write_bytes(b"fixture")

            resolved = resolve_whisper_model("small", skill_root=skill_root, cached_model=lambda _name: None)
            self.assertEqual(resolved, str(bundled.resolve()))

    def test_missing_small_model_has_one_command_repair_message(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(MissingWhisperModelError, "download-model.ps1"):
                resolve_whisper_model(
                    "small", skill_root=Path(folder), cached_model=lambda _name: None
                )

    def test_inline_chinese_step_markers_are_split(self):
        steps = parse_wiki("步骤一：安装背板，锁紧一颗螺丝，步骤二，移除一颗螺丝，小心移除背板。步骤三：打开卡扣，移除热端。")
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[1]["wiki_text"], "移除一颗螺丝,小心移除背板。")

    def test_filename_parts_and_camera_names(self):
        self.assertEqual(parse_filename(Path("安装侧板_第2段.mov"))["part_number"], 2)
        self.assertEqual(parse_filename(Path("安装侧板二.mp4"))["part_number"], 2)
        self.assertEqual(parse_filename(Path("020_移除支架_01.mov"))["label"], "移除支架")
        self.assertIsNone(parse_filename(Path("DJI_0001.mp4"))["label"])
        self.assertIsNone(parse_filename(Path("微信视频2026-07-28_000412_000.mp4"))["label"])

    def test_split_character_end_cue_is_trimmed(self):
        words = [
            {"start": 0.0, "end": 0.3, "word": "开始"},
            {"start": 1.0, "end": 1.4, "word": "安装热端"},
            {"start": 4.0, "end": 4.2, "word": "结"},
            {"start": 4.2, "end": 4.4, "word": "束"},
        ]
        takes = segment_transcript(words, 6.0)
        self.assertAlmostEqual(takes[0]["out"], 4.0)
        self.assertEqual(takes[0]["end_reason"], "spoken_cue")

    def test_no_speech_still_preserves_the_media_take(self):
        takes = segment_transcript([], 6.0)
        self.assertEqual(takes, [{
            "in": 0.0, "out": 6.0, "spoken_label": None, "end_reason": "no_speech",
        }])

    def test_unrelated_speech_falls_back_to_wiki_related_filename(self):
        steps = parse_wiki("1. 安装侧板。\n2. 移除支架。")
        plan = build_edit_plan(steps, [{
            "source_file": "移除支架.mp4", "duration": 4.0,
            "spoken_label": "今天天气不错",
        }])
        segment = plan["segments"][0]
        self.assertEqual(segment["wiki_step_id"], "step-002")
        self.assertEqual(segment["evidence"]["selected_source"], "filename")

    def test_wiki_related_speech_has_priority_over_conflicting_filename(self):
        steps = parse_wiki("1. 安装侧板。\n2. 移除支架。")
        plan = build_edit_plan(steps, [{
            "source_file": "安装侧板.mp4", "duration": 4.0,
            "spoken_label": "移除支架",
        }])
        segment = plan["segments"][0]
        self.assertEqual(segment["wiki_step_id"], "step-002")
        self.assertEqual(segment["status"], "ambiguous")
        self.assertEqual(segment["evidence"]["selected_source"], "spoken")

    def test_no_related_speech_or_filename_requires_user_action(self):
        steps = parse_wiki("1. 安装侧板。")
        plan = build_edit_plan(steps, [{
            "source_file": "DJI_0001.mp4", "duration": 4.0,
            "spoken_label": "测试测试",
        }])
        self.assertEqual(plan["action_required_files"], ["DJI_0001.mp4"])
        self.assertTrue(plan["segments"][0]["evidence"]["needs_user_input"])

    def test_wiki_order_drives_edit_order_and_keeps_duplicates(self):
        steps = parse_wiki("""# 安装教程
1. 移除运输支架。
2. 安装右侧板并拧紧两颗螺丝。
3. 连接 AMS 电缆。
""")
        takes = [
            {"source_file": "安装侧板_第2段.mov", "duration": 4.0},
            {"source_file": "移除支架.mp4", "duration": 3.0},
            {"source_file": "安装侧板_第1段.mov", "duration": 5.0},
            {"source_file": "C0001.mp4", "duration": 2.0},
        ]
        plan = build_edit_plan(steps, takes)
        names = [Path(x["source_file"]).name for x in plan["segments"]]
        self.assertEqual(names[:3], ["移除支架.mp4", "安装侧板_第1段.mov", "安装侧板_第2段.mov"])
        self.assertEqual(plan["segments"][-1]["status"], "unmatched")
        self.assertEqual(plan["missing_step_ids"], ["step-003"])

    def test_voice_markers_do_not_match_normal_sentences(self):
        words = [
            {"start": 0.0, "end": 0.5, "word": "三二一开始"},
            {"start": 0.6, "end": 1.1, "word": "安装侧板"},
            {"start": 2.0, "end": 2.5, "word": "可以安装"},
            {"start": 4.0, "end": 4.3, "word": "OK"},
        ]
        takes = segment_transcript(words, duration=7.0)
        self.assertEqual(len(takes), 1)
        self.assertAlmostEqual(takes[0]["in"], 0.5)
        self.assertAlmostEqual(takes[0]["out"], 4.0)
        self.assertIn("可以安装", takes[0]["spoken_label"])

    def test_single_file_can_split_at_next_step(self):
        words = [
            {"start": 0.0, "end": 0.3, "word": "开始"},
            {"start": 0.4, "end": 0.9, "word": "安装侧板"},
            {"start": 3.0, "end": 3.5, "word": "下一步移除支架"},
            {"start": 6.0, "end": 6.2, "word": "过"},
        ]
        takes = segment_transcript(words, 7.0)
        self.assertEqual([x["spoken_label"] for x in takes], ["安装侧板", "移除支架"])

    def test_filename_project_emits_editable_interchange(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / "media"
            media.mkdir()
            (media / "移除支架.mp4").write_bytes(b"placeholder")
            wiki = root / "wiki.md"
            wiki.write_text("1. 移除运输支架。\n2. 安装右侧板。", encoding="utf-8")
            output = root / "output"
            result = run_project(media, wiki, output, mode="filename", probe_media=False)
            expected = {
                "wiki-source.md", "wiki-steps.json", "takes.json", "edit-plan.json",
                "review.md", "wiki-subtitles.srt", "review-subtitles.srt", "timeline.fcpxml",
            }
            self.assertTrue(expected.issubset({p.name for p in output.iterdir()}))
            self.assertFalse((output / "jianying-draft").exists())
            plan = json.loads((output / "edit-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["segments"][0]["status"], "matched")
            self.assertIn("<fcpxml", (output / "timeline.fcpxml").read_text(encoding="utf-8"))

    def test_pipeline_stops_and_prompts_when_audio_and_filename_are_unusable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root / "media"
            media.mkdir()
            (media / "DJI_0001.mp4").write_bytes(b"placeholder")
            wiki = root / "wiki.md"
            wiki.write_text("1. 安装侧板。", encoding="utf-8")
            output = root / "output"

            with self.assertRaisesRegex(MissingTakeEvidenceError, "重新录制带有步骤口播"):
                run_project(media, wiki, output, mode="filename", probe_media=False)
            self.assertIn("需要用户处理", (output / "review.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
