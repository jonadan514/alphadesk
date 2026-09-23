"""워치리스트 후보에 밸류 지표(PSR/PER)를 채운다.

워치리스트는 함정 필터를 통과한 "재무가 탄탄한 종목" 목록인데, 화면에 보이는 지표가
F-Score·부채비율·이자보상뿐이라 **전부 품질 지표**였다. 장기 투자자가 새 아이디어를
찾을 때 가장 자연스러운 진입점인 "탄탄한데 싸기도 한 것"을 이 화면에서는 찾을 수 없었다.

계산은 새로 만들지 않는다 - 분기 재설계에서 쓰는 것과 **같은 함수**
(`src/analyzers/company_valuation.py`)를 그대로 쓴다. PSR/PER을 두 곳에서 다르게
계산하면 같은 종목이 화면마다 다른 값으로 보인다.

  PSR = 시가총액 ÷ 최근 4분기 매출 합
  PER = 시가총액 ÷ 최근 4분기 순이익 합 (순이익 합이 0 이하면 표시 안 함)

시가총액은 watchlist_candidates에 이미 있는 값을 쓴다(스크리닝 시점 기준) - 분기
화면이 fetch_status.info_payload를 쓰는 것과 출처가 다르지만, 워치리스트 행의 다른
숫자들과 같은 시점이어야 화면 안에서 앞뒤가 맞는다.

## 3등분 기준이 분기 화면과 다르다

분기 화면(SPEC 5-4)은 **테마 안에서** 3등분한다 - 같은 산업끼리 비교해야 의미가 있어서다.
여기서는 **같은 시장 후보 전체 안에서** 3등분한다. 워치리스트는 테마가 아니라 "재무 통과
종목 전부"라 비교 대상이 후보 목록 그 자체이기 때문이다. 같은 종목이 두 화면에서 다른
등급으로 보일 수 있는데, 비교 대상이 다르니 그게 맞다(화면에 기준을 밝혀 둔다).

## 스크리닝 뒤에 반드시 다시 돌려야 한다

run_watchlist_screen.py는 매주 해당 시장 행을 DELETE하고 새로 INSERT한다. 그러면
여기서 채운 psr/per/valuation_tier도 같이 사라진다. 그래서 run_watchlist_screen.py
main()이 Turso 업로드 직후 이 스크립트의 run()을 호출한다. 이 파일을 직접 실행하는
건 수동 보정이나 지금처럼 처음 채워 넣을 때를 위한 것이다.

Usage:
  python scripts/compute_watchlist_valuation.py
  python scripts/compute_watchlist_valuation.py --market KR
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.analyzers.company_valuation import per as calc_per, psr as calc_psr, theme_valuation_tiers
from src.db.data_store import get_db
from src.db.quarterly_financials import select_quarters_bulk
from src.db.turso_http import execute_many, get_credentials

# watchlist_candidates에 뒤늦게 붙이는 컬럼. DDL(CREATE TABLE IF NOT EXISTS)만 고치면
# 이미 있는 표에는 반영되지 않아서, theme_signals.py의 LATE_COLUMNS와 같은 방식으로
# ALTER TABLE을 try/except로 감싸 돌린다.
LATE_COLUMNS = [("psr", "REAL"), ("per", "REAL"), ("valuation_tier", "TEXT")]

UPDATE_SQL = (
    "UPDATE watchlist_candidates SET psr = ?, per = ?, valuation_tier = ? "
    "WHERE market = ? AND symbol = ?"
)
BATCH = 50   # push_to_turso()와 같은 크기


def _log(msg: str) -> None:
    print(f"[wl-value] {msg}", flush=True)


def ensure_columns(conn) -> None:
    for name, coltype in LATE_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE watchlist_candidates ADD COLUMN {name} {coltype}")
        except Exception:
            pass   # 이미 있는 컬럼 - 정상
    conn.commit()


def load_candidates(conn, market: str) -> list[dict]:
    rows = conn.execute(
        "SELECT symbol, market_cap FROM watchlist_candidates WHERE market = ?", (market,)
    ).fetchall()
    # Turso는 REAL도 문자열로 돌려준다 - 문자열을 시가총액으로 나누면 죽는다.
    return [
        {"symbol": r[0], "market_cap": float(r[1]) if r[1] is not None else None}
        for r in rows
    ]


def write_valuations(conn, market: str, updates: list[tuple]) -> None:
    """updates: (psr, per, tier, symbol) 목록.

    후보가 시장당 100종목이 넘어서 _TursoConn.execute()로 한 줄씩 보내면 UPDATE 하나마다
    HTTP 왕복이 생긴다 - push_to_turso()와 같이 pipeline 배치로 묶는다.
    """
    if get_credentials():
        statements = [(UPDATE_SQL, [p, e, t, market, s]) for p, e, t, s in updates]
        for i in range(0, len(statements), BATCH):
            execute_many(statements[i:i + BATCH])
        return
    # 로컬 sqlite(개발·테스트)에서는 왕복 비용이 없으니 한 줄씩 보낸다. executemany는
    # 쓰지 않는다 - 운영 연결(_TursoConn)에도, 테스트 fixture에도 그 메서드가 없다.
    for p, e, t, s in updates:
        conn.execute(UPDATE_SQL, (p, e, t, market, s))
    conn.commit()


def run(conn, markets: list[str]) -> None:
    for market in markets:
        candidates = load_candidates(conn, market)
        if not candidates:
            _log(f"{market}: 후보 없음 - 건너뜀")
            continue

        quarters_by_ticker = select_quarters_bulk(conn, [c["symbol"] for c in candidates], market)

        psr_by_ticker: dict[str, float | None] = {}
        per_by_ticker: dict[str, float | None] = {}
        for c in candidates:
            quarters = quarters_by_ticker.get(c["symbol"], [])
            psr_by_ticker[c["symbol"]] = calc_psr(c["market_cap"], quarters)
            per_by_ticker[c["symbol"]] = calc_per(c["market_cap"], quarters)

        # 같은 시장 후보 전체 안에서 3등분(위 모듈 설명 참고 - 분기 화면은 테마 안에서 나눈다).
        tiers = theme_valuation_tiers(psr_by_ticker)

        write_valuations(conn, market, [
            (psr_by_ticker[c["symbol"]], per_by_ticker[c["symbol"]],
             tiers[c["symbol"]], c["symbol"])
            for c in candidates
        ])

        have_psr = sum(1 for v in psr_by_ticker.values() if v is not None)
        have_per = sum(1 for v in per_by_ticker.values() if v is not None)
        _log(f"{market}: 후보 {len(candidates)}종목 / PSR {have_psr} / PER {have_per}"
             f" (PER은 흑자 기업만) / 분기 재무 있는 종목 {len(quarters_by_ticker)}")
        if have_psr:
            vals = sorted(v for v in psr_by_ticker.values() if v is not None)
            _log(f"  PSR 최소 {vals[0]:.2f} / 중앙 {vals[len(vals) // 2]:.2f} / 최대 {vals[-1]:.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default=None, choices=["KR", "US"], help="비우면 둘 다")
    args = ap.parse_args()

    conn = get_db()
    try:
        ensure_columns(conn)
        run(conn, [args.market] if args.market else ["KR", "US"])
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
