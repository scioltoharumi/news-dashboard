"""Weekly prep — L3 RSS 収集 + 週次集約（D-41 後の役割）。

L4 動的発見と素材抽出（liberal_arts_extract）は CC が `/loop` 内で実行する。
本モジュールは決定論的な前処理だけ:
  --layer L3  : L3 ソースから今週分を取得 → data/raw/l3-{YYYY-WNN}.jsonl
  --aggregate : 今週の L1/L2 cards を集約 → data/processed/week-{YYYY-WNN}.json

呼び出し（CC が `weekly_prep_prompt.md` 手順内で実行）:
  python -m src.pipeline.weekly_prep --layer L3
  python -m src.pipeline.weekly_prep --aggregate
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src import validate
from src.collectors import rss

logger = logging.getLogger("weekly_prep")

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, default=str) + "\n")


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _iso_week_label(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def collect_l3(today: date | None = None) -> dict[str, Any]:
    """L3 ソースを取得、今週分を data/raw/l3-{YYYY-WNN}.jsonl に保存。"""
    today = today or date.today()
    week_label = _iso_week_label(today)
    sources_cfg = _load_yaml(CONFIG_DIR / "sources.yaml")
    l3_sources = [s for s in sources_cfg["sources"] if s.get("layer") == "L3"]

    items: list[dict[str, Any]] = []
    for src in l3_sources:
        if src.get("type") != "rss":
            logger.warning("non-RSS L3 source skipped: %s", src.get("id"))
            continue
        try:
            fetched = rss.fetch(src)
            logger.info("fetched %d items from %s (L3)", len(fetched), src.get("id"))
            items.extend(fetched)
        except Exception as e:  # noqa: BLE001
            logger.error("failed to fetch L3 %s: %s", src.get("id"), e)

    # L3 はスコープ "l34" でバリデーション（週内制約なし、未来日付・形式不正のみ除外）
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for it in items:
        ok, reason = validate.validate_for_scope(it, "l34", today=today)
        if ok:
            accepted.append(it)
        else:
            rejected.append({**it, "rejected_reason": reason})

    out_path = DATA_DIR / "raw" / f"l3-{week_label}.jsonl"
    _save_jsonl(out_path, accepted)

    summary = {
        "week_label": week_label,
        "raw_count": len(items),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "out_path": str(out_path.relative_to(REPO_ROOT)),
    }
    logger.info("L3 prep done: %s", summary)
    return summary


def aggregate_week(today: date | None = None) -> dict[str, Any]:
    """今週の L1/L2 cards を集約。月-金分。"""
    today = today or date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_label = _iso_week_label(today)

    cards_dir = DATA_DIR / "processed" / "cards"
    week_cards: list[dict[str, Any]] = []

    if cards_dir.exists():
        for p in sorted(cards_dir.glob("*.json")):
            try:
                d = date.fromisoformat(p.stem)
            except ValueError:
                continue
            if d.isocalendar()[:2] == (iso_year, iso_week):
                with p.open(encoding="utf-8") as f:
                    week_cards.extend(json.load(f))

    out = {
        "week_label": week_label,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "card_count": len(week_cards),
        "cards": week_cards,
    }
    out_path = DATA_DIR / "processed" / f"week-{week_label}.json"
    _save_json(out_path, out)

    summary = {
        "week_label": week_label,
        "card_count": len(week_cards),
        "out_path": str(out_path.relative_to(REPO_ROOT)),
    }
    logger.info("week aggregate done: %s", summary)
    return summary


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Weekly prep: L3 collection / weekly aggregation")
    parser.add_argument("--layer", choices=["L3"], help="Collect this layer only")
    parser.add_argument("--aggregate", action="store_true", help="Aggregate this week's L1/L2 cards")
    parser.add_argument("--today", type=str, help="Override today (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    result: dict[str, Any] = {}
    if args.layer == "L3":
        result["l3"] = collect_l3(today=today)
    if args.aggregate:
        result["aggregate"] = aggregate_week(today=today)
    if not result:
        parser.error("specify --layer L3 and/or --aggregate")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
