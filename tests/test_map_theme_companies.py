"""매핑 스크립트의 모델 선택과 실행 기록 (검토 지적 A·B, 2026-09-21).

모델은 config/models.yaml 또는 환경변수 MODEL_<ROLE>로 정해진다. 두 가지가 어긋나면 안 된다.
  - 호출에 실제로 쓴 모델과 mapping_runs에 적힌 모델이 같아야 한다(A)
  - A/B 측정이 넣는 덮어쓰기는 "기본 모델과 같은 이름"이어도 그대로 지켜져야 한다(B)
"""
from __future__ import annotations

import pytest

import scripts.map_theme_companies as mapping
from src.db.theme_mapping import ensure_schema


@pytest.fixture(autouse=True)
def _깨끗한_모델_설정(monkeypatch):
    """테스트 사이에 덮어쓰기·환경변수가 새지 않게 한다."""
    monkeypatch.setattr(mapping, "MODEL_OVERRIDE", None, raising=False)
    for role in ("THEME_MAPPING", "MAPPING_CRITIC"):
        monkeypatch.delenv(f"MODEL_{role}", raising=False)


# ── B: 모델 선택 ──────────────────────────────────────────────

def test_덮어쓰기가_없으면_설정의_모델을_쓴다(monkeypatch):
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    assert mapping.active_model("theme_mapping") == "o4-mini"


def test_덮어쓰기가_기본_모델과_같은_이름이어도_그대로_쓴다(monkeypatch):
    """A/B의 기준선 팔이 이 경우다. 예전에는 '기본값과 같다'며 설정 쪽으로 새어나갔다."""
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    monkeypatch.setattr(mapping, "MODEL_OVERRIDE", "gpt-4o-mini")
    assert mapping.active_model("theme_mapping") == "gpt-4o-mini"


def test_덮어쓰기가_있으면_설정을_읽지_않는다(monkeypatch):
    def 부르면_안_됨(*a, **k):
        raise AssertionError("덮어쓰기가 있는데 설정을 읽었다")
    monkeypatch.setattr(mapping.oj, "model_for", 부르면_안_됨)
    monkeypatch.setattr(mapping, "MODEL_OVERRIDE", "gpt-4.1")
    assert mapping.active_model("theme_mapping") == "gpt-4.1"
    assert mapping.active_model("mapping_critic") == "gpt-4.1"


def test_역할마다_설정의_모델이_따로_간다(monkeypatch):
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    monkeypatch.setenv("MODEL_MAPPING_CRITIC", "gpt-4.1-mini")
    assert mapping.active_model("theme_mapping") == "o4-mini"
    assert mapping.active_model("mapping_critic") == "gpt-4.1-mini"


# ── A: 실행 기록 ──────────────────────────────────────────────

def _기록된_모델(conn, run_id):
    return conn.execute("SELECT model FROM mapping_runs WHERE run_id = ?", (run_id,)).fetchone()[0]


def test_실행_기록에_설정의_모델이_남는다(memory_db, monkeypatch):
    """설정을 바꿔 돌렸는데 기록이 옛 기본 모델로 남으면 모델 비교표가 거짓이 된다."""
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    ensure_schema(memory_db)
    run_id = mapping.begin_run(memory_db)
    assert _기록된_모델(memory_db, run_id) == "o4-mini"


def test_실행_기록에_덮어쓴_모델이_남는다(memory_db, monkeypatch):
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    monkeypatch.setattr(mapping, "MODEL_OVERRIDE", "gpt-4o-mini")
    ensure_schema(memory_db)
    run_id = mapping.begin_run(memory_db)
    assert _기록된_모델(memory_db, run_id) == "gpt-4o-mini"


def test_실행_기록에_프롬프트_버전도_남는다(memory_db):
    ensure_schema(memory_db)
    run_id = mapping.begin_run(memory_db)
    got = memory_db.execute("SELECT prompt_ver FROM mapping_runs WHERE run_id = ?", (run_id,)).fetchone()[0]
    assert got == mapping.PROMPT_VERSION
