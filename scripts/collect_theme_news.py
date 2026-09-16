"""Phase A-3/B-1: 테마별 뉴스 수집 + 뉴스 축 신호 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §2
Phase A는 미국 시장만 대상이었으나, Phase B에서 한국(keywords_ko)도 같은
로직으로 처리한다 - 시장별로 그 시장에 해당하는 테마만 순회한다
(themes.yaml의 markets 필드 기준).

weeks-back 하나로 평시 주간 실행과 콜드스타트 백필을 겸한다 - 매주 도는
정상 실행(weeks-back=1)과 최초 8주 백필(weeks-back=8)이 로직상 동일하고
(둘 다 after:/before: 날짜 범위로 특정 주를 조회), 오래된 주부터 최신 주
순서로 처리해야 baseline(직전 8주 중앙값)이 순서대로 쌓이기 때문이다.

Usage:
  python scripts/collect_theme_news.py                        # 이번 주(가장 최근 주)만
  python scripts/collect_theme_news.py --weeks-back 8          # 콜드스타트 백필
  python scripts/collect_theme_news.py --theme-id nuclear_smr  # 특정 테마만
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import ensure_schema, insert_theme_news_bulk, get_prior_news_counts, upsert_news_signal
from collectors.theme_news_collector import collect_theme_news

THEMES_YAML = ROOT / "config" / "themes.yaml"


def _log(msg: str) -> None:
    print(f"[news] {msg}")


def _current_week_monday(today: date) -> date:
    """today가 속한 주(월~일)의 월요일 날짜."""
    return today - timedelta(days=today.weekday())


BASELINE_WEEKS = 8      # 기준선을 만들 때 참고하는 직전 주 수
BASELINE_MIN_WEEKS = 4  # 이만큼도 없으면 판정 보류


def compute_news_arrow(news_count: int, min_articles: int, prior_counts: list[int],
                        thresholds: dict) -> tuple[float | None, float | None, str]:
    """SPEC §2.3 판정 로직. 반환: (baseline, ratio, arrow).

    기준선은 직전 8주의 **중앙값**이다(2026-09-16 변경, 이전에는 직전 4주 평균).
    평균 4주는 한 주 급증이 그다음 4주의 기준선을 통째로 끌어올려, 테마가 실제로
    달아오르는 구간에서 오히려 화살표가 죽는 문제가 있었다. 중앙값은 그 급증 주를
    한 표로만 세고, 8주로 넓히면 기준선 자체가 덜 출렁인다.
    """
    if len(prior_counts) < BASELINE_MIN_WEEKS:
        return None, None, "na"
    baseline = statistics.median(prior_counts)
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

    KEYWORD_FIELD = {"US": "keywords_en", "KR": "keywords_ko"}

    for market, keyword_field in KEYWORD_FIELD.items():
        market_themes = [t for t in themes if market in t.get("markets", [])]
        _log(f"대상 테마 {len(market_themes)}개({market}), 처리 주 {len(weeks)}개 "
             f"({weeks[0].isoformat()} ~ {weeks[-1].isoformat()})")

        for theme in market_themes:
            theme_id = theme["id"]
            keywords = theme.get(keyword_field, [])
            if not keywords:
                _log(f"{theme_id}({market}): {keyword_field} 없음 - 건너뜀")
                continue
            min_articles = theme.get("min_articles", default_min_articles)
            # 키워드가 바뀐 테마는 바뀐 주 이전 건수를 기준선에 쓰지 않는다(유지보수 규칙 2).
            # 기준선 최소 4주가 쌓일 때까지 뉴스 축은 na(데이터부족)로 남는다 - 탈락이 아니다.
            kw_changed = theme.get("keywords_changed_at")
            since = None
            if kw_changed:
                kc = kw_changed if isinstance(kw_changed, date) else date.fromisoformat(str(kw_changed))
                since = _current_week_monday(kc).isoformat()

            for week_start in weeks:
                week_end = week_start + timedelta(days=7)  # before: 는 배타적이라 +7로 일요일까지 포함
                backfilled = week_start != current_week

                articles, stats = collect_theme_news(keywords, week_start, week_end, market=market)
                insert_theme_news_bulk(conn, theme_id, market, week_start.isoformat(), articles)
                news_count = len(articles)
                _log(f"{theme_id}({market}) {week_start.isoformat()}: 원본 {stats['raw_total']}건 -> "
                     f"URL중복제거후 {stats['after_url_dedup']}건 -> 제목중복제거후 {news_count}건 "
                     f"(키워드별 {stats['per_keyword']})")

                prior_counts = get_prior_news_counts(conn, theme_id, market, week_start.isoformat(),
                                                     weeks=BASELINE_WEEKS, since=since)
                baseline, ratio, arrow = compute_news_arrow(news_count, min_articles, prior_counts, thresholds)
                ratio_str = f"{ratio:.2f}" if ratio is not None else "-"
                baseline_str = f"{baseline:.1f}" if baseline is not None else "-"
                _log(f"  -> baseline={baseline_str} ratio={ratio_str} arrow={arrow} "
                     f"(backfilled={backfilled}, 직전주 {len(prior_counts)}개 확보"
                     f"{', 키워드 변경 ' + since + ' 이후만' if since else ''})")

                upsert_news_signal(
                    conn, theme_id, market, week_start.isoformat(), news_count, baseline,
                    ratio, arrow, backfilled, datetime.utcnow().isoformat(),
                )
                conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
