"""매핑 코드 검증 규칙 (작업지시서 16장).

LLM이 만든 후보를 코드가 걸러내는 단계다. 여기서 잘못 떨어뜨리면 정당한 기업이
테마에서 통째로 빠지고, 잘못 통과시키면 사람 검토 부담이 늘어난다.
"""
from __future__ import annotations

import pytest

from scripts.map_theme_companies import (industry_theme_conflict, validate_members,
                                          _evidence_subject_mismatch)

# 실제 상수와 같은 값(watchlist_collector). 통화 단위가 다르다는 점이 아래 시장 오판
# 테스트의 핵심이라 테스트 안에 그대로 적어둔다.
US_MIN_CAP = 2_000_000_000        # 20억 달러
KR_MIN_CAP = 200_000_000_000      # 2000억 원

EVID = "반도체 전공정 식각 장비를 공급한다"   # 15자 이상, 금지어 없음


def cand(ticker: str, market: str | None = None, evidence: str = EVID, **extra) -> dict:
    m = {"ticker": ticker, "evidence": evidence, "linkage": "direct", **extra}
    if market:
        m["market"] = market
    return m


# ── 티커·근거 검증 ────────────────────────────────────────────

def test_유니버스에_없는_티커는_제외한다():
    out, stats = validate_members([cand("ZZZZ")], [], {"AAPL"}, {})
    assert out == []
    assert stats["티커실재실패"] == 1


def test_근거가_15자_미만이면_제외한다():
    out, stats = validate_members([cand("AAPL", evidence="짧다")], [], {"AAPL"}, {})
    assert out == []
    assert stats["evidence품질실패"] == 1


def test_근거의_주어가_다른_회사면_제외한다():
    names = {"000660": "SK하이닉스", "096770": "SK이노베이션"}
    out, stats = validate_members(
        [cand("000660", evidence="SK이노베이션은 전기차 배터리를 생산한다")], [], {"000660"}, {}, names)
    assert out == []
    assert stats["근거주어불일치"] == 1


def test_주어가_본인이면_통과한다():
    names = {"000660": "SK하이닉스"}
    out, _ = validate_members(
        [cand("000660", evidence="SK하이닉스는 HBM 고대역폭 메모리를 양산한다")], [], {"000660"}, {}, names)
    assert [m["ticker"] for m in out] == ["000660"]


@pytest.mark.parametrize("phrase", ["관련주", "테마주", "수혜 예상"])
def test_금지_문구는_제외가_아니라_표시만_한다(phrase):
    out, _ = validate_members([cand("AAPL", evidence=f"이 기업은 {phrase}로 자주 거론된다")],
                              [], {"AAPL"}, {})
    assert len(out) == 1 and out[0]["flagged"] is True


def test_linkage_이상값은_partial로_바꾼다():
    out, _ = validate_members([cand("AAPL", linkage="strong")], [], {"AAPL"}, {})
    assert out[0]["linkage"] == "partial"


# ── 시가총액 하한과 시장 판정 (Phase 2) ───────────────────────
#
# 하한값의 통화가 다르다: US는 달러, KR은 원. 그래서 오판 방향에 따라 결과가 다르다.
#   KR 종목을 US로 오판 -> 원화 시총(5e11)을 달러 하한(2e9)과 비교 -> 늘 통과(무해)
#   US 종목을 KR로 오판 -> 달러 시총(3e9)을 원화 하한(2e11)과 비교 -> 부당 탈락(위험)
# 라벨만 확인하는 테스트로는 이 버그를 못 잡는다 - 시총 판정 결과를 봐야 한다.

def test_미국_종목을_LLM이_한국으로_잘못_답해도_탈락시키지_않는다():
    """이게 Phase 2가 고치는 버그다. 고치기 전에는 시가총액 미달로 빠진다."""
    out, stats = validate_members(
        [cand("NVDA", market="KR")], [], {"NVDA"}, {"NVDA": 3_000_000_000},
        universe_market={"NVDA": "US"})
    assert [m["ticker"] for m in out] == ["NVDA"], "30억 달러짜리 미국 기업이 빠지면 안 된다"
    assert stats["시가총액미달"] == 0
    assert out[0]["market"] == "US"


def test_한국_종목을_LLM이_미국으로_잘못_답해도_한국으로_처리한다():
    out, _ = validate_members(
        [cand("064760", market="US")], [], {"064760"}, {"064760": 500_000_000_000},
        universe_market={"064760": "KR"})
    assert out[0]["market"] == "KR"


def test_시가총액이_정말_미달이면_제외한다():
    out, stats = validate_members(
        [cand("TINY")], [], {"TINY"}, {"TINY": 1_000_000_000},
        universe_market={"TINY": "US"})
    assert out == []
    assert stats["시가총액미달"] == 1


def test_시가총액을_모르면_통과시킨다():
    """계산 불가를 탈락으로 처리하지 않는다(원칙 4)."""
    out, _ = validate_members([cand("AAPL")], [], {"AAPL"}, {}, universe_market={"AAPL": "US"})
    assert len(out) == 1


# ── 업종-테마 허용 규칙 ───────────────────────────────────────

def test_금융사는_일반_산업테마에_들어갈_수_없다():
    profiles = {"001450": {"industry": "Insurance - Property & Casualty"}}
    assert industry_theme_conflict("battery", "001450", profiles) == "Insurance - Property & Casualty"


def test_식품사는_K푸드_테마에는_허용한다():
    profiles = {"004370": {"industry": "Packaged Foods"}}
    assert industry_theme_conflict("k_food", "004370", profiles) is None
    assert industry_theme_conflict("petrochemical", "004370", profiles) is not None


def test_산업분류가_없으면_규칙을_적용하지_않는다():
    assert industry_theme_conflict("battery", "999999", {"999999": {}}) is None


def test_근거_주어_검사_함수는_회사명_3글자_이상_일치할_때만_잡는다():
    names = {"000660": "SK하이닉스", "096770": "SK이노베이션"}
    assert _evidence_subject_mismatch("000660", "SK이노베이션의 배터리 사업", names) == "SK이노베이션"
    assert _evidence_subject_mismatch("000660", "HBM을 양산한다", names) is None
