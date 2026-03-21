from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.models import SessionFile, SessionState
from app.services.parser import detect_resource_type, parse_file
from app.services.storage import attach_file_to_session, persist_parsed_asset, session_store
from app.utils.paths import build_upload_path, ensure_project_directories


router = APIRouter(prefix="/files", tags=["files"])


class FileUploadResponse(BaseModel):
    session_id: str
    file: SessionFile
    session: SessionState


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    title: str = Form(default="Untitled Session"),
) -> FileUploadResponse:
    ensure_project_directories()

    resource_type = detect_resource_type(
        file.filename or "upload",
        content_type=file.content_type,
    )
    if resource_type is None:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    session = session_store.get(session_id) if session_id else None
    if session is None:
        session = session_store.create_session(title=title)

    upload_path = build_upload_path(session.session_id, file.filename or "upload")
    file_bytes = await file.read()
    Path(upload_path).write_bytes(file_bytes)

    session_file = SessionFile(
        filename=file.filename or upload_path.name,
        resource_type=resource_type,
        path=str(upload_path),
    )

    try:
        parsed_asset = parse_file(upload_path, resource_type=resource_type)
        parsed_path = persist_parsed_asset(
            session_id=session.session_id,
            file_id=session_file.file_id,
            parsed_asset=parsed_asset,
        )
        session_file.parsed_path = parsed_path
        session_file.summary = parsed_asset.text_preview
        session_file.metadata = parsed_asset.metadata
        session_file.parse_status = "completed"
    except Exception as exc:
        session_file.parse_status = "failed"
        session_file.parse_error = str(exc)

    session = attach_file_to_session(session, session_file)
    session_store.save(session)

    return FileUploadResponse(
        session_id=session.session_id,
        file=session_file,
        session=session,
    )
