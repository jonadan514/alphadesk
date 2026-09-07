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
from src.db.theme_signals import ensure_schema, get_approved_theme_members, upsert_earn_signal
from analyzers.theme_earnings import compute_earn_signal

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

    week_start = _current_week_monday(date.today()).isoformat()

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

    financials = get_cached_financials_bulk(conn, sorted(all_tickers))
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

    now = datetime.utcnow().isoformat()
    for (theme_id, market), members in members_by_theme_market.items():
        result = compute_earn_signal(members, revenue_by_ticker, thresholds)
        run_id = members[0]["run_id"]
        _log(f"{theme_id}({market}): members={result['members']} improved={result['improved']} "
             f"insufficient={result['insufficient']} ratio={result['ratio']} "
             f"arrow={result['arrow']} as_of={result['as_of']}")

        upsert_earn_signal(
            conn, theme_id, market, week_start,
            result["members"], result["improved"], result["insufficient"],
            result["ratio"], result["arrow"], result["as_of"],
            result["members"], run_id, now,
        )
        conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
