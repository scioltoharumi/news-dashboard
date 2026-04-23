"""Generic RSS/Atom collector for L1/L2/L3.

feedparser でパースし、published_at を ISO 8601 (YYYY-MM-DD) に正規化する。
欠落は None を返し、スキップ判定は src/validate.py (D-37) が行う。

sources.yaml の type: `rss` がこのモジュールにディスパッチされる。
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

import feedparser
import httpx

USER_AGENT = "news-dashboard/0.1 (+https://github.com/scioltoharumi/news-dashboard)"


def _make_id(source_id: str, url: str) -> str:
    return sha1(f"{source_id}|{url}".encode("utf-8")).hexdigest()[:16]


def _iso_date_or_none(struct_time) -> str | None:
    if not struct_time:
        return None
    try:
        dt = datetime(*struct_time[:6], tzinfo=timezone.utc)
        return dt.date().isoformat()
    except (TypeError, ValueError):
        return None


def _extract_content(entry) -> str | None:
    """Atom <content> または <content:encoded> を取得。無ければ None。"""
    content_field = entry.get("content")
    if content_field and isinstance(content_field, list) and content_field:
        value = content_field[0].get("value")
        if value:
            return value
    return None


# sources.yaml の info_type → RawItem.source_type マッピング
_SOURCE_TYPE_MAP = {
    "industry_media": "業界メディア",
    "vendor_blog": "一次",
    "community_curated": "コミュニティ集約",
    "individual_blog": "個人ブログ",
    "academic": "学術",
    "long_form": "書籍・論考",
}


def fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch generic RSS/Atom feed and return a list of RawItem dicts.

    期待する source フィールド:
      - id:        'itmedia_news' 等
      - url:       feed URL
      - layer:     'L1' | 'L2' | 'L3'
      - type:      'rss'
      - name:      表示名
      - info_type: 'industry_media' 等（source_type 導出に使用）
    """
    resp = httpx.get(
        source["url"],
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    source_type = _SOURCE_TYPE_MAP.get(source.get("info_type", ""), "業界メディア")
    collected_at = datetime.now(timezone.utc).isoformat()

    items: list[dict[str, Any]] = []
    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue

        published = _iso_date_or_none(entry.get("published_parsed")) or _iso_date_or_none(
            entry.get("updated_parsed")
        )

        items.append(
            {
                "id": _make_id(source["id"], url),
                "source_id": source["id"],
                "source_name": source.get("name"),
                "source_type": source_type,
                "layer": source.get("layer", "L2"),
                "title": (entry.get("title") or "").strip(),
                "summary": (entry.get("summary") or "").strip(),
                "content": _extract_content(entry),
                "url": url,
                "published_at": published,
                "raw_popularity_signal": None,
                "collected_at": collected_at,
                "raw": {
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "published": entry.get("published"),
                    "updated": entry.get("updated"),
                },
            }
        )
    return items
