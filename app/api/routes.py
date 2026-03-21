from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.evidence import router as evidence_router
from app.api.export import router as export_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.kb import router as kb_router
from app.api.planner import router as planner_router
from app.api.preview import router as preview_router
from app.api.quality import router as quality_router
from app.api.svg import router as svg_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(evidence_router)
api_router.include_router(export_router)
api_router.include_router(files_router)
api_router.include_router(kb_router)
api_router.include_router(planner_router)
api_router.include_router(preview_router)
api_router.include_router(quality_router)
api_router.include_router(svg_router)
