"""판정 원장 규칙 (docs/TEST_PLAN.md 6장, 작업지시서 17장).

사람이 한 번 내린 판정을 다음 분기 run에 자동 적용하는 장치의 순수 함수만 덮는다.
TTL(400일)·stale(300일) 처리는 apply_decision_ledger.main() 안에 있어 아직 함수로
분리돼 있지 않다 - Phase 6에서 판정 로직을 함수로 빼낸 뒤 여기에 추가한다.
"""
from __future__ import annotations

import pytest

from scripts.apply_decision_ledger import STALE_DAYS, TTL_DAYS, both_axes_failed, needs_look
from scripts.build_decision_ledger import _market, _walk


def walk(data: dict) -> list[dict]:
    out: list[dict] = []
    _walk(data, "test.json", "2026-09-21", out)
    return out


# ── 시장 판정 ─────────────────────────────────────────────────

@pytest.mark.parametrize("ticker,market", [
    ("005930", "KR"),
    ("0126Z0", "KR"),    # 영문이 섞인 신형 코드
    ("064760", "KR"),
    ("AAPL", "US"),
    ("BRK-B", "US"),
    ("GE", "US"),
])
def test_티커_모양으로_시장을_가른다(ticker, market):
    assert _market(ticker) == market


# ── 검토 파일 읽기 ────────────────────────────────────────────

def test_exclude와_unapprove는_제외_판정이다():
    got = walk({"exclude": [["battery", "AAPL", "배터리 아님"]],
                "unapprove": [["power_grid", "ES", "유틸리티 경계"]]})
    assert [(r["ticker"], r["decision"]) for r in got] == [("AAPL", "exclude"), ("ES", "exclude")]


@pytest.mark.parametrize("key", ["keep", "restore", "approve", "items"])
def test_keep_restore_approve_items는_정상_판정이다(key):
    got = walk({key: [["medical_device", "JNJ", "MedTech 사업부"]]})
    assert got[0]["decision"] == "keep" and got[0]["market"] == "US"


def test_이유에_판단보류가_있으면_hold():
    got = walk({"keep": [["ai_software", "CDNS", "EDA에 AI 기능 - 판단보류"]]})
    assert got[0]["decision"] == "hold"


def test_이유에_판단보류가_있어도_제외_판정은_제외다():
    got = walk({"exclude": [["battery", "AAPL", "판단보류였다가 제외"]]})
    assert got[0]["decision"] == "exclude"


def test_중첩된_구조도_읽는다():
    got = walk({"round2_gate": {"unapprove": [["semi_equipment", "INTC", "칩 설계사"]]}})
    assert got[0]["ticker"] == "INTC" and got[0]["source"].endswith("round2_gate.unapprove")


def test_메모용_키는_읽지_않는다():
    got = walk({"_about": "설명", "empty_themes": [["rare_earth", "메모"]], "tickers": ["CRWD"],
                "exclude": [["battery", "AAPL", "x"]]})
    assert [r["ticker"] for r in got] == ["AAPL"]


def test_형식이_이상한_항목은_건너뛴다():
    got = walk({"exclude": [["battery"], "문자열", ["battery", "AAPL", "정상"]]})
    assert [r["ticker"] for r in got] == ["AAPL"]


def test_이유가_없어도_판정은_읽는다():
    got = walk({"exclude": [["battery", "AAPL"]]})
    assert got[0]["reason"] == ""


def test_판정일과_출처를_남긴다():
    got = walk({"exclude": [["battery", "AAPL", "x"]]})
    assert got[0]["decided_at"] == "2026-09-21" and got[0]["source"] == "test.json.exclude"


# ── 감사 판정 해석 ────────────────────────────────────────────

@pytest.mark.parametrize("verdict,expected", [
    ({"evidence": "contradicts", "fit": "fits"}, True),
    ({"evidence": "consistent", "fit": "not_fits"}, True),
    ({"evidence": "contradicts", "fit": "not_fits"}, True),
    ({"evidence": "missing", "fit": "missing"}, True),
    ({"evidence": "error", "fit": "error"}, True),
    ({"evidence": "consistent", "fit": "fits"}, False),
    ({"evidence": "unverifiable", "fit": "unclear"}, False),   # 확인 불가는 오류로 치지 않는다
])
def test_감사가_문제_삼았거나_판정이_없으면_사람이_본다(verdict, expected):
    assert needs_look(verdict) is expected


@pytest.mark.parametrize("verdict,expected", [
    ({"evidence": "contradicts", "fit": "not_fits"}, True),
    ({"evidence": "contradicts", "fit": "fits"}, False),
    ({"evidence": "consistent", "fit": "not_fits"}, False),
    ({"evidence": "contradicts", "fit": "fits", "quote_verified": False}, False),   # 인용만 어긋난 경우
    ({"evidence": "missing", "fit": "missing"}, False),
    ({"evidence": "consistent", "fit": "fits"}, False),
])
def test_두_축이_모두_실패한_경우에만_자동_제외한다(verdict, expected):
    assert both_axes_failed(verdict) is expected


def test_유효기간_상수():
    """4분기 + 여유(400일)가 만료, 300일부터 '사업 변화 확인' 표시."""
    assert TTL_DAYS == 400 and STALE_DAYS == 300
    assert STALE_DAYS < TTL_DAYS
