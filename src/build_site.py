"""Build site — Jinja2 で site/ 配下に静的 HTML を生成。

エントリポイント:
  python -m src.build_site                 # data/processed/ から実データで build
  python -m src.build_site --dummy         # ダミーデータで build (G-2 用)

生成物:
  site/index.html              最新デイリー
  site/weekly/index.html       ウィークリー一覧 (D-38)
  site/daily/{YYYY-MM-DD}.html 過去デイリー（実データある分のみ）

注: site/assets/ は build 対象外（既存ファイルをそのまま GitHub Pages が配信）。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger("build_site")

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "site" / "templates"
SITE_DIR = REPO_ROOT / "site"
ASSETS_DIR = SITE_DIR / "assets"
DATA_DIR = REPO_ROOT / "data"

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def _load_icons_sprite() -> str:
    """site/assets/icons.svg の中身を返す（HTML に inline 埋込用）。"""
    path = ASSETS_DIR / "icons.svg"
    if not path.exists():
        logger.warning("icons.svg not found: %s", path)
        return ""
    return path.read_text(encoding="utf-8")


def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # 注: asset() / url() はテンプレ側で {{ root_prefix }} を直接使用する方針へ移行済 (2026-04-26)
    #     深さ依存の正しいパスを得るには render 時の root_prefix が必要なため。
    return env


def _format_today_label(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日 ({WEEKDAY_JP[d.weekday()]})"


def _generated_at() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _compute_root_prefix(output_path: Path) -> str:
    """SITE_DIR からの深さに応じて '../' を必要数返す。

    - site/index.html       → depth 0 → ''
    - site/weekly/index.html → depth 1 → '../'
    - site/daily/2026-04-24.html → depth 1 → '../'
    - site/inquiries/{id}/latest.html → depth 2 → '../../'

    これによりブラウザが `{root_prefix}assets/style.css` を常に正しい URL に解決できる。
    """
    rel = output_path.relative_to(SITE_DIR)
    depth = len(rel.parts) - 1
    return "../" * depth


def _render(env: Environment, template_name: str, output_path: Path, **ctx: Any) -> None:
    template = env.get_template(template_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = template.render(
        icons_sprite=_load_icons_sprite(),
        generated_at=_generated_at(),
        root_prefix=_compute_root_prefix(output_path),
        **ctx,
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info("rendered %s (%d B)", output_path.relative_to(REPO_ROOT), len(html))


def _load_cards_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_daily_summary_md(date_iso: str) -> str | None:
    """data/processed/daily_summary-{date}.md があれば読込、HTML 化して返す。

    マークダウンの場合は将来 markdown -> html を入れる。当面は <p> ラップだけ。
    """
    path = DATA_DIR / "processed" / f"daily_summary-{date_iso}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    # 段落単位で <p> ラップ（簡易処理、後続 Phase で markdown ライブラリ導入検討）
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n".join(f"<p>{p}</p>" for p in paragraphs)


def _list_weekly_files() -> list[Path]:
    """data/processed/weekly/{YYYY-WNN}.json の一覧を週降順で返す。"""
    weekly_dir = DATA_DIR / "processed" / "weekly"
    if not weekly_dir.exists():
        return []
    return sorted(weekly_dir.glob("*.json"), reverse=True)


def _list_daily_archive_dates() -> list[date]:
    """data/processed/cards/*.json から過去のデイリー日付一覧を降順で返す。"""
    cards_dir = DATA_DIR / "processed" / "cards"
    if not cards_dir.exists():
        return []
    dates: list[date] = []
    for p in cards_dir.glob("*.json"):
        try:
            dates.append(date.fromisoformat(p.stem))
        except ValueError:
            continue
    return sorted(dates, reverse=True)


def _generate_dummy_cards(today: date) -> list[dict[str, Any]]:
    """ダミーカード 8 件（G-2 用、ロジック全部図解、テキスト最小化）。

    各 card に diagram_fact / diagram_context / diagram_impact を任意で付けられる。
    使えるテンプレ:
      - diagram-flow / diagram-stat / diagram-compare
      - diagram-pivot (旧→新)
      - diagram-bullets (1.2.3 番号付き)
      - diagram-timeline (時系列)
    """
    today_iso = today.isoformat()

    # ---- 図解テンプレ集 ----
    flow_3layer = """
<div class="diagram diagram-flow">
  <div class="flow-row">
    <div class="flow-step">CS<span class="flow-step-cap">呼び出し</span></div>
    <div class="flow-arrow">→</div>
    <div class="flow-step">Dify<span class="flow-step-cap">AI 処理</span></div>
    <div class="flow-arrow">→</div>
    <div class="flow-step">PA<span class="flow-step-cap">業務自動化</span></div>
  </div>
  <div class="diagram-note">Power Fx スクリプトで連携制御（プレビュー）</div>
</div>
""".strip()

    stat_yokohama = """
<div class="diagram diagram-stat">
  <div class="stat-number">1,600 <span class="stat-unit">件 / 月</span></div>
  <div class="stat-caption">電話オペレーター介入なしで完結（運用 6 ヶ月）</div>
</div>
""".strip()

    stat_failure = """
<div class="diagram diagram-stat">
  <div class="stat-number">8 <span class="stat-unit">%</span></div>
  <div class="stat-caption">社内 AI チャットボット利用率（半年で低下）</div>
</div>
""".strip()

    stat_growth = """
<div class="diagram diagram-stat">
  <div class="stat-number">×1.8</div>
  <div class="stat-caption">国内エンタープライズ AI 基盤市場 (2025 年度 / 前年比)</div>
</div>
""".strip()

    compare_meeting = """
<div class="diagram diagram-compare">
  <div class="compare-col compare-left">
    <div class="compare-title">ベンダー言説</div>
    <div class="compare-point">会議が減る</div>
    <div class="compare-point">作業時間 50% 削減</div>
  </div>
  <div class="compare-vs">vs</div>
  <div class="compare-col compare-right">
    <div class="compare-title">現場感覚</div>
    <div class="compare-point">準備が増えた</div>
    <div class="compare-point">意思決定可視化で会議増</div>
  </div>
</div>
""".strip()

    pivot_orchestration = """
<div class="diagram diagram-pivot">
  <div class="pivot-cell pivot-from">
    <div class="pivot-label">これまで</div>
    <div class="pivot-text">単体エージェント</div>
  </div>
  <div class="pivot-arrow">→</div>
  <div class="pivot-cell pivot-to">
    <div class="pivot-label">これから</div>
    <div class="pivot-text">オーケストレーション</div>
  </div>
</div>
""".strip()

    pivot_voicebot = """
<div class="diagram diagram-pivot">
  <div class="pivot-cell pivot-from">
    <div class="pivot-label">補助</div>
    <div class="pivot-text">人 + 音声 AI</div>
  </div>
  <div class="pivot-arrow">→</div>
  <div class="pivot-cell pivot-to">
    <div class="pivot-label">完結</div>
    <div class="pivot-text">音声 AI のみ</div>
  </div>
</div>
""".strip()

    pivot_creative = """
<div class="diagram diagram-pivot">
  <div class="pivot-cell pivot-from">
    <div class="pivot-label">既存文脈</div>
    <div class="pivot-text">効率化のための AI</div>
  </div>
  <div class="pivot-arrow">→</div>
  <div class="pivot-cell pivot-to">
    <div class="pivot-label">新文脈</div>
    <div class="pivot-text">人間の余白を残す AI</div>
  </div>
</div>
""".strip()

    bullets_powerfx_impact = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">CS / Dify / PA の 3 層提案で前提化できる</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">プレビュー段階のため本番投入は慎重に</span></div>
</div>
""".strip()

    bullets_yokohama_impact = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">金融提案の完結型音声 AI リファレンス化</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">顧客体験との両立は別途検討</span></div>
</div>
""".strip()

    bullets_creative_impact = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">「ワクワク提案」の素材として引用可能</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">業務文脈と創作文脈の前提差を踏まえる</span></div>
</div>
""".strip()

    bullets_n8n_context = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">複数ツール併用が現実的な選択肢として広がる</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">実装ノウハウの公開で業界リテラシー底上げ</span></div>
</div>
""".strip()

    bullets_failure_impact = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">「利用率」単一 KPI のリスク提示材料</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">業務文脈調査を提案初期に組み込む後押し</span></div>
</div>
""".strip()

    bullets_failure_context = """
<div class="diagram diagram-bullets">
  <div class="bullet-item"><span class="bullet-num">1</span><span class="bullet-text">技術ではなく業務文脈の理解不足が示唆</span></div>
  <div class="bullet-item"><span class="bullet-num">2</span><span class="bullet-text">「答えが返ってこない」「検索が早い」の声</span></div>
</div>
""".strip()

    timeline_anthropic = """
<div class="diagram diagram-timeline">
  <div class="timeline-step">OpenAI<span class="timeline-cap">2024</span></div>
  <div class="timeline-arrow">→</div>
  <div class="timeline-step">Google<span class="timeline-cap">2025</span></div>
  <div class="timeline-arrow">→</div>
  <div class="timeline-step timeline-current">Anthropic<span class="timeline-cap">2026 ベータ</span></div>
</div>
""".strip()

    return [
        {
            "id": "dummy-001",
            "layer": "L1",
            "topic": "ai_agents",
            "importance": "high",
            "info_type": "vendor_announcement",
            "title": "Microsoft、Copilot Studio に Power Fx ベースのエージェント連携を発表",
            "source_name": "ITmedia NEWS",
            "published_at": today_iso,
            "url": "https://example.com/dummy/1",
            "fact": "Microsoft が Build 2026 で、Copilot Studio に Power Fx スクリプトでエージェント間連携を制御する機能を追加したと発表しました。プレビュー版は本日提供開始です。",
            "diagram_fact": flow_3layer,
            "context_analysis": "ベンダー発表のため第三者検証は伴っていません。Power Platform の既存顧客基盤を活かし、Dify など新興プラットフォームへの対抗軸を打ち出した動きで、エージェント運用の主戦場が「単体導入」から「複数エージェントのオーケストレーション」へ移っている流れの上にあります。",
            "diagram_context": pivot_orchestration,
            "impact": "CS / Dify / PA の 3 層アーキテクチャ提案で、Power Fx 連携を前提にしたシナリオが描けます。プレビュー段階のため、本番投入の判断にはベンダーの一般提供 (GA) と独立検証を待つ余地があります。",
            "diagram_impact": bullets_powerfx_impact,
        },
        {
            "id": "dummy-002",
            "layer": "L2",
            "topic": "dx_cases",
            "importance": "high",
            "info_type": "success_case",
            "title": "横浜銀行、ボイスボットで月 1,600 件の証明書発行を自動完結",
            "source_name": "日経クロステック",
            "published_at": today_iso,
            "url": "https://example.com/dummy/2",
            "fact": "横浜銀行はボイスボットを活用した証明書発行の自動化を本格稼働させ、月 1,600 件を電話オペレーター介入なしで完結させていると発表しました。導入から 6 ヶ月の運用実績です。",
            "diagram_fact": stat_yokohama,
            "context_analysis": "金融機関での音声 AI はこれまで「補助」としての導入が主流でした。月 1,600 件規模の完結処理は、業界構造として「人を介さない選択肢」が現実化しつつある兆候です。導入事例レポートのため、失敗側の言及はありません。",
            "diagram_context": pivot_voicebot,
            "impact": "金融業界向け提案で「完結型音声 AI」のリファレンスとして引用できます。一方、お客様体験の観点で「人を介さない」是非は別途検討が必要な余地があります。",
            "diagram_impact": bullets_yokohama_impact,
        },
        {
            "id": "dummy-003",
            "layer": "L1",
            "topic": "other",
            "importance": "mid",
            "info_type": "essay",
            "title": "「AI と創作」の境界: 人間が描くべき余白とは何か",
            "source_name": "はてなブックマーク - テクノロジー",
            "published_at": today_iso,
            "url": "https://example.com/dummy/3",
            "fact": "「生成 AI の普及で創作の主体は誰なのか」を論じた個人ブログ記事が、はてブで 320 ブックマークを集めています。著者は文芸誌の連載作家です。",
            "context_analysis": "創作の議論はこれまで効率化の文脈で語られがちでしたが、本記事は「人間の余白を残す」という視点を持ち込みます。エッセイのため一般化は慎重に行いますが、はてブの反応からは類似の問題意識を持つ読み手が一定数いることがわかります。",
            "diagram_context": pivot_creative,
            "impact": "コンサル提案で「ワクワクする業務」を語る素材として引用できます。ただし業務文脈と創作文脈は前提が異なるため、安易な類推は避ける必要があります。",
            "diagram_impact": bullets_creative_impact,
        },
        {
            "id": "dummy-004",
            "layer": "L2",
            "topic": "automation",
            "importance": "mid",
            "info_type": "tech_validation",
            "title": "n8n と Power Automate の統合パターン 5 選: 実装上の落とし穴",
            "source_name": "Publickey",
            "published_at": today_iso,
            "url": "https://example.com/dummy/4",
            "fact": "Publickey は、ワークフロー自動化ツール n8n と Microsoft Power Automate を組み合わせた統合パターン 5 種について、実装上の制約と落とし穴を検証記事として公開しました。",
            "context_analysis": "技術検証記事であり、ベンダー側の宣伝とは異なる第三者視点で書かれています。RPA 領域では複数ツール併用が現実解として広まっており、実装ノウハウの可視化が業界全体のリテラシー底上げに寄与します。",
            "diagram_context": bullets_n8n_context,
            "impact": "業務自動化案件のツール選定議論で本記事の検証結果を参照できます。ハイブリッド構成を選択した場合の運用コスト試算にも有用です。",
        },
        {
            "id": "dummy-005",
            "layer": "L1",
            "topic": "ai_agents",
            "importance": "low",
            "info_type": "market",
            "title": "国内エンタープライズ AI 基盤市場、2025 年度は前年比 1.8 倍",
            "source_name": "はてなブックマーク - テクノロジー",
            "published_at": today_iso,
            "url": "https://example.com/dummy/5",
            "fact": "民間調査会社が国内エンタープライズ AI 基盤市場の 2025 年度規模を発表しました。Copilot Studio / Dify / 国産プラットフォームの競合が激化しているとされています。",
            "diagram_fact": stat_growth,
            "context_analysis": "調査会社レポートのため、サンプリングと市場区分の取り方が結果を大きく左右します。1.8 倍という伸び率自体は他調査と整合的ですが、解釈は前提次第で変わります。",
            "impact": "市場サイズの議論を提案資料に組み込む際の参考データとして使えます。一次ソース（調査会社レポート本体）を確認した上で引用するのが望ましい状況です。",
        },
        {
            "id": "dummy-006",
            "layer": "L2",
            "topic": "dx_cases",
            "importance": "mid",
            "info_type": "failure",
            "title": "ある製造業の AI チャットボット、半年で利用率 8% に低下",
            "source_name": "日経クロステック",
            "published_at": today_iso,
            "url": "https://example.com/dummy/6",
            "fact": "ある中堅製造業が導入した社内 AI チャットボットの利用率が、運用半年で 8% まで低下したと記事は報告しています。同社は導入当初の社内告知で「業務効率化」を前面に出していました。",
            "diagram_fact": stat_failure,
            "context_analysis": "失敗事例の記事は業界誌で扱われる頻度が成功事例より少ないため貴重です。利用率低下の主因は「答えが返ってこない」「自分で検索した方が早い」という従業員の声で、技術ではなく業務文脈の理解不足が示唆されています。",
            "diagram_context": bullets_failure_context,
            "impact": "提案で KPI を「利用率」だけで測ることのリスクを示す材料として使えます。業務文脈の調査を初期フェーズに組み込む提案アプローチの後押しになります。",
            "diagram_impact": bullets_failure_impact,
        },
        {
            "id": "dummy-007",
            "layer": "L1",
            "topic": "other",
            "importance": "high",
            "info_type": "critic",
            "title": "「生成 AI は本当に会議を減らしているのか」議論、800 ブクマ突破",
            "source_name": "はてなブックマーク - テクノロジー",
            "published_at": today_iso,
            "url": "https://example.com/dummy/7",
            "fact": "個人ブログ記事「生成 AI は本当に会議を減らしているのか」がはてブで 800 ブックマークを超え、議論が活発化しています。著者は事業会社の DX 推進担当です。",
            "diagram_fact": compare_meeting,
            "context_analysis": "ベンダー言説の「会議が減る」と現場感覚の「むしろ準備が増えた」「意思決定の可視化で会議が増えた」のずれを論じる記事です。批判的記事のため一般化には注意が必要ですが、この乖離は複数の現場で観察される構造です。",
            "impact": "提案資料で導入効果を語る際、定量 ROI だけでなく「現場での使用感」を定性指標として組み込む設計が、提案の深さに効いてきます。",
        },
        {
            "id": "dummy-008",
            "layer": "L2",
            "topic": "ai_agents",
            "importance": "low",
            "info_type": "vendor_announcement",
            "title": "Anthropic、Claude のメモリ機能ベータ提供開始",
            "source_name": "ITmedia NEWS",
            "published_at": today_iso,
            "url": "https://example.com/dummy/8",
            "fact": "Anthropic は Claude のメモリ機能をベータ提供開始したと発表しました。会話履歴を超えた永続的なコンテキスト保持を実現するとされています。",
            "context_analysis": "ベンダー発表のため第三者検証は伴っていません。OpenAI / Google が先行している領域への追随で、エージェント運用の文脈で重要な機能ですが、企業利用におけるデータ保護観点での評価は別途必要です。",
            "diagram_context": timeline_anthropic,
            "impact": "エージェント設計の提案でメモリ機能を前提にしたシナリオが描けます。ベータ段階のため SLA の確認が必要な状況です。",
        },
    ]


_TOPIC_LABEL = {
    "ai_agents": "AIエージェント",
    "automation": "業務自動化",
    "dx_cases": "DX事例",
    "other": "その他",
}
_TOPIC_ORDER = ["ai_agents", "automation", "dx_cases", "other"]


def compute_today_stats(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Today's Pulse パネル用の集計。"""
    importance_counter = Counter(c.get("importance", "low") for c in cards)
    info_type_counter = Counter(c.get("info_type") for c in cards)
    topic_counter = Counter(c.get("topic", "other") for c in cards)
    topics_list = [
        {"id": tid, "label": _TOPIC_LABEL[tid], "count": topic_counter.get(tid, 0)}
        for tid in _TOPIC_ORDER
    ]
    return {
        "total": len(cards),
        "high": importance_counter.get("high", 0),
        "mid": importance_counter.get("mid", 0),
        "low": importance_counter.get("low", 0),
        "vendor": info_type_counter.get("vendor_announcement", 0),
        "success": info_type_counter.get("success_case", 0),
        "failure": info_type_counter.get("failure", 0),
        "critic": info_type_counter.get("critic", 0),
        "topics": topics_list,
    }


def sort_cards_by_importance(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """重要度順 high → mid → low、各内では published_at 降順。"""
    rank = {"high": 0, "mid": 1, "low": 2}
    return sorted(
        cards,
        key=lambda c: (
            rank.get(c.get("importance"), 3),
            c.get("published_at") or "",
        ),
        reverse=False,
    )


def group_weekly_by_month(items: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """weekly_items を 月ラベル ('2026 年 4月') でグルーピング。降順。

    各 item は date_range の先頭日付 (YYYY-MM-DD) を `_sort_date` キーで保持する想定。
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        # date_range '2026-04-19 〜 2026-04-25' から先頭日付抽出
        sort_date_str = it.get("_sort_date") or it.get("date_range", "").split(" ")[0]
        try:
            d = date.fromisoformat(sort_date_str)
            month_key = (d.year, d.month)
            month_label = f"{d.year} 年 {d.month} 月"
        except ValueError:
            month_key = (0, 0)
            month_label = "日付不明"
        grouped[month_label].append(it)

    # 月キーで降順ソート
    def month_key(label: str) -> tuple[int, int]:
        try:
            year_part, month_part = label.replace("年", "").replace("月", "").split()
            return (int(year_part), int(month_part))
        except (ValueError, IndexError):
            return (0, 0)

    return sorted(grouped.items(), key=lambda kv: month_key(kv[0]), reverse=True)


def _generate_dummy_summary() -> str:
    return """
<p>本日のハイライトは、エージェント運用の主戦場が「単体導入」から「オーケストレーション・全社展開」に移っている兆候です。Microsoft の Power Fx 連携追加と、横浜銀行のボイスボット完結事例は、別の角度から同じ方向を指しています。</p>
<p>業界構造としては、Copilot Studio / Dify / Power Automate の 3 層アーキテクチャが提案標準になりつつあります。失敗事例（製造業のチャットボット利用率 8%）や、はてブで 800 ブクマを集めた「会議は減ったか」議論は、ベンダー言説と現場感覚の乖離を裏テーマとして示しています。</p>
<p>注目すべきカード: <a href="#card-dummy-001">Power Fx 連携</a>、<a href="#card-dummy-002">横浜銀行ボイスボット</a>、<a href="#card-dummy-007">会議論争</a>。</p>
""".strip()


def _generate_dummy_weekly_items() -> list[dict[str, Any]]:
    """ウィークリー一覧 (D-38) のダミーデータ。

    積み重なり時の視認性確認のため、4 ヶ月にわたる 9 週分を生成。
    レンズ ID で色分け、各週にトピックチップを付与して内容を一目で把握可能に。
    """

    def topics(ai: int, au: int, dx: int, other: int) -> list[dict[str, Any]]:
        return [
            {"id": "ai_agents", "label": "AIエージェント", "count": ai},
            {"id": "automation", "label": "業務自動化", "count": au},
            {"id": "dx_cases", "label": "DX事例", "count": dx},
            {"id": "other", "label": "その他", "count": other},
        ]

    return [
        {
            "_sort_date": "2026-04-19",
            "href": "weekly/2026-W17.html",
            "week_label": "WEEK 17 / 2026",
            "date_range": "2026-04-19 〜 2026-04-25",
            "theme_title": "「導入して終わり」から「内製化・オーケストレーション」へ — 主戦場の第 2 ラウンド",
            "lens": "労働",
            "lens_id": "labor",
            "summary_excerpt": "今週は、複数の動きが同じ方向を指している週でした。エージェント・オーケストレーターという新職務、Power Fx 連携、月 1,600 件のボイスボット完結事例。一方で「会議は減っていない」という現場感覚も。",
            "topics": topics(12, 4, 6, 3),
        },
        {
            "_sort_date": "2026-04-12",
            "href": "weekly/2026-W16.html",
            "week_label": "WEEK 16 / 2026",
            "date_range": "2026-04-12 〜 2026-04-18",
            "theme_title": "「生成AI導入済み → エージェント化」企業 AI 活用が第 2 段階の競争フェーズへ",
            "lens": "知識民主化",
            "lens_id": "knowledge",
            "summary_excerpt": "Google Cloud は「エージェント・オーケストレーター」という新職務を提唱、AIsmiley は「答える AI と動く AI」の分類論を、Microsoft は Copilot Studio に Power Fx 連携を発表しました。",
            "topics": topics(11, 3, 5, 4),
        },
        {
            "_sort_date": "2026-04-05",
            "href": "weekly/2026-W15.html",
            "week_label": "WEEK 15 / 2026",
            "date_range": "2026-04-05 〜 2026-04-11",
            "theme_title": "プライバシー設計が AI エージェント運用の前提条件に",
            "lens": "プライバシー",
            "lens_id": "privacy",
            "summary_excerpt": "国内外で AI エージェント運用におけるデータ保護要件の議論が活発化。EU AI 法の高リスク分類に該当する事例の整理が進んでいます。",
            "topics": topics(8, 5, 4, 6),
        },
        {
            "_sort_date": "2026-03-29",
            "href": "weekly/2026-W14.html",
            "week_label": "WEEK 14 / 2026",
            "date_range": "2026-03-29 〜 2026-04-04",
            "theme_title": "RPA から自律エージェントへ — 業務自動化の主役が交代しはじめた週",
            "lens": "労働",
            "lens_id": "labor",
            "summary_excerpt": "従来 RPA ベンダーが軒並み「エージェント機能搭載」を発表。同時に「RPA は AI エージェントに置き換えられるのか」という現場議論も加熱しました。",
            "topics": topics(9, 11, 4, 2),
        },
        {
            "_sort_date": "2026-03-22",
            "href": "weekly/2026-W13.html",
            "week_label": "WEEK 13 / 2026",
            "date_range": "2026-03-22 〜 2026-03-28",
            "theme_title": "ベンダー集中の懸念と国産プラットフォームの再評価",
            "lens": "権力配分",
            "lens_id": "power",
            "summary_excerpt": "Microsoft / OpenAI / Google の寡占懸念に対し、国産 AI プラットフォーム陣営が連携を発表。エンタープライズ調達の選択肢として再評価されています。",
            "topics": topics(7, 6, 8, 4),
        },
        {
            "_sort_date": "2026-03-15",
            "href": "weekly/2026-W12.html",
            "week_label": "WEEK 12 / 2026",
            "date_range": "2026-03-15 〜 2026-03-21",
            "theme_title": "「ワクワクする業務」を語る企業文化の変化兆候",
            "lens": "倫理責任",
            "lens_id": "ethics",
            "summary_excerpt": "効率化一辺倒の DX 言説に対し、「働きがい」「創造性」を前面に出した変革事例が複数報じられました。一方で表層的な置き換えとの批判も。",
            "topics": topics(5, 3, 9, 7),
        },
        {
            "_sort_date": "2026-03-08",
            "href": "weekly/2026-W11.html",
            "week_label": "WEEK 11 / 2026",
            "date_range": "2026-03-08 〜 2026-03-14",
            "theme_title": "若手・ベテラン世代間で生成 AI 活用の差が顕在化",
            "lens": "世代間非対称",
            "lens_id": "generation",
            "summary_excerpt": "新人 OJT に AI を組み込む企業と、ベテラン業務知識のドキュメント化に AI を使う企業で、組織内のスキル分布が変化しはじめています。",
            "topics": topics(6, 4, 8, 5),
        },
        {
            "_sort_date": "2026-02-22",
            "href": "weekly/2026-W08.html",
            "week_label": "WEEK 08 / 2026",
            "date_range": "2026-02-22 〜 2026-02-28",
            "theme_title": "金融・行政におけるエージェント活用の規制動向",
            "lens": "プライバシー",
            "lens_id": "privacy",
            "summary_excerpt": "金融庁・デジタル庁から、エージェント運用時のログ保管要件と説明責任ガイドラインが相次いで公表されました。",
            "topics": topics(7, 2, 10, 3),
        },
        {
            "_sort_date": "2026-02-15",
            "href": "weekly/2026-W07.html",
            "week_label": "WEEK 07 / 2026",
            "date_range": "2026-02-15 〜 2026-02-21",
            "theme_title": "失敗事例の共有が始まった週 — 撤退・見直しの公開議論",
            "lens": "倫理責任",
            "lens_id": "ethics",
            "summary_excerpt": "AI チャットボット撤退、社内 RAG 運用見直し、コスト超過の Copilot 削減など、これまで公にされにくかった失敗事例の共有が始まりました。",
            "topics": topics(4, 6, 7, 5),
        },
    ]


def build_index(
    env: Environment,
    cards: list[dict[str, Any]],
    today: date,
    daily_summary: str | None = None,
) -> None:
    iso_year, iso_week, iso_dow = today.isocalendar()
    sorted_cards = sort_cards_by_importance(cards)
    stats = compute_today_stats(cards)
    # 引数の daily_summary が None なら data/processed/ から読込試行
    if daily_summary is None:
        daily_summary = _load_daily_summary_md(today.isoformat())
    _render(
        env,
        "index.html.j2",
        SITE_DIR / "index.html",
        cards=sorted_cards,
        stats=stats,
        today_iso=today.isoformat(),
        today_label=_format_today_label(today),
        iso_week=iso_week,
        iso_dow=iso_dow,
        daily_summary=daily_summary,
    )


def build_weekly_index(env: Environment, items: list[dict[str, Any]]) -> None:
    items_by_month = group_weekly_by_month(items)
    _render(
        env,
        "weekly_index.html.j2",
        SITE_DIR / "weekly" / "index.html",
        items_by_month=items_by_month,
        total_count=len(items),
    )


def build_weekly_details(env: Environment) -> int:
    """data/processed/weekly/{YYYY-WNN}.json の各週から site/weekly/{YYYY-WNN}.html を生成。"""
    count = 0
    for p in _list_weekly_files():
        with p.open(encoding="utf-8") as f:
            weekly_data = json.load(f)
        # Markdown 文字列を簡易 HTML 化
        weekly_data = dict(weekly_data)
        for k_md, k_html in [("part1", "part1_html"), ("part2", "part2_html"), ("part3", "part3_html")]:
            if weekly_data.get(k_md) and not weekly_data.get(k_html):
                weekly_data[k_html] = _md_to_simple_html(weekly_data[k_md])
        if weekly_data.get("theme_summary") and not weekly_data.get("theme_summary_html"):
            weekly_data["theme_summary"] = _md_to_simple_html(weekly_data["theme_summary"])
        slug = p.stem  # YYYY-WNN
        _render(
            env,
            "weekly_detail.html.j2",
            SITE_DIR / "weekly" / f"{slug}.html",
            weekly=weekly_data,
        )
        count += 1
    return count


def _load_inquiries() -> list[dict[str, Any]]:
    path = REPO_ROOT / "config" / "inquiries.yaml"
    if not path.exists():
        return []
    import yaml
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("inquiries", []) or []


def _md_to_simple_html(md_text: str) -> str:
    """簡易 Markdown → HTML（# / ## / ### 見出しと段落のみ）。

    Phase 5 で markdown ライブラリ導入検討。当面は最低限。
    """
    lines = md_text.split("\n")
    out: list[str] = []
    para_buf: list[str] = []

    def flush_para():
        if para_buf:
            text = " ".join(para_buf).strip()
            if text:
                out.append(f"<p>{text}</p>")
            para_buf.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            continue
        if line.startswith("### "):
            flush_para()
            out.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            flush_para()
            out.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("# "):
            flush_para()
            out.append(f"<h1>{line[2:].strip()}</h1>")
        elif line.startswith("- "):
            flush_para()
            out.append(f"<li>{line[2:].strip()}</li>")
        else:
            para_buf.append(line)
    flush_para()
    return "\n".join(out)


def build_inquiries(env: Environment) -> int:
    """問い一覧 + 各 inquiry の latest / archive を生成。"""
    inquiries = _load_inquiries()
    if not inquiries:
        # 問いがない場合でも index 自体は生成（空メッセージ）
        _render(env, "inquiries_index.html.j2", SITE_DIR / "inquiries" / "index.html", inquiries=[])
        return 0

    _render(env, "inquiries_index.html.j2", SITE_DIR / "inquiries" / "index.html", inquiries=inquiries)

    count = 0
    for inq in inquiries:
        inq_id = inq["id"]
        reports_dir = DATA_DIR / "reports" / inq_id

        # 最新レポート
        latest_md_path = reports_dir / "latest.md"
        report_html = None
        report_date = None
        if latest_md_path.exists():
            md = latest_md_path.read_text(encoding="utf-8")
            report_html = _md_to_simple_html(md)
            # ファイル更新日時から日付推定（後で frontmatter で明示する案あり）
            try:
                report_date = datetime.fromtimestamp(latest_md_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
            except OSError:
                report_date = None

        _render(
            env,
            "inquiry_latest.html.j2",
            SITE_DIR / "inquiries" / inq_id / "latest.html",
            inquiry=inq,
            report_html=report_html,
            report_date=report_date,
        )

        # アーカイブ一覧
        items = []
        if reports_dir.exists():
            for p in sorted(reports_dir.glob("*.md"), reverse=True):
                if p.name == "latest.md":
                    continue
                items.append({
                    "href": f"../{p.stem}.html",  # 個別ページは Phase 5 で実装、当面は latest と archive のみ
                    "report_date": p.stem,
                    "inquiry_title": inq["question"],
                    "exec_summary": "",  # 将来 frontmatter or 先頭抜粋
                })
        _render(
            env,
            "inquiry_archive.html.j2",
            SITE_DIR / "inquiries" / inq_id / "archive.html",
            inquiry=inq,
            items=items,
        )
        count += 1

    return count


def build_daily_pages(env: Environment, today: date) -> int:
    """過去全デイリーの個別ページ + デイリー一覧 (/daily/archive/) を生成。"""
    dates = _list_daily_archive_dates()
    count = 0
    # 個別ページ
    for d in dates:
        d_iso = d.isoformat()
        cards = _load_cards_json(DATA_DIR / "processed" / "cards" / f"{d_iso}.json")
        if not cards:
            continue
        sorted_cards = sort_cards_by_importance(cards)
        daily_summary = _load_daily_summary_md(d_iso)
        _render(
            env,
            "daily.html.j2",
            SITE_DIR / "daily" / f"{d_iso}.html",
            cards=sorted_cards,
            daily_summary=daily_summary,
            date_iso=d_iso,
            date_label=_format_today_label(d),
            today_iso=today.isoformat(),
        )
        count += 1

    # アーカイブ一覧 (/daily/archive/index.html)
    items = []
    items_by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in dates:
        d_iso = d.isoformat()
        cards = _load_cards_json(DATA_DIR / "processed" / "cards" / f"{d_iso}.json")
        item = {
            "_sort_date": d_iso,
            "href": f"../{d_iso}.html",
            "date_label": _format_today_label(d),
            "card_count": len(cards),
        }
        items.append(item)
        month_label = f"{d.year} 年 {d.month} 月"
        items_by_month[month_label].append(item)

    # 月降順ソート
    def month_key(label: str) -> tuple[int, int]:
        try:
            year_part, month_part = label.replace("年", "").replace("月", "").split()
            return (int(year_part), int(month_part))
        except (ValueError, IndexError):
            return (0, 0)

    sorted_months = sorted(items_by_month.items(), key=lambda kv: month_key(kv[0]), reverse=True)

    _render(
        env,
        "daily_archive.html.j2",
        SITE_DIR / "daily" / "archive" / "index.html",
        items_by_month=sorted_months,
        total_count=len(items),
    )
    return count


def run(today: date | None = None, dummy: bool = False) -> dict[str, Any]:
    today = today or date.today()
    env = _build_env()

    # データ読込
    if dummy:
        cards = _generate_dummy_cards(today)
        daily_summary = _generate_dummy_summary()
        weekly_items = _generate_dummy_weekly_items()
    else:
        cards_path = DATA_DIR / "processed" / "cards" / f"{today.isoformat()}.json"
        cards = _load_cards_json(cards_path)
        daily_summary = None  # Phase 2 で daily_summary.json も読み込む
        weekly_items = []  # Phase 4 で weekly インデックス読込

    # 各ページ build
    build_index(env, cards, today, daily_summary=daily_summary)
    build_weekly_index(env, weekly_items)

    # /daily/archive/ + 過去デイリー個別ページ（ダミーモードでは過去データなし、
    # 通常モードでは data/processed/cards/*.json を全部レンダ）
    daily_pages_count = 0
    if not dummy:
        daily_pages_count = build_daily_pages(env, today)

    # /inquiries/ 関連（Phase 3）
    inquiries_count = build_inquiries(env)

    # /weekly/{YYYY-WNN}.html 詳細ページ（Phase 4）
    weekly_details_count = 0
    if not dummy:
        weekly_details_count = build_weekly_details(env)

    return {
        "today": today.isoformat(),
        "dummy": dummy,
        "cards": len(cards),
        "weekly_items": len(weekly_items),
        "daily_pages": daily_pages_count,
        "inquiries": inquiries_count,
        "weekly_details": weekly_details_count,
    }


def main() -> int:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Build static site")
    parser.add_argument("--dummy", action="store_true", help="Use dummy data (G-2 review)")
    parser.add_argument("--today", type=str, help="Override today (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    result = run(today=today, dummy=args.dummy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
