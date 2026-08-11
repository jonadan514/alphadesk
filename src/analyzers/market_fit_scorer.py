"""시장 적합 점수 (Market Fit Score, 0~100).

함정 필터 통과 종목을 "지금 시장에서 살 만한 순서"로 줄 세운다.

  품질     40점 — Piotroski, ROE, 이자보상배율 (재무가 얼마나 탄탄한가)
  모멘텀   35점 — 3·6개월 지수 대비 상대수익률 (시장이 지금 사주고 있는가)
  체제정합 25점 — 현재 시장 체제(risk_on/neutral/risk_off)와 종목 성격의 궁합

모멘텀은 네러티브의 정량 지표: 시장이 스토리를 믿기 시작하면 가격에 먼저 나타난다.
"""
from __future__ import annotations

import json
import logging

from db.turso_http import get_credentials, query as turso_query

logger = logging.getLogger(__name__)

BENCHMARK = {"US": "SPY", "KR": "^KS11"}

# 체제 × 종목성격 → 점수 (25점 만점)
REGIME_MATCH = {
    "risk_on":  {"growth": 25, "neutral": 15, "dividend": 8},
    "neutral":  {"growth": 15, "neutral": 15, "dividend": 15},
    "risk_off": {"growth": 8,  "neutral": 15, "dividend": 25},
    "crisis":   {"growth": 5,  "neutral": 12, "dividend": 25},
}


# ── 현재 시장 체제 조회 (Turso) ─────────────────────────────────────────────

def get_current_regime(market: str) -> str:
    """Turso에서 최신 체제 읽기. 실패 시 neutral."""
    if not get_credentials():
        return "neutral"

    table = "kr_regime" if market == "KR" else "data_regime"
    try:
        rows = turso_query(f"SELECT payload FROM {table} WHERE id = 1")
        payload = json.loads(rows[0]["payload"])
        regime = payload.get("regime", "neutral")
        return regime if regime in REGIME_MATCH else "neutral"
    except Exception:
        logger.warning("%s 체제 조회 실패 — neutral 가정", market)
        return "neutral"


# ── 모멘텀 (지수 대비 상대수익률) ────────────────────────────────────────────

def fetch_momentum(candidates: list[dict]) -> dict[str, tuple[float | None, float | None]]:
    """{market:symbol → (3개월 상대수익률, 6개월 상대수익률)}. 실패 종목은 (None, None)."""
    import yfinance as yf

    def _returns(closes) -> tuple[float | None, float | None]:
        closes = closes.dropna()
        if len(closes) < 70:
            return None, None
        last = float(closes.iloc[-1])
        r3 = last / float(closes.iloc[-63]) - 1 if len(closes) >= 63 else None
        r6 = last / float(closes.iloc[-126]) - 1 if len(closes) >= 126 else None
        return r3, r6

    out: dict[str, tuple[float | None, float | None]] = {}

    for market in ("US", "KR"):
        group = [c for c in candidates if c["market"] == market and c.get("yf_symbol")]
        if not group:
            continue
        symbols = [c["yf_symbol"] for c in group] + [BENCHMARK[market]]
        try:
            data = yf.download(
                symbols, period="7mo", interval="1d",
                auto_adjust=True, progress=False, group_by="ticker", threads=True,
            )
        except Exception as e:
            logger.error("%s 가격 다운로드 실패: %s", market, e)
            for c in group:
                out[f"{market}:{c['symbol']}"] = (None, None)
            continue

        def _closes(sym):
            try:
                if hasattr(data.columns, "levels"):
                    return data[sym]["Close"]
                return data["Close"]
            except Exception:
                import pandas as pd
                return pd.Series(dtype=float)

        bench3, bench6 = _returns(_closes(BENCHMARK[market]))
        for c in group:
            r3, r6 = _returns(_closes(c["yf_symbol"]))
            rel3 = (r3 - bench3) if (r3 is not None and bench3 is not None) else None
            rel6 = (r6 - bench6) if (r6 is not None and bench6 is not None) else None
            out[f"{market}:{c['symbol']}"] = (rel3, rel6)

    return out


# ── 점수 계산 ────────────────────────────────────────────────────────────────

def _quality_points(c: dict) -> float:
    """품질 40점: Piotroski 20 + ROE 10 + 이자보상 10."""
    pts = 0.0
    if c.get("piotroski") is not None:
        pts += c["piotroski"] / 9 * 20
    roe = c.get("roe")
    if roe is not None:
        pts += 10 if roe >= 20 else 8 if roe >= 15 else 5 if roe >= 10 else 3
    ic = c.get("interest_coverage")
    if ic is not None:
        pts += 10 if ic >= 10 else 7 if ic >= 5 else 4 if ic >= 3 else 2
    else:
        pts += 5  # 무차입 등으로 이자비용 없음 → 중간값
    return pts


def _momentum_points(rel3: float | None, rel6: float | None) -> float:
    """모멘텀 35점: 3개월(±20% 클램프) 17.5 + 6개월(±30% 클램프) 17.5."""
    def scaled(rel, cap):
        if rel is None:
            return 8.75  # 데이터 없으면 중간값
        x = max(-cap, min(cap, rel))
        return (x + cap) / (2 * cap) * 17.5
    return scaled(rel3, 0.20) + scaled(rel6, 0.30)


def score_and_rank(candidates: list[dict], top_n: int = 50) -> list[dict]:
    """적합 점수 계산 후 시장별 상위 top_n 반환 (점수 내림차순)."""
    momentum = fetch_momentum(candidates)
    regimes = {m: get_current_regime(m) for m in ("US", "KR")}
    logger.info("체제: US=%s KR=%s", regimes["US"], regimes["KR"])

    for c in candidates:
        key = f"{c['market']}:{c['symbol']}"
        rel3, rel6 = momentum.get(key, (None, None))
        regime = regimes.get(c["market"], "neutral")
        fit = REGIME_MATCH[regime].get(c.get("regime_fit", "neutral"), 15)

        c["rel_3m"] = round(rel3 * 100, 1) if rel3 is not None else None
        c["rel_6m"] = round(rel6 * 100, 1) if rel6 is not None else None
        c["fit_score"] = round(
            _quality_points(c) + _momentum_points(rel3, rel6) + fit, 1
        )

    result = []
    for market in ("US", "KR"):
        group = [c for c in candidates if c["market"] == market]
        group.sort(key=lambda c: c["fit_score"], reverse=True)
        result += group[:top_n]
        logger.info("%s: %d종목 중 상위 %d종목 선정", market, len(group), min(top_n, len(group)))

    return result
