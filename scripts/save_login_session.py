"""One-off interactive helper to save a logged-in Instagram/Threads session.

This opens a real (non-headless) Chromium window pointed at the platform's own
login page. Log in there yourself -- this script never sees or handles your
credentials. Once you're looking at your own feed/profile, come back to this
terminal and press Enter; the resulting Playwright ``storage_state`` (cookies)
is written to the given output path.

Use a dedicated, disposable account, not your main one: running an automated
crawler against a real logged-in session violates Instagram/Threads' terms of
service and risks that account being flagged, checkpointed, or banned.

The output file is a bearer credential -- anyone with it can act as that
account. Never commit it; inject it into the server as a secret and point
INSTAGRAM_STORAGE_STATE_PATH / THREADS_STORAGE_STATE_PATH at it (see
app/config.py). Sessions can still expire or get revoked, especially when
reused from a different IP than the one used to log in, so expect to redo
this occasionally.

Usage:
    uv run python scripts/save_login_session.py instagram out/instagram_state.json
    uv run python scripts/save_login_session.py threads out/threads_state.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LOGIN_URLS = {
    "instagram": "https://www.instagram.com/accounts/login/",
    "threads": "https://www.threads.com/login",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=sorted(LOGIN_URLS))
    parser.add_argument("output", type=Path, help="Where to write the storage_state JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.platform == "instagram":
        from app.instagram.client import open_page
    else:
        from app.threads.client import open_page

    with open_page(headless=False, locale="zh-TW", storage_state_path=None) as page:
        page.goto(LOGIN_URLS[args.platform])
        print(f"A Chromium window opened at the {args.platform} login page.")
        print("Log in there with a DEDICATED, DISPOSABLE account (not your main one).")
        input("Once you're logged in and see your feed/profile, press Enter here... ")
        page.context.storage_state(path=str(args.output))

    print(f"Saved session to {args.output}")
    print("Keep this file secret: it is equivalent to a login for that account.")


if __name__ == "__main__":
    sys.exit(main())
