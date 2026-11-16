from __future__ import annotations
import asyncio
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.database.db import DatabaseManager, utc_now_iso
from app.models.schemas import (
    AudioConvertRequest,
    AudioExtractRequest,
    DownloadCreateRequest,
    JobRecord,
    JobStatus,
    JobType,
    MetadataCleanRequest,
    VideoConvertRequest,
)
from app.services.conversion_service import ConversionCancelledError, ConversionService
from app.services.download_service import DownloadCancelledError, DownloadService
from app.services.metadata_service import MetadataService


class JobManager:
    """
    Bounded background job queue with real-time pub/sub event broadcasting,
    cancellation tokens, duplicate prevention, and SQLite persistence.
    """

    def __init__(
        self,
        db: DatabaseManager,
        download_service: DownloadService,
        conversion_service: ConversionService,
        metadata_service: MetadataService,
    ) -> None:
        self.db = db
        self.download_service = download_service
        self.conversion_service = conversion_service
        self.metadata_service = metadata_service

        max_workers = int(self.db.get_settings().get("max_concurrent_downloads") or 3)
        self._max_workers = max(1, min(10, max_workers))
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="umt_worker")
        self._lock = threading.RLock()
        self._cancel_events: Dict[str, threading.Event] = {}
        self._futures: Dict[str, Future[Any]] = {}
        self._subscribers: Set[asyncio.Queue[Dict[str, Any]]] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Dict[str, Any]]:
        q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=250)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def _broadcast(self, event_type: str, job: JobRecord) -> None:
        payload = {
            "event": event_type,
            "job": job.model_dump(),
            "timestamp": utc_now_iso(),
        }
        with self._lock:
            subscribers = list(self._subscribers)
        if not subscribers:
            return

        for q in subscribers:
            try:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._safe_put, q, payload)
                else:
                    self._safe_put(q, payload)
            except Exception:
                pass

    @staticmethod
    def _safe_put(q: asyncio.Queue[Dict[str, Any]], item: Dict[str, Any]) -> None:
        if q.full():
            try:
                q.get_nowait()
            except Exception:
                pass
        try:
            q.put_nowait(item)
        except Exception:
            pass

    def _enqueue_job(
        self,
        job_type: JobType,
        title: str,
        source: str,
        options: Dict[str, Any],
        runner_fn: Callable[[str, threading.Event], None],
    ) -> JobRecord:
        existing = self.db.find_active_duplicate(source, job_type)
        if existing:
            raise ValueError(f"An active {job_type.value} job for '{source}' is already in the queue.")

        now = utc_now_iso()
        job = JobRecord(
            id=f"job_{uuid.uuid4().hex[:12]}",
            job_type=job_type,
            title=title,
            source=source,
            status=JobStatus.WAITING,
            progress=0.0,
            options=options,
            is_historical=False,
            created_at=now,
            updated_at=now,
        )
        self.db.create_job(job)
        cancel_ev = threading.Event()
        with self._lock:
            self._cancel_events[job.id] = cancel_ev
            fut = self._executor.submit(self._execute_wrapper, job.id, cancel_ev, runner_fn)
            self._futures[job.id] = fut

        self._broadcast("job_created", job)
        return job

    def _execute_wrapper(
        self,
        job_id: str,
        cancel_ev: threading.Event,
        runner_fn: Callable[[str, threading.Event], None],
    ) -> None:
        try:
            if cancel_ev.is_set():
                updated = self.db.update_job(job_id, status=JobStatus.CANCELLED, speed_bps=None, eta_seconds=None)
                if updated:
                    self._broadcast("job_cancelled", updated)
                return
            runner_fn(job_id, cancel_ev)
        except (DownloadCancelledError, ConversionCancelledError):
            updated = self.db.update_job(
                job_id,
                status=JobStatus.CANCELLED,
                speed_bps=None,
                eta_seconds=None,
                error_message="Cancelled by user.",
            )
            if updated:
                self._broadcast("job_cancelled", updated)
        except Exception as exc:
            updated = self.db.update_job(
                job_id,
                status=JobStatus.FAILED,
                speed_bps=None,
                eta_seconds=None,
                error_message=str(exc),
            )
            if updated:
                self._broadcast("job_failed", updated)
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)
                self._futures.pop(job_id, None)

    # ---------------- Enqueue Helpers ----------------

    def enqueue_downloads(self, req: DownloadCreateRequest) -> List[JobRecord]:
        created: List[JobRecord] = []
        for raw_url in req.urls:
            url = raw_url.strip()
            if not url:
                continue

            def _run_dl(job_id: str, cancel_ev: threading.Event, target_url: str = url) -> None:
                def _progress(update: Dict[str, Any]) -> None:
                    fields: Dict[str, Any] = {}
                    for k in (
                        "status", "title", "thumbnail", "progress",
                        "downloaded_bytes", "total_bytes", "speed_bps",
                        "eta_seconds", "destination_path", "destination_filename",
                    ):
                        if k in update and update[k] is not None:
                            fields[k] = update[k]
                    job_now = self.db.update_job(job_id, **fields)
                    if job_now:
                        self._broadcast("job_progress", job_now)

                res = self.download_service.execute_download(target_url, req, _progress, cancel_ev)
                done = self.db.update_job(
                    job_id,
                    title=res.get("title") or target_url,
                    thumbnail=res.get("thumbnail"),
                    status=JobStatus.COMPLETED,
                    progress=100.0,
                    speed_bps=None,
                    eta_seconds=0,
                    destination_path=res.get("destination_path"),
                    destination_filename=res.get("destination_filename"),
                )
                if done:
                    self._broadcast("job_completed", done)

            job = self._enqueue_job(
                job_type=JobType.DOWNLOAD,
                title=req.custom_filename or url,
                source=url,
                options=req.model_dump(),
                runner_fn=_run_dl,
            )
            created.append(job)
        return created

    def enqueue_audio_extraction(self, req: AudioExtractRequest) -> JobRecord:
        src_name = os.path.basename(req.source_path)

        def _run_extract(job_id: str, cancel_ev: threading.Event) -> None:
            started = self.db.update_job(job_id, status=JobStatus.PROCESSING, progress=5.0)
            if started:
                self._broadcast("job_started", started)

            def _progress(upd: Dict[str, Any]) -> None:
                j = self.db.update_job(job_id, status=JobStatus.PROCESSING, **upd)
                if j:
                    self._broadcast("job_progress", j)

            res = self.conversion_service.run_audio_extraction(req, _progress, cancel_ev)
            done = self.db.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100.0,
                downloaded_bytes=res["size_bytes"],
                total_bytes=res["size_bytes"],
                destination_path=res["output_path"],
                destination_filename=res["output_filename"],
                result_meta=res,
            )
            if done:
                self._broadcast("job_completed", done)

        return self._enqueue_job(
            job_type=JobType.AUDIO_EXTRACT,
            title=f"Extract {req.output_format.upper()}: {src_name}",
            source=req.source_path,
            options=req.model_dump(),
            runner_fn=_run_extract,
        )

    def enqueue_video_conversion(self, req: VideoConvertRequest) -> JobRecord:
        src_name = os.path.basename(req.source_path)

        def _run_vconv(job_id: str, cancel_ev: threading.Event) -> None:
            started = self.db.update_job(job_id, status=JobStatus.PROCESSING, progress=5.0)
            if started:
                self._broadcast("job_started", started)

            def _progress(upd: Dict[str, Any]) -> None:
                j = self.db.update_job(job_id, status=JobStatus.PROCESSING, **upd)
                if j:
                    self._broadcast("job_progress", j)

            res = self.conversion_service.run_video_conversion(req, _progress, cancel_ev)
            done = self.db.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100.0,
                downloaded_bytes=res["size_bytes"],
                total_bytes=res["size_bytes"],
                destination_path=res["output_path"],
                destination_filename=res["output_filename"],
                result_meta=res,
            )
            if done:
                self._broadcast("job_completed", done)

        return self._enqueue_job(
            job_type=JobType.VIDEO_CONVERT,
            title=f"Convert Video ({req.output_format.upper()}): {src_name}",
            source=req.source_path,
            options=req.model_dump(),
            runner_fn=_run_vconv,
        )

    def enqueue_audio_conversion(self, req: AudioConvertRequest) -> JobRecord:
        src_name = os.path.basename(req.source_path)

        def _run_aconv(job_id: str, cancel_ev: threading.Event) -> None:
            started = self.db.update_job(job_id, status=JobStatus.PROCESSING, progress=5.0)
            if started:
                self._broadcast("job_started", started)

            def _progress(upd: Dict[str, Any]) -> None:
                j = self.db.update_job(job_id, status=JobStatus.PROCESSING, **upd)
                if j:
                    self._broadcast("job_progress", j)

            res = self.conversion_service.run_audio_conversion(req, _progress, cancel_ev)
            done = self.db.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100.0,
                downloaded_bytes=res["size_bytes"],
                total_bytes=res["size_bytes"],
                destination_path=res["output_path"],
                destination_filename=res["output_filename"],
                result_meta=res,
            )
            if done:
                self._broadcast("job_completed", done)

        return self._enqueue_job(
            job_type=JobType.AUDIO_CONVERT,
            title=f"Convert Audio ({req.output_format.upper()}): {src_name}",
            source=req.source_path,
            options=req.model_dump(),
            runner_fn=_run_aconv,
        )

    def enqueue_metadata_clean(self, req: MetadataCleanRequest) -> JobRecord:
        src_name = os.path.basename(req.source_path)

        def _run_meta(job_id: str, cancel_ev: threading.Event) -> None:
            started = self.db.update_job(job_id, status=JobStatus.PROCESSING, progress=10.0)
            if started:
                self._broadcast("job_started", started)

            def _progress(pct: float, _msg: str) -> None:
                j = self.db.update_job(job_id, status=JobStatus.PROCESSING, progress=pct)
                if j:
                    self._broadcast("job_progress", j)

            res = self.metadata_service.clean_metadata(
                source_path=req.source_path,
                output_filename=req.output_filename,
                output_dir=req.output_dir,
                duplicate_policy=req.duplicate_policy,
                progress_cb=_progress,
            )
            done = self.db.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100.0,
                destination_path=res["output_path"],
                destination_filename=res["output_filename"],
                result_meta=res,
            )
            if done:
                self._broadcast("job_completed", done)

        return self._enqueue_job(
            job_type=JobType.METADATA_CLEAN,
            title=f"Clean Metadata: {src_name}",
            source=req.source_path,
            options=req.model_dump(),
            runner_fn=_run_meta,
        )

    # ---------------- Queue Actions ----------------

    def cancel_job(self, job_id: str) -> Optional[JobRecord]:
        job = self.db.get_job(job_id)
        if not job:
            return None

        with self._lock:
            ev = self._cancel_events.get(job_id)
            if ev:
                ev.set()
            fut = self._futures.get(job_id)
            if fut and fut.cancel():
                pass

        if job.status in (JobStatus.WAITING, JobStatus.PAUSED, JobStatus.FETCHING_INFO, JobStatus.DOWNLOADING, JobStatus.PROCESSING):
            updated = self.db.update_job(
                job_id,
                status=JobStatus.CANCELLED,
                speed_bps=None,
                eta_seconds=None,
                error_message="Cancelled by user.",
            )
            if updated:
                self._broadcast("job_cancelled", updated)
            return updated
        return job

    def retry_job(self, job_id: str) -> JobRecord:
        job = self.db.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        opts = job.options or {}
        if job.job_type == JobType.DOWNLOAD:
            req = DownloadCreateRequest(**{**opts, "urls": [job.source]})
            return self.enqueue_downloads(req)[0]
        if job.job_type == JobType.AUDIO_EXTRACT:
            return self.enqueue_audio_extraction(AudioExtractRequest(**opts))
        if job.job_type == JobType.VIDEO_CONVERT:
            return self.enqueue_video_conversion(VideoConvertRequest(**opts))
        if job.job_type == JobType.AUDIO_CONVERT:
            return self.enqueue_audio_conversion(AudioConvertRequest(**opts))
        if job.job_type == JobType.METADATA_CLEAN:
            return self.enqueue_metadata_clean(MetadataCleanRequest(**opts))
        raise ValueError(f"Unsupported retry for job type {job.job_type}")

    def shutdown(self) -> None:
        with self._lock:
            for ev in self._cancel_events.values():
                ev.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
