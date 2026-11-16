from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from pydantic import field_validator  # type: ignore
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import validator as _v1_validator  # type: ignore
    PYDANTIC_V2 = False

    def field_validator(*fields: str, **kwargs: Any):  # type: ignore
        return _v1_validator(*fields, allow_reuse=True)


def _compat_field(*args: Any, pattern: Optional[str] = None, **kwargs: Any) -> Any:
    if pattern is not None:
        if PYDANTIC_V2:
            kwargs["pattern"] = pattern
        else:
            kwargs["regex"] = pattern
    return Field(*args, **kwargs)


class CompatBaseModel(BaseModel):
    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()  # type: ignore[attr-defined]
        return self.dict()  # type: ignore[attr-defined]

    def model_dump(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if PYDANTIC_V2:
            return super().model_dump(*args, **kwargs)  # type: ignore[misc]
        return self.dict(*args, **kwargs)


class JobType(str, Enum):
    DOWNLOAD = "download"
    AUDIO_EXTRACT = "audio_extract"
    VIDEO_CONVERT = "video_convert"
    AUDIO_CONVERT = "audio_convert"
    METADATA_CLEAN = "metadata_clean"


class JobStatus(str, Enum):
    WAITING = "waiting"
    PAUSED = "paused"
    FETCHING_INFO = "fetching_info"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DuplicatePolicy(str, Enum):
    SKIP = "skip"
    RENAME = "rename"
    OVERWRITE = "overwrite"


class UrlProbeRequest(CompatBaseModel):
    url: str = _compat_field(..., min_length=4, max_length=2048)


class BatchProbeRequest(CompatBaseModel):
    urls: List[str] = _compat_field(..., min_items=1 if not PYDANTIC_V2 else None, min_length=1 if PYDANTIC_V2 else None)


class FormatOption(CompatBaseModel):
    format_id: str
    ext: str
    resolution: str
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    tbr: Optional[float] = None
    note: Optional[str] = None
    is_audio_only: bool = False


class PlaylistEntryInfo(CompatBaseModel):
    index: int
    id: str
    title: str
    url: str
    duration: Optional[float] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None


class MediaProbeResponse(CompatBaseModel):
    url: str
    title: str
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    duration: Optional[float] = None
    upload_date: Optional[str] = None
    webpage_url: str
    extractor: Optional[str] = None
    is_playlist: bool = False
    playlist_title: Optional[str] = None
    playlist_count: int = 0
    playlist_entries: List[PlaylistEntryInfo] = Field(default_factory=list)
    video_formats: List[FormatOption] = Field(default_factory=list)
    audio_formats: List[FormatOption] = Field(default_factory=list)
    estimated_size_bytes: Optional[int] = None
    subtitles: List[str] = Field(default_factory=list)


class DownloadCreateRequest(CompatBaseModel):
    urls: List[str]
    mode: str = _compat_field(default="video", pattern="^(video|audio)$")
    video_quality: str = _compat_field(default="1080p")
    custom_format_id: Optional[str] = None
    audio_format: str = _compat_field(default="mp3")
    audio_bitrate: str = _compat_field(default="320k")
    output_dir: Optional[str] = None
    custom_filename: Optional[str] = None
    embed_thumbnail: bool = False
    embed_subtitles: bool = False
    download_subtitles_separately: bool = False
    subtitle_langs: List[str] = Field(default_factory=lambda: ["en"])
    include_playlist: bool = False
    playlist_items: Optional[List[int]] = None
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME


class AudioExtractRequest(CompatBaseModel):
    source_path: str
    output_format: str = _compat_field(default="mp3", pattern="^(mp3|wav|m4a|flac|aac|ogg)$")
    bitrate: str = _compat_field(default="192k", pattern="^(128k|192k|256k|320k)$")
    sample_rate: int = _compat_field(default=44100)
    audio_quality: int = _compat_field(default=2, ge=0, le=9)
    output_filename: Optional[str] = None
    output_dir: Optional[str] = None
    remove_original: bool = False
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        if v not in (22050, 44100, 48000, 96000):
            raise ValueError("Sample rate must be 22050, 44100, 48000, or 96000 Hz")
        return v


class VideoConvertRequest(CompatBaseModel):
    source_path: str
    output_format: str = _compat_field(default="mp4", pattern="^(mp4|mkv|mov|avi|webm|gif)$")
    preset_profile: str = _compat_field(
        default="balanced",
        pattern="^(original|high|balanced|small|mobile|web|custom)$",
    )
    video_codec: str = _compat_field(default="libx264")
    audio_codec: str = _compat_field(default="aac")
    resolution: str = _compat_field(default="original")
    video_bitrate: Optional[str] = None
    audio_bitrate: str = _compat_field(default="192k")
    fps: Optional[int] = _compat_field(default=None, ge=1, le=120)
    crf: int = _compat_field(default=23, ge=0, le=51)
    encoder_preset: str = _compat_field(
        default="medium",
        pattern="^(ultrafast|superfast|veryfast|faster|fast|medium|slow|slower|veryslow)$",
    )
    include_audio: bool = True
    output_filename: Optional[str] = None
    output_dir: Optional[str] = None
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME


class AudioConvertRequest(CompatBaseModel):
    source_path: str
    output_format: str = _compat_field(default="mp3", pattern="^(mp3|wav|flac|aac|m4a|ogg|opus)$")
    bitrate: str = _compat_field(default="192k", pattern="^(64k|96k|128k|160k|192k|256k|320k)$")
    sample_rate: int = _compat_field(default=44100)
    channels: int = _compat_field(default=2, ge=1, le=2)
    codec: Optional[str] = None
    output_filename: Optional[str] = None
    output_dir: Optional[str] = None
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME

    @field_validator("sample_rate")
    @classmethod
    def validate_sr(cls, v: int) -> int:
        if v not in (16000, 22050, 44100, 48000, 96000):
            raise ValueError("Unsupported sample rate")
        return v


class MetadataInspectRequest(CompatBaseModel):
    source_path: str


class MetadataCleanRequest(CompatBaseModel):
    source_path: str
    output_filename: Optional[str] = None
    output_dir: Optional[str] = None
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME


class FileRenameRequest(CompatBaseModel):
    path: str
    new_name: str = _compat_field(..., min_length=1, max_length=255)


class FileOpenRequest(CompatBaseModel):
    path: str
    reveal_in_folder: bool = False


class SettingsUpdateModel(CompatBaseModel):
    download_dir: Optional[str] = None
    conversion_dir: Optional[str] = None
    max_concurrent_downloads: Optional[int] = _compat_field(default=None, ge=1, le=10)
    default_video_quality: Optional[str] = None
    default_audio_format: Optional[str] = None
    default_audio_bitrate: Optional[str] = None
    duplicate_handling: Optional[DuplicatePolicy] = None
    theme: Optional[str] = _compat_field(default=None, pattern="^(dark|light)$")
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None
    ytdlp_check_updates: Optional[bool] = None
    enable_browser_cookies: Optional[bool] = None
    browser_for_cookies: Optional[str] = None
    embed_thumbnail: Optional[bool] = None
    embed_subtitles: Optional[bool] = None


class JobRecord(CompatBaseModel):
    id: str
    job_type: JobType
    title: str
    source: str
    thumbnail: Optional[str] = None
    status: JobStatus
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[int] = None
    destination_path: Optional[str] = None
    destination_filename: Optional[str] = None
    error_message: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    result_meta: Dict[str, Any] = Field(default_factory=dict)
    is_historical: bool = False
    created_at: str
    updated_at: str
