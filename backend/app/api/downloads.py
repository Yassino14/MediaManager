from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import BatchProbeRequest, DownloadCreateRequest, UrlProbeRequest
from app.utils.security import SecurityValidationError

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.post("/probe")
def probe_media_url(payload: UrlProbeRequest, request: Request):
    dl_service = request.app.state.download_service
    try:
        return dl_service.probe_url(payload.url)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/validate-batch")
def validate_batch_urls(payload: BatchProbeRequest):
    results = []
    for raw in payload.urls:
        u = raw.strip()
        if not u:
            continue
        try:
            clean = validate_url_only(u)
            results.append({"url": clean, "valid": True, "error": None})
        except SecurityValidationError as exc:
            results.append({"url": u, "valid": False, "error": str(exc)})
    return {"results": results}


def validate_url_only(url: str) -> str:
    from app.utils.security import validate_download_url
    return validate_download_url(url)


@router.post("/enqueue")
def enqueue_download_jobs(payload: DownloadCreateRequest, request: Request):
    try:
        for u in payload.urls:
            validate_url_only(u)
        jobs = request.app.state.job_manager.enqueue_downloads(payload)
        return {"jobs": jobs, "count": len(jobs)}
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs")
def list_all_jobs(request: Request, job_type: Optional[str] = None, limit: int = 200):
    jobs = request.app.state.db.list_jobs(job_type=job_type, limit=limit)
    return {"jobs": jobs}


@router.post("/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str, request: Request):
    updated = request.app.state.job_manager.cancel_job(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job": updated}


@router.post("/jobs/{job_id}/retry")
def retry_job_endpoint(job_id: str, request: Request):
    try:
        new_job = request.app.state.job_manager.retry_job(job_id)
        return {"job": new_job}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}")
def delete_job_endpoint(job_id: str, request: Request):
    request.app.state.job_manager.cancel_job(job_id)
    deleted = request.app.state.db.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": True, "id": job_id}


@router.post("/jobs/clear-completed")
def clear_completed_endpoint(request: Request):
    removed = request.app.state.db.clear_completed_jobs()
    return {"cleared_count": removed}
