"""기업 카드의 변화 신호 3개 + 변화 기업 판정 (분기 재설계 docs/REDESIGN_SPEC.md 5장).

입력 계약: `quarters`는 반드시 `src/db/quarterly_financials.py`의 `select_quarters()`가
돌려준 리스트여야 한다. 그 함수가 이미 연결재무 우선·최신 수집분 우선으로 분기 하나당
값 하나씩 고르고, 숫자 컬럼을 실제 숫자로 보정해뒀다(Turso HTTP는 INTEGER를 문자열로
돌려준다 - 2026-09-01 뉴스 기준선이 이걸로 죽은 적이 있다). 이 모듈은 그 위에서 순수
계산만 한다 - DB도, 네트워크도 건드리지 않는다.

## "최근 분기"와 "1년 전 같은 분기"

"최근 분기"는 raw 표에 존재하는 (연도, 분기) 중 가장 큰 값이다. 그 분기의 매출·영업이익이
None이어도(수집은 했는데 값이 비었어도) 그 분기 자체는 "최근 분기"로 친다 - 값이 없으면
그 신호가 데이터부족으로 나올 뿐이다.

"1년 전 같은 분기"는 최근 분기에서 정확히 4분기 앞이다. **raw 표에 있는 분기 목록에서
4번째로 최신인 항목이 아니다** - 중간에 분기가 비어 있으면(예: 2026Q3, 2026Q2, 2025Q4처럼
Q1이 빠짐) 건너뛰어 잇지 않는다(작업지시서 3-1 "분기 누락" 규칙과 같은 원칙). 연도·분기
산수로 목표 분기를 먼저 정하고, 그 분기가 raw 표에 없으면 데이터부족으로 본다.

## 원칙 4: 계산 불가는 탈락이 아니다

세 신호 모두 계산할 수 없으면 `pass: None`을 돌려준다(`False`가 아니다). 변화 기업
판정도 매출 전환이 데이터부족이면 `changed: None`이다(5-2). 매출 흐름·이익 전환이
데이터부족이어도 매출 전환만 계산됐다면 변화 기업 판정은 계속 낼 수 있다 - 5-2는
"매출 전환이 데이터부족이면"이라고만 했지 나머지 둘의 데이터부족을 전체 판정에
전파하라고 하지 않았다. 즉 매출 흐름·이익 전환의 None은 "그 조건은 통과가 아니다"로
취급한다(OR 판정에서 False처럼 작동) - 어차피 두 신호 중 하나만 통과해도 되므로, 하나가
데이터부족이어도 다른 하나가 통과라면 변화 기업이 된다.

## 매출 전환은 비율을 만들지 않는다

"최근 매출 ≥ 1년 전 매출 × 1.20"을 `최근/1년전 - 1 >= 0.20`으로 계산하면 부동소수점
오차로 경계값에서 틀릴 수 있다(나눗셈 뒤 뺄셈은 오차가 겹친다 - 이 저장소에서
`1.10/1 - 1`이 정확히 `0.10`이 아니어서 실제로 틀린 적이 있다). `최근 >= 1년전 * 1.20`
곱셈 비교 하나로 끝낸다.
"""
from __future__ import annotations

import statistics

from src.analyzers import quarterly_thresholds as qt


def _quarter_map(quarters: list[dict]) -> dict[tuple[int, int], dict]:
    """(연도, 분기) -> 그 분기 레코드. fiscal_year/quarter는 int로 다시 감싼다 - select_quarters()가
    이미 보정해두지만, 이 함수를 그 계약 밖(예: DB row를 직접)에서 부르는 실수를 막는 안전망이다."""
    return {(int(q["fiscal_year"]), int(q["fiscal_quarter"])): q for q in quarters}


def _shift_quarter(year: int, quarter: int, n: int) -> tuple[int, int]:
    """분기를 n개 앞으로 민다. n=4면 1년 전 같은 분기, n=1이면 직전 분기."""
    idx = year * 4 + (quarter - 1) - n
    return idx // 4, idx % 4 + 1


def revenue_transition(quarters: list[dict], config: dict | None = None) -> dict:
    """매출 전환: 최근 분기 매출 ≥ 1년 전 같은 분기 매출 × (1 + 기준배수) (5-1).

    데이터부족: 두 분기 중 하나라도 매출 값이 없거나, 1년 전 매출이 0 이하
    (기준을 음수·0에 곱하면 부등식 방향이 뒤집혀 의미가 없어진다).

    반환: {"pass": bool|None, "recent": float|None, "year_ago": float|None, "reason": str|None}
    """
    qmap = _quarter_map(quarters)
    if not qmap:
        return {"pass": None, "recent": None, "year_ago": None, "reason": "분기 재무 없음"}

    latest_key = max(qmap)
    recent_rev = qmap[latest_key].get("revenue")
    year_ago = qmap.get(_shift_quarter(*latest_key, 4))
    year_ago_rev = year_ago.get("revenue") if year_ago else None

    if recent_rev is None or year_ago_rev is None:
        return {"pass": None, "recent": recent_rev, "year_ago": year_ago_rev,
                "reason": "두 분기 중 하나라도 매출 없음"}
    if year_ago_rev <= 0:
        return {"pass": None, "recent": recent_rev, "year_ago": year_ago_rev,
                "reason": "1년 전 매출이 0 이하"}

    pct = qt.revenue_transition_pct(config)
    passed = recent_rev >= year_ago_rev * (1 + pct)
    return {"pass": passed, "recent": recent_rev, "year_ago": year_ago_rev, "reason": None}


def revenue_flow(quarters: list[dict], config: dict | None = None) -> dict:
    """매출 흐름: 최근 5분기 중 직전 분기 대비 매출 증가가 4번 비교 중 기준 횟수 이상 (5-1).

    5분기는 최근 분기에서 연산으로 정한 4개 목표 분기다(위 모듈 설명 참고) - raw 표에
    있는 분기 개수가 아니다. 다섯 중 하나라도 없거나 매출이 없으면 데이터부족이다
    (일부만으로 "4번 중 3번"을 계산하면 비교 횟수 자체가 줄어 기준의 의미가 달라진다).

    반환: {"pass": bool|None, "hits": int|None, "reason": str|None}
    """
    qmap = _quarter_map(quarters)
    if not qmap:
        return {"pass": None, "hits": None, "reason": "분기 재무 없음"}

    latest_key = max(qmap)
    window = [qmap.get(_shift_quarter(*latest_key, n)) for n in range(5)]
    revenues = [w.get("revenue") if w else None for w in window]
    if any(r is None for r in revenues):
        return {"pass": None, "hits": None, "reason": "5분기 매출이 다 갖춰지지 않음"}

    hits = sum(1 for i in range(4) if revenues[i] > revenues[i + 1])
    passed = hits >= qt.revenue_flow_min_hits(config)
    return {"pass": passed, "hits": hits, "reason": None}


def profit_transition(quarters: list[dict]) -> dict:
    """이익 전환: 영업이익률이 1년 전보다 높거나, 1년 전 적자에서 최근 흑자로 (5-1).

    데이터부족: 두 분기 중 하나라도 매출 또는 영업이익이 없음.

    매출이 0이면 그 분기의 영업이익률은 정의되지 않는다(0으로 나눔) - 그 경우 마진
    비교(조건1)만 성립하지 않을 뿐, 적자→흑자 전환(조건2)은 영업이익 부호만 보므로
    매출이 0이어도 그대로 판정할 수 있다. 데이터부족으로 만들지 않고 조건2로 판정을
    넘긴다.

    반환: {"pass": bool|None, "reason": str|None}
    """
    qmap = _quarter_map(quarters)
    if not qmap:
        return {"pass": None, "reason": "분기 재무 없음"}

    latest_key = max(qmap)
    recent = qmap[latest_key]
    year_ago = qmap.get(_shift_quarter(*latest_key, 4))
    if year_ago is None:
        return {"pass": None, "reason": "1년 전 분기 없음"}

    recent_rev, recent_op = recent.get("revenue"), recent.get("operating_income")
    year_rev, year_op = year_ago.get("revenue"), year_ago.get("operating_income")
    if recent_rev is None or recent_op is None or year_rev is None or year_op is None:
        return {"pass": None, "reason": "두 분기 중 하나라도 매출 또는 영업이익 없음"}

    margin_now = recent_op / recent_rev if recent_rev else None
    margin_year_ago = year_op / year_rev if year_rev else None
    margin_improved = (margin_now is not None and margin_year_ago is not None
                       and margin_now > margin_year_ago)
    turned_profitable = year_op < 0 and recent_op > 0
    return {"pass": margin_improved or turned_profitable, "reason": None}


def change_company(quarters: list[dict], config: dict | None = None) -> dict:
    """변화 기업 판정 (5-2): 매출 전환 통과, 그리고 매출 흐름·이익 전환 중 하나 이상 통과.

    매출 전환이 데이터부족이면 전체 판정도 데이터부족이다. 매출 흐름·이익 전환의
    데이터부족은 전체에 전파하지 않는다 - 위 모듈 설명 "원칙 4" 참고.

    반환: {"changed": bool|None, "revenue_transition": {...}, "revenue_flow": {...},
           "profit_transition": {...}}
    """
    rt = revenue_transition(quarters, config)
    if rt["pass"] is None:
        return {"changed": None, "revenue_transition": rt,
                "revenue_flow": None, "profit_transition": None}

    rf = revenue_flow(quarters, config)
    pt = profit_transition(quarters)
    changed = rt["pass"] and (rf["pass"] is True or pt["pass"] is True)
    return {"changed": changed, "revenue_transition": rt,
            "revenue_flow": rf, "profit_transition": pt}


def revenue_yoy_growth(quarters: list[dict]) -> float | None:
    """전년동기 대비 매출 증가율 (화면 참고값 전용, 5-1 마지막 줄 - 판정에는 쓰지 않는다).

    시장 유니버스 중앙값을 내려면 기업마다 이 값을 구해 market_median_revenue_growth()에
    넘긴다. revenue_transition()과 데이터부족 규칙은 같지만 반환이 판정이 아니라 비율이다.
    """
    qmap = _quarter_map(quarters)
    if not qmap:
        return None
    latest_key = max(qmap)
    recent_rev = qmap[latest_key].get("revenue")
    year_ago = qmap.get(_shift_quarter(*latest_key, 4))
    year_ago_rev = year_ago.get("revenue") if year_ago else None
    if recent_rev is None or year_ago_rev is None or year_ago_rev <= 0:
        return None
    return recent_rev / year_ago_rev - 1


def market_median_revenue_growth(growth_rates: list[float | None]) -> float | None:
    """국가별 유니버스 전체의 매출 증가율 중앙값 (5-1 화면 참고값). 판정에는 쓰지 않는다.

    growth_rates는 유니버스 기업마다 revenue_yoy_growth()를 부른 결과 목록이다 - None(계산
    불가)은 걸러내고 나머지로만 중앙값을 낸다(있는 값만으로 평균·중앙값을 내는 건
    괜찮다 - 6-3의 "직전 4분기 평균"과 달리 이건 판정이 아니라 참고 표시이기 때문이다).
    """
    valid = [g for g in growth_rates if g is not None]
    if not valid:
        return None
    return statistics.median(valid)
