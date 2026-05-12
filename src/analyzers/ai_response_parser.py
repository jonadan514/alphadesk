import json
import re

REQUIRED_FIELDS = {
    "thesis":         str,
    "catalysts":      list,
    "bear_cases":     list,
    "recommendation": str,
    "confidence":     (int, float),
}

FALLBACK: dict = {
    "thesis":         "분석 데이터 부족으로 AI 요약을 생성하지 못했습니다.",
    "catalysts":      [],
    "bear_cases":     [],
    "recommendation": "HOLD",
    "confidence":     0,
    "_fallback":      True,
}


def _extract_json(text: str) -> str:
    """Extract first {...} block from text, handling markdown code fences."""
    # strip ```json ... ``` fences
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    # bare JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _validate(data: dict) -> dict:
    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"missing field: {field}")
            continue
        if not isinstance(data[field], expected_type):
            errors.append(f"{field} wrong type: expected {expected_type}, got {type(data[field])}")

    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)) and not (0 <= confidence <= 100):
        errors.append(f"confidence out of range: {confidence}")

    if errors:
        raise ValueError("; ".join(errors))
    return data


def parse_ai_response(text: str) -> dict:
    if not text or not text.strip():
        return {**FALLBACK, "_reason": "empty response"}

    try:
        raw = _extract_json(text)
        data = json.loads(raw)
        return _validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[ai_response_parser] parse failed: {exc}")
        return {**FALLBACK, "_reason": str(exc)}
