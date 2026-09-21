"""OpenAI Chat Completions JSON 호출 - 매핑·감사가 공용으로 쓴다 (작업지시서 Phase 4).

왜 한 곳으로 모았나
  매핑(경로 A·B·비판)은 429 재시도·o-시리즈 파라미터 처리가 있었지만 감사(판정·재질의)에는
  없었다 - 감사 모델을 o4-mini로 바꾸면 두 호출이 400으로 실패했을 것이다. 같은 규칙이 여러
  파일에 복제되면 한쪽만 고쳐진다. 재시도·모델 계열 차이·JSON 파싱은 여기서만 처리한다.

이 모듈이 하지 않는 것
  - API 제품을 바꾸지 않는다(Chat Completions 그대로, Responses API로 옮기지 않는다)
  - 프롬프트를 만들지 않는다 - 호출부가 넘긴 문자열을 그대로 보낸다
  - 실패를 삼키지 않는다 - 재시도를 다 써도 실패하면 OpenAICallError를 올린다.
    "실패하면 None" 같은 정책은 호출부가 정한다(매핑은 실패 횟수를 세어 계속 진행하고,
    감사는 그 테마를 '판정 호출 실패'로 표시한다).
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import requests
import yaml

ENDPOINT = "https://api.openai.com/v1/chat/completions"
MAX_ATTEMPTS = 6
DEFAULT_MODEL = "gpt-4o-mini"
MODELS_CONFIG = Path(__file__).resolve().parents[2] / "config" / "models.yaml"

# temperature를 받지 않고 max_tokens 대신 max_completion_tokens를 쓰는 모델 계열
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")
# 추론 모델은 눈에 보이지 않는 추론 토큰도 출력 한도에서 소모한다 - 같은 한도를 주면 답이 잘린다
_REASONING_TOKEN_FACTOR = 2


class OpenAICallError(RuntimeError):
    """재시도를 다 써도 호출이 실패했거나, 재시도해도 소용없는 오류(400 등)."""


def model_for(role: str, *, config_path: Path | None = None) -> str:
    """역할(theme_mapping / mapping_critic / mapping_audit / mapping_requote)의 모델 이름.

    우선순위: 환경변수 MODEL_<ROLE 대문자> > config/models.yaml > DEFAULT_MODEL.
    설정 파일이 없거나 깨져 있어도 기본 모델로 계속 동작한다.
    """
    env = os.environ.get(f"MODEL_{role.upper()}", "").strip()
    if env:
        return env
    try:
        data = yaml.safe_load((config_path or MODELS_CONFIG).read_text(encoding="utf-8")) or {}
        name = (data.get(role) or {}).get("model")
        if name:
            return str(name)
    except (OSError, yaml.YAMLError, AttributeError):
        pass
    return DEFAULT_MODEL


def is_reasoning_model(model: str) -> bool:
    return model.startswith(_REASONING_PREFIXES)


def build_payload(model: str, system_prompt: str, user_prompt: str, *,
                  max_output_tokens: int, temperature: float) -> dict:
    """모델 계열에 맞는 요청 본문."""
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
        "response_format": {"type": "json_object"},
    }
    if is_reasoning_model(model):
        body["max_completion_tokens"] = max_output_tokens * _REASONING_TOKEN_FACTOR
    else:
        body["temperature"] = temperature
        body["max_tokens"] = max_output_tokens
    return body


def _retry_wait(resp: requests.Response | None, attempt: int) -> float:
    """429·5xx 대기 시간. 서버가 알려주면 그 값(+1초), 아니면 지수 백오프(2,4,8,16,32초)에 지터."""
    if resp is not None:
        ra = resp.headers.get("retry-after")
        try:
            if ra:
                return min(float(ra) + 1, 60)
        except ValueError:
            pass
    return min(2 ** (attempt + 1), 32) + random.random()


def call_json(model: str, system_prompt: str, user_prompt: str, *, api_key: str,
              max_output_tokens: int = 2000, temperature: float = 0.2,
              timeout: float = 90) -> dict:
    """JSON 객체를 돌려주는 호출. 429·5xx·타임아웃·연결 오류는 MAX_ATTEMPTS까지 다시 부른다.

    실패하면 OpenAICallError. 응답이 JSON이 아니어도 실패로 본다.
    """
    body = build_payload(model, system_prompt, user_prompt,
                         max_output_tokens=max_output_tokens, temperature=temperature)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        resp = None
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=body, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
                time.sleep(_retry_wait(resp, attempt))
                continue
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        except (requests.Timeout, requests.ConnectionError) as e:
            last = type(e).__name__
            time.sleep(_retry_wait(None, attempt))
        except Exception as e:  # noqa: BLE001 - 400·파싱 오류는 다시 보내도 같은 결과다
            raise OpenAICallError(f"{type(e).__name__}: {e}") from e
    raise OpenAICallError(f"재시도 {MAX_ATTEMPTS}회 후에도 실패: {last}")
