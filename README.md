# auto-podcast — 自分専用デイリー音声ブリーフ

論文・記事を Claude Code が毎日収集・要約し、OpenAI TTS で音声化、GitHub Pages で
RSS 配信する。手持ちのポッドキャストアプリ（Apple Podcasts / Overcast / Pocket Casts 等）で購読して聴く。

```
収集・要約 (Claude Code)  →  音声化 (OpenAI TTS)  →  公開 (GitHub Pages: docs/)  →  購読
```

## 構成
- `config.json` — 番組名・トピック・声・言語・base_url など全設定
- `prompts/daily_brief.md` — Claude Code への台本作成指示
- `scripts/make_episode.py` — 台本テキスト → mp3 + RSS（標準ライブラリのみ）
- `run_daily.sh` — 収集→音声化→公開を一括実行
- `docs/` — GitHub Pages の公開ルート（`podcast.xml` と `episodes/*.mp3`）
- `episodes.json` — エピソード台帳（フィード再生成の元データ）

## 必要なもの
- `OPENAI_API_KEY` 環境変数
- GitHub Pages 有効化（public リポジトリの `docs/` を配信）

## 使い方
```bash
# 手動で1本作る（台本がある場合）
OPENAI_API_KEY=sk-... python3 scripts/make_episode.py build/script-2026-06-21.md --date 2026-06-21

# フィードだけ作り直す
python3 scripts/make_episode.py --rebuild-feed

# 収集から公開まで全自動
OPENAI_API_KEY=sk-... ./run_daily.sh
```

## 言語の切替
`config.json` の `output_language`（"ja" / "en"）と `voice_instructions` を変えるだけ。
