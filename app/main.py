from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.config import get_settings
from app.utils.paths import ensure_project_directories


settings = get_settings()
ensure_project_directories()

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
PAGES_DIR = APP_DIR / "templates" / "pages"
INDEX_PAGE_PATH = PAGES_DIR / "index.html"
VIEWER_PAGE_PATH = PAGES_DIR / "viewer.html"


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    summary="Multimodal teaching assistant MVP",
)
app.include_router(api_router, prefix=settings.api_prefix)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", tags=["root"], response_class=HTMLResponse)
def read_root() -> FileResponse:
    response = FileResponse(INDEX_PAGE_PATH, media_type="text/html")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/viewer", tags=["root"], response_class=HTMLResponse)
def read_viewer() -> FileResponse:
    response = FileResponse(VIEWER_PAGE_PATH, media_type="text/html")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
