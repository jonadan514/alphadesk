"""주간 분석 완료 후 텔레그램으로 핵심 신호를 요약 발송.

Usage:
  python scripts/send_telegram_digest.py

필요 secrets (없으면 조용히 건너뜀 — 파이프라인을 막지 않음):
  TELEGRAM_BOT_TOKEN   BotFather에서 발급받은 봇 토큰
  TELEGRAM_CHAT_ID     알림 받을 채팅방 ID (개인 DM이면 본인 user id)

봇 만드는 법:
  1. 텔레그램에서 @BotFather 검색 → /newbot → 토큰 발급
  2. 만든 봇과 대화 시작(아무 메시지나 전송) 후,
     https://api.telegram.org/bot<TOKEN>/getUpdates 접속해 chat.id 확인
  3. GitHub secrets에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 등록
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.turso_http import get_credentials, query as _turso_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENTIMENT_KO = {"HOT": "🔥HOT", "WARM": "🌤WARM", "COLD": "❄️COLD"}


# ── Turso (Hrana v2 HTTP) — 다른 스크립트들과 동일한 패턴 ──────────────────

def _require_turso() -> None:
    if not get_credentials():
        logger.error("TURSO_DATA_URL / TURSO_DATA_TOKEN 미설정")
        sys.exit(1)


def turso_query(sql: str, args: list | None = None) -> list[dict]:
    _require_turso()
    try:
        return _turso_query(sql, args)
    except Exception as e:
        logger.warning("Turso 조회 실패 (%s): %s", sql[:40], type(e).__name__)
        return []


def get_latest_timeseries(table: str) -> dict:
    rows = turso_query(f"SELECT payload FROM {table} ORDER BY date DESC LIMIT 1")
    if not rows:
        return {}
    try:
        return json.loads(rows[0]["payload"])
    except Exception:
        return {}


# ── 데이터 수집 ──────────────────────────────────────────────────────────────

def disp(market: str, symbol: str, name: str | None = None) -> str:
    """표시용 라벨 — KR은 코드 대신 종목명(있으면), US는 티커."""
    flag = "🇰🇷" if market == "KR" else "🇺🇸"
    label = (name or symbol) if market == "KR" else symbol
    return f"{flag} {label}"


def get_narrative_shifts() -> list[str]:
    # 주 1회 실행에 맞춰 지난 7일 갱신분을 본다 (narratives 배치도 주 1회 실행됨)
    rows = turso_query(
        "SELECT market, symbol, payload FROM narrative_briefs "
        "WHERE updated_at > datetime('now', '-7 days')"
    )
    lines = []
    for r in rows:
        try:
            payload = json.loads(r["payload"])
        except Exception:
            continue
        if payload.get("trend") == "up":
            label = disp(r["market"], r["symbol"], payload.get("name"))
            lines.append(
                f"📈 {label} {payload.get('prev_sentiment','?')}"
                f"→{payload.get('sentiment','?')}"
            )
    return lines


def get_cross_hits() -> list[str]:
    """내 워치리스트 중 이번 주 재무 필터 통과 후보 목록에 새로 등장한 종목."""
    my_watch = {f"{r['market']}:{r['symbol']}": r.get("name")
                for r in turso_query("SELECT market, symbol, name FROM my_watchlist")}
    if not my_watch:
        return []

    hits = []
    for c in turso_query("SELECT market, symbol, name FROM watchlist_candidates"):
        key = f"{c['market']}:{c['symbol']}"
        if key in my_watch:
            name = c.get("name") or my_watch.get(key)
            hits.append(f"⭐ {disp(c['market'], c['symbol'], name)} — 이번 주 재무 필터 통과 후보 등장")

    return hits


# ── 텔레그램 발송 ────────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.info("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 알림 건너뜀 (기능은 비활성 상태)")
        return False

    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except Exception as e:
        logger.error("텔레그램 발송 실패: %s", e)
        return False


def should_send(signature: str) -> bool:
    """중복 발송 억제 — 직전 발송과 내용이 같으면 건너뛰되,
    24시간 넘게 조용했으면 앵커로 1회는 발송 (시스템 생존 확인용)."""
    turso_query(
        "CREATE TABLE IF NOT EXISTS telegram_digest_state ("
        "  id INTEGER PRIMARY KEY CHECK (id = 1),"
        "  signature TEXT, sent_at TEXT)"
    )
    rows = turso_query("SELECT signature, sent_at FROM telegram_digest_state WHERE id = 1")
    if rows:
        prev_sig = rows[0].get("signature")
        sent_at = rows[0].get("sent_at") or ""
        try:
            last = datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        except Exception:
            hours = 999
        if prev_sig == signature and hours < 24:
            logger.info("직전 발송과 내용 동일 (%.1f시간 전) — 발송 생략", hours)
            return False
    return True


def mark_sent(signature: str) -> None:
    turso_query(
        "INSERT INTO telegram_digest_state (id, signature, sent_at) "
        "VALUES (1, ?, strftime('%Y-%m-%d %H:%M:%S','now')) "
        "ON CONFLICT(id) DO UPDATE SET signature=excluded.signature, sent_at=excluded.sent_at",
        [signature],
    )


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    shifts = get_narrative_shifts()
    cross_hits = get_cross_hits()

    # 의미 있는 내용의 지문 — 날짜는 제외 (같은 내용이면 날짜만 달라도 중복)
    signature = json.dumps(
        {"cross": cross_hits, "shifts": shifts},
        ensure_ascii=False, sort_keys=True,
    )
    if not should_send(signature):
        return

    lines = [f"<b>📊 AlphaDesk 주간 요약 — {today}</b>", ""]

    if cross_hits:
        lines += ["", "<b>⭐ 워치리스트 ↔ 상위 종목 교차</b>"] + cross_hits
    if shifts:
        lines += ["", "<b>📈 관심도 상승</b>"] + shifts

    if not (cross_hits or shifts):
        lines += ["", "오늘은 별다른 신호 없음."]

    text = "\n".join(lines)
    logger.info("메시지 구성 완료 (%d줄)\n%s", len(lines), text)

    sent = send_telegram(text)
    if sent:
        mark_sent(signature)
        logger.info("텔레그램 발송 완료")


if __name__ == "__main__":
    main()
