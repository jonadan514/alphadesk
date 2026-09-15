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
