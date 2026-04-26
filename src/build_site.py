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
    # カスタムグローバル: asset() / url()（将来 base path 切替対応の余地）
    env.globals["asset"] = lambda p: f"assets/{p}"
    env.globals["url"] = lambda p: p
    return env


def _format_today_label(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日 ({WEEKDAY_JP[d.weekday()]})"


def _generated_at() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _render(env: Environment, template_name: str, output_path: Path, **ctx: Any) -> None:
    template = env.get_template(template_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = template.render(
        icons_sprite=_load_icons_sprite(),
        generated_at=_generated_at(),
        **ctx,
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info("rendered %s (%d B)", output_path.relative_to(REPO_ROOT), len(html))


def _load_cards_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _generate_dummy_cards(today: date) -> list[dict[str, Any]]:
    """ダミーカード 8 件（G-2 レビュー用）。

    マスター中心テーマ「業務革新・幸せな働き方・ワクワク」を反映、
    info_type / topic / importance / layer をバラけさせる。
    """
    today_iso = today.isoformat()
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
            "fact": "Microsoft は Build 2026 で、Copilot Studio に Power Fx スクリプトでエージェント間連携を制御する機能を追加したと発表しました。プレビュー版は本日提供開始です。",
            "context_analysis": "このニュースはベンダー発表であり、第三者検証は伴っていません。背景には、エージェント技術が「単体」から「オーケストレーション」へ主戦場が移っている流れがあります。Power Fx を採用した点は、Microsoft の既存 Power Platform 顧客基盤を活かす戦略であり、Dify などの新興プラットフォームへの対抗軸として読めます。",
            "impact": "Copilot Studio / Dify / Power Automate の 3 層アーキテクチャ提案を行う際、Power Fx 連携を前提としたシナリオが描ける余地があります。ただしプレビュー段階のため本番投入は慎重に検討する余地があります。",
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
            "fact": "横浜銀行は、ボイスボットを活用した証明書発行の自動化を本格稼働させ、月 1,600 件を電話オペレーターを介さず完結させていると発表しました。導入から 6 か月の実績です。",
            "context_analysis": "金融機関での音声 AI による完結型業務処理は、これまで「補助」としての導入が主流でした。月 1,600 件規模の完結処理は、業界構造として「人を介さない選択肢」が現実になりつつあることを示しています。導入事例レポートのため、失敗事例や撤退事例の言及はありません。",
            "impact": "金融業界向け提案で「完結型音声 AI」のリファレンスケースとして引用できる余地があります。一方で、お客様体験の観点から「人を介さない」ことの是非は別途検討する必要があります。",
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
            "fact": "個人ブログで「生成 AI の普及で創作の主体は誰なのか」を論じた記事が、はてブで 320 ブックマークを集めています。著者は文芸誌の連載作家です。",
            "context_analysis": "創作系の議論はこれまで「効率化の文脈」で語られがちでしたが、本記事は「人間の余白」という視点を持ち込んでいます。エッセイのため一般化は慎重に行う必要がありますが、はてブの反応からは類似の問題意識を持つ読み手が一定数いることがわかります。",
            "impact": "コンサル提案で「ワクワクする業務」を語る際の素材として、創作領域での議論を引用できる余地があります。ただし業務文脈と創作文脈は前提が異なるため、安易な類推は避ける必要があります。",
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
            "context_analysis": "技術検証記事であり、ベンダー側の宣伝とは異なる視点で書かれています。RPA 領域では「複数ツール併用」が現実的な選択肢として広まっており、実装ノウハウの可視化は業界全体のリテラシー向上に寄与します。",
            "impact": "業務自動化案件の提案時、ツール選定の議論で本記事の検証結果を参照できる余地があります。特に「ハイブリッド構成」を選択した場合の運用コストの試算に役立ちます。",
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
            "fact": "民間調査会社が国内エンタープライズ AI 基盤市場の 2025 年度規模を発表しました。前年度比 1.8 倍の伸びで、Copilot Studio / Dify / 国産プラットフォームの競合が激化しているとされています。",
            "context_analysis": "調査会社レポートのため、サンプリング・定義の前提が結果を大きく左右します。1.8 倍の伸び自体は他調査と整合的ですが、市場区分の取り方によって解釈は変わります。",
            "impact": "市場サイズの議論を提案資料に組み込む際の参考データとして使える余地があります。一次ソース（調査会社レポート本体）を確認した上で引用するのが望ましい状況です。",
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
            "context_analysis": "失敗事例の記事は、業界誌で扱われる頻度が成功事例より少ないため貴重です。利用率低下の主因は「知りたいことに答えてくれない」「自分で検索した方が早い」という従業員の声で、技術側ではなく業務文脈の理解不足が示唆されています。",
            "impact": "導入提案の際、KPI を「利用率」だけで測ることのリスクを示す材料として使える余地があります。業務文脈の調査を初期フェーズに組み込む提案アプローチの後押しになります。",
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
            "context_analysis": "記事は、ベンダー言説の「会議が減る」と現場感覚の「むしろ準備が増えた」「意思決定の可視化で会議が増えた」のずれを論じています。批判的記事のため一般化には注意が必要ですが、ベンダー言説と現場感覚の乖離は、複数の現場で観察される構造です。",
            "impact": "提案資料で導入効果を語る際、定量 ROI だけでなく「現場での使用感」を定性指標として組み込む設計が、提案の深さに効いてくる余地があります。",
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
            "context_analysis": "このニュースはベンダー発表であり、第三者検証は伴っていません。OpenAI / Google が先行している領域への追随で、エージェント運用の文脈で重要な機能ですが、企業利用におけるデータ保護観点での評価は別途必要です。",
            "impact": "エージェント設計提案でメモリ機能を前提にしたシナリオを描く際、実装オプションが増える余地があります。ベータ段階のため SLA の確認が必要な状況です。",
        },
    ]


def _generate_dummy_summary() -> str:
    return """
<p>本日のハイライトは、エージェント運用の主戦場が「単体導入」から「オーケストレーション・全社展開」に移っている兆候です。Microsoft の Power Fx 連携追加と、横浜銀行のボイスボット完結事例は、別の角度から同じ方向を指しています。</p>
<p>業界構造としては、Copilot Studio / Dify / Power Automate の 3 層アーキテクチャが提案標準になりつつあります。失敗事例（製造業のチャットボット利用率 8%）や、はてブで 800 ブクマを集めた「会議は減ったか」議論は、ベンダー言説と現場感覚の乖離を裏テーマとして示しています。</p>
<p>注目すべきカード: <a href="#card-dummy-001">Power Fx 連携</a>、<a href="#card-dummy-002">横浜銀行ボイスボット</a>、<a href="#card-dummy-007">会議論争</a>。</p>
""".strip()


def _generate_dummy_weekly_items() -> list[dict[str, Any]]:
    """ウィークリー一覧 (D-38) のダミーデータ。"""
    return [
        {
            "href": "weekly/2026-W17.html",
            "week_label": "WEEK 17 / 2026",
            "date_range": "2026-04-19 〜 2026-04-25",
            "theme_title": "「導入して終わり」から「内製化・オーケストレーション」へ — 主戦場の第 2 ラウンド",
            "lens": "労働 × 知識民主化",
            "summary_excerpt": "今週は、複数の動きが同じ方向を指している週でした。エージェント・オーケストレーターという新職務、Power Fx 連携、月 1,600 件のボイスボット完結事例。一方で「会議は減っていない」という現場感覚も…",
        },
        {
            "href": "weekly/2026-W16.html",
            "week_label": "WEEK 16 / 2026",
            "date_range": "2026-04-12 〜 2026-04-18",
            "theme_title": "「生成AI導入済み → エージェント化」企業 AI 活用が第 2 段階の競争フェーズへ",
            "lens": "労働 × 知識民主化",
            "summary_excerpt": "Google Cloud は「エージェント・オーケストレーター」という新職務を提唱、AIsmiley は「答える AI と動く AI」の分類論を…",
        },
    ]


def build_index(
    env: Environment,
    cards: list[dict[str, Any]],
    today: date,
    daily_summary: str | None = None,
) -> None:
    iso_year, iso_week, iso_dow = today.isocalendar()
    _render(
        env,
        "index.html.j2",
        SITE_DIR / "index.html",
        cards=cards,
        today_iso=today.isoformat(),
        today_label=_format_today_label(today),
        iso_week=iso_week,
        iso_dow=iso_dow,
        daily_summary=daily_summary,
    )


def build_weekly_index(env: Environment, items: list[dict[str, Any]]) -> None:
    _render(
        env,
        "weekly_index.html.j2",
        SITE_DIR / "weekly" / "index.html",
        items=items,
    )


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

    return {
        "today": today.isoformat(),
        "dummy": dummy,
        "cards": len(cards),
        "weekly_items": len(weekly_items),
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
