"""한국 기업 분기 재무(매출·영업이익·순이익)를 DART에서 모아 quarterly_financials에 저장한다.

분기 재설계 docs/REDESIGN_SPEC.md 4-1. 계산 규칙은 src/collectors/dart_financials.py.

최근 5분기가 필요하므로 올해·작년 보고서를 먼저 받고, 5분기가 안 모이면 재작년까지 받는다
(연초에는 작년 사업보고서가 아직 안 나와서 최신 분기가 재작년 3분기일 수 있다).
기업당 8-12회 호출이라 KR 유니버스 664종목이면 약 6,000-8,000회 - DART 일일 한도(2만) 안이다.

Usage:
  python scripts/collect_kr_quarterly_financials.py --tickers 005930 086520   # 몇 종목만 + 표 출력
  python scripts/collect_kr_quarterly_financials.py                           # KR 유니버스 전체
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.quarterly_financials import ensure_schema, get_quarters, upsert_quarter
from collectors import dart_client as dart
from collectors.dart_financials import REPORT_CODES, latest_quarters, quarterly_values

CORP_CACHE = ROOT / "data" / "dart_corp_codes.json"
UNIVERSE = ROOT / "data" / "kr_universe.json"
CALL_SLEEP = 0.12  # DART 분당 요청 제한 여유


def _log(msg: str) -> None:
    print(f"[dart-fin] {msg}", flush=True)


def collect_one(corp_code: str, today: date) -> dict:
    reports: dict = {}
    for year in (today.year, today.year - 1):
        for code in REPORT_CODES:
            reports[(year, code)] = dart.fetch_key_accounts(corp_code, year, code)
            time.sleep(CALL_SLEEP)
    values = quarterly_values(reports)
    if len(latest_quarters(values)) < 5:
        year = today.year - 2
        for code in REPORT_CODES:
            reports[(year, code)] = dart.fetch_key_accounts(corp_code, year, code)
            time.sleep(CALL_SLEEP)
        values = quarterly_values(reports)
    return values


def fmt_eok(v) -> str:
    """원 -> 억원(표 확인용)."""
    return "-" if v is None else f"{v / 1e8:,.0f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", default=None, help="종목코드 몇 개만 (확인용)")
    ap.add_argument("--limit", type=int, default=None, help="유니버스 앞에서 N개만")
    args = ap.parse_args()

    universe = {i["symbol"]: i for i in json.loads(UNIVERSE.read_text(encoding="utf-8"))["items"]}
    tickers = args.tickers or sorted(universe)
    if args.limit:
        tickers = tickers[:args.limit]

    corp = dart.load_corp_codes(CORP_CACHE)
    _log(f"기업코드 매핑 {len(corp)}건 / 대상 {len(tickers)}종목")

    conn = get_db()
    ensure_schema(conn)
    today = date.today()
    now = datetime.utcnow().isoformat()
    stats = {"ok": 0, "no_corp": 0, "no_data": 0, "lt5": 0, "error": 0, "ofs": 0}

    for n, t in enumerate(tickers, 1):
        cc = corp.get(t)
        if not cc:
            stats["no_corp"] += 1
            _log(f"  {t} {universe.get(t, {}).get('name', '')}: DART 기업코드 없음")
            continue
        try:
            values = collect_one(cc, today)
        except dart.DartKeyError:
            raise
        except Exception as e:  # noqa: BLE001 - 한 종목 실패로 전체를 멈추지 않는다
            stats["error"] += 1
            _log(f"  {t}: 실패 {type(e).__name__}: {str(e)[:120]}")
            continue
        if not values:
            stats["no_data"] += 1
            continue
        for (y, q), v in values.items():
            upsert_quarter(conn, t, "KR", y, q, v, "DART", "KRW", now)
        conn.commit()
        stats["ok"] += 1
        recent = latest_quarters(values)
        if len(recent) < 5:
            stats["lt5"] += 1
        if recent and recent[0][1].get("fs_div") == "OFS":
            stats["ofs"] += 1
        if n % 50 == 0:
            _log(f"  진행 {n}/{len(tickers)} {stats}")

    _log(f"완료 {stats} (lt5=최근 5분기 미만, ofs=최신 분기가 별도재무)")

    if args.tickers:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        for t in args.tickers:
            name = universe.get(t, {}).get("name", "")
            rows = get_quarters(conn, t, "KR")[:5]
            print(f"\n{t} {name}  (단위: 억원)")
            print(f"  {'분기':8s} {'매출':>12s} {'영업이익':>10s} {'순이익':>10s}  구분  산출")
            for r in rows:
                print(f"  {r['fiscal_year']}Q{r['fiscal_quarter']}   {fmt_eok(r['revenue']):>12s} "
                      f"{fmt_eok(r['operating_income']):>10s} {fmt_eok(r['net_income']):>10s}  "
                      f"{r['fs_div'] or '-':4s}  {'4분기 계산' if r['derived'] == 'annual_minus_9m' else '보고값'}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
