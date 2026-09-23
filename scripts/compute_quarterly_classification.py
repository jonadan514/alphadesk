"""분기 4칸 분류 실행 (분기 재설계 docs/REDESIGN_SPEC.md 9장, 10장 8단계).

파이프라인의 마지막 계산 단계다. 승인된 매핑의 소속 기업마다 분기 재무를 읽어 변화
신호를 계산하고(5장), 테마 단위로 모아 재무 신호를 내고(7-1), 뉴스 분기 비율(6-3)과
합쳐 4칸으로 분류해(7-3) 저장한다. 시장 유니버스 전체의 매출 증가율 중앙값(5-1 화면
참고값)도 함께 낸다.

## 이 스크립트가 하지 않는 일 (먼저 끝나 있어야 한다)

  - DART·yfinance 분기 재무 수집: collect_kr_quarterly_financials.py 등.
  - 뉴스 분기 집계 재료 쌓기: 주간 뉴스 수집(collect_theme_news.py)과
    백필(backfill_theme_news_counts.py).
  - 테마 매핑 승인: approve_theme_mapping.py.
  이 셋이 안 된 테마·기업은 실패가 아니라 데이터부족으로 나올 뿐이다(원칙 4).

## 배치로 묶어 읽는다

테마 소속 기업과 유니버스 전체(수백 종목)를 종목마다 select_quarters()로 조회하면
운영 DB(Turso HTTP)에 종목 수만큼 왕복이 쌓인다. 시장 하나당 필요한 티커를 전부
모아 select_quarters_bulk() 한 번으로 가져온다(compute_theme_earnings.py의 기존
"배치로" 원칙과 같다).

Usage:
  python scripts/compute_quarterly_classification.py                   # 막 끝난 분기
  python scripts/compute_quarterly_classification.py --quarter 2026Q3  # 특정 분기(진행 중이어도 됨 - 점검용)
  python scripts/compute_quarterly_classification.py --theme-id battery
  python scripts/compute_quarterly_classification.py --market KR
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

from src.analyzers import quarterly_thresholds as qt
from src.analyzers.company_change_signals import (change_company, market_median_revenue_growth,
                                                   revenue_yoy_growth)
from src.analyzers.theme_news_quarterly import aggregate_quarters, news_ratio, prior_quarters, quarter_of
from src.analyzers.theme_quarterly_classification import classify, financial_signal
from src.db.data_store import get_db
from src.db.quarterly_classification import (ensure_schema as ensure_classification_schema,
                                              upsert_classification, upsert_market_reference)
from src.db.quarterly_financials import (ensure_schema as ensure_financials_schema,
                                         select_quarters_bulk)
from src.db.theme_signals import (ensure_schema as ensure_signals_schema,
                                  get_approved_theme_members, get_weekly_news_counts)
from collectors.watchlist_collector import get_kr_universe, get_us_universe

THEMES_YAML = ROOT / "config" / "themes.yaml"
UNIVERSE_GETTER = {"KR": get_kr_universe, "US": get_us_universe}


def _log(msg: str) -> None:
    print(f"[quarterly-classify] {msg}", flush=True)


def load_active_themes(theme_ids: list[str] | None) -> list[dict]:
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    themes = [t for t in data["themes"] if t.get("status") == "active"]
    if theme_ids:
        wanted = set(theme_ids)
        themes = [t for t in themes if t["id"] in wanted]
    return themes


def parse_quarter(text: str) -> tuple[int, int]:
    y, q = text.upper().split("Q")
    return int(y), int(q)


def previous_quarter(today: date) -> tuple[int, int]:
    """막 끝난 분기. 분기 시작일(예: 10/1)에 돌리는 게 기본 쓰임새라, "오늘이 속한
    분기"가 아니라 그 앞 분기를 돌려준다."""
    return prior_quarters(*quarter_of(today), n=1)[0]


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def news_since(theme: dict) -> str | None:
    """키워드가 바뀐 테마는 바뀌기 전 이력과 잇지 않는다(themes.yaml 유지보수 규칙 2)."""
    kw_changed = theme.get("keywords_changed_at")
    if not kw_changed:
        return None
    kc = kw_changed if isinstance(kw_changed, date) else date.fromisoformat(str(kw_changed))
    return week_monday(kc).isoformat()


def compute_market_reference(quarters_by_ticker: dict[str, list[dict]],
                             universe_tickers: list[str]) -> dict:
    """시장 유니버스 전체의 매출 증가율 중앙값 (5-1 화면 참고값 - 판정에는 쓰지 않는다)."""
    growths = [revenue_yoy_growth(quarters_by_ticker.get(t, [])) for t in universe_tickers]
    median = market_median_revenue_growth(growths)
    sample = sum(1 for g in growths if g is not None)
    return {"median": median, "sample": sample}


def compute_theme(theme: dict, market: str, members: list[dict],
                  quarters_by_ticker: dict[str, list[dict]], conn, target: tuple[int, int],
                  config: dict) -> dict:
    """테마 하나의 재무 신호 + 뉴스 비율 + 4칸 분류."""
    flags = [change_company(quarters_by_ticker.get(m["ticker"], []), config)["changed"]
             for m in members]
    financial = financial_signal(flags, config)

    weekly = get_weekly_news_counts(conn, theme["id"], market, since=news_since(theme))
    quarters = aggregate_quarters(weekly)
    news = news_ratio(quarters, target)
    news_high = qt.is_news_high(news["ratio"], market, config)

    label = classify(financial["on"], news_high)
    return {
        "financial": financial,
        "news": {"high": news_high, "ratio": news["ratio"], "this_quarter": news["this_quarter"]},
        "classification": label,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarter", default=None, help="예: 2026Q3 (비우면 막 끝난 분기)")
    ap.add_argument("--theme-id", nargs="*", default=None, help="특정 테마만 (비우면 전체)")
    ap.add_argument("--market", default=None, choices=["KR", "US"])
    ap.add_argument("--include-peripheral", action="store_true",
                    help="linkage=peripheral도 포함 (기본은 제외)")
    args = ap.parse_args()

    target = parse_quarter(args.quarter) if args.quarter else previous_quarter(date.today())
    themes = load_active_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        return 1
    linkages = ("direct", "partial", "peripheral") if args.include_peripheral else ("direct", "partial")
    markets = [args.market] if args.market else ["KR", "US"]
    config = qt.load()
    now = datetime.utcnow().isoformat()

    conn = get_db()
    ensure_financials_schema(conn)
    ensure_signals_schema(conn)
    ensure_classification_schema(conn)

    _log(f"대상 분기 {target[0]}Q{target[1]}")

    for market in markets:
        theme_members: dict[str, list[dict]] = {}
        all_tickers: set[str] = set()
        for theme in themes:
            if market not in theme.get("markets", []):
                continue
            members = get_approved_theme_members(conn, theme["id"], market, linkages)
            if not members:
                _log(f"  {theme['id']}({market}): 승인된 소속 기업 없음 - 건너뜀")
                continue
            theme_members[theme["id"]] = members
            all_tickers.update(m["ticker"] for m in members)

        if not theme_members:
            _log(f"{market}: 승인된 매핑이 있는 테마가 없음 - 건너뜀")
            continue

        try:
            universe_tickers = [it["symbol"] for it in UNIVERSE_GETTER[market]()]
        except Exception as e:  # noqa: BLE001 - 유니버스를 못 읽어도 테마 분류는 계속한다
            _log(f"{market} 유니버스 로드 실패 {type(e).__name__}: {str(e)[:80]} - 참고값 생략")
            universe_tickers = []

        needed = sorted(all_tickers | set(universe_tickers))
        quarters_by_ticker = select_quarters_bulk(conn, needed, market)
        _log(f"{market}: 대상 테마 {len(theme_members)}개, 소속 기업(중복제거) {len(all_tickers)}개, "
             f"유니버스 {len(universe_tickers)}개, 분기 재무 확보 {len(quarters_by_ticker)}종목")

        ref = compute_market_reference(quarters_by_ticker, universe_tickers)
        upsert_market_reference(conn, market, target[0], target[1], ref["median"], ref["sample"], now)
        ref_display = f"{ref['median'] * 100:.1f}%" if ref["median"] is not None else "계산불가"
        _log(f"{market} 매출 증가율 중앙값(참고, 판정에는 안 씀): {ref_display} (표본 {ref['sample']}개)")

        stats = {"classified": 0, "na": 0}
        by_label: dict[str, int] = {}
        for theme in themes:
            if theme["id"] not in theme_members:
                continue
            result = compute_theme(theme, market, theme_members[theme["id"]], quarters_by_ticker,
                                   conn, target, config)
            upsert_classification(conn, theme["id"], market, target[0], target[1],
                                  financial=result["financial"], news=result["news"],
                                  classification=result["classification"], computed_at=now)

            fin, news, label = result["financial"], result["news"], result["classification"]
            fin_display = f"{fin['on']}({fin['changed']}/{fin['judged']})"
            news_ratio_display = f"{news['ratio']:.2f}" if news["ratio"] is not None else "-"
            news_display = f"{news['high']}({news_ratio_display})"
            _log(f"  {theme['id']}({market}): 재무 {fin_display} 뉴스 {news_display} -> {label}")

            if label is None:
                stats["na"] += 1
            else:
                stats["classified"] += 1
                by_label[label] = by_label.get(label, 0) + 1
        conn.commit()

        label_summary = ", ".join(f"{k} {v}" for k, v in by_label.items()) or "-"
        _log(f"{market} 완료 - 분류 {stats['classified']}개({label_summary}), "
             f"데이터부족 {stats['na']}개")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
