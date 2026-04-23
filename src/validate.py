"""Date validation (D-37) — 4層除外ロジック。

親プロジェクト `01_domain/DOMAIN_RULES.md` §9 の実装。
日付欠落・形式不正・未来日付・スコープ外のアイテムは UI に到達させない。

呼び出し側は除外理由をログ記録し、`data/rejected/{YYYY-MM-DD}.jsonl` に append する。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

Scope = Literal["daily", "weekly", "l34"]


def validate_for_scope(
    item: dict[str, Any],
    scope: Scope,
    today: date | None = None,
) -> tuple[bool, str]:
    """スコープ別の日付バリデーション。

    Args:
        item: `published_at` フィールドを持つ RawItem or Card。
        scope: 'daily' | 'weekly' | 'l34'。
        today: テスト用に今日を固定可能。None の場合は `date.today()`。

    Returns:
        (accepted: bool, reason: str)。
        accepted=True のとき reason は空文字列。
        False のとき reason は:
          - missing_published_at
          - invalid_iso8601
          - future_date
          - out_of_week    (weekly のみ)
          - too_old_for_daily (daily のみ)
    """
    today = today or date.today()
    date_str = item.get("published_at")
    if not date_str:
        return False, "missing_published_at"
    try:
        d = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return False, "invalid_iso8601"
    if d > today:
        return False, "future_date"
    if scope == "weekly":
        # ISO 年 + 週番号が一致する場合のみ採用
        if today.isocalendar()[:2] != d.isocalendar()[:2]:
            return False, "out_of_week"
    elif scope == "daily":
        if (today - d).days > 7:
            return False, "too_old_for_daily"
    # l34: 長期素材のため週制約なし
    return True, ""
