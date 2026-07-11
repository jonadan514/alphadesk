"""주간 브리핑 생성 — 주간 워치리스트 스크리닝 직후(일요일 밤) 실행.

한 주의 데이터를 모아 구조화된 브리핑을 만들고:
  1. Turso weekly_briefings 테이블에 저장 (웹 '주간 브리핑' 탭이 읽음)
  2. 텔레그램으로 요약 발송

섹션:
  - 지난주 시장 궤적 (US/KR 게이트·체제·verdict 이력, 지수 주간 등락)
  - 워치리스트 변동 (신규 진입/탈락 — watchlist_weekly_snapshots 비교)
  - 관심도 흐름 (한 주간 sentiment 상승 종목)
  - 다가오는 촉매 (내 워치리스트 종목의 네러티브 촉매 모음)
  - GPT 총평 · 다음 주 관전 포인트

Usage: python scripts/generate_weekly_briefing.py [--no-telegram]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENTIMENT_RANK = {"COLD": 0, "WARM": 1, "HOT": 2}


# ── Turso (Hrana v2 HTTP) — 다른 스크립트와 동일 패턴 ──────────────────────

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


def turso_exec(sql: str, args: list | None = None) -> list[dict]:
    url, headers = _turso_base()
    stmt = {"type": "execute", "stmt": {"sql": sql}}
    if args:
        stmt["stmt"]["args"] = [_turso_val(a) for a in args]
    body = json.dumps({"requests": [stmt]}).encode()
    req = urllib.request.Request(f"{url}/v2/pipeline", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            results = json.loads(resp.read()).get("results", [])
    except Exception as e:
        logger.warning("Turso 실패 (%s): %s", sql[:50], type(e).__name__)
        return []
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


def _payload(rows: list[dict], key: str = "payload") -> list[dict]:
    out = []
    for r in rows:
        try:
            out.append({**r, "_data": json.loads(r[key])})
        except Exception:
            continue
    return out


# ── 섹션 수집 ────────────────────────────────────────────────────────────────

def get_market_week(market: str) -> dict:
    """최근 5거래일 verdict·regime 이력 + 현재 게이트."""
    table = "kr_daily_reports" if market == "KR" else "data_daily_reports"
    gate_table = "kr_market_gate" if market == "KR" else "data_market_gate"

    reports = _payload(turso_exec(f"SELECT date, payload FROM {table} ORDER BY date DESC LIMIT 5"))
    history = [
        {"date": r["date"], "verdict": r["_data"].get("verdict"), "regime": r["_data"].get("regime")}
        for r in reversed(reports)
    ]
    gate_rows = _payload(turso_exec(f"SELECT payload FROM {gate_table} WHERE id = 1"))
    gate = gate_rows[0]["_data"].get("gate") if gate_rows else None
    regime = history[-1]["regime"] if history else None

    # 지수 주간 등락 (yfinance)
    idx_chg = None
    try:
        import yfinance as yf
        ticker = "^KS11" if market == "KR" else "SPY"
        hist = yf.Ticker(ticker).history(period="7d", auto_adjust=True)["Close"].dropna()
        if len(hist) >= 2:
            idx_chg = round(float(hist.iloc[-1] / hist.iloc[0] - 1) * 100, 2)
    except Exception:
        pass

    return {"gate": gate, "regime": regime, "history": history, "index_chg_1w": idx_chg}


def get_watchlist_changes() -> dict:
    """이번 주 후보 vs 지난주 스냅샷 비교 → 신규/탈락. 이번 주 스냅샷 저장."""
    turso_exec(
        "CREATE TABLE IF NOT EXISTS watchlist_weekly_snapshots ("
        "  week TEXT PRIMARY KEY, payload TEXT NOT NULL,"
        "  created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )

    current = turso_exec(
        "SELECT market, symbol, name, fit_score FROM watchlist_candidates ORDER BY fit_score DESC"
    )
    cur_map = {f"{c['market']}:{c['symbol']}": c for c in current}

    prev_rows = _payload(turso_exec(
        "SELECT week, payload FROM watchlist_weekly_snapshots ORDER BY week DESC LIMIT 1"
    ))
    prev_map: dict[str, dict] = {}
    if prev_rows:
        prev_map = {f"{c['market']}:{c['symbol']}": c for c in prev_rows[0]["_data"]}

    added   = [cur_map[k] for k in cur_map if k not in prev_map]
    removed = [prev_map[k] for k in prev_map if k not in cur_map]
    top     = current[:5]

    # 이번 주 스냅샷 저장 (월요일 날짜 기준)
    week = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    turso_exec(
        "INSERT INTO watchlist_weekly_snapshots (week, payload) VALUES (?, ?) "
        "ON CONFLICT(week) DO UPDATE SET payload=excluded.payload",
        [week, json.dumps(current, ensure_ascii=False)],
    )

    return {
        "total": len(current),
        "added": added[:10],
        "removed": removed[:10],
        "top": top,
        "has_prev": bool(prev_map),
    }


def get_sentiment_week() -> list[dict]:
    """최근 7일 관심도 이력에서 상승 전환 종목."""
    rows = turso_exec(
        "SELECT market, symbol, date, sentiment FROM narrative_sentiment_history "
        "WHERE date >= date('now', '-7 days') ORDER BY market, symbol, date"
    )
    by_sym: dict[str, list] = {}
    for r in rows:
        by_sym.setdefault(f"{r['market']}:{r['symbol']}", []).append(r["sentiment"])

    # 이름 조회
    names = {f"{c['market']}:{c['symbol']}": c.get("name")
             for c in turso_exec("SELECT market, symbol, name FROM watchlist_candidates")}

    heating = []
    for key, seq in by_sym.items():
        if len(seq) < 2:
            continue
        first, last = SENTIMENT_RANK.get(seq[0], 1), SENTIMENT_RANK.get(seq[-1], 1)
        if last > first:
            market, symbol = key.split(":", 1)
            heating.append({
                "market": market, "symbol": symbol, "name": names.get(key),
                "path": f"{seq[0]}→{seq[-1]}",
            })
    return heating[:10]


def get_upcoming_catalysts() -> list[dict]:
    """내 워치리스트 종목의 네러티브 촉매 모음."""
    my = turso_exec("SELECT market, symbol, name FROM my_watchlist")
    if not my:
        return []
    out = []
    for m in my:
        rows = _payload(turso_exec(
            "SELECT payload FROM narrative_briefs WHERE market = ? AND symbol = ?",
            [m["market"], m["symbol"]],
        ))
        if not rows:
            continue
        cats = rows[0]["_data"].get("catalysts") or []
        if cats:
            out.append({
                "market": m["market"], "symbol": m["symbol"],
                "name": m.get("name") or rows[0]["_data"].get("name"),
                "catalysts": cats[:3],
            })
    return out[:10]


# ── GPT 총평 ─────────────────────────────────────────────────────────────────

def gpt_comment(briefing: dict) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return ""

    import requests

    compact = {
        "us": {k: briefing["us"][k] for k in ("gate", "regime", "index_chg_1w", "history")},
        "kr": {k: briefing["kr"][k] for k in ("gate", "regime", "index_chg_1w", "history")},
        "watchlist_added": [f"{a.get('name') or a['symbol']}" for a in briefing["watchlist"]["added"][:5]],
        "watchlist_removed": [f"{a.get('name') or a['symbol']}" for a in briefing["watchlist"]["removed"][:5]],
        "sentiment_heating": [f"{h.get('name') or h['symbol']} {h['path']}" for h in briefing["sentiment_heating"]],
    }
    prompt = f"""다음은 개인 투자 대시보드의 지난주 데이터 요약입니다:

{json.dumps(compact, ensure_ascii=False, indent=1)}

이 데이터만 근거로 다음 3개 문단의 주간 총평을 한국어로 작성하세요 (문단당 2~3문장, 마크다운 없이 평문):
1. 지난주 시장 요약 — 미국·한국 체제/게이트 흐름과 지수 움직임
2. 워치리스트·관심도 변화의 의미 — 어떤 종류의 종목이 들어오고 나갔는지, 시장이 어디로 관심을 옮기는지
3. 다음 주 관전 포인트 — 주의할 것과 지켜볼 것

데이터에 없는 사실(구체적 뉴스·수치)을 지어내지 마세요."""

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "당신은 간결하고 정직한 투자 브리핑 작가입니다."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 800,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("GPT 총평 생성 실패: %s", type(e).__name__)
        return ""


# ── 텔레그램 요약 ────────────────────────────────────────────────────────────

def send_telegram_summary(b: dict) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.info("텔레그램 미설정 — 발송 건너뜀")
        return

    def disp(item):
        flag = "🇰🇷" if item["market"] == "KR" else "🇺🇸"
        label = (item.get("name") or item["symbol"]) if item["market"] == "KR" else item["symbol"]
        return f"{flag} {label}"

    lines = [f"<b>📋 주간 브리핑 — {b['week']} 주</b>", ""]
    us, kr = b["us"], b["kr"]
    lines.append(f"🇺🇸 {us.get('gate','?')} · {us.get('regime','?')}"
                 + (f" · SPY 주간 {us['index_chg_1w']:+.1f}%" if us.get("index_chg_1w") is not None else ""))
    lines.append(f"🇰🇷 {kr.get('gate','?')} · {kr.get('regime','?')}"
                 + (f" · KOSPI 주간 {kr['index_chg_1w']:+.1f}%" if kr.get("index_chg_1w") is not None else ""))

    wl = b["watchlist"]
    if wl["has_prev"] and (wl["added"] or wl["removed"]):
        lines.append("")
        lines.append(f"<b>🔖 워치리스트</b> 신규 {len(wl['added'])} · 탈락 {len(wl['removed'])}")
        for a in wl["added"][:3]:
            lines.append(f"  + {disp(a)} (적합 {a.get('fit_score','—')})")
    if b["sentiment_heating"]:
        lines.append("")
        lines.append("<b>📈 이번 주 달아오른 종목</b>")
        for h in b["sentiment_heating"][:3]:
            lines.append(f"  {disp(h)} {h['path']}")

    if b.get("gpt_comment"):
        first_para = b["gpt_comment"].split("\n")[0][:200]
        lines += ["", f"💬 {first_para}"]
    lines += ["", "전체 브리핑은 웹 '주간 브리핑' 탭에서."]

    body = json.dumps({"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        logger.info("텔레그램 주간 요약 발송 완료")
    except Exception as e:
        logger.error("텔레그램 발송 실패: %s", e)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    # 브리핑 주차 라벨 = 다가오는 월요일 (일요일 밤 실행 기준)
    days_to_mon = (7 - now.weekday()) % 7
    week = (now + timedelta(days=days_to_mon)).strftime("%Y-%m-%d")

    logger.info("주간 브리핑 생성 시작 (week=%s)", week)

    briefing = {
        "week": week,
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "us": get_market_week("US"),
        "kr": get_market_week("KR"),
        "watchlist": get_watchlist_changes(),
        "sentiment_heating": get_sentiment_week(),
        "catalysts": get_upcoming_catalysts(),
    }
    briefing["gpt_comment"] = gpt_comment(briefing)

    turso_exec(
        "CREATE TABLE IF NOT EXISTS weekly_briefings ("
        "  week TEXT PRIMARY KEY, payload TEXT NOT NULL,"
        "  created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    turso_exec(
        "INSERT INTO weekly_briefings (week, payload) VALUES (?, ?) "
        "ON CONFLICT(week) DO UPDATE SET payload=excluded.payload, created_at=datetime('now')",
        [week, json.dumps(briefing, ensure_ascii=False)],
    )
    logger.info("저장 완료 — 워치리스트 신규 %d·탈락 %d, 관심도 상승 %d, 촉매 %d종목",
                len(briefing["watchlist"]["added"]), len(briefing["watchlist"]["removed"]),
                len(briefing["sentiment_heating"]), len(briefing["catalysts"]))

    if not args.no_telegram:
        send_telegram_summary(briefing)


if __name__ == "__main__":
    main()
