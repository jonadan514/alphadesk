import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit

from src.ml.pipeline.feature_store import FeatureStore

SEED        = 42
N_SPLITS    = 5
TARGET_COL  = "fwd_20d_rank"
OUTPUT_DIR  = Path(__file__).parents[3] / "output" / "models"

LGB_PARAMS = {
    "objective":        "rank_xendcg",
    "metric":           "ndcg",
    "ndcg_eval_at":     [5, 10, 20],
    "learning_rate":    0.05,
    "num_leaves":       63,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":     5,
    "lambda_l1":        0.1,
    "lambda_l2":        0.1,
    "verbose":          -1,
    "seed":             SEED,
}


def _make_target(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Forward 20d return, cross-sectionally ranked into 5 integer quintiles (0-4)."""
    fwd_ret = df.groupby("symbol")["close"].transform(
        lambda s: s.pct_change(window).shift(-window)
    )
    def _to_quintile(s: pd.Series) -> pd.Series:
        try:
            return pd.qcut(s, q=5, labels=[0, 1, 2, 3, 4], duplicates="drop").astype(float)
        except Exception:
            return pd.Series(np.nan, index=s.index)
    return fwd_ret.groupby(df.index).transform(_to_quintile)


def _split_X_y(df: pd.DataFrame, feature_cols: list[str]):
    X = df[feature_cols].values.astype(np.float32)
    y = df[TARGET_COL].values.astype(np.float32)
    groups = df.groupby(df.index).ngroup().values  # query groups for LTR
    return X, y, groups


def train(features_df: pd.DataFrame | None = None) -> lgb.Booster:
    store = FeatureStore()

    if features_df is None:
        features_df = store.get_latest_features("equity_features")

    # Attach target if not present
    if TARGET_COL not in features_df.columns:
        if "close" not in features_df.columns:
            raise ValueError("features_df must have a 'close' column or pre-built target")
        features_df = features_df.copy()
        features_df[TARGET_COL] = _make_target(features_df)

    features_df = features_df.dropna(subset=[TARGET_COL])

    # Drop non-feature columns
    drop_cols = {TARGET_COL, "symbol", "close", "open", "high", "low", "volume"}
    feature_cols = [c for c in features_df.columns if c not in drop_cols]

    dates = features_df.index.unique().sort_values()
    tscv  = TimeSeriesSplit(n_splits=N_SPLITS)

    val_scores: list[float] = []
    best_model: lgb.Booster | None = None
    best_score = -np.inf

    for fold, (train_idx, val_idx) in enumerate(tscv.split(dates)):
        train_dates = dates[train_idx]
        val_dates   = dates[val_idx]

        tr_df  = features_df[features_df.index.isin(train_dates)]
        va_df  = features_df[features_df.index.isin(val_dates)]

        X_tr, y_tr, g_tr = _split_X_y(tr_df, feature_cols)
        X_va, y_va, g_va = _split_X_y(va_df, feature_cols)

        dtrain = lgb.Dataset(X_tr, label=y_tr, group=np.bincount(g_tr), free_raw_data=False)
        dval   = lgb.Dataset(X_va, label=y_va, group=np.bincount(g_va), reference=dtrain)

        callbacks = [
            lgb.early_stopping(stopping_rounds=50, verbose=False),
            lgb.log_evaluation(period=100),
        ]

        booster = lgb.train(
            LGB_PARAMS,
            dtrain,
            num_boost_round=1000,
            valid_sets=[dval],
            callbacks=callbacks,
        )

        score = booster.best_score["valid_0"].get("ndcg@20", 0.0)
        val_scores.append(score)
        print(f"  Fold {fold+1}/{N_SPLITS}  NDCG@20={score:.4f}")

        if score > best_score:
            best_score = score
            best_model = booster

    print(f"\nCV NDCG@20 mean={np.mean(val_scores):.4f}  std={np.std(val_scores):.4f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.today().strftime("%Y%m%d")
    model_path = OUTPUT_DIR / f"lgbm_fwd20d_{date_str}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": best_model, "feature_cols": feature_cols}, f)
    print(f"Model saved → {model_path}")
    return best_model


if __name__ == "__main__":
    train()
