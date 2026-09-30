"""quarterly_company_signals에 실제로 쌓인 회사별 신호를 보여준다 (분기 재설계 5장 점검용).

**읽기 전용이다.** 아무것도 쓰지 않는다. compute_quarterly_classification.py가 회사별
결과를 제대로 저장했는지(값·타입·데이터부족 처리) 눈으로 확인하려고 만들었다 -
화면(8장 "소속 기업 카드")이 실제로 쓰게 될 형태 그대로 보여준다.

Usage:
  python scripts/inspect_quarterly_company_signals.py --quarter 2026Q3
  python scripts/inspect_quarterly_company_signals.py --quarter 2026Q3 --theme-id battery --market KR
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.quarterly_company_signals import get_theme_company_signals
from src.db.theme_signals import get_approved_theme_members


def _log(msg: str) -> None:
    print(msg, flush=True)


def parse_quarter(text: str) -> tuple[int, int]:
    y, q = text.upper().split("Q")
    return int(y), int(q)


def fmt(v, digits=1) -> str:
    return "-" if v is None else f"{v:,.{digits}f}"


def show_theme(conn, theme_id: str, market: str, target: tuple[int, int]) -> int:
    rows = get_theme_company_signals(conn, theme_id, market, target[0], target[1])
    if not rows:
        _log(f"{theme_id}({market}): 저장된 행 없음")
        return 0

    _log(f"\n=== {theme_id}({market}) - {len(rows)}개 기업 ===")
    _log(f"{'티커':<10}{'매출전환':>8}{'매출흐름':>8}{'이익전환':>8}{'변화':>6} "
         f"{'PSR':>12} {'PER':>12}  등급")
    for r in rows:
        def b(v):
            return "-" if v is None else ("O" if v else "X")
        _log(f"{r['ticker']:<10}{b(r['revenue_transition']):>8}{b(r['revenue_flow']):>8}"
             f"{b(r['profit_transition']):>8}{b(r['changed']):>6} "
             f"{fmt(r['psr'], 2):>12} {fmt(r['per'], 1):>12}  {r['valuation_tier'] or '-'}")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarter", required=True, help="예: 2026Q3")
    ap.add_argument("--theme-id", nargs="*", default=None, help="비우면 매핑 승인된 테마 중 몇 개 표본")
    ap.add_argument("--market", default=None, choices=["KR", "US"])
    args = ap.parse_args()

    target = parse_quarter(args.quarter)
    conn = get_db()
    markets = [args.market] if args.market else ["KR", "US"]

    total = 0
    for market in markets:
        if args.theme_id:
            theme_ids = args.theme_id
        else:
            # 표본: 이 시장에서 승인된 매핑이 있는 테마 중 앞 3개만 - 전체를 다 찍으면
            # 화면이 너무 길어진다(점검용이라 몇 개만 봐도 충분하다).
            rows = conn.execute(
                "SELECT DISTINCT theme_id FROM theme_members WHERE approved = 1 AND market = ? "
                "ORDER BY theme_id LIMIT 3", (market,)
            ).fetchall()
            theme_ids = [r[0] for r in rows]
            if not theme_ids:
                _log(f"{market}: 승인된 매핑이 있는 테마 없음 - 건너뜀")
                continue

        for theme_id in theme_ids:
            total += show_theme(conn, theme_id, market, target)

    if total == 0:
        _log("\n저장된 행이 하나도 없다 - compute_quarterly_classification.py를 먼저 돌릴 것.")
        return 1

    _log(f"\n총 {total}행 확인.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
