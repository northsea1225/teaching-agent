from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.models import ExportArtifact, SessionState
from app.services.confirmation import refresh_planning_confirmation
from app.services.exporter import export_docx_for_session, export_pptx_for_session
from app.services.planner import generate_slide_plan_for_session
from app.services.quality import refresh_quality_report
from app.services.svg import generate_svg_deck_for_session
from app.services.storage import session_store
from app.utils.paths import get_session_exports_dir


router = APIRouter(prefix="/export", tags=["export"])


EXPORT_BLOCKING_STATUSES = {"blocked", "review"}


class ExportDocxRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ExportDocxResponse(BaseModel):
    session_id: str
    artifact: ExportArtifact
    session: SessionState
    download_url: str


class ExportPptxRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    theme_id: str | None = None
    font_preset: str | None = None


class ExportPptxResponse(BaseModel):
    session_id: str
    artifact: ExportArtifact
    session: SessionState
    download_url: str


def _prepare_docx_export_session(
    session: SessionState,
    *,
    store_namespace: str | None,
    top_k: int,
) -> SessionState:
    session = generate_slide_plan_for_session(
        session,
        store_namespace=store_namespace,
        top_k=top_k,
    )
    session = refresh_planning_confirmation(session)
    session = refresh_quality_report(session)
    session_store.save(session)
    return session


def _prepare_pptx_export_session(
    session: SessionState,
    *,
    store_namespace: str | None,
    top_k: int,
    theme_id: str | None,
    font_preset: str | None,
) -> SessionState:
    session = generate_svg_deck_for_session(
        session,
        store_namespace=store_namespace,
        top_k=top_k,
        theme_id=theme_id,
        font_preset=font_preset,
    )
    session = refresh_planning_confirmation(session)
    session = refresh_quality_report(session)
    session_store.save(session)
    return session


def _assert_export_ready(session: SessionState) -> None:
    if not session.planning_confirmation.confirmed:
        raise HTTPException(
            status_code=409,
            detail="关键约束尚未确认，请先完成约束确认后再导出正式稿。",
        )

    report = session.quality_report
    if report is None:
        raise HTTPException(status_code=409, detail="当前还没有质量报告，请先重新生成后再导出。")

    if report.status in EXPORT_BLOCKING_STATUSES:
        top_issues = "；".join(issue.message for issue in report.issues[:3])
        detail = f"当前质量状态为 {report.status}，已拦截正式导出。"
        if top_issues:
            detail = f"{detail} 主要问题：{top_issues}"
        raise HTTPException(status_code=409, detail=detail)


@router.post("/docx", response_model=ExportDocxResponse)
def create_docx_export(payload: ExportDocxRequest) -> ExportDocxResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")
    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")
    session = _prepare_docx_export_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
    )
    _assert_export_ready(session)

    updated_session, artifact = export_docx_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
    )
    session_store.save(updated_session)
    download_url = f"/api/export/files/{updated_session.session_id}/{artifact.filename}"
    return ExportDocxResponse(
        session_id=updated_session.session_id,
        artifact=artifact,
        session=updated_session,
        download_url=download_url,
    )


@router.post("/pptx", response_model=ExportPptxResponse)
def create_pptx_export(payload: ExportPptxRequest) -> ExportPptxResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")
    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")
    session = _prepare_pptx_export_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
        theme_id=payload.theme_id,
        font_preset=payload.font_preset,
    )
    _assert_export_ready(session)

    updated_session, artifact = export_pptx_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
        theme_id=payload.theme_id,
        font_preset=payload.font_preset,
    )
    session_store.save(updated_session)
    download_url = f"/api/export/files/{updated_session.session_id}/{artifact.filename}"
    return ExportPptxResponse(
        session_id=updated_session.session_id,
        artifact=artifact,
        session=updated_session,
        download_url=download_url,
    )


@router.get("/files/{session_id}/{filename}")
def download_export_file(session_id: str, filename: str) -> FileResponse:
    exports_dir = get_session_exports_dir(session_id)
    file_path = (exports_dir / filename).resolve()
    try:
        file_path.relative_to(exports_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid export path") from exc

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")

    media_type_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    media_type = media_type_map.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=Path(file_path), media_type=media_type, filename=filename)
