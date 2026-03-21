from __future__ import annotations

import json

from app.config import get_settings
from app.services.openai_dialog import extract_teaching_spec_with_openai, openai_dialog_ready


def main() -> int:
    settings = get_settings()
    if not openai_dialog_ready(settings):
        print("dialog provider is not enabled")
        return 1

    spec = extract_teaching_spec_with_openai(
        None,
        "我想做一节初中历史《工业革命》课程，45分钟，教学目标：理解蒸汽机与工厂制度的关系。加入材料分析和课堂讨论，只使用上传资料和检索命中。",
        settings=settings,
    )
    print(
        json.dumps(
            {
                "education_stage": spec.education_stage,
                "subject": spec.subject,
                "lesson_title": spec.lesson_title,
                "class_duration_minutes": spec.class_duration_minutes,
                "learning_objectives": [item.description for item in spec.learning_objectives],
                "interaction_preferences": [item.value for item in spec.interaction_preferences],
                "additional_requirements": spec.additional_requirements,
                "confirmed": spec.confirmed,
                "unresolved_questions": [item.prompt for item in spec.unresolved_questions],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
