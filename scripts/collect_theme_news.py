"""Phase A-3: 테마별 뉴스 수집 + 뉴스 축 신호 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §2
Phase A는 미국 시장만 대상으로 한다(한국은 Phase B).

weeks-back 하나로 평시 주간 실행과 콜드스타트 백필을 겸한다 - 매주 도는
정상 실행(weeks-back=1)과 최초 8주 백필(weeks-back=8)이 로직상 동일하고
(둘 다 after:/before: 날짜 범위로 특정 주를 조회), 오래된 주부터 최신 주
순서로 처리해야 baseline(직전 4주 평균)이 순서대로 쌓이기 때문이다.

Usage:
  python scripts/collect_theme_news.py                        # 이번 주(가장 최근 주)만
  python scripts/collect_theme_news.py --weeks-back 8          # 콜드스타트 백필
  python scripts/collect_theme_news.py --theme-id nuclear_smr  # 특정 테마만
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import ensure_schema, insert_theme_news, get_prior_news_counts, upsert_news_signal
from collectors.theme_news_collector import collect_theme_news

THEMES_YAML = ROOT / "config" / "themes.yaml"


def _log(msg: str) -> None:
    print(f"[news] {msg}")


def _current_week_monday(today: date) -> date:
    """today가 속한 주(월~일)의 월요일 날짜."""
    return today - timedelta(days=today.weekday())


def compute_news_arrow(news_count: int, min_articles: int, prior_counts: list[int],
                        thresholds: dict) -> tuple[float | None, float | None, str]:
    """SPEC §2.3 판정 로직. 반환: (baseline, ratio, arrow)."""
    if len(prior_counts) < 4:
        return None, None, "na"
    baseline = sum(prior_counts) / len(prior_counts)
    if news_count < min_articles or baseline == 0:
        return baseline, None, "na"
    ratio = news_count / baseline
    if ratio >= thresholds.get("strong_up", 2.0):
        arrow = "up2"
    elif ratio >= thresholds.get("up", 1.3):
        arrow = "up1"
    elif ratio <= thresholds.get("down", 0.7):
        arrow = "down"
    else:
        arrow = "flat"
    return baseline, ratio, arrow


def load_active_themes(theme_ids: list[str] | None) -> tuple[list[dict], dict]:
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    themes = [t for t in data["themes"] if t.get("status") == "active"]
    if theme_ids:
        wanted = set(theme_ids)
        themes = [t for t in themes if t["id"] in wanted]
    return themes, data.get("config", {})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weeks-back", type=int, default=1,
                         help="처리할 주 수 (1=이번 주만, 8=콜드스타트 백필)")
    parser.add_argument("--theme-id", nargs="*", default=None, help="특정 테마만 (비우면 전체)")
    args = parser.parse_args()

    themes, config = load_active_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        sys.exit(1)
    default_min_articles = config.get("default_min_articles", 10)
    thresholds = config.get("news_thresholds", {"strong_up": 2.0, "up": 1.3, "down": 0.7})

    conn = get_db()
    ensure_schema(conn)

    current_week = _current_week_monday(date.today())
    weeks = [current_week - timedelta(weeks=i) for i in range(args.weeks_back - 1, -1, -1)]

    us_themes = [t for t in themes if "US" in t.get("markets", [])]
    _log(f"대상 테마 {len(us_themes)}개(US), 처리 주 {len(weeks)}개 "
         f"({weeks[0].isoformat()} ~ {weeks[-1].isoformat()})")

    for theme in us_themes:
        theme_id = theme["id"]
        keywords = theme.get("keywords_en", [])
        if not keywords:
            _log(f"{theme_id}: keywords_en 없음 - 건너뜀")
            continue
        min_articles = theme.get("min_articles", default_min_articles)

        for week_start in weeks:
            week_end = week_start + timedelta(days=7)  # before: 는 배타적이라 +7로 일요일까지 포함
            backfilled = week_start != current_week

            articles, stats = collect_theme_news(keywords, week_start, week_end)
            for a in articles:
                insert_theme_news(
                    conn, theme_id, "US", a["_url_hash"], a["title"], a["url"],
                    a["published_at"], a["source"], week_start.isoformat(),
                )
            news_count = len(articles)
            _log(f"{theme_id} {week_start.isoformat()}: 원본 {stats['raw_total']}건 -> "
                 f"URL중복제거후 {stats['after_url_dedup']}건 -> 제목중복제거후 {news_count}건 "
                 f"(키워드별 {stats['per_keyword']})")

            prior_counts = get_prior_news_counts(conn, theme_id, "US", week_start.isoformat(), weeks=4)
            baseline, ratio, arrow = compute_news_arrow(news_count, min_articles, prior_counts, thresholds)

            upsert_news_signal(
                conn, theme_id, "US", week_start.isoformat(), news_count, baseline,
                ratio, arrow, backfilled, datetime.utcnow().isoformat(),
            )
            conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
