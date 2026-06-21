#!/usr/bin/env bash
# Daily pipeline: research+write script (Claude Code) -> TTS (OpenAI) -> publish (GitHub Pages)
set -euo pipefail
cd "$(dirname "$0")"

DATE="$(date +%F)"
SCRIPT="build/script-$DATE.md"
mkdir -p build

# 1) Claude Code researches and writes today's narration script to $SCRIPT
echo "[1/3] Researching & writing script via Claude Code..."
claude -p "$(cat prompts/daily_brief.md)

今日の日付は $DATE です。台本は build/script-$DATE.md に書き出してください。" \
  --allowedTools "WebSearch,WebFetch,Read,Write" >/dev/null

[ -s "$SCRIPT" ] || { echo "script not produced: $SCRIPT" >&2; exit 1; }

# 2) Synthesize audio + rebuild feed
echo "[2/3] Synthesizing audio with OpenAI TTS..."
python3 scripts/make_episode.py "$SCRIPT" --date "$DATE"

# 3) Publish to GitHub Pages
echo "[3/3] Publishing..."
git add -A
git commit -m "episode $DATE" >/dev/null
git push >/dev/null
echo "Published episode $DATE."
