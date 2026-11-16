from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.models.schemas import (
    DownloadCreateRequest,
    DuplicatePolicy,
    FormatOption,
    JobStatus,
    MediaProbeResponse,
    PlaylistEntryInfo,
)
from app.utils.binaries import check_disk_space, resolve_binary
from app.utils.security import (
    resolve_output_filepath,
    sanitize_filename,
    validate_download_url,
    validate_path_in_allowed_dirs,
)


QUALITY_FORMAT_EXPRESSIONS: Dict[str, str] = {
    "best": "bestvideo*+bestaudio/best",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
}


class DownloadCancelledError(Exception):
    """Raised inside yt-dlp progress hook when a user cancels an active download."""


class DownloadService:
    """
    Uses yt-dlp's Python API (`yt_dlp.YoutubeDL`) with real progress hooks and
    postprocessor hooks to probe and download media safely without shell interpolation.
    """

    def __init__(self, get_settings_fn: Callable[[], Dict[str, Any]]) -> None:
        self._get_settings = get_settings_fn

    def _allowed_dirs(self) -> list[str]:
        s = self._get_settings()
        return [s.get("download_dir", ""), s.get("conversion_dir", "")]

    @staticmethod
    def _load_yt_dlp() -> Any:
        try:
            import yt_dlp  # type: ignore
            return yt_dlp
        except ImportError as exc:
            raise RuntimeError(
                "yt-dlp Python package is not installed. Run `pip install -U yt-dlp` or launch via `start.bat`."
            ) from exc

    def probe_url(self, url: str) -> MediaProbeResponse:
        clean_url = validate_download_url(url)
        yt_dlp = self._load_yt_dlp()
        settings = self._get_settings()

        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "socket_timeout": 20,
        }
        if settings.get("enable_browser_cookies") and settings.get("browser_for_cookies"):
            ydl_opts["cookiesfrombrowser"] = (settings["browser_for_cookies"],)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)

        if not info:
            raise ValueError("Unable to extract media information from the provided URL.")

        is_playlist = info.get("_type") in ("playlist", "multi_video") or "entries" in info
        playlist_entries: List[PlaylistEntryInfo] = []
        video_formats: List[FormatOption] = []
        audio_formats: List[FormatOption] = []
        estimated_size: Optional[int] = None

        if is_playlist:
            raw_entries = [e for e in (info.get("entries") or []) if e]
            for idx, entry in enumerate(raw_entries, start=1):
                entry_url = entry.get("url") or entry.get("webpage_url") or clean_url
                playlist_entries.append(
                    PlaylistEntryInfo(
                        index=idx,
                        id=str(entry.get("id") or idx),
                        title=entry.get("title") or f"Track {idx}",
                        url=entry_url,
                        duration=entry.get("duration"),
                        uploader=entry.get("uploader") or entry.get("channel"),
                        thumbnail=entry.get("thumbnail"),
                    )
                )
        else:
            for f in info.get("formats") or []:
                fid = str(f.get("format_id") or "")
                ext = str(f.get("ext") or "mp4")
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                height = f.get("height")
                width = f.get("width")
                fsize = f.get("filesize") or f.get("filesize_approx")
                is_audio = vcodec in (None, "none") and acodec not in (None, "none")
                res_label = "audio only" if is_audio else (f"{height}p" if height else (f.get("resolution") or "unknown"))

                opt = FormatOption(
                    format_id=fid,
                    ext=ext,
                    resolution=res_label,
                    fps=f.get("fps"),
                    vcodec=vcodec,
                    acodec=acodec,
                    filesize=fsize,
                    tbr=f.get("tbr"),
                    note=f.get("format_note"),
                    is_audio_only=is_audio,
                )
                if is_audio:
                    audio_formats.append(opt)
                elif vcodec not in (None, "none"):
                    video_formats.append(opt)
                    if fsize and (estimated_size is None or fsize > estimated_size):
                        estimated_size = fsize

        subtitles = list((info.get("subtitles") or {}).keys())

        return MediaProbeResponse(
            url=clean_url,
            title=info.get("title") or "Untitled Media",
            thumbnail=info.get("thumbnail"),
            uploader=info.get("uploader") or info.get("channel"),
            duration=info.get("duration"),
            upload_date=info.get("upload_date"),
            webpage_url=info.get("webpage_url") or clean_url,
            extractor=info.get("extractor_key") or info.get("extractor"),
            is_playlist=is_playlist,
            playlist_title=info.get("title") if is_playlist else None,
            playlist_count=len(playlist_entries) if is_playlist else 1,
            playlist_entries=playlist_entries,
            video_formats=video_formats,
            audio_formats=audio_formats,
            estimated_size_bytes=estimated_size or info.get("filesize") or info.get("filesize_approx"),
            subtitles=subtitles,
        )

    def build_ytdlp_options(
        self,
        req: DownloadCreateRequest,
        output_dir: Path,
        ffmpeg_bin: Optional[str],
        progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        postprocessor_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        settings = self._get_settings()

        if req.custom_filename and req.custom_filename.strip():
            clean_stem = os.path.splitext(sanitize_filename(req.custom_filename.strip()))[0]
            outtmpl = str(output_dir / f"{clean_stem}.%(ext)s")
        else:
            outtmpl = str(output_dir / "%(title).150B [%(id)s].%(ext)s")

        postprocessors: List[Dict[str, Any]] = []

        if req.mode == "audio":
            fmt_expr = "bestaudio/best"
            if req.audio_format != "best":
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": req.audio_format,
                    "preferredquality": req.audio_bitrate.rstrip("k"),
                })
        else:
            if req.custom_format_id and req.custom_format_id.strip():
                fmt_expr = f"{req.custom_format_id.strip()}+bestaudio/best"
            else:
                fmt_expr = QUALITY_FORMAT_EXPRESSIONS.get(
                    req.video_quality,
                    QUALITY_FORMAT_EXPRESSIONS["1080p"],
                )

        if req.embed_thumbnail:
            postprocessors.append({"key": "EmbedThumbnail"})
        if req.embed_subtitles:
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        opts: Dict[str, Any] = {
            "format": fmt_expr,
            "outtmpl": outtmpl,
            "noplaylist": not req.include_playlist,
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": req.embed_thumbnail,
            "writesubtitles": req.embed_subtitles or req.download_subtitles_separately,
            "subtitleslangs": req.subtitle_langs or ["en"],
            "overwrites": req.duplicate_policy == DuplicatePolicy.OVERWRITE,
            "nopart": False,
            "postprocessors": postprocessors,
            "progress_hooks": [progress_hook] if progress_hook else [],
            "postprocessor_hooks": [postprocessor_hook] if postprocessor_hook else [],
        }

        if req.mode == "video":
            opts["merge_output_format"] = "mp4"

        if req.include_playlist and req.playlist_items:
            opts["playlist_items"] = ",".join(str(i) for i in req.playlist_items if i > 0)

        if ffmpeg_bin:
            opts["ffmpeg_location"] = str(Path(ffmpeg_bin).parent)

        if settings.get("enable_browser_cookies") and settings.get("browser_for_cookies"):
            opts["cookiesfrombrowser"] = (settings["browser_for_cookies"],)

        return opts

    def execute_download(
        self,
        url: str,
        req: DownloadCreateRequest,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        clean_url = validate_download_url(url)
        settings = self._get_settings()
        allowed = self._allowed_dirs()

        dest_dir_raw = req.output_dir or settings.get("download_dir")
        dest_dir = validate_path_in_allowed_dirs(dest_dir_raw, allowed, must_exist=False)
        dest_dir.mkdir(parents=True, exist_ok=True)

        space = check_disk_space(dest_dir)
        if not space["has_enough_space"]:
            raise RuntimeError("Insufficient disk space in destination download directory.")

        ffmpeg_bin = resolve_binary("ffmpeg", settings.get("ffmpeg_path", ""))
        yt_dlp = self._load_yt_dlp()

        final_filepath: Optional[str] = None
        last_title: Optional[str] = None
        last_thumb: Optional[str] = None

        def _on_progress(d: Dict[str, Any]) -> None:
            nonlocal final_filepath, last_title, last_thumb
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledError("Download cancelled by user.")

            info_dict = d.get("info_dict") or {}
            if info_dict.get("title"):
                last_title = info_dict.get("title")
            if info_dict.get("thumbnail"):
                last_thumb = info_dict.get("thumbnail")

            status = d.get("status")
            if status == "downloading":
                downloaded = int(d.get("downloaded_bytes") or 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                total_int = int(total) if total else None
                pct = (downloaded / total_int * 100.0) if total_int and total_int > 0 else 0.0
                if progress_cb:
                    progress_cb({
                        "status": JobStatus.DOWNLOADING,
                        "title": last_title,
                        "thumbnail": last_thumb,
                        "progress": round(min(99.0, pct), 1),
                        "downloaded_bytes": downloaded,
                        "total_bytes": total_int,
                        "speed_bps": d.get("speed"),
                        "eta_seconds": int(d["eta"]) if d.get("eta") is not None else None,
                        "destination_filename": os.path.basename(d.get("filename") or ""),
                    })
            elif status == "finished":
                final_filepath = d.get("filename")
                if progress_cb:
                    progress_cb({
                        "status": JobStatus.PROCESSING,
                        "progress": 99.0,
                        "speed_bps": None,
                        "eta_seconds": 0,
                        "destination_path": final_filepath,
                        "destination_filename": os.path.basename(final_filepath or ""),
                    })

        def _on_postprocessor(d: Dict[str, Any]) -> None:
            nonlocal final_filepath
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelledError("Download cancelled during post-processing.")
            info_dict = d.get("info_dict") or {}
            if info_dict.get("filepath"):
                final_filepath = info_dict["filepath"]

        opts = self.build_ytdlp_options(req, dest_dir, ffmpeg_bin, _on_progress, _on_postprocessor)

        if progress_cb:
            progress_cb({"status": JobStatus.FETCHING_INFO, "progress": 2.0})

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if info:
                last_title = info.get("title") or last_title
                last_thumb = info.get("thumbnail") or last_thumb
                if not final_filepath:
                    final_filepath = ydl.prepare_filename(info)

        return {
            "title": last_title or "Downloaded Media",
            "thumbnail": last_thumb,
            "destination_path": final_filepath,
            "destination_filename": os.path.basename(final_filepath) if final_filepath else None,
        }
