"""판정 원장이 읽을 검토 파일 목록(manifest) (작업지시서 Phase 9).

전에는 build_decision_ledger.py에 파일 목록이 하드코딩돼 있어 새 검토를 마칠 때마다 Python 코드를
고쳐야 했다. 이제 data/eval/review_manifest.json에 적는다. 자동 탐색은 하지 않는다 - data/eval에는
정답지·진단 결과 같은 다른 JSON도 있어서 "검토 파일처럼 생긴 것"을 무조건 읽으면 위험하다.
대신 manifest에서 빠진 검토 파일이 있으면 경고해서 조용한 누락을 막는다.
"""
from __future__ import annotations

import json

import pytest

from scripts import build_decision_ledger as bdl


def write_manifest(tmp_path, files):
    (tmp_path / "review_manifest.json").write_text(
        json.dumps({"files": files}, ensure_ascii=False), encoding="utf-8")
    return tmp_path / "review_manifest.json"


def review(tmp_path, name, body):
    (tmp_path / name).write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")


def test_manifest에_적힌_파일과_판정일을_순서대로_읽는다(tmp_path):
    m = write_manifest(tmp_path, [
        {"path": "a_manual_review_1.json", "decided_at": "2026-09-01"},
        {"path": "b_manual_review_2.json", "decided_at": "2026-09-15"},
    ])
    got = bdl.load_manifest(m)
    assert got == [("a_manual_review_1.json", "2026-09-01"), ("b_manual_review_2.json", "2026-09-15")]


def test_파일이_없으면_명확한_오류로_멈춘다(tmp_path):
    with pytest.raises(FileNotFoundError, match="review_manifest"):
        bdl.load_manifest(tmp_path / "none.json")


@pytest.mark.parametrize("entry", [
    {"path": "a.json"},                                    # 판정일 없음
    {"decided_at": "2026-09-15"},                          # 경로 없음
    {"path": "a.json", "decided_at": "15/09/2026"},        # 날짜 형식 오류
])
def test_항목이_잘못되면_어느_항목인지_알려준다(tmp_path, entry):
    m = write_manifest(tmp_path, [entry])
    with pytest.raises(ValueError, match="항목 1"):
        bdl.load_manifest(m)


def test_manifest에_적힌_파일이_디스크에_없으면_오류(tmp_path):
    m = write_manifest(tmp_path, [{"path": "ghost.json", "decided_at": "2026-09-15"}])
    with pytest.raises(FileNotFoundError, match="ghost.json"):
        bdl.collect(m)


def test_판정이_뒤의_파일에서_앞의_파일을_덮는다(tmp_path):
    review(tmp_path, "a_manual_review_1.json", {"exclude": [["battery", "AAPL", "x"]]})
    review(tmp_path, "b_manual_review_2.json", {"keep": [["battery", "AAPL", "재확인 - 정상"]]})
    m = write_manifest(tmp_path, [
        {"path": "a_manual_review_1.json", "decided_at": "2026-09-01"},
        {"path": "b_manual_review_2.json", "decided_at": "2026-09-15"},
    ])
    events = bdl.collect(m)
    assert [e["decision"] for e in events] == ["exclude", "keep"]
    assert [e["decided_at"] for e in events] == ["2026-09-01", "2026-09-15"]


def test_정답지_형식도_읽는다(tmp_path):
    review(tmp_path, "evidence_audit_labels_x.json",
           {"labels": [{"theme_id": "battery", "ticker": "005180", "error": True, "note": "식품"}]})
    m = write_manifest(tmp_path, [{"path": "evidence_audit_labels_x.json", "decided_at": "2026-09-15"}])
    assert bdl.collect(m)[0]["decision"] == "exclude"


# ── manifest에서 빠진 검토 파일 경고 ──────────────────────────

def test_manifest에_없는_검토_파일을_찾아낸다(tmp_path):
    review(tmp_path, "us_v7_manual_review_20260915.json", {})
    review(tmp_path, "us_v8_manual_review_20261001.json", {})     # 새로 만들고 manifest에 안 넣음
    m = write_manifest(tmp_path, [{"path": "us_v7_manual_review_20260915.json", "decided_at": "2026-09-15"}])
    assert bdl.unlisted_review_files(m) == ["us_v8_manual_review_20261001.json"]


def test_검토_파일이_아닌_JSON은_경고하지_않는다(tmp_path):
    review(tmp_path, "mapping_decisions.json", {})          # 원장 자체
    review(tmp_path, "review_manifest.json", {})
    review(tmp_path, "model_ab_result.json", {})
    m = write_manifest(tmp_path, [])
    assert bdl.unlisted_review_files(m) == []


def test_모두_등록돼_있으면_경고가_없다(tmp_path):
    review(tmp_path, "a_manual_review_1.json", {})
    m = write_manifest(tmp_path, [{"path": "a_manual_review_1.json", "decided_at": "2026-09-01"}])
    assert bdl.unlisted_review_files(m) == []


# ── 실제 저장소 파일 ──────────────────────────────────────────

def test_실제_manifest가_기존_하드코딩_목록과_같다():
    """이번 작업은 목록의 위치만 옮기는 것이지 내용을 바꾸는 게 아니다."""
    expected = [
        ("evidence_audit_labels_20260915.json", "2026-09-15"),
        ("v5_1_manual_review_20260915.json", "2026-09-15"),
        ("v6_manual_review_20260915.json", "2026-09-15"),
        ("us_v6_manual_review_20260915.json", "2026-09-15"),
        ("us_v7_manual_review_20260915.json", "2026-09-15"),
    ]
    assert bdl.load_manifest() == expected


def test_실제_data_eval에_manifest에서_빠진_검토_파일이_없다():
    assert bdl.unlisted_review_files() == []


def test_manifest로_만든_원장이_저장소의_원장과_같다():
    """manifest 방식으로 바꿔도 mapping_decisions.json의 내용이 그대로여야 한다."""
    committed = json.loads(bdl.OUT.read_text(encoding="utf-8"))["decisions"]
    key = lambda r: (r["market"], r["theme_id"], r["ticker"])
    ledger = {}
    for e in bdl.collect():
        ledger[key(e)] = e
    rebuilt = sorted(ledger.values(), key=key)
    assert len(rebuilt) == len(committed)
    assert [(r["theme_id"], r["ticker"], r["decision"]) for r in rebuilt] == \
           [(r["theme_id"], r["ticker"], r["decision"]) for r in committed]
