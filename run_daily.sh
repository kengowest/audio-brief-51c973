#!/usr/bin/env bash
# Daily pipeline: research+write (Claude Code) -> TTS JA+EN (edge-tts)
# -> show notes with sources -> log to Notion -> publish (GitHub Pages).
set -uo pipefail
cd "$(dirname "$0")"

PY="/usr/local/bin/python3.12"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f .env ] && set -a && . ./.env && set +a   # NOTION_TOKEN / NOTION_DB_ID (optional)

DATE="$(date +%F)"
BASE_URL="https://kengowest.github.io/audio-brief-51c973"
JA="build/script-$DATE.md"; EN="build/script-$DATE-en.md"; NOTES="build/notes-$DATE.md"
mkdir -p build
exec >>"build/cron-$DATE.log" 2>&1
echo "===== run_daily $DATE $(date) ====="

# 1) Research + write JA script, EN script, and notes (with sources)
echo "[1/4] Claude Code research & write..."
claude -p "$(cat prompts/daily_brief.md)

今日の日付は $DATE です。build/script-$DATE.md（日本語）、build/script-$DATE-en.md（英語）、build/notes-$DATE.md（ショーノート）の3ファイルを書き出してください。" \
  --allowedTools "WebSearch,WebFetch,Read,Write"

[ -s "$JA" ] || { echo "FATAL: $JA not produced"; exit 1; }

# 2) Synthesize audio (JA + EN) with show-notes description
echo "[2/4] TTS..."
EN_VOICE="$("$PY" -c 'import json;print(json.load(open("config.json")).get("edge_voice_en","en-US-GuyNeural"))')"
"$PY" scripts/make_episode.py "$JA" --date "$DATE" --notes "$NOTES" \
  --title "デイリーブリーフ $DATE"
if [ -s "$EN" ]; then
  "$PY" scripts/make_episode.py "$EN" --date "$DATE" --slug en --notes "$NOTES" \
    --voice "$EN_VOICE" --rate "+20%" --title "Daily Brief $DATE (English)"
fi

# 3) Log to Notion (skips quietly if NOTION_TOKEN/NOTION_DB_ID unset)
echo "[3/4] Notion..."
"$PY" scripts/notion_log.py --date "$DATE" --lang JA --notes "$NOTES" \
  --title "デイリーブリーフ $DATE" --audio "$BASE_URL/episodes/$DATE.mp3"
if [ -s "$EN" ]; then
  "$PY" scripts/notion_log.py --date "$DATE" --lang EN --notes "$NOTES" \
    --title "Daily Brief $DATE (English)" --audio "$BASE_URL/episodes/$DATE-en.mp3"
fi

# 4) Publish
echo "[4/4] Publish..."
git add -A
git -c user.email="info@emptea.co" -c user.name="kengowest" commit -q -m "episode $DATE (JA+EN)" || { echo "nothing to commit"; exit 0; }
GIT_TERMINAL_PROMPT=0 git push origin master
echo "DONE $DATE"
