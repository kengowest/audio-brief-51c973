#!/usr/bin/env bash
# Special (one-off deep-dive) pipeline: TTS JA+EN -> Notion (Type=Special) -> publish.
# Research + script writing is done BEFORE this (e.g. via the deep-research skill).
# This script expects these files to already exist:
#   build/script-<DATE>-special.md      (Japanese narration)
#   build/script-<DATE>-special-en.md   (English narration)
#   build/notes-<DATE>-special.md       (SUMMARY/TOPICS/SOURCE lines)
#
# Usage:
#   ./run_special.sh "<TOPIC>" [DATE]
# e.g.
#   ./run_special.sh "日米ウェルネス比較" 2026-06-22
#
# Slug rule (matches make_episode.py lang detection: slug.startswith("en") => English voice):
#   JA slug = "special"      -> episodes/<DATE>-special.mp3
#   EN slug = "en-special"   -> episodes/<DATE>-en-special.mp3
set -uo pipefail
cd "$(dirname "$0")"

PY="/usr/local/bin/python3.12"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f .env ] && set -a && . ./.env && set +a   # NOTION_TOKEN / NOTION_DB_ID (optional)

TOPIC="${1:?usage: ./run_special.sh \"<TOPIC>\" [DATE]}"
DATE="${2:-$(date +%F)}"
BASE_URL="https://kengowest.github.io/audio-brief-51c973"

JA="build/script-$DATE-special.md"
EN="build/script-$DATE-special-en.md"
NOTES="build/notes-$DATE-special.md"

[ -s "$JA" ]    || { echo "FATAL: $JA not found (write the JA script first)"; exit 1; }
[ -s "$NOTES" ] || { echo "WARN: $NOTES not found — show notes / Notion will be sparse"; }

echo "===== run_special $DATE \"$TOPIC\" $(date) ====="

# 1) TTS (JA + EN)
echo "[1/3] TTS..."
EN_VOICE="$("$PY" -c 'import json;print(json.load(open("config.json")).get("edge_voice_en","en-US-GuyNeural"))')"
"$PY" scripts/make_episode.py "$JA" --date "$DATE" --slug special --notes "$NOTES" \
  --title "デイリーブリーフ 特別編：$TOPIC $DATE"
if [ -s "$EN" ]; then
  "$PY" scripts/make_episode.py "$EN" --date "$DATE" --slug en-special --notes "$NOTES" \
    --voice "$EN_VOICE" --rate "+0%" --title "Daily Brief Special: $TOPIC $DATE (English)"
fi

# 2) Notion (Type=Special). Skips quietly if NOTION_TOKEN/NOTION_DB_ID unset.
echo "[2/3] Notion..."
"$PY" scripts/notion_log.py --date "$DATE" --lang JA --type Special --notes "$NOTES" \
  --title "デイリーブリーフ 特別編：$TOPIC $DATE" --audio "$BASE_URL/episodes/$DATE-special.mp3"
if [ -s "$EN" ]; then
  "$PY" scripts/notion_log.py --date "$DATE" --lang EN --type Special --notes "$NOTES" \
    --title "Daily Brief Special: $TOPIC $DATE (English)" --audio "$BASE_URL/episodes/$DATE-en-special.mp3"
fi

# 3) Publish
echo "[3/3] Publish..."
git add -A
git -c user.email="info@emptea.co" -c user.name="kengowest" commit -q -m "special episode $DATE: $TOPIC (JA+EN)" || { echo "nothing to commit"; exit 0; }
GIT_TERMINAL_PROMPT=0 git push origin master
echo "DONE special $DATE"
