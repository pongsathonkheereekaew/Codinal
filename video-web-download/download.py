#!/usr/bin/env python3
"""Download embedded HLS videos from supported web pages.

Currently supports pages that expose an .m3u8 URL via schema.org metadata
or embedded player iframes (e.g. fapnut.net-style WordPress players).

Requirements:
    pip install yt-dlp
    ffmpeg (recommended, for merging HLS segments)

Examples:
    python3 download.py "https://example.com/video-page/"
    python3 download.py "https://example.com/video-page/" -o ~/Downloads
    python3 download.py "https://cdn.example.com/stream.m3u8" -o ~/Downloads
    python3 download.py "https://example.com/video-page/" --list-formats
"""

from __future__ import annotations

import argparse
import base64
import html
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

M3U8_PATTERNS = [
    re.compile(r'itemprop="contentURL"\s+content="([^"]+\.m3u8[^"]*)"', re.I),
    re.compile(r'<meta[^>]+itemprop="contentURL"[^>]+content="([^"]+\.m3u8[^"]*)"', re.I),
    re.compile(r'content="([^"]+\.m3u8[^"]*)"[^>]+itemprop="contentURL"', re.I),
    re.compile(r'source\s+src="([^"]+\.m3u8[^"]*)"', re.I),
    re.compile(r'"(https?://[^"\s<>]+\.m3u8[^"\s<>]*)"', re.I),
]

IFRAME_PLAYER_PATTERN = re.compile(r'player-x\.php\?q=([A-Za-z0-9+/=]+)', re.I)
IFRAME_SOURCE_PATTERN = re.compile(r"source\s+src=([^&\s]+)", re.I)


def default_output_dir() -> str:
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return str(downloads)
    return str(Path.cwd() / "downloads")


def page_origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/"


def fetch_page(url: str, referer: str | None = None) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer or page_origin(url),
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_title(page_html: str) -> str | None:
    match = re.search(r'itemprop="name"\s+content="([^"]+)"', page_html, re.I)
    if match:
        return html.unescape(match.group(1))
    match = re.search(r"<title>([^<]+)</title>", page_html, re.I)
    if match:
        return html.unescape(match.group(1).split(" - ")[0].strip())
    return None


def extract_m3u8_url(page_html: str) -> str | None:
    for pattern in M3U8_PATTERNS:
        match = pattern.search(page_html)
        if match:
            return html.unescape(urllib.parse.unquote(match.group(1)))

    iframe_match = IFRAME_PLAYER_PATTERN.search(page_html)
    if iframe_match:
        try:
            decoded = base64.b64decode(iframe_match.group(1)).decode("utf-8", errors="replace")
            source_match = IFRAME_SOURCE_PATTERN.search(decoded)
            if source_match:
                return html.unescape(urllib.parse.unquote(source_match.group(1)))
        except Exception:
            pass

    return None


def is_direct_stream_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.endswith(".m3u8") or ".m3u8?" in lowered


def resolve_stream(page_url: str) -> tuple[str, str | None, str]:
    if is_direct_stream_url(page_url):
        return page_url, None, page_origin(page_url)

    page_html = fetch_page(page_url)
    if len(page_html) < 1000:
        raise RuntimeError(
            f"Page response looks blocked or empty ({len(page_html)} bytes). "
            "Open the page in a browser, then try again."
        )

    stream_url = extract_m3u8_url(page_html)
    if not stream_url:
        debug_path = Path.cwd() / "video_page_debug.html"
        debug_path.write_text(page_html, encoding="utf-8")
        raise RuntimeError(
            "Could not find an .m3u8 stream URL on this page. "
            f"Saved HTML to {debug_path} for debugging."
        )

    return stream_url, extract_title(page_html), page_origin(page_url)


def sanitize_filename(title: str | None) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", title or "video").strip()
    return cleaned or "video"


def run_yt_dlp(
    stream_url: str,
    output_dir: str,
    title: str | None,
    referer: str,
    list_formats: bool,
    extra_args: list[str],
) -> int:
    yt_dlp = shutil.which("yt-dlp")
    if not yt_dlp:
        raise RuntimeError(
            "yt-dlp not found.\n"
            "Install: pip install -U yt-dlp\n"
            "Mac:     brew install yt-dlp ffmpeg"
        )

    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    output_template = str(output_path / f"{sanitize_filename(title)}.%(ext)s")

    command = [
        yt_dlp,
        "--no-playlist",
        "--restrict-filenames",
        "--merge-output-format",
        "mp4",
        "--referer",
        referer,
        "-o",
        output_template,
    ]

    if list_formats:
        command.extend(["-F", stream_url])
    else:
        command.extend(extra_args)
        command.append(stream_url)

    print(f"Stream URL: {stream_url}")
    if title:
        print(f"Title: {title}")
    print(f"Output dir: {output_path}")
    print(f"Running: {' '.join(command)}")
    return subprocess.call(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download embedded HLS videos from supported web pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 download.py \"https://example.com/video/\"\n"
            "  python3 download.py \"https://example.com/video/\" -o ~/Downloads\n"
            "  python3 download.py \"https://cdn.example.com/stream.m3u8\"\n"
        ),
    )
    parser.add_argument("url", help="Video page URL or direct .m3u8 URL")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=default_output_dir(),
        help=f"Output directory (default: {default_output_dir()})",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="List available formats via yt-dlp -F",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)

    if not args.url.startswith("http"):
        parser.error("URL must start with http:// or https://")

    try:
        stream_url, title, referer = resolve_stream(args.url)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    extra_args = [arg for arg in extra if arg != "--"]
    try:
        return run_yt_dlp(
            stream_url,
            args.output_dir,
            title,
            referer,
            args.list_formats,
            extra_args,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
