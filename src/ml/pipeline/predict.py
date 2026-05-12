import pickle
import numpy as np
import pandas as pd
from pathlib import Path

from src.ml.pipeline.feature_store import FeatureStore

MODEL_DIR  = Path(__file__).parents[3] / "output" / "models"
OUTPUT_DIR = Path(__file__).parents[3] / "output"


def _load_latest_model() -> tuple:
    """Return (booster, feature_cols) from the newest pkl in MODEL_DIR."""
    pkls = sorted(MODEL_DIR.glob("lgbm_fwd20d_*.pkl"), reverse=True)
    if not pkls:
        raise FileNotFoundError(f"No model files found in {MODEL_DIR}")
    path = pkls[0]
    print(f"[predict] Loading model: {path}")
    with open(path, "rb") as f:
        payload = pickle.load(f)
    return payload["model"], payload["feature_cols"]


def predict(top_n: int = 20) -> pd.DataFrame:
    booster, feature_cols = _load_latest_model()

    store    = FeatureStore()
    feats_df = store.get_latest_features("equity_features")

    # Use the most recent date's snapshot
    latest_date = feats_df.index.max()
    snapshot    = feats_df.loc[feats_df.index == latest_date].copy()

    # Align columns — fill missing with 0
    for col in feature_cols:
        if col not in snapshot.columns:
            snapshot[col] = 0.0

    X = snapshot[feature_cols].values.astype(np.float32)
    scores = booster.predict(X)

    result = snapshot[["symbol"]].copy() if "symbol" in snapshot.columns else snapshot[[]].copy()
    result["pred_score"] = scores
    result["pred_rank"]  = result["pred_score"].rank(ascending=False).astype(int)
    result = result.sort_values("pred_score", ascending=False).head(top_n)
    result = result.reset_index().rename(columns={"index": "date"})

    out_path = OUTPUT_DIR / "gbm_predictions.parquet"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_path, index=False)
    print(f"[predict] Top-{top_n} predictions saved → {out_path}")
    return result


if __name__ == "__main__":
    df = predict()
    print(df.to_string(index=False))
