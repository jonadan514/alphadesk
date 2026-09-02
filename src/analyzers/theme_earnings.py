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
"""
from __future__ import annotations

import pandas as pd

# 5개 분기 필요 - g_yoy(t/t-4) 계산에 t-4까지 있어야 함 (인덱스 0~4).
# yfinance 무료 API가 실질적으로 제공하는 상한이 5분기라 이 이상 요구할 수 없음.
MIN_QUARTERS = 5


def _quarter_label(ts) -> str:
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}-Q{q}"


def classify_company_earnings(quarterly_revenue: pd.Series | None) -> tuple[str, str | None]:
    """분기별 매출 Series(index=기간, 최신이 0번째, NaN 제거됨)를 받아
    (status, quarter_label)을 반환한다. status는 'improved'|'not_improved'|'insufficient'.

    전년동기 대비 성장률(g_yoy = 이번 분기 / 작년 같은 분기 - 1)이 양수면 improved.
    분모가 0이거나 없는 경우도 insufficient로 처리 - 성장률 자체가 정의 안 됨.
    """
    if quarterly_revenue is None or len(quarterly_revenue) < MIN_QUARTERS:
        return "insufficient", None

    r = quarterly_revenue
    denom_yoy = r.iloc[4]
    if not denom_yoy:
        return "insufficient", None

    g_yoy = r.iloc[0] / denom_yoy - 1
    status = "improved" if g_yoy > 0 else "not_improved"
    return status, _quarter_label(r.index[0])


def compute_earn_signal(members: list[dict], quarterly_revenue_by_ticker: dict[str, pd.Series | None],
                         thresholds: dict) -> dict:
    """members: linkage 필터링이 이미 적용된 theme_members 행 목록(딕셔너리,
    최소 'ticker' 키 필요). 반환: {members, improved, insufficient, ratio, arrow, as_of}."""
    improved = 0
    insufficient = 0
    quarter_labels: list[str] = []

    for m in members:
        revenue = quarterly_revenue_by_ticker.get(m["ticker"])
        status, q_label = classify_company_earnings(revenue)
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
                "ratio": None, "arrow": "na", "as_of": as_of}

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
            "ratio": ratio, "arrow": arrow, "as_of": as_of}
