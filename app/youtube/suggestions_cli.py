"""Command-line entry point for YouTube search-box suggestions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from app.youtube.suggestions import get_youtube_suggestions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch YouTube search-box suggestions with Playwright."
    )
    parser.add_argument("query", help="partial YouTube search keyword")
    parser.add_argument("-n", "--limit", type=int, default=10, help="suggestion count")
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="run Chromium without a visible window (default: false)",
    )
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--locale", default="zh-TW")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    suggestions = get_youtube_suggestions(
        args.query,
        args.limit,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        locale=args.locale,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(suggestions, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
