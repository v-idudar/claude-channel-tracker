#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "yt-dlp",
#   "youtube-transcript-api",
# ]
# ///
"""
Tracks @claude YouTube channel for new videos, fetches transcripts,
and generates AI summaries using the claude CLI.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CHANNEL_URL = "https://www.youtube.com/@claude/videos"
BASE_DIR = Path(__file__).parent
VIDEOS_DIR = BASE_DIR / "videos"
SEEN_FILE = BASE_DIR / "seen.json"

SUMMARY_PROMPT = """You are reviewing a transcript from Anthropic's official Claude YouTube channel.
Produce a concise markdown summary with these sections:

## Summary
2-3 sentence overview of what this video covers.

## Key Takeaways
- Bullet list of the most important concepts, decisions, or insights

## Tools & Approaches Mentioned
- List every tool, library, API, framework, or technique discussed with a one-line description

## Code & Commands
If any code snippets, CLI commands, or configuration patterns were mentioned, reproduce them in fenced code blocks.

## Quotable Moments
1-2 direct quotes that capture the core message well.

Be concise. Focus on what's actionable for a developer wanting to stay expert on Claude.
"""


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def list_channel_videos(since_date: str | None = None) -> list[dict]:
    print(f"Fetching video list from {CHANNEL_URL}...")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s\t%(duration_string)s",
        "--no-warnings",
    ]
    if since_date:
        cmd += ["--dateafter", since_date]
    cmd.append(CHANNEL_URL)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr}", file=sys.stderr)
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            videos.append({
                "id": parts[0],
                "title": parts[1],
                "upload_date": parts[2] if len(parts) > 2 else "",
                "duration": parts[3] if len(parts) > 3 else "",
            })
    return videos


def fetch_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        return " ".join(entry.text for entry in fetched)
    except Exception as e:
        print(f"  Transcript unavailable: {e}")
        return None


def summarize_with_claude(title: str, transcript: str) -> str:
    prompt = f"Video title: {title}\n\nTranscript:\n{transcript[:30000]}"
    result = subprocess.run(
        ["claude", "-p", SUMMARY_PROMPT + "\n\n" + prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return f"*Summary failed: {result.stderr.strip()}*"
    return result.stdout.strip()


def get_video_date(video_id: str) -> str:
    result = subprocess.run(
        ["yt-dlp", "--print", "%(upload_date)s", "--no-warnings",
         f"https://www.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True, timeout=30,
    )
    raw = result.stdout.strip()
    if len(raw) == 8 and raw != "NA":
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return datetime.now().strftime("%Y-%m-%d")


def save_video_note(video: dict, transcript: str | None, summary: str):
    date_str = video.get("upload_date", "")
    if not date_str or date_str == "NA":
        date_str = get_video_date(video["id"])
    elif len(date_str) == 8:
        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in video["title"])[:60]
    filename = f"{date_str}_{video['id']}_{safe_title}.md".replace(" ", "_")
    filepath = VIDEOS_DIR / filename

    content = f"""# {video['title']}

- **YouTube:** https://www.youtube.com/watch?v={video['id']}
- **Date:** {date_str}
- **Duration:** {video.get('duration', 'unknown')}
- **Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

{summary}

---

<details>
<summary>Full Transcript</summary>

{transcript or '*No transcript available*'}

</details>
"""
    filepath.write_text(content)
    print(f"  Saved: {filepath.name}")
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Track @claude YouTube channel")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the N most recent new videos (default: all)")
    parser.add_argument("--mark-seen", action="store_true",
                        help="Mark all existing videos as seen without processing them")
    parser.add_argument("--since", type=str, default=None,
                        help="Only fetch videos uploaded after this date (YYYYMMDD), e.g. 20260506")
    args = parser.parse_args()

    VIDEOS_DIR.mkdir(exist_ok=True)
    seen = load_seen()

    videos = list_channel_videos(since_date=args.since)
    if not videos:
        print("No videos found.")
        return

    if args.mark_seen:
        count = 0
        for v in videos:
            if v["id"] not in seen:
                seen[v["id"]] = {"title": v["title"], "processed": "marked-seen"}
                count += 1
        save_seen(seen)
        print(f"Marked {count} videos as seen (no processing). Future runs will only pick up new videos.")
        return

    new_videos = [v for v in videos if v["id"] not in seen]
    print(f"Found {len(videos)} total videos, {len(new_videos)} new.")

    if args.limit and len(new_videos) > args.limit:
        print(f"Limiting to {args.limit} most recent.")
        new_videos = new_videos[:args.limit]

    if not new_videos:
        print("Nothing new to process.")
        return

    for i, video in enumerate(new_videos, 1):
        print(f"\n[{i}/{len(new_videos)}] {video['title']}")

        transcript = fetch_transcript(video["id"])
        if transcript:
            print(f"  Transcript: {len(transcript)} chars — summarizing with Claude...")
            summary = summarize_with_claude(video["title"], transcript)
        else:
            summary = "*No transcript available for this video.*"

        save_video_note(video, transcript, summary)
        seen[video["id"]] = {
            "title": video["title"],
            "processed": datetime.now().isoformat(),
        }
        save_seen(seen)

    print(f"\nDone. Notes saved to {VIDEOS_DIR}")


if __name__ == "__main__":
    main()
