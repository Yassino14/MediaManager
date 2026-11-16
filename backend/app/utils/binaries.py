from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def _windows_candidate_dirs() -> list[Path]:
    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")
    program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")

    if local_app_data:
        candidates.append(Path(local_app_data) / "Microsoft" / "WinGet" / "Links")
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.is_dir():
            for pkg_dir in winget_pkgs.glob("*FFmpeg*"):
                for bin_dir in pkg_dir.glob("**/bin"):
                    if bin_dir.is_dir():
                        candidates.append(bin_dir)
    if user_profile:
        candidates.append(Path(user_profile) / "scoop" / "shims")
    candidates.extend([
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
        Path(program_data) / "chocolatey" / "bin",
    ])
    return candidates


def resolve_binary(name: str, custom_path: Optional[str] = None) -> Optional[str]:
    """
    Resolves `ffmpeg` or `ffprobe` binary path.
    Checks custom_path first, then PATH via shutil.which, then common Windows paths.
    """
    if custom_path and custom_path.strip():
        custom = Path(custom_path.strip()).expanduser()
        if custom.is_file() and os.access(custom, os.X_OK):
            return str(custom.resolve())
        # Check if user pointed to folder containing the binary
        for ext in ("", ".exe"):
            candidate = custom / f"{name}{ext}"
            if candidate.is_file():
                return str(candidate.resolve())

    found = shutil.which(name)
    if found:
        return found

    for folder in _windows_candidate_dirs():
        for ext in (".exe", ""):
            candidate = folder / f"{name}{ext}"
            if candidate.is_file():
                return str(candidate.resolve())

    return None


def get_binary_version(binary_path: Optional[str]) -> Optional[str]:
    if not binary_path:
        return None
    try:
        proc = subprocess.run(
            [binary_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.splitlines()[0].strip()
    except Exception:
        pass
    return None


def get_ytdlp_status() -> Dict[str, Any]:
    try:
        import yt_dlp  # type: ignore
        version = getattr(yt_dlp.version, "__version__", "installed")
        return {"available": True, "version": version, "mode": "python_api"}
    except ImportError:
        cli_path = shutil.which("yt-dlp")
        if cli_path:
            return {"available": True, "version": "cli", "mode": "cli"}
        return {
            "available": False,
            "version": None,
            "install_hint": "pip install -U yt-dlp",
        }


def get_environment_diagnostics(ffmpeg_custom: str = "", ffprobe_custom: str = "") -> Dict[str, Any]:
    ffmpeg_bin = resolve_binary("ffmpeg", ffmpeg_custom)
    ffprobe_bin = resolve_binary("ffprobe", ffprobe_custom)
    ytdlp_info = get_ytdlp_status()

    return {
        "ffmpeg": {
            "available": ffmpeg_bin is not None,
            "path": ffmpeg_bin,
            "version": get_binary_version(ffmpeg_bin),
            "install_hint": "winget install Gyan.FFmpeg  OR  choco install ffmpeg",
        },
        "ffprobe": {
            "available": ffprobe_bin is not None,
            "path": ffprobe_bin,
            "version": get_binary_version(ffprobe_bin),
            "install_hint": "Included with standard FFmpeg full builds (winget install Gyan.FFmpeg)",
        },
        "yt_dlp": ytdlp_info,
    }


def check_disk_space(directory: Path, min_free_bytes: int = 50 * 1024 * 1024) -> Dict[str, Any]:
    target = directory if directory.exists() else directory.parent
    usage = shutil.disk_usage(target)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "has_enough_space": usage.free >= min_free_bytes,
    }
