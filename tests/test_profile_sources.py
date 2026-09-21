"""KR 프로필의 출처를 필드별로 기록 (작업지시서 Phase 8).

전에는 레코드 전체에 source="dart" 하나만 붙였다. 그런데 실제로는 industry는 DART지만
summary는 yfinance일 수 있다 - 어느 필드를 어디서 가져왔는지 알아야 나중에 값이 이상할 때
원인을 좇을 수 있다.

규칙
  - DART가 **실제로 채운 필드만** <필드>_source = "dart"로 기록한다
  - 이미 값이 있어서 건드리지 않은 필드는 출처를 바꾸지 않는다
  - 출처가 아직 없는 기존 값은 "yfinance"로 간주한다(옛 데이터는 전부 yfinance에서 왔다)
  - 기존 source 필드는 하위 호환을 위해 유지한다
  - kr_profile_overrides.json이 덮은 industry는 industry_source="override" (기존 동작)
"""
from __future__ import annotations

import pytest

from scripts.fill_kr_profiles_from_dart import apply_dart_fields
from src.collectors.kr_profiles import FIELD_SOURCE_KEYS, backfill_field_sources


def test_비어_있던_필드만_DART로_채우고_출처를_남긴다():
    rec = apply_dart_fields({}, industry="반도체 제조업", industry_code="26110",
                            overview="당사는 반도체 장비를 제조합니다. " * 20)
    assert rec["industry"] == "반도체 제조업" and rec["industry_source"] == "dart"
    assert rec["summary_source"] == "dart" and rec["summary_long_source"] == "dart"
    assert rec["industry_code"] == "26110"


def test_이미_있는_요약은_덮어쓰지_않고_출처도_바꾸지_않는다():
    existing = {"industry": "Semiconductors", "summary": "Samsung makes chips.",
                "summary_long": "Samsung makes chips and phones.",
                "industry_source": "yfinance", "summary_source": "yfinance",
                "summary_long_source": "yfinance"}
    rec = apply_dart_fields(existing, industry="반도체 제조업", industry_code="26110",
                            overview="당사는 반도체를 제조합니다. " * 20)
    assert rec["summary"] == "Samsung makes chips."
    assert rec["summary_source"] == "yfinance" and rec["summary_long_source"] == "yfinance"
    assert rec["industry"] == "Semiconductors" and rec["industry_source"] == "yfinance"


def test_산업분류만_DART로_채우고_요약은_원래_출처를_유지한다():
    """요약은 yfinance에 있고 산업분류만 비어 있던 종목."""
    existing = {"summary": "A company.", "summary_source": "yfinance"}
    rec = apply_dart_fields(existing, industry="화학", industry_code="20111", overview=None)
    assert rec["industry_source"] == "dart" and rec["summary_source"] == "yfinance"
    assert "summary_long_source" not in rec


def test_사업의_개요를_못_찾으면_요약_출처를_만들지_않는다():
    rec = apply_dart_fields({}, industry="지주회사", industry_code="64992", overview=None)
    assert rec["industry_source"] == "dart"
    assert "summary" not in rec and "summary_source" not in rec


def test_요약은_140자와_2500자로_나눠_저장한다():
    rec = apply_dart_fields({}, industry="x", industry_code="1", overview="가" * 3000)
    assert len(rec["summary"]) == 140 and len(rec["summary_long"]) == 2500


def test_옛_source_필드는_유지한다():
    rec = apply_dart_fields({}, industry="x", industry_code="1", overview="가" * 300)
    assert rec["source"] == "dart"


def test_DART가_아무것도_바꾸지_않으면_source를_붙이지_않는다():
    existing = {"industry": "Semiconductors", "summary": "s", "summary_long": "sl"}
    rec = apply_dart_fields(existing, industry="반도체", industry_code="26", overview="가" * 300)
    assert "source" not in rec


def test_refresh_모드에서는_DART가_채운_요약만_다시_쓴다():
    existing = {"summary": "old", "summary_long": "old long", "summary_source": "dart",
                "summary_long_source": "dart", "source": "dart"}
    rec = apply_dart_fields(existing, industry=None, industry_code=None,
                            overview="새 본문입니다. " * 30, refresh=True)
    assert rec["summary"].startswith("새 본문") and rec["summary_source"] == "dart"


def test_refresh_모드에서도_yfinance_요약은_건드리지_않는다():
    existing = {"summary": "yf", "summary_long": "yf long", "summary_source": "yfinance",
                "summary_long_source": "yfinance"}
    rec = apply_dart_fields(existing, industry=None, industry_code=None,
                            overview="새 본문입니다. " * 30, refresh=True)
    assert rec["summary"] == "yf" and rec["summary_source"] == "yfinance"


def test_원본_dict를_바꾸지_않는다():
    existing = {"industry": "x", "industry_source": "yfinance"}
    apply_dart_fields(existing, industry="y", industry_code="1", overview="가" * 300)
    assert existing == {"industry": "x", "industry_source": "yfinance"}


# ── 기존 데이터에 출처 채우기 ─────────────────────────────────

def test_출처가_없는_기존_값은_yfinance로_간주한다():
    rec = backfill_field_sources({"industry": "Semiconductors", "sector": "Technology",
                                  "summary": "s", "summary_long": "sl"})
    assert rec["industry_source"] == rec["summary_source"] == rec["summary_long_source"] == "yfinance"


def test_옛_record_source가_dart이면_DART가_채운_필드는_dart로_표시한다():
    """옛 형식: industry_code가 있으면 industry는 DART, summary는 DART가 채웠을 때만 source=dart."""
    rec = backfill_field_sources({"industry": "지주회사", "industry_code": "64992",
                                  "summary": "본문", "summary_long": "본문 길게", "source": "dart"})
    assert rec["industry_source"] == "dart" and rec["summary_source"] == "dart"


def test_industry_code가_없는_옛_dart_레코드의_산업분류는_yfinance다():
    rec = backfill_field_sources({"industry": "Semiconductors", "summary": "본문", "source": "dart"})
    assert rec["industry_source"] == "yfinance"
    assert rec["summary_source"] == "dart"


def test_이미_출처가_있으면_바꾸지_않는다():
    rec = backfill_field_sources({"industry": "x", "industry_source": "override"})
    assert rec["industry_source"] == "override"


def test_값이_없는_필드에는_출처를_만들지_않는다():
    rec = backfill_field_sources({"industry": "x"})
    assert "summary_source" not in rec and "summary_long_source" not in rec


def test_출처_기록_대상_필드():
    assert set(FIELD_SOURCE_KEYS) == {"industry", "summary", "summary_long"}
