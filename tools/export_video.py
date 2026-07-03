#!/usr/bin/env python3
"""Export a run-record replay as a video file (optional helper).

Renders the record to the standard self-contained HTML replay, opens it in a headless
browser with autoplay armed, records the playback, and writes a video file. Requires
Playwright, which is deliberately NOT a dependency of this repository:

    pip install playwright && playwright install chromium

Without it, this script exits with that instruction. The zero-install alternative is to
open the replay (``bsq render <record.json>``) and capture it with any screen recorder.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=str, help="path to a run-record .json")
    parser.add_argument("-o", "--out", type=str, default=None, help="output video path (.webm)")
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run: pip install playwright && "
            "playwright install chromium\n(or screen-record the replay opened via "
            "`bsq render` instead)",
            file=sys.stderr,
        )
        return 1

    from bsq.record import load_record
    from bsq.render import render_html

    record_path = Path(args.record)
    html = render_html(load_record(record_path))
    out = Path(args.out) if args.out else record_path.with_suffix(".webm")

    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "replay.html"
        page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                record_video_dir=tmp,
                record_video_size={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(page_path.as_uri() + "?autoplay")
            page.wait_for_function(
                "document.body.dataset.replayDone === '1'", timeout=180_000
            )
            page.wait_for_timeout(1_500)  # hold the finale frame
            video = page.video
            context.close()
            browser.close()
            if video is None:
                print("no video was recorded", file=sys.stderr)
                return 1
            out.parent.mkdir(parents=True, exist_ok=True)
            Path(video.path()).rename(out)
    print(f"video: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
