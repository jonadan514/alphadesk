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
from datetime import date
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse, urlunparse

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Google News RSS는 공식 요율제한 문서가 없는 비공식에 가까운 엔드포인트다.
# 키워드별로 따로 검색하면 요청 수가 늘어나므로(테마당 키워드 수 x 8주 백필 시
# 수백 건), Phase 0의 yfinance 요율제한 사고를 반복하지 않기 위한 안전장치.
KEYWORD_SLEEP_SEC = 1.0

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
                         hl: str, gl: str, ceid: str, limit: int = 100) -> list[dict]:
    """단일 키워드로 Google News RSS 검색, after~before 날짜 범위로 제한한다
    (before는 배타적 - Google 검색 연산자 규칙).
    반환 필드: title, url, published_at('YYYY-MM-DD' 또는 ''), source."""
    query = f"{keyword} after:{after.isoformat()} before:{before.isoformat()}"
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []

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


def search_google_news_en(keyword: str, after: date, before: date, limit: int = 100) -> list[dict]:
    return _search_google_news(keyword, after, before, hl="en-US", gl="US", ceid="US:en", limit=limit)


def search_google_news_kr(keyword: str, after: date, before: date, limit: int = 100) -> list[dict]:
    return _search_google_news(keyword, after, before, hl="ko", gl="KR", ceid="KR:ko", limit=limit)


def collect_theme_news(keywords: list[str], after: date, before: date, market: str = "US") -> tuple[list[dict], dict]:
    """키워드별로 따로 검색 -> 합치기 -> URL 해시 중복 제거 -> 제목 정규화/유사도
    중복 제거. 반환: (중복 제거된 기사 목록 - 각 항목에 '_url_hash' 추가됨, 통계 dict)."""
    search_fn = search_google_news_kr if market == "KR" else search_google_news_en
    raw: list[dict] = []
    per_keyword_counts: dict[str, int] = {}
    for kw in keywords:
        articles = search_fn(kw, after, before)
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
    }
    return deduped, stats
