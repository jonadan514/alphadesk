"""Phase A-4: 실적 축(매출 성장률 가속도) 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §3
"""
from __future__ import annotations

import pandas as pd

# 6개 분기 필요 - g_t(t/t-4)와 g_t-1(t-1/t-5) 계산에 t-5까지 있어야 함 (인덱스 0~5).
MIN_QUARTERS = 6


def _quarter_label(ts) -> str:
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}-Q{q}"


def classify_company_earnings(quarterly_revenue: pd.Series | None) -> tuple[str, str | None]:
    """분기별 매출 Series(index=기간, 최신이 0번째, NaN 제거됨)를 받아
    (status, quarter_label)을 반환한다. status는 'improved'|'not_improved'|'insufficient'.

    분모가 0이거나 없는 경우도 insufficient로 처리 - 성장률 자체가 정의 안 됨.
    """
    if quarterly_revenue is None or len(quarterly_revenue) < MIN_QUARTERS:
        return "insufficient", None

    r = quarterly_revenue
    denom_t4, denom_t5 = r.iloc[4], r.iloc[5]
    if not denom_t4 or not denom_t5:
        return "insufficient", None

    g_t = r.iloc[0] / denom_t4 - 1
    g_t1 = r.iloc[1] / denom_t5 - 1
    status = "improved" if g_t > g_t1 else "not_improved"
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
