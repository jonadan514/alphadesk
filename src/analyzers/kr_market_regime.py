"""
한국 시장 체제 감지
- KOSPI(^KS11) 기반
- Trend / Volatility / Momentum(60일) / Breadth / USD/KRW 5개 센서
"""
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime


REGIME_LABELS = {
    "risk_on":  "Risk On (강세)",
    "neutral":  "Neutral (중립)",
    "risk_off": "Risk Off (약세)",
    "crisis":   "Crisis (위기)",
}


class KRMarketRegimeDetector:
    def detect(self) -> dict:
        kospi = yf.Ticker("^KS11").history(period="2y", auto_adjust=True)
        if kospi.empty or len(kospi) < 60:
            return self._fallback()

        close = kospi["Close"].dropna()

        # ── Sensor 1: Trend (KOSPI vs SMA200) ──────────────────────────────
        sma200 = close.rolling(200).mean()
        sma50  = close.rolling(50).mean()
        last   = float(close.iloc[-1])
        s200   = float(sma200.iloc[-1]) if not np.isnan(sma200.iloc[-1]) else last
        s50    = float(sma50.iloc[-1])  if not np.isnan(sma50.iloc[-1])  else last
        trend_score = 0.0
        if last > s200: trend_score += 1.0
        if last > s50:  trend_score += 0.5
        if s50  > s200: trend_score += 0.5

        # ── Sensor 2: Volatility (60일 실현 변동성, VIX 프록시) ────────────
        ret60 = close.pct_change().dropna().iloc[-60:]
        vol60 = float(ret60.std() * np.sqrt(252) * 100)  # annualized %
        if vol60 < 15:   vol_score = 2.0
        elif vol60 < 25: vol_score = 1.0
        elif vol60 < 35: vol_score = 0.0
        else:            vol_score = -1.0

        # ── Sensor 3: Momentum (60일 수익률 — 중기 관점) ──────────────────
        mom60 = float(close.iloc[-1] / close.iloc[-min(60, len(close)-1)] - 1) * 100
        mom20 = float(close.iloc[-1] / close.iloc[-min(20, len(close)-1)] - 1) * 100  # 표시용 단기 모멘텀
        if mom60 > 10:    mom_score = 2.0
        elif mom60 > 3:   mom_score = 1.0
        elif mom60 > -3:  mom_score = 0.0
        elif mom60 > -10: mom_score = -0.5
        else:             mom_score = -1.0

        # ── Sensor 4: Breadth (1년 KOSPI 누적 수익률) ──────────────────────
        ret250 = float(close.iloc[-1] / close.iloc[-min(250, len(close)-1)] - 1) * 100
        if ret250 > 20:    brd_score = 2.0
        elif ret250 > 5:   brd_score = 1.5
        elif ret250 > 0:   brd_score = 1.0
        elif ret250 > -10: brd_score = 0.0
        else:              brd_score = -1.0

        # ── Sensor 5: USD/KRW 환율 (외국인 수급 프록시) ────────────────────
        try:
            fx = yf.Ticker("KRW=X").history(period="3mo", auto_adjust=True)
            if fx is not None and not fx.empty:
                fx_close = fx["Close"].dropna()
                # 20일 환율 변화율 (원화 약세 = 외국인 이탈 = 위험)
                fx_chg = float(fx_close.iloc[-1] / fx_close.iloc[-min(20, len(fx_close)-1)] - 1) * 100
                if fx_chg > 5:    fx_score = -1.5   # 원화 급락 → 위험
                elif fx_chg > 2:  fx_score = -0.5   # 원화 약세
                elif fx_chg > -2: fx_score = 1.0    # 안정
                else:             fx_score = 1.5    # 원화 강세 → 외국인 유입
                usdkrw_last = round(float(fx_close.iloc[-1]), 2)
                usdkrw_chg  = round(fx_chg, 2)
            else:
                fx_score = 0.0
                usdkrw_last = None
                usdkrw_chg  = None
        except Exception:
            fx_score = 0.0
            usdkrw_last = None
            usdkrw_chg  = None

        # ── 가중 합산 ─────────────────────────────────────────────────────
        WEIGHTS = {"trend": 0.30, "vol": 0.20, "mom": 0.20, "brd": 0.15, "fx": 0.15}
        weighted = (
            trend_score * WEIGHTS["trend"] +
            vol_score   * WEIGHTS["vol"]   +
            mom_score   * WEIGHTS["mom"]   +
            brd_score   * WEIGHTS["brd"]   +
            fx_score    * WEIGHTS["fx"]
        )

        if weighted >= 1.5:    regime = "risk_on"
        elif weighted >= 0.5:  regime = "neutral"
        elif weighted >= -0.3: regime = "risk_off"
        else:                  regime = "crisis"

        # ── 급락 서킷브레이커 ─────────────────────────────────────────────
        # 추세(SMA200)·모멘텀(60일)·시장폭(250일)은 장기 후행이라 1~2주 급락을
        # 못 본다 (실례: 2026-07 KOSPI 주간 -12% 급락에도 neutral 판정).
        # 20일 수익률로 단기 급락을 직접 반영한다.
        circuit_breaker = None
        if mom20 <= -15 and regime != "crisis":
            circuit_breaker = f"20일 {mom20:.1f}% 급락 → crisis 강등"
            regime = "crisis"
        elif mom20 <= -8 and regime in ("risk_on", "neutral"):
            circuit_breaker = f"20일 {mom20:.1f}% 급락 → risk_off 강등"
            regime = "risk_off"

        sensor_scores = {
            "trend":      round(trend_score, 2),
            "volatility": round(vol_score, 2),
            "momentum":   round(mom_score, 2),
            "breadth":    round(brd_score, 2),
            "usdkrw":     round(fx_score, 2),
        }

        return {
            "market":         "KR",
            "regime":         regime,
            "regime_label":   REGIME_LABELS[regime],
            "weighted_score": round(weighted, 3),
            "sensor_scores":  sensor_scores,
            "kospi_last":     round(last, 2),
            "kospi_sma200":   round(s200, 2),
            "vol_60d":        round(vol60, 2),
            "mom_60d":        round(mom60, 2),
            "mom_20d":        round(mom20, 2),
            "usdkrw_last":    usdkrw_last,
            "usdkrw_chg_20d": usdkrw_chg,
            "circuit_breaker": circuit_breaker,   # 급락 강등 사유 (없으면 None)
            "computed_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def _fallback(self) -> dict:
        return {
            "market": "KR", "regime": "neutral",
            "regime_label": REGIME_LABELS["neutral"],
            "weighted_score": 0.5,
            "sensor_scores": {},
            "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


if __name__ == "__main__":
    import json
    r = KRMarketRegimeDetector().detect()
    print(json.dumps(r, ensure_ascii=False, indent=2))
