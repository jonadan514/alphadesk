"""분기 4칸 분류의 기준값을 읽는다 (docs/REDESIGN_SPEC.md 7장, config/quarterly.yaml).

설정 파일이 없거나 깨져 있어도 기본값으로 계속 동작한다 - 기준값을 못 읽었다고 테마를
탈락시키면 원칙 4(계산 불가는 탈락이 아니다)를 어긴다. 대신 어떤 값을 쓰는지 화면과
로그에 함께 남긴다.

기준값 자체를 코드에서 바꾸지 않는다(원칙 3). 바꿀 근거는 실측 분포에서 나온다:
`python scripts/report_quarterly_news.py`
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "quarterly.yaml"

# 설정을 못 읽을 때 쓰는 값. config/quarterly.yaml과 같게 유지한다.
DEFAULT_NEWS_HIGH = {"KR": 1.75, "US": 1.50, "default": 1.50}
DEFAULT_FINANCIAL_ON = {"change_ratio": 0.30, "min_changed": 2, "min_judged": 2}
DEFAULT_CHANGE_SIGNAL = {"revenue_transition_pct": 0.20, "revenue_flow_min_hits": 3}


def load(config_path: Path | None = None) -> dict:
    """{'news_high': {...}, 'financial_on': {...}, 'change_signal': {...}}.
    빠진 항목은 기본값으로 채운다."""
    news = dict(DEFAULT_NEWS_HIGH)
    financial = dict(DEFAULT_FINANCIAL_ON)
    change = dict(DEFAULT_CHANGE_SIGNAL)
    try:
        data = yaml.safe_load((config_path or CONFIG_PATH).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"news_high": news, "financial_on": financial, "change_signal": change}
    if isinstance(data.get("news_high"), dict):
        news.update({k: float(v) for k, v in data["news_high"].items()
                     if isinstance(v, (int, float))})
    if isinstance(data.get("financial_on"), dict):
        financial.update({k: v for k, v in data["financial_on"].items()
                          if isinstance(v, (int, float))})
    if isinstance(data.get("change_signal"), dict):
        change.update({k: v for k, v in data["change_signal"].items()
                       if isinstance(v, (int, float))})
    return {"news_high": news, "financial_on": financial, "change_signal": change}


def news_high_threshold(market: str, config: dict | None = None) -> float:
    """그 시장의 뉴스 '많음' 기준. 시장별로 다르다 - 이유는 config/quarterly.yaml 참고."""
    news = (config or load())["news_high"]
    return float(news.get(market, news.get("default", DEFAULT_NEWS_HIGH["default"])))


def is_news_high(ratio: float | None, market: str, config: dict | None = None) -> bool | None:
    """뉴스가 '많음'인가. 비율이 없으면(데이터부족) None - 적음(False)이 아니다."""
    if ratio is None:
        return None
    return ratio >= news_high_threshold(market, config)


def revenue_transition_pct(config: dict | None = None) -> float:
    """매출 전환 기준 배수 (5-1). 기본 0.20 - 1년 전 같은 분기보다 20% 이상 늘어야 통과."""
    return float((config or load())["change_signal"]["revenue_transition_pct"])


def revenue_flow_min_hits(config: dict | None = None) -> int:
    """매출 흐름 기준 (5-1). 5분기 중 직전 분기 대비 증가 4번 중 이 값 이상이면 통과."""
    return int((config or load())["change_signal"]["revenue_flow_min_hits"])
