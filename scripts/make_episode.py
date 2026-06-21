#!/usr/bin/env python3
"""
Generate a podcast episode (mp3) from a plain-text narration script using the
OpenAI TTS API, then (re)build the RSS feed served by GitHub Pages.

No third-party dependencies — standard library only (urllib). Works on py3.9+.

Usage:
  OPENAI_API_KEY=sk-... python3 scripts/make_episode.py build/script-2026-06-21.md
  python3 scripts/make_episode.py build/script.md --title "デイリーブリーフ 6/21" --date 2026-06-21
  python3 scripts/make_episode.py --rebuild-feed      # only regenerate podcast.xml
"""
import sys, os, json, re, time, html, subprocess, tempfile
import urllib.request, urllib.error
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EP_DIR = DOCS / "episodes"
MANIFEST = ROOT / "episodes.json"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

API_URL = "https://api.openai.com/v1/audio/speech"
MAX_CHARS = 3500          # safely under the 4096-char TTS input limit


def die(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def chunk_text(text, limit=MAX_CHARS):
    """Split into <=limit pieces on paragraph, then sentence, boundaries."""
    paras = re.split(r"\n\s*\n", text.strip())
    chunks, cur = [], ""
    for p in (p.strip() for p in paras):
        if not p:
            continue
        if cur and len(cur) + len(p) + 2 <= limit:
            cur += "\n\n" + p
        elif len(p) <= limit:
            if cur:
                chunks.append(cur)
            cur = p
        else:  # paragraph longer than limit -> split by sentence
            if cur:
                chunks.append(cur)
                cur = ""
            for s in re.split(r"(?<=[。．.!?！？])\s*", p):
                if len(cur) + len(s) <= limit:
                    cur += s
                else:
                    if cur:
                        chunks.append(cur)
                    cur = s
    if cur:
        chunks.append(cur)
    return chunks


def tts_edge(text, out_path):
    """Free, no-key TTS via Microsoft Edge neural voices (edge-tts).
    edge-tts handles long text internally, so no chunking needed."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(text)
        tmp = tf.name
    cmd = [sys.executable, "-m", "edge_tts",
           "--voice", CONFIG.get("edge_voice", "ja-JP-NanamiNeural"),
           "--rate", CONFIG.get("edge_rate", "+0%"),
           "--file", tmp, "--write-media", str(out_path)]
    try:
        for attempt in range(1, 4):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                return
            if attempt == 3:
                die(f"edge-tts failed: {r.stderr.strip() or r.stdout.strip()}")
            print(f"    retry {attempt}/2 (edge-tts)")
            time.sleep(2 * attempt)
    finally:
        os.unlink(tmp)


def tts_openai(text, api_key):
    payload = {
        "model": CONFIG.get("tts_model", "gpt-4o-mini-tts"),
        "voice": CONFIG.get("voice", "alloy"),
        "input": text,
        "response_format": "mp3",
    }
    instr = CONFIG.get("voice_instructions", "").strip()
    if instr:
        payload["instructions"] = instr
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def synthesize(text, out_path, backend, api_key):
    if backend == "edge":
        print("  TTS backend: edge-tts (free)")
        tts_edge(text, out_path)
        return
    print("  TTS backend: openai")
    chunks = chunk_text(text)
    print(f"  splitting into {len(chunks)} chunk(s)")
    with open(out_path, "wb") as f:
        for i, c in enumerate(chunks, 1):
            for attempt in range(1, 4):
                try:
                    audio = tts_openai(c, api_key)
                    f.write(audio)
                    print(f"    chunk {i}/{len(chunks)} ok ({len(audio):,} bytes)")
                    break
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", "ignore")
                    if attempt == 3:
                        die(f"TTS failed ({e.code}): {body}")
                    print(f"    retry {attempt}/2 after HTTP {e.code}")
                    time.sleep(2 * attempt)
                except urllib.error.URLError as e:
                    if attempt == 3:
                        die(f"network error: {e}")
                    time.sleep(2 * attempt)


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def estimate_duration(text):
    cps = CONFIG.get("chars_per_sec", 7)
    secs = max(1, int(len(text) / cps))
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


def build_feed():
    cfg = CONFIG
    base = cfg["base_url"].rstrip("/") + "/"
    items = []
    for ep in sorted(load_manifest(), key=lambda e: e["date"], reverse=True):
        url = base + "episodes/" + ep["file"]
        pub = format_datetime(datetime.fromisoformat(ep["date"]).replace(tzinfo=timezone.utc))
        items.append(
            "    <item>\n"
            f"      <title>{html.escape(ep['title'])}</title>\n"
            f"      <description>{html.escape(ep.get('description', ''))}</description>\n"
            f"      <pubDate>{pub}</pubDate>\n"
            f'      <enclosure url="{html.escape(url)}" length="{ep["bytes"]}" type="audio/mpeg"/>\n'
            f'      <guid isPermaLink="false">{html.escape(ep["file"])}</guid>\n'
            f"      <itunes:duration>{ep.get('duration', '')}</itunes:duration>\n"
            "      <itunes:explicit>false</itunes:explicit>\n"
            "    </item>")
    cover = f'    <itunes:image href="{html.escape(base + "cover.jpg")}"/>\n' if cfg.get("has_cover") else ""
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "  <channel>\n"
        f"    <title>{html.escape(cfg['podcast_title'])}</title>\n"
        f"    <link>{html.escape(base)}</link>\n"
        f"    <language>{cfg.get('language_code', 'ja')}</language>\n"
        f"    <description>{html.escape(cfg.get('podcast_description', ''))}</description>\n"
        f"    <itunes:author>{html.escape(cfg.get('author', 'auto'))}</itunes:author>\n"
        f"    <itunes:summary>{html.escape(cfg.get('podcast_description', ''))}</itunes:summary>\n"
        "    <itunes:explicit>false</itunes:explicit>\n"
        f'    <itunes:category text="{html.escape(cfg.get("category", "Education"))}"/>\n'
        f"{cover}"
        + "\n".join(items) + "\n"
        "  </channel>\n"
        "</rss>\n")
    (DOCS / "podcast.xml").write_text(feed, encoding="utf-8")
    print(f"  feed rebuilt with {len(items)} episode(s)")


def main():
    EP_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").touch()
    if len(sys.argv) < 2:
        die("usage: make_episode.py <script.md> [--title T] [--date YYYY-MM-DD] | --rebuild-feed")
    if "FILL_AFTER" in CONFIG.get("base_url", ""):
        die("config.json の base_url がまだ未設定です（リポジトリ作成後に埋めます）。")

    if sys.argv[1] == "--rebuild-feed":
        build_feed()
        return

    backend = CONFIG.get("tts_backend", "edge")
    api_key = os.environ.get("OPENAI_API_KEY")
    if backend == "openai" and not api_key:
        die("tts_backend=openai ですが OPENAI_API_KEY が未設定です。")

    args = sys.argv[2:]
    def opt(name):
        return args[args.index(name) + 1] if name in args else None
    date = opt("--date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = opt("--slug")                      # e.g. "en" -> 2026-06-21-en.mp3
    if opt("--voice"):                        # per-run voice override (e.g. English voice)
        CONFIG["edge_voice"] = opt("--voice")
    if opt("--rate"):
        CONFIG["edge_rate"] = opt("--rate")
    text = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    if not text:
        die("台本が空です。")
    title = opt("--title") or f"{CONFIG.get('episode_title_prefix', 'Daily Brief')} {date}"
    desc = re.sub(r"\s+", " ", text)[:300]

    fname = f"{date}-{slug}.mp3" if slug else f"{date}.mp3"
    out = EP_DIR / fname
    print(f"Generating: {title}")
    synthesize(text, out, backend, api_key)
    nbytes = out.stat().st_size

    m = [e for e in load_manifest() if e["file"] != fname]
    m.append({"title": title, "date": date, "file": fname,
              "bytes": nbytes, "duration": estimate_duration(text), "description": desc})
    save_manifest(m)
    build_feed()
    print(f"Done -> {out}  ({nbytes:,} bytes, ~{estimate_duration(text)})")


if __name__ == "__main__":
    main()
