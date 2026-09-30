"""테마 뉴스 언급을 분기로 집계한다 (분기 재설계 docs/REDESIGN_SPEC.md 6-3).

뉴스 비율 = 이번 분기 ÷ 직전 4분기 평균. 1.5 이상이면 "많음"(7-2).

## 합이 아니라 주당 평균으로 비교한다

SPEC 6-3은 "기사 수"라고 썼지만 분기 합을 그대로 비교하면 두 가지가 섞인다.
  - **달력**: 한 분기의 월요일은 12-14개로 다르다. 14주 분기는 13주 분기보다 합이 8% 크다.
    화제성이 그대로여도 비율이 8% 움직인다.
  - **결측**: 한 주가 빠지면 그 분기만 8% 작아진다.
주당 평균(기사 수 ÷ 수집된 주 수)으로 비교하면 둘 다 사라진다. 모든 분기가 같은 주 수로
다 모였을 때는 합으로 비교한 값과 같다.

## 스펙과 다르게 한 것: 분기를 나누는 기준

SPEC 6-2는 **발행일** 기준으로 분기를 나누라고 했다. 그렇게 할 수 없다.
백필한 과거 이력(theme_news_weekly)은 **기사 원문을 저장하지 않고 건수만** 남겼다
(62주치 원문이 100만 건이 넘어서 내린 결정). 발행일이 없으니 발행일로 다시 나눌 수 없다.

그래서 **주 단위로 집계하고, 그 주의 월요일이 속한 분기로 센다.**
2026-09-17 점검에서 확인된 차이는 이렇다.
  - 발행일 결측은 0건이지만, 발행일이 수집 주 범위를 벗어난 기사가 10% 있다
    (구글의 after:/before: 필터가 정확하지 않아 앞뒤 주 기사가 섞인다).
  - 분기 경계에 걸친 주에서 이 10%가 다른 분기로 갈 수 있다. 한 분기가 13주이므로
    경계 주 하나의 10%는 전체의 1%가 안 된다.
발행일 기준이 필요해지면 theme_news(원문 표)가 있는 구간만 가능하다.

## 읽는 곳이 두 개인 이유

같은 주간 건수가 두 표에 나뉘어 있다.
  - theme_news_weekly: 과거를 채운 백필 결과 (2025-07-07 이후)
  - theme_signals.news_count: 매주 도는 수집이 남기는 값 (2026-07-13 이후)
둘은 **같은 함수(collect_theme_news)로 같은 주를 조회해 중복 제거 후 센 값**이라 이어
붙일 수 있다. 백필 표를 먼저 쓰고(포화·실패 키워드 정보가 함께 있다), 없는 주만
theme_signals에서 가져온다.

## 데이터부족 (원칙 4: 계산 불가를 탈락으로 처리하지 않는다)

  - 직전 4분기 중 하나라도 없으면 데이터부족 (SPEC 6-3)
  - 어느 분기든 수집된 주가 그 분기 월요일 수의 MIN_WEEK_COVERAGE 미만이면 그 분기는 없는 것으로 본다
    (주당 평균이라 결측이 값을 기울이지는 않지만, 3-4주만 모인 분기를 한 분기로 치지는 않는다)
"""
from __future__ import annotations

from datetime import date, timedelta

MIN_WEEK_COVERAGE = 0.75   # 한 분기에서 이만큼의 주가 모여야 그 분기를 쓴다 (13주 중 10주)
PRIOR_QUARTERS = 4         # 비교 대상 직전 분기 수 (SPEC 6-3)


def quarter_of(week_start: date) -> tuple[int, int]:
    """그 주가 속한 분기. 주의 월요일이 속한 달로 정한다."""
    return week_start.year, (week_start.month - 1) // 3 + 1


def quarter_mondays(year: int, quarter: int) -> list[date]:
    """그 분기에 속하는 월요일 전부. 분기마다 12-14개로 다르다."""
    first = date(year, (quarter - 1) * 3 + 1, 1)
    end = date(year + (quarter == 4), (quarter * 3) % 12 + 1, 1)   # 다음 분기 첫날
    d = first + timedelta(days=(7 - first.weekday()) % 7)          # 첫 월요일
    out = []
    while d < end:
        out.append(d)
        d += timedelta(days=7)
    return out


def prior_quarters(year: int, quarter: int, n: int = PRIOR_QUARTERS) -> list[tuple[int, int]]:
    """직전 n개 분기를 최근 순으로."""
    out = []
    for _ in range(n):
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
        out.append((year, quarter))
    return out


def aggregate_quarters(weekly: dict[str, int]) -> dict[tuple[int, int], dict]:
    """주간 건수 {'2026-07-06': 120, ...}를 분기별로 합친다.

    반환: {(연, 분기): {"articles": 합, "weeks": 수집된 주 수, "per_week": 주당 평균,
                        "expected_weeks": 그 분기 월요일 수, "complete": 충분히 모였는가}}
    """
    by_q: dict[tuple[int, int], dict] = {}
    for wk, count in weekly.items():
        if count is None:
            continue
        key = quarter_of(date.fromisoformat(wk))
        slot = by_q.setdefault(key, {"articles": 0, "weeks": 0})
        slot["articles"] += int(count)
        slot["weeks"] += 1
    for (y, q), slot in by_q.items():
        expected = len(quarter_mondays(y, q))
        slot["expected_weeks"] = expected
        slot["complete"] = slot["weeks"] >= expected * MIN_WEEK_COVERAGE
        slot["per_week"] = slot["articles"] / slot["weeks"] if slot["weeks"] else 0.0
    return by_q


def news_ratio(quarters: dict[tuple[int, int], dict], target: tuple[int, int]) -> dict:
    """이번 분기 ÷ 직전 4분기 평균.

    비교는 주당 평균끼리 한다(위 설명). this_quarter는 화면에 보여줄 실제 기사 수,
    baseline은 직전 4분기의 주당 평균이다.

    반환: {"ratio": float|None, "this_quarter": int|None, "baseline": float|None,
           "reason": str|None}  - reason은 데이터부족일 때만 채운다.
    """
    cur = quarters.get(target)
    if cur is None or not cur["complete"]:
        have = f"{cur['weeks']}/{cur['expected_weeks']}주" if cur else "0주"
        return {"ratio": None, "this_quarter": cur["articles"] if cur else None,
                "baseline": None, "reason": f"이번 분기 주가 모자람({have})"}

    priors = []
    missing = []
    for key in prior_quarters(*target):
        slot = quarters.get(key)
        if slot is None or not slot["complete"]:
            missing.append(f"{key[0]}Q{key[1]}")
        else:
            priors.append(slot["per_week"])
    if missing:
        # SPEC 6-3: 있는 분기만으로 평균 내지 않는다.
        return {"ratio": None, "this_quarter": cur["articles"], "baseline": None,
                "reason": f"직전 분기 이력 없음({', '.join(missing)})"}

    baseline = sum(priors) / len(priors)      # 직전 4분기의 주당 평균
    if baseline == 0:
        return {"ratio": None, "this_quarter": cur["articles"], "baseline": 0.0,
                "reason": "직전 4분기 기사 수가 0"}
    return {"ratio": cur["per_week"] / baseline, "this_quarter": cur["articles"],
            "baseline": baseline, "reason": None}
