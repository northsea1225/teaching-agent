from __future__ import annotations

from collections import Counter
from pathlib import Path


PATHS = [
    Path(r"D:\BaiduNetdiskDownload\教学设计"),
    Path(r"D:\BaiduNetdiskDownload\课件"),
    Path(r"D:\BaiduNetdiskDownload\课件2"),
]


def main() -> None:
    for path in PATHS:
        print(f"=== {path} ===")
        if not path.exists():
            print("MISSING")
            continue
        files = [item for item in path.rglob("*") if item.is_file()]
        total_size = sum(file.stat().st_size for file in files)
        print(f"TOTAL_FILES\t{len(files)}")
        print(f"TOTAL_GB\t{total_size / 1024 / 1024 / 1024:.2f}")
        counts = Counter(file.suffix.lower() or "<noext>" for file in files)
        for suffix, count in counts.most_common():
            print(f"{suffix}\t{count}")
        print()


if __name__ == "__main__":
    main()
