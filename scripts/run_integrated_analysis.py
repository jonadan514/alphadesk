"""
통합 분석 파이프라인
Usage: python scripts/run_integrated_analysis.py [--date YYYY-MM-DD]
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.collectors.fetch_sp500_list import save_sp500_list
from src.collectors.fetch_sp500_prices import fetch_sp500_prices
from src.collectors.us_price_fetcher import USPriceFetcher
from src.analyzers.market_regime import MarketRegimeDetector
from src.analyzers.market_gate import USMarketGate
from src.analyzers.smart_money_screener_v2 import EnhancedSmartMoneyScreener
from src.analyzers.ai_summary_generator import OpenAISummaryGenerator
from src.analyzers.final_report_generator import FinalReportGenerator, ACTION_MAP
from src.us_market.index_predictor import IndexPredictor
from src.db.data_store import get_db, init_db, upsert_daily_report, upsert_regime, upsert_regime_history, upsert_market_gate, upsert_index_prediction, upsert_ai_summaries, upsert_risk, upsert_costs, upsert_full_scores
from src.portfolio.tracker import init_portfolio_tables, execute_sells, execute_buys, check_alerts, snapshot, get_portfolio_summary
from src.risk.portfolio_risk import compute_risk
from src.analyzers.sector_analyzer import analyze as analyze_sectors

SP500_CSV    = ROOT / "data" / "sp500_list.csv"
PRICES_CSV   = ROOT / "data" / "us_daily_prices.csv"

# ── helpers ────────────────────────────────────────────────────────────────

def _get_index_price(prices_df, ticker: str, as_of: str):
    try:
        sub = prices_df[prices_df["ticker"] == ticker]
        sub = sub[sub["date"] <= as_of].sort_values("date", ascending=False)
        return float(sub.iloc[0]["close"]) if not sub.empty else None
    except Exception:
        return None


def _mtime_days(path: Path) -> float:
    if not path.exists():
        return float("inf")
    return (time.time() - path.stat().st_mtime) / 86400


def _log(phase: str, msg: str, t0: float | None = None) -> None:
    elapsed = f"  [{time.time()-t0:.1f}s]" if t0 else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase}{elapsed}  {msg}")


# ── phases ─────────────────────────────────────────────────────────────────

def phase0_refresh_data(t0: float) -> tuple:
    _log("Phase0", "데이터 신선도 체크")

    if _mtime_days(SP500_CSV) > 7:
        _log("Phase0", "sp500_list.csv 재수집 중…")
        sp500_df = save_sp500_list()
    else:
        import pandas as pd
        sp500_df = pd.read_csv(SP500_CSV)
        _log("Phase0", f"sp500_list.csv 캐시 사용 ({len(sp500_df)}종목)", t0)

    if _mtime_days(PRICES_CSV) > 1:
        _log("Phase0", "가격 데이터 재다운로드 중 (시간 소요)…")
        prices_df = fetch_sp500_prices()
    else:
        import pandas as pd
        prices_df = pd.read_csv(PRICES_CSV)
        _log("Phase0", f"prices 캐시 사용 ({len(prices_df):,}행)", t0)

    # symbol → DataFrame 매핑
    price_map: dict = {}
    if not prices_df.empty and "Symbol" in prices_df.columns:
        import pandas as pd
        prices_df["Date"] = pd.to_datetime(prices_df["Date"])
        for sym, grp in prices_df.groupby("Symbol"):
            price_map[sym] = grp.set_index("Date").sort_index()

    return sp500_df, price_map


def phase1_market_analysis(t0: float) -> tuple:
    _log("Phase1", "시장 체제 분석 시작")

    regime_result = MarketRegimeDetector().detect()
    _log("Phase1", f"Regime={regime_result['regime']}  score={regime_result['weighted_score']}", t0)

    gate_result = USMarketGate().analyze()
    _log("Phase1", f"Gate={gate_result['gate']}", t0)

    spy_result = IndexPredictor("SPY").predict_next_week()
    _log("Phase1", f"SPY 예측={spy_result['direction']} prob={spy_result['probability']:.2f} conf={spy_result['confidence']}", t0)

    qqq_result = IndexPredictor("QQQ").predict_next_week()
    _log("Phase1", f"QQQ 예측={qqq_result['direction']} prob={qqq_result['probability']:.2f} conf={qqq_result['confidence']}", t0)

    index_result = {"spy": spy_result, "qqq": qqq_result}
    return regime_result, gate_result, index_result


def phase2_screening(sp500_df, price_map, t0: float):
    _log("Phase2", "스마트머니 스크리닝 시작")
    symbols = sp500_df["Symbol"].tolist()
    screener = EnhancedSmartMoneyScreener()
    picks_df = screener.screen(symbols, price_map)
    _log("Phase2", f"선별 완료: {len(picks_df)}종목 (전체 채점 {len(screener.full_scored)}종목)", t0)
    return picks_df, screener.full_scored


def phase2_5_ai_summary(picks_df, t0: float):
    _log("Phase2.5", "AI 요약 생성 시작 (GPT-4o mini)")
    generator = OpenAISummaryGenerator()
    ai_results = {}
    for _, row in picks_df.iterrows():
        symbol = row.get("symbol", "")
        stock_data = {
            "composite_score":   row.get("composite_score"),
            "grade":             row.get("grade"),
            "technical":         row.get("technical"),
            "fundamental":       row.get("fundamental"),
            "analyst":           row.get("analyst"),
            "relative_strength": row.get("relative_strength"),
            "sector":            row.get("sector", ""),
        }
        result = generator.generate(symbol, stock_data)

        # AI를 검사(prosecutor)로 활용 — thesis와 독립된 별도 호출로 약세 논거만 심사
        bear = generator.generate_bear_case(symbol, stock_data, market="US", sector=row.get("sector", ""))
        result["independent_bear_case_found"] = bear["bear_case_found"]
        result["independent_bear_cases"] = bear["bear_cases"]

        ai_results[symbol] = result
        _log("Phase2.5", f"{symbol} → {result.get('recommendation','?')} (conf={result.get('confidence','?')}, 독립약세={bear['bear_case_found']})", t0)

    import pandas as pd
    ai_df = pd.DataFrame([
        {"symbol": sym, **{k: v for k, v in data.items() if k != "ticker"}}
        for sym, data in ai_results.items()
    ])
    if not ai_df.empty:
        picks_df = picks_df.merge(ai_df, on="symbol", how="left")
    _log("Phase2.5", f"AI 요약 완료: {len(ai_results)}종목", t0)
    return picks_df, ai_results


def phase3_report(regime_result, gate_result, index_result, picks_df, full_scored, analysis_date: str, t0: float):
    _log("Phase3", "최종 리포트 생성")

    regime = regime_result["regime"]
    gate   = gate_result["gate"]

    report = FinalReportGenerator().generate(regime, gate, picks_df)
    report["analysis_date"]    = analysis_date
    report["index_prediction"] = index_result
    _log("Phase3", f"Verdict={report['verdict']}  picks={len(report['picks'])}", t0)

    # Build AI summaries payload for separate table
    def _confidence_level(conf) -> str:
        c = int(conf) if conf else 0
        if c >= 70: return "HIGH"
        if c >= 40: return "MODERATE"
        return "LOW"

    ai_summaries = []
    for p in report["picks"]:
        if p.get("thesis"):
            ai_summaries.append({
                "ticker":           p["symbol"],
                "recommendation":   p.get("recommendation", "HOLD"),
                "confidence":       p.get("confidence", 0),
                "confidence_level": _confidence_level(p.get("confidence", 0)),
                "thesis":           p.get("thesis"),
                "catalysts":        p.get("catalysts", []),
                "bear_cases":       p.get("bear_cases", []),
                "_fallback":        p.get("_fallback", False),
            })

    # 전체 채점 결과 (top-20 밖 포함) — 매수체크 폴백용 lean 페이로드.
    # grade는 절대 임계값, action은 (gate, grade)로 정해지므로 top-20을 왜곡하지 않는다.
    full_scores = []
    if full_scored is not None and not full_scored.empty:
        for _, r in full_scored.iterrows():
            g = r.get("grade", "F")
            full_scores.append({
                "symbol":          r.get("symbol"),
                "grade":           g,
                "composite_score": r.get("composite_score"),
                "action":          ACTION_MAP.get((gate, g), "SKIP"),
                "current_price":   r.get("current_price"),
                "target_price":    r.get("target_price"),  # 매수체크 손익비 자동 계산용
                "sector":          r.get("sector", ""),
            })

    # SQLite upsert
    conn = get_db()
    init_db(conn)
    upsert_daily_report(conn, analysis_date, report)
    upsert_regime(conn, regime_result)
    upsert_regime_history(conn, analysis_date, regime_result)
    upsert_market_gate(conn, gate_result)
    upsert_index_prediction(conn, index_result)
    if ai_summaries:
        upsert_ai_summaries(conn, {"summaries": ai_summaries})
    upsert_full_scores(conn, {"date": analysis_date, "gate": gate, "scores": full_scores})
    conn.close()
    _log("Phase3", f"DB upsert 완료 (전체 채점 {len(full_scores)}종목 저장)", t0)

    return report


def phase4_risk_and_costs(ai_results: dict, analysis_date: str, t0: float) -> None:
    import numpy as np
    import yfinance as yf
    _log("Phase4", "Risk 계산 + Costs 집계 시작")

    # ── Risk: SPY 1년 일간수익률 기반 VaR95 / MDD ──────────────────────────
    try:
        spy = yf.Ticker("SPY").history(period="1y", auto_adjust=True)
        closes = spy["Close"].dropna()
        daily_rets = closes.pct_change().dropna()
        var_95 = float(np.percentile(daily_rets, 5))
        roll_max = closes.cummax()
        drawdown = (closes - roll_max) / roll_max
        mdd = float(drawdown.min())
        risk_data = {
            "var_95": round(var_95, 6),
            "mdd":    round(mdd, 6),
            "computed_at": analysis_date,
        }
    except Exception as e:
        risk_data = {"var_95": None, "mdd": None, "error": str(e)}
    _log("Phase4", f"Risk: VaR95={risk_data.get('var_95')}  MDD={risk_data.get('mdd')}", t0)

    # ── Costs: OpenAI 토큰 집계 ────────────────────────────────────────────
    # gpt-4o-mini: $0.15/M input tokens, $0.60/M output tokens
    # 토큰 수는 API 응답의 usage를 기록하는 usage_tracker 싱글턴에서 읽는다
    from src.analyzers.ai_summary_generator import usage_tracker
    PRICE_IN  = 0.15 / 1_000_000
    PRICE_OUT = 0.60 / 1_000_000
    total_in  = usage_tracker.total_input_tokens
    total_out = usage_tracker.total_output_tokens
    cost_usd = round(total_in * PRICE_IN + total_out * PRICE_OUT, 6)

    entry = {
        "date":       analysis_date,
        "service":    "OpenAI",
        "model":      "gpt-4o-mini",
        "tokens_in":  total_in,
        "tokens_out": total_out,
        "cost_usd":   cost_usd,
        "note":       f"AI summary {len(ai_results)} stocks",
    }
    costs_data = {"entries": [entry]}
    _log("Phase4", f"Costs: in={total_in} out={total_out} cost=${cost_usd:.4f}", t0)

    conn = get_db()
    upsert_risk(conn, risk_data)
    upsert_costs(conn, costs_data)
    conn.close()
    _log("Phase4", "Risk + Costs DB upsert 완료", t0)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="US Stock Integrated Analysis")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print(f"  US Stock 통합 분석  |  date={args.date}")
    print("=" * 60)

    sp500_df, price_map = phase0_refresh_data(t0)
    regime_result, gate_result, index_result = phase1_market_analysis(t0)
    picks_df, full_scored = phase2_screening(sp500_df, price_map, t0)
    picks_df, ai_results = phase2_5_ai_summary(picks_df, t0)
    report   = phase3_report(regime_result, gate_result, index_result, picks_df, full_scored, args.date, t0)
    phase4_risk_and_costs(ai_results, args.date, t0)

    # ── Phase5 포트폴리오 트래킹 ───────────────────────────────────────────
    _log("Phase5", "포트폴리오 트래킹 업데이트")
    try:
        import pandas as pd
        prices_df = pd.read_csv(PRICES_CSV)
        prices_df.columns = [c.lower() for c in prices_df.columns]
        prices_df = prices_df.rename(columns={"symbol": "ticker", "date": "date"})

        regime = regime_result.get("regime", "neutral")
        picks_list = picks_df[["symbol", "grade"]].to_dict("records") if len(picks_df) else []

        init_portfolio_tables()
        execute_sells(prices_df, args.date, regime)
        execute_buys(picks_list, prices_df, args.date, regime, gate=gate_result.get("gate", "GO"))
        check_alerts(prices_df, args.date)

        spy_price  = _get_index_price(prices_df, "SPY",  args.date)
        qqq_price  = _get_index_price(prices_df, "QQQ",  args.date)
        snapshot(prices_df, args.date, spy_price, qqq_price)
        _log("Phase5", "포트폴리오 스냅샷 저장 완료", t0)
    except Exception as e:
        print(f"[Phase5 경고] 포트폴리오 업데이트 실패 (분석은 정상 완료): {e}")

    # ── Phase6 포트폴리오 리스크 분석 ─────────────────────────────────────
    _log("Phase6", "포트폴리오 리스크 분석 시작")
    try:
        compute_risk(args.date)
        _log("Phase6", "리스크 분석 저장 완료", t0)
    except Exception as e:
        print(f"[Phase6 경고] 리스크 분석 실패: {e}")

    # ── Phase7 섹터 분석 ────────────────────────────────────────────────
    _log("Phase7", "섹터 분석 시작")
    try:
        analyze_sectors()
        _log("Phase7", "섹터 분석 저장 완료", t0)
    except Exception as e:
        print(f"[Phase7 경고] 섹터 분석 실패: {e}")

    # WAL → 메인 DB 체크포인트 (Next.js readonly 연결이 즉시 읽을 수 있도록)
    try:
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(str(ROOT / "output" / "data.db"))
        _conn.execute("PRAGMA wal_checkpoint(FULL)")
        _conn.close()
        _log("Final", "WAL 체크포인트 완료")
    except Exception as e:
        print(f"[WAL 체크포인트 경고] {e}")

    elapsed = time.time() - t0
    print("=" * 60)
    print(f"  완료  |  총 소요: {elapsed:.1f}초")
    print(f"  Verdict: {report['verdict']}  |  Gate: {gate_result['gate']}  |  Regime: {regime_result['regime']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
