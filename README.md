# Universal Media Downloader & Converter

A local-first, privacy-respecting desktop web application that unifies **yt-dlp**, **FFmpeg**, and **FFprobe** behind a clean FastAPI + React/TypeScript interface. Built for Windows 10/11 without advertisements, telemetry, cloud dependencies, or unsafe shell interpolation.

## Features

1. **Universal Video & Audio Downloader (`yt-dlp` Python API)**
   - Inspect single URLs or playlists before downloading (title, thumbnail, uploader, duration, upload date, video/audio stream formats, estimated size, and subtitles).
   - Select resolution presets (`Best`, `2160p/4K`, `1440p`, `1080p`, `720p`, `480p`, `360p`, or custom format ID) or extract audio directly (`MP3`, `M4A`, `WAV`, `FLAC`).
   - Selective playlist downloading, thumbnail embedding, subtitle embedding/extraction, and configurable duplicate policies (`Auto-Rename`, `Skip`, `Overwrite`).
2. **Batch Downloader & Real-Time Queue Manager**
   - Paste multiple URLs (one per line), validate all URLs upfront, and process jobs concurrently via a bounded worker pool.
   - Real-time Server-Sent Events (`/api/events/stream`) push live progress percentage, downloaded bytes, total size, transfer speed, and ETA.
   - Persist job history and settings in SQLite (`backend/data/media_tool.db`). Interrupted jobs from prior sessions are automatically marked as historical and recovered on startup.
3. **Audio Extractor (`FFmpeg`)**
   - Extract audio from local video files to `MP3`, `WAV`, `M4A`, `FLAC`, `AAC`, or `OGG` with configurable bitrate (`128k`–`320k`), sample rate (`22050`–`96000` Hz), and VBR quality.
4. **Video Converter & Compressor (`FFmpeg`)**
   - Convert between `MP4`, `MKV`, `MOV`, `AVI`, `WEBM`, and `GIF` using optimization presets (`Original`, `High`, `Balanced`, `Small File`, `Mobile`, `Web Optimized`) or custom codec/CRF/resolution controls.
5. **Audio Converter (`FFmpeg`)**
   - Transcode audio files across `MP3`, `WAV`, `FLAC`, `AAC`, `M4A`, `OGG`, and `OPUS` with bitrate, sample rate, and stereo/mono channel controls.
6. **Metadata Inspector & Cleaner (`FFprobe` + `FFmpeg`)**
   - Inspect container, stream, and chapter metadata via `ffprobe`, strip metadata into a new clean copy (`-map_metadata -1 -map_chapters -1`), and immediately reinspect the output file.
   - **Important limitation**: Metadata removal is format-dependent and is not a forensic guarantee of complete anonymization. Container muxers may retain basic structural headers (such as `encoder` or `major_brand`), and visible content, burned-in watermarks, or information embedded in the actual video/audio signal are not altered.
7. **Sandboxed Media Library Manager**
   - Browse, search, filter, sort, preview (via HTTP Range streaming), rename, delete, and reveal files in Windows Explorer strictly within configured media directories.

## Architecture

```text
universal-media-tool/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point & lifespan manager
│   │   ├── config.py                # Local defaults & CORS configuration
│   │   ├── api/                     # Modular routers (downloads, conversions, files, settings, events)
│   │   ├── services/                # JobManager, DownloadService, ConversionService, MetadataService, FileService
│   │   ├── models/schemas.py        # Pydantic validation schemas
│   │   ├── database/db.py           # Thread-safe SQLite persistence & crash recovery
│   │   └── utils/                   # URL SSRF & path-traversal security, binary discovery
│   ├── requirements.txt
│   └── tests/test_backend.py        # Unit & real FFmpeg/FFprobe integration test suite
├── frontend/
│   ├── src/
│   │   ├── components/              # Sidebar, Toast notifications
│   │   ├── pages/                   # All 9 application views
│   │   ├── hooks/useJobStream.ts    # Real-time SSE progress subscription
│   │   ├── services/api.ts          # Typed REST client
│   │   ├── utils/validation.mjs     # Client URL validation & size estimators
│   │   ├── types/index.ts           # TypeScript interfaces
│   │   └── tests/frontend.test.mjs  # Node automated frontend test suite
│   └── package.json
├── downloads/
├── converted/
└── start.bat                        # One-click Windows launcher
```

## Prerequisites & Installing on Windows

1. **Python 3.12+**
   ```powershell
   winget install Python.Python.3.12
   ```
2. **Node.js LTS (v20+)**
   ```powershell
   winget install OpenJS.NodeJS.LTS
   ```
3. **FFmpeg & FFprobe**
   ```powershell
   winget install Gyan.FFmpeg
   ```
   *(Alternatively: `choco install ffmpeg` or `scoop install ffmpeg`, or point to `C:\ffmpeg\bin\ffmpeg.exe` in the Settings page.)*

## Starting the Application

Double-click **`start.bat`** or run it from PowerShell / Command Prompt:

```cmd
start.bat
```

`start.bat` automatically checks Python, creates `backend\.venv`, installs Python and Node dependencies if needed, verifies FFmpeg, launches the FastAPI backend on `http://127.0.0.1:8000` and the Vite React UI on `http://127.0.0.1:5173`, and opens your default browser.

## Updating `yt-dlp`

Sites frequently update their streaming layouts. To update `yt-dlp` inside the virtual environment:

```cmd
backend\.venv\Scripts\python.exe -m pip install -U yt-dlp
```

## Running Automated Tests

```cmd
:: Backend unit + FFmpeg integration tests
cd backend
python -m unittest discover -s tests -v

:: Frontend validation & calculation tests
cd ..\frontend
node --test src/tests/frontend.test.mjs
```

## Privacy & Responsible Use

- Binds strictly to `127.0.0.1` by default with zero telemetry, analytics, or third-party trackers.
- Rejects non-HTTP(S) schemes and local/private network targets (SSRF protection) and restricts file operations to configured directories.
- Does not implement DRM circumvention or paywall bypassing. Use this tool only for content you own or are authorized to download and process under applicable terms and laws.
