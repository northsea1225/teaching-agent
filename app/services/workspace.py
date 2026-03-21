from __future__ import annotations

import json
from pathlib import Path

from app.models import SessionState
from app.utils.paths import get_session_workspace_dir


def ensure_session_workspace(session: SessionState) -> Path:
    workspace_dir = get_session_workspace_dir(session.session_id)
    for name in ("snapshots", "reports", "exports", "manifests"):
        (workspace_dir / name).mkdir(parents=True, exist_ok=True)
    session.workspace_path = str(workspace_dir)
    return workspace_dir


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def persist_workspace_snapshot(session: SessionState) -> SessionState:
    workspace_dir = ensure_session_workspace(session)

    session_payload = session.model_dump(mode="json")
    _write_json(workspace_dir / "session.json", session_payload)

    manifests_dir = workspace_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        manifests_dir / "project_manifest.json",
        {
            "session_id": session.session_id,
            "title": session.title,
            "stage": session.stage.value,
            "workspace_path": session.workspace_path,
            "uploaded_files": [
                {
                    "file_id": session_file.file_id,
                    "filename": session_file.filename,
                    "resource_type": session_file.resource_type.value,
                    "path": session_file.path,
                    "parsed_path": session_file.parsed_path,
                    "parse_status": session_file.parse_status,
                }
                for session_file in session.uploaded_files
            ],
            "export_artifacts": [
                artifact.model_dump(mode="json")
                for artifact in session.export_artifacts
            ],
        },
    )

    snapshots_dir = workspace_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    if session.teaching_spec is not None:
        _write_json(snapshots_dir / "teaching_spec.json", session.teaching_spec.model_dump(mode="json"))
    if session.outline is not None:
        _write_json(snapshots_dir / "lesson_outline.json", session.outline.model_dump(mode="json"))
    if session.slide_plan is not None:
        _write_json(snapshots_dir / "slide_plan.json", session.slide_plan.model_dump(mode="json"))
    if session.svg_deck is not None:
        _write_json(snapshots_dir / "svg_deck.json", session.svg_deck.model_dump(mode="json"))
    if session.preview_deck is not None:
        _write_json(snapshots_dir / "preview_deck.json", session.preview_deck.model_dump(mode="json"))

    reports_dir = workspace_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_json(reports_dir / "planning_confirmation.json", session.planning_confirmation.model_dump(mode="json"))
    if session.quality_report is not None:
        _write_json(reports_dir / "quality_report.json", session.quality_report.model_dump(mode="json"))

    return session
