# video-web-download

Download embedded HLS (`.m3u8`) videos from supported web pages using [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Install

```bash
# Python dependency
pip install -r requirements.txt

# Mac (recommended)
brew install yt-dlp ffmpeg

# Linux
sudo apt install ffmpeg
pip install -U yt-dlp
```

## Usage

```bash
# Download to ~/Downloads (default on macOS if the folder exists)
python3 download.py "https://example.com/video-page/"

# Custom output folder
python3 download.py "https://example.com/video-page/" -o ~/Downloads

# Direct .m3u8 URL
python3 download.py "https://cdn.example.com/stream.m3u8" -o ~/Downloads

# List formats only
python3 download.py "https://example.com/video-page/" --list-formats

# Pass extra yt-dlp flags after --
python3 download.py "https://example.com/video-page/" -o ~/Downloads -- --download-sections "*0:00-0:30"
```

## How it works

1. Fetches the page HTML with browser-like headers
2. Finds an embedded `.m3u8` URL from:
   - `itemprop="contentURL"` metadata
   - generic `.m3u8` links in the page
   - base64-encoded iframe player payloads
3. Downloads and merges the stream with `yt-dlp`

## Notes

- Only download content you have the right to access.
- Site support depends on how the page exposes its stream URL.
- If extraction fails, the script saves `video_page_debug.html` in the current directory for troubleshooting.
