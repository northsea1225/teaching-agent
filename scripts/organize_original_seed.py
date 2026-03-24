from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(r"E:\teaching-agent_resources")
ORIGINAL_ROOT = ROOT / "original_seed"
STAGE1_ROOT = ROOT / "public_seed" / "curated_from_original"
STAGE2_ROOT = ROOT / "subject_seed"

STAGE1_KEYWORDS = (
    "课程标准",
    "课程方案",
    "教学标准",
    "专业目录",
    "专业简介",
    "指南",
    "质量国家标准",
    "平台",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify(path: Path) -> tuple[str, str]:
    name = path.stem

    if _contains_any(name, STAGE1_KEYWORDS):
        return "stage1", "general"

    history_keywords = (
        "专题",
        "民族解放战争",
        "新民主主义革命",
        "社会主义革命",
        "现代化强国",
        "历史主动",
        "当代中国命运",
    )
    chemistry_keywords = (
        "氯",
        "卤族",
        "硫",
        "氮及其化合物",
        "硝酸",
        "氨",
        "铵盐",
        "气体",
        "过渡金属",
        "碳酸钠",
        "碳酸氢钠",
        "碱金属",
        "铁",
        "铝",
        "镁",
        "铜",
        "STSE",
        "化学",
        "离子",
        "非金属",
        "Na2CO3",
        "NaHCO3",
    )
    computer_keywords = (
        "人工智能",
        "机器学习",
        "计算机",
        "Win10",
        "Word2016",
        "EXCEL2016",
        "数字图像",
        "视频处理",
        "软硬件环境",
    )
    electrical_keywords = ("电路",)
    physics_keywords = ("量子物理",)
    accounting_keywords = ("非货币性资产交换",)

    if _contains_any(name, accounting_keywords):
        return "stage2", "accounting"
    if _contains_any(name, history_keywords):
        return "stage2", "history"
    if _contains_any(name, chemistry_keywords):
        return "stage2", "chemistry"
    if _contains_any(name, computer_keywords):
        return "stage2", "computer"
    if _contains_any(name, electrical_keywords):
        return "stage2", "electrical"
    if _contains_any(name, physics_keywords):
        return "stage2", "physics"
    return "stage2", "uncategorized"


def safe_target_path(target_dir: Path, filename: str) -> Path:
    candidate = target_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def repair_stage2_layout() -> list[dict[str, str]]:
    repaired: list[dict[str, str]] = []
    for path in sorted(p for p in STAGE2_ROOT.rglob("*") if p.is_file()):
        stage, category = classify(path)
        if stage != "stage2":
            continue
        current_category = path.parent.name
        if current_category == category:
            continue
        target_dir = STAGE2_ROOT / category
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = safe_target_path(target_dir, path.name)
        shutil.move(str(path), str(target_path))
        repaired.append(
            {
                "source": str(path),
                "target": str(target_path),
                "stage": stage,
                "category": category,
            }
        )
        print(f"{path} => {target_path}")
    return repaired


def main() -> None:
    ORIGINAL_ROOT.mkdir(parents=True, exist_ok=True)
    STAGE1_ROOT.mkdir(parents=True, exist_ok=True)
    STAGE2_ROOT.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in ORIGINAL_ROOT.rglob("*") if path.is_file())
    moved: list[dict[str, str]] = []

    for path in files:
        stage, category = classify(path)
        target_root = STAGE1_ROOT if stage == "stage1" else STAGE2_ROOT
        target_dir = target_root / category
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = safe_target_path(target_dir, path.name)
        shutil.move(str(path), str(target_path))
        moved.append(
            {
                "source": str(path),
                "target": str(target_path),
                "stage": stage,
                "category": category,
            }
        )
        print(f"{path} => {target_path}")

    repaired = repair_stage2_layout()

    summary: dict[str, dict[str, int]] = {"stage1": {}, "stage2": {}}
    for item in moved + repaired:
        stage = item["stage"]
        category = item["category"]
        summary[stage][category] = summary[stage].get(category, 0) + 1

    print(
        json.dumps(
            {
                "moved_count": len(moved),
                "repaired_count": len(repaired),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
