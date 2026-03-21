from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import QualityReport, SessionState
from app.services.quality import refresh_quality_report
from app.services.storage import session_store


router = APIRouter(prefix="/quality", tags=["quality"])


class QualityReportRequest(BaseModel):
    session_id: str


class QualityReportResponse(BaseModel):
    session_id: str
    quality_report: QualityReport
    session: SessionState


@router.post("/report", response_model=QualityReportResponse)
def create_quality_report(payload: QualityReportRequest) -> QualityReportResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session = refresh_quality_report(session)
    session_store.save(session)
    assert session.quality_report is not None
    return QualityReportResponse(
        session_id=session.session_id,
        quality_report=session.quality_report,
        session=session,
    )
