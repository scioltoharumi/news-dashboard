"""Context loader — 親プロジェクトの USER_CONTEXT.md から §6 読者文脈テンプレートを読み込む。

SSoT 原則: 実装リポには `docs/` を作らず、設計・規約の正は親プロジェクト（Google Drive）。
このモジュールは `01_domain/USER_CONTEXT.md` §6 の「プロンプトへの組み込み方針」テンプレ
（コードブロック内の `## 読者文脈` 以下）を抽出し、プロンプトの `{{USER_CONTEXT}}` プレースホルダに埋め込む。
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

# 親プロジェクトのデフォルトパス（環境変数 NEWS_DASHBOARD_DOCS_ROOT で上書き可能）
_DEFAULT_DOCS_ROOT = r"G:\マイドライブ\匠\テクノロジー\20260418_claude_autonews"


def _docs_root() -> Path:
    return Path(os.environ.get("NEWS_DASHBOARD_DOCS_ROOT", _DEFAULT_DOCS_ROOT))


def _user_context_path() -> Path:
    return _docs_root() / "01_domain" / "USER_CONTEXT.md"


@lru_cache(maxsize=1)
def load_user_context() -> str:
    """USER_CONTEXT.md §6 内の `## 読者文脈` コードブロックを抽出して返す。

    §6 の本文中に ```で囲まれたテンプレートがあり、その中身を取り出す。
    見つからない場合は ValueError を送出（プロンプト組込時に早期失敗させるため）。
    """
    path = _user_context_path()
    if not path.exists():
        raise FileNotFoundError(
            f"USER_CONTEXT.md が見つかりません: {path}  "
            f"環境変数 NEWS_DASHBOARD_DOCS_ROOT で親プロジェクトパスを指定してください"
        )
    text = path.read_text(encoding="utf-8")

    # §6 以降を切り出し
    m = re.search(r"^## 6\. プロンプトへの組み込み方針", text, re.MULTILINE)
    if not m:
        raise ValueError("USER_CONTEXT.md に §6 が見つかりません")
    section = text[m.end():]

    # 最初のコードブロック（```...```）を抽出
    code_match = re.search(r"```\s*\n(.*?)^```", section, re.DOTALL | re.MULTILINE)
    if not code_match:
        raise ValueError("USER_CONTEXT.md §6 内の ``` コードブロックが見つかりません")

    context_text = code_match.group(1).strip()
    if "読者文脈" not in context_text:
        raise ValueError("抽出したコードブロックに『読者文脈』見出しが含まれません")
    return context_text


def render_prompt(prompt_template: str) -> str:
    """`{{USER_CONTEXT}}` を USER_CONTEXT.md §6 のテンプレートで置換。

    他のプレースホルダ（今後追加の可能性）は将来拡張。
    """
    context = load_user_context()
    return prompt_template.replace("{{USER_CONTEXT}}", context)
