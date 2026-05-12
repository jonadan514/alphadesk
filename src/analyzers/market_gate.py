from src.analyzers.market_regime import MarketRegimeDetector

REGIME_GATE = {
    "risk_on":  "GO",
    "neutral":  "CAUTION",
    "risk_off": "STOP",
    "crisis":   "STOP",
}


class USMarketGate:
    def __init__(self):
        self._detector = MarketRegimeDetector()

    def analyze(self) -> dict:
        regime_result = self._detector.detect()
        regime        = regime_result["regime"]
        gate          = REGIME_GATE.get(regime, "CAUTION")
        avg_score     = regime_result["weighted_score"]

        result = {
            "gate":           gate,
            "regime":         regime,
            "avg_score":      avg_score,
            "sensor_scores":  regime_result["sensor_scores"],
            "macro_snapshot": regime_result["macro_snapshot"],
            "collected_at":   regime_result["collected_at"],
        }
        return result
