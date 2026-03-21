from __future__ import annotations

from app.models import RetrievalHit, SessionState
from app.models.session import utc_now


def get_selected_retrieval_hits(
    session: SessionState,
    hits: list[RetrievalHit] | None = None,
) -> list[RetrievalHit]:
    source_hits = hits if hits is not None else session.retrieval_hits
    excluded_ids = {chunk_id for chunk_id in session.excluded_retrieval_chunk_ids if chunk_id}
    if not excluded_ids:
        return list(source_hits)
    return [hit for hit in source_hits if hit.chunk_id not in excluded_ids]


def set_excluded_retrieval_hits(
    session: SessionState,
    excluded_chunk_ids: list[str],
) -> SessionState:
    current_ids = {hit.chunk_id for hit in session.retrieval_hits}
    normalized: list[str] = []
    for chunk_id in excluded_chunk_ids:
        if chunk_id and chunk_id in current_ids and chunk_id not in normalized:
            normalized.append(chunk_id)
    session.excluded_retrieval_chunk_ids = normalized
    session.updated_at = utc_now()
    return session


def refresh_session_retrieval_hits(
    session: SessionState,
    *,
    store_namespace: str | None = None,
    top_k: int = 8,
    use_web_search: bool | None = None,
) -> SessionState:
    if session.teaching_spec is None:
        raise ValueError("Session has no teaching spec")

    from app.services.planner import fetch_retrieval_hits

    session.retrieval_hits = fetch_retrieval_hits(
        session.teaching_spec,
        session=session,
        store_namespace=store_namespace,
        top_k=top_k,
        use_web_search=use_web_search,
    )
    current_ids = {hit.chunk_id for hit in session.retrieval_hits}
    session.excluded_retrieval_chunk_ids = [
        chunk_id
        for chunk_id in session.excluded_retrieval_chunk_ids
        if chunk_id in current_ids
    ]
    session.updated_at = utc_now()
    return session
