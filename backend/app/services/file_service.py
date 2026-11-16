from __future__ import annotations
import mimetypes
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.utils.binaries import check_disk_space
from app.utils.security import sanitize_filename, validate_path_in_allowed_dirs

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".gif"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma"}
ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


class FileService:
    """
    Manages browsing, searching, filtering, sorting, renaming, deleting, and
    opening files strictly within configured media directories.
    """

    def __init__(self, get_settings_fn: Callable[[], Dict[str, Any]]) -> None:
        self._get_settings = get_settings_fn

    def get_allowed_roots(self) -> List[Path]:
        settings = self._get_settings()
        roots: List[Path] = []
        for key in ("download_dir", "conversion_dir"):
            val = settings.get(key)
            if val:
                p = Path(val).expanduser().resolve()
                p.mkdir(parents=True, exist_ok=True)
                if p not in roots:
                    roots.append(p)
        return roots

    @staticmethod
    def classify_extension(ext: str) -> str:
        low = ext.lower()
        if low in VIDEO_EXTENSIONS:
            return "video"
        if low in AUDIO_EXTENSIONS:
            return "audio"
        return "other"

    def list_files(
        self,
        search: str = "",
        media_type: str = "all",
        sort_by: str = "date",
        sort_desc: bool = True,
    ) -> Dict[str, Any]:
        roots = self.get_allowed_roots()
        items: List[Dict[str, Any]] = []
        seen_paths: set[str] = set()
        total_media_bytes = 0

        query = search.strip().lower()

        for root in roots:
            if not root.exists():
                continue
            for entry in root.rglob("*"):
                if not entry.is_file() or entry.name.startswith(".") or entry.name.startswith(".tmp_"):
                    continue
                resolved_str = str(entry.resolve())
                if resolved_str in seen_paths:
                    continue
                seen_paths.add(resolved_str)

                ext = entry.suffix.lower()
                category = self.classify_extension(ext)
                stat = entry.stat()
                total_media_bytes += stat.st_size

                if media_type != "all" and category != media_type:
                    continue
                if query and query not in entry.name.lower():
                    continue

                mime, _ = mimetypes.guess_type(entry.name)
                items.append({
                    "name": entry.name,
                    "path": resolved_str,
                    "directory": str(entry.parent),
                    "extension": ext.lstrip("."),
                    "category": category,
                    "mime_type": mime or "application/octet-stream",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "modified_ts": stat.st_mtime,
                })

        if sort_by == "name":
            items.sort(key=lambda x: x["name"].lower(), reverse=sort_desc)
        elif sort_by == "size":
            items.sort(key=lambda x: x["size_bytes"], reverse=sort_desc)
        elif sort_by == "format":
            items.sort(key=lambda x: x["extension"].lower(), reverse=sort_desc)
        else:
            items.sort(key=lambda x: x["modified_ts"], reverse=sort_desc)

        disk_info = check_disk_space(roots[0]) if roots else {
            "total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "has_enough_space": True
        }

        return {
            "files": items,
            "total_count": len(items),
            "library_used_bytes": total_media_bytes,
            "disk_usage": disk_info,
            "allowed_directories": [str(r) for r in roots],
        }

    def rename_file(self, file_path: str, new_name: str) -> Dict[str, Any]:
        roots = self.get_allowed_roots()
        target = validate_path_in_allowed_dirs(file_path, roots, must_exist=True)
        safe_new = sanitize_filename(new_name)
        if not os.path.splitext(safe_new)[1] and target.suffix:
            safe_new = f"{safe_new}{target.suffix}"

        new_path = (target.parent / safe_new).resolve()
        validate_path_in_allowed_dirs(new_path, roots, must_exist=False)

        if new_path.exists() and new_path != target:
            raise FileExistsError(f"A file named '{safe_new}' already exists in that directory.")

        target.rename(new_path)
        return {
            "old_path": str(target),
            "new_path": str(new_path),
            "new_name": new_path.name,
        }

    def delete_file(self, file_path: str) -> Dict[str, Any]:
        roots = self.get_allowed_roots()
        target = validate_path_in_allowed_dirs(file_path, roots, must_exist=True)
        if not target.is_file():
            raise ValueError("Only regular files can be deleted.")
        target.unlink()
        return {"deleted_path": str(target), "filename": target.name}

    def open_in_os(self, file_path: str, reveal_in_folder: bool = False) -> Dict[str, Any]:
        roots = self.get_allowed_roots()
        target = validate_path_in_allowed_dirs(file_path, roots, must_exist=True)
        sys_name = platform.system().lower()

        if sys_name == "windows":
            if reveal_in_folder:
                target_Select = str(target) if target.is_file() else str(target)
                subprocess.Popen(["explorer.exe", f"/select,{target_Select}"], shell=False)
            else:
                os.startfile(str(target))  # type: ignore[attr-defined]
            return {"opened": True, "path": str(target), "platform": "windows"}

        return {
            "opened": False,
            "path": str(target),
            "platform": sys_name,
            "note": "OS shell launch is enabled on Windows desktops.",
        }
