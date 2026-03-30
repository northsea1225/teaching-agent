from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.services.rag import LocalKnowledgeBase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest only supported seed files in batches."
    )
    parser.add_argument("--source-dir", required=True, help="Seed directory to ingest.")
    parser.add_argument(
        "--extensions",
        default=".pdf,.docx,.pptx",
        help="Comma-separated file extensions to include.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="How many files to ingest per batch.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start ingesting from this file index after filtering and sorting.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of files to ingest after offset. 0 means all.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Optional vector-store namespace under vector_store/.",
    )
    parser.add_argument("--reset", action="store_true", help="Reset the vector store before ingest.")
    return parser


def batched(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def main() -> None:
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        raise SystemExit(f"Source directory does not exist: {source_dir}")

    suffixes = {
        item.strip().lower() if item.strip().startswith(".") else f".{item.strip().lower()}"
        for item in args.extensions.split(",")
        if item.strip()
    }
    paths = sorted(
        path.resolve()
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )
    if not paths:
        raise SystemExit("No supported files found for ingestion.")

    offset = max(args.offset, 0)
    limit = max(args.limit, 0)
    if offset:
        paths = paths[offset:]
    if limit:
        paths = paths[:limit]
    if not paths:
        raise SystemExit("No supported files found after applying offset/limit.")

    kb = LocalKnowledgeBase(namespace=args.namespace)
    total_processed = 0
    total_chunks = 0
    total_skipped: list[str] = []
    total_batches = 0
    final_total_chunks = 0

    for batch_index, batch_paths in enumerate(batched(paths, max(args.batch_size, 1)), start=1):
        stats = kb.ingest_paths(batch_paths, reset=args.reset and batch_index == 1)
        total_batches += 1
        total_processed += int(stats.get("processed_files", 0))
        total_chunks += int(stats.get("chunk_count", 0))
        total_skipped.extend(str(item) for item in stats.get("skipped_files", []))
        final_total_chunks = int(stats.get("total_chunks_in_store", final_total_chunks))
        print(
            f"BATCH {batch_index}\tFILES {len(batch_paths)}\tPROCESSED {stats.get('processed_files', 0)}"
            f"\tCHUNKS {stats.get('chunk_count', 0)}\tTOTAL {stats.get('total_chunks_in_store', final_total_chunks)}"
        , flush=True)

    print("Knowledge base supported-seed ingest complete.", flush=True)
    print(f"Store directory: {kb.store_dir}", flush=True)
    print(f"source_dir: {source_dir}", flush=True)
    print(f"extensions: {','.join(sorted(suffixes))}", flush=True)
    print(f"offset: {offset}", flush=True)
    print(f"limit: {limit}", flush=True)
    print(f"batch_count: {total_batches}", flush=True)
    print(f"supported_files: {len(paths)}", flush=True)
    print(f"processed_files: {total_processed}", flush=True)
    print(f"skipped_files: {len(total_skipped)}", flush=True)
    print(f"chunk_count: {total_chunks}", flush=True)
    print(f"total_chunks_in_store: {final_total_chunks}", flush=True)
    print(f"embedding_backend: {kb.embedding_provider.name}", flush=True)


if __name__ == "__main__":
    main()
