"""실적 발표 서프라이즈(추정치 대비 실제치) 수집.

왜 필요한가 (2026-09-16):
실적 축은 분기 매출 성장률 기반이라 분기에 한 번만 움직인다. 반면 "추정치를 얼마나
넘겼나"는 발표 당일에 확정되고, 시장이 곧바로 반응하는 값이다. 실적 축을 대체하지
않고(원칙 1: 축을 늘리거나 합치지 않는다) 실적 축 옆에 붙는 참고 수치로만 쓴다.

yfinance의 earnings_dates는 배치 API가 없어 종목별 호출이다. 그래서
  - 승인된 테마 소속 기업만 대상으로 하고(전체 유니버스 아님)
  - 최근에 받아둔 종목은 건너뛰며(STALE_DAYS)
  - 한 번 실행에서 받는 수를 예산으로 제한한다
전체를 매주 새로 받지 않아도 되는 이유는, 값이 바뀌는 시점이 분기 발표일뿐이기 때문이다.
"""
from __future__ import annotations

import time
from datetime import date, datetime

import yfinance as yf

STALE_DAYS = 25        # 이 기간 안에 받아둔 종목은 건너뛴다(분기 발표 주기보다 짧게)
DEFAULT_BUDGET = 150   # 한 번 실행에서 새로 조회할 종목 수 상한
SLEEP_SEC = 0.3


def _to_date(value) -> str | None:
    try:
        return value.date().isoformat() if hasattr(value, "date") else str(value)[:10]
    except Exception:
        return None


def fetch_latest_surprise(yf_symbol: str) -> dict | None:
    """가장 최근 '발표가 끝난' 분기의 서프라이즈. 실적 발표 이력이 없으면 None.

    반환: {report_date, surprise_pct, eps_estimate, eps_reported}
    미래 예정일 행은 Reported EPS가 비어 있어 자연스럽게 걸러진다.
    """
    try:
        df = yf.Ticker(yf_symbol).earnings_dates
    except Exception:
        return None
    if df is None or len(df) == 0 or "Reported EPS" not in df.columns:
        return None

    past = df[df["Reported EPS"].notna()]
    if len(past) == 0:
        return None
    # earnings_dates는 최신순 정렬이지만 보장에 기대지 않는다.
    past = past.sort_index(ascending=False)
    row = past.iloc[0]
    surprise = row.get("Surprise(%)")
    try:
        surprise = None if surprise is None or surprise != surprise else float(surprise)
    except (TypeError, ValueError):
        surprise = None
    if surprise is None:
        return None
    return {
        "report_date": _to_date(past.index[0]),
        "surprise_pct": surprise,
        "eps_estimate": float(row["EPS Estimate"]) if row.get("EPS Estimate") == row.get("EPS Estimate") else None,
        "eps_reported": float(row["Reported EPS"]) if row.get("Reported EPS") == row.get("Reported EPS") else None,
    }


def collect_surprises(targets: list[tuple[str, str, str]], known: dict[str, str],
                      budget: int = DEFAULT_BUDGET, today: date | None = None,
                      log=print) -> dict[str, dict]:
    """targets: (ticker, market, yf_symbol) 목록. known: {ticker: 마지막 수집일 ISO}.

    반환: {ticker: {market, report_date, surprise_pct, eps_estimate, eps_reported}} -
    이번에 새로 받은 것만 담는다(건너뛴 종목은 이미 DB에 있는 값을 그대로 쓴다).
    """
    today = today or date.today()
    todo = []
    for ticker, market, yf_symbol in targets:
        last = known.get(ticker)
        if last:
            try:
                if (today - date.fromisoformat(last[:10])).days < STALE_DAYS:
                    continue
            except ValueError:
                pass
        todo.append((ticker, market, yf_symbol))

    log(f"서프라이즈 대상 {len(targets)}종목 중 갱신 필요 {len(todo)}, 이번 예산 {budget}")
    out: dict[str, dict] = {}
    for ticker, market, yf_symbol in todo[:budget]:
        rec = fetch_latest_surprise(yf_symbol)
        if rec:
            out[ticker] = {"market": market, **rec}
        time.sleep(SLEEP_SEC)
    log(f"새로 확보 {len(out)}종목 (조회 {min(len(todo), budget)})")
    return out


def summarize_theme(members: list[dict], surprise_by_ticker: dict[str, dict],
                    as_of: date | None = None, window_days: int = 100) -> dict:
    """테마 단위 요약. 반환: {n, beat, ratio, median_pct}.

    window_days 안에 발표한 소속 기업만 센다 - 두 분기 전 서프라이즈까지 섞이면
    "최근 발표" 의미가 사라진다. 표본 5개 미만이면 ratio는 None(na와 같은 취급).
    """
    import statistics
    as_of = as_of or date.today()
    vals = []
    for m in members:
        rec = surprise_by_ticker.get(m["ticker"])
        if not rec or rec.get("surprise_pct") is None:
            continue
        rd = rec.get("report_date")
        if rd:
            try:
                if (as_of - date.fromisoformat(rd[:10])).days > window_days:
                    continue
            except ValueError:
                continue
        vals.append(float(rec["surprise_pct"]))
    if not vals:
        return {"n": 0, "beat": 0, "ratio": None, "median_pct": None}
    beat = sum(1 for v in vals if v > 0)
    return {"n": len(vals), "beat": beat,
            "ratio": beat / len(vals) if len(vals) >= 5 else None,
            "median_pct": statistics.median(vals)}
