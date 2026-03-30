from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize KB metadata by source path prefix.")
    parser.add_argument("--metadata-path", default=r"C:\Users\15635\teaching-agent\vector_store\kb_metadata.json")
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path)
    items = json.loads(metadata_path.read_text(encoding="utf-8"))

    filtered = [item for item in items if not args.prefix or str(item.get("source_path", "")).startswith(args.prefix)]
    unique_sources = Counter(str(item.get("source_path", "")) for item in filtered)

    print(f"CHUNKS\t{len(filtered)}")
    print(f"UNIQUE_SOURCES\t{len(unique_sources)}")
    extension_counts = Counter(Path(path).suffix.lower() or "<noext>" for path in unique_sources)
    for suffix, count in extension_counts.most_common():
        print(f"EXT\t{suffix}\t{count}")

    for path, count in unique_sources.most_common(20):
        print(f"SOURCE\t{count}\t{path}")


if __name__ == "__main__":
    main()
