from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.services.rag import LocalKnowledgeBase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest local knowledge-base files.")
    parser.add_argument("--source-dir", default=None, help="Optional source directory to ingest.")
    parser.add_argument(
        "--include-parsed-assets",
        action="store_true",
        help="Also ingest parsed upload artifacts from data/parsed.",
    )
    parser.add_argument("--session-id", default=None, help="Limit parsed assets to one session.")
    parser.add_argument("--reset", action="store_true", help="Reset the vector store before ingest.")
    parser.add_argument(
        "--namespace",
        default=None,
        help="Optional vector-store namespace under vector_store/.",
    )
    parser.add_argument(
        "--include-keyword",
        action="append",
        default=[],
        help="Only ingest files whose full path contains one of these keywords. Repeatable.",
    )
    parser.add_argument(
        "--exclude-keyword",
        action="append",
        default=[],
        help="Skip files whose full path contains one of these keywords. Repeatable.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    kb = LocalKnowledgeBase(namespace=args.namespace)
    if args.include_keyword or args.exclude_keyword:
        source_dir = Path(args.source_dir) if args.source_dir else None
        if source_dir is None:
            raise SystemExit("--include-keyword/--exclude-keyword 需要和 --source-dir 一起使用。")
        paths = [
            path
            for path in source_dir.rglob("*")
            if path.is_file() and not path.name.startswith(".")
        ]
        include_keywords = [item.lower() for item in args.include_keyword]
        exclude_keywords = [item.lower() for item in args.exclude_keyword]
        filtered_paths = []
        for path in paths:
            full_path = str(path).lower()
            if include_keywords and not any(keyword in full_path for keyword in include_keywords):
                continue
            if exclude_keywords and any(keyword in full_path for keyword in exclude_keywords):
                continue
            filtered_paths.append(path.resolve())
        stats = kb.ingest_paths(filtered_paths, reset=args.reset)
    else:
        stats = kb.ingest_default_sources(
            source_dir=args.source_dir,
            include_parsed_assets=args.include_parsed_assets,
            session_id=args.session_id,
            reset=args.reset,
        )
    print("Knowledge base ingest complete.")
    print(f"Store directory: {kb.store_dir}")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
