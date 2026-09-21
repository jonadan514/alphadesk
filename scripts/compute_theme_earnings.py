"""Phase A-4/B-2: 테마별 실적 축 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §3
Phase A는 미국 시장만 대상이었으나, Phase B에서 한국도 같은 로직으로
처리한다(시장별로 그 시장의 승인된 소속 기업만 순회). 분기 재무제표는
scripts/backfill_quarterly_financials.py로 미리 채워져 있어야 한다
(승인된 테마 매핑 종목만 대상으로 함).

실적 축은 주간 신호가 아니지만(분기에 한 번만 바뀜), 매주 도는 파이프라인이
현재 주 행에 같은 값을 다시 채워 넣는다 - 화면이 그 주의 세 축을 한 행에서
보게 하기 위함(earn_as_of로 "이 값은 지난 분기 것"임을 표시).

Usage:
  python scripts/compute_theme_earnings.py                       # 전체 US+KR 테마
  python scripts/compute_theme_earnings.py --theme-id nuclear_smr  # 특정 테마만
  python scripts/compute_theme_earnings.py --include-peripheral   # peripheral 포함(옵션)
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
from src.db.fundamentals_cache import ensure_schema as ensure_fundamentals_schema, get_cached_financials_bulk
from src.db.theme_signals import (ensure_schema, get_approved_theme_members, get_surprises,
                                   upsert_earn_signal)
from analyzers.theme_earnings import compute_earn_signal, reference_growth_for_market
from collectors.watchlist_collector import get_kr_universe, get_us_universe
from collectors.earnings_surprise_collector import summarize_theme

THEMES_YAML = ROOT / "config" / "themes.yaml"


def _log(msg: str) -> None:
    print(f"[earn] {msg}")


def _current_week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


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
    parser.add_argument("--theme-id", nargs="*", default=None, help="특정 테마만 (비우면 전체)")
    parser.add_argument("--include-peripheral", action="store_true",
                         help="linkage=peripheral도 포함 (SPEC §3.2 옵션 - 기본은 제외)")
    parser.add_argument("--week-start", default=None,
                         help="기준 주 월요일(YYYY-MM-DD). 비우면 오늘이 속한 주 - "
                              "평시 크론(일요일 밤)은 방금 끝난 주를 잡지만, 주 초에 "
                              "수동 실행하면 아직 데이터가 없는 새 주를 잡게 되므로 "
                              "그때 명시적으로 지정하기 위한 옵션.")
    args = parser.parse_args()

    themes, config = load_active_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        sys.exit(1)
    thresholds = config.get("earnings_thresholds", {"strong_up": 0.70, "up": 0.55, "down": 0.45})
    linkages = ("direct", "partial", "peripheral") if args.include_peripheral else ("direct", "partial")

    conn = get_db()
    ensure_fundamentals_schema(conn)
    ensure_schema(conn)

    week_start = args.week_start or _current_week_monday(date.today()).isoformat()

    # (테마, 시장) 쌍별 소속 기업을 먼저 다 모아서, 필요한 티커 전체(US+KR
    # 합쳐)에 대해 재무 캐시를 한 번만 벌크 조회한다 - 개별 조회하면 겹치는
    # 종목(여러 테마 소속)을 중복으로 왕복하게 된다(SPEC §7과 동일한 "배치로"
    # 원칙). US 티커(알파벳)와 KR 티커(6자리 숫자)는 문자열이 겹칠 일이 없어
    # 하나의 집합으로 안전하게 합칠 수 있다.
    members_by_theme_market: dict[tuple[str, str], list[dict]] = {}
    all_tickers: set[str] = set()
    for theme in themes:
        for market in theme.get("markets", []):
            if market not in ("US", "KR"):
                continue
            members = get_approved_theme_members(conn, theme["id"], market, linkages)
            if not members:
                continue
            members_by_theme_market[(theme["id"], market)] = members
            all_tickers.update(m["ticker"] for m in members)

    _log(f"대상 (테마,시장) {len(members_by_theme_market)}개, "
         f"소속 기업(중복제거) {len(all_tickers)}개, 기준 주 {week_start}")

    # 기준 성장률의 표본은 테마 소속이 아니라 **시장 유니버스 전체**다(2026-09-21 수정).
    # 소속 기업이 곧 표본이면 절반이 자동으로 기준 위에 놓여 개선 비율이 0.5 근처로 쏠린다.
    universe_by_market: dict[str, list[str]] = {}
    for market, getter in (("US", get_us_universe), ("KR", get_kr_universe)):
        if not any(mk == market for _, mk in members_by_theme_market):
            continue
        try:
            universe_by_market[market] = [it["symbol"] for it in getter()]
        except Exception as e:  # noqa: BLE001 - 유니버스를 못 읽으면 소속 기업만으로 폴백한다
            _log(f"{market} 유니버스 로드 실패 {type(e).__name__}: {str(e)[:80]} - 소속 기업만으로 기준선 계산")
            universe_by_market[market] = []

    needed = set(all_tickers)
    for tickers in universe_by_market.values():
        needed.update(tickers)

    financials = get_cached_financials_bulk(conn, sorted(needed))
    revenue_by_ticker = {}
    for ticker, data in financials.items():
        if data is None:
            revenue_by_ticker[ticker] = None
            continue
        q_df = data.get("financials_quarterly")
        if q_df is None or q_df.empty or "Total Revenue" not in q_df.index:
            revenue_by_ticker[ticker] = None
            continue
        revenue_by_ticker[ticker] = q_df.loc["Total Revenue"].dropna()

    # 기준 성장률(시장 중앙값)은 반드시 시장별로 따로 낸다 - 미국과 한국의
    # 성장률 분포가 다른데 한 덩어리로 중앙값을 내면 한쪽이 통째로 위/아래로
    # 쏠린다(주가 축에서 시장별 지수를 쓰는 것과 같은 이유).
    reference_by_market: dict[str, float | None] = {}
    for market in {m for _, m in members_by_theme_market}:
        sample = universe_by_market.get(market) or sorted({
            m["ticker"] for (tid, mk), members in members_by_theme_market.items()
            if mk == market for m in members})   # 유니버스를 못 읽었을 때만 소속 기업으로 폴백
        ref = reference_growth_for_market({t: revenue_by_ticker.get(t) for t in sample}, market)
        reference_by_market[market] = ref
        usable = sum(1 for t in sample if revenue_by_ticker.get(t) is not None)
        if ref is None:
            _log(f"{market}: 표본 부족으로 중앙값 산출 불가 - 절대 기준(0%)으로 폴백 "
                 f"(유니버스 {len(sample)}개 중 매출 확보 {usable}개)")
        else:
            _log(f"{market}: 기준 성장률(시장 유니버스 중앙값) {ref*100:.1f}% "
                 f"(유니버스 {len(sample)}개 중 매출 확보 {usable}개)")

    # 실적 발표 서프라이즈(참고 수치). scripts/collect_earnings_surprise.py가 쌓아둔 값만
    # 읽는다 - 여기서 새로 조회하지 않는다(종목별 호출이라 수집은 따로 예산제로 돈다).
    surprises = get_surprises(conn, sorted(all_tickers))
    _log(f"서프라이즈 보유 {len(surprises)}/{len(all_tickers)}종목")

    now = datetime.utcnow().isoformat()
    for (theme_id, market), members in members_by_theme_market.items():
        result = compute_earn_signal(members, revenue_by_ticker, thresholds,
                                      reference_by_market.get(market))
        surprise = summarize_theme(members, surprises)
        run_id = members[0]["run_id"]
        sp_str = (f"{surprise['beat']}/{surprise['n']}" if surprise["n"] else "-")
        _log(f"{theme_id}({market}): members={result['members']} "
             f"기준초과={result['improved']} insufficient={result['insufficient']} "
             f"ratio={result['ratio']} arrow={result['arrow']} as_of={result['as_of']} "
             f"서프라이즈 상회={sp_str}")

        upsert_earn_signal(
            conn, theme_id, market, week_start,
            result["members"], result["improved"], result["insufficient"],
            result["ratio"], result["arrow"], result["as_of"],
            result["members"], run_id, now, surprise,
        )
        conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
