"""Phase A-4: 실적 축(매출 성장률) 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §3

SPEC 원안은 "가속도"(g_t > g_t-1, 6분기 필요)를 계산하지만, 실제 백필해보니
yfinance 무료 분기 재무제표(quarterly_financials/quarterly_income_stmt 둘 다)가
사실상 5분기까지만 준다(2026-09-01 확인 - AAPL 등 다수 종목이 정확히 5분기,
그 이상 있는 종목도 오래된 분기는 Total Revenue 자체가 비어있음). 6분기가
필요한 "가속도" 공식은 구조적으로 계산이 안 되어 전체 종목이 데이터부족으로
나오는 문제를 실제로 겪음.

사용자 결정(2026-09-01): 5분기로 계산 가능한 "전년동기 대비 성장" 하나만
본다 - "가속" 개념은 포기하되, 계절성 보정(전년동기 비교)은 유지. 이 도구가
심화분석 이전의 1차 스크리닝 용도라 이 정도 단순화로 충분하다는 판단.

2026-09-07 개정 - 절대 기준("성장률 > 0")에서 상대 기준("같은 시장 중앙값
초과")으로 바꿈. 이유: 성장률 > 0은 미국 138개 기업 중 92%, 한국 58개 중
90%가 통과해서 아무도 못 걸렀고, 그 결과 실적 축이 판정 가능한 테마 전부
up2로 나와 **정보를 전혀 주지 않는 상수**가 돼 있었다(미국 14/14, 한국 7/8).
라벨도 사실상 뉴스·주가로만 결정되고 있었다.

상대 기준의 좋은 성질: 기업의 절반이 자동으로 기준선 위에 놓이므로 테마별
비율이 0.50 중심으로 분포한다 - 기존 임계값(up2 0.70 / up1 0.55 / down 0.45)이
0.50 대칭이라 임계값을 안 바꿔도 그대로 의미를 갖는다. 시장 사이클(호황이면
전부 up, 불황이면 전부 down)에도 흔들리지 않는다. 주가 축이 이미 "지수 대비
초과수익"이라는 상대 비교를 쓰고 있어 도구 전체와도 일관된다.

트레이드오프: "실적이 좋아졌다"가 아니라 "같은 시장 기업들보다 잘했다"는
뜻이 된다. 시장 전체가 역성장하는 국면에서도 상위 테마는 up으로 나올 수 있다.
"""
from __future__ import annotations

import statistics

import pandas as pd

# 5개 분기 필요 - g_yoy(t/t-4) 계산에 t-4까지 있어야 함 (인덱스 0~4).
# yfinance 무료 API가 실질적으로 제공하는 상한이 5분기라 이 이상 요구할 수 없음.
MIN_QUARTERS = 5

# 시장 중앙값을 신뢰하려면 최소 이만큼의 기업 표본이 필요하다. 미달이면
# 중앙값 대신 절대 기준 0으로 폴백한다(개정 전 동작).
MIN_MEDIAN_SAMPLE = 20


def _quarter_label(ts) -> str:
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}-Q{q}"


def yoy_growth(quarterly_revenue: pd.Series | None) -> float | None:
    """전년동기 대비 매출 성장률(g_yoy = 이번 분기 / 작년 같은 분기 - 1).
    계산 불가면 None(분기 부족·분모 0) - 탈락이 아니라 데이터부족이다."""
    if quarterly_revenue is None or len(quarterly_revenue) < MIN_QUARTERS:
        return None
    denom = quarterly_revenue.iloc[4]
    if not denom:
        return None
    return quarterly_revenue.iloc[0] / denom - 1


def market_median_growth(quarterly_revenue_by_ticker: dict[str, pd.Series | None],
                          min_sample: int = MIN_MEDIAN_SAMPLE) -> float | None:
    """이 시장 기업들의 YoY 성장률 중앙값. 표본이 min_sample 미만이면 None
    (중앙값을 신뢰할 수 없어 절대 기준 0으로 폴백하기 위함)."""
    vals = [g for g in (yoy_growth(r) for r in quarterly_revenue_by_ticker.values())
            if g is not None]
    if len(vals) < min_sample:
        return None
    return statistics.median(vals)


def classify_company_earnings(quarterly_revenue: pd.Series | None,
                               reference_growth: float = 0.0) -> tuple[str, str | None]:
    """분기별 매출 Series(index=기간, 최신이 0번째, NaN 제거됨)를 받아
    (status, quarter_label)을 반환한다. status는 'improved'|'not_improved'|'insufficient'.

    성장률이 reference_growth를 넘으면 improved. reference_growth는 보통 같은
    시장의 중앙값이며, 0을 주면 예전(절대 기준) 동작과 같다.
    """
    g_yoy = yoy_growth(quarterly_revenue)
    if g_yoy is None:
        return "insufficient", None

    status = "improved" if g_yoy > reference_growth else "not_improved"
    return status, _quarter_label(quarterly_revenue.index[0])


def compute_earn_signal(members: list[dict], quarterly_revenue_by_ticker: dict[str, pd.Series | None],
                         thresholds: dict, reference_growth: float | None = None) -> dict:
    """members: linkage 필터링이 이미 적용된 theme_members 행 목록(딕셔너리,
    최소 'ticker' 키 필요).
    reference_growth: 이 시장의 기준 성장률(보통 중앙값). None이면 0(절대 기준).
    반환: {members, improved, insufficient, ratio, arrow, as_of, reference_growth}."""
    ref = 0.0 if reference_growth is None else reference_growth
    improved = 0
    insufficient = 0
    quarter_labels: list[str] = []

    for m in members:
        revenue = quarterly_revenue_by_ticker.get(m["ticker"])
        status, q_label = classify_company_earnings(revenue, ref)
        if status == "insufficient":
            insufficient += 1
            continue
        if status == "improved":
            improved += 1
        if q_label:
            quarter_labels.append(q_label)

    total = len(members)
    valid = total - insufficient
    as_of = max(quarter_labels) if quarter_labels else None

    # SPEC §3.3 - 표본 부족(5명 미만) 또는 데이터 신뢰 불가(insufficient 40% 초과)면 na
    if valid < 5 or (total and insufficient / total > 0.4):
        return {"members": total, "improved": improved, "insufficient": insufficient,
                "ratio": None, "arrow": "na", "as_of": as_of, "reference_growth": ref}

    ratio = improved / valid
    if ratio >= thresholds.get("strong_up", 0.70):
        arrow = "up2"
    elif ratio >= thresholds.get("up", 0.55):
        arrow = "up1"
    elif ratio <= thresholds.get("down", 0.45):
        arrow = "down"
    else:
        arrow = "flat"

    return {"members": total, "improved": improved, "insufficient": insufficient,
            "ratio": ratio, "arrow": arrow, "as_of": as_of, "reference_growth": ref}
