"""승인된 테마 소속 기업의 실적 서프라이즈를 수집해 earnings_surprise에 쌓는다.

실적 축(분기 매출 성장률)은 분기에 한 번만 움직인다. 서프라이즈는 발표 당일 확정되는
값이라 그보다 빠르다. 축을 새로 만들지 않고 실적 축 옆에 붙는 참고 수치로 쓴다
(compute_theme_earnings.py가 읽어 테마 단위로 요약).

yfinance earnings_dates는 종목별 호출이라, 최근 받아둔 종목은 건너뛰고(25일) 한 번에
받는 수도 예산으로 제한한다. 주 1회 실행이면 몇 주 안에 전 종목이 한 바퀴 돌고,
그 뒤로는 분기 발표가 있는 종목만 갱신된다.

Usage:
  python scripts/collect_earnings_surprise.py
  python scripts/collect_earnings_surprise.py --budget 300
  python scripts/collect_earnings_surprise.py --market KR
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import (ensure_schema, get_approved_theme_members, get_surprises,
                                   upsert_surprise)
from collectors.earnings_surprise_collector import DEFAULT_BUDGET, collect_surprises
from collectors.kr_kospi_list import yf_suffix as kr_yf_suffix

THEMES_YAML = ROOT / "config" / "themes.yaml"


def _log(msg: str) -> None:
    print(f"[surprise] {msg}", flush=True)


def to_yf_symbol(ticker: str, market: str) -> str:
    return f"{ticker}{kr_yf_suffix(ticker)}" if market == "KR" else ticker


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--market", choices=["US", "KR"], default=None)
    args = ap.parse_args()

    themes = [t for t in yaml.safe_load(THEMES_YAML.read_text(encoding="utf-8"))["themes"]
              if t.get("status") == "active"]
    conn = get_db()
    ensure_schema(conn)

    targets: dict[str, tuple[str, str, str]] = {}
    for theme in themes:
        for market in theme.get("markets", []):
            if market not in ("US", "KR") or (args.market and market != args.market):
                continue
            for m in get_approved_theme_members(conn, theme["id"], market, ("direct", "partial")):
                targets[m["ticker"]] = (m["ticker"], market, to_yf_symbol(m["ticker"], market))

    known = {t: rec.get("fetched_at") or "" for t, rec in get_surprises(conn, list(targets)).items()}
    fresh = collect_surprises(list(targets.values()), known, budget=args.budget, log=_log)

    now = datetime.utcnow().isoformat()
    for ticker, rec in fresh.items():
        upsert_surprise(conn, ticker, rec["market"], rec.get("report_date"),
                        rec.get("surprise_pct"), rec.get("eps_estimate"),
                        rec.get("eps_reported"), now)
    conn.commit()

    total = len(get_surprises(conn, list(targets)))
    _log(f"저장 {len(fresh)}종목 / 소속 기업 {len(targets)}종목 중 서프라이즈 보유 {total}종목")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
