"""Analyze — Claude API でカード JSON を生成する。

親プロジェクト `04_core/07_prompts_design.md` §2 実装。
- モデル: claude-sonnet-4-6（D-28）
- プロンプト: config/prompts/card_analyze.md（{{USER_CONTEXT}} は context_loader が差し込む）
- 出力: 3 ブロック (fact / context_analysis / impact) + topic / importance / info_type / source_type
- 日付不正/欠落: {"skip": true, "reason": "..."} として返る（LLM 側判定）
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.utils.context_loader import render_prompt

DEFAULT_MODEL = "claude-sonnet-4-6"  # D-28、§H で実在確認（BK1-02）
DEFAULT_MAX_TOKENS = 2048
DEFAULT_PROMPT_FILE = "config/prompts/card_analyze.md"


def _build_system_prompt(prompt_file: str | Path = DEFAULT_PROMPT_FILE) -> str:
    """プロンプトテンプレを読み、USER_CONTEXT を埋めたうえで system prompt として返す。"""
    template = Path(prompt_file).read_text(encoding="utf-8")
    return render_prompt(template)


def _build_user_message(item: dict[str, Any]) -> str:
    """Raw item を JSON string 化してユーザーメッセージに格納。"""
    payload = {
        "layer": item.get("layer"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "content": item.get("content"),
        "url": item.get("url"),
        "source_name": item.get("source_name"),
        "source_type": item.get("source_type"),
        "published_at": item.get("published_at"),
        "raw_popularity_signal": item.get("raw_popularity_signal"),
    }
    return (
        "以下の raw news item を分析し、カード JSON を生成してください。\n"
        "出力は JSON のみ。ファクト/背景考察/実務への影響の 3 ブロックを含めてください。\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """LLM 応答から JSON オブジェクトを抽出。``` でフェンスされている場合は剥がす。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        # コードフェンス開始行を剥がす
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def analyze_card(
    item: dict[str, Any],
    client: Anthropic | None = None,
    model: str = DEFAULT_MODEL,
    prompt_file: str | Path = DEFAULT_PROMPT_FILE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """1 件の raw item を Claude API に送り、カード JSON を返す。

    skip 判定の場合は {"skip": true, "reason": "..."} を返す。
    API エラーは例外として raise（呼び出し側でリトライ/ログ処理）。
    """
    client = client or Anthropic()
    system_prompt = _build_system_prompt(prompt_file)
    user_msg = _build_user_message(item)

    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    # 応答テキスト抽出
    text_parts = [block.text for block in resp.content if block.type == "text"]
    raw_text = "".join(text_parts)
    return _extract_json(raw_text)


def client_from_env() -> Anthropic:
    """環境変数 ANTHROPIC_API_KEY から Anthropic クライアントを生成。

    `.env` が配置されている場合は呼び出し側で事前に `load_dotenv()` しておくこと。
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY が未設定です。.env を読み込むか GitHub Secret 経由で供給してください。"
        )
    return Anthropic()
