"""
섹터 분석기
- 11개 SPDR ETF 기반 섹터 순환 분석
- SPY 대비 상대 강도(RS) 계산 (1d / 1w / 1m / 3m)
- 경기 사이클 판단 (Early / Mid / Late / Recession)
- 4주 RS 이력
- 섹터별 구성 종목 (daily report picks 활용)
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from src.db.data_store import get_db

SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLY":  "Consumer Disc.",
    "XLB":  "Materials",
    "XLU":  "Utilities",
    "XLE":  "Energy",
    "XLP":  "Consumer Staples",
    "XLRE": "Real Estate",
    "XLF":  "Financials",
    "XLI":  "Industrials",
    "XLV":  "Healthcare",
    "XLC":  "Comm. Services",
}

# 경기 사이클별 대표 섹터 (해당 섹터 RS 합산으로 사이클 점수 계산)
CYCLE_SECTORS = {
    "early":     ["XLY", "XLF", "XLI"],
    "mid":       ["XLK", "XLE", "XLB"],
    "late":      ["XLE", "XLB", "XLP"],
    "recession": ["XLV", "XLU", "XLP"],
}

CYCLE_LABELS = {
    "early":     "Early Cycle",
    "mid":       "Mid Cycle",
    "late":      "Late Cycle",
    "recession": "Recession",
}

# GICS 섹터명 → ETF 매핑 (daily report picks 섹터 연결용)
SECTOR_TO_ETF = {
    "Technology":            "XLK",
    "Consumer Cyclical":     "XLY",
    "Consumer Defensive":    "XLP",
    "Basic Materials":       "XLB",
    "Energy":                "XLE",
    "Financial Services":    "XLF",
    "Healthcare":            "XLV",
    "Industrials":           "XLI",
    "Real Estate":           "XLRE",
    "Utilities":             "XLU",
    "Communication Services":"XLC",
}


def _fetch_closes(period: str = "4mo") -> pd.DataFrame:
    tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    closes = data["Close"]
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    return closes


def _ret(closes: pd.DataFrame, ticker: str, days: int) -> float | None:
    if ticker not in closes.columns:
        return None
    s = closes[ticker].dropna()
    if len(s) < days + 1:
        return None
    return float(s.iloc[-1] / s.iloc[-days - 1] - 1)


def _weekly_ret(closes: pd.DataFrame, ticker: str, weeks_ago: int) -> float | None:
    """weeks_ago주 전의 주간 수익률 (5 거래일 단위)"""
    if ticker not in closes.columns:
        return None
    s = closes[ticker].dropna()
    end_idx   = len(s) - 1 - weeks_ago * 5
    start_idx = end_idx - 5
    if start_idx < 0 or end_idx < 0:
        return None
    return float(s.iloc[end_idx] / s.iloc[start_idx] - 1)


def _get_sector_stocks() -> dict[str, list[dict]]:
    """워치리스트 스크리닝 통과 종목(watchlist_candidates)에서 섹터별로 묶는다.

    예전엔 data_daily_reports.payload.picks(모멘텀 스코어링 픽)에서 읽었는데,
    그 picks 필드 자체가 스윙 스크리너 제거("0번 기능제거")로 없어져서 이
    함수가 조용히 죽어있었다(2026-09-03 발견 - 항상 빈 dict 반환). 등급/점수
    대신 실제 재무 지표(Piotroski F-Score)로 교체 - "종합 점수 없음" 원칙에
    맞춤.

    Turso HTTP 클라이언트는 INTEGER 컬럼을 문자열로 반환한다(Phase A-3에서
    이미 한 번 겪은 문제 - get_prior_news_counts 참고) - json.dumps로 그대로
    저장하면 프론트가 문자열로 받게 되므로 여기서 명시적으로 int() 캐스팅."""
    try:
        with get_db() as con:
            rows = con.execute(
                "SELECT symbol, sector, piotroski FROM watchlist_candidates WHERE market = 'US'"
            ).fetchall()
        result: dict[str, list[dict]] = {}
        for symbol, sector, piotroski in rows:
            etf = SECTOR_TO_ETF.get(sector or "", "Other")
            result.setdefault(etf, []).append({
                "symbol":    symbol,
                "piotroski": int(piotroski) if piotroski is not None else None,
                "sector":    sector or "",
            })
    except Exception:
        result = {}
    return result


def analyze() -> dict:
    """섹터 분석 실행 후 DB 저장 및 결과 반환"""
    today = datetime.today().strftime("%Y-%m-%d")
    closes = _fetch_closes("4mo")

    # ── ETF 수익률 & RS 계산 ────────────────────────────────────────────
    period_days = {"1d": 1, "1w": 5, "1m": 21, "3m": 63}
    etf_data = []
    rs_1m: dict[str, float] = {}

    for ticker, name in SECTOR_ETFS.items():
        entry: dict = {"ticker": ticker, "name": name}
        for label, days in period_days.items():
            etf_ret = _ret(closes, ticker, days)
            spy_ret = _ret(closes, "SPY", days)
            entry[f"ret_{label}"] = round(etf_ret * 100, 2) if etf_ret is not None else None
            entry[f"rs_{label}"]  = round((etf_ret - spy_ret) * 100, 2) if (etf_ret is not None and spy_ret is not None) else None
        if entry.get("rs_1m") is not None:
            rs_1m[ticker] = entry["rs_1m"]
        entry["cur_price"] = round(float(closes[ticker].dropna().iloc[-1]), 2) if ticker in closes.columns else None
        etf_data.append(entry)

    # 1m RS 기준 내림차순 정렬
    etf_data.sort(key=lambda x: -(x.get("rs_1m") or -999))

    # ── 경기 사이클 판단 ───────────────────────────────────────────────
    cycle_scores: dict[str, float] = {}
    for cycle, tickers in CYCLE_SECTORS.items():
        vals = [rs_1m.get(t, 0) for t in tickers]
        cycle_scores[cycle] = round(float(np.mean(vals)), 2)

    current_cycle = max(cycle_scores, key=cycle_scores.get)

    # 선행 / 후행 섹터
    sorted_rs = sorted(rs_1m.items(), key=lambda x: -x[1])
    leading = [{"ticker": t, "name": SECTOR_ETFS[t], "rs": round(v, 2)} for t, v in sorted_rs if v > 0][:3]
    lagging = [{"ticker": t, "name": SECTOR_ETFS[t], "rs": round(v, 2)} for t, v in reversed(sorted_rs) if v < 0][:3]

    # ── 4주 RS 이력 ────────────────────────────────────────────────────
    spy_weekly = [_weekly_ret(closes, "SPY", w) for w in range(4)]
    rs_history = []
    for ticker, name in SECTOR_ETFS.items():
        row: dict = {"ticker": ticker, "name": name}
        for w in range(4):
            etf_w = _weekly_ret(closes, ticker, w)
            spy_w = spy_weekly[w]
            row[f"w{w}"] = round((etf_w - spy_w) * 100, 2) if (etf_w is not None and spy_w is not None) else None
        rs_history.append(row)
    rs_history.sort(key=lambda x: -(x.get("w0") or -999))

    # ── 섹터별 구성 종목 ────────────────────────────────────────────────
    sector_stocks = _get_sector_stocks()

    result = {
        "date":          today,
        "current_cycle": current_cycle,
        "cycle_label":   CYCLE_LABELS[current_cycle],
        "cycle_scores":  cycle_scores,
        "leading":       leading,
        "lagging":       lagging,
        "etf_data":      etf_data,
        "rs_history":    rs_history,
        "sector_stocks": sector_stocks,
        "spy_ret": {
            label: round((_ret(closes, "SPY", days) or 0) * 100, 2)
            for label, days in period_days.items()
        },
    }

    _save(result)
    return result


def _save(data: dict):
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sector_analysis (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL UNIQUE,
                payload    TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            INSERT OR REPLACE INTO sector_analysis (date, payload, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (data["date"], json.dumps(data, ensure_ascii=False)))
