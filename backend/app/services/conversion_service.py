from __future__ import annotations
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.models.schemas import (
    AudioConvertRequest,
    AudioExtractRequest,
    DuplicatePolicy,
    VideoConvertRequest,
)
from app.utils.binaries import check_disk_space, resolve_binary
from app.utils.security import resolve_output_filepath, validate_path_in_allowed_dirs


VIDEO_PRESET_PROFILES: Dict[str, Dict[str, Any]] = {
    "original": {"crf": 18, "encoder_preset": "fast", "resolution": "original"},
    "high": {"crf": 19, "encoder_preset": "slow", "resolution": "original"},
    "balanced": {"crf": 23, "encoder_preset": "medium", "resolution": "original"},
    "small": {"crf": 28, "encoder_preset": "faster", "resolution": "1280x720"},
    "mobile": {"crf": 26, "encoder_preset": "fast", "resolution": "1280x720"},
    "web": {"crf": 24, "encoder_preset": "fast", "resolution": "1920x1080"},
}

RESOLUTION_MAP = {
    "2160p": "3840:2160",
    "3840x2160": "3840:2160",
    "1440p": "2560:1440",
    "2560x1440": "2560:1440",
    "1080p": "1920:1080",
    "1920x1080": "1920:1080",
    "720p": "1280:720",
    "1280x720": "1280:720",
    "480p": "854:480",
    "854x480": "854:480",
    "360p": "640:360",
    "640x360": "640:360",
}

AUDIO_CODEC_BY_FORMAT = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "flac": "flac",
    "aac": "aac",
    "m4a": "aac",
    "ogg": "libvorbis",
    "opus": "libopus",
}


class ConversionCancelledError(Exception):
    """Raised when an active FFmpeg conversion is cancelled by the user."""


class ConversionService:
    """
    Executes audio extraction, video conversion/compression, and audio conversion
    using FFmpeg with real-time progress parsing and atomic temporary file handling.
    """

    def __init__(self, get_settings_fn: Callable[[], Dict[str, Any]]) -> None:
        self._get_settings = get_settings_fn

    def _allowed_dirs(self) -> list[str]:
        s = self._get_settings()
        return [s.get("download_dir", ""), s.get("conversion_dir", "")]

    def probe_duration(self, source_path: Path) -> Optional[float]:
        settings = self._get_settings()
        ffprobe_bin = resolve_binary("ffprobe", settings.get("ffprobe_path", ""))
        if not ffprobe_bin:
            return None
        try:
            proc = subprocess.run(
                [
                    ffprobe_bin,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(source_path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return max(0.01, float(proc.stdout.strip()))
        except Exception:
            pass
        return None

    def estimate_output_size(
        self,
        source_path: str | Path,
        target_bitrate_kbps: Optional[int] = None,
        crf: Optional[int] = None,
    ) -> Dict[str, Any]:
        src = validate_path_in_allowed_dirs(source_path, self._allowed_dirs(), must_exist=True)
        src_size = src.stat().st_size
        duration = self.probe_duration(src)
        if duration and target_bitrate_kbps:
            est = int((target_bitrate_kbps * 1000 / 8) * duration)
        elif crf is not None:
            # Empirical ratio relative to CRF 23 baseline
            factor = 2 ** ((23 - crf) / 6.0)
            est = int(src_size * min(1.5, max(0.18, 0.65 * factor)))
        else:
            est = int(src_size * 0.75)

        return {
            "source_size_bytes": src_size,
            "duration_seconds": duration,
            "estimated_output_bytes": max(1024, est),
        }

    # ---------------- Command Builders (Testable & Deterministic) ----------------

    @staticmethod
    def build_audio_extract_command(
        ffmpeg_bin: str,
        source_path: Path,
        temp_output_path: Path,
        req: AudioExtractRequest,
    ) -> List[str]:
        codec = AUDIO_CODEC_BY_FORMAT.get(req.output_format, "libmp3lame")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            "-vn",
            "-acodec", codec,
            "-ar", str(req.sample_rate),
        ]
        if req.output_format not in ("wav", "flac"):
            cmd.extend(["-b:a", req.bitrate])
        if req.output_format == "mp3":
            cmd.extend(["-q:a", str(req.audio_quality)])
        cmd.extend([
            "-progress", "pipe:1",
            "-nostats",
            str(temp_output_path),
        ])
        return cmd

    @staticmethod
    def build_audio_convert_command(
        ffmpeg_bin: str,
        source_path: Path,
        temp_output_path: Path,
        req: AudioConvertRequest,
    ) -> List[str]:
        codec = req.codec or AUDIO_CODEC_BY_FORMAT.get(req.output_format, "libmp3lame")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            "-vn",
            "-acodec", codec,
            "-ar", str(req.sample_rate),
            "-ac", str(req.channels),
        ]
        if req.output_format not in ("wav", "flac"):
            cmd.extend(["-b:a", req.bitrate])
        cmd.extend([
            "-progress", "pipe:1",
            "-nostats",
            str(temp_output_path),
        ])
        return cmd

    @staticmethod
    def build_video_convert_command(
        ffmpeg_bin: str,
        source_path: Path,
        temp_output_path: Path,
        req: VideoConvertRequest,
    ) -> List[str]:
        profile = VIDEO_PRESET_PROFILES.get(req.preset_profile, {})
        crf = profile.get("crf", req.crf) if req.preset_profile != "custom" else req.crf
        preset = profile.get("encoder_preset", req.encoder_preset) if req.preset_profile != "custom" else req.encoder_preset
        resolution = profile.get("resolution", req.resolution) if req.preset_profile != "custom" and req.resolution == "original" else req.resolution

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
        ]

        if req.output_format == "gif":
            scale_expr = RESOLUTION_MAP.get(resolution, "480:-1").split(":")[0]
            fps_val = req.fps or 12
            cmd.extend([
                "-vf", f"fps={fps_val},scale={scale_expr}:-1:flags=lanczos",
                "-loop", "0",
            ])
        else:
            vcodec = req.video_codec
            if req.output_format == "webm" and vcodec in ("libx264", "libx265"):
                vcodec = "libvpx-vp9"

            cmd.extend(["-c:v", vcodec])
            if vcodec != "copy":
                if vcodec in ("libx264", "libx265"):
                    cmd.extend(["-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"])
                elif vcodec == "libvpx-vp9":
                    cmd.extend(["-crf", str(crf), "-b:v", req.video_bitrate or "0"])

                if req.video_bitrate and vcodec != "libvpx-vp9":
                    cmd.extend(["-b:v", req.video_bitrate])

                vf_filters: List[str] = []
                if resolution != "original" and resolution in RESOLUTION_MAP:
                    vf_filters.append(f"scale={RESOLUTION_MAP[resolution]}")
                if req.fps:
                    vf_filters.append(f"fps={req.fps}")
                if vf_filters:
                    cmd.extend(["-vf", ",".join(vf_filters)])

            if not req.include_audio:
                cmd.append("-an")
            else:
                acodec = req.audio_codec
                if req.output_format == "webm" and acodec == "aac":
                    acodec = "libopus"
                cmd.extend(["-c:a", acodec])
                if acodec != "copy":
                    cmd.extend(["-b:a", req.audio_bitrate])

            if req.output_format in ("mp4", "mov"):
                cmd.extend(["-movflags", "+faststart"])

        cmd.extend([
            "-progress", "pipe:1",
            "-nostats",
            str(temp_output_path),
        ])
        return cmd

    # ---------------- Execution Engine ----------------

    def _run_ffmpeg_with_progress(
        self,
        cmd: List[str],
        temp_path: Path,
        final_path: Path,
        total_duration: Optional[float],
        progress_cb: Optional[Callable[[Dict[str, Any]], None]],
        cancel_event: Optional[threading.Event],
    ) -> Path:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
        )

        stderr_lines: List[str] = []

        def _drain_stderr() -> None:
            if not proc.stderr:
                return
            try:
                for err_line in proc.stderr:
                    stderr_lines.append(err_line)
                    if len(stderr_lines) > 50:
                        stderr_lines.pop(0)
            except Exception:
                pass

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        last_Size = 0
        try:
            if proc.stdout:
                for raw_line in proc.stdout:
                    if cancel_event and cancel_event.is_set():
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        raise ConversionCancelledError("Operation cancelled by user.")

                    line = raw_line.strip()
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()

                    if key == "total_size" and val.isdigit():
                        last_Size = int(val)
                    elif key in ("out_time_us", "out_time_ms") and val.lstrip("-").isdigit():
                        us = int(val)
                        if us > 0 and total_duration and total_duration > 0:
                            elapsed_sec = us / 1_000_000.0
                            pct = min(99.0, max(1.0, (elapsed_sec / total_duration) * 100.0))
                            if progress_cb:
                                progress_cb({
                                    "progress": round(pct, 1),
                                    "downloaded_bytes": last_Size,
                                })
                    elif key == "progress" and val == "end":
                        if progress_cb:
                            progress_cb({"progress": 99.5, "downloaded_bytes": last_Size})

            proc.wait()
            stderr_thread.join(timeout=2)
            if cancel_event and cancel_event.is_set():
                raise ConversionCancelledError("Operation cancelled by user.")

            if proc.returncode != 0 or not temp_path.exists():
                tail = " ".join(s.strip() for s in stderr_lines[-4:] if s.strip())
                raise RuntimeError(f"FFmpeg processing failed (exit {proc.returncode}): {tail}")

            shutil.move(str(temp_path), str(final_path))
            return final_path
        finally:
            if proc.stdout:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            if proc.stderr:
                try:
                    proc.stderr.close()
                except Exception:
                    pass
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def run_audio_extraction(
        self,
        req: AudioExtractRequest,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        settings = self._get_settings()
        allowed = self._allowed_dirs()
        src = validate_path_in_allowed_dirs(req.source_path, allowed, must_exist=True)

        dest_dir_raw = req.output_dir or settings.get("conversion_dir")
        dest_dir = validate_path_in_allowed_dirs(dest_dir_raw, allowed, must_exist=False)
        dest_dir.mkdir(parents=True, exist_ok=True)

        space = check_disk_space(dest_dir)
        if not space["has_enough_space"]:
            raise RuntimeError("Insufficient disk space in destination directory.")

        ffmpeg_bin = resolve_binary("ffmpeg", settings.get("ffmpeg_path", ""))
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable was not found. Install FFmpeg or configure its path in Settings.")

        stem = os.path.splitext(src.name)[0]
        desired = req.output_filename.strip() if req.output_filename and req.output_filename.strip() else f"{stem}.{req.output_format}"
        if not desired.lower().endswith(f".{req.output_format}"):
            desired = f"{os.path.splitext(desired)[0]}.{req.output_format}"

        final_path = resolve_output_filepath(dest_dir, desired, policy=req.duplicate_policy, forbid_same_as=src)
        if final_path is None:
            raise FileExistsError(f"File '{desired}' already exists and duplicate handling is set to skip.")

        temp_path = final_path.with_name(f".tmp_{final_path.stem}.{req.output_format}")
        duration = self.probe_duration(src)
        cmd = self.build_audio_extract_command(ffmpeg_bin, src, temp_path, req)

        out = self._run_ffmpeg_with_progress(cmd, temp_path, final_path, duration, progress_cb, cancel_event)

        if req.remove_original and out.exists() and out.stat().st_size > 0 and src.exists():
            try:
                src.unlink()
            except OSError:
                pass

        return {
            "output_path": str(out),
            "output_filename": out.name,
            "size_bytes": out.stat().st_size,
            "removed_original": req.remove_original,
        }

    def run_video_conversion(
        self,
        req: VideoConvertRequest,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        settings = self._get_settings()
        allowed = self._allowed_dirs()
        src = validate_path_in_allowed_dirs(req.source_path, allowed, must_exist=True)

        dest_dir_raw = req.output_dir or settings.get("conversion_dir")
        dest_dir = validate_path_in_allowed_dirs(dest_dir_raw, allowed, must_exist=False)
        dest_dir.mkdir(parents=True, exist_ok=True)

        space = check_disk_space(dest_dir)
        if not space["has_enough_space"]:
            raise RuntimeError("Insufficient disk space in destination directory.")

        ffmpeg_bin = resolve_binary("ffmpeg", settings.get("ffmpeg_path", ""))
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable was not found. Install FFmpeg or configure its path in Settings.")

        stem = os.path.splitext(src.name)[0]
        desired = req.output_filename.strip() if req.output_filename and req.output_filename.strip() else f"{stem}_{req.preset_profile}.{req.output_format}"
        if not desired.lower().endswith(f".{req.output_format}"):
            desired = f"{os.path.splitext(desired)[0]}.{req.output_format}"

        final_path = resolve_output_filepath(dest_dir, desired, policy=req.duplicate_policy, forbid_same_as=src)
        if final_path is None:
            raise FileExistsError(f"File '{desired}' already exists and duplicate handling is set to skip.")

        temp_path = final_path.with_name(f".tmp_{final_path.stem}.{req.output_format}")
        duration = self.probe_duration(src)
        cmd = self.build_video_convert_command(ffmpeg_bin, src, temp_path, req)

        out = self._run_ffmpeg_with_progress(cmd, temp_path, final_path, duration, progress_cb, cancel_event)
        return {
            "output_path": str(out),
            "output_filename": out.name,
            "size_bytes": out.stat().st_size,
        }

    def run_audio_conversion(
        self,
        req: AudioConvertRequest,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        settings = self._get_settings()
        allowed = self._allowed_dirs()
        src = validate_path_in_allowed_dirs(req.source_path, allowed, must_exist=True)

        dest_dir_raw = req.output_dir or settings.get("conversion_dir")
        dest_dir = validate_path_in_allowed_dirs(dest_dir_raw, allowed, must_exist=False)
        dest_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_bin = resolve_binary("ffmpeg", settings.get("ffmpeg_path", ""))
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg executable was not found. Install FFmpeg or configure its path in Settings.")

        stem = os.path.splitext(src.name)[0]
        desired = req.output_filename.strip() if req.output_filename and req.output_filename.strip() else f"{stem}_converted.{req.output_format}"
        if not desired.lower().endswith(f".{req.output_format}"):
            desired = f"{os.path.splitext(desired)[0]}.{req.output_format}"

        final_path = resolve_output_filepath(dest_dir, desired, policy=req.duplicate_policy, forbid_same_as=src)
        if final_path is None:
            raise FileExistsError(f"File '{desired}' already exists and duplicate handling is set to skip.")

        temp_path = final_path.with_name(f".tmp_{final_path.stem}.{req.output_format}")
        duration = self.probe_duration(src)
        cmd = self.build_audio_convert_command(ffmpeg_bin, src, temp_path, req)

        out = self._run_ffmpeg_with_progress(cmd, temp_path, final_path, duration, progress_cb, cancel_event)
        return {
            "output_path": str(out),
            "output_filename": out.name,
            "size_bytes": out.stat().st_size,
        }
