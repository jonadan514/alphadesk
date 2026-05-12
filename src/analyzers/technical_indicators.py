import pandas as pd
import numpy as np


def add_sma(df: pd.DataFrame) -> pd.DataFrame:
    for window in (20, 50, 200):
        df[f"SMA{window}"] = df["Close"].rolling(window).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR14"] = tr.ewm(span=period, adjust=False).mean()
    return df


def add_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = df["Close"].rolling(window).mean()
    std = df["Close"].rolling(window).std()
    df["BB_Mid"] = mid
    df["BB_Upper"] = mid + num_std * std
    df["BB_Lower"] = mid - num_std * std
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / mid
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = add_sma(out)
    out = add_rsi(out)
    out = add_macd(out)
    out = add_atr(out)
    out = add_bollinger(out)
    return out
