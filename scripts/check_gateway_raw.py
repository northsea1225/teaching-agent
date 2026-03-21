from __future__ import annotations

import json

import httpx

from app.config import get_settings
from app.services.openai_dialog import build_dialog_input
from app.utils.prompts import DIALOG_STRUCTURING_SYSTEM_PROMPT


def _post(client: httpx.Client, url: str, headers: dict[str, str], payload: dict[str, object]) -> None:
    response = client.post(url, headers=headers, json=payload)
    print(f"status={response.status_code}")
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(response.text)
    print("-" * 48)


def main() -> int:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{settings.openai_base_url.rstrip('/')}/chat/completions"

    minimal_payload = {
        "model": settings.openai_dialog_model,
        "messages": [
            {"role": "system", "content": "Reply with a JSON object only."},
            {"role": "user", "content": "Return {\"ok\": true, \"provider\": \"reachable\"}"},
        ],
        "temperature": 0,
    }
    dialog_payload = {
        "model": settings.openai_dialog_model,
        "messages": [
            {"role": "system", "content": DIALOG_STRUCTURING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_dialog_input(
                    None,
                    "我想做一节初中历史《工业革命》课程，45分钟，教学目标：理解蒸汽机与工厂制度的关系。加入材料分析和课堂讨论，只使用上传资料和检索命中。",
                ),
            },
        ],
        "temperature": 0,
    }

    with httpx.Client(timeout=settings.openai_dialog_timeout_seconds) as client:
        print("=== minimal ===")
        _post(client, endpoint, headers, minimal_payload)
        print("=== dialog ===")
        _post(client, endpoint, headers, dialog_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
