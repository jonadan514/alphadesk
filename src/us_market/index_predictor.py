import os
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv

load_dotenv()

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

CONFIDENCE_THRESHOLDS = {"HIGH": 0.70, "MODERATE": 0.55}

# 피처 표시명 및 방향 판단 (양수=강세 여부)
FEATURE_META: dict[str, dict] = {
    "ret_3m":              {"label": "SPY 3M RETURN",      "bullish_if_positive": True},
    "ret_6m":              {"label": "SPY 6M RETURN",      "bullish_if_positive": True},
    "ret_1m":              {"label": "SPY 1M RETURN",      "bullish_if_positive": True},
    "spy_return_5d":       {"label": "SPY 5D RETURN",      "bullish_if_positive": True},
    "spy_macd_signal":     {"label": "SPY MACD SIGNAL",    "bullish_if_positive": True},
    "spy_atr_pct":         {"label": "SPY 5D VOL TREND",   "bullish_if_positive": False},
    "vix_level":           {"label": "VIX",                "bullish_if_positive": False},
    "vix_change_5d":       {"label": "VIX 5D CHANGE",      "bullish_if_positive": False},
    "vix_ma20_diff":       {"label": "VIX VS MA20",        "bullish_if_positive": False},
    "macro_yield_curve":   {"label": "YIELD SPREAD",       "bullish_if_positive": True},
    "macro_credit_spread": {"label": "CREDIT SPREAD",      "bullish_if_positive": False},
    "macro_fear_greed":    {"label": "FEAR & GREED",       "bullish_if_positive": True},
    "advance_decline":     {"label": "ADVANCE/DECLINE",    "bullish_if_positive": True},
    "new_high_low":        {"label": "NEW HIGH/LOW",       "bullish_if_positive": True},
    "xlk_rel_strength":    {"label": "XLK 1M RS",          "bullish_if_positive": True},
    "xly_rel_strength":    {"label": "XLY 1M RS",          "bullish_if_positive": True},
    "xlu_rel_strength":    {"label": "XLU 1M RS",          "bullish_if_positive": False},
    "qqq_return_5d":       {"label": "QQQ 5D RETURN",      "bullish_if_positive": True},
    "spy_volume_ratio":    {"label": "SPY VOLUME RATIO",   "bullish_if_positive": True},
    "spy_volume_surge":    {"label": "SPY VOLUME SURGE",   "bullish_if_positive": True},
    "roc_20":              {"label": "SPY ROC 20",         "bullish_if_positive": True},
}

LGB_PARAMS = {
    "objective":        "binary",
    "metric":           "binary_logloss",
    "num_leaves":       31,
    "learning_rate":    0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":     5,
    "verbose":          -1,
    "seed":             42,
}


class IndexPredictor:
    def __init__(self, symbol: str = "SPY"):
        self.symbol  = symbol.upper()
        self._session = curl_requests.Session(impersonate="chrome")
        self._fred_key = os.getenv("FRED_API_KEY", "")
        self._model: lgb.Booster | None = None
        self._feature_names: list[str] = []
        self._cv_accuracy: float | None = None
        self._trained_at: str | None = None
        self._last_features: dict = {}

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _hist(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        try:
            df = yf.Ticker(ticker, session=self._session).history(
                period=period, auto_adjust=True
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df
        except Exception as exc:
            print(f"[IndexPredictor] {ticker} fetch error: {exc}")
            return pd.DataFrame()

    def _fred_latest(self, series_id: str) -> float | None:
        if not self._fred_key:
            return None
        try:
            r = self._session.get(
                FRED_BASE,
                params={
                    "series_id":  series_id,
                    "api_key":    self._fred_key,
                    "file_type":  "json",
                    "sort_order": "desc",
                    "limit":      5,
                },
                timeout=10,
            )
            obs = [o for o in r.json().get("observations", []) if o["value"] != "."]
            return float(obs[0]["value"]) if obs else None
        except Exception:
            return None

    def _fear_greed(self) -> float | None:
        try:
            r = self._session.get(FEAR_GREED_URL, timeout=10)
            fg = r.json().get("fear_and_greed", {})
            v = fg.get("score")
            return float(v) if v is not None else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Feature builder  → returns single-row dict
    # ------------------------------------------------------------------

    def _build_features(self) -> dict[str, float]:
        spy  = self._hist("SPY",  "1y")
        qqq  = self._hist("QQQ",  "3mo")
        vix  = self._hist("^VIX", "3mo")
        xlk  = self._hist("XLK",  "3mo")
        xly  = self._hist("XLY",  "3mo")
        xlu  = self._hist("XLU",  "3mo")
        rsp  = self._hist("RSP",  "3mo")   # equal-weight → breadth proxy

        def ret(df: pd.DataFrame, n: int) -> float:
            c = df["Close"] if not df.empty else pd.Series()
            return float(c.iloc[-1] / c.iloc[-n] - 1) if len(c) >= n else 0.0

        def vol_ratio(df: pd.DataFrame, short: int, long: int) -> float:
            v = df["Volume"] if not df.empty else pd.Series()
            if len(v) < long:
                return 1.0
            return float(v.tail(short).mean() / v.tail(long).mean())

        feats: dict[str, float] = {}

        # ── SPY 7 ──────────────────────────────────────────────────────
        feats["spy_return_5d"]  = ret(spy, 5)
        feats["spy_return_20d"] = ret(spy, 20)

        if not spy.empty and len(spy) >= 14:
            delta = spy["Close"].diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
            feats["spy_rsi_14"] = float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1]))
        else:
            feats["spy_rsi_14"] = 50.0

        if not spy.empty and len(spy) >= 26:
            c    = spy["Close"]
            macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
            sig  = macd.ewm(span=9, adjust=False).mean()
            feats["spy_macd_signal"] = float(macd.iloc[-1] - sig.iloc[-1])
        else:
            feats["spy_macd_signal"] = 0.0

        if not spy.empty and len(spy) >= 20:
            c    = spy["Close"]
            mid  = c.rolling(20).mean()
            std  = c.rolling(20).std()
            bw   = (4 * std).replace(0, np.nan)
            feats["spy_bb_pct_b"] = float((c.iloc[-1] - (mid.iloc[-1] - 2 * std.iloc[-1])) / bw.iloc[-1])
        else:
            feats["spy_bb_pct_b"] = 0.5

        feats["spy_volume_ratio"] = vol_ratio(spy, 5, 20)

        if not spy.empty and len(spy) >= 15:
            c    = spy["Close"]
            h    = spy["High"]
            lo   = spy["Low"]
            hl   = h - lo
            hpc  = (h - c.shift()).abs()
            lpc  = (lo - c.shift()).abs()
            tr   = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
            atr  = tr.ewm(span=14, adjust=False).mean()
            feats["spy_atr_pct"] = float(atr.iloc[-1] / c.iloc[-1])
        else:
            feats["spy_atr_pct"] = 0.01

        # ── VIX 3 ──────────────────────────────────────────────────────
        if not vix.empty:
            v = vix["Close"]
            feats["vix_level"]    = float(v.iloc[-1])
            feats["vix_change_5d"] = ret(vix, 5)
            feats["vix_ma20_diff"] = float(v.iloc[-1] - v.tail(20).mean()) if len(v) >= 20 else 0.0
        else:
            feats["vix_level"]    = 20.0
            feats["vix_change_5d"] = 0.0
            feats["vix_ma20_diff"] = 0.0

        # ── QQQ 2 ──────────────────────────────────────────────────────
        feats["qqq_return_5d"] = ret(qqq, 5)
        if not qqq.empty and not spy.empty:
            feats["qqq_spy_ratio"] = float(qqq["Close"].iloc[-1] / spy["Close"].iloc[-1])
        else:
            feats["qqq_spy_ratio"] = 1.0

        # ── Breadth 2 ─────────────────────────────────────────────────
        # advance/decline proxy: RSP vs SPY 5d return spread
        feats["advance_decline"] = ret(rsp, 5) - ret(spy, 5)
        # new high/low proxy: distance from 52w high
        if not spy.empty and len(spy) >= 252:
            c = spy["Close"]
            feats["new_high_low"] = float(c.iloc[-1] / c.tail(252).max() - 1)
        else:
            feats["new_high_low"] = 0.0

        # ── Sector 3 ─────────────────────────────────────────────────
        spy_ret20 = ret(spy, 20)
        feats["xlk_rel_strength"] = ret(xlk, 20) - spy_ret20
        feats["xly_rel_strength"] = ret(xly, 20) - spy_ret20
        feats["xlu_rel_strength"] = ret(xlu, 20) - spy_ret20

        # ── Macro 3 ──────────────────────────────────────────────────
        t10y2y = self._fred_latest("T10Y2Y")
        hy     = self._fred_latest("BAMLH0A0HYM2")
        fg     = self._fear_greed()
        feats["macro_yield_curve"]    = t10y2y if t10y2y is not None else 0.0
        feats["macro_credit_spread"]  = hy     if hy     is not None else 5.0
        feats["macro_fear_greed"]     = fg     if fg     is not None else 50.0

        # ── Volume 3 ─────────────────────────────────────────────────
        feats["spy_volume_surge"]  = vol_ratio(spy, 3, 20)
        # sector momentum trend: XLK 5d vs 20d vol ratio
        feats["sector_trend"]      = vol_ratio(xlk, 5, 20)
        # dark-pool proxy: dollar volume spike (close * volume ratio)
        feats["dark_pool_proxy"]   = feats["spy_volume_surge"] * abs(feats["spy_return_5d"])

        # ── Momentum 4 ───────────────────────────────────────────────
        feats["ret_1m"]  = ret(spy, 21)
        feats["ret_3m"]  = ret(spy, 63)
        feats["ret_6m"]  = ret(spy, 126)
        if not spy.empty and len(spy) >= 20:
            c = spy["Close"]
            feats["roc_20"] = float((c.iloc[-1] - c.iloc[-20]) / c.iloc[-20])
        else:
            feats["roc_20"] = 0.0

        return feats

    # ------------------------------------------------------------------
    # Train on historical data
    # ------------------------------------------------------------------

    def _train(self, spy: pd.DataFrame) -> None:
        if spy.empty or len(spy) < 60:
            return

        c = spy["Close"]
        records = []
        for i in range(30, len(c) - 5):
            sub = spy.iloc[max(0, i-126): i]
            if len(sub) < 30:
                continue
            label = 1 if c.iloc[i + 5] > c.iloc[i] else 0
            row: dict[str, float] = {}

            def ret_i(n: int) -> float:
                return float(c.iloc[i] / c.iloc[i - n] - 1) if i >= n else 0.0

            row["spy_return_5d"]  = ret_i(5)
            row["spy_return_20d"] = ret_i(20)

            delta = c.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
            row["spy_rsi_14"] = float(100 - 100 / (1 + gain.iloc[i] / loss.iloc[i])) if loss.iloc[i] else 50.0

            macd_line = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
            sig_line  = macd_line.ewm(span=9, adjust=False).mean()
            row["spy_macd_signal"] = float(macd_line.iloc[i] - sig_line.iloc[i])

            mid = c.rolling(20).mean()
            std = c.rolling(20).std()
            bw  = (4 * std).replace(0, np.nan)
            row["spy_bb_pct_b"] = float((c.iloc[i] - (mid.iloc[i] - 2 * std.iloc[i])) / bw.iloc[i]) if bw.iloc[i] else 0.5

            row["spy_volume_ratio"] = float(spy["Volume"].iloc[i-4:i+1].mean() / spy["Volume"].iloc[i-19:i+1].mean()) if i >= 20 else 1.0

            hl  = spy["High"] - spy["Low"]
            hpc = (spy["High"] - c.shift()).abs()
            lpc = (spy["Low"]  - c.shift()).abs()
            tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
            atr = tr.ewm(span=14, adjust=False).mean()
            row["spy_atr_pct"] = float(atr.iloc[i] / c.iloc[i]) if c.iloc[i] else 0.01

            # remaining features filled with neutral defaults for training
            row["vix_level"]          = 20.0
            row["vix_change_5d"]      = 0.0
            row["vix_ma20_diff"]      = 0.0
            row["qqq_return_5d"]      = ret_i(5)
            row["qqq_spy_ratio"]      = 1.0
            row["advance_decline"]    = 0.0
            row["new_high_low"]       = float(c.iloc[i] / c.iloc[max(0, i-252):i+1].max() - 1)
            row["xlk_rel_strength"]   = 0.0
            row["xly_rel_strength"]   = 0.0
            row["xlu_rel_strength"]   = 0.0
            row["macro_yield_curve"]  = 0.5
            row["macro_credit_spread"] = 4.0
            row["macro_fear_greed"]   = 50.0
            row["spy_volume_surge"]   = row["spy_volume_ratio"]
            row["sector_trend"]       = 1.0
            row["dark_pool_proxy"]    = row["spy_volume_surge"] * abs(row["spy_return_5d"])
            row["ret_1m"]             = ret_i(21)
            row["ret_3m"]             = ret_i(63) if i >= 63 else 0.0
            row["ret_6m"]             = ret_i(126) if i >= 126 else 0.0
            row["roc_20"]             = ret_i(20)
            row["_label"]             = label
            records.append(row)

        if len(records) < 20:
            return

        df_tr = pd.DataFrame(records)
        self._feature_names = [c for c in df_tr.columns if c != "_label"]
        X = df_tr[self._feature_names].values.astype(np.float32)
        y = df_tr["_label"].values.astype(np.float32)

        dtrain = lgb.Dataset(X, label=y, feature_name=self._feature_names)
        self._model = lgb.train(
            LGB_PARAMS,
            dtrain,
            num_boost_round=200,
            callbacks=[lgb.log_evaluation(period=9999)],
        )
        self._trained_at = datetime.now().strftime("%Y-%m-%d")

        # TimeSeriesSplit CV 정확도
        try:
            tscv = TimeSeriesSplit(n_splits=5)
            accs = []
            for tr_idx, val_idx in tscv.split(X):
                xtr, ytr = X[tr_idx], y[tr_idx]
                xval, yval = X[val_idx], y[val_idx]
                if len(xtr) < 10 or len(xval) < 5:
                    continue
                ds = lgb.Dataset(xtr, label=ytr, feature_name=self._feature_names)
                m  = lgb.train(LGB_PARAMS, ds, num_boost_round=200, callbacks=[lgb.log_evaluation(period=9999)])
                preds = (m.predict(xval) >= 0.5).astype(int)
                accs.append(accuracy_score(yval.astype(int), preds))
            self._cv_accuracy = float(np.mean(accs)) if accs else None
        except Exception:
            self._cv_accuracy = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_next_week(self) -> dict:
        spy = self._hist("SPY", "3y")

        # train on historical SPY data
        self._train(spy)

        feats = self._build_features()
        self._last_features = feats

        if self._model is None or not self._feature_names:
            return {
                "symbol":        self.symbol,
                "direction":     "neutral",
                "probability":   0.5,
                "confidence":    "LOW",
                "key_drivers":   [],
                "cv_accuracy":   None,
                "predicted_return": 0.0,
                "trained_at":    self._trained_at,
                "feature_count": 0,
                "_note":         "insufficient data to train model",
            }

        X = np.array([[feats.get(f, 0.0) for f in self._feature_names]], dtype=np.float32)
        prob_bullish = float(self._model.predict(X)[0])
        direction    = "bullish" if prob_bullish >= 0.5 else "bearish"
        probability  = prob_bullish if direction == "bullish" else 1 - prob_bullish

        if probability >= CONFIDENCE_THRESHOLDS["HIGH"]:
            confidence = "HIGH"
        elif probability >= CONFIDENCE_THRESHOLDS["MODERATE"]:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        # 예상 수익률: 확률의 강도에 비례
        predicted_return = round((prob_bullish - 0.5) * 2 * 0.5, 4)

        # top-5 feature importances (gain) — enriched with value & direction
        raw_importance = dict(zip(
            self._feature_names,
            self._model.feature_importance(importance_type="gain").tolist(),
        ))
        max_imp = max(raw_importance.values()) or 1.0
        top5_names = sorted(raw_importance, key=raw_importance.get, reverse=True)[:5]

        key_drivers = []
        for fname in top5_names:
            meta = FEATURE_META.get(fname, {"label": fname.upper().replace("_", " "), "bullish_if_positive": True})
            val  = feats.get(fname, 0.0)
            imp  = raw_importance[fname]
            bullish_if_pos = meta["bullish_if_positive"]
            drv_dir = "bullish" if (val >= 0) == bullish_if_pos else "bearish"
            key_drivers.append({
                "name":           fname,
                "label":          meta["label"],
                "importance":     round(imp, 2),
                "importance_pct": round(imp / max_imp, 4),
                "value":          round(val, 4),
                "direction":      drv_dir,
            })

        return {
            "symbol":           self.symbol,
            "direction":        direction,
            "probability":      round(probability, 4),
            "confidence":       confidence,
            "predicted_return": predicted_return,
            "cv_accuracy":      round(self._cv_accuracy, 4) if self._cv_accuracy else None,
            "trained_at":       self._trained_at,
            "feature_count":    len(self._feature_names),
            "key_drivers":      key_drivers,
        }
