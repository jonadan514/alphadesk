"""Phase A-5/B-3: 테마별 주가 축 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §4
Phase A는 미국 시장만 대상이었으나(^GSPC), Phase B에서 한국(^KS11, KOSPI)을
추가한다 - SPEC §4.1의 "시장 지수는 US=S&P 500, KR=KOSPI로 각각 비교한다"
그대로. 시장별로 그 시장의 지수와 비교해야 코리아 디스카운트 같은 시장 간
구조적 차이가 신호를 오염시키지 않는다.

Usage:
  python scripts/compute_theme_price.py                        # 전체 US+KR 테마
  python scripts/compute_theme_price.py --theme-id nuclear_smr   # 특정 테마만
  python scripts/compute_theme_price.py --include-peripheral     # peripheral 포함(옵션)
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
from src.db.theme_signals import ensure_schema, get_approved_theme_members, upsert_price_signal
from analyzers.theme_price import compute_price_signal
from collectors.theme_price_collector import compute_price_batch
from collectors.kr_kospi_list import yf_suffix as kr_yf_suffix

THEMES_YAML = ROOT / "config" / "themes.yaml"

# SPEC §4.1 - 시장별로 그 시장의 지수와 비교한다. ^KS11(KOSPI)은
# kr_sector_analyzer.py가 이미 쓰고 있는, 검증된 티커.
INDEX_SYMBOL = {"US": "^GSPC", "KR": "^KS11"}


def _log(msg: str) -> None:
    print(f"[price] {msg}")


def _current_week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def to_yf_symbol(ticker: str, market: str) -> str:
    """theme_members.ticker(캐시 키)를 yfinance 조회용 심볼로 변환.
    US는 동일. KR은 6자리 코드라 거래소 접미사가 필요하고, 코스피(.KS)/
    코스닥(.KQ)을 정확히 구분해야 한다 - 코스닥 종목에 .KS를 붙이면
    yfinance가 에러 없이 **다른 가격 시계열**을 돌려준다(2026-09-07 발견,
    kr_kospi_list.py 주석 참고)."""
    return ticker if market != "KR" else f"{ticker}{kr_yf_suffix(ticker)}"


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
                         help="linkage=peripheral도 포함 (SPEC §10 옵션 - 기본은 제외)")
    parser.add_argument("--week-start", default=None,
                         help="기준 주 월요일(YYYY-MM-DD). 비우면 오늘이 속한 주 - "
                              "주 초에 수동 실행할 때 아직 데이터가 없는 새 주를 잡지 "
                              "않도록 명시적으로 지정하기 위한 옵션.")
    args = parser.parse_args()

    themes, config = load_active_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        sys.exit(1)
    thresholds = config.get("price_thresholds", {"strong_up": 0.08, "up": 0.03, "down": -0.03})
    linkages = ("direct", "partial", "peripheral") if args.include_peripheral else ("direct", "partial")

    conn = get_db()
    ensure_schema(conn)

    week_start = args.week_start or _current_week_monday(date.today()).isoformat()

    members_by_theme_market: dict[tuple[str, str], list[dict]] = {}
    yf_symbols: set[str] = set()
    for theme in themes:
        for market in theme.get("markets", []):
            if market not in INDEX_SYMBOL:
                continue
            members = get_approved_theme_members(conn, theme["id"], market, linkages)
            if not members:
                continue
            members_by_theme_market[(theme["id"], market)] = members
            yf_symbols.update(to_yf_symbol(m["ticker"], market) for m in members)

    _log(f"대상 (테마,시장) {len(members_by_theme_market)}개, "
         f"소속 기업(중복제거) {len(yf_symbols)}개, 기준 주 {week_start}")

    # 지수(^GSPC/^KS11)도 같은 배치 호출에 얹어서 조회 - 종목별 개별 호출 금지(SPEC §4.3).
    query_symbols = sorted(yf_symbols) + sorted(INDEX_SYMBOL.values())
    raw = compute_price_batch(query_symbols)
    raw_returns = {k: v["ret"] for k, v in raw.items()}

    index_returns = {mkt: raw_returns.get(sym) for mkt, sym in INDEX_SYMBOL.items()}
    for mkt, ret in index_returns.items():
        if ret is None:
            _log(f"⚠ {INDEX_SYMBOL[mkt]} 수익률 조회 실패 - {mkt} 테마는 전부 na로 처리됨")

    now = datetime.utcnow().isoformat()
    for (theme_id, market), members in members_by_theme_market.items():
        # compute_price_signal은 원본 ticker 키로 조회하므로, yf 심볼로 받은
        # 결과를 이 테마의 티커 기준으로 되돌려 넘긴다.
        returns_by_ticker = {
            m["ticker"]: raw_returns.get(to_yf_symbol(m["ticker"], market)) for m in members
        }
        vol_by_ticker = {
            m["ticker"]: (raw.get(to_yf_symbol(m["ticker"], market)) or {}).get("vol_ratio")
            for m in members
        }
        index_return = index_returns[market]

        result = compute_price_signal(members, returns_by_ticker, index_return, thresholds,
                                      vol_by_ticker)
        run_id = members[0]["run_id"]
        median_str = f"{result['median_ret']:.3f}" if result["median_ret"] is not None else "-"
        excess_str = f"{result['excess']:.3f}" if result["excess"] is not None else "-"
        vol_str = f"{result['volume_ratio']:.2f}" if result.get("volume_ratio") is not None else "-"
        _log(f"{theme_id}({market}): valid={result['valid_count']}/{len(members)} "
             f"median={median_str} index={index_return} excess={excess_str} arrow={result['arrow']} "
             f"거래대금비={vol_str}")

        upsert_price_signal(
            conn, theme_id, market, week_start,
            result["median_ret"], result["index_ret"], result["excess"], result["arrow"],
            len(members), run_id, now, result.get("volume_ratio"),
        )
        conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
