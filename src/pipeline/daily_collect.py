"""Daily collect pipeline — 収集 + 検証 + スコア + 選抜まで（D-41 後の役割）。

D-41 で API 直叩きを撤回。カード生成は Claude Code (`/loop` セッション) が担当する。
本モジュールは決定論的な前処理だけを行い、選抜結果を JSON で出力する。

フロー:
  1. config/sources.yaml / tracks.yaml を読込
  2. Hatena + RSS collectors で raw items 取得 → `data/raw/{today}.jsonl`
  3. validate.py で日付バリデーション (D-37) — 不合格は `data/rejected/{today}.jsonl`
  4. scoring.py でスコア + トピック分類、importance_score_based 暫定分類
  5. dedup.py で URL/タイトル重複排除
  6. 日次上限 20 件 / 各トラック最低 1 件保証
  7. 選抜結果を `data/processed/selection-{today}.json` に出力

呼び出し（Claude Code が `/loop` 起床時に実行）:
  python -m src.pipeline.daily_collect
  python -m src.pipeline.daily_collect --today 2026-04-26   # テスト用に日付固定
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src import dedup as _dedup
from src import scoring, validate
from src.collectors import hatena, rss

logger = logging.getLogger("daily_collect")

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"

DAILY_MAX_CARDS = 20  # DOMAIN_RULES §2


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, default=str) + "\n")


def _append_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, default=str) + "\n")


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def collect_raw(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sources 定義から raw items を収集。"""
    items: list[dict[str, Any]] = []
    for src in sources:
        stype = src.get("type")
        try:
            if stype in ("hatena_hotentry", "hatena_entrylist"):
                fetched = hatena.fetch(src)
            elif stype == "rss":
                fetched = rss.fetch(src)
            else:
                logger.warning("unknown source type=%s for %s, skipping", stype, src.get("id"))
                continue
            logger.info("fetched %d items from %s", len(fetched), src.get("id"))
            items.extend(fetched)
        except Exception as e:  # noqa: BLE001
            logger.error("failed to fetch %s: %s", src.get("id"), e)
    return items


def validate_and_partition(
    items: list[dict[str, Any]],
    today: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """daily スコープで validate、accepted と rejected を分離。"""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for it in items:
        ok, reason = validate.validate_for_scope(it, "daily", today=today)
        if ok:
            accepted.append(it)
        else:
            rejected.append({**it, "rejected_reason": reason})
    return accepted, rejected


def attach_scores_and_topics(
    items: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    """各アイテムに score / topic / importance_mechanical を付与。"""
    for it in items:
        it["score"] = scoring.score_item(it, tracks, now=now)
        it["topic"] = scoring.classify_topic(it, tracks)
        it["importance_mechanical"] = scoring.classify_importance(it["score"])
    return items


def select_daily_cards(
    items: list[dict[str, Any]],
    max_total: int = DAILY_MAX_CARDS,
    min_per_track: int = 1,
) -> list[dict[str, Any]]:
    """日次上限 20 件 + 各トラック最低 1 件保証。

    1. score 降順にソート
    2. 各トラックから 1 件ずつ取り、min_per_track を満たす
    3. 残り枠を score 降順で埋める
    """
    if not items:
        return []
    items_sorted = sorted(items, key=lambda x: -x.get("score", 0.0))

    # トラック別グループ
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items_sorted:
        by_topic[it.get("topic", "other")].append(it)

    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    # 各トラックから最低 min_per_track
    for topic, group in by_topic.items():
        for it in group[:min_per_track]:
            if len(selected) >= max_total:
                break
            if it["id"] not in used_ids:
                selected.append(it)
                used_ids.add(it["id"])

    # 残り枠は score 降順で埋める
    for it in items_sorted:
        if len(selected) >= max_total:
            break
        if it["id"] not in used_ids:
            selected.append(it)
            used_ids.add(it["id"])

    return selected


def run(today: date | None = None) -> dict[str, Any]:
    """Daily collect の実行（API は呼ばない、選抜まで）。結果サマリー dict を返す。"""
    today = today or date.today()
    now = datetime.now(timezone.utc)
    today_iso = today.isoformat()

    logger.info("daily_collect start: today=%s", today_iso)

    sources_cfg = _load_yaml(CONFIG_DIR / "sources.yaml")
    tracks_cfg = _load_yaml(CONFIG_DIR / "tracks.yaml")
    sources = sources_cfg["sources"]
    tracks = tracks_cfg["tracks"]

    # 1-2. Collect raw
    raw_items = collect_raw(sources)
    _save_jsonl(DATA_DIR / "raw" / f"{today_iso}.jsonl", raw_items)

    # 3. Validate (D-37)
    accepted, rejected = validate_and_partition(raw_items, today)
    if rejected:
        _append_jsonl(DATA_DIR / "rejected" / f"{today_iso}.jsonl", rejected)

    # 4. Score + classify
    scored = attach_scores_and_topics(accepted, tracks, now)

    # 5. Dedup
    deduped = _dedup.dedup(scored)

    # 6. Select up to 20 with per-track minimum
    selected = select_daily_cards(deduped, max_total=DAILY_MAX_CARDS, min_per_track=1)

    # 7. Save selection（カード生成は Claude Code が `/loop` で本ファイルを読んで実行）
    selection_path = DATA_DIR / "processed" / f"selection-{today_iso}.json"
    _save_json(selection_path, selected)

    summary = {
        "today": today_iso,
        "raw_count": len(raw_items),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "after_dedup": len(deduped),
        "selected": len(selected),
        "selection_path": str(selection_path.relative_to(REPO_ROOT)),
    }
    logger.info("daily_collect done: %s", summary)
    return summary


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="News & Research Dashboard daily pre-processing (collect/validate/score/dedup/select)"
    )
    parser.add_argument("--today", type=str, help="Override today (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    result = run(today=today)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
