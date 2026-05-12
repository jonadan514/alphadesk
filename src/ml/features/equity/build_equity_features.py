import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from scipy.stats import skew, kurtosis

OUTPUT_DIR = Path(__file__).parents[4] / "data"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _rank(s: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank (0-1)."""
    return s.rank(pct=True)


def _zscore_60d(s: pd.Series) -> pd.Series:
    mu = s.rolling(60).mean()
    sd = s.rolling(60).std().replace(0, np.nan)
    return (s - mu) / sd


def _beta(ret: pd.Series, mkt: pd.Series, window: int = 60) -> pd.Series:
    cov  = ret.rolling(window).cov(mkt)
    varm = mkt.rolling(window).var().replace(0, np.nan)
    return cov / varm


def _realized_skew(ret: pd.Series, window: int = 60) -> pd.Series:
    return ret.rolling(window).apply(lambda x: float(skew(x)), raw=True)


def _realized_kurt(ret: pd.Series, window: int = 60) -> pd.Series:
    return ret.rolling(window).apply(lambda x: float(kurtosis(x)), raw=True)


def _amihud(ret: pd.Series, dollar_vol: pd.Series, window: int = 20) -> pd.Series:
    ratio = ret.abs() / dollar_vol.replace(0, np.nan)
    return ratio.rolling(window).mean() * 1e6


# ------------------------------------------------------------------
# Main builder
# ------------------------------------------------------------------

def build_equity_features(
    price_df: pd.DataFrame,
    spy_close: pd.Series | None = None,
    shares_outstanding: float | None = None,
) -> pd.DataFrame:
    """
    price_df: DatetimeIndex, columns [Open, High, Low, Close, Volume]
    Returns feature DataFrame with shift(1) applied to prevent look-ahead bias.
    """
    df = price_df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    ret = close.pct_change()

    f = pd.DataFrame(index=df.index)

    # ── Momentum ──────────────────────────────────────────────────────
    f["ret_1m"]            = close.pct_change(21)
    f["ret_3m"]            = close.pct_change(63)
    f["ret_6m"]            = close.pct_change(126)
    f["ret_12m"]           = close.pct_change(252)
    f["ret_1m_minus_12m"]  = f["ret_1m"] - f["ret_12m"]
    # skip-1m: 6m return excluding last month
    f["ret_6m_skip1m"]     = close.shift(21).pct_change(105)   # [t-126, t-21]

    # ── Mean Reversion ─────────────────────────────────────────────────
    # RSI-14
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    f["rsi_14"] = 100 - (100 / (1 + gain / loss))

    # Bollinger %B
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_pct_b"]          = (close - (sma20 - 2 * std20)) / (4 * std20).replace(0, np.nan)

    # Distance from 52-week high/low
    high_52w               = close.rolling(252).max()
    low_52w                = close.rolling(252).min()
    f["distance_52w_high"] = close / high_52w.replace(0, np.nan) - 1
    f["distance_52w_low"]  = close / low_52w.replace(0, np.nan) - 1

    f["z_score_60d"]       = _zscore_60d(close)

    # ── Volatility ─────────────────────────────────────────────────────
    f["vol_20d"]           = ret.rolling(20).std() * np.sqrt(252)
    f["vol_60d"]           = ret.rolling(60).std() * np.sqrt(252)

    # ATR-14
    hl  = high - low
    hpc = (high - close.shift()).abs()
    lpc = (low  - close.shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    f["atr_14"]            = tr.ewm(span=14, adjust=False).mean() / close.replace(0, np.nan)

    mkt_ret = spy_close.pct_change() if spy_close is not None else ret  # fallback self
    f["beta_60d"]          = _beta(ret, mkt_ret, 60)
    f["realized_skew"]     = _realized_skew(ret, 60)
    f["realized_kurt"]     = _realized_kurt(ret, 60)

    # ── Volume ────────────────────────────────────────────────────────
    dollar_vol             = close * volume
    f["vol_ratio_20_60"]   = volume.rolling(20).mean() / volume.rolling(60).mean().replace(0, np.nan)
    f["dollar_volume"]     = dollar_vol.rolling(20).mean()
    f["amihud_illiq"]      = _amihud(ret, dollar_vol, 20)

    if shares_outstanding:
        f["turnover_rate"] = volume / shares_outstanding
    else:
        f["turnover_rate"] = volume / volume.rolling(252).mean().replace(0, np.nan)

    # ── MA Crossover ──────────────────────────────────────────────────
    sma50                  = close.rolling(50).mean()
    sma200                 = close.rolling(200).mean()
    f["price_ma20"]        = close / sma20.replace(0, np.nan) - 1
    f["price_ma50"]        = close / sma50.replace(0, np.nan) - 1
    f["ma20_slope"]        = sma20.pct_change(5)
    f["golden_cross"]      = (sma50 > sma200).astype(float)

    # ── Cross-sectional rank (each feature individually) ──────────────
    for col in f.columns:
        f[f"{col}_rank"] = _rank(f[col])

    # ── Look-ahead bias prevention: shift all features by 1 bar ───────
    f = f.shift(1)

    return f.dropna(how="all")


def build_and_save(price_df: pd.DataFrame, symbol: str = "batch") -> pd.DataFrame:
    feats = build_equity_features(price_df)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.today().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"equity_features_{date_str}.parquet"
    feats.to_parquet(path)
    print(f"[{symbol}] Saved equity features {feats.shape} → {path}")
    return feats


if __name__ == "__main__":
    import yfinance as yf
    df = yf.Ticker("AAPL").history(period="3y", auto_adjust=True)
    build_and_save(df, symbol="AAPL")
