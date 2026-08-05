from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import tempfile
import time
import re
from pathlib import Path


def _jianying_is_running() -> bool:
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return b"jianyingpro.exe" in completed.stdout.lower()


def _backup_root_metadata(user_data: Path, draft_root: Path) -> Path | None:
    root_meta = user_data / "Projects" / "com.lveditor.draft" / "root_meta_info.json"
    if not root_meta.is_file():
        return None
    backup_dir = draft_root / ".roughcut-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"root_meta_info.{stamp}-{time.time_ns()}.json"
    shutil.copy2(root_meta, backup_path)
    return backup_path


_UNINSTALL_SUBKEYS = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\JianyingPro",
    r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\JianyingPro",
)


def read_registry_entry() -> dict:
    """Read Jianying's uninstall entry for its version and install root.

    InstallLocation is often empty, but UninstallString and DisplayIcon point at
    ``<install root>\\uninst.exe``, which is the only reliable way to locate an
    install placed outside Program Files.
    """
    if os.name != "nt":
        return {}
    import winreg

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for subkey in _UNINSTALL_SUBKEYS:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    values = {}
                    for name in ("DisplayVersion", "InstallLocation", "UninstallString", "DisplayIcon"):
                        try:
                            values[name] = str(winreg.QueryValueEx(key, name)[0]).strip()
                        except OSError:
                            continue
            except OSError:
                continue
            roots: list[Path] = []
            location = values.get("InstallLocation")
            if location:
                roots.append(Path(location))
            for name in ("UninstallString", "DisplayIcon"):
                raw = values.get(name, "").strip('"').split(",")[0].strip().strip('"')
                if raw.lower().endswith(".exe"):
                    roots.append(Path(raw).parent)
            if values.get("DisplayVersion") or roots:
                return {"version": values.get("DisplayVersion"), "roots": roots}
    return {}


def discover_jianying_install_dir(
    preferred: Path | None = None,
    *,
    draft_root: Path | None = None,
) -> Path:
    """Resolve a Jianying installation containing videoeditor.dll.

    Jianying's updater can remove an old version directory after the app exits.
    Honor an exact valid path, otherwise search its siblings and common roots,
    choosing the highest version number.
    """
    preferred_path = Path(preferred).resolve() if preferred else None
    if preferred_path and (preferred_path / "videoeditor.dll").is_file():
        return preferred_path

    roots: list[Path] = []
    if preferred_path:
        roots.extend([preferred_path, preferred_path.parent])
    if draft_root:
        roots.append(Path(draft_root).resolve().parent / "JianyingPro")
    roots.extend(read_registry_entry().get("roots", []))
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable)
        if value:
            roots.extend([
                Path(value) / "JianyingPro",
                Path(value) / "Programs" / "JianyingPro",
            ])

    candidates: dict[str, Path] = {}
    for root in roots:
        if (root / "videoeditor.dll").is_file():
            candidates[str(root).lower()] = root.resolve()
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir() and (child / "videoeditor.dll").is_file():
                    candidates[str(child).lower()] = child.resolve()
    if not candidates:
        requested = str(preferred_path) if preferred_path else "auto-detected locations"
        raise FileNotFoundError(f"videoeditor.dll was not found under {requested}")

    def version_key(path: Path) -> tuple[tuple[int, ...], int]:
        numbers = tuple(int(part) for part in re.findall(r"\d+", path.name))
        return numbers, path.stat().st_mtime_ns

    return max(candidates.values(), key=version_key)


def fingerprint(preferred: Path | None = None, *, draft_root: Path | None = None) -> dict:
    """Signature of everything that can break draft encoding.

    A staging validation only needs to run again when this changes, which in
    practice means Jianying updated itself or the writer library was upgraded.
    """
    entry = read_registry_entry()
    result = {
        "registry_version": entry.get("version"),
        "install_dir": None,
        "videoeditor_dll": None,
        "writer_version": None,
    }
    try:
        install_dir = discover_jianying_install_dir(preferred, draft_root=draft_root)
    except FileNotFoundError:
        install_dir = None
    if install_dir is not None:
        result["install_dir"] = str(install_dir)
        dll = install_dir / "videoeditor.dll"
        if dll.is_file():
            stat = dll.stat()
            result["videoeditor_dll"] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    try:
        from importlib.metadata import version

        result["writer_version"] = version("pyJianYingDraft")
    except Exception:
        try:
            import pyJianYingDraft

            result["writer_version"] = getattr(pyJianYingDraft, "__version__", "unknown")
        except ImportError:
            pass
    return result


def export_jianying10(
    plan: dict,
    draft_root: Path,
    draft_name: str,
    *,
    user_data: Path | None = None,
    jy_install_dir: Path | None = None,
    encrypt: bool = True,
    allow_replace: bool = False,
) -> Path:
    """Create a native Jianying 10/11 draft with editable source cut points and text tracks."""
    try:
        import pyJianYingDraft as draft
        from pyJianYingDraft.draft_codec import write_json_object_with_codec
    except ImportError as exc:
        raise RuntimeError("pyJianYingDraft 0.3 high-version fork is not installed") from exc

    draft_root = Path(draft_root).resolve()
    draft_root.mkdir(parents=True, exist_ok=True)
    resolved_user_data = Path(user_data).resolve() if user_data else None
    if resolved_user_data is not None and _jianying_is_running():
        raise RuntimeError("JianyingPro is running. Save your work and fully exit Jianying before registering a draft.")
    if resolved_user_data is not None:
        _backup_root_metadata(resolved_user_data, draft_root)
    codec = None
    if encrypt:
        resolved_install_dir = discover_jianying_install_dir(jy_install_dir, draft_root=draft_root)
        codec = draft.JianyingDraftCryptoCodec(
            draft.DraftCryptoConfig(
                jy_install_dir=str(resolved_install_dir),
                isolated=True,
                validate_roundtrip=True,
                backup=False,
            )
        )

    # The dependency falls back to %LOCALAPPDATA% when user_data_path is None.
    # Use a disposable User Data tree for staging so an unregistered validation
    # export can never leak into the user's Jianying homepage index.
    isolated_registration = tempfile.TemporaryDirectory(prefix="roughcut-jianying-registration-") if user_data is None else None
    effective_user_data = (
        Path(isolated_registration.name)
        if isolated_registration is not None
        else resolved_user_data
    )
    try:
        folder = draft.DraftFolder(
            str(draft_root),
            content_codec=codec,
            user_data_path=str(effective_user_data),
        )
        project = folder.create_draft(draft_name, 1920, 1080, fps=30, allow_replace=allow_replace)
        video_track, document_track, review_track = project.append_tracks([
            draft.TrackSpec(draft.TrackType.video, "主视频"),
            draft.TrackSpec(draft.TrackType.text, "文档字幕"),
            draft.TrackSpec(draft.TrackType.text, "待确认"),
        ])

        cursor_us = 0
        for segment in plan.get("segments", []):
            source_path = str(Path(segment["source_file"]).resolve())
            material = draft.VideoMaterial(source_path)
            source_in_us = max(0, round(float(segment["source_in"]) * 1_000_000))
            requested_out_us = round(float(segment["source_out"]) * 1_000_000)
            source_out_us = min(requested_out_us, material.duration)
            duration_us = source_out_us - source_in_us
            if duration_us <= 0:
                raise ValueError(
                    f"Invalid source range for {source_path}: "
                    f"{source_in_us}..{requested_out_us} us, media duration {material.duration} us"
                )
            target_range = draft.Timerange(cursor_us, duration_us)
            source_range = draft.Timerange(source_in_us, duration_us)
            video = draft.VideoSegment(
                material,
                target_range,
                source_timerange=source_range,
                volume=1.0,
            )
            project.add_segment(video, track=video_track)
            _add_texts(draft, project, document_track, segment.get("captions") or [], target_range, transform_y=-0.78)
            _add_texts(draft, project, review_track, segment.get("review_caption") or [], target_range, transform_y=-0.58)
            cursor_us += duration_us

        # New ScriptFile objects are plaintext by default. Registration runs first;
        # then both project sidecars are encoded using Jianying's own local DLL.
        project.save()
        draft_dir = draft_root / draft_name
        content_path = draft_dir / "draft_content.json"
        meta_path = draft_dir / "draft_meta_info.json"
        if codec:
            content = json.loads(content_path.read_text(encoding="utf-8"))
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            write_json_object_with_codec(content_path, content, content_codec=codec, indent=None)
            write_json_object_with_codec(meta_path, meta, content_codec=codec, indent=None)

        _write_auxiliary_files(draft_dir, content_path, project.content.get("id", ""))
        return draft_dir
    finally:
        if isolated_registration is not None:
            isolated_registration.cleanup()


def _add_texts(draft, project, track, texts: list[str], timerange, *, transform_y: float) -> None:
    if not texts:
        return
    each = max(100_000, timerange.duration // len(texts))
    for index, text in enumerate(texts):
        start = timerange.start + index * each
        duration = timerange.duration - each * index if index == len(texts) - 1 else each
        item = draft.TextSegment(
            str(text),
            draft.Timerange(start, duration),
            style=draft.TextStyle(size=8.0, bold=False, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True),
            border=draft.TextBorder(color=(0.0, 0.0, 0.0), width=35.0),
            clip_settings=draft.ClipSettings(transform_y=transform_y),
        )
        project.add_segment(item, track=track)


def _write_auxiliary_files(draft_dir: Path, content_path: Path, project_id: str) -> None:
    content_bytes = content_path.read_bytes()
    (draft_dir / "draft_content.json.bak").write_bytes(content_bytes)
    (draft_dir / "template-2.tmp").write_bytes(content_bytes)
    (draft_dir / "draft_biz_config.json").write_bytes(b"")
    (draft_dir / "draft_agency_config.json").write_text(
        json.dumps({
            "is_auto_agency_enabled": False, "is_auto_agency_popup": False,
            "is_single_agency_mode": False, "marterials": None,
            "use_converter": False, "video_resolution": 720,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
    )
    (draft_dir / "timeline_layout.json").write_text(
        json.dumps({"dockItems": [{"dockIndex": 0, "ratio": 1, "timelineIds": [project_id], "timelineNames": ["时间线01"]}], "layoutOrientation": 1}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    settings = configparser.ConfigParser()
    now = int(time.time())
    settings["General"] = {"draft_create_time": str(now), "draft_last_edit_time": str(now), "real_edit_seconds": "0", "real_edit_keys": "0"}
    with (draft_dir / "draft_settings").open("w", encoding="utf-8", newline="\n") as stream:
        settings.write(stream, space_around_delimiters=False)
    try:
        from PIL import Image
        Image.new("RGB", (640, 360), (16, 16, 16)).save(draft_dir / "draft_cover.jpg", quality=85)
    except ImportError:
        pass
