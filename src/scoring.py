"""Scoring — L1/L2 収集アイテムの注目度スコアとトピック分類。

親プロジェクト `01_domain/DOMAIN_RULES.md` §1, §3 の実装。

score = freshness * 0.5 + popularity * 0.5 + keyword_match * 0.1
- freshness: 発行からの経過時間（1 週間で線形減衰）
- popularity: 人気度シグナル（はてブ users 数等）を log-scale で正規化
- keyword_match: tracks.yaml キーワード辞書とのマッチ度

トピック分類: tracks.yaml の 4 トラック（ai_agents / automation / dx_cases / other）のうち、
キーワードマッチ数が最大のトラックを採用。マッチなしなら `other`。
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any


def compute_freshness(published_at: str | None, now: datetime | None = None) -> float:
    """発行からの経過時間ベースの鮮度（0.0 〜 1.0）。

    max(0, 1 - hours_since_pub / 168)。1 週間で 0 に線形減衰。
    """
    if not published_at:
        return 0.0
    try:
        d = date.fromisoformat(published_at)
    except (TypeError, ValueError):
        return 0.0
    now = now or datetime.now(timezone.utc)
    pub_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    hours = (now - pub_dt).total_seconds() / 3600.0
    if hours < 0:
        return 1.0  # 未来日付は上限（validate.py 側で除外されるはず）
    return max(0.0, 1.0 - hours / 168.0)


def compute_popularity(raw_popularity_signal: dict[str, Any] | None) -> float:
    """人気度シグナルを 0.0 〜 1.0 に正規化。

    はてブ users を log10 ベースで正規化:
      1 user -> 0.0
      10 users -> 約 0.33
      100 users -> 約 0.67
      1000 users -> 1.0（上限）
    """
    if not raw_popularity_signal:
        return 0.0
    users = raw_popularity_signal.get("hatebu_users") or 0
    if users <= 0:
        return 0.0
    normalized = math.log10(users + 1) / 3.0  # log10(1001) ≈ 3.0
    return min(1.0, max(0.0, normalized))


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """テキストに含まれるキーワードの個数。大文字小文字無視。"""
    if not text:
        return 0
    lowered = text.lower()
    return sum(1 for kw in keywords if kw.lower() in lowered)


def compute_keyword_match(item: dict[str, Any], tracks: list[dict[str, Any]]) -> float:
    """全トラックのキーワード辞書に対する最大マッチ数を 0.0 〜 1.0 に正規化。

    マッチ数 0 -> 0.0
    マッチ数 5 以上 -> 1.0（上限）
    """
    haystack = f"{item.get('title', '')} {item.get('summary', '')} {item.get('content') or ''}"
    max_matches = 0
    for track in tracks:
        keywords = track.get("keywords", []) or []
        count = _count_keyword_matches(haystack, keywords)
        if count > max_matches:
            max_matches = count
    return min(1.0, max_matches / 5.0)


def classify_topic(item: dict[str, Any], tracks: list[dict[str, Any]]) -> str:
    """tracks.yaml のキーワードで最大マッチするトラック id を返す。マッチなしなら 'other'。"""
    haystack = f"{item.get('title', '')} {item.get('summary', '')} {item.get('content') or ''}"
    best_id = "other"
    best_count = 0
    for track in tracks:
        keywords = track.get("keywords", []) or []
        count = _count_keyword_matches(haystack, keywords)
        if count > best_count:
            best_count = count
            best_id = track["id"]
    return best_id


def score_item(
    item: dict[str, Any],
    tracks: list[dict[str, Any]],
    now: datetime | None = None,
) -> float:
    """アイテムの注目度スコア（0.0 〜 約 1.1）。"""
    freshness = compute_freshness(item.get("published_at"), now=now)
    popularity = compute_popularity(item.get("raw_popularity_signal"))
    keyword_match = compute_keyword_match(item, tracks)
    return freshness * 0.5 + popularity * 0.5 + keyword_match * 0.1


def classify_importance(score: float) -> str:
    """注目度スコア → importance 閾値マッピング（Phase 1 simple rule）。

    LLM 判定の `importance` とは別軸（注目度スコアは機械的）。
    最終的なカードの `importance` は LLM (analyze.py) が決定するが、
    Phase 1 では LLM 判定前の暫定分類としても使える。
    """
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "mid"
    return "low"
