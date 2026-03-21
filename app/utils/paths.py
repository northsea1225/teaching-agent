from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.config import get_settings


def ensure_project_directories() -> None:
    settings = get_settings()
    for path in [
        settings.data_dir,
        settings.raw_data_dir,
        settings.parsed_data_dir,
        settings.knowledge_base_dir,
        settings.vector_store_dir,
        settings.exports_dir,
        settings.workspaces_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(filename: str) -> str:
    filename = filename.strip() or "upload"
    filename = re.sub(r"[^\w\-.]+", "_", filename, flags=re.UNICODE)
    return filename[:120]


def get_session_raw_dir(session_id: str) -> Path:
    settings = get_settings()
    path = settings.raw_data_dir / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_session_parsed_dir(session_id: str) -> Path:
    settings = get_settings()
    path = settings.parsed_data_dir / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_session_exports_dir(session_id: str) -> Path:
    settings = get_settings()
    path = settings.exports_dir / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_session_workspace_dir(session_id: str) -> Path:
    settings = get_settings()
    path = settings.workspaces_dir / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_upload_path(session_id: str, original_filename: str) -> Path:
    safe_name = _sanitize_filename(original_filename)
    return get_session_raw_dir(session_id) / f"{uuid4().hex}_{safe_name}"


def build_parsed_asset_path(session_id: str, file_id: str) -> Path:
    return get_session_parsed_dir(session_id) / f"{file_id}.json"


def build_export_path(session_id: str, filename_stem: str, extension: str) -> Path:
    safe_stem = _sanitize_filename(filename_stem) or "export"
    safe_extension = extension.lower().lstrip(".") or "bin"
    return get_session_exports_dir(session_id) / f"{uuid4().hex}_{safe_stem}.{safe_extension}"
