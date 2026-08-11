"""
한국 섹터 분석기
- KOSPI 섹터별 대표 ETF/지수 없이 개별 종목 기반으로 섹터 RS 계산
- KOSPI(^KS11) 대비 각 섹터 수익률 집계
- 경기 사이클 판단 (Early / Mid / Late / Recession)
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from src.collectors.kr_kospi_list import get_kospi_list
from src.db.data_store import get_db

# 경기 사이클별 대표 섹터
CYCLE_SECTORS = {
    "early":     ["Consumer Cyclical", "Financial Services", "Industrials"],
    "mid":       ["Technology", "Energy", "Basic Materials"],
    "late":      ["Energy", "Basic Materials", "Consumer Defensive"],
    "recession": ["Healthcare", "Utilities", "Consumer Defensive"],
}

CYCLE_LABELS = {
    "early":     "Early Cycle",
    "mid":       "Mid Cycle",
    "late":      "Late Cycle",
    "recession": "Recession",
}

# KOSPI 섹터별 대표 종목 (섹터 RS 계산용 앵커 티커)
SECTOR_ANCHORS = {
    "Technology":             ["005930.KS", "000660.KS", "006400.KS"],   # 삼성전자, SK하이닉스, 삼성SDI
    "Consumer Cyclical":      ["005380.KS", "000270.KS", "004170.KS"],   # 현대차, 기아, 신세계
    "Consumer Defensive":     ["033780.KS", "097950.KS", "000080.KS"],   # KT&G, CJ제일제당, 하이트진로
    "Financial Services":     ["105560.KS", "055550.KS", "086790.KS"],   # KB금융, 신한지주, 하나금융
    "Industrials":            ["028260.KS", "034730.KS", "003550.KS"],   # 삼성물산, SK, LG
    "Healthcare":             ["207940.KS", "068270.KS", "000100.KS"],   # 삼성바이오, 셀트리온, 유한양행
    "Communication Services": ["035420.KS", "035720.KS", "017670.KS"],   # NAVER, 카카오, SKT
    "Basic Materials":        ["051910.KS", "047050.KS", "010130.KS"],   # LG화학, 포스코홀딩스, 고려아연
    "Energy":                 ["096770.KS", "010950.KS", "078930.KS"],   # SK이노베이션, S-Oil, GS
    "Utilities":              ["015760.KS"],                              # 한국전력
}


def _fetch_sector_data(period: str = "4mo") -> dict[str, pd.Series]:
    """섹터별 앵커 종목 평균 수익률 시리즈 반환"""
    all_tickers = ["^KS11"]
    for tickers in SECTOR_ANCHORS.values():
        all_tickers.extend(tickers)
    all_tickers = list(set(all_tickers))

    try:
        data = yf.download(all_tickers, period=period, auto_adjust=True, progress=False)
        closes = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
    except Exception:
        return {}

    sector_series: dict[str, pd.Series] = {}
    if "^KS11" in closes.columns:
        sector_series["KOSPI"] = closes["^KS11"].dropna()

    for sector, tickers in SECTOR_ANCHORS.items():
        available = [t for t in tickers if t in closes.columns]
        if not available:
            continue
        sector_df = closes[available].dropna(how="all")
        if sector_df.empty:
            continue
        # 정규화 후 평균 (각 종목 첫 날 = 1)
        normed = sector_df.div(sector_df.iloc[0])
        sector_series[sector] = normed.mean(axis=1)

    return sector_series


def _ret(series: pd.Series, days: int) -> float | None:
    s = series.dropna()
    if len(s) < days + 1:
        return None
    return float(s.iloc[-1] / s.iloc[-days - 1] - 1)


def _weekly_ret(series: pd.Series, weeks_ago: int) -> float | None:
    s = series.dropna()
    end_idx   = len(s) - 1 - weeks_ago * 5
    start_idx = end_idx - 5
    if start_idx < 0 or end_idx < 0:
        return None
    return float(s.iloc[end_idx] / s.iloc[start_idx] - 1)


def _get_sector_stocks() -> dict[str, list[dict]]:
    """kr_daily_reports에서 섹터별 종목 추출"""
    try:
        with get_db() as con:
            row = con.execute(
                "SELECT payload FROM kr_daily_reports ORDER BY date DESC LIMIT 1"
            ).fetchone()
        if not row:
            return {}
        picks = json.loads(row[0]).get("picks", [])
        result: dict[str, list[dict]] = {}
        for p in picks:
            sector = p.get("sector", "Other")
            if sector not in result:
                result[sector] = []
            result[sector].append({
                "symbol": p["symbol"],
                "name":   p.get("name", ""),
                "grade":  p.get("grade", "—"),
                "score":  p.get("composite_score"),
                "sector": sector,
            })
    except Exception:
        result = {}
    return result


def analyze() -> dict:
    today = datetime.today().strftime("%Y-%m-%d")
    sector_series = _fetch_sector_data("4mo")

    kospi_series = sector_series.get("KOSPI")

    period_days = {"1d": 1, "1w": 5, "1m": 21, "3m": 63}
    sector_data = []
    rs_1m: dict[str, float] = {}

    for sector, series in sector_series.items():
        if sector == "KOSPI":
            continue
        entry: dict = {"sector": sector}
        for label, days in period_days.items():
            sec_ret    = _ret(series, days)
            kospi_ret  = _ret(kospi_series, days) if kospi_series is not None else None
            entry[f"ret_{label}"] = round(sec_ret * 100, 2) if sec_ret is not None else None
            entry[f"rs_{label}"]  = (
                round((sec_ret - kospi_ret) * 100, 2)
                if (sec_ret is not None and kospi_ret is not None) else None
            )
        if entry.get("rs_1m") is not None:
            rs_1m[sector] = entry["rs_1m"]
        sector_data.append(entry)

    # 1m RS 기준 정렬
    sector_data.sort(key=lambda x: -(x.get("rs_1m") or -999))

    # ── 경기 사이클 판단 ──────────────────────────────────────────────────
    cycle_scores: dict[str, float] = {}
    for cycle, sectors in CYCLE_SECTORS.items():
        vals = [rs_1m.get(s, 0) for s in sectors]
        cycle_scores[cycle] = round(float(np.mean(vals)), 2)
    current_cycle = max(cycle_scores, key=cycle_scores.get)

    # 선행 / 후행 섹터
    sorted_rs = sorted(rs_1m.items(), key=lambda x: -x[1])
    leading = [{"sector": s, "rs": round(v, 2)} for s, v in sorted_rs if v > 0][:3]
    lagging = [{"sector": s, "rs": round(v, 2)} for s, v in reversed(sorted_rs) if v < 0][:3]

    # ── 4주 RS 이력 ──────────────────────────────────────────────────────
    rs_history = []
    for sector, series in sector_series.items():
        if sector == "KOSPI":
            continue
        row: dict = {"sector": sector}
        for w in range(4):
            sec_w   = _weekly_ret(series, w)
            kospi_w = _weekly_ret(kospi_series, w) if kospi_series is not None else None
            row[f"w{w}"] = (
                round((sec_w - kospi_w) * 100, 2)
                if (sec_w is not None and kospi_w is not None) else None
            )
        rs_history.append(row)
    rs_history.sort(key=lambda x: -(x.get("w0") or -999))

    kospi_ret_dict = {}
    if kospi_series is not None:
        for label, days in period_days.items():
            r = _ret(kospi_series, days)
            kospi_ret_dict[label] = round(r * 100, 2) if r is not None else None

    sector_stocks = _get_sector_stocks()

    result = {
        "date":          today,
        "market":        "KR",
        "current_cycle": current_cycle,
        "cycle_label":   CYCLE_LABELS[current_cycle],
        "cycle_scores":  cycle_scores,
        "leading":       leading,
        "lagging":       lagging,
        "sector_data":   sector_data,
        "rs_history":    rs_history,
        "sector_stocks": sector_stocks,
        "kospi_ret":     kospi_ret_dict,
    }

    _save(result)
    return result


def _save(data: dict):
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS kr_sector_analysis (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL UNIQUE,
                payload    TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            INSERT OR REPLACE INTO kr_sector_analysis (date, payload, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (data["date"], json.dumps(data, ensure_ascii=False)))


if __name__ == "__main__":
    r = analyze()
    print(f"사이클: {r['cycle_label']}")
    print(f"선행: {r['leading']}")
    print(f"후행: {r['lagging']}")
