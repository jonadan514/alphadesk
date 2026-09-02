"""Phase A-5: 테마별 주가 축 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §4
Phase A는 미국 시장만 대상 - 시장지수는 S&P 500(^GSPC).

Usage:
  python scripts/compute_theme_price.py                        # 전체 US 테마
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
from collectors.theme_price_collector import compute_return_batch

THEMES_YAML = ROOT / "config" / "themes.yaml"
US_INDEX_SYMBOL = "^GSPC"


def _log(msg: str) -> None:
    print(f"[price] {msg}")


def _current_week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def load_active_us_themes(theme_ids: list[str] | None) -> tuple[list[dict], dict]:
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    themes = [t for t in data["themes"] if t.get("status") == "active" and "US" in t.get("markets", [])]
    if theme_ids:
        wanted = set(theme_ids)
        themes = [t for t in themes if t["id"] in wanted]
    return themes, data.get("config", {})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme-id", nargs="*", default=None, help="특정 테마만 (비우면 전체)")
    parser.add_argument("--include-peripheral", action="store_true",
                         help="linkage=peripheral도 포함 (SPEC §10 옵션 - 기본은 제외)")
    args = parser.parse_args()

    themes, config = load_active_us_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        sys.exit(1)
    thresholds = config.get("price_thresholds", {"strong_up": 0.08, "up": 0.03, "down": -0.03})
    linkages = ("direct", "partial", "peripheral") if args.include_peripheral else ("direct", "partial")

    conn = get_db()
    ensure_schema(conn)

    week_start = _current_week_monday(date.today()).isoformat()

    members_by_theme: dict[str, list[dict]] = {}
    all_tickers: set[str] = set()
    for theme in themes:
        members = get_approved_theme_members(conn, theme["id"], "US", linkages)
        members_by_theme[theme["id"]] = members
        all_tickers.update(m["ticker"] for m in members)

    _log(f"대상 테마 {len(themes)}개, 소속 기업(중복제거) {len(all_tickers)}개, 기준 주 {week_start}")

    # 지수(^GSPC)도 같은 배치 호출에 얹어서 조회 - 종목별 개별 호출 금지(SPEC §4.3).
    query_tickers = sorted(all_tickers) + [US_INDEX_SYMBOL]
    returns = compute_return_batch(query_tickers)
    index_return = returns.get(US_INDEX_SYMBOL)
    if index_return is None:
        _log(f"⚠ {US_INDEX_SYMBOL} 수익률 조회 실패 - 이번 실행은 전 테마 na로 처리됨")

    now = datetime.utcnow().isoformat()
    for theme in themes:
        theme_id = theme["id"]
        members = members_by_theme[theme_id]
        if not members:
            _log(f"{theme_id}: 승인된 소속 기업 없음 - 건너뜀")
            continue

        result = compute_price_signal(members, returns, index_return, thresholds)
        run_id = members[0]["run_id"]
        median_str = f"{result['median_ret']:.3f}" if result["median_ret"] is not None else "-"
        excess_str = f"{result['excess']:.3f}" if result["excess"] is not None else "-"
        _log(f"{theme_id}: valid={result['valid_count']}/{len(members)} "
             f"median={median_str} index={index_return} excess={excess_str} arrow={result['arrow']}")

        upsert_price_signal(
            conn, theme_id, "US", week_start,
            result["median_ret"], result["index_ret"], result["excess"], result["arrow"],
            len(members), run_id, now,
        )
        conn.commit()

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
