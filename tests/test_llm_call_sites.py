"""매핑·감사의 LLM 호출부가 공통 클라이언트를 거치는지 (작업지시서 Phase 4·5).

호출부마다 이전 동작(temperature·토큰 한도·타임아웃·실패 처리)이 달랐다. 공통화하면서
그 차이가 조용히 사라지면 감사·매핑 품질이 달라지므로 호출부별로 고정해 둔다.
"""
from __future__ import annotations

import json

import pytest

import scripts.audit_mapping_evidence as audit
import scripts.map_theme_companies as mapping
from src.llm import openai_json as oj


class Resp:
    def __init__(self, content, status=200):
        self.status_code = status
        self.headers = {}
        self._c = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise oj.requests.HTTPError(str(self.status_code))

    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self._c)}}]}


@pytest.fixture
def http(monkeypatch):
    st = {"queue": [], "calls": []}

    def post(url, headers=None, json=None, timeout=None):
        st["calls"].append({"body": json, "timeout": timeout})
        item = st["queue"].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(oj.requests, "post", post)
    monkeypatch.setattr(oj.time, "sleep", lambda s: None)
    return st


THEME = {"id": "battery", "name_ko": "2차전지", "name_en": "Battery", "keywords_ko": ["배터리"],
         "value_chain": "배터리 셀 제조"}
MEMBER = {"theme_id": "battery", "ticker": "373220", "evidence": "배터리 셀을 생산한다", "linkage": "direct"}
PROFILES = {"373220": {"industry": "Batteries", "summary_long": "LG Energy Solution makes battery cells."}}


# ── 매핑 ──────────────────────────────────────────────────────

def test_매핑_호출은_예전_파라미터를_유지한다(http):
    http["queue"].append(Resp({"members": []}))
    assert mapping._openai_json("p", "s", "k") == {"members": []}
    call = http["calls"][0]
    assert call["timeout"] == 90
    assert call["body"]["temperature"] == 0.2 and call["body"]["max_tokens"] == 2000


def test_매핑은_호출이_실패하면_None을_돌려주고_실패를_센다(http):
    http["queue"].append(oj.requests.HTTPError("x"))     # 400 계열 - 재시도 없이 실패
    before = mapping.CALL_FAILURES
    assert mapping._openai_json("p", "s", "k") is None
    assert mapping.CALL_FAILURES == before + 1


def test_매핑_모델을_바꾸면_추론_모델용_파라미터가_간다(http, monkeypatch):
    monkeypatch.setattr(mapping, "OPENAI_MODEL", "o4-mini")
    http["queue"].append(Resp({"members": []}))
    mapping._openai_json("p", "s", "k")
    body = http["calls"][0]["body"]
    assert body["model"] == "o4-mini" and "temperature" not in body and "max_completion_tokens" in body


def test_비판_패스는_mapping_critic_역할의_모델을_쓴다(http, monkeypatch):
    monkeypatch.setenv("MODEL_MAPPING_CRITIC", "gpt-4.1-mini")
    monkeypatch.setenv("MODEL_THEME_MAPPING", "gpt-4o")
    http["queue"] += [Resp({"flag": []}), Resp({"members": []})]
    mapping.critique_pass(THEME, [{"ticker": "373220", "evidence": "배터리 셀을 생산한다"}], {}, "k", PROFILES)
    mapping._openai_json("p", "s", "k")
    assert http["calls"][0]["body"]["model"] == "gpt-4.1-mini"     # 비판
    assert http["calls"][1]["body"]["model"] == "gpt-4o"           # 후보 생성


# ── 감사 ──────────────────────────────────────────────────────

def test_감사_판정은_예전_파라미터를_유지한다(http):
    http["queue"].append(Resp({"verdicts": [{"ticker": "373220", "evidence": "consistent", "fit": "fits"}]}))
    got = audit.judge(THEME, [MEMBER], {"373220": "LG에너지솔루션"}, PROFILES, "k")
    assert "373220" in got
    call = http["calls"][0]
    assert call["timeout"] == 180
    assert call["body"]["temperature"] == 0.0 and call["body"]["max_tokens"] == 4000


def test_감사_판정이_실패하면_예외가_올라간다(http):
    """호출부(main)가 이 예외로 테마를 '판정 호출 실패'로 표시한다 - None으로 삼키면 안 된다."""
    http["queue"].append(oj.requests.HTTPError("x"))
    with pytest.raises(oj.OpenAICallError):
        audit.judge(THEME, [MEMBER], {}, PROFILES, "k")


def test_인용_재질의는_예전_파라미터를_유지한다(http):
    http["queue"].append(Resp({"quotes": [{"ticker": "373220", "support": "makes battery cells"}]}))
    got = audit.requote(THEME, [(MEMBER, {})], PROFILES, "k")
    assert got == {"373220": "makes battery cells"}
    call = http["calls"][0]
    assert call["body"]["temperature"] == 0.0 and call["body"]["max_tokens"] == 2000 and call["timeout"] == 180


def test_인용_재질의도_이제_일시_오류를_재시도한다(http):
    """예전에는 재시도가 없어 일시 오류가 나면 1차 판정이 그대로 남았다."""
    class R429(Resp):
        def __init__(self): super().__init__({}, 429)
    http["queue"] += [R429(), Resp({"quotes": [{"ticker": "373220", "support": "x"}]})]
    assert audit.requote(THEME, [(MEMBER, {})], PROFILES, "k") == {"373220": "x"}
    assert len(http["calls"]) == 2


def test_감사_모델을_o4_mini로_바꿔도_요청이_거절되지_않는_형식이다(http, monkeypatch):
    """지시서가 걱정한 문제: 감사에 temperature·max_tokens가 박혀 있어 o4-mini로 바꾸면 400이 난다."""
    monkeypatch.setattr(audit, "MODEL", "o4-mini")
    http["queue"].append(Resp({"verdicts": []}))
    audit.judge(THEME, [MEMBER], {}, PROFILES, "k")
    body = http["calls"][0]["body"]
    assert "temperature" not in body and "max_tokens" not in body and "max_completion_tokens" in body


def test_감사와_매핑_모델을_따로_고를_수_있다(monkeypatch):
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    assert oj.model_for("theme_mapping") == "o4-mini"
    assert oj.model_for("mapping_audit") == "gpt-4o-mini"


def test_운영_코드는_공통_클라이언트를_한_가지_경로로만_import한다():
    """src와 src/가 둘 다 import 경로에 있어 같은 모듈이 `src.llm`과 `llm` 두 이름으로 따로
    로드될 수 있다. 그러면 예외 클래스가 서로 달라 `except OpenAICallError`가 안 잡힌다.
    운영 코드는 `from src.llm import openai_json`(src.db와 같은 형태) 하나로 통일한다."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for base in ("scripts", "src"):
        for path in (root / base).rglob("*.py"):
            if "src/llm" in path.as_posix() or path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if line.startswith(("from llm ", "import llm")):
                    offenders.append(f"{path.relative_to(root)}:{i}: {line.strip()}")
    assert not offenders, "짧은 경로 import가 섞여 있다:\n" + "\n".join(offenders)


def test_두_호출부가_같은_모듈_객체를_쓴다():
    assert audit.oj is mapping.oj
    assert audit.oj.OpenAICallError is oj.OpenAICallError
