import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).parents[1] / "skills" / "rough-cut-wiki-video"
sys.path.insert(0, str(SKILL / "scripts"))

from roughcut.jianying10 import (  # noqa: E402
    _jianying_is_running,
    discover_jianying_install_dir,
    export_jianying10,
)


class Jianying10ExportTests(unittest.TestCase):
    def test_install_discovery_recovers_when_requested_version_was_upgraded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "JianyingPro"
            old = root / "10.6.0.14057"
            current = root / "11.1.0.14287"
            old.mkdir(parents=True)
            current.mkdir(parents=True)
            (current / "videoeditor.dll").write_bytes(b"fixture")

            self.assertEqual(discover_jianying_install_dir(old), current.resolve())

    @unittest.skipUnless(os.name == "nt", "Windows process detection")
    def test_jianying_process_detection_uses_tasklist_image_name(self):
        completed = type("Completed", (), {"stdout": b"JianyingPro.exe  123 Console"})()
        with patch("roughcut.jianying10.subprocess.run", return_value=completed) as run:
            self.assertTrue(_jianying_is_running())
        run.assert_called_once()

    def test_export_writes_native_cut_points_and_text_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = Path(__file__).parent / "generated" / "media" / "移除支架.mp4"
            self.assertTrue(media.exists(), "run the media smoke fixture before this integration test")
            plan = {
                "segments": [{
                    "source_file": str(media), "source_in": 0.25, "source_out": 2.75,
                    "captions": ["安装背板。"], "review_caption": ["待确认"],
                }]
            }
            draft_dir = export_jianying10(plan, root / "drafts", "test_native", encrypt=False)
            content = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
            self.assertEqual([track["type"] for track in content["tracks"]], ["video", "text", "text"])
            video = content["tracks"][0]["segments"][0]
            self.assertEqual(video["source_timerange"], {"start": 250_000, "duration": 2_500_000})
            self.assertEqual(video["target_timerange"], {"start": 0, "duration": 2_500_000})

    def test_export_clamps_plan_out_point_to_native_media_duration(self):
        import pyJianYingDraft as draft

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = Path(__file__).parent / "generated" / "media" / "移除支架.mp4"
            native_duration = draft.VideoMaterial(str(media)).duration
            plan = {"segments": [{
                "source_file": str(media), "source_in": 0.25, "source_out": 99.0,
                "captions": ["安装背板。"], "review_caption": [],
            }]}

            draft_dir = export_jianying10(plan, root / "drafts", "clamped", encrypt=False)
            content = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
            video = content["tracks"][0]["segments"][0]
            self.assertEqual(
                video["source_timerange"],
                {"start": 250_000, "duration": native_duration - 250_000},
            )

    def test_staging_export_does_not_implicitly_register_via_localappdata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake_local_app_data = root / "local-app-data"
            media = Path(__file__).parent / "generated" / "media" / "移除支架.mp4"
            plan = {"segments": [{
                "source_file": str(media), "source_in": 0.0, "source_out": 1.0,
                "captions": ["移除支架。"], "review_caption": [],
            }]}
            with patch.dict(os.environ, {"LOCALAPPDATA": str(fake_local_app_data)}):
                export_jianying10(plan, root / "drafts", "staging", encrypt=False)

            implicit_root_meta = (
                fake_local_app_data / "JianyingPro" / "User Data" / "Projects"
                / "com.lveditor.draft" / "root_meta_info.json"
            )
            self.assertFalse(implicit_root_meta.exists())

    def test_encrypted_draft_roundtrips_with_local_jianying_dll(self):
        try:
            configured = os.environ.get("JIANYING_TEST_INSTALL_DIR")
            install = discover_jianying_install_dir(Path(configured) if configured else None)
        except FileNotFoundError:
            self.skipTest("No compatible Jianying videoeditor.dll is installed")
        import pyJianYingDraft as draft
        from pyJianYingDraft.draft_codec import load_json_object_with_codec

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = Path(__file__).parent / "generated" / "media" / "移除支架.mp4"
            plan = {"segments": [{
                "source_file": str(media), "source_in": 0.25, "source_out": 2.75,
                "captions": ["安装背板。"], "review_caption": [],
            }]}
            draft_dir = export_jianying10(plan, root / "drafts", "encrypted", jy_install_dir=install)
            content_path = draft_dir / "draft_content.json"
            self.assertFalse(content_path.read_bytes().lstrip().startswith(b"{"))
            codec = draft.JianyingDraftCryptoCodec(draft.DraftCryptoConfig(jy_install_dir=install, backup=False))
            decoded, used_codec = load_json_object_with_codec(content_path, content_codec=codec)
            self.assertTrue(used_codec)
            self.assertEqual(decoded["tracks"][0]["segments"][0]["source_timerange"]["start"], 250_000)


if __name__ == "__main__":
    unittest.main()
