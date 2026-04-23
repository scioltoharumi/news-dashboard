"""Dedup — URL 正規化とタイトル 5-gram Jaccard で重複排除。

親プロジェクト `01_domain/DOMAIN_RULES.md` §4 の実装。
- URL: canonical 正規化（トラッキング系クエリパラメータを除去）
- タイトル: 5-gram Jaccard >= 0.8 で同一記事候補
- 同一候補が複数ソースで見つかった場合、popularity 最大のソースを代表に採用
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# トラッキング/アナリティクス系クエリパラメータ（URL 正規化時に除去）
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "yclid",
    "ref",
    "ref_src",
    "ref_url",
    "_ga",
    "_gl",
    "mc_cid",
    "mc_eid",
}


def canonical_url(url: str) -> str:
    """URL を正規化。スキーム小文字化、フラグメント除去、トラッキングパラメータ除去、末尾スラッシュ統一。"""
    if not url:
        return ""
    parsed = urlparse(url)
    # クエリパラメータのフィルタリング
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    new_query = urlencode(query_pairs)
    # パス末尾の "/" を取り除く（ただし root "/" は残す）
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # scheme / netloc は小文字化
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            "",  # fragment を捨てる
        )
    )


def _char_ngrams(text: str, n: int = 5) -> set[str]:
    """文字 n-gram の集合。空白正規化済み。"""
    if not text:
        return set()
    normalized = "".join(text.split())  # 空白類を全て除去
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def title_jaccard(title_a: str, title_b: str, n: int = 5) -> float:
    """2 つのタイトルの文字 n-gram Jaccard 類似度。"""
    a = _char_ngrams(title_a, n)
    b = _char_ngrams(title_b, n)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _popularity_key(item: dict[str, Any]) -> int:
    pop = item.get("raw_popularity_signal") or {}
    return int(pop.get("hatebu_users") or 0)


def dedup(
    items: list[dict[str, Any]],
    title_threshold: float = 0.8,
) -> list[dict[str, Any]]:
    """重複排除。

    1. canonical URL が同じアイテム → popularity 最大を残す
    2. タイトル 5-gram Jaccard >= threshold → popularity 最大を残す

    入力順は保持しない（代表選択の都合）。出力は popularity 降順 + canonical url 昇順。
    """
    if not items:
        return []

    # Phase 1: canonical URL でグループ化、各グループで popularity 最大を代表
    by_url: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        key = canonical_url(it.get("url", ""))
        by_url.setdefault(key, []).append(it)
    url_deduped = [max(group, key=_popularity_key) for group in by_url.values()]

    # Phase 2: タイトル類似度でさらに merge
    representatives: list[dict[str, Any]] = []
    for candidate in url_deduped:
        merged = False
        for i, rep in enumerate(representatives):
            if title_jaccard(candidate.get("title", ""), rep.get("title", "")) >= title_threshold:
                # より popularity が高い方を代表に差し替える
                if _popularity_key(candidate) > _popularity_key(rep):
                    representatives[i] = candidate
                merged = True
                break
        if not merged:
            representatives.append(candidate)

    # popularity 降順 + url 昇順でソート
    representatives.sort(
        key=lambda it: (-_popularity_key(it), canonical_url(it.get("url", "")))
    )
    return representatives
