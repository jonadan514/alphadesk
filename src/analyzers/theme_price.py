"""Phase A-5: 주가 축(4주 수익률 중앙값 vs 시장지수) 계산.

SPEC: docs/radar/SPEC_phase_a_signals.md §4
"""
from __future__ import annotations

import statistics


def compute_price_signal(members: list[dict], returns_by_ticker: dict[str, float | None],
                          index_return: float | None, thresholds: dict,
                          vol_ratio_by_ticker: dict[str, float | None] | None = None) -> dict:
    """members: linkage 필터링이 이미 적용된 theme_members 행 목록(최소 'ticker' 키).
    반환: {valid_count, median_ret, index_ret, excess, arrow, volume_ratio}.

    평균이 아니라 중앙값을 쓴다(SPEC §4.1) - 한 종목 급등락에 전체가 안 흔들리게.

    volume_ratio(2026-09-16 추가)는 소속 기업 거래대금 변화의 중앙값이다. 화살표를
    만들지 않는다 - 네 번째 축이 아니라 주가 축 옆에 붙는 참고 수치다(원칙 1: 축을
    늘리거나 합산하지 않는다). 수익률보다 반 박자 빠르게 움직이는 경우를 보라고 둔 것.
    """
    valid_returns = [returns_by_ticker[m["ticker"]] for m in members
                      if returns_by_ticker.get(m["ticker"]) is not None]
    valid_count = len(valid_returns)

    vols = [v for v in ((vol_ratio_by_ticker or {}).get(m["ticker"]) for m in members) if v is not None]
    volume_ratio = statistics.median(vols) if len(vols) >= 5 else None

    # SPEC §4.2 - 가격 데이터 확보 기업 5명 미만이거나 지수 수익률 자체를 못 구했으면 na
    if valid_count < 5 or index_return is None:
        return {"valid_count": valid_count, "median_ret": None, "index_ret": index_return,
                "excess": None, "arrow": "na", "volume_ratio": volume_ratio}

    median_ret = statistics.median(valid_returns)
    excess = median_ret - index_return

    if excess >= thresholds.get("strong_up", 0.08):
        arrow = "up2"
    elif excess >= thresholds.get("up", 0.03):
        arrow = "up1"
    elif excess <= thresholds.get("down", -0.03):
        arrow = "down"
    else:
        arrow = "flat"

    return {"valid_count": valid_count, "median_ret": median_ret, "index_ret": index_return,
            "excess": excess, "arrow": arrow, "volume_ratio": volume_ratio}
