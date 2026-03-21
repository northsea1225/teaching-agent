from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_evidence_refresh_and_selection_api() -> None:
    chat_response = client.post(
        "/api/chat/messages",
        json={
            "title": "Evidence Demo",
            "content": "我想做一节初中历史《工业革命》课程，45分钟，教学目标：理解蒸汽机与工厂制度的关系。加入材料分析和讨论。",
        },
    )
    assert chat_response.status_code == 200
    session_id = chat_response.json()["session_id"]

    refresh_response = client.post(
        "/api/evidence/refresh",
        json={
            "session_id": session_id,
            "top_k": 5,
        },
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["session_id"] == session_id
    assert "selected_count" in refresh_payload
    assert "total_count" in refresh_payload

    hits = refresh_payload["retrieval_hits"]
    if hits:
        excluded_chunk_id = hits[0]["chunk_id"]
        selection_response = client.post(
            "/api/evidence/selection",
            json={
                "session_id": session_id,
                "excluded_chunk_ids": [excluded_chunk_id],
            },
        )
        assert selection_response.status_code == 200
        selection_payload = selection_response.json()
        assert selection_payload["selected_count"] == max(0, refresh_payload["selected_count"] - 1)
        assert excluded_chunk_id not in {
            hit["chunk_id"] for hit in selection_payload["selected_hits"]
        }
