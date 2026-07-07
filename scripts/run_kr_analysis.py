"""
한국 주식 통합 분석 파이프라인
Usage: python scripts/run_kr_analysis.py [--date YYYY-MM-DD]
"""
import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db


def _log(phase: str, msg: str, t0: float | None = None) -> None:
    elapsed = f"  [{time.time()-t0:.1f}s]" if t0 else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase}{elapsed}  {msg}")


_KR_TABLES = [
    """CREATE TABLE IF NOT EXISTS kr_daily_reports (
        date        TEXT PRIMARY KEY,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS kr_regime (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        payload     TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS kr_market_gate (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        payload     TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS kr_sector_analysis (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT NOT NULL UNIQUE,
        payload    TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS kr_ai_summaries (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        payload     TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS kr_index_prediction (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        payload     TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
]


def _init_kr_tables(conn) -> None:
    for ddl in _KR_TABLES:
        conn.execute(ddl)
    conn.commit()


def _sanitize(obj):
    """NaN/Infinity → None (JSON 스펙 준수)"""
    import math
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _upsert_timeseries(conn, table: str, date: str, data: dict) -> None:
    payload = json.dumps(_sanitize(data), ensure_ascii=False, default=str)
    conn.execute(
        f"""
        INSERT INTO {table} (date, payload)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET
            payload    = excluded.payload,
            created_at = datetime('now')
        """,
        (date, payload),
    )
    conn.commit()


def _upsert_snapshot(conn, table: str, data: dict) -> None:
    payload = json.dumps(_sanitize(data), ensure_ascii=False, default=str)
    conn.execute(
        f"""
        INSERT INTO {table} (id, payload)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            payload    = excluded.payload,
            updated_at = datetime('now')
        """,
        (payload,),
    )
    conn.commit()


# ── phases ─────────────────────────────────────────────────────────────────

def phase1_regime(t0: float) -> dict:
    _log("Phase1", "한국 시장 체제 분석 시작")
    from src.analyzers.kr_market_regime import KRMarketRegimeDetector
    result = KRMarketRegimeDetector().detect()
    _log("Phase1", f"Regime={result['regime']}  score={result['weighted_score']}", t0)
    return result


def phase2_gate(regime_result: dict, t0: float) -> dict:
    _log("Phase2", "마켓 게이트 판단")
    regime = regime_result["regime"]
    weighted = regime_result["weighted_score"]

    if regime == "risk_on":
        gate = "GO"
        reason = "KOSPI 강세장 — 적극 매수 가능"
    elif regime == "neutral":
        gate = "GO"
        reason = "중립 시장 — 선별 매수"
    elif regime == "risk_off":
        gate = "CAUTION"
        reason = "약세 신호 — 신규 진입 자제"
    else:  # crisis
        gate = "STOP"
        reason = "위기 — 현금 보유"

    result = {
        "market":    "KR",
        "gate":      gate,
        "regime":    regime,
        "score":     weighted,
        "reason":    reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _log("Phase2", f"Gate={gate}", t0)
    return result


def phase3_screening(regime: str, analysis_date: str, t0: float) -> dict:
    _log("Phase3", "KOSPI 스크리닝 시작")
    from src.analyzers.kr_screener import KRStockScreener
    picks_df = KRStockScreener().screen(regime)
    _log("Phase3", f"스크리닝 완료: {len(picks_df)}종목", t0)

    picks = picks_df.to_dict("records") if not picks_df.empty else []
    buy_picks   = [p for p in picks if p.get("action") == "BUY"]
    watch_picks = [p for p in picks if p.get("action") == "WATCH"]

    # verdict 결정
    if regime in ("risk_on",):
        verdict = "GO" if buy_picks else "CAUTION"
    elif regime == "neutral":
        verdict = "GO" if len(buy_picks) >= 3 else "CAUTION"
    else:
        verdict = "STOP"

    report = {
        "analysis_date": analysis_date,
        "market":        "KR",
        "regime":        regime,
        "verdict":       verdict,
        "picks":         picks,
        "buy_count":     len(buy_picks),
        "watch_count":   len(watch_picks),
        "summary":       f"BUY {len(buy_picks)}종목, WATCH {len(watch_picks)}종목 선별",
    }
    _log("Phase3", f"Verdict={verdict}  BUY={len(buy_picks)}", t0)
    return report


def phase3_5_ai_summary(report: dict, regime_result: dict, sector_result: dict | None, t0: float) -> list:
    _log("Phase3.5", "KR AI 요약 생성 (GPT-4o mini)")
    try:
        from src.analyzers.ai_summary_generator import OpenAISummaryGenerator
    except ImportError:
        _log("Phase3.5", "OpenAISummaryGenerator import 실패 — 건너뜀")
        return []

    picks = [p for p in report.get("picks", []) if p.get("action") == "BUY"][:15]
    generator = OpenAISummaryGenerator()
    summaries = []

    # 시장 컨텍스트 문자열 구성
    regime      = regime_result.get("regime_label", regime_result.get("regime", ""))
    kospi_last  = regime_result.get("kospi_last", "")
    mom20       = float(regime_result.get("mom_20d") or 0)
    vol60       = float(regime_result.get("vol_60d") or 0)
    cycle_label = sector_result.get("cycle_label", "") if sector_result else ""
    top_sectors = []
    if sector_result:
        for s in (sector_result.get("sectors") or [])[:3]:
            top_sectors.append(f"{s.get('sector','')} ({s.get('rs_20d',0):+.1f}%)")

    market_context = (
        f"KOSPI 체제: {regime} | KOSPI: {kospi_last} | 20일 모멘텀: {mom20:+.1f}% | 60일 변동성: {vol60:.1f}%\n"
        f"경기 사이클: {cycle_label}\n"
        f"강세 섹터: {', '.join(top_sectors) if top_sectors else '데이터 없음'}"
    )

    for p in picks:
        stock_data = {
            "composite_score":   p.get("composite_score"),
            "grade":             p.get("grade"),
            "technical_score":   p.get("technical"),
            "fundamental_score": p.get("fundamental"),
            "relative_strength_vs_kospi": p.get("relative_strength"),
            "volume_score":      p.get("volume"),
            "cur_price_krw":     p.get("cur_price"),
            "per":               p.get("per"),
            "pbr":               p.get("pbr"),
            "roe_pct":           p.get("roe"),
            "market_cap_krw":    p.get("market_cap"),
            "week52_high":       p.get("week52_high"),
            "week52_low":        p.get("week52_low"),
            "pct_from_52w_high": p.get("pct_from_52h"),
            "dividend_yield_pct": p.get("dividend_yield"),
            "earnings_growth_pct": p.get("earnings_growth"),
            "debt_to_equity":    p.get("debt_to_equity"),
        }
        result = generator.generate(
            p["symbol"], stock_data,
            market="KR",
            market_context=market_context,
            name=p.get("name", ""),
            sector=p.get("sector", ""),
        )
        summaries.append({
            "ticker":           p["symbol"],
            "name":             p.get("name", ""),
            "sector":           p.get("sector", ""),
            "recommendation":   result.get("recommendation", "HOLD"),
            "confidence":       result.get("confidence", 0),
            "thesis":           result.get("thesis", ""),
            "catalysts":        result.get("catalysts", []),
            "bear_cases":       result.get("bear_cases", []),
            "target_price":     result.get("target_price"),
            "composite_score":  p.get("composite_score"),
            "grade":            p.get("grade"),
            "cur_price":        p.get("cur_price"),
            "_fallback":        result.get("_fallback", False),
        })
        _log("Phase3.5", f"{p['symbol']}({p.get('name','')}) → {result.get('recommendation','?')}  목표가: {result.get('target_price','?')}", t0)

    _log("Phase3.5", f"AI 요약 완료: {len(summaries)}종목", t0)
    return summaries


def phase5_index_prediction(t0: float) -> dict:
    _log("Phase5", "KOSPI 방향 예측 (LightGBM) 시작")
    try:
        from src.analyzers.kr_index_predictor import KrIndexPredictor
        result = KrIndexPredictor().predict_next_week()
        _log("Phase5", f"방향={result['direction']}  확률={result['probability']}  CV={result.get('cv_accuracy')}", t0)
        return result
    except Exception as e:
        _log("Phase5", f"예측 실패: {e}")
        return {}


def phase4_sector(t0: float) -> dict:
    _log("Phase4", "섹터 분석 시작")
    try:
        from src.analyzers.kr_sector_analyzer import analyze
        result = analyze()
        _log("Phase4", f"사이클={result['cycle_label']}", t0)
        return result
    except Exception as e:
        _log("Phase4", f"섹터 분석 실패: {e}")
        return {}


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="KR Stock Integrated Analysis")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()
    analysis_date = args.date

    t0 = time.time()
    print("=" * 60)
    print(f"  KR Stock 통합 분석  |  date={analysis_date}")
    print("=" * 60)

    conn = get_db()
    _init_kr_tables(conn)

    try:
        regime_result = phase1_regime(t0)
        _upsert_snapshot(conn, "kr_regime", regime_result)

        gate_result = phase2_gate(regime_result, t0)
        _upsert_snapshot(conn, "kr_market_gate", gate_result)

        report = phase3_screening(regime_result["regime"], analysis_date, t0)
        _upsert_timeseries(conn, "kr_daily_reports", analysis_date, report)

        sector_result = phase4_sector(t0)
        # sector analyzer saves itself to kr_sector_analysis

        ai_summaries = phase3_5_ai_summary(report, regime_result, sector_result, t0)
        if ai_summaries:
            _upsert_snapshot(conn, "kr_ai_summaries", {"summaries": ai_summaries})

        kr_pred = phase5_index_prediction(t0)
        if kr_pred:
            _upsert_snapshot(conn, "kr_index_prediction", kr_pred)

    finally:
        conn.close()

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
