"""verify_prompt.py — プロンプト組立の検証（API 呼び出しなし）。

card_analyze.md に {{USER_CONTEXT}} を埋め込んだ最終 system prompt を生成し、
期待されるセクションがすべて含まれているかを確認する。

使い方:
  python scripts/verify_prompt.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

# Windows cp932 でも UTF-8 出力できるようにする
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.analyze import _build_system_prompt  # noqa: E402

EXPECTED_SECTIONS = [
    # USER_CONTEXT 由来
    ("読者文脈ヘッダ", "## 読者文脈"),
    ("業務革新コンサル", "業務革新コンサルタント"),
    ("中心テーマ ワクワク", "ワクワク"),
    ("進行中案件 顔認証", "顔認証ゲート"),
    # 文体指定 D-36
    ("ですます調指定", "ですます調"),
    # DO_NOTS 関連
    ("陳腐類推禁止", "陳腐な類推"),
    ("ベンダーPR批判", "ベンダー PR"),
    ("バズワード禁止", "バズワード"),
    ("社会的意味禁止", "社会構造"),
    # 日付バリデーション D-37
    ("日付バリデーション", "ISO 8601"),
    ("skip 規約", '"skip": true'),
    # 出力スキーマ
    ("3 ブロック構成", "fact"),
    ("topic field", "topic"),
    ("importance field", "importance"),
    ("info_type field", "info_type"),
    # アイコンマッピング
    ("info_type -> icon マッピング", "icon-vendor"),
    # モデル指定
    ("モデル sonnet-4-6", "claude-sonnet-4-6"),
]


def main() -> int:
    prompt = _build_system_prompt()
    print(f"=== Rendered prompt: {len(prompt)} bytes ===\n")

    failures = []
    for label, needle in EXPECTED_SECTIONS:
        ok = needle in prompt
        mark = "OK" if ok else "NG"
        print(f"  [{mark}] {label}: {needle!r}")
        if not ok:
            failures.append(label)

    print()
    if failures:
        print(f"FAIL: {len(failures)} 項目が見つかりません: {failures}")
        return 1
    print(f"ALL {len(EXPECTED_SECTIONS)} CHECKS PASS")
    print("\n--- prompt head (first 500 chars) ---")
    print(prompt[:500])
    print("\n--- prompt tail (last 500 chars) ---")
    print(prompt[-500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
