#!/usr/bin/env python3
"""
Append one episode to the Notion "Daily Brief (Podcast Log)" database via the
official Notion API. Cron-safe: uses an integration token, no MCP needed.

Reads NOTION_TOKEN and NOTION_DB_ID from the environment (load .env first).
If either is missing, exits 0 quietly (so the audio pipeline still succeeds).

Usage:
  notion_log.py --title T --date YYYY-MM-DD --lang JA|EN --audio URL --notes build/notes-DATE.md [--type Daily|Special]

notes file format (one per line):
  SUMMARY: <one paragraph>
  TOPICS: gut-health,startups,tech-AI,tea,amazon
  SOURCE: <title> | <url>
"""
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

API = "https://api.notion.com/v1/pages"
VALID_TOPICS = {"gut-health", "startups", "tech-AI", "tea", "amazon"}


def opt(name, default=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a else default


def parse_notes(path):
    summary, topics, sources = "", [], []
    if path and Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            up = s.upper()
            if up.startswith("SUMMARY:"):
                summary = s.split(":", 1)[1].strip()
            elif up.startswith("TOPICS:"):
                topics = [t.strip() for t in s.split(":", 1)[1].split(",")
                          if t.strip() in VALID_TOPICS]
            elif up.startswith("SOURCE:"):
                v = s.split(":", 1)[1].strip()
                if "|" in v:
                    t, u = [x.strip() for x in v.split("|", 1)]
                else:
                    t, u = v, ""
                if t:
                    sources.append((t, u))
    return summary, topics, sources


def main():
    token = os.environ.get("NOTION_TOKEN")
    db = os.environ.get("NOTION_DB_ID")
    if not token or not db:
        print("notion_log: NOTION_TOKEN/NOTION_DB_ID 未設定 → スキップ")
        return
    title = opt("--title") or "Daily Brief"
    date = opt("--date")
    lang = opt("--lang") or "JA"
    audio = opt("--audio")
    ep_type = opt("--type") or "Daily"   # Daily | Special
    summary, topics, sources = parse_notes(opt("--notes"))

    props = {"Name": {"title": [{"text": {"content": title[:2000]}}]},
             "Language": {"select": {"name": lang}},
             "Type": {"select": {"name": ep_type}}}
    if date:
        props["Date"] = {"date": {"start": date}}
    if audio:
        props["Audio"] = {"url": audio}
    if summary:
        props["Summary"] = {"rich_text": [{"text": {"content": summary[:1900]}}]}
    if topics:
        props["Topics"] = {"multi_select": [{"name": t} for t in topics]}
    if sources:
        inline = " / ".join(t for t, _ in sources)
        props["Sources"] = {"rich_text": [{"text": {"content": inline[:1900]}}]}

    children = []
    if summary:
        children.append({"object": "block", "type": "paragraph",
                         "paragraph": {"rich_text": [{"type": "text", "text": {"content": summary[:1900]}}]}})
    if sources:
        children.append({"object": "block", "type": "heading_2",
                         "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Sources"}}]}})
        for t, u in sources:
            rt = {"type": "text", "text": {"content": t}}
            if u:
                rt["text"]["link"] = {"url": u}
            children.append({"object": "block", "type": "bulleted_list_item",
                             "bulleted_list_item": {"rich_text": [rt]}})

    flag = "\U0001F1EF\U0001F1F5" if lang == "JA" else "\U0001F1FA\U0001F1F8"
    body = json.dumps({"parent": {"database_id": db},
                       "icon": {"type": "emoji", "emoji": flag},
                       "properties": props, "children": children}).encode("utf-8")
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            url = json.loads(r.read()).get("url", "")
            print(f"notion_log: 追記OK ({lang}) {url}")
    except urllib.error.HTTPError as e:
        print(f"notion_log: FAILED {e.code}: {e.read().decode('utf-8','ignore')[:400]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
