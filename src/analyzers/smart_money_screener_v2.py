import numpy as np
import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from datetime import datetime
from pathlib import Path

from src.analyzers.technical_indicators import add_all_indicators

OUTPUT_DIR = Path(__file__).parents[2] / "output" / "picks"

WEIGHTS = {
    "technical":        0.25,
    "fundamental":      0.20,
    "analyst":          0.15,
    "relative_strength": 0.15,
    "volume":           0.15,
    "institutional":    0.10,
}

GRADE_THRESHOLDS = [(80, "A"), (70, "B"), (60, "C"), (50, "D")]


def _grade(score: float) -> str:
    for threshold, letter in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


class EnhancedSmartMoneyScreener:
    def __init__(self):
        self._session = curl_requests.Session(impersonate="chrome")
        self._spy_ret20: float | None = None

    # ------------------------------------------------------------------
    # SPY benchmark
    # ------------------------------------------------------------------
    def _get_spy_ret20(self) -> float:
        if self._spy_ret20 is not None:
            return self._spy_ret20
        try:
            df = yf.Ticker("SPY", session=self._session).history(period="3mo", auto_adjust=True)
            if df is not None and len(df) >= 20:
                self._spy_ret20 = float(df["Close"].iloc[-1] / df["Close"].iloc[-20] - 1) * 100
                return self._spy_ret20
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # Factor scorers  (each returns 0-100)
    # ------------------------------------------------------------------

    def _score_technical(self, df: pd.DataFrame) -> float:
        if df.empty or len(df) < 30:
            return 50.0
        ind = add_all_indicators(df)
        last = ind.iloc[-1]
        score = 50.0

        rsi = last.get("RSI14")
        if rsi is not None:
            if 40 <= rsi <= 60:
                score += 10
            elif rsi < 30:
                score += 15   # oversold bounce
            elif rsi > 70:
                score -= 10

        macd = last.get("MACD")
        signal = last.get("MACD_Signal")
        if macd is not None and signal is not None:
            score += 10 if macd > signal else -5

        close = last.get("Close")
        sma50 = last.get("SMA50")
        sma200 = last.get("SMA200")
        if close and sma50 and close > sma50:
            score += 10
        if close and sma200 and close > sma200:
            score += 10
        if sma50 and sma200 and sma50 > sma200:
            score += 5   # golden cross

        return float(np.clip(score, 0, 100))

    def _score_fundamental(self, info: dict) -> float:
        score = 50.0

        pe = info.get("forwardPE") or info.get("trailingPE")
        if pe is not None:
            if pe < 15:
                score += 10
            elif pe < 25:
                score += 5
            elif pe > 40:
                score -= 10

        eg = info.get("earningsGrowth")
        if eg is not None:
            if eg > 0.25:   score += 15   # O'Neil: +25% EPS 최소 기준
            elif eg > 0.15: score += 10
            elif eg > 0.05: score += 5
            elif eg < 0:    score -= 12

        # Lynch 핵심: PEG 비율 (PER ÷ 이익성장률) — 1 미만이 매수 적기
        if pe and eg and pe > 0 and eg > 0:
            peg = pe / (eg * 100)
            if peg < 0.5:   score += 20
            elif peg < 1.0: score += 15
            elif peg < 1.5: score += 8
            elif peg < 2.0: score += 3
            elif peg > 2.5: score -= 10

        roe = info.get("returnOnEquity")
        if roe is not None:
            if roe > 0.20:  score += 10
            elif roe > 0.10: score += 5
            elif roe < 0:   score -= 10

        # O'Neil: 52주 신고가 근접 (바닥보다 고점 돌파 선호)
        week52_high = info.get("fiftyTwoWeekHigh")
        current     = info.get("currentPrice")
        if week52_high and current and week52_high > 0:
            pct_from_high = (current / week52_high - 1) * 100
            if pct_from_high > -5:    score += 12  # 신고가 돌파 직전
            elif pct_from_high > -15: score += 6   # 조정 후 재상승 구간
            elif pct_from_high < -35: score -= 8   # 고점 대비 너무 하락

        return float(np.clip(score, 0, 100))

    def _score_analyst(self, info: dict) -> float:
        score = 50.0

        rating = info.get("recommendationMean")  # 1=Strong Buy … 5=Sell
        if rating is not None:
            if rating <= 1.5:
                score += 25
            elif rating <= 2.0:
                score += 15
            elif rating <= 2.5:
                score += 5
            elif rating >= 4.0:
                score -= 20

        target = info.get("targetMeanPrice")
        current = info.get("currentPrice")
        if target and current and current > 0:
            upside = (target - current) / current
            if upside > 0.20:
                score += 15
            elif upside > 0.10:
                score += 8
            elif upside < -0.05:
                score -= 10

        return float(np.clip(score, 0, 100))

    def _score_relative_strength(self, df: pd.DataFrame) -> float:
        spy_ret = self._get_spy_ret20()
        if df.empty or len(df) < 20:
            return 50.0
        close = df["Close"]
        ret20 = float(close.iloc[-1] / close.iloc[-20] - 1) * 100
        diff = ret20 - spy_ret
        if diff > 5:
            return 90.0
        if diff > 2:
            return 75.0
        if diff > 0:
            return 60.0
        if diff > -3:
            return 45.0
        return 25.0

    def _score_volume(self, df: pd.DataFrame) -> float:
        if df.empty or "Volume" not in df.columns or len(df) < 20:
            return 50.0
        vol = df["Volume"].tail(20)
        mean = vol.mean()
        std = vol.std()
        if std == 0:
            return 50.0
        recent_avg = df["Volume"].tail(5).mean()
        z = (recent_avg - mean) / std
        if z > 2:
            return 90.0
        if z > 1:
            return 75.0
        if z > 0:
            return 60.0
        if z > -1:
            return 45.0
        return 30.0

    def _score_institutional(self, symbol: str) -> float:
        try:
            t = yf.Ticker(symbol, session=self._session)
            holders = t.major_holders
            if holders is None or holders.empty:
                return 50.0
            # row 0: % of shares held by all insider, row 1: % held by institutions
            inst_pct_str = holders.iloc[1, 0] if len(holders) > 1 else None
            if inst_pct_str is None:
                return 50.0
            pct = float(str(inst_pct_str).replace("%", "").strip())
            if pct > 80:
                return 85.0
            if pct > 60:
                return 70.0
            if pct > 40:
                return 55.0
            return 40.0
        except Exception:
            return 50.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def _score_symbol(self, symbol: str, price_data: dict[str, pd.DataFrame]) -> dict | None:
        df = price_data.get(symbol, pd.DataFrame())
        try:
            info = yf.Ticker(symbol, session=self._session).info or {}
        except Exception:
            info = {}

        tech  = self._score_technical(df)
        fund  = self._score_fundamental(info)
        anal  = self._score_analyst(info)
        rs    = self._score_relative_strength(df)
        vol   = self._score_volume(df)
        inst  = self._score_institutional(symbol)

        composite = (
            tech  * WEIGHTS["technical"]
            + fund  * WEIGHTS["fundamental"]
            + anal  * WEIGHTS["analyst"]
            + rs    * WEIGHTS["relative_strength"]
            + vol   * WEIGHTS["volume"]
            + inst  * WEIGHTS["institutional"]
        )

        pe = info.get("forwardPE") or info.get("trailingPE")
        eg = info.get("earningsGrowth")
        peg = round(pe / (eg * 100), 2) if (pe and eg and eg > 0 and pe > 0) else None
        week52_high = info.get("fiftyTwoWeekHigh")
        cur_price   = info.get("currentPrice")
        pct_from_52h = round((cur_price / week52_high - 1) * 100, 1) if (week52_high and cur_price) else None

        return {
            "symbol":            symbol,
            "composite_score":   round(composite, 2),
            "grade":             _grade(composite),
            "technical":         round(tech, 2),
            "fundamental":       round(fund, 2),
            "analyst":           round(anal, 2),
            "relative_strength": round(rs, 2),
            "volume":            round(vol, 2),
            "institutional":     round(inst, 2),
            "current_price":     cur_price,
            "target_price":      info.get("targetMeanPrice"),
            "sector":            info.get("sector", ""),
            "peg_ratio":         peg,
            "earnings_growth":   round(eg * 100, 1) if eg else None,
            "pct_from_52h":      pct_from_52h,
        }

    def screen(
        self,
        symbols: list[str],
        price_data: dict[str, pd.DataFrame],
        top_n: int = 20,
    ) -> pd.DataFrame:
        rows = []
        for sym in symbols:
            try:
                row = self._score_symbol(sym, price_data)
                if row:
                    rows.append(row)
            except Exception as exc:
                print(f"[Screener] {sym} skipped: {exc}")

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).sort_values("composite_score", ascending=False).head(top_n)
        df = df.reset_index(drop=True)
        df.index += 1

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.today().strftime("%Y%m%d")
        path = OUTPUT_DIR / f"smart_money_picks_{date_str}.csv"
        df.to_csv(path, index=True, index_label="rank")
        print(f"Saved {len(df)} picks → {path}")
        return df
