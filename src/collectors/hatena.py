"""Hatena Bookmark collector for L1.

はてブ hotentry / entrylist RSS を feedparser で解析する。
各 entry の hatena:bookmarkcount 名前空間にブックマーク数（人気度シグナル）が入る。

sources.yaml の type: `hatena_hotentry` or `hatena_entrylist` がこのモジュールにディスパッチされる。
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
    """feedparser の struct_time から ISO 8601 (YYYY-MM-DD) を返す。欠落・不正は None。"""
    if not struct_time:
        return None
    try:
        dt = datetime(*struct_time[:6], tzinfo=timezone.utc)
        return dt.date().isoformat()
    except (TypeError, ValueError):
        return None


def fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch Hatena Bookmark RSS and return a list of RawItem dicts.

    期待する source フィールド:
      - id:    'hatena_it_hotentry' | 'hatena_it_entrylist'
      - url:   'https://b.hatena.ne.jp/hotentry/it.rss'
      - layer: 'L1'
      - name:  表示名
    """
    resp = httpx.get(
        source["url"],
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    collected_at = datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []
    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue

        published = _iso_date_or_none(entry.get("published_parsed")) or _iso_date_or_none(
            entry.get("updated_parsed")
        )

        raw_popularity: dict[str, Any] | None = None
        bookmarkcount = entry.get("hatena_bookmarkcount")
        if bookmarkcount is not None:
            try:
                raw_popularity = {"hatebu_users": int(bookmarkcount)}
            except (TypeError, ValueError):
                pass

        items.append(
            {
                "id": _make_id(source["id"], url),
                "source_id": source["id"],
                "source_name": source.get("name"),
                "source_type": "コミュニティ集約",
                "layer": source.get("layer", "L1"),
                "title": (entry.get("title") or "").strip(),
                "summary": (entry.get("summary") or "").strip(),
                "content": None,  # Hatena RSS は本文を含まない
                "url": url,
                "published_at": published,  # None の場合、validate.py が skip 扱い（D-37）
                "raw_popularity_signal": raw_popularity,
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
