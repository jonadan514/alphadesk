"""시장 인식(perceived) 후보 - ETF 구성종목과 현재 소속 비교 (SPEC_theme_company_mapping.md 11장).

DB·네트워크를 쓰지 않는다. 비중 하한, 유니버스 밖 제외, 이미 소속인 종목 제외,
근거가 사라진 perceived 소속 표시를 고정한다.
"""
from __future__ import annotations

from scripts.fetch_kr_theme_etf_holdings import match_themes
from scripts.report_perception_candidates import build_candidates

HOLDINGS = {"date": "20261002", "etfs": [
    {"etf": "111111", "name": "KODEX 해저케이블", "themes": ["cable_wire"], "holdings": [
        {"ticker": "060370", "weight": 8.0},   # 소속 아님 -> 후보
        {"ticker": "001440", "weight": 9.0},   # 이미 소속 -> 제외
        {"ticker": "999999", "weight": 5.0},   # 유니버스 밖 -> 제외
        {"ticker": "222222", "weight": 0.5},   # 비중 하한 미만 -> 제외
    ]},
]}
NAMES = {"060370": "LS마린솔루션", "001440": "대한전선", "222222": "꼬리종목", "333333": "옛인식"}


def test_후보는_비중_하한_이상_유니버스_안_비소속만():
    members = {"cable_wire": {"001440": "direct"}}
    res = build_candidates(HOLDINGS, members, NAMES)
    assert [r[:2] for r in res["add"]] == [["cable_wire", "060370"]]
    tid, code, stage, ev, linkage, name = res["add"][0]
    assert linkage == "perceived" and ev.startswith("ETF 편입:") and "KODEX 해저케이블(111111) 8.0%" in ev


def test_근거가_사라진_시장인식_소속을_표시한다():
    members = {"cable_wire": {"001440": "direct", "333333": "perceived"}}
    res = build_candidates(HOLDINGS, members, NAMES)
    assert res["stale"] == [["cable_wire", "333333", "옛인식"]]


def test_사업_근거_소속은_ETF에_없어도_근거소멸이_아니다():
    members = {"cable_wire": {"444444": "direct"}}
    assert build_candidates(HOLDINGS, members, NAMES)["stale"] == []


def test_ETF_이름_매칭은_해외_레버리지를_거른다():
    kw = {"defense": ["방산"], "shipbuilding": ["조선"]}
    assert match_themes("KODEX K방산", kw) == ["defense"]
    assert match_themes("SOL 조선 TOP3플러스", kw) == ["shipbuilding"]
    assert match_themes("TIGER 미국방산", kw) == []
    assert match_themes("KODEX 방산레버리지", kw) == []
