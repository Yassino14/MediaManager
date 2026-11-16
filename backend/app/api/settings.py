from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import SettingsUpdateModel
from app.utils.binaries import get_environment_diagnostics

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_endpoint(request: Request):
    settings = request.app.state.db.get_settings()
    diagnostics = get_environment_diagnostics(
        ffmpeg_custom=settings.get("ffmpeg_path", ""),
        ffprobe_custom=settings.get("ffprobe_path", ""),
    )
    return {"settings": settings, "diagnostics": diagnostics}


@router.put("")
def update_settings_endpoint(payload: SettingsUpdateModel, request: Request):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "duplicate_handling" in updates and hasattr(updates["duplicate_handling"], "value"):
        updates["duplicate_handling"] = updates["duplicate_handling"].value

    for dir_key in ("download_dir", "conversion_dir"):
        if dir_key in updates:
            raw_dir = str(updates[dir_key]).strip()
            if not raw_dir or "\x00" in raw_dir:
                raise HTTPException(status_code=400, detail=f"Invalid directory path for {dir_key}.")
            resolved = Path(raw_dir).expanduser().resolve()
            try:
                resolved.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Cannot create directory '{raw_dir}': {exc}") from exc
            updates[dir_key] = str(resolved)

    settings = request.app.state.db.update_settings(updates)
    diagnostics = get_environment_diagnostics(
        ffmpeg_custom=settings.get("ffmpeg_path", ""),
        ffprobe_custom=settings.get("ffprobe_path", ""),
    )
    return {"settings": settings, "diagnostics": diagnostics}
