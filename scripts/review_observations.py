"""관찰 노트 주간 회고 - 작성 4주·12주가 지난 관찰에 "지금 값"을 붙인다 (src/db/observations.py).

테마 관찰: 그 테마의 최신 세 축·라벨·지수 대비 주가.
종목 관찰: 소속 테마 세 축·최근 기업별 값·재무 꼬리표 + 작성일 종가 대비 지금 수익률과 같은 기간 지수 수익률.
같은 체크포인트는 한 번만 쓴다. 판정은 사람이 화면에서 한다.

라벨 계산 직후(compute-theme-labels.yml)에 돈다.
    python scripts/review_observations.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.observations import (due_checkpoints, ensure_schema, expect_results, fill_review_returns,
                                 insert_review, load_open_observations, load_refill_candidates,
                                 stock_snapshot, theme_snapshot)
from src.db.theme_signals import signal_week_monday

INDEX_SYMBOL = {"US": "^GSPC", "KR": "^KS11"}


def _log(msg: str) -> None:
    print(f"[observe] {msg}", flush=True)


def yf_symbol(ticker: str, market: str) -> str:
    if market != "KR":
        return ticker          # 미국은 theme_members 표기 그대로(yfinance도 BRK-B 꼴)
    from collectors.kr_kospi_list import yf_suffix
    return f"{ticker}{yf_suffix(ticker)}"


def return_since(symbol: str, since: date, until: date | None = None) -> float | None:
    """since(작성일) 당일 또는 직전 거래일 종가 대비 until(기본 오늘) 당일 또는 직전 거래일 종가 수익률.
    조회 실패면 None. until은 빈 값을 나중에 채울 때 원래 회고일까지만 재기 위해 쓴다."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(start=(since - timedelta(days=10)).isoformat(), auto_adjust=True)["Close"].dropna()
    except Exception as e:  # noqa: BLE001
        _log(f"  {symbol} 시세 조회 실패 {type(e).__name__}")
        return None
    if hist.empty:
        return None
    idx = hist.index.tz_localize(None) if getattr(hist.index, "tz", None) is not None else hist.index
    before = hist[idx.date <= since]
    if before.empty:
        return None
    upto = hist[idx.date <= until] if until else hist
    if upto.empty:
        return None
    then, now = float(before.iloc[-1]), float(upto.iloc[-1])
    return None if then == 0 else now / then - 1


def main() -> int:
    conn = get_db()
    ensure_schema(conn)
    current_week = signal_week_monday(date.today()).isoformat()
    now_iso = datetime.utcnow().isoformat()
    written = 0
    for obs in load_open_observations(conn):
        for cp in due_checkpoints(obs["week_start"], current_week, obs["done"]):
            if obs["kind"] == "theme":
                snap = theme_snapshot(conn, obs["theme_id"], obs["market"])
                if not snap:
                    _log(f"#{obs['id']} {obs['theme_id']}: 테마 신호 없음 - 다음 주에 다시")
                    continue
            else:
                snap = stock_snapshot(conn, obs["ticker"], obs["market"])
                created = date.fromisoformat(obs["created_at"][:10])
                snap["ret_since"] = return_since(yf_symbol(obs["ticker"], obs["market"]), created)
                snap["index_ret_since"] = return_since(INDEX_SYMBOL.get(obs["market"], "^GSPC"), created)
                snap["week_start"] = snap.get("week_start") or current_week
            results = expect_results(obs["kind"], obs["expects"], snap)
            insert_review(conn, obs["id"], cp, now_iso, snap.get("week_start") or current_week, snap, results)
            conn.commit()
            written += 1
            _log(f"#{obs['id']} {obs['kind']} {obs['theme_id'] or obs['ticker']}({obs['market']}) {cp}주 회고: {results}")
    # 지난 회고 중 시세 조회 실패로 비어 있던 종목 수익률 다시 채우기(판단 전인 것만, 원래 회고일 기준)
    refilled = 0
    for rv in load_refill_candidates(conn):
        created = date.fromisoformat(rv["created_at"][:10])
        until = date.fromisoformat(rv["reviewed_at"][:10])
        snap = dict(rv["snapshot"])
        if snap.get("ret_since") is None:
            snap["ret_since"] = return_since(yf_symbol(rv["ticker"], rv["market"]), created, until)
        if snap.get("index_ret_since") is None:
            snap["index_ret_since"] = return_since(INDEX_SYMBOL.get(rv["market"], "^GSPC"), created, until)
        if snap.get("ret_since") is None or snap.get("index_ret_since") is None:
            continue
        fill_review_returns(conn, rv["observation_id"], rv["checkpoint"], snap, expect_results("stock", rv["expects"], snap))
        conn.commit()
        refilled += 1
        _log(f"#{rv['observation_id']} {rv['ticker']} {rv['checkpoint']}주 회고 - 빈 수익률 채움")
    _log(f"완료 - 회고 {written}건, 빈 값 채움 {refilled}건 (기준 주 {current_week})")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
