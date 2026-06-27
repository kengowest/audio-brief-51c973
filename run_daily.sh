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
LOG="build/cron-$DATE.log"
exec >>"$LOG" 2>&1
echo "===== run_daily $DATE $(date) ====="

# --- Slack notification (chat.postMessage). Needs SLACK_BOT_TOKEN in .env. ---
SLACK_NOTIFY_CHANNEL="${SLACK_NOTIFY_CHANNEL:-D0APBH10LSG}"
notify_slack() {
  # Prefer Incoming Webhook (simplest); fall back to Bot Token (chat.postMessage).
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    local body
    body="$(SLACK_TEXT="$1" "$PY" -c 'import json,os;print(json.dumps({"text":os.environ["SLACK_TEXT"]}))')"
    curl -sS -X POST -H "Content-type: application/json" --data "$body" "$SLACK_WEBHOOK_URL" \
      >/dev/null && echo "slack: sent (webhook)" || echo "slack: webhook failed"
  elif [ -n "${SLACK_BOT_TOKEN:-}" ]; then
    local payload
    payload="$(SLACK_TEXT="$1" SLACK_CH="$SLACK_NOTIFY_CHANNEL" "$PY" -c \
      'import json,os;print(json.dumps({"channel":os.environ["SLACK_CH"],"text":os.environ["SLACK_TEXT"],"unfurl_links":False,"unfurl_media":False}))')"
    curl -sS -X POST https://slack.com/api/chat.postMessage \
      -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
      -H "Content-type: application/json; charset=utf-8" \
      --data "$payload" | grep -q '"ok":true' && echo "slack: sent (bot)" || echo "slack: post failed"
  else
    echo "slack: no SLACK_WEBHOOK_URL / SLACK_BOT_TOKEN, skip"
  fi
}

# On any unexpected/early exit, alert with the tail of today's log.
SUCCESS=0
on_exit() {
  [ "$SUCCESS" = "1" ] && return 0
  notify_slack "$(printf '🚨 デイリーブリーフ %s 生成失敗\n%s\nlog: %s' \
    "$DATE" "$(tail -n 6 "$LOG" 2>/dev/null)" "$LOG")"
}
trap on_exit EXIT

# 1) Research + write JA script, EN script, and notes (with sources)
# Retry on transient API failures (e.g. "Connection closed mid-response")
echo "[1/4] Claude Code research & write..."
PROMPT="$(cat prompts/daily_brief.md)

今日の日付は $DATE です。build/script-$DATE.md（日本語）、build/script-$DATE-en.md（英語）、build/notes-$DATE.md（ショーノート）の3ファイルを書き出してください。"
for attempt in 1 2 3 4 5; do
  echo "  [1/4] attempt $attempt/5 @ $(date)"
  claude -p "$PROMPT" --allowedTools "WebSearch,WebFetch,Read,Write"
  [ -s "$JA" ] && { echo "  [1/4] OK on attempt $attempt"; break; }
  echo "  [1/4] attempt $attempt failed ($JA not produced); retrying in 120s..."
  sleep 120
done

[ -s "$JA" ] || { echo "FATAL: $JA not produced after 5 attempts"; exit 1; }

# 2) Synthesize audio (JA + EN) with show-notes description
echo "[2/4] TTS..."
EN_VOICE="$("$PY" -c 'import json;print(json.load(open("config.json")).get("edge_voice_en","en-US-GuyNeural"))')"
"$PY" scripts/make_episode.py "$JA" --date "$DATE" --notes "$NOTES" \
  --title "デイリーブリーフ $DATE"
if [ -s "$EN" ]; then
  "$PY" scripts/make_episode.py "$EN" --date "$DATE" --slug en --notes "$NOTES" \
    --voice "$EN_VOICE" --rate "+0%" --title "Daily Brief $DATE (English)"
fi

# 3) Log to Notion (skips quietly if NOTION_TOKEN/NOTION_DB_ID unset)
echo "[3/4] Notion..."
"$PY" scripts/notion_log.py --date "$DATE" --lang JA --type Daily --notes "$NOTES" \
  --title "デイリーブリーフ $DATE" --audio "$BASE_URL/episodes/$DATE.mp3"
if [ -s "$EN" ]; then
  "$PY" scripts/notion_log.py --date "$DATE" --lang EN --type Daily --notes "$NOTES" \
    --title "Daily Brief $DATE (English)" --audio "$BASE_URL/episodes/$DATE-en.mp3"
fi

# 4) Publish
echo "[4/4] Publish..."
git add -A
if git -c user.email="info@emptea.co" -c user.name="kengowest" commit -q -m "episode $DATE (JA+EN)"; then
  GIT_TERMINAL_PROMPT=0 git push origin master
else
  echo "nothing to commit"
fi
echo "DONE $DATE"

# --- Success: notify with audio links (JA + EN) ---
SUCCESS=1
MSG="$(printf '✅ デイリーブリーフ %s 公開完了\nJA: %s/episodes/%s.mp3' "$DATE" "$BASE_URL" "$DATE")"
[ -s "$EN" ] && MSG="$(printf '%s\nEN: %s/episodes/%s-en.mp3' "$MSG" "$BASE_URL" "$DATE")"
notify_slack "$MSG"
