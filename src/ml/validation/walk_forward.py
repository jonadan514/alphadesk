import pickle
import itertools
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from scipy.stats import norm

TRAIN_WINDOW = 730   # days
VAL_WINDOW   = 180   # days
EMBARGO      = 20    # days gap between train end and val start
RISK_FREE    = 0.0   # annualised, for Sharpe calculation


# ------------------------------------------------------------------
# Walk-forward split generator
# ------------------------------------------------------------------

def walk_forward_splits(
    dates: pd.DatetimeIndex,
    train_window: int = TRAIN_WINDOW,
    val_window:   int = VAL_WINDOW,
    embargo:      int = EMBARGO,
) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    dates  = dates.sort_values().unique()
    splits = []
    i = 0
    while True:
        train_end_i = i + train_window
        val_start_i = train_end_i + embargo
        val_end_i   = val_start_i + val_window
        if val_end_i > len(dates):
            break
        train_dates = dates[i:train_end_i]
        val_dates   = dates[val_start_i:val_end_i]
        splits.append((train_dates, val_dates))
        i += val_window   # step forward by one val window
    return splits


# ------------------------------------------------------------------
# Sharpe ratio helpers
# ------------------------------------------------------------------

def _sharpe(returns: pd.Series, freq: int = 252) -> float:
    excess = returns - RISK_FREE / freq
    std    = excess.std()
    if std == 0:
        return 0.0
    return float(excess.mean() / std * np.sqrt(freq))


def _deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    T: int,
    skew_sr: float = 0.0,
    kurt_sr: float = 3.0,
) -> float:
    """
    DSR as per Bailey & López de Prado (2014).
    Adjusts SR for selection bias across n_trials back-tested strategies.
    """
    # Expected maximum SR under iid assumption
    e_max_sr = (
        (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_trials)
        + np.euler_gamma * norm.ppf(1 - 1 / (n_trials * np.e))
    )
    # Variance of SR estimator
    var_sr = (1 / T) * (
        1
        - skew_sr * sharpe
        + ((kurt_sr - 1) / 4) * sharpe ** 2
    )
    se_sr = np.sqrt(var_sr)
    if se_sr == 0:
        return 0.0
    z = (sharpe - e_max_sr) / se_sr
    return float(norm.cdf(z))


# ------------------------------------------------------------------
# PBO (Probability of Backtest Overfitting)
# ------------------------------------------------------------------

def _pbo(perf_matrix: np.ndarray) -> float:
    """
    Bailey et al. (2014) combinatorially symmetric cross-validation PBO.
    perf_matrix: shape (n_configs, n_splits) – each entry is IS or OOS performance.
    """
    n_configs, n_splits = perf_matrix.shape
    half = n_splits // 2

    # All ways to split n_splits into two halves of size `half`
    split_indices = list(range(n_splits))
    all_combos    = list(itertools.combinations(split_indices, half))

    overfit_count = 0
    total         = 0

    for is_idx in all_combos:
        oos_idx = [i for i in split_indices if i not in is_idx]
        is_perf  = perf_matrix[:, list(is_idx)].mean(axis=1)
        oos_perf = perf_matrix[:, oos_idx].mean(axis=1)

        best_is  = int(np.argmax(is_perf))
        # Rank of best IS config in OOS (lower rank = worse)
        oos_rank = (oos_perf < oos_perf[best_is]).sum() / (n_configs - 1)
        if oos_rank < 0.5:
            overfit_count += 1
        total += 1

    return overfit_count / total if total > 0 else np.nan


# ------------------------------------------------------------------
# Main validator
# ------------------------------------------------------------------

class WalkForwardValidator:
    def __init__(
        self,
        train_window: int = TRAIN_WINDOW,
        val_window:   int = VAL_WINDOW,
        embargo:      int = EMBARGO,
    ):
        self.train_window = train_window
        self.val_window   = val_window
        self.embargo      = embargo

    def validate(
        self,
        features_df: pd.DataFrame,
        target_col:  str,
        feature_cols: list[str],
        lgb_params:  dict,
    ) -> dict:
        dates  = features_df.index.unique().sort_values()
        splits = walk_forward_splits(dates, self.train_window, self.val_window, self.embargo)

        if not splits:
            raise ValueError(
                f"No walk-forward splits possible. Need at least "
                f"{self.train_window + self.embargo + self.val_window} trading days of data."
            )

        fold_sharpes: list[float] = []
        fold_ndcg:    list[float] = []
        # perf_matrix for PBO: here we use a single "config" (given model params)
        oos_returns_all: list[pd.Series] = []

        for fold_i, (train_dates, val_dates) in enumerate(splits):
            tr_df = features_df[features_df.index.isin(train_dates)].dropna(subset=[target_col])
            va_df = features_df[features_df.index.isin(val_dates)].dropna(subset=[target_col])

            if tr_df.empty or va_df.empty:
                continue

            X_tr = tr_df[feature_cols].values.astype(np.float32)
            y_tr = tr_df[target_col].values.astype(np.float32)
            X_va = va_df[feature_cols].values.astype(np.float32)
            y_va = va_df[target_col].values.astype(np.float32)

            g_tr = np.ones(len(X_tr), dtype=int) * len(X_tr)
            g_va = np.ones(len(X_va), dtype=int) * len(X_va)

            dtrain = lgb.Dataset(X_tr, label=y_tr, group=g_tr)
            dval   = lgb.Dataset(X_va, label=y_va, group=g_va, reference=dtrain)

            booster = lgb.train(
                lgb_params,
                dtrain,
                num_boost_round=300,
                valid_sets=[dval],
                callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(9999)],
            )

            preds  = booster.predict(X_va)
            # top-decile long portfolio daily PnL proxy
            threshold = np.percentile(preds, 80)
            long_mask = preds >= threshold
            if long_mask.sum() == 0:
                continue

            oos_ret = pd.Series(y_va[long_mask]).reset_index(drop=True)
            fold_sharpes.append(_sharpe(oos_ret))
            oos_returns_all.append(oos_ret)

            ndcg = booster.best_score.get("valid_0", {}).get("ndcg@20", np.nan)
            fold_ndcg.append(ndcg)
            print(f"  Fold {fold_i+1}/{len(splits)}  Sharpe={fold_sharpes[-1]:.3f}  NDCG@20={ndcg:.4f}")

        if not fold_sharpes:
            return {"error": "no valid folds"}

        all_oos = pd.concat(oos_returns_all).reset_index(drop=True) if oos_returns_all else pd.Series()

        mean_sharpe = float(np.mean(fold_sharpes))
        n_obs       = len(all_oos)
        n_trials    = len(splits)

        dsr = _deflated_sharpe_ratio(
            sharpe=mean_sharpe,
            n_trials=n_trials,
            T=max(n_obs, 1),
            skew_sr=float(all_oos.skew()) if n_obs > 3 else 0.0,
            kurt_sr=float(all_oos.kurt() + 3) if n_obs > 3 else 3.0,
        )

        # PBO needs a perf_matrix; with a single config we compute a degenerate estimate
        perf_matrix = np.array(fold_sharpes).reshape(1, -1)
        pbo = _pbo(perf_matrix) if len(fold_sharpes) >= 4 else np.nan

        result = {
            "n_folds":          len(splits),
            "valid_folds":      len(fold_sharpes),
            "fold_sharpes":     fold_sharpes,
            "mean_sharpe":      round(mean_sharpe, 4),
            "std_sharpe":       round(float(np.std(fold_sharpes)), 4),
            "mean_ndcg20":      round(float(np.mean(fold_ndcg)), 4) if fold_ndcg else None,
            "dsr":              round(dsr, 4),
            "pbo":              round(float(pbo), 4) if not np.isnan(pbo) else None,
            "overfit_warning":  (pbo > 0.5) if not np.isnan(pbo) else None,
        }
        print(f"\nWalk-Forward Summary: {result}")
        return result
