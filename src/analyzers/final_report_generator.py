import json
import pandas as pd
from datetime import datetime
from pathlib import Path

OUTPUT_PATH = Path(__file__).parents[2] / "output" / "latest_report.json"

# (gate, grade) -> action
ACTION_MAP = {
    ("GO",      "A"): "BUY",
    ("GO",      "B"): "BUY",
    ("GO",      "C"): "WATCH",
    ("GO",      "D"): "WATCH",
    ("GO",      "F"): "SKIP",
    ("CAUTION", "A"): "SMALL BUY",
    ("CAUTION", "B"): "SMALL BUY",
    ("CAUTION", "C"): "WATCH",
    ("CAUTION", "D"): "SKIP",
    ("CAUTION", "F"): "SKIP",
    ("STOP",    "A"): "HOLD",
    ("STOP",    "B"): "HOLD",
    ("STOP",    "C"): "HOLD",
    ("STOP",    "D"): "HOLD",
    ("STOP",    "F"): "HOLD",
}


def _verdict(regime: str, gate: str) -> str:
    if regime in ("crisis", "risk_off"):
        return "STOP"
    if gate == "GO":
        return "GO"
    return "CAUTION"


class FinalReportGenerator:
    def generate(
        self,
        regime: str,
        gate: str,
        picks_df: pd.DataFrame,
    ) -> dict:
        verdict = _verdict(regime, gate)

        picks_list: list[dict] = []
        if not picks_df.empty:
            for _, row in picks_df.iterrows():
                grade = row.get("grade", "F")
                action = ACTION_MAP.get((gate, grade), "SKIP")
                entry = {
                    "symbol":             row.get("symbol"),
                    "grade":              grade,
                    "composite_score":    row.get("composite_score"),
                    "action":             action,
                    "current_price":      row.get("current_price"),
                    "target_price":       row.get("target_price"),
                    "sector":             row.get("sector", ""),
                    "technical":          row.get("technical"),
                    "fundamental":        row.get("fundamental"),
                    "analyst":            row.get("analyst"),
                    "relative_strength":  row.get("relative_strength"),
                    "volume":             row.get("volume"),
                    "institutional":      row.get("institutional"),
                }
                # AI 요약이 이미 picks_df에 포함된 경우 병합
                for ai_key in ("thesis", "catalysts", "bear_cases", "recommendation", "confidence",
                               "independent_bear_case_found", "independent_bear_cases"):
                    if ai_key in row and row.get(ai_key) is not None:
                        entry[ai_key] = row.get(ai_key)
                picks_list.append(entry)

        # summary counts
        action_counts: dict[str, int] = {}
        for p in picks_list:
            a = p["action"]
            action_counts[a] = action_counts.get(a, 0) + 1

        report = {
            "generated_at":  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "verdict":        verdict,
            "regime":         regime,
            "gate":           gate,
            "action_summary": action_counts,
            "picks":          picks_list,
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        print(f"Report saved → {OUTPUT_PATH}  |  verdict={verdict}  picks={len(picks_list)}")
        return report
