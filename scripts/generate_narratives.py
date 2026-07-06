"""워치리스트 네러티브 브리프 생성 — 일간 파이프라인에서 실행.

워치리스트 후보 + 내 워치리스트 종목별로:
  1. 최근 7일 뉴스 헤드라인 수집 (Yahoo/Google News RSS, KR은 한국어 검색)
  2. GPT-4o mini가 투자 스토리·촉매·리스크·시장 관심도를 JSON으로 요약
  3. Turso narrative_briefs 테이블에 upsert (프론트엔드가 읽음)

사용:
  python scripts/generate_narratives.py                  # 기본 (20시간 내 갱신분은 건너뜀)
  python scripts/generate_narratives.py --force          # 전부 재생성
  python scripts/generate_narratives.py --limit 5        # 테스트용
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_AGE_HOURS = 20          # 이보다 최신인 브리프는 건너뜀 (하루 2회 크론 대비)
OPENAI_MODEL = "gpt-4o-mini"


# ── Turso (Hrana v2 HTTP) ──────────────────────────────────────────────────

def _turso_base():
    url = os.environ.get("TURSO_DATA_URL", "").replace("libsql://", "https://")
    token = os.environ.get("TURSO_DATA_TOKEN", "")
    if not url or not token:
        logger.error("TURSO_DATA_URL / TURSO_DATA_TOKEN 미설정")
        sys.exit(1)
    return url, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _turso_val(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def turso_pipeline(statements: list[dict]) -> list:
    """execute 문 리스트를 한 번에 전송, 결과 리스트 반환."""
    url, headers = _turso_base()
    body = json.dumps({"requests": statements}).encode()
    req = urllib.request.Request(f"{url}/v2/pipeline", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read()).get("results", [])


def turso_query(sql: str, args: list | None = None) -> list[dict]:
    """SELECT 실행 후 dict 행 리스트 반환."""
    stmt = {"type": "execute", "stmt": {"sql": sql}}
    if args:
        stmt["stmt"]["args"] = [_turso_val(a) for a in args]
    results = turso_pipeline([stmt])
    if not results or results[0].get("type") != "ok":
        return []
    result = results[0]["response"]["result"]
    cols = [c["name"] for c in result.get("cols", [])]
    rows = []
    for raw in result.get("rows", []):
        row = {}
        for col, cell in zip(cols, raw):
            row[col] = cell.get("value") if isinstance(cell, dict) else cell
        rows.append(row)
    return rows


# ── 뉴스 수집 ───────────────────────────────────────────────────────────────

def collect_news(market: str, symbol: str, name: str | None) -> list[dict]:
    if market == "KR":
        return _google_news_kr(name or symbol)
    from src.analyzers.ai_summary_generator import NewsCollector
    return NewsCollector().get_news_for_ticker(symbol, name)


def _google_news_kr(name: str, limit: int = 6) -> list[dict]:
    """한국 종목: 구글 뉴스 한국어 RSS 검색."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from urllib.parse import quote

    try:
        query = f'"{name}" 주가 OR 실적'
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        results = []
        for item in root.iter("item"):
            if len(results) >= limit:
                break
            pub_date = ""
            pub_el = item.find("pubDate")
            if pub_el is not None and pub_el.text:
                try:
                    dt = parsedate_to_datetime(pub_el.text)
                    if dt < cutoff:
                        continue
                    pub_date = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    pass
            title_el = item.find("title")
            link_el = item.find("link")
            source_el = item.find("source")
            results.append({
                "title": title_el.text if title_el is not None else "",
                "publisher": source_el.text if source_el is not None else "",
                "link": link_el.text if link_el is not None else "",
                "published": pub_date,
                "source": "GoogleKR",
            })
        return results
    except Exception:
        logger.debug("%s KR 뉴스 수집 실패", name, exc_info=True)
        return []


# ── GPT-4o mini 네러티브 생성 ───────────────────────────────────────────────

NO_NEWS_BRIEF = {
    "story": "최근 1주일간 주요 뉴스가 수집되지 않았습니다. 시장의 관심 밖에 있는 시기일 수 있습니다.",
    "catalysts": [],
    "risks": [],
    "sentiment": "COLD",
    "sentiment_reason": "최근 7일 뉴스 없음",
}


def generate_brief(market: str, symbol: str, name: str | None, news: list[dict]) -> dict | None:
    """뉴스 헤드라인 기반 네러티브 JSON 생성. 실패 시 None."""
    if not news:
        return {**NO_NEWS_BRIEF, "sources": []}

    import requests

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY 미설정")
        sys.exit(1)

    headlines = "\n".join(
        f"- [{n.get('published','?')}] {n.get('title','')} ({n.get('publisher','')})"
        for n in news
    )
    market_label = "한국(KOSPI/KOSDAQ)" if market == "KR" else "미국(NYSE/NASDAQ)"
    prompt = f"""종목: {name or symbol} (티커/코드: {symbol}, {market_label} 상장)

아래는 이 종목의 최근 1주일 뉴스 헤드라인입니다:
{headlines}

이 헤드라인들을 바탕으로 현재 시장에서 이 종목에 형성된 투자 네러티브(스토리)를 분석해 아래 JSON 형식으로만 답하세요. 헤드라인에 없는 내용을 지어내지 마세요.

{{
  "story": "핵심 투자 스토리 2~3문장 — 시장이 왜 이 종목에 관심을 갖는지(또는 안 갖는지)",
  "catalysts": ["다가오는 촉매 최대 3개 (실적발표·신제품·정책·계약 등)"],
  "risks": ["이 스토리가 깨질 수 있는 리스크 최대 3개"],
  "sentiment": "HOT 또는 WARM 또는 COLD",
  "sentiment_reason": "시장 관심도 판단 근거 한 문장"
}}

sentiment 기준: HOT=뉴스가 많고 시장이 활발히 이야기하는 인기 테마, WARM=꾸준한 관심, COLD=뉴스가 적거나 관심 밖. 모든 내용은 한국어로 작성하세요."""

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "당신은 주식 시장 네러티브 분석가입니다. 반드시 유효한 JSON만 출력합니다."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 700,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        if not isinstance(parsed.get("story"), str):
            return None
        sentiment = parsed.get("sentiment", "WARM")
        if sentiment not in ("HOT", "WARM", "COLD"):
            sentiment = "WARM"
        return {
            "story": parsed["story"],
            "catalysts": (parsed.get("catalysts") or [])[:3],
            "risks": (parsed.get("risks") or [])[:3],
            "sentiment": sentiment,
            "sentiment_reason": parsed.get("sentiment_reason", ""),
            "sources": [n["link"] for n in news if n.get("link")][:5],
        }
    except Exception as e:
        logger.warning("%s GPT 요약 실패: %s", symbol, type(e).__name__)
        return None


# ── main ───────────────────────────────────────────────────────────────────

CREATE_SQL = (
    "CREATE TABLE IF NOT EXISTS narrative_briefs ("
    "  market TEXT NOT NULL,"
    "  symbol TEXT NOT NULL,"
    "  payload TEXT NOT NULL,"
    "  updated_at TEXT NOT NULL DEFAULT (datetime('now')),"
    "  PRIMARY KEY (market, symbol)"
    ")"
)

UPSERT_SQL = (
    "INSERT INTO narrative_briefs (market, symbol, payload, updated_at) "
    "VALUES (?, ?, ?, datetime('now')) "
    "ON CONFLICT(market, symbol) DO UPDATE SET "
    "payload=excluded.payload, updated_at=excluded.updated_at"
)


def get_targets() -> list[dict]:
    """내 워치리스트(우선) + 스크리닝 후보 종목 목록. (market, symbol, name)"""
    targets: dict[str, dict] = {}
    for row in turso_query("SELECT market, symbol, name FROM my_watchlist"):
        targets[f"{row['market']}:{row['symbol']}"] = row
    for row in turso_query("SELECT market, symbol, name FROM watchlist_candidates"):
        targets.setdefault(f"{row['market']}:{row['symbol']}", row)
    return list(targets.values())


def get_fresh_symbols(max_age_hours: int) -> set[str]:
    rows = turso_query(
        f"SELECT market, symbol FROM narrative_briefs "
        f"WHERE updated_at > datetime('now', '-{int(max_age_hours)} hours')"
    )
    return {f"{r['market']}:{r['symbol']}" for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="워치리스트 네러티브 브리프 생성")
    parser.add_argument("--limit", type=int, default=0, help="처리 종목 수 제한 (0=전체)")
    parser.add_argument("--force", action="store_true", help="신선도 무시하고 전부 재생성")
    args = parser.parse_args()

    t0 = time.time()
    turso_pipeline([{"type": "execute", "stmt": {"sql": CREATE_SQL}}])

    targets = get_targets()
    if not targets:
        logger.warning("대상 종목 없음 (my_watchlist / watchlist_candidates 비어 있음)")
        return

    fresh = set() if args.force else get_fresh_symbols(MAX_AGE_HOURS)
    todo = [t for t in targets if f"{t['market']}:{t['symbol']}" not in fresh]
    if args.limit > 0:
        todo = todo[: args.limit]

    logger.info("대상 %d종목 중 %d종목 생성 (신선한 %d종목 건너뜀)",
                len(targets), len(todo), len(targets) - len(todo))

    ok = fail = 0
    for i, t in enumerate(todo, 1):
        market, symbol, name = t["market"], t["symbol"], t.get("name")
        news = collect_news(market, symbol, name)
        brief = generate_brief(market, symbol, name, news)
        if brief is None:
            fail += 1
            continue
        turso_pipeline([{
            "type": "execute",
            "stmt": {
                "sql": UPSERT_SQL,
                "args": [_turso_val(market), _turso_val(symbol),
                         _turso_val(json.dumps(brief, ensure_ascii=False))],
            },
        }])
        ok += 1
        logger.info("[%d/%d] %s(%s) %s 뉴스%d건", i, len(todo), symbol, market,
                    brief["sentiment"], len(news))
        time.sleep(0.3)  # API 예의

    logger.info("완료: 성공 %d / 실패 %d / 소요 %.1f초", ok, fail, time.time() - t0)


if __name__ == "__main__":
    main()
