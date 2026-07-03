#!/usr/bin/env python3
"""
Prune old *daily* episode audio to keep the published site (docs/) small, so the
GitHub Pages build stays fast and doesn't stall (see 2026-07-03 stuck-build 404).

What it does:
  - Deletes daily mp3s older than KEEP_DAYS from docs/episodes/ AND removes their
    entries from episodes.json (so the feed never points at a 404).
  - KEEPS all *special* episodes forever (deep-dive / series content is evergreen).
  - Rebuilds podcast.xml.

What it does NOT touch:
  - Notion log (the only durable, searchable record of summaries/sources — separate layer).
  - git history: pruned mp3s remain in past commits, so any episode is recoverable via git.

Standard library only. Run from anywhere; paths resolve relative to repo root.

Usage:
  python3 scripts/prune_episodes.py                 # keep-days from config (default 30), dry-run off
  python3 scripts/prune_episodes.py --keep-days 45
  python3 scripts/prune_episodes.py --dry-run       # show what would be pruned, change nothing
"""
import sys, json, subprocess
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EP_DIR = ROOT / "docs" / "episodes"
MANIFEST = ROOT / "episodes.json"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def is_special(entry):
    """Specials are kept forever. Detect by filename slug (…-special.mp3)."""
    return "special" in entry.get("file", "").lower()


def parse_date(entry):
    try:
        return date.fromisoformat(entry.get("date", "")[:10])
    except ValueError:
        return None


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    keep_days = CONFIG.get("keep_daily_days", 30)
    if "--keep-days" in args:
        keep_days = int(args[args.index("--keep-days") + 1])

    if not MANIFEST.exists():
        print("prune: no episodes.json, nothing to do")
        return

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cutoff = date.today() - timedelta(days=keep_days)

    kept, pruned = [], []
    for e in manifest:
        d = parse_date(e)
        if is_special(e) or d is None or d >= cutoff:
            kept.append(e)
        else:
            pruned.append(e)

    if not pruned:
        print(f"prune: nothing older than {keep_days}d (daily). {len(kept)} episode(s) kept.")
        return

    print(f"prune: removing {len(pruned)} daily mp3(s) older than {cutoff} "
          f"(keep {keep_days}d; specials always kept){' [dry-run]' if dry else ''}")
    for e in pruned:
        f = EP_DIR / e["file"]
        print(f"  - {e['file']}  ({e.get('date','?')})")
        if not dry and f.exists():
            f.unlink()

    if dry:
        return

    MANIFEST.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    # Rebuild the feed so podcast.xml matches the trimmed manifest.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_episode.py"),
                    "--rebuild-feed"], check=False)
    print(f"prune: done. {len(kept)} episode(s) remain in feed.")


if __name__ == "__main__":
    main()
