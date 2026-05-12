"""
KOSPI 방향 예측 모델 (LightGBM)
미국 IndexPredictor와 동일한 구조, KOSPI에 맞는 피처 사용
"""
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from curl_cffi import requests as curl_requests

CONFIDENCE_THRESHOLDS = {"HIGH": 0.70, "MODERATE": 0.55}

FEATURE_META: dict[str, dict] = {
    "ks11_return_5d":   {"label": "KOSPI 5D RETURN",     "bullish_if_positive": True,  "desc": "최근 5거래일 KOSPI 수익률. 단기 모멘텀을 반영합니다."},
    "ks11_return_20d":  {"label": "KOSPI 20D RETURN",    "bullish_if_positive": True,  "desc": "최근 20거래일 KOSPI 수익률. 중기 추세를 나타냅니다."},
    "ks11_ret_1m":      {"label": "KOSPI 1M RETURN",     "bullish_if_positive": True,  "desc": "1개월 KOSPI 수익률. 월간 추세 방향을 측정합니다."},
    "ks11_ret_3m":      {"label": "KOSPI 3M RETURN",     "bullish_if_positive": True,  "desc": "3개월 KOSPI 수익률. 분기 단위 추세 강도를 나타냅니다."},
    "ks11_ret_6m":      {"label": "KOSPI 6M RETURN",     "bullish_if_positive": True,  "desc": "6개월 KOSPI 수익률. 중장기 모멘텀을 반영합니다."},
    "ks11_rsi_14":      {"label": "KOSPI RSI 14",        "bullish_if_positive": True,  "desc": "14일 RSI 과매수/과매도 지표. 70 이상 과매수, 30 이하 과매도 신호입니다."},
    "ks11_macd_signal": {"label": "KOSPI MACD",          "bullish_if_positive": True,  "desc": "MACD - Signal 값. 양수이면 단기 이평선이 장기를 돌파한 상승 모멘텀입니다."},
    "ks11_bb_pct_b":    {"label": "KOSPI BB %B",         "bullish_if_positive": True,  "desc": "볼린저 밴드 내 위치. 1이면 상단, 0이면 하단이며 0.5 이상이면 강세 구간입니다."},
    "ks11_atr_pct":     {"label": "KOSPI ATR%",          "bullish_if_positive": False, "desc": "ATR 기반 변동성 비율. 높을수록 시장 불안정 — 약세 신호로 해석합니다."},
    "ks11_roc_20":      {"label": "KOSPI ROC 20",        "bullish_if_positive": True,  "desc": "20일 변화율(Rate of Change). 추세 가속도를 측정합니다."},
    "ks11_new_high_low":{"label": "KOSPI 52W HIGH DIST", "bullish_if_positive": True,  "desc": "52주 최고가 대비 현재 위치. 0에 가까울수록 신고점 근처 — 강세 신호입니다."},
    "usdkrw_change_5d": {"label": "USD/KRW 5D CHG",      "bullish_if_positive": False, "desc": "5일 달러/원 환율 변화. 원화 약세(환율 상승)는 외국인 매도 압력을 높여 약세 신호입니다."},
    "spy_return_5d":    {"label": "SPY 5D RETURN",       "bullish_if_positive": True,  "desc": "미국 S&P500 ETF 5일 수익률. 미국 시장 흐름이 KOSPI에 파급되는 효과를 반영합니다."},
    "kq11_return_5d":   {"label": "KOSDAQ 5D RETURN",    "bullish_if_positive": True,  "desc": "KOSDAQ 5일 수익률. 국내 중소형·성장주 수요를 나타내는 브레드스 지표입니다."},
    "kq_ks_spread_5d":  {"label": "KOSDAQ/KOSPI SPREAD", "bullish_if_positive": True,  "desc": "KOSDAQ - KOSPI 상대 수익률. 양수면 위험 선호 심리가 강해 중소형주 주도 장세입니다."},
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


class KrIndexPredictor:
    def __init__(self):
        self._session = curl_requests.Session(impersonate="chrome")
        self._model: lgb.Booster | None = None
        self._feature_names: list[str] = []
        self._cv_accuracy: float | None = None
        self._trained_at: str | None = None

    def _hist(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        try:
            df = yf.Ticker(ticker, session=self._session).history(
                period=period, auto_adjust=True
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df
        except Exception as e:
            print(f"[KrIndexPredictor] {ticker} fetch error: {e}")
            return pd.DataFrame()

    def _build_features(self, ks11: pd.DataFrame, usdkrw: pd.DataFrame,
                        spy: pd.DataFrame, kq11: pd.DataFrame) -> dict[str, float]:
        feats: dict[str, float] = {}

        def ret(df: pd.DataFrame, n: int) -> float:
            c = df["Close"] if not df.empty else pd.Series()
            return float(c.iloc[-1] / c.iloc[-n] - 1) if len(c) >= n else 0.0

        # ── KOSPI 가격 기반 ────────────────────────────────────────────
        feats["ks11_return_5d"]  = ret(ks11, 5)
        feats["ks11_return_20d"] = ret(ks11, 20)
        feats["ks11_ret_1m"]     = ret(ks11, 21)
        feats["ks11_ret_3m"]     = ret(ks11, 63)  if len(ks11) >= 63  else 0.0
        feats["ks11_ret_6m"]     = ret(ks11, 126) if len(ks11) >= 126 else 0.0

        if not ks11.empty and len(ks11) >= 14:
            c     = ks11["Close"]
            delta = c.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
            feats["ks11_rsi_14"] = float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1]))
        else:
            feats["ks11_rsi_14"] = 50.0

        if not ks11.empty and len(ks11) >= 26:
            c    = ks11["Close"]
            macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
            sig  = macd.ewm(span=9, adjust=False).mean()
            feats["ks11_macd_signal"] = float(macd.iloc[-1] - sig.iloc[-1])
        else:
            feats["ks11_macd_signal"] = 0.0

        if not ks11.empty and len(ks11) >= 20:
            c   = ks11["Close"]
            mid = c.rolling(20).mean()
            std = c.rolling(20).std()
            bw  = (4 * std).replace(0, np.nan)
            feats["ks11_bb_pct_b"] = float((c.iloc[-1] - (mid.iloc[-1] - 2 * std.iloc[-1])) / bw.iloc[-1])
        else:
            feats["ks11_bb_pct_b"] = 0.5

        if not ks11.empty and len(ks11) >= 15:
            c   = ks11["Close"]
            h   = ks11["High"]
            lo  = ks11["Low"]
            hl  = h - lo
            hpc = (h - c.shift()).abs()
            lpc = (lo - c.shift()).abs()
            tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
            atr = tr.ewm(span=14, adjust=False).mean()
            feats["ks11_atr_pct"] = float(atr.iloc[-1] / c.iloc[-1]) if c.iloc[-1] else 0.01
        else:
            feats["ks11_atr_pct"] = 0.01

        if not ks11.empty and len(ks11) >= 20:
            c = ks11["Close"]
            feats["ks11_roc_20"] = float((c.iloc[-1] - c.iloc[-20]) / c.iloc[-20])
        else:
            feats["ks11_roc_20"] = 0.0

        if not ks11.empty and len(ks11) >= 252:
            c = ks11["Close"]
            feats["ks11_new_high_low"] = float(c.iloc[-1] / c.tail(252).max() - 1)
        else:
            feats["ks11_new_high_low"] = 0.0

        # ── 환율 (USD/KRW) — 하락이 원화 강세 → KOSPI 호재 ────────────
        feats["usdkrw_change_5d"] = ret(usdkrw, 5) if len(usdkrw) >= 5 else 0.0

        # ── SPY spillover ─────────────────────────────────────────────
        feats["spy_return_5d"] = ret(spy, 5) if len(spy) >= 5 else 0.0

        # ── KOSDAQ (브레드스 proxy) ───────────────────────────────────
        feats["kq11_return_5d"]  = ret(kq11, 5) if len(kq11) >= 5 else 0.0
        feats["kq_ks_spread_5d"] = feats["kq11_return_5d"] - feats["ks11_return_5d"]

        return feats

    def _train(self, ks11: pd.DataFrame) -> None:
        if ks11.empty or len(ks11) < 60:
            return

        c = ks11["Close"]
        records = []
        for i in range(30, len(c) - 5):
            label = 1 if c.iloc[i + 5] > c.iloc[i] else 0

            def ret_i(n: int) -> float:
                return float(c.iloc[i] / c.iloc[i - n] - 1) if i >= n else 0.0

            row: dict[str, float] = {}
            row["ks11_return_5d"]  = ret_i(5)
            row["ks11_return_20d"] = ret_i(20)
            row["ks11_ret_1m"]     = ret_i(21)
            row["ks11_ret_3m"]     = ret_i(63)  if i >= 63  else 0.0
            row["ks11_ret_6m"]     = ret_i(126) if i >= 126 else 0.0

            delta = c.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
            row["ks11_rsi_14"] = float(100 - 100 / (1 + gain.iloc[i] / loss.iloc[i])) if loss.iloc[i] else 50.0

            macd_line = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
            sig_line  = macd_line.ewm(span=9, adjust=False).mean()
            row["ks11_macd_signal"] = float(macd_line.iloc[i] - sig_line.iloc[i])

            mid = c.rolling(20).mean()
            std = c.rolling(20).std()
            bw  = (4 * std).replace(0, np.nan)
            row["ks11_bb_pct_b"] = float((c.iloc[i] - (mid.iloc[i] - 2 * std.iloc[i])) / bw.iloc[i]) if bw.iloc[i] else 0.5

            row["ks11_atr_pct"]     = 0.01
            row["ks11_roc_20"]      = ret_i(20)
            row["ks11_new_high_low"]= float(c.iloc[i] / c.iloc[max(0, i-252):i+1].max() - 1)

            # 학습 시 외부 데이터 neutral 기본값
            row["usdkrw_change_5d"] = 0.0
            row["spy_return_5d"]    = ret_i(5)   # proxy: KOSPI 자체 수익률
            row["kq11_return_5d"]   = ret_i(5)
            row["kq_ks_spread_5d"]  = 0.0
            row["_label"] = label
            records.append(row)

        if len(records) < 20:
            return

        df_tr = pd.DataFrame(records)
        self._feature_names = [col for col in df_tr.columns if col != "_label"]
        X = df_tr[self._feature_names].values.astype(np.float32)
        y = df_tr["_label"].values.astype(np.float32)

        dtrain = lgb.Dataset(X, label=y, feature_name=self._feature_names)
        self._model = lgb.train(
            LGB_PARAMS, dtrain,
            num_boost_round=200,
            callbacks=[lgb.log_evaluation(period=9999)],
        )
        self._trained_at = datetime.now().strftime("%Y-%m-%d")

        try:
            tscv = TimeSeriesSplit(n_splits=5)
            accs = []
            for tr_idx, val_idx in tscv.split(X):
                xtr, ytr = X[tr_idx], y[tr_idx]
                xval, yval = X[val_idx], y[val_idx]
                if len(xtr) < 10 or len(xval) < 5:
                    continue
                ds = lgb.Dataset(xtr, label=ytr, feature_name=self._feature_names)
                m  = lgb.train(LGB_PARAMS, ds, num_boost_round=200,
                               callbacks=[lgb.log_evaluation(period=9999)])
                preds = (m.predict(xval) >= 0.5).astype(int)
                accs.append(accuracy_score(yval.astype(int), preds))
            self._cv_accuracy = float(np.mean(accs)) if accs else None
        except Exception:
            self._cv_accuracy = None

    def predict_next_week(self) -> dict:
        ks11   = self._hist("^KS11",  "3y")
        usdkrw = self._hist("KRW=X",  "3mo")
        spy    = self._hist("SPY",    "3mo")
        kq11   = self._hist("^KQ11",  "3mo")

        self._train(ks11)

        feats = self._build_features(ks11, usdkrw, spy, kq11)

        if self._model is None or not self._feature_names:
            return {
                "market": "KR", "index": "KOSPI",
                "direction": "neutral", "probability": 0.5,
                "confidence": "LOW", "key_drivers": [],
                "cv_accuracy": None, "feature_count": 0,
                "trained_at": self._trained_at,
                "model_type": "lightgbm",
                "_note": "insufficient data",
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

        predicted_return = round((prob_bullish - 0.5) * 2 * 0.5, 4)

        raw_importance = dict(zip(
            self._feature_names,
            self._model.feature_importance(importance_type="gain").tolist(),
        ))
        max_imp = max(raw_importance.values()) or 1.0
        top5 = sorted(raw_importance, key=raw_importance.get, reverse=True)[:5]

        key_drivers = []
        for fname in top5:
            meta = FEATURE_META.get(fname, {"label": fname.upper().replace("_", " "), "bullish_if_positive": True})
            val  = feats.get(fname, 0.0)
            imp  = raw_importance[fname]
            drv_dir = "bullish" if (val >= 0) == meta["bullish_if_positive"] else "bearish"
            key_drivers.append({
                "name":           fname,
                "label":          meta["label"],
                "desc":           meta.get("desc", ""),
                "importance":     round(imp, 2),
                "importance_pct": round(imp / max_imp, 4),
                "value":          round(val, 4),
                "direction":      drv_dir,
            })

        return {
            "market":           "KR",
            "index":            "KOSPI",
            "direction":        direction,
            "probability":      round(probability, 4),
            "confidence":       confidence,
            "predicted_return": predicted_return,
            "cv_accuracy":      round(self._cv_accuracy, 4) if self._cv_accuracy else None,
            "trained_at":       self._trained_at,
            "feature_count":    len(self._feature_names),
            "key_drivers":      key_drivers,
            "model_type":       "lightgbm",
        }


if __name__ == "__main__":
    import json
    result = KrIndexPredictor().predict_next_week()
    print(json.dumps(result, indent=2, ensure_ascii=False))
