"""
포트폴리오 리스크 분석
- Position Sizing (보유 종목별 포지션 크기)
- Sector Concentration (섹터 집중도)
- Correlation Risk (종목 간 상관관계)
- Component VaR (종목별 VaR 기여도)
- CDAR / CVaR (조건부 기대 손실)

기준 포트폴리오: equal_medium (60일 보유, 균등 배분)
"""

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH     = os.getenv("DATA_DB_PATH", "output/data.db")
PRICES_CSV  = "data/us_daily_prices.csv"
REF_PF      = "equal_medium"   # 분석 기준 포트폴리오
LOOKBACK    = 60               # 수익률 계산 기간 (거래일)
VAR_CONF    = 0.95
CORR_THRESH = 0.7              # 고상관 경보 임계값
STARTING_CASH = 100_000.0

REGIME_ALLOC = {
    "risk_on":  0.80,
    "neutral":  0.60,
    "risk_off": 0.40,
    "crisis":   0.20,
}


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _load_holdings() -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT h.symbol, h.grade, h.shares, h.entry_price, h.weight
            FROM pf_holdings h
            WHERE h.portfolio_id = ?
        """, (REF_PF,)).fetchall()
        cash = con.execute(
            "SELECT cash FROM pf_portfolios WHERE portfolio_id=?", (REF_PF,)
        ).fetchone()
    cash_val = cash[0] if cash else 0.0
    return [
        {"symbol": r[0], "grade": r[1], "shares": r[2],
         "entry_price": r[3], "weight": r[4]}
        for r in rows
    ], cash_val


def _get_sector_map() -> dict[str, str]:
    """모든 daily report picks를 순회해 섹터 정보 구축 (최신 리포트 우선)"""
    with _conn() as con:
        rows = con.execute(
            "SELECT payload FROM data_daily_reports ORDER BY date DESC"
        ).fetchall()
    sector_map: dict[str, str] = {}
    for (payload,) in rows:
        picks = json.loads(payload).get("picks", [])
        for p in picks:
            sym = p.get("symbol")
            sec = p.get("sector")
            if sym and sec and sec != "Unknown" and sym not in sector_map:
                sector_map[sym] = sec
    return sector_map


def _load_prices(symbols: list[str]) -> pd.DataFrame:
    df = pd.read_csv(PRICES_CSV)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"symbol": "ticker"})
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["ticker"].isin(symbols)].sort_values(["ticker", "date"])
    return df


def _latest_price(df: pd.DataFrame, symbol: str) -> float | None:
    sub = df[df["ticker"] == symbol].sort_values("date")
    return float(sub["close"].iloc[-1]) if not sub.empty else None


def _returns_matrix(df: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """최근 LOOKBACK 거래일 일간 수익률 행렬 (날짜 × 종목)"""
    pivoted = df.pivot_table(index="date", columns="ticker", values="close")
    pivoted = pivoted[symbols].dropna(axis=1, how="all")
    rets = pivoted.pct_change().dropna(how="all").tail(LOOKBACK)
    return rets


def compute_risk(analysis_date: str | None = None) -> dict:
    """
    리스크 분석 메인 함수.
    결과를 DB에 저장하고 dict 반환.
    """
    if analysis_date is None:
        analysis_date = datetime.today().strftime("%Y-%m-%d")

    # ── 보유 종목 로드 ──────────────────────────────────────────────────
    holdings, cash_val = _load_holdings()
    if not holdings:
        return {"error": "보유 종목 없음", "date": analysis_date}

    symbols = [h["symbol"] for h in holdings]
    sector_map = _get_sector_map()
    prices_df = _load_prices(symbols)

    # ── 현재 가격 & 포지션 크기 ──────────────────────────────────────────
    total_value = cash_val
    position_sizing = []
    for h in holdings:
        cur_price = _latest_price(prices_df, h["symbol"]) or h["entry_price"]
        pos_value = h["shares"] * cur_price
        total_value += pos_value
        position_sizing.append({
            "symbol":      h["symbol"],
            "grade":       h["grade"],
            "sector":      sector_map.get(h["symbol"], "Unknown"),
            "entry_price": round(h["entry_price"], 2),
            "cur_price":   round(cur_price, 2),
            "shares":      round(h["shares"], 4),
            "value":       round(pos_value, 2),
            "weight_pct":  0.0,   # 아래에서 채움
            "pnl_pct":     round((cur_price - h["entry_price"]) / h["entry_price"], 4),
        })

    for p in position_sizing:
        p["weight_pct"] = round(p["value"] / total_value, 4) if total_value else 0.0

    position_sizing.sort(key=lambda x: x["value"], reverse=True)

    # ── 섹터 집중도 ──────────────────────────────────────────────────────
    sector_totals: dict[str, float] = {}
    for p in position_sizing:
        sec = p["sector"]
        sector_totals[sec] = sector_totals.get(sec, 0) + p["value"]
    sector_concentration = [
        {
            "sector": sec,
            "value":  round(val, 2),
            "weight_pct": round(val / (total_value - cash_val), 4) if (total_value - cash_val) else 0.0,
        }
        for sec, val in sorted(sector_totals.items(), key=lambda x: -x[1])
    ]

    # ── 수익률 행렬 ──────────────────────────────────────────────────────
    avail_syms = [s for s in symbols if s in prices_df["ticker"].values]
    rets = _returns_matrix(prices_df, avail_syms) if avail_syms else pd.DataFrame()

    # ── 포트폴리오 VaR ────────────────────────────────────────────────────
    weights_arr = np.array([
        next((p["weight_pct"] for p in position_sizing if p["symbol"] == s), 0.0)
        for s in (rets.columns if not rets.empty else [])
    ])

    portfolio_var = None
    portfolio_cvar = None
    if not rets.empty and len(weights_arr) > 0:
        port_rets = rets.values @ weights_arr
        portfolio_var  = float(np.percentile(port_rets, (1 - VAR_CONF) * 100))
        below_var = port_rets[port_rets <= portfolio_var]
        portfolio_cvar = float(below_var.mean()) if len(below_var) > 0 else portfolio_var

    # ── 상관관계 ─────────────────────────────────────────────────────────
    high_corr_pairs = []
    if not rets.empty and rets.shape[1] >= 2:
        corr = rets.corr()
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                c = corr.iloc[i, j]
                if abs(c) >= CORR_THRESH:
                    high_corr_pairs.append({
                        "sym_a": corr.columns[i],
                        "sym_b": corr.columns[j],
                        "corr":  round(float(c), 3),
                    })
        high_corr_pairs.sort(key=lambda x: -abs(x["corr"]))

    # ── Component VaR ─────────────────────────────────────────────────────
    component_var = []
    if not rets.empty and len(weights_arr) > 0:
        port_rets_arr = rets.values @ weights_arr
        cov = rets.cov().values
        port_std = float(np.sqrt(weights_arr @ cov @ weights_arr))
        for i, sym in enumerate(rets.columns):
            cov_with_port = float(cov[i] @ weights_arr)
            comp_var_pct  = -(weights_arr[i] * cov_with_port / port_std) * 1.645 if port_std else 0.0
            comp_var_usd  = comp_var_pct * total_value
            component_var.append({
                "symbol":     sym,
                "cvar_pct":   round(comp_var_pct, 4),
                "cvar_usd":   round(comp_var_usd, 2),
                "weight_pct": round(weights_arr[i], 4),
            })
        component_var.sort(key=lambda x: -abs(x["cvar_pct"]))

    # ── CDAR / CVaR per stock ──────────────────────────────────────────────
    cdar_cvar_table = []
    if not rets.empty:
        for sym in rets.columns:
            sr = rets[sym].dropna()
            if len(sr) < 10:
                continue
            # max drawdown
            cumret = (1 + sr).cumprod()
            rolling_max = cumret.cummax()
            dd = (cumret - rolling_max) / rolling_max
            mdd = float(dd.min())
            # CVaR
            var_5 = float(np.percentile(sr, 5))
            cvar  = float(sr[sr <= var_5].mean()) if len(sr[sr <= var_5]) > 0 else var_5
            current_dd = float(dd.iloc[-1])
            cdar_cvar_table.append({
                "symbol":     sym,
                "cdar":       round(mdd, 4),           # 최대 낙폭
                "cvar":       round(cvar, 4),           # 조건부 VaR
                "max_dd":     round(mdd, 4),
                "current_dd": round(current_dd, 4),
            })
        cdar_cvar_table.sort(key=lambda x: x["cdar"])

    # ── 리스크 알림 ─────────────────────────────────────────────────────
    with _conn() as con:
        regime_row = con.execute(
            "SELECT payload FROM data_regime ORDER BY id DESC LIMIT 1"
        ).fetchone()
        gate_row = con.execute(
            "SELECT payload FROM data_market_gate ORDER BY id DESC LIMIT 1"
        ).fetchone()
        risk_row = con.execute(
            "SELECT payload FROM data_risk ORDER BY id DESC LIMIT 1"
        ).fetchone()

    regime = json.loads(regime_row[0]).get("regime", "neutral") if regime_row else "neutral"
    gate   = json.loads(gate_row[0]).get("gate", "GO") if gate_row else "GO"
    spy_var95 = json.loads(risk_row[0]).get("var_95") if risk_row else None
    mdd_val   = json.loads(risk_row[0]).get("mdd") if risk_row else None

    recommended_alloc = REGIME_ALLOC.get(regime, 0.6)
    invested_pct = (total_value - cash_val) / total_value if total_value else 0.0
    var_usd = abs(portfolio_var * total_value) if portfolio_var else None

    alerts = []
    alert_id = 1

    if portfolio_var and abs(portfolio_var) > 0.015:
        alerts.append({
            "id": alert_id, "level": "WARNING", "category": "RISK_BUDGET",
            "ticker": "PORTFOLIO",
            "message": f"리스크 예산 초과",
            "value": round(portfolio_var, 4),
            "threshold": -0.015,
        })
        alert_id += 1

    if regime in ("risk_off", "crisis"):
        alerts.append({
            "id": alert_id, "level": "WARNING", "category": "REGIME",
            "ticker": "PORTFOLIO",
            "message": f"Regime: {regime}; Verdict: {gate}",
            "value": round(invested_pct, 2),
            "threshold": recommended_alloc,
        })
        alert_id += 1
    elif regime == "neutral":
        alerts.append({
            "id": alert_id, "level": "INFO", "category": "REGIME",
            "ticker": "PORTFOLIO",
            "message": f"Regime: {regime}; Verdict: {gate}",
            "value": round(invested_pct, 2),
            "threshold": recommended_alloc,
        })
        alert_id += 1

    if var_usd:
        alerts.append({
            "id": alert_id, "level": "INFO", "category": "RISK_BUDGET",
            "ticker": "PORTFOLIO",
            "message": f"VaR(95): ${var_usd:,.0f} ({'WARNING' if abs(portfolio_var) > 0.015 else 'OK'})",
            "value": round(portfolio_var, 4),
            "threshold": -0.015,
        })

    # 심각 / 경고 카운트
    critical_count = sum(1 for a in alerts if a["level"] == "CRITICAL")
    warning_count  = sum(1 for a in alerts if a["level"] == "WARNING")

    risk_status = "NORMAL"
    if critical_count > 0:   risk_status = "DANGER"
    elif warning_count > 0:  risk_status = "WATCH"

    # ── 결과 취합 ──────────────────────────────────────────────────────
    result = {
        "date":            analysis_date,
        "regime":          regime,
        "gate":            gate,
        "risk_status":     risk_status,
        "critical_count":  critical_count,
        "warning_count":   warning_count,
        "total_value":     round(total_value, 2),
        "cash_value":      round(cash_val, 2),
        "invested_pct":    round(invested_pct, 4),
        "recommended_alloc": recommended_alloc,
        "portfolio_var":   round(portfolio_var, 4) if portfolio_var else None,
        "portfolio_cvar":  round(portfolio_cvar, 4) if portfolio_cvar else None,
        "var_usd":         round(var_usd, 2) if var_usd else None,
        "spy_var95":       spy_var95,
        "spy_mdd":         mdd_val,
        "alerts":          alerts,
        "position_sizing": position_sizing,
        "sector_concentration": sector_concentration,
        "high_corr_pairs": high_corr_pairs[:10],
        "component_var":   component_var[:20],
        "cdar_cvar":       cdar_cvar_table,
    }

    # DB 저장
    _save(result)
    return result


def _to_python(obj):
    """numpy 타입을 Python 기본 타입으로 변환"""
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_python(v) for v in obj]
    if hasattr(obj, "item"):   # np.float64, np.int64 등
        return obj.item()
    return obj


def _save(data: dict):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS risk_portfolio (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,
                payload    TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(date)
            )
        """)
        con.execute("""
            INSERT OR REPLACE INTO risk_portfolio (date, payload, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (data["date"], json.dumps(_to_python(data), ensure_ascii=False)))
