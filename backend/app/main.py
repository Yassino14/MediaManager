from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversions, downloads, events, files, settings
from app.config import ALLOWED_ORIGINS, DB_PATH, HOST, PORT
from app.database.db import DatabaseManager
from app.models.schemas import JobStatus
from app.services.conversion_service import ConversionService
from app.services.download_service import DownloadService
from app.services.file_service import FileService
from app.services.job_manager import JobManager
from app.services.metadata_service import MetadataService
from app.utils.binaries import get_environment_diagnostics


def create_app(db_path: Optional[Path] = None) -> FastAPI:
    db = DatabaseManager(db_path or DB_PATH)
    dl_service = DownloadService(db.get_settings)
    conv_service = ConversionService(db.get_settings)
    meta_service = MetadataService(db.get_settings)
    file_service = FileService(db.get_settings)
    job_manager = JobManager(db, dl_service, conv_service, meta_service)

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        job_manager.bind_event_loop(asyncio.get_running_loop())
        yield
        job_manager.shutdown()

    app_instance = FastAPI(
        title="Universal Media Downloader & Converter API",
        version="1.0.0",
        description="Local-first desktop web application powered by yt-dlp, FFmpeg, FastAPI, and SQLite.",
        lifespan=lifespan,
    )

    app_instance.state.db = db
    app_instance.state.download_service = dl_service
    app_instance.state.conversion_service = conv_service
    app_instance.state.metadata_service = meta_service
    app_instance.state.file_service = file_service
    app_instance.state.job_manager = job_manager

    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app_instance.include_router(downloads.router)
    app_instance.include_router(conversions.router)
    app_instance.include_router(files.router)
    app_instance.include_router(settings.router)
    app_instance.include_router(events.router)

    @app_instance.get("/api/dashboard")
    def get_dashboard_overview():
        all_jobs = db.list_jobs(limit=500)
        total_downloads = sum(1 for j in all_jobs if j.job_type.value == "download")
        completed_jobs = sum(1 for j in all_jobs if j.status == JobStatus.COMPLETED)
        active_jobs = sum(
            1
            for j in all_jobs
            if j.status in (JobStatus.WAITING, JobStatus.FETCHING_INFO, JobStatus.DOWNLOADING, JobStatus.PROCESSING)
        )
        failed_jobs = sum(1 for j in all_jobs if j.status == JobStatus.FAILED)
        file_summary = file_service.list_files()
        cur_settings = db.get_settings()

        return {
            "stats": {
                "total_jobs": len(all_jobs),
                "total_downloads": total_downloads,
                "completed_jobs": completed_jobs,
                "active_jobs": active_jobs,
                "failed_jobs": failed_jobs,
                "storage_used_bytes": file_summary["library_used_bytes"],
                "total_files": file_summary["total_count"],
                "disk_usage": file_summary["disk_usage"],
            },
            "recent_jobs": all_jobs[:15],
            "diagnostics": get_environment_diagnostics(
                ffmpeg_custom=cur_settings.get("ffmpeg_path", ""),
                ffprobe_custom=cur_settings.get("ffprobe_path", ""),
            ),
        }

    return app_instance


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
