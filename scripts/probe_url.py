from __future__ import annotations

import re
import sys
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: probe_url.py <url>")
    url = sys.argv[1]
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8", errors="ignore")
    print(payload[:4000])
    print("\n--- LINKS ---")
    for link in re.findall(r'''(?i)(?:href|src)\s*=\s*["']([^"'#]+)["']''', payload)[:80]:
        print(link)


if __name__ == "__main__":
    main()
