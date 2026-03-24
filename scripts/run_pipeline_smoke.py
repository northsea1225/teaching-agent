from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.main import app


DEFAULT_CONTENT = (
    "我想做一节初中历史《工业革命》课程，45分钟。"
    "教学目标：理解蒸汽机与工厂制度的关系，并能说明工业革命对城市化的影响。"
    "重点难点：区分技术进步与社会结构变化之间的关系。"
    "加入材料分析和课堂讨论。"
    "资料边界：默认使用本地知识库，可结合当前命中证据，不扩展未提供的课外史实。"
)


def summarize_hit(hit: dict[str, object]) -> dict[str, object]:
    content = str(hit.get("content") or "")
    return {
        "score": round(float(hit.get("score") or 0.0), 3),
        "source_title": hit.get("source_title"),
        "source_filename": hit.get("source_filename"),
        "subject_tag": hit.get("subject_tag"),
        "topic_hint": hit.get("topic_hint"),
        "content_preview": content[:120],
    }


def main() -> None:
    client = TestClient(app)

    chat_response = client.post(
        "/api/chat/messages",
        json={
            "title": "Industrial Revolution Smoke",
            "content": DEFAULT_CONTENT,
            "use_web_search": False,
        },
    )
    chat_response.raise_for_status()
    chat_payload = chat_response.json()
    session_id = chat_payload["session_id"]

    evidence_response = client.post(
        "/api/evidence/refresh",
        json={
            "session_id": session_id,
            "top_k": 8,
            "use_web_search": False,
        },
    )
    evidence_response.raise_for_status()
    evidence_payload = evidence_response.json()

    refresh_response = client.post(
        "/api/planner/confirmation/refresh",
        json={"session_id": session_id},
    )
    refresh_response.raise_for_status()

    confirm_response = client.post(
        "/api/planner/confirmation/confirm",
        json={
            "session_id": session_id,
            "note": "按当前需求、命中证据与默认本地知识库来源继续生成。",
        },
    )
    confirm_response.raise_for_status()

    outline_response = client.post(
        "/api/planner/outline",
        json={
            "session_id": session_id,
            "top_k": 8,
            "use_web_search": False,
        },
    )
    outline_response.raise_for_status()
    outline_payload = outline_response.json()

    slide_response = client.post(
        "/api/planner/slide-plan",
        json={
            "session_id": session_id,
            "top_k": 8,
            "use_web_search": False,
        },
    )
    slide_response.raise_for_status()
    slide_payload = slide_response.json()

    quality_response = client.post(
        "/api/quality/report",
        json={"session_id": session_id},
    )
    quality_response.raise_for_status()
    quality_payload = quality_response.json()

    summary = {
        "session_id": session_id,
        "teaching_spec": {
            "stage": chat_payload.get("teaching_spec", {}).get("education_stage"),
            "subject": chat_payload.get("teaching_spec", {}).get("subject"),
            "lesson_title": chat_payload.get("teaching_spec", {}).get("lesson_title"),
            "duration_minutes": chat_payload.get("teaching_spec", {}).get("duration_minutes"),
            "learning_objectives": chat_payload.get("teaching_spec", {}).get("learning_objectives"),
            "constraints": chat_payload.get("teaching_spec", {}).get("additional_requirements"),
        },
        "evidence": {
            "selected_count": evidence_payload.get("selected_count"),
            "total_count": evidence_payload.get("total_count"),
            "top_hits": [summarize_hit(hit) for hit in evidence_payload.get("selected_hits", [])[:5]],
        },
        "outline": {
            "title": outline_payload.get("outline", {}).get("title"),
            "sections": [
                {
                    "title": item.get("title"),
                    "goal": item.get("goal"),
                    "estimated_slides": item.get("estimated_slides"),
                    "recommended_slide_type": item.get("recommended_slide_type"),
                }
                for item in outline_payload.get("outline", {}).get("sections", [])
            ],
        },
        "slide_plan": {
            "total_slides": slide_payload.get("slide_plan", {}).get("total_slides"),
            "slides": [
                {
                    "slide_number": item.get("slide_number"),
                    "title": item.get("title"),
                    "slide_type": item.get("slide_type"),
                    "citations": item.get("citations"),
                    "speaker_notes": item.get("speaker_notes"),
                }
                for item in slide_payload.get("slide_plan", {}).get("slides", [])[:5]
            ],
        },
        "quality": {
            "status": quality_payload.get("quality_report", {}).get("status"),
            "score": quality_payload.get("quality_report", {}).get("score"),
            "issues": quality_payload.get("quality_report", {}).get("issues"),
        },
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
