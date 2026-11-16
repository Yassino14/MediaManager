from __future__ import annotations
import shutil
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.models.schemas import FileOpenRequest, FileRenameRequest
from app.utils.security import SecurityValidationError, sanitize_filename, validate_path_in_allowed_dirs

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("")
def list_media_files(
    request: Request,
    search: str = Query(default=""),
    media_type: str = Query(default="all"),
    sort_by: str = Query(default="date"),
    sort_desc: bool = Query(default=True),
):
    return request.app.state.file_service.list_files(
        search=search,
        media_type=media_type,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


@router.post("/upload")
async def upload_local_media(request: Request, file: UploadFile = File(...)):
    settings = request.app.state.db.get_settings()
    dl_dir = Path(settings["download_dir"]).resolve()
    dl_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(file.filename or "uploaded_media")
    dest_path = dl_dir / safe_name
    counter = 1
    stem, ext = dest_path.stem, dest_path.suffix
    while dest_path.exists():
        dest_path = dl_dir / f"{stem} ({counter}){ext}"
        counter += 1

    with dest_path.open("wb") as out_f:
        shutil.copyfileobj(file.file, out_f)

    return {
        "filename": dest_path.name,
        "path": str(dest_path),
        "size_bytes": dest_path.stat().st_size,
    }


@router.get("/stream")
def stream_media_file(path: str, request: Request):
    roots = request.app.state.file_service.get_allowed_roots()
    try:
        target = validate_path_in_allowed_dirs(path, roots, must_exist=True)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return FileResponse(str(target), filename=target.name)


@router.post("/rename")
def rename_media_file(payload: FileRenameRequest, request: Request):
    try:
        return request.app.state.file_service.rename_file(payload.path, payload.new_name)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("")
def delete_media_file(path: str, request: Request):
    try:
        return request.app.state.file_service.delete_file(path)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/open")
def open_media_in_os(payload: FileOpenRequest, request: Request):
    try:
        return request.app.state.file_service.open_in_os(payload.path, payload.reveal_in_folder)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
