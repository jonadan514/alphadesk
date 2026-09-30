"""매출 성장률을 실제로 계산해 분포를 본다. 아무것도 쓰지 않는다.

1차 조사(probe_growth_fcf_data.py)로 데이터가 있다는 건 확인했다. 이건 두 가지를
더 보기 위한 것이다.

  1. **임계값을 실측에서 정하려고** - "성장/정체/역성장"을 나눌 기준을 머리로
     정하면 MASTER_PLAN §9의 "임의로 정한 숫자"가 하나 더 늘어난다. 실제 분포를
     보고 정한다.
  2. **파싱이 실전에서 깨지는 자리를 미리 찾으려고** - 회계기간 정렬, 회계연도
     간격, 매출 0/음수 같은 건 코드를 쓰고 나서 발견하면 늦다. 실패 사유별로
     몇 종목인지 세어 둔다.

계산 규칙(설계안 - 여기서 검증하고 SPEC에 확정한다)
  - 연차 손익계산서의 period_end를 최신순으로 정렬해 4개 시점을 쓴다.
  - 3년 CAGR = (최신매출 / 3년전매출)^(1/3) - 1
  - 최근 1년   = (최신매출 / 직전매출) - 1
  - 최신·기준 시점 매출이 0 이하이면 None (성장률이 정의되지 않는다).
  - **연도 간격이 정확히 3년이 아니면 None.** company_valuation._last_4q_sum이
    "연속 4분기"를 요구하는 것과 같은 엄격함 - 간격이 벌어진 채 "3년"이라고
    부르면 말과 값이 달라진다. 이 규칙으로 몇 종목이 탈락하는지도 센다.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

REVENUE_KEYS = ("Total Revenue", "Operating Revenue")
OPERATING_INCOME_KEYS = ("Operating Income", "Total Operating Income As Reported", "EBIT")
YEARS = 3


def _log(msg: str) -> None:
    print(f"[probe-dist] {msg}", flush=True)


def _pick(d: dict, keys: tuple[str, ...]):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return float(v)
    return None


def load_annual(conn, tickers: list[str]) -> dict[str, list[tuple[str, dict]]]:
    """티커 -> [(period_end, data), ...] 최신순."""
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT ticker, period_end, data FROM fundamentals_cache "
        f"WHERE statement = 'income' AND ticker IN ({placeholders})",
        tuple(tickers),
    ).fetchall()
    out: dict[str, list[tuple[str, dict]]] = {}
    for ticker, period_end, data in rows:
        try:
            out.setdefault(ticker, []).append((str(period_end), json.loads(data)))
        except Exception:
            continue
    for v in out.values():
        v.sort(key=lambda x: x[0], reverse=True)   # ISO 날짜라 문자열 정렬이 곧 날짜 정렬
    return out


def growth_for(periods: list[tuple[str, dict]]) -> tuple[float | None, float | None, str]:
    """(3년 CAGR, 최근 1년, 사유) - 사유는 실패했을 때 어디서 걸렸는지."""
    if len(periods) < YEARS + 1:
        return None, None, f"회계기간 부족({len(periods)}개)"

    window = periods[: YEARS + 1]
    years = [int(p[0][:4]) for p in window]
    if years[0] - years[-1] != YEARS:
        return None, None, f"연도 간격 불일치({years[0]}-{years[-1]})"

    revs = [_pick(d, REVENUE_KEYS) for _, d in window]
    if any(r is None for r in revs):
        return None, None, "매출 계정 없음"
    if revs[0] <= 0 or revs[-1] <= 0:
        return None, None, "매출 0 이하"

    cagr = (revs[0] / revs[-1]) ** (1 / YEARS) - 1
    yoy = (revs[0] / revs[1] - 1) if revs[1] > 0 else None
    return cagr, yoy, "ok"


def op_margin_direction(periods: list[tuple[str, dict]]) -> str:
    """영업이익률이 3년 전보다 올랐는지. 계정이 없으면 '계정없음'."""
    if len(periods) < YEARS + 1:
        return "기간부족"
    window = periods[: YEARS + 1]
    now_oi = _pick(window[0][1], OPERATING_INCOME_KEYS)
    old_oi = _pick(window[-1][1], OPERATING_INCOME_KEYS)
    now_rev = _pick(window[0][1], REVENUE_KEYS)
    old_rev = _pick(window[-1][1], REVENUE_KEYS)
    if None in (now_oi, old_oi, now_rev, old_rev):
        return "계정없음"
    if now_rev <= 0 or old_rev <= 0:
        return "매출0이하"
    return "개선" if (now_oi / now_rev) > (old_oi / old_rev) else "악화"


def describe(label: str, values: list[float]) -> None:
    if not values:
        _log(f"    {label}: 값 없음")
        return
    v = sorted(values)
    def q(p):
        return v[min(len(v) - 1, int(len(v) * p))]
    _log(f"    {label} (n={len(v)})")
    _log(f"      최소 {v[0]*100:6.1f}%  10% {q(.1)*100:6.1f}%  25% {q(.25)*100:6.1f}%  "
         f"중앙 {statistics.median(v)*100:6.1f}%")
    _log(f"      75% {q(.75)*100:6.1f}%  90% {q(.9)*100:6.1f}%  최대 {v[-1]*100:6.1f}%")
    for cut in (-0.05, 0.0, 0.05, 0.10, 0.15, 0.20):
        n = sum(1 for x in v if x >= cut)
        _log(f"      {cut*100:+5.0f}% 이상: {n:>3}종목 ({n/len(v)*100:.0f}%)")


def main() -> int:
    conn = get_db()
    rows = conn.execute("SELECT market, symbol FROM watchlist_candidates").fetchall()
    by_market: dict[str, list[str]] = {}
    for market, symbol in rows:
        by_market.setdefault(market, []).append(symbol)

    for market in sorted(by_market):
        tickers = by_market[market]
        _log("=" * 64)
        _log(f"[{market}] 후보 {len(tickers)}종목")
        annual = load_annual(conn, tickers)

        cagrs: list[float] = []
        yoys: list[float] = []
        reasons: Counter[str] = Counter()
        directions: Counter[str] = Counter()

        for t in tickers:
            periods = annual.get(t, [])
            cagr, yoy, reason = growth_for(periods)
            reasons[reason] += 1
            if cagr is not None:
                cagrs.append(cagr)
            if yoy is not None:
                yoys.append(yoy)
            directions[op_margin_direction(periods)] += 1

        ok = reasons.get("ok", 0)
        _log(f"  계산 성공: {ok}/{len(tickers)} ({ok/len(tickers)*100:.0f}%)")
        for r, n in reasons.most_common():
            if r != "ok":
                _log(f"    실패 - {r}: {n}종목")
        describe("매출 3년 CAGR", cagrs)
        describe("최근 1년 매출 성장률", yoys)
        _log(f"    영업이익률 방향: {dict(directions)}")

    conn.close()
    _log("=" * 64)
    _log("완료 - 아무것도 쓰지 않았다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
