"""함정 필터 + Piotroski F-Score.

"명백히 위험한 것만 제외"가 아니라 "확실히 우량한 것만 통과"를 목표로 하는 임계값.
(2026-08-21: 스크리닝 후보가 570종목 중 302개로 너무 많다는 판단에 따라 상향 조정 —
전에는 Piotroski≥5/ROE≥8%/이자보상≥1배/부채비율≤200%로 "안 망한 회사"만 걸렀다면,
지금은 "재무가 실제로 탄탄한 회사"로 기준을 올림.)

필터 순서:
  1. 관리종목 / 감사의견 비적정 (KR)
  2. 이자보상배율 < 3배 (안전마진 확보)
  3. 영업현금흐름 2년 연속 마이너스
  4. 부채비율 > 150% (금융업 제외)
  5. 매출 + 순이익 3년 연속 동시 감소
  6. Piotroski F-Score < 6
  7. ROE < 12%

`apply_trap_filters()`의 반환값에는 `status`(pass/fail/insufficient_data) 3분류가
들어있다 (SPEC_fundamentals_cache.md §4). 재무 데이터가 아예 없거나 3분류 판정에
필요한 최소 회계기간(MIN_INCOME_PERIODS 등)이 안 되면 탈락이 아니라
insufficient_data — 상장 3년 미만·회계연도 변경 기업이 F-Score 낮음으로 조용히
탈락하는 걸 막기 위함. `pass`/`red_flags`는 하위 호환을 위해 그대로 두었다
(insufficient_data도 pass=False로 나가며, run_screen()은 아직 이 둘을 구분하지
않는다 — 실제 파이프라인 반영은 §3에서).
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

FINANCIAL_SECTORS = {"Financial Services", "Banking", "Insurance", "금융", "은행", "보험"}

# 3분류(통과/탈락/데이터부족) 판정에 필요한 최소 회계기간 수 (SPEC_fundamentals_cache.md §4).
# 매출·순이익 3년 연속 감소 체크에 손익계산서 3개년이 필요하고, Piotroski와
# 영업현금흐름 2년 체크에는 각각 전년 대비 비교가 필요해 2개년이 최소치다.
MIN_INCOME_PERIODS = 3
MIN_BALANCE_PERIODS = 2
MIN_CASHFLOW_PERIODS = 2


def _safe(series: pd.Series | None, col: str, idx: int = 0) -> float | None:
    """DataFrame row에서 안전하게 값 추출."""
    if series is None or col not in series.index:
        return None
    vals = series.loc[col]
    if hasattr(vals, "iloc"):
        vals = vals.dropna()
        return float(vals.iloc[idx]) if len(vals) > idx else None
    return float(vals) if vals is not None else None


def calc_piotroski(fin: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame) -> tuple[int | None, dict]:
    """Piotroski F-Score (0~9) 계산."""
    scores: dict[str, int] = {}

    def g(df, col, idx=0):
        return _safe(df, col, idx)

    # ── 재무 데이터 추출 ──
    net_income   = g(fin, "Net Income")
    net_income_p = g(fin, "Net Income", 1)
    revenue      = g(fin, "Total Revenue")
    revenue_p    = g(fin, "Total Revenue", 1)
    gross_profit = g(fin, "Gross Profit")
    gross_profit_p = g(fin, "Gross Profit", 1)
    ebit         = g(fin, "EBIT") or g(fin, "Operating Income")
    interest_exp = g(fin, "Interest Expense")

    total_assets   = g(bs, "Total Assets")
    total_assets_p = g(bs, "Total Assets", 1)
    lt_debt        = g(bs, "Long Term Debt") or 0.0
    lt_debt_p      = g(bs, "Long Term Debt", 1) or 0.0
    curr_assets    = g(bs, "Current Assets")
    curr_assets_p  = g(bs, "Current Assets", 1)
    curr_liab      = g(bs, "Current Liabilities")
    curr_liab_p    = g(bs, "Current Liabilities", 1)
    shares         = g(bs, "Ordinary Shares Number") or g(bs, "Share Issued")
    shares_p       = g(bs, "Ordinary Shares Number", 1) or g(bs, "Share Issued", 1)

    cfo   = g(cf, "Operating Cash Flow")
    cfo_p = g(cf, "Operating Cash Flow", 1)

    # ── 비율 계산 ──
    roa   = (net_income / total_assets)     if net_income   and total_assets   else None
    roa_p = (net_income_p / total_assets_p) if net_income_p and total_assets_p else None
    lever   = (lt_debt / total_assets)     if total_assets   else 0.0
    lever_p = (lt_debt_p / total_assets_p) if total_assets_p else 0.0
    curr   = (curr_assets / curr_liab)     if curr_assets   and curr_liab   else None
    curr_p = (curr_assets_p / curr_liab_p) if curr_assets_p and curr_liab_p else None
    gm     = (gross_profit / revenue)      if gross_profit and revenue      else None
    gm_p   = (gross_profit_p / revenue_p)  if gross_profit_p and revenue_p  else None
    at     = (revenue / total_assets)      if revenue   and total_assets    else None
    at_p   = (revenue_p / total_assets_p)  if revenue_p and total_assets_p  else None
    cfo_ta = (cfo / total_assets)          if cfo and total_assets          else None

    # ── F-Score 9개 항목 ──
    scores["f1_roa_pos"]        = 1 if roa   and roa > 0                                else 0
    scores["f2_cfo_pos"]        = 1 if cfo   and cfo > 0                                else 0
    scores["f3_roa_inc"]        = 1 if roa   and roa_p  and roa > roa_p                 else 0
    scores["f4_accrual"]        = 1 if cfo_ta and roa   and cfo_ta > roa               else 0
    scores["f5_lever_dec"]      = 1 if lever <= lever_p                                 else 0
    scores["f6_curr_inc"]       = 1 if curr  and curr_p and curr > curr_p               else 0
    scores["f7_no_dilution"]    = 1 if shares and shares_p and shares <= shares_p       else 0
    scores["f8_margin_inc"]     = 1 if gm    and gm_p   and gm > gm_p                  else 0
    scores["f9_turnover_inc"]   = 1 if at    and at_p   and at > at_p                   else 0

    total = sum(scores.values())
    return total, scores


def apply_trap_filters(item: dict) -> dict:
    """
    단일 종목에 함정 필터 적용.

    Returns:
        {
          "pass": bool,
          "red_flags": list[str],
          "piotroski": int | None,
          "debt_ratio": float | None,
          "interest_coverage": float | None,
          "cfo_positive_count": int,   # 최근 2년 중 CFO 양수 연도 수
          "regime_fit": str,           # growth / dividend / neutral
        }
    """
    data       = item.get("financials_data", {})
    info       = data.get("info", {})
    fin: pd.DataFrame = data.get("financials", pd.DataFrame())
    bs: pd.DataFrame  = data.get("balance_sheet", pd.DataFrame())
    cf: pd.DataFrame  = data.get("cashflow", pd.DataFrame())

    red_flags: list[str] = []
    sector = item.get("sector", "")

    # 재무제표가 아예 없거나 3분류 판정에 필요한 최소 기간이 안 되면 탈락이
    # 아니라 데이터부족으로 분류한다 (SPEC §4) — 상장 3년 미만·회계연도 변경·
    # 스핀오프 직후 기업은 F-Score가 낮은 게 아니라 계산 자체가 불가능한
    # 것이라 탈락과 구분해야 한다. red_flags는 기존 그대로(문구만 유지)
    # 채워서, 아직 안 바꾼 주간 파이프라인의 화면 표시는 오늘 그대로 간다 —
    # 새로 추가된 status 필드만 3분류를 구분해서 알려준다.
    insufficient_reason: str | None = None
    if fin.empty and bs.empty and cf.empty:
        insufficient_reason = "재무 데이터 없음"
    elif len(fin.columns) < MIN_INCOME_PERIODS:
        insufficient_reason = f"손익계산서 {len(fin.columns)}개년 (3개년 미만)"
    elif len(bs.columns) < MIN_BALANCE_PERIODS:
        insufficient_reason = f"재무상태표 {len(bs.columns)}개년 (2개년 미만)"
    elif len(cf.columns) < MIN_CASHFLOW_PERIODS:
        insufficient_reason = f"현금흐름표 {len(cf.columns)}개년 (2개년 미만)"

    if insufficient_reason:
        return {
            "pass": False,
            "status": "insufficient_data",
            "red_flags": [insufficient_reason],
            "piotroski": None,
            "debt_ratio": None,
            "interest_coverage": None,
            "cfo_positive_count": 0,
            "regime_fit": "neutral",
            "roe": None,
            "data_notes": {"interest": "데이터 없음", "debt": "데이터 없음"},
        }

    def g_fin(col, idx=0): return _safe(fin, col, idx)
    def g_bs(col, idx=0):  return _safe(bs, col, idx)
    def g_cf(col, idx=0):  return _safe(cf, col, idx)

    # 값이 None인 지표의 "이유" (프론트에서 "-" 대신 표시)
    data_notes: dict[str, str] = {}

    # ── 이자보상배율 ──
    ebit = g_fin("EBIT") or g_fin("Operating Income")
    interest = abs(g_fin("Interest Expense") or 0)
    interest_coverage: float | None = None
    if ebit is not None and interest and interest > 0:
        interest_coverage = ebit / interest
        if interest_coverage < 3.0:
            red_flags.append("이자보상배율<3 (안전마진 부족)")
    elif ebit is not None and ebit < 0:
        red_flags.append("영업이익 적자")
    elif ebit is not None and ebit > 0:
        data_notes["interest"] = "무차입"   # 이자비용 없음 — 계산 불필요한 좋은 상태
    else:
        data_notes["interest"] = "데이터 없음"

    # ── 영업현금흐름 2년 연속 마이너스 ──
    cfo_vals = [g_cf("Operating Cash Flow", i) for i in range(2)]
    cfo_positive_count = sum(1 for v in cfo_vals if v is not None and v > 0)
    if all(v is not None and v < 0 for v in cfo_vals):
        red_flags.append("영업현금흐름 2년 연속 마이너스")

    # ── 부채비율 (금융업 제외) ──
    debt_ratio: float | None = None
    is_financial = any(s in sector for s in FINANCIAL_SECTORS)
    if is_financial:
        data_notes["debt"] = "금융업 제외"
    else:
        # 부채 0(무차입)과 데이터 없음을 구분 — 진짜 0이면 부채비율 0%로 표시
        total_debt = g_bs("Total Debt")
        if total_debt is None:
            ltd, cd = g_bs("Long Term Debt"), g_bs("Current Debt")
            total_debt = ((ltd or 0) + (cd or 0)) if (ltd is not None or cd is not None) else None
        equity = g_bs("Stockholders Equity") or g_bs("Total Stockholder Equity")
        if total_debt is not None and equity and equity > 0:
            debt_ratio = total_debt / equity * 100
            if debt_ratio > 150:
                red_flags.append(f"부채비율 {debt_ratio:.0f}% (150% 초과)")
        elif equity is not None and equity <= 0:
            # 대규모 자사주 매입 기업(DVA·SBUX 등)에서 흔함 — 탈락은 아니지만 알아야 할 정보
            data_notes["debt"] = "자본잠식(음수 자본)"
        else:
            data_notes["debt"] = "데이터 없음"

    # ── 매출 + 순이익 3년 연속 동시 감소 ──
    revenues = [g_fin("Total Revenue", i) for i in range(3)]
    net_incomes = [g_fin("Net Income", i) for i in range(3)]
    if all(v is not None for v in revenues[:3]) and all(v is not None for v in net_incomes[:3]):
        rev_declining    = all(revenues[i] < revenues[i+1] for i in range(2))
        income_declining = all(net_incomes[i] < net_incomes[i+1] for i in range(2))
        if rev_declining and income_declining:
            red_flags.append("매출+순이익 3년 연속 감소")

    # ── 매출 2년 연속 감소 (단독) ──
    if (all(v is not None for v in revenues[:3]) and
            revenues[0] < revenues[1] and revenues[1] < revenues[2]):
        if "매출+순이익 3년 연속 감소" not in red_flags:
            red_flags.append("매출 2년 연속 감소")

    # ── ROE < 12% ──
    roe_pct: float | None = None
    net_income_cur = g_fin("Net Income")
    equity = g_bs("Stockholders Equity") or g_bs("Total Stockholder Equity")
    if net_income_cur is not None and equity and equity > 0:
        roe = net_income_cur / equity
        roe_pct = round(roe * 100, 1)
        if roe < 0.12:
            red_flags.append(f"ROE {roe*100:.1f}% (<12%)")

    # ── Piotroski F-Score ──
    piotroski, _ = calc_piotroski(fin, bs, cf)
    if piotroski is not None and piotroski < 6:
        red_flags.append(f"Piotroski {piotroski}/9 (<6 재무 우량 기준 미달)")

    # ── 시장 체제별 적합도 판단 ──
    div_yield = info.get("dividendYield") or 0
    rev_growth = info.get("revenueGrowth") or 0
    eps_growth = info.get("earningsGrowth") or 0

    if div_yield > 0.02 and (g_fin("Net Income") or 0) > 0:
        regime_fit = "dividend"
    elif rev_growth > 0.1 or eps_growth > 0.15:
        regime_fit = "growth"
    else:
        regime_fit = "neutral"

    return {
        "pass": len(red_flags) == 0,
        "status": "pass" if len(red_flags) == 0 else "fail",
        "red_flags": red_flags,
        "piotroski": piotroski,
        "debt_ratio": round(debt_ratio, 1) if debt_ratio is not None else None,
        "interest_coverage": round(interest_coverage, 2) if interest_coverage is not None else None,
        "cfo_positive_count": cfo_positive_count,
        "regime_fit": regime_fit,
        "roe": roe_pct,
        "data_notes": data_notes,
    }


def run_screen(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """전체 유니버스에 필터 적용. (통과, 탈락) 리스트 반환."""
    passed, failed = [], []

    for item in items:
        result = apply_trap_filters(item)
        info = item.get("financials_data", {}).get("info", {})
        entry = {
            "market":      item.get("market"),
            "symbol":      item.get("symbol"),
            "yf_symbol":   item.get("yf_symbol"),
            "name":        item.get("name"),
            "market_cap":  item.get("market_cap"),
            "sector":      item.get("sector"),
            "piotroski":   result["piotroski"],
            "debt_ratio":  result["debt_ratio"],
            "interest_coverage": result["interest_coverage"],
            "cfo_positive_count": result["cfo_positive_count"],
            "red_flags":   result["red_flags"],
            "regime_fit":  result["regime_fit"],
            "roe":         result["roe"],
            "current_price": info.get("currentPrice"),
            "data_notes":  result["data_notes"],
        }
        if result["pass"]:
            passed.append(entry)
        else:
            failed.append(entry)

    logger.info("스크리닝 완료 — 통과: %d, 탈락: %d", len(passed), len(failed))
    return passed, failed
