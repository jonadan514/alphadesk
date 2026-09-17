"""DART 정기보고서 주요계정 응답을 분기별 매출·영업이익·순이익으로 바꾼다.

네트워크 없이 테스트할 수 있게 계산만 따로 둔다(호출은 dart_client.py).
분기 재설계 명세 docs/REDESIGN_SPEC.md 4-1의 규칙을 그대로 옮겼다.

DART 보고서 코드
  11013 1분기보고서   손익 thstrm_amount = 1-3월(3개월)
  11012 반기보고서    손익 thstrm_amount = 4-6월(3개월), thstrm_add_amount = 1-6월 누적
  11014 3분기보고서   손익 thstrm_amount = 7-9월(3개월), thstrm_add_amount = 1-9월 누적
  11011 사업보고서    손익 thstrm_amount = 연간 합계 -> 4분기는 직접 계산해야 한다

규칙
  - 연결재무(CFS)를 우선하고, 없으면 별도재무(OFS). 어느 쪽을 썼는지 남긴다.
  - 반기·3분기는 "3개월" 값(thstrm_amount)을 쓴다. 누적값을 쓰면 분기 비교가 망가진다.
  - 4분기 = 연간 - 1~3분기 누적. 3분기보고서의 누적값이 있으면 그것을, 없으면
    1·2·3분기 3개월 값의 합을 쓴다. 셋 중 하나라도 없으면 4분기는 계산하지 않는다(데이터부족).
  - 한 분기 안에서 매출·영업이익·순이익은 같은 재무제표 구분(CFS/OFS)에서 가져온다.
    섞어 쓰면 영업이익률 같은 비율이 의미 없어진다.
"""
from __future__ import annotations

REPORT_Q1 = "11013"
REPORT_H1 = "11012"
REPORT_Q3 = "11014"
REPORT_FY = "11011"
REPORT_CODES = (REPORT_Q1, REPORT_H1, REPORT_Q3, REPORT_FY)
QUARTER_OF_REPORT = {REPORT_Q1: 1, REPORT_H1: 2, REPORT_Q3: 3}

# 주요계정 API의 계정명은 회사마다 조금씩 다르다("영업이익(손실)", "당기순이익(손실)" 등).
ACCOUNT_PREFIXES = {
    "revenue": ("매출액", "수익(매출액)", "영업수익"),
    "operating_income": ("영업이익",),
    "net_income": ("당기순이익", "당기순손익"),
}


def parse_amount(text) -> int | None:
    """'1,234,567' / '-1,234' / '' / '-' -> int 또는 None."""
    if text is None:
        return None
    s = str(text).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _account_key(account_nm: str) -> str | None:
    name = (account_nm or "").replace(" ", "")
    for key, prefixes in ACCOUNT_PREFIXES.items():
        if any(name.startswith(p) for p in prefixes):
            return key
    return None


def extract_statement(rows: list[dict]) -> dict:
    """한 보고서의 주요계정 행 목록 -> {fs_div, three_month: {...}, cumulative: {...}}.

    손익계산서(sj_div == 'IS' 또는 'CIS') 행만 본다. CFS가 하나라도 있으면 CFS만 쓰고,
    없으면 OFS를 쓴다. 계정이 없으면 그 키를 넣지 않는다.
    """
    income_rows = [r for r in rows if str(r.get("sj_div", "")).upper() in ("IS", "CIS")]
    divs = {str(r.get("fs_div", "")).upper() for r in income_rows}
    fs_div = "CFS" if "CFS" in divs else ("OFS" if "OFS" in divs else None)
    out: dict = {"fs_div": fs_div, "three_month": {}, "cumulative": {}}
    if fs_div is None:
        return out
    for r in income_rows:
        if str(r.get("fs_div", "")).upper() != fs_div:
            continue
        key = _account_key(r.get("account_nm", ""))
        if not key or key in out["three_month"]:
            continue  # 같은 계정이 여러 번 나오면 첫 행(보통 대표 계정)을 쓴다
        three = parse_amount(r.get("thstrm_amount"))
        cum = parse_amount(r.get("thstrm_add_amount"))
        if three is not None:
            out["three_month"][key] = three
        if cum is not None:
            out["cumulative"][key] = cum
    return out


def quarterly_values(reports: dict[tuple[int, str], list[dict]]) -> dict[tuple[int, int], dict]:
    """{(사업연도, 보고서코드): 주요계정 행 목록} -> {(연도, 분기): 값}.

    값: {revenue, operating_income, net_income, fs_div, derived}
      derived: 'reported'(보고서 3개월 값) | 'annual_minus_9m'(4분기 계산값)
    계산할 수 없는 계정은 None. 분기 자체를 만들 수 없으면 키를 넣지 않는다.
    """
    parsed = {k: extract_statement(v) for k, v in reports.items()}
    result: dict[tuple[int, int], dict] = {}
    keys = ("revenue", "operating_income", "net_income")

    years = sorted({y for y, _ in parsed})
    for year in years:
        for code, q in QUARTER_OF_REPORT.items():
            st = parsed.get((year, code))
            if not st or st["fs_div"] is None or not st["three_month"]:
                continue
            result[(year, q)] = {**{k: st["three_month"].get(k) for k in keys},
                                 "fs_div": st["fs_div"], "derived": "reported"}

        fy = parsed.get((year, REPORT_FY))
        if not fy or fy["fs_div"] is None:
            continue
        # 4분기: 연간 - 1~3분기 누적. 같은 재무제표 구분(CFS/OFS)끼리만 뺀다.
        q3 = parsed.get((year, REPORT_Q3))
        q4: dict = {"fs_div": fy["fs_div"], "derived": "annual_minus_9m"}
        for k in keys:
            annual = fy["three_month"].get(k)  # 사업보고서의 thstrm_amount는 연간
            nine = None
            if q3 and q3["fs_div"] == fy["fs_div"]:
                nine = q3["cumulative"].get(k)
            if nine is None:
                parts = [result.get((year, i), {}) for i in (1, 2, 3)]
                if all(p.get("fs_div") == fy["fs_div"] and p.get(k) is not None for p in parts):
                    nine = sum(p[k] for p in parts)
            q4[k] = annual - nine if annual is not None and nine is not None else None
        if any(q4[k] is not None for k in keys):
            result[(year, 4)] = q4
    return result


def latest_quarters(values: dict[tuple[int, int], dict], n: int = 5) -> list[tuple[tuple[int, int], dict]]:
    """가장 최근 분기부터 거꾸로 n개. 중간에 빠진 분기가 있으면 거기서 멈춘다 -
    연속되지 않은 분기로 "직전 분기 대비"를 계산하면 틀린 신호가 나온다."""
    if not values:
        return []
    ordered = sorted(values, reverse=True)
    out = [(ordered[0], values[ordered[0]])]
    y, q = ordered[0]
    while len(out) < n:
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
        if (y, q) not in values:
            break
        out.append(((y, q), values[(y, q)]))
    return out
