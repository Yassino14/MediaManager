from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import (
    AudioConvertRequest,
    AudioExtractRequest,
    MetadataCleanRequest,
    MetadataInspectRequest,
    VideoConvertRequest,
)
from app.utils.security import SecurityValidationError

router = APIRouter(prefix="/api/conversions", tags=["conversions"])


@router.post("/audio-extract")
def extract_audio_endpoint(payload: AudioExtractRequest, request: Request, sync: bool = False):
    try:
        if sync:
            res = request.app.state.conversion_service.run_audio_extraction(payload)
            return {"status": "completed", "result": res}
        job = request.app.state.job_manager.enqueue_audio_extraction(payload)
        return {"job": job}
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/video-convert")
def convert_video_endpoint(payload: VideoConvertRequest, request: Request, sync: bool = False):
    try:
        if sync:
            res = request.app.state.conversion_service.run_video_conversion(payload)
            return {"status": "completed", "result": res}
        job = request.app.state.job_manager.enqueue_video_conversion(payload)
        return {"job": job}
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/audio-convert")
def convert_audio_endpoint(payload: AudioConvertRequest, request: Request, sync: bool = False):
    try:
        if sync:
            res = request.app.state.conversion_service.run_audio_conversion(payload)
            return {"status": "completed", "result": res}
        job = request.app.state.job_manager.enqueue_audio_conversion(payload)
        return {"job": job}
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/estimate")
def estimate_conversion_size(
    source_path: str,
    request: Request,
    target_bitrate_kbps: Optional[int] = None,
    crf: Optional[int] = None,
):
    try:
        return request.app.state.conversion_service.estimate_output_size(
            source_path=source_path,
            target_bitrate_kbps=target_bitrate_kbps,
            crf=crf,
        )
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/metadata/inspect")
def inspect_metadata_endpoint(payload: MetadataInspectRequest, request: Request):
    try:
        return request.app.state.metadata_service.inspect_file(payload.source_path)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/metadata/clean")
def clean_metadata_endpoint(payload: MetadataCleanRequest, request: Request, sync: bool = True):
    try:
        if sync:
            res = request.app.state.metadata_service.clean_metadata(
                source_path=payload.source_path,
                output_filename=payload.output_filename,
                output_dir=payload.output_dir,
                duplicate_policy=payload.duplicate_policy,
            )
            return res
        job = request.app.state.job_manager.enqueue_metadata_clean(payload)
        return {"job": job}
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
