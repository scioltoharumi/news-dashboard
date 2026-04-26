# Weekly Prep Prompt — 日曜 20:00 JST 起床手順書

`/loop` セッションが日曜 20:00 JST に `ScheduleWakeup` で起床した時の自己実行手順。
**L3 / L4 素材を集めて週次生成（月曜 6:00 JST）の準備を完了**させる。

---

## 0. 当日判定

```bash
python -c "from datetime import datetime; n=datetime.now(); print(n.isoformat(), n.weekday(), n.hour)"
```

`weekday()=6` 日曜かつ `hour>=20` でなければ §6 へ。

---

## 1. L3 長文論考の収集

```bash
cd C:\Users\Takumi\dev\news-dashboard
python -m src.pipeline.weekly_prep --layer L3
```

これにより `sources.yaml` の `layer: L3` ソース（東洋経済 / Aeon / The Atlantic 等）から
今週分のエントリが `data/raw/l3-{YYYY-WNN}.jsonl` に保存される。

---

## 2. L4 動的発見（CC 主導の能動探索）

`config/prompts/liberal_arts_extract.md` を参照しながら、以下を実行:

### 2.1 今週のテーマ抽出

`data/processed/cards/*.json` の今週分（ISO 週で当週のもの）を Read。
中心テーマを 1-2 個特定（例: "AI 代替の職業不安", "ベンダー言説と現場感覚の乖離"）。

### 2.2 4 分野での能動探索（D-08）

各分野で WebSearch + WebFetch:

| 分野 | 探索軸の例 |
|---|---|
| 歴史・人類学 | 技術史、産業革命、経済史、制度の変遷、労働史 |
| 文学・批評 | 現代文学論、SF 批評、長文エッセイ |
| 精神医学・心理学 | AI 時代の認知・感情・自己意識の変容 |
| 社会学・経営学 | 組織論、労働社会学、制度派経済学 |

抽出したテーマと **構造的に接続しうる** 書籍・論考・歴史事例・心理学研究を能動検索。

### 2.3 1 分野あたり最大 3 件

合計 4 分野 × 3 件 = **最大 12 件** を素材プールとしてストック:
```
data/raw/l4-{YYYY-WNN}/{domain}-{slug}.json
```

---

## 3. AnalogyMaterial 抽出

各 L3 / L4 素材について `config/prompts/liberal_arts_extract.md` を適用し、
AnalogyMaterial JSON を生成:
```
data/liberal_arts/{YYYY-WNN}/{source-slug}.json
```

`confidence: low` のものは Part 3 では使わない（陳腐類推回避、D-18）。

---

## 4. 週次選抜 + キャッシュ

```bash
python -m src.pipeline.weekly_prep --aggregate
```

L1/L2 の今週分カード（`data/processed/cards/{date}.json` 月-金分）を
1 つの `data/processed/week-{YYYY-WNN}.json` に集約。
Part 1/2/3 生成時に読込。

---

## 5. git commit & push

```bash
git add data/raw/l3-* data/raw/l4-* data/liberal_arts/ data/processed/week-*
git commit -m "weekly prep: $(date +%Y-W%V)"
git push origin main
```

site の更新はないため Pages デプロイは走らない。

---

## 6. 次回スケジューリング

`ScheduleWakeup` で **次の月曜 6:00 JST**（同週、約 10 時間後）:
- prompt: `<<autonomous-loop-dynamic>>`
- reason: 「同週月曜 6:00 JST に weekly_generate 起動」

---

## 注意

- WebFetch / WebSearch の使用は CC 内蔵ツール経由（API キー不要）
- 素材プール 12 件はあくまで上限、構造的接続が薄ければ少なくて良い
- 失敗時は前週素材を流用、`blockers.md` 記録
