# liberal_arts_extract.md — L4 素材から AnalogyMaterial 抽出

## System

L3/L4 のソース 1 件（書籍要約 / 論考 / エッセイ等）を入力に、ウィークリー Part 3 のアナロジーで使える **AnalogyMaterial JSON** を生成します。

{{USER_CONTEXT}}

---

## 入力

```yaml
source: "媒体名・著者・年"
domain: "history | literature | psychology | sociology"
title: "素材のタイトル"
content: "本文（切り詰めあり）"
```

---

## 出力（JSON 固定）

```json
{
  "summary": "内容の 3-5 行要約、ですます調",
  "extracted_patterns": [
    "抽出できる構造パターン（例: 『専門職の陳腐化』『制度の正統性危機』『境界仕事の交渉』）"
  ],
  "potential_analogies": [
    {
      "modern_phenomenon": "現代の IT/DX/AI で何に類推できそうか",
      "structural_similarity": "構造的類似点を具体的に言語化",
      "confidence": "high|medium|low"
    }
  ],
  "keywords": ["使えそうな概念・キーワード"],
  "direct_quotes": [
    "引用可能な印象的な文（出典明記）"
  ]
}
```

---

## 設計のポイント

- 安易な類推は `confidence: low` に下げる
- 「AI 革命は産業革命と同じ」レベルの陳腐類推は `confidence: low`
- 一見無関係な事例から思わぬ類推が引けるケースを優先
- マスター中心テーマ（業務革新・ワクワクする働き方）への構造的接続が見える素材を高評価
- 引用は出典明記（書籍ページ / 論文 DOI / 記事 URL）

---

## モデル

`/loop` 実行下で Claude Code（Pro/Max）が担当。
