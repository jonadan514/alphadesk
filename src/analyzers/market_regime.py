import json
import time
import yfinance as yf
import pandas as pd
from pathlib import Path
from curl_cffi import requests as curl_requests
from src.collectors.macro_collector import MacroDataCollector

OUTPUT_PATH = Path(__file__).parents[2] / "output" / "regime_result.json"

WEIGHTS = {
    "vix":         0.25,
    "trend":       0.25,
    "breadth":     0.18,
    "credit":      0.15,
    "yield_curve": 0.17,
}

# sensor raw score → 0=benign, 1=neutral, 2=stressed, 3=crisis


class MarketRegimeDetector:
    def __init__(self):
        self._session = curl_requests.Session(impersonate="chrome")
        self._macro = MacroDataCollector()

    # ------------------------------------------------------------------
    # Individual sensors  (each returns float 0-3)
    # ------------------------------------------------------------------

    def _sensor_vix(self, vix: dict) -> float:
        v = vix.get("current")
        if v is None:
            return 1.0
        if v < 15:
            return 0.0
        if v < 20:
            return 0.5
        if v < 30:
            return 1.5
        if v < 40:
            return 2.5
        return 3.0

    def _sensor_trend(self) -> float:
        try:
            df = yf.Ticker("SPY", session=self._session).history(period="1y", auto_adjust=True)
            if df is None or df.empty:
                return 1.0
            close = df["Close"]
            sma50  = close.tail(50).mean()
            sma200 = close.tail(200).mean()
            cur    = float(close.iloc[-1])
            above50  = cur > sma50
            above200 = cur > sma200
            golden   = sma50 > sma200
            if above50 and above200 and golden:
                return 0.0
            if above200:
                return 0.75
            if above50:
                return 1.5
            return 2.5
        except Exception:
            return 1.0

    def _sensor_breadth(self) -> float:
        """NYSE advance/decline proxy via equal-weight vs cap-weight spread."""
        try:
            tickers = ["RSP", "SPY"]
            frames = {}
            for t in tickers:
                df = yf.Ticker(t, session=self._session).history(period="3mo", auto_adjust=True)
                if df is not None and not df.empty:
                    frames[t] = df["Close"]
            if len(frames) < 2:
                return 1.0
            rsp = frames["RSP"]
            spy = frames["SPY"]
            # align
            combined = pd.DataFrame({"RSP": rsp, "SPY": spy}).dropna()
            ret_rsp = float(combined["RSP"].iloc[-1] / combined["RSP"].iloc[0] - 1)
            ret_spy = float(combined["SPY"].iloc[-1] / combined["SPY"].iloc[0] - 1)
            spread = ret_rsp - ret_spy   # positive = broad participation
            if spread > 0.02:
                return 0.0
            if spread > -0.02:
                return 1.0
            if spread > -0.05:
                return 2.0
            return 3.0
        except Exception:
            return 1.0

    def _sensor_credit(self, fred: dict) -> float:
        hy = fred.get("BAMLH0A0HYM2", {}).get("value")
        if hy is None:
            return 1.0
        if hy < 3.5:
            return 0.0
        if hy < 5.0:
            return 1.0
        if hy < 7.0:
            return 2.0
        return 3.0

    def _sensor_yield_curve(self, fred: dict) -> float:
        spread = fred.get("T10Y2Y", {}).get("value")
        if spread is None:
            return 1.0
        if spread > 0.5:
            return 0.0
        if spread > 0.0:
            return 0.75
        if spread > -0.5:
            return 1.5
        return 2.5

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify(score: float) -> str:
        if score < 0.75:
            return "risk_on"
        if score < 1.5:
            return "neutral"
        if score < 2.25:
            return "risk_off"
        return "crisis"

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def _spy_metrics(self) -> dict:
        """SPY 현재가·SMA200·변동성·모멘텀 계산"""
        try:
            df = yf.Ticker("SPY", session=self._session).history(period="1y", auto_adjust=True)
            if df is None or df.empty:
                return {}
            close = df["Close"]
            cur    = float(close.iloc[-1])
            sma200 = float(close.tail(200).mean())
            vol60  = float(close.pct_change().tail(60).std() * (252 ** 0.5) * 100)
            mom20  = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
            return {
                "spy_last":   round(cur, 2),
                "spy_sma200": round(sma200, 2),
                "vol_60d":    round(vol60, 2),
                "mom_20d":    round(mom20, 2) if mom20 is not None else None,
            }
        except Exception:
            return {}

    def detect(self) -> dict:
        macro = self._macro.get_macro_summary()
        vix   = macro.get("vix", {})
        fred  = macro.get("fred", {})

        scores = {
            "vix":         self._sensor_vix(vix),
            "trend":       self._sensor_trend(),
            "breadth":     self._sensor_breadth(),
            "credit":      self._sensor_credit(fred),
            "yield_curve": self._sensor_yield_curve(fred),
        }

        weighted_score = sum(scores[k] * WEIGHTS[k] for k in scores)
        regime = self._classify(weighted_score)
        spy = self._spy_metrics()

        result = {
            "regime":         regime,
            "weighted_score": round(weighted_score, 4),
            "sensor_scores":  {k: round(v, 4) for k, v in scores.items()},
            "spy_last":       spy.get("spy_last"),
            "spy_sma200":     spy.get("spy_sma200"),
            "vol_60d":        spy.get("vol_60d"),
            "mom_20d":        spy.get("mom_20d"),
            "macro_snapshot": {
                "vix_current": vix.get("current"),
                "vix_ma20":    vix.get("ma20"),
                "hy_spread":   fred.get("BAMLH0A0HYM2", {}).get("value"),
                "t10y2y":      fred.get("T10Y2Y", {}).get("value"),
                "dff":         fred.get("DFF", {}).get("value"),
            },
            "collected_at": macro.get("collected_at"),
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"Regime: {regime}  |  Score: {weighted_score:.4f}  →  {OUTPUT_PATH}")
        return result


if __name__ == "__main__":
    detector = MarketRegimeDetector()
    result = detector.detect()
    print(json.dumps(result, indent=2, ensure_ascii=False))
