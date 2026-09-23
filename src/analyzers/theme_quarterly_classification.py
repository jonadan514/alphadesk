"""테마 4칸 분류 (분기 재설계 docs/REDESIGN_SPEC.md 7장).

이 모듈은 이미 있는 두 판정을 테마 단위로 모으기만 한다.
  - 뉴스 "많음"(7-2): `src/analyzers/quarterly_thresholds.is_news_high()`
  - 기업의 변화 판정(5-2): `src/analyzers/company_change_signals.change_company()`

재무 신호 "켜짐"(7-1)은 그 테마 소속 기업들의 `changed` 값을 모아 비율을 낸다 -
계산 자체는 여기서 처음 한다.

## 데이터부족은 탈락이 아니다 (원칙 4)

- 재무: 판정 가능(데이터부족이 아닌) 기업이 `min_judged`(기본 2) 미만이면 재무 신호
  자체가 데이터부족이다. 판정 못 낸 기업을 분모에서 빼는 이유는, 넣으면 판정 가능
  기업이 적을수록 비율이 왜곡되기 때문이다 - 기업 10곳 중 2곳만 판정됐는데 그 2곳이
  다 변화 기업이면 "10곳 중 2곳(20%)"이 아니라 "판정된 2곳 중 2곳(100%)"이 맞는 그림이다.
- 분류: 재무·뉴스 둘 중 하나라도 데이터부족이면 그 테마는 이번 분기에 분류하지 않는다
  (7-3). "꺼짐"이나 "적음"으로 억지로 채우면 근거 없는 판정이 4칸 표에 섞여 든다.
"""
from __future__ import annotations

from src.analyzers import quarterly_thresholds as qt

QUIET_CHANGE = "조용한 변화"       # 재무 켜짐 + 뉴스 적음 - 가장 먼저 볼 후보
CONFIRMED_CHANGE = "확인된 변화"   # 재무 켜짐 + 뉴스 많음 - 밸류 위치를 꼭 확인
LEADING_HYPE = "기대 선행"         # 재무 꺼짐 + 뉴스 많음 - 다음 분기 재무가 따라오는지 관찰
OFF_RADAR = "관심 밖"              # 재무 꺼짐 + 뉴스 적음


def financial_signal(changed_flags: list[bool | None], config: dict | None = None) -> dict:
    """재무 신호 "켜짐" (7-1).

    changed_flags: 그 테마 소속 기업마다
    `company_change_signals.change_company(quarters)["changed"]` 값 (True/False/None)을
    모은 목록.

    켜짐: 변화 기업 비율이 `change_ratio`(기본 30%) 이상이고, 변화 기업 수가
    `min_changed`(기본 2) 이상 - 비율만 보면 기업 1곳짜리 테마가 그 1곳만 변해도
    100%로 켜지므로 최소 개수 조건을 같이 둔다.

    반환: {"on": bool|None, "changed": int, "judged": int, "ratio": float|None,
           "reason": str|None}
    """
    cfg = (config or qt.load())["financial_on"]
    min_judged = int(cfg["min_judged"])
    min_changed = int(cfg["min_changed"])
    change_ratio = float(cfg["change_ratio"])

    judged = [f for f in changed_flags if f is not None]
    n_judged = len(judged)
    n_changed = sum(1 for f in judged if f)

    if n_judged < min_judged:
        return {"on": None, "changed": n_changed, "judged": n_judged, "ratio": None,
                "reason": f"판정 가능 기업이 {min_judged}곳 미만({n_judged}곳)"}

    ratio = n_changed / n_judged
    on = ratio >= change_ratio and n_changed >= min_changed
    return {"on": on, "changed": n_changed, "judged": n_judged, "ratio": ratio, "reason": None}


def classify(financial_on: bool | None, news_high: bool | None) -> str | None:
    """4칸 분류 (7-3). 재무·뉴스 둘 중 하나라도 데이터부족(None)이면 분류하지 않는다."""
    if financial_on is None or news_high is None:
        return None
    if financial_on:
        return CONFIRMED_CHANGE if news_high else QUIET_CHANGE
    return LEADING_HYPE if news_high else OFF_RADAR
