"""
한국 주식 스크리너
- KOSPI 주요 종목 대상
- 4팩터: 기술적(0.35) + 펀더멘털(0.20) + RS vs KOSPI(0.30) + 거래량(0.15)
- yfinance .KS 티커 사용
"""
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

from src.analyzers.technical_indicators import add_all_indicators
from src.collectors.kr_kospi_list import get_kospi_list

WEIGHTS = {
    "technical":        0.35,
    "fundamental":      0.20,
    "relative_strength": 0.30,
    "volume":           0.15,
}

GRADE_THRESHOLDS = [(80, "A"), (70, "B"), (60, "C"), (50, "D")]


def _grade(score: float) -> str:
    for threshold, letter in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


class KRStockScreener:
    def __init__(self):
        self._kospi_ret20: float | None = None
        self.full_scored: pd.DataFrame = pd.DataFrame()  # screen() 후 전체 채점 결과

    def _get_kospi_ret20(self) -> float:
        if self._kospi_ret20 is not None:
            return self._kospi_ret20
        try:
            df = yf.Ticker("^KS11").history(period="3mo", auto_adjust=True)
            if df is not None and len(df) >= 20:
                self._kospi_ret20 = float(df["Close"].iloc[-1] / df["Close"].iloc[-20] - 1) * 100
                return self._kospi_ret20
        except Exception:
            pass
        return 0.0

    def _score_technical(self, df: pd.DataFrame) -> float:
        if df.empty or len(df) < 30:
            return 50.0
        try:
            ind = add_all_indicators(df)
            last = ind.iloc[-1]
            score = 50.0

            rsi = last.get("RSI14")
            if rsi is not None:
                if 40 <= rsi <= 60: score += 10
                elif rsi < 30:      score += 15
                elif rsi > 70:      score -= 10

            macd   = last.get("MACD")
            signal = last.get("MACD_Signal")
            if macd is not None and signal is not None:
                score += 10 if macd > signal else -5

            close  = last.get("Close")
            sma50  = last.get("SMA50")
            sma200 = last.get("SMA200")
            if close and sma50  and close > sma50:  score += 10
            if close and sma200 and close > sma200: score += 10
            if sma50  and sma200 and sma50 > sma200: score += 5

            return float(np.clip(score, 0, 100))
        except Exception:
            return 50.0

    def _score_fundamental(self, info: dict) -> float:
        score = 50.0
        try:
            pe = info.get("trailingPE") or info.get("forwardPE")
            if pe and pe > 0:
                if pe < 10:   score += 10
                elif pe < 15: score += 7
                elif pe < 25: score += 3
                elif pe > 40: score -= 10

            pb = info.get("priceToBook")
            if pb and pb > 0:
                if pb < 1.0:  score += 12
                elif pb < 2.0: score += 6
                elif pb > 5.0: score -= 10

            roe = info.get("returnOnEquity")
            if roe and roe > 0:
                if roe > 0.20: score += 10
                elif roe > 0.10: score += 5
                elif roe < 0:  score -= 10

            eg = info.get("earningsGrowth")
            if eg is not None:
                if eg > 0.25:   score += 15  # O'Neil: +25% EPS 최소 기준
                elif eg > 0.15: score += 10
                elif eg > 0.05: score += 5
                elif eg < 0:    score -= 12

            # Lynch 핵심: PEG 비율 — 한국 시장은 PEG < 0.7이 매력적
            if pe and pe > 0 and eg and eg > 0:
                peg = pe / (eg * 100)
                if peg < 0.5:   score += 20
                elif peg < 0.7: score += 15
                elif peg < 1.0: score += 8
                elif peg < 1.5: score += 3
                elif peg > 2.0: score -= 10

            de = info.get("debtToEquity")
            if de is not None and de > 0:
                if de < 50:   score += 5
                elif de > 200: score -= 8
        except Exception:
            pass
        return float(np.clip(score, 0, 100))

    def _score_rs(self, df: pd.DataFrame) -> float:
        try:
            if df.empty or len(df) < 20:
                return 50.0
            ret20 = float(df["Close"].iloc[-1] / df["Close"].iloc[-20] - 1) * 100
            kospi_ret20 = self._get_kospi_ret20()
            rs = ret20 - kospi_ret20
            if rs > 10:   return 90.0
            if rs > 5:    return 75.0
            if rs > 2:    return 65.0
            if rs > 0:    return 55.0
            if rs > -3:   return 45.0
            if rs > -7:   return 35.0
            return 20.0
        except Exception:
            return 50.0

    def _score_volume(self, df: pd.DataFrame) -> float:
        try:
            if df.empty or len(df) < 20:
                return 50.0
            vol20_avg = df["Volume"].iloc[-20:-1].mean()
            vol_today = float(df["Volume"].iloc[-1])
            if vol20_avg <= 0:
                return 50.0
            ratio = vol_today / vol20_avg
            if ratio > 3.0:  return 90.0
            if ratio > 2.0:  return 80.0
            if ratio > 1.5:  return 70.0
            if ratio > 1.0:  return 60.0
            if ratio > 0.7:  return 45.0
            return 30.0
        except Exception:
            return 50.0

    def _action(self, score: float, regime: str) -> str:
        if regime in ("risk_on", "neutral"):
            if score >= 70: return "BUY"
            if score >= 55: return "WATCH"
        else:
            if score >= 80: return "WATCH"
        return "HOLD"

    def screen(self, regime: str = "neutral") -> pd.DataFrame:
        kospi_list = get_kospi_list()
        results = []

        for _, row in kospi_list.iterrows():
            symbol = row["Symbol"]   # e.g. "005930.KS"
            name   = row["Name"]
            sector = row["Sector"]
            try:
                ticker = yf.Ticker(symbol)
                hist   = ticker.history(period="1y", auto_adjust=True)
                if hist.empty or len(hist) < 30:
                    continue
                info = {}
                try:
                    info = ticker.info or {}
                except Exception:
                    pass

                tech  = self._score_technical(hist)
                fund  = self._score_fundamental(info)
                rs    = self._score_rs(hist)
                vol   = self._score_volume(hist)

                composite = (
                    tech  * WEIGHTS["technical"] +
                    fund  * WEIGHTS["fundamental"] +
                    rs    * WEIGHTS["relative_strength"] +
                    vol   * WEIGHTS["volume"]
                )
                grade  = _grade(composite)
                action = self._action(composite, regime)

                cur_price   = round(float(hist["Close"].iloc[-1]), 0)
                week52_high = info.get("fiftyTwoWeekHigh")
                week52_low  = info.get("fiftyTwoWeekLow")
                pct_from_high = round((cur_price / week52_high - 1) * 100, 1) if week52_high else None
                pe_val = info.get("trailingPE") or info.get("forwardPE")
                eg_val = info.get("earningsGrowth")
                peg = round(pe_val / (eg_val * 100), 2) if (pe_val and eg_val and pe_val > 0 and eg_val > 0) else None

                results.append({
                    "symbol":          symbol,
                    "name":            name,
                    "sector":          sector,
                    "composite_score": round(composite, 2),
                    "grade":           grade,
                    "action":          action,
                    "technical":       round(tech, 1),
                    "fundamental":     round(fund, 1),
                    "relative_strength": round(rs - 50, 2),
                    "volume":          round(vol, 1),
                    "cur_price":       cur_price,
                    "per":             round(pe_val or 0, 1) or None,
                    "pbr":             round(info.get("priceToBook") or 0, 2) or None,
                    "roe":             round((info.get("returnOnEquity") or 0) * 100, 1) or None,
                    "peg_ratio":       peg,
                    "earnings_growth": round((eg_val or 0) * 100, 1) or None,
                    "market_cap":      info.get("marketCap"),
                    "week52_high":     week52_high,
                    "week52_low":      week52_low,
                    "pct_from_52h":    pct_from_high,
                    "dividend_yield":  round((info.get("dividendYield") or 0) * 100, 2) or None,
                    "debt_to_equity":  info.get("debtToEquity"),
                })
            except Exception:
                continue

        df = pd.DataFrame(results)
        if df.empty:
            self.full_scored = df
            return df
        # 전체 채점 결과 보존 (top-30 밖 종목도 매수체크에서 조회 가능하게)
        df_full = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
        self.full_scored = df_full
        return df_full.head(30).reset_index(drop=True)


if __name__ == "__main__":
    screener = KRStockScreener()
    picks = screener.screen("neutral")
    print(picks[["symbol", "name", "composite_score", "grade", "action"]].to_string())
