"""KR 기업 사업정보(산업분류·사업요약) 로더.

테마 매핑(scripts/map_theme_companies.py)과 근거 감사(scripts/audit_mapping_evidence.py)가
반드시 같은 값을 보도록 한 곳에서 읽는다. 둘이 다른 정보를 보면, 매핑이 틀린 라벨에
속아 만든 편입을 감사도 같은 라벨에 속아 통과시키거나(2026-09-15 SK오션플랜트 사례),
반대로 한쪽만 보정돼 판정이 엇갈린다.

data/kr_profiles.json          yfinance에서 받은 원본 (scripts/fetch_kr_profiles.py)
data/kr_profile_overrides.json 원본 industry가 틀린 종목의 보정값
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "kr_profiles.json"
OVERRIDES = ROOT / "data" / "kr_profile_overrides.json"


# 출처를 필드별로 기록하는 대상. 각 필드의 출처는 "<필드>_source"에 남긴다
# ("dart" | "yfinance" | "override"). 기존 kr_profile_overrides.json이 이미
# industry_source="override"를 쓰고 있어 같은 규칙을 따른다.
FIELD_SOURCE_KEYS = ("industry", "summary", "summary_long")


def backfill_field_sources(rec: dict) -> dict:
    """출처가 안 적힌 기존 값에 출처를 채운다(원본은 바꾸지 않고 새 dict를 돌려준다).

    옛 데이터는 전부 yfinance에서 왔고, 예외는 DART로 보강한 종목뿐이다. 옛 형식에서는
    레코드 전체에 source="dart" 하나만 있었으므로 필드별로 이렇게 가른다.
      industry : industry_code가 있으면 DART가 채운 것, 없으면 yfinance 원본
      summary  : source="dart"인 레코드면 DART가 채운 것(DART 보강은 요약이 비어 있을 때만 쓴다)
    값이 없는 필드에는 출처를 만들지 않는다. 이미 출처가 있으면 바꾸지 않는다.
    """
    out = dict(rec)
    legacy_dart = rec.get("source") == "dart"
    for key in FIELD_SOURCE_KEYS:
        src_key = f"{key}_source"
        if not rec.get(key) or rec.get(src_key):
            continue
        if key == "industry":
            out[src_key] = "dart" if rec.get("industry_code") else "yfinance"
        else:
            out[src_key] = "dart" if legacy_dart else "yfinance"
    return out


def load_kr_profiles() -> dict[str, dict]:
    if not PROFILES.exists():
        return {}
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    if OVERRIDES.exists():
        ov = json.loads(OVERRIDES.read_text(encoding="utf-8")).get("industry", {})
        for code, fix in ov.items():
            if code in profiles and fix.get("industry"):
                profiles[code] = {**profiles[code], "industry": fix["industry"],
                                  "industry_source": "override"}
    return profiles


US_PROFILES = ROOT / "data" / "us_profiles.json"


def load_profiles(market: str) -> dict[str, dict]:
    """시장별 사업정보. KR은 산업분류 보정 포함, US는 yfinance 원본(scripts/fetch_us_profiles.py).

    매핑 프롬프트는 KR에만 사업정보를 붙이지만(미국 기업은 모델이 사명으로 안다),
    근거 감사는 양쪽 다 실제 사업정보와 대조해야 한다 - US에 정보가 없으면 거의 전부
    '확인 불가'가 돼 감사가 무의미하다(2026-09-15 신규 테마 US 26건 중 21건).
    """
    if market == "US":
        if not US_PROFILES.exists():
            return {}
        return json.loads(US_PROFILES.read_text(encoding="utf-8"))
    return load_kr_profiles()
