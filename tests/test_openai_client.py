"""OpenAI JSON 호출 공통 모듈 (작업지시서 Phase 4).

매핑(경로 A·B·비판)과 감사(판정·인용 재질의)가 각자 갖고 있던 호출 코드를 한 곳으로 모은다.
모델 계열별 파라미터 차이(o-시리즈·gpt-5는 temperature 금지, max_completion_tokens 사용)와
429·5xx·타임아웃 재시도를 한 곳에서만 처리한다.
"""
from __future__ import annotations

import json

import pytest
import requests

from src.llm import openai_json as oj


class FakeResp:
    def __init__(self, status=200, content=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self._content)}}]}


@pytest.fixture
def http(monkeypatch):
    """requests.post를 가짜로 바꾼다. state["queue"]에 응답(또는 예외)을 순서대로 넣는다."""
    state = {"queue": [], "calls": [], "sleeps": []}

    def fake_post(url, headers=None, json=None, timeout=None):
        state["calls"].append({"url": url, "body": json, "timeout": timeout, "headers": headers})
        item = state["queue"].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(oj.requests, "post", fake_post)
    monkeypatch.setattr(oj.time, "sleep", lambda s: state["sleeps"].append(s))
    return state


# ── 모델 계열별 요청 형식 ─────────────────────────────────────

@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"])
def test_일반_모델은_temperature와_max_tokens를_쓴다(model):
    body = oj.build_payload(model, "sys", "usr", max_output_tokens=2000, temperature=0.2)
    assert body["temperature"] == 0.2 and body["max_tokens"] == 2000
    assert "max_completion_tokens" not in body


@pytest.mark.parametrize("model", ["o1-mini", "o3", "o4-mini", "gpt-5", "gpt-5-mini"])
def test_추론_모델은_temperature를_보내지_않고_max_completion_tokens를_쓴다(model):
    """이걸 그대로 보내면 400으로 거절당한다(2026-09-16 모델 A/B에서 겪음)."""
    body = oj.build_payload(model, "sys", "usr", max_output_tokens=2000, temperature=0.2)
    assert "temperature" not in body and "max_tokens" not in body
    assert body["max_completion_tokens"] >= 2000


def test_추론_모델은_추론_토큰_몫으로_출력_한도를_늘린다():
    body = oj.build_payload("o4-mini", "s", "u", max_output_tokens=2000, temperature=0.0)
    assert body["max_completion_tokens"] > 2000


def test_요청은_JSON_응답을_요구한다():
    body = oj.build_payload("gpt-4o-mini", "s", "u", max_output_tokens=100, temperature=0.0)
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


# ── 성공·재시도·실패 ──────────────────────────────────────────

def test_정상_응답을_JSON으로_돌려준다(http):
    http["queue"].append(FakeResp(200, {"members": []}))
    assert oj.call_json("gpt-4o-mini", "s", "u", api_key="k") == {"members": []}


def test_키를_Authorization_헤더로_보낸다(http):
    http["queue"].append(FakeResp(200, {}))
    oj.call_json("gpt-4o-mini", "s", "u", api_key="sk-test")
    assert http["calls"][0]["headers"]["Authorization"] == "Bearer sk-test"


def test_429는_기다렸다_다시_부른다(http):
    http["queue"] += [FakeResp(429), FakeResp(429), FakeResp(200, {"ok": 1})]
    assert oj.call_json("gpt-4o-mini", "s", "u", api_key="k") == {"ok": 1}
    assert len(http["calls"]) == 3 and len(http["sleeps"]) == 2


def test_5xx도_다시_부른다(http):
    http["queue"] += [FakeResp(503), FakeResp(200, {"ok": 1})]
    assert oj.call_json("gpt-4o-mini", "s", "u", api_key="k") == {"ok": 1}


def test_retry_after가_있으면_그_값을_따른다(http):
    http["queue"] += [FakeResp(429, headers={"retry-after": "7"}), FakeResp(200, {})]
    oj.call_json("gpt-4o-mini", "s", "u", api_key="k")
    assert http["sleeps"][0] == pytest.approx(8, abs=0.01)     # 7초 + 1초 여유


def test_타임아웃과_연결_오류도_다시_부른다(http):
    http["queue"] += [requests.Timeout(), requests.ConnectionError(), FakeResp(200, {"ok": 1})]
    assert oj.call_json("gpt-4o-mini", "s", "u", api_key="k") == {"ok": 1}


def test_재시도를_다_써도_실패하면_예외를_올린다(http):
    http["queue"] += [FakeResp(429)] * oj.MAX_ATTEMPTS
    with pytest.raises(oj.OpenAICallError):
        oj.call_json("gpt-4o-mini", "s", "u", api_key="k")
    assert len(http["calls"]) == oj.MAX_ATTEMPTS


def test_400은_재시도하지_않고_바로_실패한다(http):
    """요청 형식 오류는 다시 보내도 소용없다."""
    http["queue"] += [FakeResp(400)]
    with pytest.raises(oj.OpenAICallError):
        oj.call_json("gpt-4o-mini", "s", "u", api_key="k")
    assert len(http["calls"]) == 1


def test_JSON이_아닌_응답은_실패로_다룬다(http):
    class Bad(FakeResp):
        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}
    http["queue"] += [Bad(200)]
    with pytest.raises(oj.OpenAICallError):
        oj.call_json("gpt-4o-mini", "s", "u", api_key="k")


def test_호출별_타임아웃과_토큰_한도를_넘긴다(http):
    http["queue"].append(FakeResp(200, {}))
    oj.call_json("gpt-4o-mini", "s", "u", api_key="k", timeout=180, max_output_tokens=4000, temperature=0.0)
    call = http["calls"][0]
    assert call["timeout"] == 180 and call["body"]["max_tokens"] == 4000 and call["body"]["temperature"] == 0.0


# ── 모델 설정 ─────────────────────────────────────────────────

def test_역할별_모델을_설정에서_읽는다(tmp_path):
    cfg = tmp_path / "models.yaml"
    cfg.write_text("theme_mapping:\n  model: o4-mini\nmapping_audit:\n  model: gpt-4o-mini\n",
                   encoding="utf-8")
    assert oj.model_for("theme_mapping", config_path=cfg) == "o4-mini"
    assert oj.model_for("mapping_audit", config_path=cfg) == "gpt-4o-mini"


def test_설정에_없는_역할은_기본_모델을_쓴다(tmp_path):
    cfg = tmp_path / "models.yaml"
    cfg.write_text("theme_mapping:\n  model: o4-mini\n", encoding="utf-8")
    assert oj.model_for("mapping_requote", config_path=cfg) == oj.DEFAULT_MODEL


def test_설정_파일이_없어도_기본_모델을_쓴다(tmp_path):
    assert oj.model_for("theme_mapping", config_path=tmp_path / "none.yaml") == oj.DEFAULT_MODEL


def test_환경변수가_설정_파일보다_우선한다(tmp_path, monkeypatch):
    cfg = tmp_path / "models.yaml"
    cfg.write_text("theme_mapping:\n  model: gpt-4o-mini\n", encoding="utf-8")
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    assert oj.model_for("theme_mapping", config_path=cfg) == "o4-mini"


def test_매핑과_감사_모델을_따로_바꿀_수_있다(tmp_path, monkeypatch):
    """향후 실험: 매핑은 o4-mini, 감사는 gpt-4o-mini (또는 반대)."""
    cfg = tmp_path / "models.yaml"
    cfg.write_text("theme_mapping:\n  model: gpt-4o-mini\nmapping_audit:\n  model: gpt-4o-mini\n",
                   encoding="utf-8")
    monkeypatch.setenv("MODEL_THEME_MAPPING", "o4-mini")
    assert oj.model_for("theme_mapping", config_path=cfg) == "o4-mini"
    assert oj.model_for("mapping_audit", config_path=cfg) == "gpt-4o-mini"


def test_실제_설정_파일의_역할이_모두_현행_모델이다():
    """이번 작업은 모델 교체가 아니라 교체 가능한 구조까지다 - 기본값은 그대로 gpt-4o-mini."""
    for role in ("theme_mapping", "mapping_critic", "mapping_audit", "mapping_requote"):
        assert oj.model_for(role) == "gpt-4o-mini", role
