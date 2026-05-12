"""
주간 뉴스 수집 스크립트 — RSS 기반
Usage: python scripts/fetch_news.py
       python scripts/fetch_news.py --days 14   # 최근 14일치 재수집
       python scripts/fetch_news.py --no-translate
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("feedparser가 없습니다. 설치: pip install feedparser")
    sys.exit(1)

ROOT    = Path(__file__).parents[1]
DB_PATH = ROOT / "output" / "data.db"

# ── RSS 피드 목록 ──────────────────────────────────────────────────────────────
FEEDS = [
    # 미국
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/",              "source": "MarketWatch",  "market": "US"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",              "source": "CNBC",         "market": "US"},
    {"url": "https://www.cnbc.com/id/20910258/device/rss/rss.html",               "source": "CNBC Tech",    "market": "US"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                      "source": "WSJ Markets",  "market": "US"},
    {"url": "https://rss.cnn.com/rss/money_news_international.rss",               "source": "CNN Money",    "market": "US"},
    {"url": "https://www.investing.com/rss/news_25.rss",                           "source": "Investing.com","market": "US"},
    # 한국
    {"url": "https://rss.hankyung.com/economy.xml",                                "source": "한국경제",     "market": "KR"},
    {"url": "https://www.mk.co.kr/rss/40300001/",                                  "source": "매일경제",     "market": "KR"},
    {"url": "https://biz.chosun.com/arc/outboundfeeds/rss/category/stock/",        "source": "조선비즈",     "market": "KR"},
]

# ── 섹터 분류 키워드 ───────────────────────────────────────────────────────────
SECTOR_RULES = [
    ("AI·반도체", ["nvidia", "nvda", "semiconductor", "chip", "ai ", "artificial intelligence",
                   "arm ", "tsmc", "amd", "intel", "반도체", "엔비디아", "인공지능"]),
    ("빅테크",    ["apple", "google", "alphabet", "microsoft", "meta", "amazon", "tesla",
                   "aapl", "msft", "googl", "amzn", "삼성전자", "sk하이닉스"]),
    ("거시경제",  ["fed", "federal reserve", "interest rate", "inflation", "cpi", "gdp",
                   "recession", "treasury", "bond yield", "기준금리", "물가", "경기", "금리"]),
    ("에너지",    ["oil", "crude", "opec", "energy", "petroleum", "lng", "원유", "에너지"]),
    ("금융",      ["bank", "banking", "jpmorgan", "goldman", "finance", "earnings",
                   "은행", "금융", "실적"]),
    ("헬스케어",  ["pharma", "biotech", "fda", "drug", "clinical", "vaccine",
                   "제약", "바이오", "헬스케어"]),
    ("무역·지정학",["china", "tariff", "trade war", "sanction", "geopolit",
                   "중국", "관세", "무역", "지정학"]),
]

def classify_sector(title: str) -> str:
    t = title.lower()
    for sector, keywords in SECTOR_RULES:
        if any(k in t for k in keywords):
            return sector
    return "일반"

def parse_published(entry) -> str | None:
    """RSS entry에서 발행일 추출 → ISO 문자열"""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt = datetime(*val[:6], tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            dt = parsedate_to_datetime(raw).astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return None

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            title_ko     TEXT,
            url          TEXT    NOT NULL UNIQUE,
            source       TEXT,
            market       TEXT,
            sector       TEXT,
            published_at TEXT,
            fetched_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
        )
    """)
    # 기존 DB에 title_ko 컬럼이 없을 경우 추가
    try:
        conn.execute("ALTER TABLE news_items ADD COLUMN title_ko TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 존재
    conn.commit()

def fetch_feed(feed_meta: dict, cutoff: datetime) -> list[dict]:
    url = feed_meta["url"]
    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        print(f"  [오류] {url}: {e}")
        return []

    items = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "").strip()
        link  = getattr(entry, "link",  "").strip()
        if not title or not link:
            continue

        pub = parse_published(entry)
        if pub:
            try:
                dt = datetime.strptime(pub, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except ValueError:
                pass

        items.append({
            "title":        title,
            "url":          link,
            "source":       feed_meta["source"],
            "market":       feed_meta["market"],
            "sector":       classify_sector(title),
            "published_at": pub,
        })
    return items

def translate_titles(titles: list[str]) -> list[str | None]:
    """Google 번역 무료 API로 제목 일괄 번역 (deep-translator)"""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("  [번역] deep-translator 없음. 설치: pip install deep-translator")
        return [None] * len(titles)

    translator = GoogleTranslator(source="auto", target="ko")
    results: list[str | None] = []
    for title in titles:
        try:
            translated = translator.translate(title)
            results.append(translated)
            time.sleep(0.15)  # rate limit 방지
        except Exception:
            results.append(None)
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="최근 N일치 수집 (기본 7)")
    parser.add_argument("--no-translate", action="store_true", help="번역 건너뜀")
    args = parser.parse_args()

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)

    total_new = 0
    for meta in FEEDS:
        print(f"  수집 중: {meta['source']} ({meta['market']}) ...", end=" ", flush=True)
        items = fetch_feed(meta, cutoff)

        # US 뉴스만 번역
        if not args.no_translate and meta["market"] == "US" and items:
            print(f"{len(items)}개 번역 중...", end=" ", flush=True)
            translated = translate_titles([i["title"] for i in items])
            for item, ko in zip(items, translated):
                item["title_ko"] = ko
        else:
            for item in items:
                item["title_ko"] = None

        inserted = 0
        for item in items:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO news_items (title, title_ko, url, source, market, sector, published_at) VALUES (?,?,?,?,?,?,?)",
                    (item["title"], item.get("title_ko"), item["url"], item["source"], item["market"], item["sector"], item["published_at"]),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except sqlite3.Error:
                pass
        conn.commit()
        print(f"{len(items)}개 확인 / {inserted}개 신규")
        total_new += inserted
        time.sleep(0.5)

    # 오래된 기사 정리 (30일 초과)
    conn.execute("""
        DELETE FROM news_items
        WHERE fetched_at < strftime('%Y-%m-%d %H:%M', 'now', '-30 days', 'localtime')
    """)
    conn.commit()
    conn.close()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n완료 [{now}] — 신규 {total_new}개 저장")

if __name__ == "__main__":
    main()
