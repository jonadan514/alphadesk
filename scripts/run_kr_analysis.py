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

from src.db.data_store import get_db, init_db


def _log(phase: str, msg: str, t0: float | None = None) -> None:
    elapsed = f"  [{time.time()-t0:.1f}s]" if t0 else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase}{elapsed}  {msg}")


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

    # ── 위기 센서 거부권 ──────────────────────────────────────────────
    # 개별 센서가 위기 수준(-1.0 이하)이면 가중 평균이 좋아도 게이트를
    # 한 단계 강등한다. (예: 변동성 66%로 위기인데 장기 센서들이 좋아
    # 종합 GO가 나오는 상황 방지)
    SENSOR_KO = {"trend": "추세", "volatility": "변동성", "momentum": "모멘텀",
                 "breadth": "시장폭", "usdkrw": "환율"}
    sensors = regime_result.get("sensor_scores", {}) or {}
    crisis_sensors = [SENSOR_KO.get(k, k) for k, v in sensors.items()
                      if isinstance(v, (int, float)) and v <= -1.0]
    if crisis_sensors:
        label = "·".join(crisis_sensors)
        if gate == "GO":
            gate = "CAUTION"
            reason = f"{label} 위기 신호 — 신규 진입 신중 (거부권 강등)"
        elif gate == "CAUTION":
            gate = "STOP"
            reason = f"{label} 위기 신호 — 진입 보류 (거부권 강등)"
        _log("Phase2", f"센서 거부권 발동: {label} → {gate}")

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


def phase3_report(regime: str, gate: str, analysis_date: str, t0: float) -> dict:
    """일간 리포트 — 체제/게이트만 저장 (종목 픽은 주간 워치리스트 스크리닝이 담당)."""
    report = {
        "analysis_date": analysis_date,
        "market":        "KR",
        "regime":        regime,
        "gate":          gate,
    }
    _log("Phase3", f"Regime={regime}  Gate={gate}", t0)
    return report


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
    init_db(conn)

    try:
        regime_result = phase1_regime(t0)
        _upsert_snapshot(conn, "kr_regime", regime_result)
        _upsert_timeseries(conn, "kr_regime_history", analysis_date, regime_result)

        gate_result = phase2_gate(regime_result, t0)
        _upsert_snapshot(conn, "kr_market_gate", gate_result)

        report = phase3_report(regime_result["regime"], gate_result["gate"], analysis_date, t0)
        _upsert_timeseries(conn, "kr_daily_reports", analysis_date, report)

        sector_result = phase4_sector(t0)
        # sector analyzer saves itself to kr_sector_analysis

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
    print(f"  Gate: {gate_result['gate']}  |  Regime: {regime_result['regime']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
