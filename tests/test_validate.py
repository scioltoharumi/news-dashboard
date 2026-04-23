"""validate.py のユニットテスト。

DOMAIN_RULES.md §9.5 のテスト観点に対応。
"""
from __future__ import annotations

from datetime import date

from src.validate import validate_for_scope


# Reference: 2026-04-22 (水曜) を「今日」とする。ISO 週 17, 年 2026。
TODAY = date(2026, 4, 22)


def test_accepted_same_day():
    item = {"published_at": "2026-04-22"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is True and reason == ""


def test_missing_published_at():
    ok, reason = validate_for_scope({}, "daily", today=TODAY)
    assert ok is False and reason == "missing_published_at"


def test_none_published_at():
    ok, reason = validate_for_scope({"published_at": None}, "daily", today=TODAY)
    assert ok is False and reason == "missing_published_at"


def test_empty_string_published_at():
    ok, reason = validate_for_scope({"published_at": ""}, "daily", today=TODAY)
    assert ok is False and reason == "missing_published_at"


def test_invalid_iso_year_month_only():
    # "2026-02" は年月のみで ISO 8601 (YYYY-MM-DD) 不完全 → invalid
    item = {"published_at": "2026-02"}
    ok, reason = validate_for_scope(item, "weekly", today=TODAY)
    assert ok is False and reason == "invalid_iso8601"


def test_invalid_iso_japanese_text():
    # "2026 春" のような曖昧表記
    item = {"published_at": "2026 春"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is False and reason == "invalid_iso8601"


def test_future_date():
    item = {"published_at": "2026-05-01"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is False and reason == "future_date"


def test_weekly_out_of_week_previous():
    # ISO 週 17 の前週 = ISO 週 16（2026-04-13〜2026-04-19）
    item = {"published_at": "2026-04-15"}
    ok, reason = validate_for_scope(item, "weekly", today=TODAY)
    assert ok is False and reason == "out_of_week"


def test_weekly_same_week_accepted():
    # ISO 週 17 の月曜 2026-04-20
    item = {"published_at": "2026-04-20"}
    ok, reason = validate_for_scope(item, "weekly", today=TODAY)
    assert ok is True and reason == ""


def test_daily_7_days_ago_accepted():
    # 7 日前ちょうどは採用（境界テスト）
    item = {"published_at": "2026-04-15"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is True and reason == ""


def test_daily_8_days_ago_rejected():
    item = {"published_at": "2026-04-14"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is False and reason == "too_old_for_daily"


def test_daily_10_days_ago_rejected():
    item = {"published_at": "2026-04-12"}
    ok, reason = validate_for_scope(item, "daily", today=TODAY)
    assert ok is False and reason == "too_old_for_daily"


def test_l34_no_week_constraint():
    # L3/L4 は長期素材のため週範囲制約なし（未来日付のみ NG）
    item = {"published_at": "2025-06-01"}
    ok, reason = validate_for_scope(item, "l34", today=TODAY)
    assert ok is True and reason == ""


def test_l34_future_still_rejected():
    item = {"published_at": "2026-05-01"}
    ok, reason = validate_for_scope(item, "l34", today=TODAY)
    assert ok is False and reason == "future_date"


def test_weekly_same_year_different_week_rejected():
    # 2026 年 ISO 週 15 は out_of_week（17 と違う週）
    item = {"published_at": "2026-04-06"}
    ok, reason = validate_for_scope(item, "weekly", today=TODAY)
    assert ok is False and reason == "out_of_week"
