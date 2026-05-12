"""
백테스트 실행 스크립트
Usage:
  python scripts/run_backtest.py
  python scripts/run_backtest.py --run-id bt_custom --rebal 5 --top-n 20
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio.backtest_engine import run_backtest

PRICES_CSV = str(ROOT / "data" / "us_daily_prices.csv")


def main():
    parser = argparse.ArgumentParser(description="백테스트 실행")
    parser.add_argument("--run-id",  default=f"bt_{datetime.today().strftime('%Y%m%d')}",
                        help="결과 구분 ID (기본: bt_오늘날짜)")
    parser.add_argument("--rebal",   type=int, default=5,
                        help="리밸런싱 주기 (거래일 수, 기본 5=주 1회)")
    parser.add_argument("--top-n",   type=int, default=20,
                        help="매수 대상 상위 종목 수 (기본 20)")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print(f"  백테스트  |  run_id={args.run_id}")
    print(f"  리밸런싱: 매 {args.rebal}거래일  |  상위 {args.top_n}종목")
    print("=" * 60)

    summary = run_backtest(
        run_id     = args.run_id,
        prices_csv = PRICES_CSV,
        rebal_freq = args.rebal,
        top_n      = args.top_n,
    )

    elapsed = time.time() - t0
    print("=" * 60)
    print(f"  완료  |  소요: {elapsed:.1f}초")
    print()
    print(f"{'전략':<20}  {'수익률':>8}  {'MDD':>8}  {'승률':>7}  {'거래수':>6}")
    print("-" * 60)
    for pid, s in summary.items():
        ret  = f"{s['total_return']*100:+.2f}%"
        mdd  = f"{s['mdd']*100:.2f}%"
        wr   = f"{s['win_rate']*100:.1f}%" if s['win_rate'] is not None else "  N/A"
        cnt  = str(s['trade_count'])
        print(f"{pid:<20}  {ret:>8}  {mdd:>8}  {wr:>7}  {cnt:>6}")
    print("=" * 60)
    print(f"  결과는 DB에 저장됨  (run_id: {args.run_id})")
    print(f"  프론트엔드 /backtest 탭에서 확인하세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()
