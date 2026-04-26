# Deep Research Prompt — Sunday 22:00 JST 起床手順書

`/loop` セッションが日曜 22:00 JST に `ScheduleWakeup` で起床した時の自己実行手順。

親プロジェクト (`G:\マイドライブ\匠\テクノロジー\20260418_claude_autonews`) は
`--add-dir` で参照可能。

---

## 0. 当日判定

日曜 22:00 JST であることを確認:

```bash
python -c "from datetime import datetime; n=datetime.now(); print(n.isoformat(), n.weekday(), n.hour)"
```

`weekday()=6` （日曜）かつ `hour>=22` でなければ §6 次回スケジューリングへ。

---

## 1. 問い読込

```bash
cd C:\Users\Takumi\dev\news-dashboard
cat config/inquiries.yaml
```

各 inquiry について以下を実行（同時 3 本まで、D-12）:

---

## 2. 各 inquiry のディープリサーチ

### 2.1 前回レポート読込
- `data/reports/{inquiry_id}/latest.md` があれば内容を保持
- 初回は前回 None 扱い

### 2.2 プロンプト適用
- `config/prompts/deep_research.md` を Read
- `{{USER_CONTEXT}}` を親プロジェクト USER_CONTEXT.md §6 で置換
- inquiry エントリと previous_report をペイロードに

### 2.3 反復リサーチ
- `WebSearch` でサブ問いを検索
- `WebFetch` で一次ソース取得
- `depth` パラメータに応じて反復数を制御:
  - shallow: 最大 8 反復
  - medium: 最大 12 反復
  - deep: 最大 20 反復
- 派生サブ問いが出たら掘り下げる

### 2.4 レポート生成
- `deep_research.md` の出力スキーマに従い Markdown 生成
- 不確実性を必ず明示
- DO_NOTS 準拠（陳腐類推禁止、ベンダー PR 無批判禁止、限界独立段落必須）

### 2.5 保存
```bash
data/reports/{inquiry_id}/{YYYY-MM-DD}.md   # 本日分
data/reports/{inquiry_id}/latest.md         # 最新へのコピー（symlink ではなくファイルコピー、Windows 互換性のため）
```

---

## 3. サイトビルド

```bash
python -m src.build_site
```

`/inquiries/` インデックスと各 `/inquiries/{id}/latest.html` `/inquiries/{id}/archive.html` が更新される。

---

## 4. self-critique

- ですます調統一（D-36）
- 陳腐類推がないか
- 不確実性が明示されているか
- 限界段落があるか
- 出典 URL がすべて記録されているか
- マスターの中心テーマ（ワクワクする業務 / 業務革新）と接続しているか

問題ありなら push 前に修正、不可なら `blockers.md` 記録。

---

## 5. git commit & push

```bash
git add data/reports/ site/inquiries/
git commit -m "deep research: $(date +%Y-%m-%d)"
git push origin main
```

---

## 6. 次回スケジューリング

`ScheduleWakeup` で **次の日曜 22:00 JST**:
- prompt: `<<autonomous-loop-dynamic>>`
- reason: 「次の日曜 22:00 JST に deep research 起動」

---

## 注意

- 反復回数が `max-iterations` 上限に達したら、現状の知見でレポート生成して終了（無限ループ防止）
- 1 inquiry あたりの実時間が長い（30-120 分）ため、他のスケジュール（平日 daily / weekly）と衝突しないよう開始時刻を調整
- 失敗時は前回レポートを残す（次週リトライで上書き可能）
