from __future__ import annotations

from dataclasses import dataclass

from app.models import SlideType


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    label: str
    slide_types: tuple[SlideType, ...]
    subject_families: tuple[str, ...]
    description: str


TEMPLATE_REGISTRY: dict[str, TemplateDefinition] = {
    "cover-hero": TemplateDefinition(
        template_id="cover-hero",
        label="Cover Hero",
        slide_types=(SlideType.COVER,),
        subject_families=("general", "stem", "humanities", "language"),
        description="封面主视觉布局，突出课题、目标和课堂入口。",
    ),
    "split-grid": TemplateDefinition(
        template_id="split-grid",
        label="Split Grid",
        slide_types=(SlideType.CONCEPT, SlideType.AGENDA),
        subject_families=("general", "stem", "humanities", "language"),
        description="双栏知识讲解布局，适合概念、线索和页级提示。",
    ),
    "comparison-columns": TemplateDefinition(
        template_id="comparison-columns",
        label="Comparison Columns",
        slide_types=(SlideType.COMPARISON,),
        subject_families=("general", "humanities", "language"),
        description="左右对比布局，适合材料对读、观点比较和错题分析。",
    ),
    "process-ladder": TemplateDefinition(
        template_id="process-ladder",
        label="Process Ladder",
        slide_types=(SlideType.PROCESS,),
        subject_families=("general", "stem", "language"),
        description="步骤梯级布局，适合方法、实验流程和操作步骤。",
    ),
    "media-gallery": TemplateDefinition(
        template_id="media-gallery",
        label="Media Gallery",
        slide_types=(SlideType.MEDIA,),
        subject_families=("general", "stem", "humanities"),
        description="图文混排布局，适合资料摘录、图像和案例展示。",
    ),
    "workshop-board": TemplateDefinition(
        template_id="workshop-board",
        label="Workshop Board",
        slide_types=(SlideType.ACTIVITY,),
        subject_families=("general", "stem", "humanities", "language"),
        description="课堂活动布局，突出任务、流程和输出要求。",
    ),
    "assignment-brief": TemplateDefinition(
        template_id="assignment-brief",
        label="Assignment Brief",
        slide_types=(SlideType.ASSIGNMENT,),
        subject_families=("general", "stem", "humanities", "language"),
        description="作业布置布局，突出提交物和评价标准。",
    ),
    "recap-strip": TemplateDefinition(
        template_id="recap-strip",
        label="Recap Strip",
        slide_types=(SlideType.SUMMARY,),
        subject_families=("general", "stem", "humanities", "language"),
        description="总结回收布局，突出重点、反思和迁移任务。",
    ),
    "timeline-ribbon": TemplateDefinition(
        template_id="timeline-ribbon",
        label="Timeline Ribbon",
        slide_types=(SlideType.TIMELINE,),
        subject_families=("general", "stem", "humanities"),
        description="时间线布局，适合事件、阶段或流程推进。",
    ),
}


DEFAULT_TEMPLATE_BY_TYPE: dict[SlideType, str] = {
    SlideType.COVER: "cover-hero",
    SlideType.AGENDA: "split-grid",
    SlideType.CONCEPT: "split-grid",
    SlideType.TIMELINE: "timeline-ribbon",
    SlideType.COMPARISON: "comparison-columns",
    SlideType.PROCESS: "process-ladder",
    SlideType.MEDIA: "media-gallery",
    SlideType.ACTIVITY: "workshop-board",
    SlideType.SUMMARY: "recap-strip",
    SlideType.ASSIGNMENT: "assignment-brief",
}


def available_templates() -> list[TemplateDefinition]:
    return list(TEMPLATE_REGISTRY.values())


def get_template_definition(template_id: str | None) -> TemplateDefinition | None:
    if not template_id:
        return None
    return TEMPLATE_REGISTRY.get(template_id)


def select_template_id(slide_type: SlideType, subject_family: str = "general") -> str:
    preferred = DEFAULT_TEMPLATE_BY_TYPE.get(slide_type, "split-grid")
    definition = TEMPLATE_REGISTRY.get(preferred)
    if definition and (subject_family in definition.subject_families or "general" in definition.subject_families):
        return definition.template_id

    for definition in TEMPLATE_REGISTRY.values():
        if slide_type in definition.slide_types and (
            subject_family in definition.subject_families or "general" in definition.subject_families
        ):
            return definition.template_id
    return preferred
