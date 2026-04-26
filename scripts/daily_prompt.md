# Daily Prompt — Claude Code 起床時の手順書

このファイルは、`/loop` で `ScheduleWakeup` 起床した Claude Code セッションが
**平日 7:00 JST に読んで自動実行する**手順書です。

親プロジェクト (`G:\マイドライブ\匠\テクノロジー\20260418_claude_autonews`) は
`--add-dir` で参照可能。CLAUDE.md / DOMAIN_RULES.md / DO_NOTS.md / USER_CONTEXT.md / STYLE_GUIDE.md
は必要に応じて Read で参照する。

---

## 0. 当日判定（土日祝はスキップ）

```bash
python -c "from datetime import date; d=date.today(); print(d.isoformat(), d.weekday())"
```

`weekday()` が 5 (土) or 6 (日) なら本日処理スキップ → 「§9 次回スケジューリング」へ直行。

---

## 1. 収集 + 選抜（決定論的処理）

```bash
cd C:\Users\Takumi\dev\news-dashboard
python -m src.pipeline.daily_collect
```

出力:
- `data/raw/{today}.jsonl`（全 raw items、デバッグ用）
- `data/rejected/{today}.jsonl`（D-37 違反、ログ）
- `data/processed/selection-{today}.json`（選抜 20 件 + メタ、次工程の入力）

---

## 2. プロンプト読込

`config/prompts/card_analyze.md` を Read。`{{USER_CONTEXT}}` の位置に
親プロジェクト `01_domain/USER_CONTEXT.md` §6 の `## 読者文脈` コードブロック
（`src/utils/context_loader.py` で抽出可能）を埋める。

ただし API 直叩きはしない。**自分（Claude Code）の判断で**プロンプト指示に従い
カードを生成する。

---

## 3. 各 selected item をカード化

`data/processed/selection-{today}.json` を Read。各 item について:

### 3.1 D-37 日付バリデーション再確認
- `published_at` 欠落 / 形式不正 / 未来日付 → `{"skip": true, "reason": "..."}` 扱い、本体生成しない
- 既に Python の validate.py で除外されているはずだが、念のため再チェック

### 3.2 出力スキーマ（card_analyze.md §出力スキーマ準拠）
```json
{
  "id": "<item.id>",
  "url": "<item.url>",
  "source_name": "<item.source_name>",
  "layer": "L1|L2",
  "published_at": "YYYY-MM-DD",
  "fact": "ファクト 3-4 行、ですます調、事実のみ",
  "context_analysis": "背景考察 4-5 行、業界構造レベルまで（社会構造に踏み込まない D-03）、情報タイプに本文中で言及",
  "impact": "実務への影響 3-4 行、断定せず（〜の余地があります）、個人名呼びかけ禁止",
  "topic": "ai_agents|automation|dx_cases|other",
  "importance": "high|mid|low",
  "info_type": "vendor_announcement|success_case|failure|critic|tech_validation|market|essay|historical",
  "source_type": "一次|業界メディア|個人ブログ|学術|書籍・論考"
}
```

### 3.3 図解の付与（D-40 §11.5）

ロジック構造を持つ要素は `diagram_fact` / `diagram_context` / `diagram_impact` に
HTML を埋める。テンプレは `site/assets/style.css` §12.12-15 を参照:
- `.diagram-flow`（順序）/ `.diagram-stat`（数値強調）
- `.diagram-compare`（2 列対比）/ `.diagram-pivot`（旧 → 新）
- `.diagram-bullets`（番号付き要点）/ `.diagram-timeline`（時系列）

**装飾目的の図は禁止**（DO_NOTS、D-40 ガードレール）。データなき定量グラフ NG。

### 3.4 DO_NOTS 厳守
- 陳腐な類推禁止（D-18）
- ベンダー PR 無批判引用禁止（D-09、背景考察で「ベンダー発表で第三者検証なし」等明示）
- バズワード結論禁止
- 個別カードに社会的意味を書かない（D-03）
- アクション自動生成禁止（D-02）
- 個人名呼びかけ禁止（D-30）
- 陳腐インフォグラフィクス禁止（D-40）

### 3.5 ですます調統一（D-36）

すべての本文をですます調で。情緒的評価語禁止、迎合表現禁止。

---

## 4. カード JSON を保存

```python
# 全 cards を 1 つの JSON 配列で保存
data/processed/cards/{today}.json
```

skip 判定された item は cards 配列に含めない（その分 20 件未満になる可能性あり）。

---

## 5. サイトビルド

```bash
python -m src.build_site
```

`site/index.html`（最新デイリー）と `site/weekly/index.html`（実装済の場合は実データ、
未実装ならダミー維持）が更新される。

---

## 6. self-critique 8 項目（CLAUDE.md §UI/視覚要素 self-critique）

UI/視覚に変化がない日は流して良いが、図解が新規に入った日は最低限:
- ページ URL から sub-resource が解決するか（curl で確認）
- 480px render での破綻がないか（mental check）
- 図解が装飾目的でないか

問題があれば `blockers.md` に記録、push 前に修正。

---

## 7. git commit & push

```bash
cd C:\Users\Takumi\dev\news-dashboard
git add data/processed/ data/rejected/ site/index.html site/weekly/index.html
git status
git commit -m "daily: {today_iso}"
git push origin main
```

push 成功で GitHub Pages の deploy_pages.yml が起動 → 公開サイト更新。

---

## 8. 失敗時の処理

途中でエラーが出たら:
- **push しない**（中途半端な状態を公開しない）
- 親プロジェクト `00_admin/steering/{phase}/blockers.md` にエラー記録
- 親プロジェクト `00_admin/tasks/lessons.md` に教訓を追記検討
- 当該 raw データは `data/raw/` に残るので翌日リカバリ可能
- `ScheduleWakeup` で次回平日 7:00 JST に再開

---

## 9. 次回スケジューリング

`ScheduleWakeup` で **次の平日 7:00 JST** を計算して再開予約:
- 月-木 → 翌日 7:00 JST
- 金 → 翌週月曜 7:00 JST（土日スキップ）
- 平日扱いの祝日もスキップ判定（祝日カレンダーは Phase 5 検討、当面 weekday() のみで判定）

`prompt` には `<<autonomous-loop-dynamic>>` センチネル渡し（autonomous /loop モード）。
`reason` 例: 「次の平日 7:00 JST に daily pipeline 起動」。

---

## 注意

- 環境変数 `ANTHROPIC_API_KEY` は **不要**（D-41、Pro/Max OAuth で動作）
- `.env` 配置 **不要**
- `src/analyze.py` は deprecated、本フローでは未使用
- 親プロジェクト USER_CONTEXT を読む際は `G:\マイドライブ\...` 経由（`--add-dir` で許可されている前提）
