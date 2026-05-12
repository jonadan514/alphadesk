"""
S&P 500 전 종목 ML 피처 빌드
Usage: python scripts/build_ml_features.py
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.ml.features.equity.build_equity_features import build_equity_features
from src.ml.pipeline.feature_store import FeatureStore

PRICES_CSV = ROOT / "data" / "us_daily_prices.csv"


def main():
    print("=" * 60)
    print("  ML Feature Builder  |  " + datetime.now().strftime("%H:%M:%S"))
    print("=" * 60)

    # 가격 데이터 로드
    print("[1/4] 가격 데이터 로드 중…")
    prices_df = pd.read_csv(PRICES_CSV)
    prices_df["Date"] = pd.to_datetime(prices_df["Date"])
    symbols = prices_df["Symbol"].unique().tolist()
    print(f"  총 {len(symbols)}종목, {len(prices_df):,}행")

    # SPY 기준 수익률 (beta 계산용)
    print("[2/4] SPY 기준 데이터 준비 중…")
    spy_df = prices_df[prices_df["Symbol"] == "SPY"].set_index("Date").sort_index()
    spy_close = spy_df["Close"] if not spy_df.empty else None

    # 종목별 피처 빌드
    print(f"[3/4] {len(symbols)}종목 피처 빌드 중…")
    all_frames = []
    errors = []
    for i, sym in enumerate(symbols):
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(symbols)} ({sym})")
        try:
            sym_df = prices_df[prices_df["Symbol"] == sym].set_index("Date").sort_index()
            if len(sym_df) < 60:
                continue
            feats = build_equity_features(sym_df, spy_close=spy_close)
            feats["symbol"] = sym
            feats["close"]  = sym_df["Close"].reindex(feats.index)
            all_frames.append(feats)
        except Exception as e:
            errors.append((sym, str(e)))

    if errors:
        print(f"  경고: {len(errors)}종목 오류 (예: {errors[0]})")

    if not all_frames:
        print("피처 데이터 없음 — 종료")
        return

    # 합치기
    print("[4/4] 병합 및 저장 중…")
    combined = pd.concat(all_frames, axis=0).sort_index()
    print(f"  합계: {combined.shape}  |  종목수: {combined['symbol'].nunique()}")

    store = FeatureStore()
    path  = store.save(combined, "equity_features")
    print(f"\n완료 → {path}")


if __name__ == "__main__":
    main()
