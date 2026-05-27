# Claude Channel Tracker

Automatically tracks [@claude](https://www.youtube.com/@claude) on YouTube, fetches transcripts, and generates AI summaries using the Claude CLI.

## Structure

```
videos/          # One markdown file per video (AI summary + full transcript)
seen.json        # Tracks processed video IDs (do not edit manually)
tracker.py       # Main script (uv-managed dependencies, no venv needed)
```

## Usage

```bash
# Process any new videos
uv run tracker.py

# First-time setup: mark all existing as seen, skip backlog
uv run tracker.py --mark-seen

# Limit to N most recent new videos
uv run tracker.py --limit 5
```

## Each video note contains

- YouTube link, date, duration
- AI summary: key takeaways, tools & approaches, code/commands, quotable moments
- Full transcript (collapsed)

## Automated via Claude Code Routines

This repo is polled daily by a Claude Code Routine. New video summaries are committed automatically — just `git pull` to get the latest.
