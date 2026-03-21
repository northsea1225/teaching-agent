from __future__ import annotations

import json
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path

from app.models import ExportArtifact, ParsedAsset, SessionFile, SessionState, build_empty_session
from app.utils.paths import build_parsed_asset_path, ensure_project_directories


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def create_session(self, title: str = "Untitled Session") -> SessionState:
        session = build_empty_session(title=title)
        self.save(session)
        return session

    def save(self, session: SessionState) -> SessionState:
        from app.services.confirmation import refresh_planning_confirmation
        from app.services.quality import refresh_quality_report
        from app.services.workspace import persist_workspace_snapshot

        if session.teaching_spec is not None:
            session = refresh_planning_confirmation(session)
            session = refresh_quality_report(session)
        with self._lock:
            self._sessions[session.session_id] = session
        persist_workspace_snapshot(session)
        return session

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()


def attach_file_to_session(session: SessionState, session_file: SessionFile) -> SessionState:
    session.uploaded_files.append(session_file)
    session.updated_at = utc_now()
    return session


def attach_export_to_session(session: SessionState, artifact: ExportArtifact) -> SessionState:
    session.export_artifacts.append(artifact)
    session.updated_at = utc_now()
    return session


def persist_parsed_asset(
    session_id: str,
    file_id: str,
    parsed_asset: ParsedAsset,
) -> str:
    ensure_project_directories()
    parsed_path = build_parsed_asset_path(session_id, file_id)
    parsed_path.write_text(
        json.dumps(parsed_asset.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(parsed_path)


def load_parsed_asset(parsed_path: str | None) -> ParsedAsset | None:
    if not parsed_path:
        return None
    path = Path(parsed_path)
    if not path.exists() or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ParsedAsset.model_validate(payload)


session_store = SessionStore()
