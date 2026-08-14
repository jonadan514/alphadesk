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

STOP_LOSS_PCT = {"risk_on": 10, "neutral": 8, "risk_off": 5, "crisis": 3}
GATE_KO = {"GO": "GO (매수 가능)", "CAUTION": "CAUTION (신중)", "STOP": "STOP (관망)"}
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


def get_snapshot(table: str) -> dict:
    rows = turso_query(f"SELECT payload FROM {table} WHERE id = 1")
    if not rows:
        return {}
    try:
        return json.loads(rows[0]["payload"])
    except Exception:
        return {}


def get_latest_timeseries(table: str) -> dict:
    rows = turso_query(f"SELECT payload FROM {table} ORDER BY date DESC LIMIT 1")
    if not rows:
        return {}
    try:
        return json.loads(rows[0]["payload"])
    except Exception:
        return {}


# ── 가격 조회 (yfinance) ────────────────────────────────────────────────────

def fetch_prices(holdings: list[dict]) -> dict[str, float]:
    if not holdings:
        return {}
    import yfinance as yf

    out: dict[str, float] = {}
    for h in holdings:
        symbol, market = h["symbol"], h["market"]
        candidates = [f"{symbol}.KS", f"{symbol}.KQ"] if market == "KR" else [symbol]
        for ysym in candidates:
            try:
                info = yf.Ticker(ysym).fast_info
                price = getattr(info, "last_price", None) or info.get("lastPrice")
                if price:
                    out[f"{market}:{symbol}"] = float(price)
                    break
            except Exception:
                continue
    return out


# ── 데이터 수집 ──────────────────────────────────────────────────────────────

def disp(market: str, symbol: str, name: str | None = None) -> str:
    """표시용 라벨 — KR은 코드 대신 종목명(있으면), US는 티커."""
    flag = "🇰🇷" if market == "KR" else "🇺🇸"
    label = (name or symbol) if market == "KR" else symbol
    return f"{flag} {label}"


def compute_holdings(trades: list[dict]) -> list[dict]:
    """my_trades → 현재 보유 종목 (프론트 portfolio 페이지와 동일한 로직)."""
    acc: dict[str, dict] = {}
    for t in sorted(trades, key=lambda r: (r.get("trade_date", ""), r.get("id", 0))):
        key = f"{t['market']}:{t['symbol']}"
        cur = acc.setdefault(key, {"market": t["market"], "symbol": t["symbol"],
                                   "name": t.get("name"), "shares": 0.0, "cost": 0.0})
        price, shares = float(t["price"]), float(t["shares"])
        if t["type"] == "buy":
            total_shares = cur["shares"] + shares
            cur["cost"] = (cur["cost"] * cur["shares"] + price * shares) / total_shares if total_shares else 0
            cur["shares"] = total_shares
        else:
            cur["shares"] = max(0.0, cur["shares"] - shares)
    return [v for v in acc.values() if v["shares"] > 0]


def get_stop_loss_alerts() -> list[str]:
    trades = turso_query("SELECT market, symbol, name, type, trade_date, price, shares, id FROM my_trades")
    holdings = compute_holdings(trades)
    if not holdings:
        return []

    prices = fetch_prices(holdings)
    regimes = {
        "US": get_snapshot("data_regime").get("regime", "neutral"),
        "KR": get_snapshot("kr_regime").get("regime", "neutral"),
    }

    alerts = []
    for h in holdings:
        price = prices.get(f"{h['market']}:{h['symbol']}")
        if price is None or h["cost"] <= 0:
            continue
        pl_pct = (price / h["cost"] - 1) * 100
        threshold = STOP_LOSS_PCT.get(regimes.get(h["market"], "neutral"), 8)
        label = disp(h["market"], h["symbol"], h.get("name"))
        if pl_pct <= -threshold:
            alerts.append(f"🔴 {label} {pl_pct:+.1f}% — 손절선(-{threshold}%) 도달")
        elif pl_pct <= -threshold + 2:
            alerts.append(f"🟠 {label} {pl_pct:+.1f}% — 손절선 근접(-{threshold}%)")
    return alerts


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

    us_gate = get_snapshot("data_market_gate")
    kr_gate = get_snapshot("kr_market_gate")
    stop_alerts = get_stop_loss_alerts()
    shifts = get_narrative_shifts()
    cross_hits = get_cross_hits()

    us_g = us_gate.get("gate", "?")
    kr_g = kr_gate.get("gate", "?")

    # 의미 있는 내용의 지문 — 날짜는 제외 (같은 내용이면 날짜만 달라도 중복)
    signature = json.dumps(
        {"us": us_g, "kr": kr_g, "stop": stop_alerts, "cross": cross_hits, "shifts": shifts},
        ensure_ascii=False, sort_keys=True,
    )
    if not should_send(signature):
        return

    lines = [f"<b>📊 AlphaDesk 주간 요약 — {today}</b>", ""]
    lines.append(f"🇺🇸 US: {GATE_KO.get(us_g, us_g)}")
    lines.append(f"🇰🇷 KR: {GATE_KO.get(kr_g, kr_g)}")

    if stop_alerts:
        lines += ["", "<b>⚠️ 손절선 경고</b>"] + stop_alerts
    if cross_hits:
        lines += ["", "<b>⭐ 워치리스트 ↔ 상위 종목 교차</b>"] + cross_hits
    if shifts:
        lines += ["", "<b>📈 관심도 상승</b>"] + shifts

    if not (stop_alerts or cross_hits or shifts):
        lines += ["", "오늘은 별다른 신호 없음."]

    text = "\n".join(lines)
    logger.info("메시지 구성 완료 (%d줄)\n%s", len(lines), text)

    sent = send_telegram(text)
    if sent:
        mark_sent(signature)
        logger.info("텔레그램 발송 완료")


if __name__ == "__main__":
    main()
