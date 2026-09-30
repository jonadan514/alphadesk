"""Phase A-3/B-1: 테마 키워드 기반 뉴스 수집 (Google News RSS).

SPEC: docs/radar/SPEC_phase_a_signals.md §2
Phase A는 미국 시장만 대상이었으나(keywords_en), Phase B에서 한국어 검색
(keywords_ko)을 추가한다 - normalize_title()이 애초에 한글 범위(가-힣)를
포함하고 있어 이 확장을 이미 염두에 두고 설계돼 있었다.

키워드별로 따로 검색해서 합친 뒤 중복 제거한다(§3 논의에서 정한 "옵션 B") -
어떤 키워드가 건수를 과도하게 밀어올리는지 나중에 진단할 수 있어야 하기 때문
(SPEC §8 "특정 테마만 계속 up2 -> 키워드가 너무 넓음" 진단과 직결).
"""
from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse, urlunparse

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Google News RSS는 공식 요율제한 문서가 없는 비공식에 가까운 엔드포인트다.
# 키워드별로 따로 검색하면 요청 수가 늘어나므로(테마당 키워드 수 x 8주 백필 시
# 수백 건), Phase 0의 yfinance 요율제한 사고를 반복하지 않기 위한 안전장치.
KEYWORD_SLEEP_SEC = 1.0

# Google News RSS는 한 요청에 최대 100건만 준다 - 2026-09-17 실측: &num=200을 붙여도,
# 기간을 하루로 좁히거나 분기로 넓혀도 똑같이 100건이 상한이다. 즉 인기 키워드는 실제
# 기사가 몇 백 건이든 100건으로 잘려 세어진다(주간 실행에서 키워드-주 조합의 16%가 상한).
# 대응: 한 주 조회가 상한에 닿으면 그 키워드만 하루 단위로 다시 세어 합친다(최대 700건).
# 키워드를 바꾸지 않으므로 과거 기간과 비교가 끊기지 않는다.
RESULT_LIMIT = 100
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SEC = [5, 15]

# SPEC §2.2 4번(제목 유사도 90%+)은 "구현 부담되면 생략 가능"이라고 돼 있지만
# stdlib difflib라 새 의존성 없이 가능해서 포함함.
TITLE_SIMILARITY_THRESHOLD = 0.90


def normalize_url(url: str) -> str:
    """쿼리스트링(트래킹 파라미터) 제거."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def hash_url(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]


def normalize_title(title: str) -> str:
    """특수문자를 공백으로 치환(삭제 아님 - "AI-powered"가 "aipowered"로
    붙어버리면 다른 매체의 "AI powered"와 안 맞아 중복 탐지가 깨진다),
    공백 정리, 소문자화."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9가-힣]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _search_google_news(keyword: str, after: date, before: date, *,
                         hl: str, gl: str, ceid: str, limit: int = RESULT_LIMIT) -> list[dict]:
    """단일 키워드로 Google News RSS 검색, after~before 날짜 범위로 제한한다
    (before는 배타적 - Google 검색 연산자 규칙).
    반환 필드: title, url, published_at('YYYY-MM-DD' 또는 ''), source."""
    query = f"{keyword} after:{after.isoformat()} before:{before.isoformat()}"
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    # 예전에는 실패하면 조용히 빈 목록을 돌려줬다. 그러면 "기사 0건"과 "조회 실패"가
    # 구별되지 않아, 일시적 오류가 그 주의 기사 수를 0으로 기록해버린다(백필에서는 그 값이
    # 기준선에 그대로 남는다). 이제 재시도하고, 끝내 실패하면 예외를 올려 호출부가 표시하게 한다.
    root = None
    last_err: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            break
        except Exception as e:  # noqa: BLE001 - 네트워크·파싱 실패를 같이 다룬다
            last_err = e
            if attempt < len(FETCH_BACKOFF_SEC):
                time.sleep(FETCH_BACKOFF_SEC[attempt])
    if root is None:
        raise RuntimeError(f"뉴스 조회 실패({keyword} {after}~{before}): {type(last_err).__name__}")

    results = []
    for item in root.iter("item"):
        if len(results) >= limit:
            break
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None or not link_el.text:
            continue
        pub_el = item.find("pubDate")
        published_at = ""
        if pub_el is not None and pub_el.text:
            try:
                published_at = parsedate_to_datetime(pub_el.text).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        source_el = item.find("source")
        results.append({
            "title": title_el.text or "",
            "url": link_el.text,
            "published_at": published_at,
            "source": source_el.text if source_el is not None else "",
        })
    return results


def search_google_news_en(keyword: str, after: date, before: date, limit: int = RESULT_LIMIT) -> list[dict]:
    return _search_google_news(keyword, after, before, hl="en-US", gl="US", ceid="US:en", limit=limit)


def search_google_news_kr(keyword: str, after: date, before: date, limit: int = RESULT_LIMIT) -> list[dict]:
    return _search_google_news(keyword, after, before, hl="ko", gl="KR", ceid="KR:ko", limit=limit)


def _collect_by_day(search_fn, keyword: str, after: date, before: date
                     ) -> tuple[list[dict], list[str], list[str]]:
    """상한에 걸린 키워드를 하루씩 나눠 다시 센다. (기사, 상한에 또 닿은 날, 실패한 날)."""
    articles: list[dict] = []
    saturated_days: list[str] = []
    failed_days: list[str] = []
    day = after
    while day < before:
        try:
            got = search_fn(keyword, day, day + timedelta(days=1))
        except Exception as e:  # noqa: BLE001
            failed_days.append(f"{keyword}@{day.isoformat()}: {type(e).__name__}")
            day += timedelta(days=1)
            time.sleep(KEYWORD_SLEEP_SEC)
            continue
        if len(got) >= RESULT_LIMIT:
            saturated_days.append(day.isoformat())
        articles.extend(got)
        day += timedelta(days=1)
        time.sleep(KEYWORD_SLEEP_SEC)
    return articles, saturated_days, failed_days


def collect_theme_news(keywords: list[str], after: date, before: date, market: str = "US",
                        expand_saturated: bool = True) -> tuple[list[dict], dict]:
    """키워드별로 따로 검색 -> 합치기 -> URL 해시 중복 제거 -> 제목 정규화/유사도
    중복 제거. 반환: (중복 제거된 기사 목록 - 각 항목에 '_url_hash' 추가됨, 통계 dict).

    expand_saturated: 한 키워드가 상한(100건)에 닿으면 그 기간을 하루씩 나눠 다시 세어
    합친다. 상한 때문에 인기 테마의 기사 수가 눌리는 것을 막는다. 하루로 나눠도 상한에
    닿는 키워드는 stats['saturated_keywords']에 남는다 - 그 주의 수치는 실제보다 작다는
    뜻이므로, 쓰는 쪽에서 데이터부족으로 다룰지 판단한다.
    """
    search_fn = search_google_news_kr if market == "KR" else search_google_news_en
    raw: list[dict] = []
    per_keyword_counts: dict[str, int] = {}
    saturated: list[str] = []
    expanded: list[str] = []
    failed: list[str] = []

    for kw in keywords:
        try:
            articles = search_fn(kw, after, before)
        except Exception as e:  # noqa: BLE001 - 조회 실패는 0건과 구별해서 기록한다
            failed.append(f"{kw}: {type(e).__name__}")
            per_keyword_counts[kw] = 0
            time.sleep(KEYWORD_SLEEP_SEC)
            continue

        if expand_saturated and len(articles) >= RESULT_LIMIT and (before - after).days > 1:
            day_articles, day_saturated, day_failed = _collect_by_day(search_fn, kw, after, before)
            if day_failed:
                failed.extend(day_failed)
            # 하루 단위 합이 더 적게 나오는 경우(조회 실패 등)는 원래 결과를 쓴다.
            if len(day_articles) >= len(articles):
                articles = day_articles
                expanded.append(kw)
            if day_saturated:
                saturated.append(kw)
        elif len(articles) >= RESULT_LIMIT:
            saturated.append(kw)

        per_keyword_counts[kw] = len(articles)
        raw.extend(articles)
        time.sleep(KEYWORD_SLEEP_SEC)

    seen_hashes: set[str] = set()
    by_url: list[dict] = []
    for a in raw:
        h = hash_url(a["url"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        a["_url_hash"] = h
        by_url.append(a)

    deduped: list[dict] = []
    seen_norm_titles: list[str] = []
    for a in by_url:
        norm = normalize_title(a["title"])
        is_dup = norm in seen_norm_titles or any(
            _title_similarity(norm, s) >= TITLE_SIMILARITY_THRESHOLD for s in seen_norm_titles
        )
        if is_dup:
            continue
        seen_norm_titles.append(norm)
        deduped.append(a)

    stats = {
        "per_keyword": per_keyword_counts,
        "raw_total": len(raw),
        "after_url_dedup": len(by_url),
        "after_title_dedup": len(deduped),
        "saturated_keywords": saturated,   # 하루로 나눠도 상한 - 실제보다 적게 세어진 키워드
        "expanded_keywords": expanded,     # 상한에 걸려 하루 단위로 다시 센 키워드
        "failed_keywords": failed,         # 조회 자체가 실패한 키워드(0건과 구별)
    }
    return deduped, stats
