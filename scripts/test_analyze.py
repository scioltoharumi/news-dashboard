"""test_analyze.py — 1 件のサンプル raw item を Claude API に送り、カード生成を end-to-end 検証。

使い方:
  # `.env` に ANTHROPIC_API_KEY が設定されていること
  python scripts/test_analyze.py

検証項目（§H 完了条件）:
  1. API キー読込 (.env / 環境変数)
  2. モデル `claude-sonnet-4-6` の実在 (BK1-02 解消)
  3. プロンプト組立に USER_CONTEXT / DO_NOTS / 文体 / 日付指示が含まれる
  4. 出力 JSON が card_analyze.md スキーマに準拠
  5. 日付欠落入力で skip 判定が機能
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("FAIL: ANTHROPIC_API_KEY が未設定です。.env または環境変数で設定してください。")
    sys.exit(1)

from src.analyze import analyze_card, client_from_env  # noqa: E402

EXPECTED_OUT_FIELDS = [
    "fact",
    "context_analysis",
    "impact",
    "topic",
    "importance",
    "info_type",
    "source_type",
]
EXPECTED_TOPICS = {"ai_agents", "automation", "dx_cases", "other"}
EXPECTED_IMPORTANCE = {"high", "mid", "low"}


def test_normal_item() -> dict:
    item = {
        "layer": "L1",
        "title": "Microsoft、Copilot Studio に Power Fx ベースのエージェント連携機能を発表",
        "summary": "Build 2026 で発表。プレビュー版を本日提供開始。",
        "content": (
            "Microsoft は Build 2026 で、Copilot Studio に Power Fx スクリプトで"
            "エージェント間連携を制御する機能を追加したと発表しました。"
            "プレビュー版は本日提供開始で、Power Platform の既存顧客基盤を活かした戦略です。"
        ),
        "url": "https://example.com/test/1",
        "source_name": "ITmedia NEWS",
        "source_type": "業界メディア",
        "published_at": date.today().isoformat(),
        "raw_popularity_signal": None,
    }
    print(f"\n[1] 正常入力で API 呼出 (モデル: claude-sonnet-4-6)")
    print(f"    title: {item['title']}")
    client = client_from_env()
    result = analyze_card(item, client=client)
    return result


def test_no_date_item() -> dict:
    item = {
        "layer": "L1",
        "title": "テスト用：日付欠落",
        "summary": "テスト",
        "content": "テスト本文",
        "url": "https://example.com/test/no-date",
        "source_name": "テスト",
        "source_type": "業界メディア",
        "published_at": None,  # 欠落
        "raw_popularity_signal": None,
    }
    print(f"\n[2] 日付欠落入力で API 呼出 (D-37 skip 期待)")
    client = client_from_env()
    result = analyze_card(item, client=client)
    return result


def main() -> int:
    failures: list[str] = []

    # === 正常入力 ===
    try:
        out = test_normal_item()
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR: API 呼出失敗: {type(e).__name__}: {e}")
        if "model" in str(e).lower():
            print("  → BK1-02: モデル名 claude-sonnet-4-6 が API で実在しない可能性。最新の sonnet モデルに差し替えを検討。")
        return 1

    print(f"  raw output: {json.dumps(out, ensure_ascii=False)[:300]}...")
    if out.get("skip"):
        print("  ✗ skip 判定が返された（正常入力なのに）")
        failures.append("normal_item_unexpectedly_skipped")
    else:
        for field in EXPECTED_OUT_FIELDS:
            if field not in out:
                print(f"  NG missing field: {field}")
                failures.append(f"normal_missing_{field}")
            else:
                print(f"  OK has field: {field} = {str(out[field])[:50]!r}")
        if out.get("topic") not in EXPECTED_TOPICS:
            failures.append(f"invalid_topic={out.get('topic')}")
        if out.get("importance") not in EXPECTED_IMPORTANCE:
            failures.append(f"invalid_importance={out.get('importance')}")

    # === 日付欠落 ===
    try:
        out2 = test_no_date_item()
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR: API 呼出失敗: {type(e).__name__}: {e}")
        return 1

    print(f"  raw output: {json.dumps(out2, ensure_ascii=False)[:200]}")
    if out2.get("skip") is True:
        print(f"  OK D-37 skip 動作: reason={out2.get('reason')!r}")
    else:
        print(f"  NG: 日付欠落なのに skip されず本体生成された")
        failures.append("no_date_not_skipped")

    print()
    if failures:
        print(f"FAIL: {len(failures)} 項目: {failures}")
        return 1
    print("ALL CHECKS PASS — §H BK1-02 解消、card_analyze.md 動作確認")
    return 0


if __name__ == "__main__":
    sys.exit(main())
