"""Command-line entry point for manually testing YouTube search."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from app.youtube.search import search_youtube


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch anonymous YouTube keyword search results with Playwright."
    )
    parser.add_argument("query", help="YouTube search keyword")
    parser.add_argument("-n", "--limit", type=int, default=10, help="result count")
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
    results = search_youtube(
        args.query,
        args.limit,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        locale=args.locale,
    )
    output = json.dumps(
        [result.as_dict() for result in results],
        ensure_ascii=False,
        indent=2,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
