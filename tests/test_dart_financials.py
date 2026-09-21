"""DART 주요계정 -> 분기값 변환 규칙 (작업지시서 3-1).

검증하는 규칙 (docs/REDESIGN_SPEC.md 4-1)
  - 금액 문자열 파싱
  - 연결재무(CFS) 우선, 없으면 별도재무(OFS)
  - 반기·3분기는 누적이 아니라 3개월 값
  - 4분기 = 연간 - 1~3분기 누적
  - 분기가 중간에 비면 그 앞으로는 이어 붙이지 않는다
"""
from __future__ import annotations

import pytest

from collectors.dart_financials import (extract_statement, latest_quarters, parse_amount,
                                         quarterly_values)


def row(account: str, fs_div: str, three: str, cumulative: str = "", sj_div: str = "IS") -> dict:
    """주요계정 API 응답 한 줄."""
    return {"account_nm": account, "fs_div": fs_div, "sj_div": sj_div,
            "thstrm_amount": three, "thstrm_add_amount": cumulative}


# ── 금액 파싱 ─────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("1,234,567", 1234567),
    ("-1,234", -1234),
    ("", None),
    ("-", None),
    (None, None),
    ("12,000,000,000", 12_000_000_000),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


# ── 연결재무 우선 ─────────────────────────────────────────────

def test_연결재무가_있으면_별도재무는_쓰지_않는다():
    rows = [row("매출액", "CFS", "300"), row("매출액", "OFS", "150")]
    st = extract_statement(rows)
    assert st["fs_div"] == "CFS"
    assert st["three_month"]["revenue"] == 300


def test_연결재무가_없으면_별도재무를_쓴다():
    st = extract_statement([row("매출액", "OFS", "150")])
    assert st["fs_div"] == "OFS"
    assert st["three_month"]["revenue"] == 150


def test_손익계산서가_아닌_행은_무시한다():
    rows = [row("매출액", "CFS", "300", sj_div="BS"), row("매출액", "CFS", "250", sj_div="IS")]
    assert extract_statement(rows)["three_month"]["revenue"] == 250


@pytest.mark.parametrize("account", ["영업이익", "영업이익(손실)"])
def test_계정명_표기가_달라도_같은_항목으로_읽는다(account):
    st = extract_statement([row(account, "CFS", "-5")])
    assert st["three_month"]["operating_income"] == -5


# ── 분기값 ────────────────────────────────────────────────────

def base_reports(year: int = 2025) -> dict:
    """1분기 200 / 2분기 250 / 3분기 260(누적 710) / 연간 1000 -> 4분기 290."""
    return {
        (year, "11013"): [row("매출액", "CFS", "200", "200"), row("영업이익", "CFS", "20", "20")],
        (year, "11012"): [row("매출액", "CFS", "250", "450"), row("영업이익", "CFS", "30", "50")],
        (year, "11014"): [row("매출액", "CFS", "260", "710"), row("영업이익", "CFS", "40", "90")],
        (year, "11011"): [row("매출액", "CFS", "1,000"), row("영업이익", "CFS", "150")],
    }


def test_반기_3분기는_누적이_아니라_3개월_값을_쓴다():
    v = quarterly_values(base_reports())
    assert v[(2025, 2)]["revenue"] == 250   # 누적 450이 아니다
    assert v[(2025, 3)]["revenue"] == 260   # 누적 710이 아니다


def test_4분기는_연간에서_3분기_누적을_뺀다():
    v = quarterly_values(base_reports())
    assert v[(2025, 4)]["revenue"] == 1000 - 710
    assert v[(2025, 4)]["operating_income"] == 150 - 90
    assert v[(2025, 4)]["derived"] == "annual_minus_9m"


def test_3분기_누적이_없으면_1_2_3분기_합으로_대신한다():
    reports = base_reports()
    reports[(2025, "11014")] = [row("매출액", "CFS", "260"), row("영업이익", "CFS", "40")]
    v = quarterly_values(reports)
    assert v[(2025, 4)]["revenue"] == 1000 - (200 + 250 + 260)


def test_연결과_별도가_섞이면_4분기를_계산하지_않는다():
    reports = {
        (2025, "11014"): [row("매출액", "OFS", "260", "710")],
        (2025, "11011"): [row("매출액", "CFS", "1,000")],
    }
    v = quarterly_values(reports)
    assert v.get((2025, 4), {}).get("revenue") is None


def test_사업보고서만_있으면_4분기를_만들지_않는다():
    v = quarterly_values({(2025, "11011"): [row("매출액", "CFS", "1,000")]})
    assert (2025, 4) not in v


# ── 최근 분기 선택 ────────────────────────────────────────────

def test_최근_5분기를_최신순으로_돌려준다():
    values = {**quarterly_values(base_reports(2025)), **quarterly_values(base_reports(2026))}
    got = [k for k, _ in latest_quarters(values, 5)]
    assert got == [(2026, 4), (2026, 3), (2026, 2), (2026, 1), (2025, 4)]


def test_중간_분기가_비면_그_앞으로는_이어_붙이지_않는다():
    # 2026Q3, 2026Q2 다음에 2026Q1이 없다 -> 2025Q4까지 이어가면 안 된다
    values = {(2026, 3): {"revenue": 1}, (2026, 2): {"revenue": 1}, (2025, 4): {"revenue": 1}}
    assert [k for k, _ in latest_quarters(values, 5)] == [(2026, 3), (2026, 2)]


def test_값이_없으면_빈_목록():
    assert latest_quarters({}, 5) == []
