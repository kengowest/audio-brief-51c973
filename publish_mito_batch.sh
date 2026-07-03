#!/usr/bin/env bash
# One-off batch publisher for Mitochondria series episodes 2-7 (same DATE, distinct slugs).
# Mirrors run_special.sh steps per episode (TTS JA+EN -> Notion Type=Special), then ONE push + verify.
set -uo pipefail
cd "$(dirname "$0")"
PY="/usr/local/bin/python3.12"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f .env ] && set -a && . ./.env && set +a

DATE="2026-07-03"
BASE_URL="https://kengowest.github.io/audio-brief-51c973"
REPO_SLUG="kengowest/audio-brief-51c973"
EN_VOICE="$("$PY" -c 'import json;print(json.load(open("config.json")).get("edge_voice_en","en-US-GuyNeural"))')"

declare -A SUB=(
  [2]="どうエネルギーを作るのか"
  [3]="弱るとどうなるのか"
  [4]="なぜ今これほど注目されるのか"
  [5]="市場とプレイヤー"
  [6]="増やす・守る科学"
  [7]="どこまで本当か"
)
declare -A SUB_EN=(
  [2]="How energy is made"
  [3]="What happens when they fail"
  [4]="Why the boom now"
  [5]="The market and players"
  [6]="The science of caring for them"
  [7]="How much is really true"
)

for n in 2 3 4 5 6 7; do
  JA="build/script-$DATE-special-$n.md"
  EN="build/script-$DATE-special-$n-en.md"
  NOTES="build/notes-$DATE-special-$n.md"
  TITLE_JA="デイリーブリーフ 特別編：ミトコンドリア 第${n}回 ${SUB[$n]} $DATE"
  TITLE_EN="Daily Brief Special: Mitochondria Ep.${n} ${SUB_EN[$n]} $DATE (English)"
  echo "===== EP $n TTS ====="
  "$PY" scripts/make_episode.py "$JA" --date "$DATE" --slug "special-$n" --notes "$NOTES" --title "$TITLE_JA"
  "$PY" scripts/make_episode.py "$EN" --date "$DATE" --slug "en-special-$n" --voice "$EN_VOICE" --rate "+0%" --notes "$NOTES" --title "$TITLE_EN"
  echo "===== EP $n Notion ====="
  "$PY" scripts/notion_log.py --date "$DATE" --lang JA --type Special --notes "$NOTES" \
    --title "$TITLE_JA" --audio "$BASE_URL/episodes/$DATE-special-$n.mp3"
  "$PY" scripts/notion_log.py --date "$DATE" --lang EN --type Special --notes "$NOTES" \
    --title "$TITLE_EN" --audio "$BASE_URL/episodes/$DATE-en-special-$n.mp3"
done

echo "===== Publish (single commit + push) ====="
git add -A
if git -c user.email="info@emptea.co" -c user.name="kengowest" commit -q -m "mitochondria series ep2-7 (JA+EN)"; then
  GIT_TERMINAL_PROMPT=0 git push origin master
else
  echo "nothing to commit"
fi

echo "===== Verify deploy (rebuild if stalled) ====="
URL="$BASE_URL/episodes/$DATE-special-7.mp3"   # last file = proxy for full deploy
for i in $(seq 1 9); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -I "$URL")"
  echo "verify poll $i: $code"
  [ "$code" = "200" ] && { echo "LIVE"; break; }
  [ "$i" = "3" ] && { echo "nudging rebuild..."; gh api -X POST "repos/$REPO_SLUG/pages/builds" >/dev/null 2>&1 && echo "rebuild requested" || echo "rebuild request failed"; }
  sleep 20
done
echo "DONE mito batch"
