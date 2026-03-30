from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".mpeg", ".mpg", ".m4v"}
LESSON_PLAN_EXTENSIONS = {".doc", ".docx", ".pdf"}
COURSEWARE_EXTENSIONS = {".ppt", ".pptx", ".pdf"}
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | LESSON_PLAN_EXTENSIONS | COURSEWARE_EXTENSIONS

DEFAULT_ENGLISH_ROOT = Path(r"D:\BaiduNetdiskDownload")
DEFAULT_DESTINATION_ROOT = Path(r"E:\teaching-agent_resources\subject_seed\english")

ENGLISH_PATH_HINTS = (
    "英语",
    "english",
    "welcome unit",
    "listening and speaking",
    "reading and thinking",
    "discovering useful structures",
    "reading for writing",
    "assessing your progress",
)

ENGLISH_FILE_HINTS = (
    "unit ",
    "welcome unit",
    "listening and speaking",
    "reading and thinking",
    "discovering useful structures",
    "reading for writing",
    "assessing your progress",
    "listening and talking",
    "words and expressions",
    "reading for writing",
    "people of achievement",
    "looking into the future",
    "fascinating parks",
    "science and scientists",
    "bridging cultures",
    "food and culture",
    "first aid",
    "poems",
    "environmental protection",
    "adversity and courage",
)


@dataclass
class ImportReport:
    source_file_count: int = 0
    source_total_bytes: int = 0
    moved_counts: dict[str, int] = field(default_factory=dict)
    moved_files: list[str] = field(default_factory=list)
    deleted_video_files: list[str] = field(default_factory=list)
    deleted_duplicate_files: list[str] = field(default_factory=list)
    skipped_unsupported_files: list[str] = field(default_factory=list)
    legacy_doc_files: list[str] = field(default_factory=list)


def sha256_for_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def ensure_unique_destination(destination_dir: Path, filename: str) -> Path:
    candidate = destination_dir / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = destination_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def load_existing_hashes(root: Path) -> set[str]:
    hashes: set[str] = set()
    if not root.exists():
        return hashes
    for file_path in root.rglob("*"):
        if file_path.is_file():
            hashes.add(sha256_for_file(file_path))
    return hashes


def looks_like_english(file_path: Path) -> bool:
    lowered_path = str(file_path).lower()
    lowered_name = file_path.name.lower()
    if any(hint in lowered_path for hint in ENGLISH_PATH_HINTS):
        return True
    if any(hint in lowered_name for hint in ENGLISH_FILE_HINTS):
        return True
    return False


def classify_destination(file_path: Path, destination_root: Path) -> Path | None:
    suffix = file_path.suffix.lower()
    parent_hint = str(file_path.parent)

    if suffix in LESSON_PLAN_EXTENSIONS and "教学设计" in parent_hint:
        return destination_root / "教学设计"
    if suffix in COURSEWARE_EXTENSIONS and ("课件" in parent_hint or suffix in {".ppt", ".pptx"}):
        return destination_root / "课件"
    if suffix in {".doc", ".docx"}:
        return destination_root / "教学设计"
    if suffix in {".ppt", ".pptx"}:
        return destination_root / "课件"
    if suffix == ".pdf":
        return destination_root / "教学设计"
    return None


def import_english_sources(source_root: Path, destination_root: Path, report_path: Path | None = None) -> ImportReport:
    destination_root.mkdir(parents=True, exist_ok=True)
    (destination_root / "教学设计").mkdir(parents=True, exist_ok=True)
    (destination_root / "课件").mkdir(parents=True, exist_ok=True)

    report = ImportReport()
    seen_hashes = load_existing_hashes(destination_root)

    for file_path in source_root.rglob("*"):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            continue
        if not looks_like_english(file_path):
            continue

        report.source_file_count += 1
        try:
            report.source_total_bytes += file_path.stat().st_size
        except OSError:
            pass

        if suffix in VIDEO_EXTENSIONS:
            report.deleted_video_files.append(str(file_path))
            file_path.unlink()
            continue

        destination_dir = classify_destination(file_path, destination_root)
        if destination_dir is None:
            report.skipped_unsupported_files.append(str(file_path))
            continue

        file_hash = sha256_for_file(file_path)
        if file_hash in seen_hashes:
            report.deleted_duplicate_files.append(str(file_path))
            file_path.unlink()
            continue

        destination_path = ensure_unique_destination(destination_dir, file_path.name)
        shutil.move(str(file_path), str(destination_path))
        seen_hashes.add(file_hash)
        report.moved_files.append(str(destination_path))
        report.moved_counts[destination_dir.name] = report.moved_counts.get(destination_dir.name, 0) + 1
        if suffix == ".doc":
            report.legacy_doc_files.append(str(destination_path))

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import English teaching files from BaiduNetdisk root into the English knowledge source directory.")
    parser.add_argument("--source-root", default=str(DEFAULT_ENGLISH_ROOT), help="BaiduNetdisk root")
    parser.add_argument("--destination-root", default=str(DEFAULT_DESTINATION_ROOT), help="English destination root")
    parser.add_argument("--report-path", required=False, help="Optional JSON report path")
    args = parser.parse_args()

    report = import_english_sources(
        Path(args.source_root),
        Path(args.destination_root),
        Path(args.report_path) if args.report_path else None,
    )

    print(f"SOURCE_FILES\t{report.source_file_count}")
    print(f"SOURCE_GB\t{report.source_total_bytes / 1024 / 1024 / 1024:.2f}")
    for key, value in sorted(report.moved_counts.items()):
        print(f"MOVED_{key}\t{value}")
    print(f"DELETED_VIDEOS\t{len(report.deleted_video_files)}")
    print(f"DELETED_DUPLICATES\t{len(report.deleted_duplicate_files)}")
    print(f"SKIPPED_UNSUPPORTED\t{len(report.skipped_unsupported_files)}")
    print(f"LEGACY_DOC\t{len(report.legacy_doc_files)}")
    if report.legacy_doc_files:
        print("LEGACY_DOC_FILES")
        for item in report.legacy_doc_files:
            print(item)


if __name__ == "__main__":
    main()
