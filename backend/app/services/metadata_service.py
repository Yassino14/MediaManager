from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.models.schemas import DuplicatePolicy
from app.utils.binaries import resolve_binary
from app.utils.security import resolve_output_filepath, validate_path_in_allowed_dirs


METADATA_DISCLAIMER = (
    "Metadata removal strips global container tags, stream-level tags, and chapter markers "
    "supported by FFmpeg (`-map_metadata -1 -map_chapters -1`). Metadata removal is format-dependent "
    "and is not a forensic guarantee of complete anonymization. Container muxers may still write "
    "structural format headers (such as codec identifiers or major_brand), and this operation does not "
    "remove visible video content, burned-in watermarks, or information embedded in the actual image or audio signal."
)


class MetadataService:
    """
    Inspects and strips metadata from media files using FFprobe and FFmpeg with shell=False.
    Never modifies the original source file.
    """

    def __init__(self, get_settings_fn: Callable[[], Dict[str, Any]]) -> None:
        self._get_settings = get_settings_fn

    def _allowed_dirs(self) -> list[str]:
        s = self._get_settings()
        return [s.get("download_dir", ""), s.get("conversion_dir", "")]

    def inspect_file(self, file_path: str | Path, check_allowed: bool = True) -> Dict[str, Any]:
        settings = self._get_settings()
        if check_allowed:
            target = validate_path_in_allowed_dirs(file_path, self._allowed_dirs(), must_exist=True)
        else:
            target = Path(file_path).resolve()
            if not target.exists():
                raise ValueError(f"File does not exist: {target.name}")

        ffprobe_bin = resolve_binary("ffprobe", settings.get("ffprobe_path", ""))
        if not ffprobe_bin:
            raise RuntimeError(
                "FFprobe executable was not found. Install FFmpeg (e.g., `winget install Gyan.FFmpeg`) "
                "or configure its path in Settings."
            )

        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(target),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if proc.returncode != 0:
            raise RuntimeError(f"FFprobe failed to inspect '{target.name}'. The file may be corrupted or unsupported.")

        try:
            raw = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse FFprobe output.") from exc

        fmt = raw.get("format", {}) or {}
        fmt_tags = fmt.get("tags", {}) or {}
        streams = raw.get("streams", []) or []
        chapters = raw.get("chapters", []) or []

        # Collect stream tags as well
        stream_tags: Dict[str, Any] = {}
        for idx, s in enumerate(streams):
            st = s.get("tags", {}) or {}
            for k, v in st.items():
                stream_tags[f"stream_{idx}_{k}"] = v

        # Normalize common fields case-insensitively
        combined_lookup = {k.lower(): v for k, v in {**stream_tags, **fmt_tags}.items()}

        def _pick(*keys: str) -> Optional[str]:
            for k in keys:
                if k in combined_lookup and str(combined_lookup[k]).strip():
                    return str(combined_lookup[k]).strip()
            return None

        normalized_fields = {
            "title": _pick("title"),
            "artist": _pick("artist", "album_artist", "performer"),
            "album": _pick("album"),
            "author": _pick("author", "composer", "writer"),
            "copyright": _pick("copyright"),
            "creation_date": _pick("creation_time", "date", "year"),
            "encoder": _pick("encoder", "encoded_by"),
            "comment": _pick("comment", "description", "synopsis"),
            "genre": _pick("genre"),
            "track": _pick("track"),
        }

        return {
            "filename": target.name,
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "format_name": fmt.get("format_name"),
            "format_long_name": fmt.get("format_long_name"),
            "duration": float(fmt["duration"]) if fmt.get("duration") else None,
            "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
            "normalized_tags": normalized_fields,
            "format_tags": fmt_tags,
            "stream_tags": stream_tags,
            "chapters_count": len(chapters),
            "streams_summary": [
                {
                    "index": s.get("index"),
                    "codec_type": s.get("codec_type"),
                    "codec_name": s.get("codec_name"),
                    "width": s.get("width"),
                    "height": s.get("height"),
                    "sample_rate": s.get("sample_rate"),
                    "channels": s.get("channels"),
                    "tags": s.get("tags", {}) or {},
                }
                for s in streams
            ],
            "total_tag_count": len(fmt_tags) + len(stream_tags) + len(chapters),
            "disclaimer": METADATA_DISCLAIMER,
        }

    def build_clean_command(self, ffmpeg_bin: str, source_path: Path, temp_output_path: Path) -> list[str]:
        return [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            "-map", "0",
            "-map_metadata", "-1",
            "-map_chapters", "-1",
            "-c", "copy",
            "-fflags", "+bitexact",
            "-flags:v", "+bitexact",
            "-flags:a", "+bitexact",
            str(temp_output_path),
        ]

    def clean_metadata(
        self,
        source_path: str | Path,
        output_filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:
        settings = self._get_settings()
        allowed = self._allowed_dirs()
        src = validate_path_in_allowed_dirs(source_path, allowed, must_exist=True)

        dest_dir_raw = output_dir or settings.get("conversion_dir") or settings.get("download_dir")
        dest_dir = validate_path_in_allowed_dirs(dest_dir_raw, allowed, must_exist=False)
        dest_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_bin = resolve_binary("ffmpeg", settings.get("ffmpeg_path", ""))
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable was not found. Please install FFmpeg or set its path in Settings.")

        before_info = self.inspect_file(src, check_allowed=False)
        if progress_cb:
            progress_cb(25.0, "Inspecting original metadata...")

        stem, ext = os.path.splitext(src.name)
        desired_name = output_filename.strip() if output_filename and output_filename.strip() else f"{stem}_clean{ext}"
        if not os.path.splitext(desired_name)[1]:
            desired_name = f"{desired_name}{ext}"

        final_path = resolve_output_filepath(
            dest_dir,
            desired_name,
            policy=duplicate_policy,
            forbid_same_as=src,
        )
        if final_path is None:
            raise FileExistsError(f"Output file '{desired_name}' already exists and duplicate policy is set to skip.")

        temp_path = final_path.with_name(f".tmp_{final_path.name}")
        if temp_path.exists():
            temp_path.unlink()

        cmd = self.build_clean_command(ffmpeg_bin, src, temp_path)
        if progress_cb:
            progress_cb(60.0, "Stripping container, stream, and chapter metadata...")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, shell=False)
            if proc.returncode != 0 or not temp_path.exists():
                err_tail = (proc.stderr or "").strip().splitlines()[-3:]
                raise RuntimeError(f"FFmpeg failed to clean metadata: {' '.join(err_tail)}")

            shutil.move(str(temp_path), str(final_path))
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        if progress_cb:
            progress_cb(90.0, "Re-inspecting cleaned file with FFprobe...")

        after_info = self.inspect_file(final_path, check_allowed=False)
        if progress_cb:
            progress_cb(100.0, "Completed")

        return {
            "source_path": str(src),
            "output_path": str(final_path),
            "output_filename": final_path.name,
            "before": before_info,
            "after": after_info,
            "removed_tag_count": max(0, before_info["total_tag_count"] - after_info["total_tag_count"]),
            "disclaimer": METADATA_DISCLAIMER,
        }
