"""
페이퍼 트레이딩 포트폴리오 트래커

10개 포트폴리오 동시 운용:
  배분 방식: equal (균등) / weighted (등급가중)
  보유 기간: short(20일) / medium(60일) / long(120일) / 1y(365일) / 3y(1095일)

자동 매도 조건 (단기/중기/120일-장기 버킷만):
  - 보유 기간 초과
  - 손절선 도달 (체제별: risk_on=-10%, neutral=-8%, risk_off=-5%, crisis=-3%)
  - 수익선 도달 (단기=+15%, 중기=+25%, 120일=+40%)

1y/3y(펀더멘털 장기) 버킷은 가격 기반 손절·익절을 적용하지 않는다 — 대신
check_alerts()가 큰 폭 하락·펀더멘털 훼손을 감지해 portfolio_alerts에
알림만 남기고, 실제 매도는 사용자가 직접 판단한다. 보유기간 만료(1년/3년)만
자동 매도로 남겨 시뮬레이션을 마감할 수 있게 한다.
"""

import json
import sqlite3
from datetime import datetime, date
from typing import Optional

from src.db.data_store import get_db

STARTING_CASH = 100_000.0  # $100,000

PORTFOLIOS = [
    {"id": "equal_short",    "alloc": "equal",    "horizon": "short",  "hold_days": 20,  "take_profit": 0.15},
    {"id": "equal_medium",   "alloc": "equal",    "horizon": "medium", "hold_days": 60,  "take_profit": 0.25},
    {"id": "equal_long",     "alloc": "equal",    "horizon": "long",   "hold_days": 120, "take_profit": 0.40},
    {"id": "weighted_short",  "alloc": "weighted", "horizon": "short",  "hold_days": 20,  "take_profit": 0.15},
    {"id": "weighted_medium", "alloc": "weighted", "horizon": "medium", "hold_days": 60,  "take_profit": 0.25},
    {"id": "weighted_long",   "alloc": "weighted", "horizon": "long",   "hold_days": 120, "take_profit": 0.40},
    # 펀더멘털 장기 버킷 — take_profit 값은 DB 스키마상 NOT NULL이라 채워두지만
    # alert_only=True인 포트폴리오는 execute_sells()에서 이 값을 아예 참조하지 않는다.
    {"id": "equal_1y",     "alloc": "equal",    "horizon": "1y", "hold_days": 365,  "take_profit": 0.40, "alert_only": True},
    {"id": "equal_3y",     "alloc": "equal",    "horizon": "3y", "hold_days": 1095, "take_profit": 0.40, "alert_only": True},
    {"id": "weighted_1y",  "alloc": "weighted", "horizon": "1y", "hold_days": 365,  "take_profit": 0.40, "alert_only": True},
    {"id": "weighted_3y",  "alloc": "weighted", "horizon": "3y", "hold_days": 1095, "take_profit": 0.40, "alert_only": True},
]

STOP_LOSS = {
    "risk_on":  -0.10,
    "neutral":  -0.08,
    "risk_off": -0.05,
    "crisis":   -0.03,
}

GRADE_WEIGHT = {"A": 2.0, "B": 1.0, "C": 0.5}


def _conn() -> sqlite3.Connection:
    return get_db()


_PF_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS pf_portfolios (
        portfolio_id  TEXT PRIMARY KEY,
        alloc_type    TEXT NOT NULL,
        horizon       TEXT NOT NULL,
        hold_days     INTEGER NOT NULL,
        take_profit   REAL NOT NULL,
        cash          REAL NOT NULL DEFAULT 100000,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pf_holdings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id  TEXT NOT NULL,
        symbol        TEXT NOT NULL,
        grade         TEXT,
        shares        REAL NOT NULL,
        entry_price   REAL NOT NULL,
        entry_date    TEXT NOT NULL,
        weight        REAL NOT NULL,
        UNIQUE(portfolio_id, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pf_trades (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id  TEXT NOT NULL,
        symbol        TEXT NOT NULL,
        action        TEXT NOT NULL,
        shares        REAL NOT NULL,
        price         REAL NOT NULL,
        value         REAL NOT NULL,
        reason        TEXT,
        trade_date    TEXT NOT NULL,
        pnl           REAL,
        pnl_pct       REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pf_snapshots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id  TEXT NOT NULL,
        snap_date     TEXT NOT NULL,
        total_value   REAL NOT NULL,
        cash          REAL NOT NULL,
        holdings_value REAL NOT NULL,
        pnl_total     REAL NOT NULL,
        pnl_pct       REAL NOT NULL,
        UNIQUE(portfolio_id, snap_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pf_benchmark (
        snap_date     TEXT NOT NULL,
        ticker        TEXT NOT NULL,
        price         REAL NOT NULL,
        pnl_pct       REAL,
        PRIMARY KEY (snap_date, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_alerts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id  TEXT NOT NULL,
        symbol        TEXT NOT NULL,
        alert_type    TEXT NOT NULL,
        detail        TEXT NOT NULL,
        alert_date    TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(portfolio_id, symbol, alert_type, alert_date)
    )
    """,
]


def init_portfolio_tables():
    with _conn() as con:
        for ddl in _PF_TABLES_DDL:
            con.execute(ddl)


def _ensure_portfolio_rows():
    with _conn() as con:
        for pf in PORTFOLIOS:
            con.execute("""
                INSERT OR IGNORE INTO pf_portfolios
                  (portfolio_id, alloc_type, horizon, hold_days, take_profit, cash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pf["id"], pf["alloc"], pf["horizon"], pf["hold_days"], pf["take_profit"], STARTING_CASH))


def _calc_weights(picks: list[dict], alloc_type: str) -> dict[str, float]:
    """종목별 포트폴리오 비중 계산"""
    if not picks:
        return {}
    if alloc_type == "equal":
        w = 1.0 / len(picks)
        return {p["symbol"]: w for p in picks}
    # grade-weighted
    raw = {p["symbol"]: GRADE_WEIGHT.get(p.get("grade", "C"), 0.5) for p in picks}
    total = sum(raw.values())
    return {sym: w / total for sym, w in raw.items()}


def _get_price(prices_df, symbol: str, as_of: str) -> Optional[float]:
    """가격 데이터프레임에서 종목 가격 조회"""
    try:
        sub = prices_df[prices_df["ticker"] == symbol]
        sub = sub[sub["date"] <= as_of].sort_values("date", ascending=False)
        if sub.empty:
            return None
        return float(sub.iloc[0]["close"])
    except Exception:
        return None


def execute_buys(picks: list[dict], prices_df, trade_date: str, regime: str, gate: str = "GO"):
    """
    스크리닝 결과를 바탕으로 포트폴리오 매수 실행.
    기존 보유 종목은 유지하고, 새 자금으로 신규 매수.

    마켓 게이트가 GO가 아니면 단기/중기/120일-장기 버킷은 매수를 건너뛴다.
    펀더멘털 장기(1y/3y) 버킷은 게이트와 무관하게 매수한다 — 저평가된 좋은 기업을
    시장 전체가 안 좋을 때 사는 것도 장기 투자에서는 정당한 진입이라서,
    단기 트레이딩용 타이밍 게이트를 장기 매수까지 막게 두지 않는다.
    """
    _ensure_portfolio_rows()

    with _conn() as con:
        for pf in PORTFOLIOS:
            pid = pf["id"]
            alert_only = pf.get("alert_only", False)
            if not alert_only and gate != "GO":
                continue

            cash = con.execute("SELECT cash FROM pf_portfolios WHERE portfolio_id=?", (pid,)).fetchone()[0]

            # 이미 보유 중인 종목 제외
            held = {r[0] for r in con.execute("SELECT symbol FROM pf_holdings WHERE portfolio_id=?", (pid,))}
            new_picks = [p for p in picks if p["symbol"] not in held]

            if not new_picks or cash < 1000:
                continue

            weights = _calc_weights(new_picks, pf["alloc"])
            spent = 0.0

            for pick in new_picks:
                sym = pick["symbol"]
                w = weights.get(sym, 0)
                alloc = cash * w
                price = _get_price(prices_df, sym, trade_date)
                if not price or price <= 0 or alloc < 100:
                    continue

                shares = alloc / price
                con.execute("""
                    INSERT OR REPLACE INTO pf_holdings
                      (portfolio_id, symbol, grade, shares, entry_price, entry_date, weight)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pid, sym, pick.get("grade"), shares, price, trade_date, w))

                con.execute("""
                    INSERT INTO pf_trades
                      (portfolio_id, symbol, action, shares, price, value, reason, trade_date)
                    VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?)
                """, (pid, sym, shares, price, shares * price, f"스크리닝 진입 ({pf['alloc']}/{pf['horizon']})", trade_date))

                spent += shares * price

            con.execute("UPDATE pf_portfolios SET cash=cash-? WHERE portfolio_id=?", (spent, pid))


def execute_sells(prices_df, trade_date: str, regime: str):
    """
    자동 매도 조건 체크 후 매도 실행:
    1. 보유 기간 초과
    2. 손절선 도달
    3. 수익선 도달
    """
    stop_loss_pct = STOP_LOSS.get(regime, -0.08)

    with _conn() as con:
        for pf in PORTFOLIOS:
            pid = pf["id"]
            hold_days = pf["hold_days"]
            take_profit = pf["take_profit"]
            alert_only = pf.get("alert_only", False)

            holdings = con.execute("""
                SELECT symbol, shares, entry_price, entry_date, grade
                FROM pf_holdings WHERE portfolio_id=?
            """, (pid,)).fetchall()

            for sym, shares, entry_price, entry_date, grade in holdings:
                price = _get_price(prices_df, sym, trade_date)
                if not price:
                    continue

                pnl_pct = (price - entry_price) / entry_price
                days_held = (date.fromisoformat(trade_date) - date.fromisoformat(entry_date)).days

                # 펀더멘털 장기 버킷은 가격 기반 손절·익절 자동매도 없음 — check_alerts()가
                # 대신 알림만 남긴다. 보유기간 만료(1년/3년)만 시뮬레이션 마감용으로 유지.
                reason = None
                if days_held >= hold_days:
                    reason = f"보유 기간 만료 ({hold_days}일)"
                elif not alert_only and pnl_pct <= stop_loss_pct:
                    reason = f"손절선 도달 ({pnl_pct*100:.1f}%)"
                elif not alert_only and pnl_pct >= take_profit:
                    reason = f"수익선 도달 ({pnl_pct*100:.1f}%)"

                if reason:
                    value = shares * price
                    pnl = (price - entry_price) * shares

                    con.execute("""
                        INSERT INTO pf_trades
                          (portfolio_id, symbol, action, shares, price, value, reason, trade_date, pnl, pnl_pct)
                        VALUES (?, ?, 'SELL', ?, ?, ?, ?, ?, ?, ?)
                    """, (pid, sym, shares, price, value, reason, trade_date, pnl, pnl_pct))

                    con.execute("DELETE FROM pf_holdings WHERE portfolio_id=? AND symbol=?", (pid, sym))
                    con.execute("UPDATE pf_portfolios SET cash=cash+? WHERE portfolio_id=?", (value, pid))


PRICE_DRAWDOWN_ALERT_PCT = -0.20  # 매수가 대비 이만큼 하락하면 알림 (자동매도 아님)

ALERT_ONLY_HORIZONS = {"1y", "3y"}


def check_alerts(prices_df, trade_date: str) -> None:
    """펀더멘털 장기(1y/3y) 버킷 보유 종목의 큰 폭 하락·재무 훼손을 점검해
    portfolio_alerts에 알림만 남긴다. 실제 매도는 사용자 판단 — 여기선 절대 안 판다.
    """
    from src.analyzers.trap_filter import apply_trap_filters
    from src.collectors.watchlist_collector import fetch_financials

    long_term_ids = [pf["id"] for pf in PORTFOLIOS if pf.get("horizon") in ALERT_ONLY_HORIZONS]
    if not long_term_ids:
        return

    fin_cache: dict[str, dict | None] = {}

    with _conn() as con:
        for pid in long_term_ids:
            holdings = con.execute(
                "SELECT symbol, entry_price FROM pf_holdings WHERE portfolio_id=?", (pid,)
            ).fetchall()

            for sym, entry_price in holdings:
                price = _get_price(prices_df, sym, trade_date)
                if not price or not entry_price:
                    continue

                # 1) 큰 폭 하락 알림
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct <= PRICE_DRAWDOWN_ALERT_PCT:
                    _upsert_alert(con, pid, sym, "price_drawdown", {
                        "pnl_pct": round(pnl_pct, 4),
                        "entry_price": entry_price,
                        "cur_price": price,
                    }, trade_date)

                # 2) 펀더멘털 훼손 알림 — 종목당 하루 한 번만 조회(여러 포트폴리오가 같은
                #    종목을 들고 있을 수 있어 캐시)
                if sym not in fin_cache:
                    try:
                        fin_cache[sym] = fetch_financials(sym)
                    except Exception:
                        fin_cache[sym] = None
                fin_data = fin_cache[sym]
                if not fin_data:
                    continue
                try:
                    result = apply_trap_filters({"symbol": sym, "sector": "", "financials_data": fin_data})
                except Exception:
                    continue
                if not result["pass"]:
                    _upsert_alert(con, pid, sym, "fundamental", {
                        "red_flags": result["red_flags"],
                        "piotroski": result["piotroski"],
                    }, trade_date)


def _upsert_alert(con, portfolio_id: str, symbol: str, alert_type: str, detail: dict, trade_date: str) -> None:
    con.execute("""
        INSERT INTO portfolio_alerts (portfolio_id, symbol, alert_type, detail, alert_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(portfolio_id, symbol, alert_type, alert_date) DO UPDATE SET
            detail = excluded.detail
    """, (portfolio_id, symbol, alert_type, json.dumps(detail, ensure_ascii=False), trade_date))


def get_recent_alerts(days: int = 30) -> list[dict]:
    """프론트엔드용 최근 알림 목록."""
    with _conn() as con:
        rows = con.execute("""
            SELECT portfolio_id, symbol, alert_type, detail, alert_date, created_at
            FROM portfolio_alerts
            WHERE alert_date >= date('now', ?)
            ORDER BY created_at DESC
        """, (f"-{days} days",)).fetchall()
    out = []
    for pid, sym, atype, detail, adate, created in rows:
        try:
            detail_obj = json.loads(detail)
        except (TypeError, ValueError):
            detail_obj = {}
        out.append({
            "portfolio_id": pid, "symbol": sym, "alert_type": atype,
            "detail": detail_obj, "alert_date": adate, "created_at": created,
        })
    return out


def snapshot(prices_df, snap_date: str, spy_price: float = None, qqq_price: float = None):
    """포트폴리오 현재 가치 스냅샷 저장"""
    with _conn() as con:
        for pf in PORTFOLIOS:
            pid = pf["id"]
            cash = con.execute("SELECT cash FROM pf_portfolios WHERE portfolio_id=?", (pid,)).fetchone()[0]

            holdings = con.execute("""
                SELECT symbol, shares, entry_price FROM pf_holdings WHERE portfolio_id=?
            """, (pid,)).fetchall()

            holdings_value = 0.0
            for sym, shares, entry_price in holdings:
                price = _get_price(prices_df, sym, snap_date) or entry_price
                holdings_value += shares * price

            total = cash + holdings_value
            pnl_total = total - STARTING_CASH
            pnl_pct = pnl_total / STARTING_CASH

            con.execute("""
                INSERT OR REPLACE INTO pf_snapshots
                  (portfolio_id, snap_date, total_value, cash, holdings_value, pnl_total, pnl_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pid, snap_date, total, cash, holdings_value, pnl_total, pnl_pct))

        # 벤치마크 저장
        first_snap = con.execute("""
            SELECT snap_date, total_value FROM pf_snapshots
            WHERE portfolio_id='equal_short' ORDER BY snap_date ASC LIMIT 1
        """).fetchone()

        for ticker, price in [("SPY", spy_price), ("QQQ", qqq_price)]:
            if not price:
                continue
            first_price_row = con.execute("""
                SELECT price FROM pf_benchmark WHERE ticker=? ORDER BY snap_date ASC LIMIT 1
            """, (ticker,)).fetchone()
            first_price = first_price_row[0] if first_price_row else price
            pnl_pct = (price - first_price) / first_price if first_price else 0

            con.execute("""
                INSERT OR REPLACE INTO pf_benchmark (snap_date, ticker, price, pnl_pct)
                VALUES (?, ?, ?, ?)
            """, (snap_date, ticker, price, pnl_pct))


def get_portfolio_summary() -> dict:
    """프론트엔드용 포트폴리오 전체 요약 데이터 반환"""
    with _conn() as con:
        result = {}

        for pf in PORTFOLIOS:
            pid = pf["id"]

            # 현재 보유 종목
            holdings = con.execute("""
                SELECT h.symbol, h.grade, h.shares, h.entry_price, h.entry_date, h.weight
                FROM pf_holdings h WHERE h.portfolio_id=?
            """, (pid,)).fetchall()

            # 최신 스냅샷
            snap = con.execute("""
                SELECT total_value, cash, holdings_value, pnl_total, pnl_pct, snap_date
                FROM pf_snapshots WHERE portfolio_id=? ORDER BY snap_date DESC LIMIT 1
            """, (pid,)).fetchone()

            # 스냅샷 이력 (차트용)
            history = con.execute("""
                SELECT snap_date, total_value, pnl_pct
                FROM pf_snapshots WHERE portfolio_id=? ORDER BY snap_date ASC
            """, (pid,)).fetchall()

            # 거래 이력
            trades = con.execute("""
                SELECT symbol, action, shares, price, value, reason, trade_date, pnl, pnl_pct
                FROM pf_trades WHERE portfolio_id=? ORDER BY trade_date DESC LIMIT 50
            """, (pid,)).fetchall()

            result[pid] = {
                "config": pf,
                "snapshot": {
                    "total_value": snap[0] if snap else STARTING_CASH,
                    "cash": snap[1] if snap else STARTING_CASH,
                    "holdings_value": snap[2] if snap else 0,
                    "pnl_total": snap[3] if snap else 0,
                    "pnl_pct": snap[4] if snap else 0,
                    "as_of": snap[5] if snap else None,
                },
                "holdings": [
                    {"symbol": r[0], "grade": r[1], "shares": r[2],
                     "entry_price": r[3], "entry_date": r[4], "weight": r[5]}
                    for r in holdings
                ],
                "history": [
                    {"date": r[0], "total_value": r[1], "pnl_pct": r[2]}
                    for r in history
                ],
                "trades": [
                    {"symbol": r[0], "action": r[1], "shares": r[2], "price": r[3],
                     "value": r[4], "reason": r[5], "date": r[6], "pnl": r[7], "pnl_pct": r[8]}
                    for r in trades
                ],
            }

        # 벤치마크
        benchmarks = {}
        for ticker in ["SPY", "QQQ"]:
            rows = con.execute("""
                SELECT snap_date, price, pnl_pct FROM pf_benchmark
                WHERE ticker=? ORDER BY snap_date ASC
            """, (ticker,)).fetchall()
            benchmarks[ticker] = [{"date": r[0], "price": r[1], "pnl_pct": r[2]} for r in rows]

        result["benchmarks"] = benchmarks
        return result
