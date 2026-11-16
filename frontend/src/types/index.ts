export type NavSection =
  | 'dashboard'
  | 'downloader'
  | 'batch'
  | 'audio-extractor'
  | 'video-converter'
  | 'audio-converter'
  | 'metadata-cleaner'
  | 'media-library'
  | 'settings';

export type JobType =
  | 'download'
  | 'audio_extract'
  | 'video_convert'
  | 'audio_convert'
  | 'metadata_clean';

export type JobStatus =
  | 'waiting'
  | 'paused'
  | 'fetching_info'
  | 'downloading'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type DuplicatePolicy = 'skip' | 'rename' | 'overwrite';

export interface FormatOption {
  format_id: string;
  ext: string;
  resolution: string;
  fps?: number | null;
  vcodec?: string | null;
  acodec?: string | null;
  filesize?: number | null;
  tbr?: number | null;
  note?: string | null;
  is_audio_only: boolean;
}

export interface PlaylistEntryInfo {
  index: number;
  id: string;
  title: string;
  url: string;
  duration?: number | null;
  uploader?: string | null;
  thumbnail?: string | null;
}

export interface MediaProbeResponse {
  url: string;
  title: string;
  thumbnail?: string | null;
  uploader?: string | null;
  duration?: number | null;
  upload_date?: string | null;
  webpage_url: string;
  extractor?: string | null;
  is_playlist: boolean;
  playlist_title?: string | null;
  playlist_count: number;
  playlist_entries: PlaylistEntryInfo[];
  video_formats: FormatOption[];
  audio_formats: FormatOption[];
  estimated_size_bytes?: number | null;
  subtitles: string[];
}

export interface JobRecord {
  id: string;
  job_type: JobType;
  title: string;
  source: string;
  thumbnail?: string | null;
  status: JobStatus;
  progress: number;
  downloaded_bytes: number;
  total_bytes?: number | null;
  speed_bps?: number | null;
  eta_seconds?: number | null;
  destination_path?: string | null;
  destination_filename?: string | null;
  error_message?: string | null;
  options: Record<string, unknown>;
  result_meta: Record<string, unknown>;
  is_historical: boolean;
  created_at: string;
  updated_at: string;
}

export interface MediaFileItem {
  name: string;
  path: string;
  directory: string;
  extension: string;
  category: 'video' | 'audio' | 'other';
  mime_type: string;
  size_bytes: number;
  modified_at: string;
  modified_ts: number;
}

export interface MetadataInspection {
  filename: string;
  path: string;
  size_bytes: number;
  format_name?: string;
  format_long_name?: string;
  duration?: number | null;
  bit_rate?: number | null;
  normalized_tags: {
    title?: string | null;
    artist?: string | null;
    album?: string | null;
    author?: string | null;
    copyright?: string | null;
    creation_date?: string | null;
    encoder?: string | null;
    comment?: string | null;
    genre?: string | null;
    track?: string | null;
  };
  format_tags: Record<string, string>;
  stream_tags: Record<string, string>;
  chapters_count: number;
  total_tag_count: number;
  disclaimer: string;
}

export interface AppSettings {
  download_dir: string;
  conversion_dir: string;
  max_concurrent_downloads: number;
  default_video_quality: string;
  default_audio_format: string;
  default_audio_bitrate: string;
  duplicate_handling: DuplicatePolicy;
  theme: 'dark' | 'light';
  ffmpeg_path: string;
  ffprobe_path: string;
  ytdlp_check_updates: boolean;
  enable_browser_cookies: boolean;
  browser_for_cookies: string;
  embed_thumbnail: boolean;
  embed_subtitles: boolean;
}

export interface EnvironmentDiagnostics {
  ffmpeg: {
    available: boolean;
    path?: string | null;
    version?: string | null;
    install_hint: string;
  };
  ffprobe: {
    available: boolean;
    path?: string | null;
    version?: string | null;
    install_hint: string;
  };
  yt_dlp: {
    available: boolean;
    version?: string | null;
    mode?: string;
    install_hint?: string;
  };
}
