# Weekly Generate Prompt — 月曜 6:00 JST 起床手順書

`/loop` セッションが月曜 6:00 JST に起床した時の自己実行手順。
**ウィークリーブリーフィング 3 部** を生成し、`/weekly/{YYYY-WNN}.html` を出力。

---

## 0. 当日判定

```bash
python -c "from datetime import datetime; n=datetime.now(); print(n.isoformat(), n.weekday(), n.hour)"
```

`weekday()=0` 月曜かつ `hour>=6` でなければ §6 へ。

---

## 1. 入力データ読込

前日（日曜）の weekly_prep が完了しているか確認:
```bash
cd C:\Users\Takumi\dev\news-dashboard
test -f data/processed/week-{YYYY-WNN}.json && echo OK || echo "FAIL: weekly_prep 未完"
```

未完なら `blockers.md` 記録 + §6 で同週月曜 7:00 へ再スケジューリング（リカバリ）。

---

## 2. Part 1: 業界動向

`config/prompts/weekly_part1_industry.md` を Read、`{{USER_CONTEXT}}` 置換。
入力: `data/processed/week-{YYYY-WNN}.json` + 前週 Part 1（`data/processed/weekly/{YYYY-WNN-1}.json` の `part1` フィールド、無ければ None）。

出力: 600-800 字の Markdown を生成 → `part1` フィールドへ。

---

## 3. Part 2: 社会構造シグナル

`config/prompts/weekly_part2_social.md` を Read、置換。
入力: `data/processed/week-{YYYY-WNN}.json` + Part 1 結果。
出力: 800-1,200 字、6 レンズから 1-2 個選択。

---

## 4. Part 3: 歴史・同類事例との照射（**最重要、品質要注意**）

`config/prompts/weekly_part3_historical.md` を Read、置換。
入力: Part 1 + Part 2 + `data/liberal_arts/{YYYY-WNN}/*.json`（liberal_arts_pool）。

### 4.1 中心テーマ抽出（1-2 個）

Part 1 / 2 から「今週の中心テーマ」を再特定。

### 4.2 アナロジー素材選定

`liberal_arts_pool` から `confidence: high|medium` のみ対象、
構造的接続が成立する 2-4 個を選択。**陳腐類推（D-18）は使わない**:
- ❌ 「AI 革命は産業革命と同じ」
- ❌ 「PC 普及期と同じ構造」と言うだけ
- ✅ 「XX 世紀の○○と同型で、△△が異なるためキーファクターは○○」

### 4.3 1,000-2,000 字、アナロジー 2-4 本

各アナロジーは:
- 素材の要約
- 当時何が本当に起きていたか（結論先出し）
- 現代シグナルへの示唆（独立段落）
- **相違点と限界**（必須、独立段落、`class="limit"` 維持）

最後の総合段落で USER_CONTEXT 中心テーマ（業務革新 / ワクワク）と接続。

---

## 5. 保存 + サイトビルド

```bash
# 3 部統合 JSON を保存
data/processed/weekly/{YYYY-WNN}.json
# 構造:
# {
#   "week_label": "WEEK 17 / 2026",
#   "date_range": "2026-04-19 〜 2026-04-25",
#   "theme_title": "（Part 1 から導出した週次テーマタイトル）",
#   "lens": "労働 × 知識民主化",
#   "lens_id": "labor",
#   "summary_excerpt": "（Part 1 の冒頭から自動抽出 or 手動）",
#   "part1": "（Markdown）",
#   "part2": "（Markdown）",
#   "part3": "（Markdown）",
#   "topics": [{id, label, count}, ...],  # 週次トピック分布
#   "references": [...]
# }

python -m src.build_site
```

`site/weekly/{YYYY-WNN}.html` と `site/weekly/index.html` が更新される。

---

## 6. self-critique

- ですます調統一（D-36）
- Part 1: 業界構造レベル止まり、社会構造に踏み込んでいない
- Part 2: 6 レンズ全部使っていない（1-2 個選択）
- Part 3: 陳腐類推なし、限界段落あり、分野分散
- 全体: 図解は装飾目的でない（D-40）
- ページ URL から sub-resource 解決確認（CLAUDE.md self-critique 8 項目）

---

## 7. git commit & push

```bash
git add data/processed/weekly/ site/weekly/
git commit -m "weekly: $(date +%Y-W%V)"
git push origin main
```

→ Pages デプロイ起動 → 公開。

---

## 8. 次回スケジューリング

`ScheduleWakeup` で **次の日曜 20:00 JST**（次週準備）:
- prompt: `<<autonomous-loop-dynamic>>`
- reason: 「次の日曜 20:00 JST に weekly_prep 起動」

---

## 注意

- 生成時間が長い（30-60 分）— マスターが起きて読む 7:00 JST に間に合うよう 6:00 開始
- 失敗時は push しない、`blockers.md` 記録、翌週再試行
- Part 3 の陳腐類推チェックは **マスター G-6 レビューで最終確認**（運用初期は CC のセルフチェック後にマスター確認）
