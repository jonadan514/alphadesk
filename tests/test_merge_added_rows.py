"""병합 도구의 직접 추가(add) - 사람이 근거를 쓴 행을 새 run에 넣는다.

AI가 어느 run에서도 고르지 않았지만 테마 정의에 맞는 종목(예: 태양광 트래커 NXT)을
넣는 경로다. 빈약한 근거나 잘못된 linkage가 조용히 들어가면 안 되고, 이미 있는
행은 중복으로 넣지 않는다. DB를 쓰지 않는다.
"""
from __future__ import annotations

import pytest

from scripts.build_merged_mapping_run import build_added_rows

EVIDENCE = "Nextpower는 대규모 태양광 발전소용 태양광 트래커를 제조·공급한다."


def _item(**kw):
    base = {"tid": "renewable_energy", "code": "NXT", "stage": "태양광 설비(트래커)",
            "evidence": EVIDENCE, "linkage": "direct"}
    base.update(kw)
    return [base["tid"], base["code"], base["stage"], base["evidence"], base["linkage"]]


def test_행을_만든다_AI판정이_아니라_flagged는_0():
    rows = build_added_rows([_item()], "US", "20261001044703-merge", set())
    assert rows == [{"theme_id": "renewable_energy", "ticker": "NXT", "market": "US",
                     "stage": "태양광 설비(트래커)", "evidence": EVIDENCE, "linkage": "direct",
                     "confidence": "normal", "flagged": 0, "run_id": "20261001044703-merge"}]


def test_이미_있는_행은_건너뛴다():
    assert build_added_rows([_item()], "US", "r", {("renewable_energy", "NXT")}) == []


def test_빈약한_근거는_예외():
    with pytest.raises(ValueError, match="짧다"):
        build_added_rows([_item(evidence="태양광")], "US", "r", set())


def test_잘못된_linkage는_예외():
    with pytest.raises(ValueError, match="linkage"):
        build_added_rows([_item(linkage="strong")], "US", "r", set())
