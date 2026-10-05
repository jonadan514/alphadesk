"""주간 브리핑 생성 — 주간 워치리스트 스크리닝 직후(일요일 밤) 실행.

한 주의 데이터를 모아 구조화된 브리핑을 만들고:
  1. Turso weekly_briefings 테이블에 저장 (웹 '주간 브리핑' 탭이 읽음)
  2. 텔레그램으로 요약 발송

섹션:
  - 지난주 시장 궤적 (US/KR 지수 주간 등락)
  - 워치리스트 변동 (신규 진입/탈락 — watchlist_weekly_snapshots 비교)
  - 관심도 흐름 (한 주간 sentiment 상승 종목)
  - 다가오는 촉매 (내 워치리스트 종목의 네러티브 촉매 모음)
  - GPT 총평 · 다음 주 관전 포인트 (웹에만 - 텔레그램은 DB·시세 숫자만, 2026-10-05)
  - 테마 레이더 라벨 변동 (미국·한국)

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

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.turso_http import get_credentials, query as _turso_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENTIMENT_RANK = {"COLD": 0, "WARM": 1, "HOT": 2}
SENTIMENT_KO = {"COLD": "낮음", "WARM": "보통", "HOT": "높음"}
SITE_URL = "https://u-sonar.vercel.app"
MARKET_FLAG = {"US": "🇺🇸", "KR": "🇰🇷"}


def _md(day: str | None) -> str:
    """'2026-09-28' -> '9/28'. 텔레그램에서 날짜를 짧게 읽히게."""
    if not day:
        return "-"
    _y, m, d = day.split("-")
    return f"{int(m)}/{int(d)}"
THEMES_YAML = ROOT / "config" / "themes.yaml"


def load_theme_names() -> dict[str, str]:
    """scripts/send_radar_digest.py와 동일한 패턴."""
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {t["id"]: t["name_ko"] for t in data["themes"]}


# ── Turso (Hrana v2 HTTP) — 다른 스크립트와 동일 패턴 ──────────────────────

def _require_turso() -> None:
    if not get_credentials():
        logger.error("TURSO_DATA_URL / TURSO_DATA_TOKEN 미설정")
        sys.exit(1)


def turso_exec(sql: str, args: list | None = None) -> list[dict]:
    _require_turso()
    try:
        return _turso_query(sql, args)
    except Exception as e:
        logger.warning("Turso 실패 (%s): %s", sql[:50], type(e).__name__)
        return []


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
    """지수 주간 등락."""
    idx_chg = None
    try:
        import yfinance as yf
        ticker = "^KS11" if market == "KR" else "SPY"
        hist = yf.Ticker(ticker).history(period="7d", auto_adjust=True)["Close"].dropna()
        if len(hist) >= 2:
            idx_chg = round(float(hist.iloc[-1] / hist.iloc[0] - 1) * 100, 2)
    except Exception:
        pass

    return {"index_chg_1w": idx_chg}


def get_watchlist_changes() -> dict:
    """이번 주 후보 vs 지난주 스냅샷 비교 → 신규/탈락. 이번 주 스냅샷 저장."""
    turso_exec(
        "CREATE TABLE IF NOT EXISTS watchlist_weekly_snapshots ("
        "  week TEXT PRIMARY KEY, payload TEXT NOT NULL,"
        "  created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )

    current = turso_exec(
        "SELECT market, symbol, name FROM watchlist_candidates ORDER BY market, symbol"
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

    # 이번 주 스냅샷 저장 (월요일 날짜 기준)
    week = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    turso_exec(
        "INSERT INTO watchlist_weekly_snapshots (week, payload) VALUES (?, ?) "
        "ON CONFLICT(week) DO UPDATE SET payload=excluded.payload",
        [week, json.dumps(current, ensure_ascii=False)],
    )

    return {
        "total": len(current),
        # 목록은 10개까지만 담고, 건수는 자르기 전 전체를 따로 둔다 - 예전엔 자른 목록 길이를 세서
        # 신규가 30개여도 "신규 10"으로 나왔다(2026-10-05 수정).
        "added": added[:10],
        "removed": removed[:10],
        "added_count": len(added),
        "removed_count": len(removed),
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
                "path": f"{SENTIMENT_KO.get(seq[0], seq[0])}→{SENTIMENT_KO.get(seq[-1], seq[-1])}",
            })
    return heating[:10]


def get_theme_label_changes() -> dict:
    """테마 레이더 라벨 변동 - 시장별로 계산된 가장 최근 두 주 비교 (미국·한국).

    라벨 계산(compute-theme-labels.yml)은 이 브리핑과 별도 워크플로라 "이번 주"라고 단정하지 않고
    실제로 계산이 끝난 week_start를 그대로 노출한다. 항목마다 market을 붙인다(2026-10-05 한국 추가 -
    예전엔 미국만 봤다). label_counts는 시장별 이번 주 라벨 수 - 0이면 텔레그램에 "아직 라벨 없음"을 쓴다.
    """
    out = {"week_start": None, "new_labels": [], "dropped_labels": [], "label_counts": {}}
    for market in ("US", "KR"):
        weeks = turso_exec(
            "SELECT DISTINCT week_start FROM theme_signals WHERE market = ? "
            "ORDER BY week_start DESC LIMIT 2", [market]
        )
        if not weeks:
            continue
        latest = weeks[0]["week_start"]
        out["week_start"] = max(out["week_start"] or latest, latest)

        def labels(week: str) -> dict[str, str]:
            rows = turso_exec(
                "SELECT theme_id, label FROM theme_signals "
                "WHERE market = ? AND week_start = ? AND label IS NOT NULL",
                [market, week],
            )
            return {r["theme_id"]: r["label"] for r in rows}

        cur_map = labels(latest)
        prev_map = labels(weeks[1]["week_start"]) if len(weeks) > 1 else {}
        out["label_counts"][market] = len(cur_map)
        out["new_labels"] += [{"theme_id": t, "label": l, "market": market}
                              for t, l in cur_map.items() if prev_map.get(t) != l]
        out["dropped_labels"] += [{"theme_id": t, "label": l, "market": market}
                                  for t, l in prev_map.items() if t not in cur_map]
    return out


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
        "us_index_chg_1w": briefing["us"]["index_chg_1w"],
        "kr_index_chg_1w": briefing["kr"]["index_chg_1w"],
        "watchlist_added": [f"{a.get('name') or a['symbol']}" for a in briefing["watchlist"]["added"][:5]],
        "watchlist_removed": [f"{a.get('name') or a['symbol']}" for a in briefing["watchlist"]["removed"][:5]],
        "sentiment_heating": [f"{h.get('name') or h['symbol']} {h['path']}" for h in briefing["sentiment_heating"]],
    }
    prompt = f"""다음은 개인 투자 대시보드의 지난주 데이터 요약입니다:

{json.dumps(compact, ensure_ascii=False, indent=1)}

이 데이터만 근거로 다음 3개 문단의 주간 총평을 한국어로 작성하세요 (문단당 2~3문장, 마크다운 없이 평문):
1. 지난주 시장 요약 — 미국·한국 지수 움직임
2. 워치리스트·관심도 변화의 의미 — 어떤 종류의 종목이 들어오고 나갔는지, 시장이 어디로 관심을 옮기는지
3. 다음 주 관전 포인트 — 주의할 것과 지켜볼 것

데이터에 없는 사실(구체적 뉴스·수치)을 지어내지 마세요.
숫자(등락률·건수 등)는 쓰지 마세요 - 숫자는 화면에 따로 표시됩니다. "올랐다/내렸다/소폭" 같은 말로만 표현하세요."""

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

def build_telegram_summary(b: dict) -> str:
    """텔레그램 요약 본문. 숫자는 전부 DB·시세에서 온 값만 쓴다 - GPT 총평은 웹에만 둔다(원칙 2)."""
    def disp(item):
        flag = MARKET_FLAG.get(item["market"], "")
        label = (item.get("name") or item["symbol"]) if item["market"] == "KR" else item["symbol"]
        return f"{flag} {label}"

    lines = [f"<b>📋 Undercurrent Sonar 주간 브리핑</b> · {_md(b['week'])}", ""]

    idx = []
    if b["us"].get("index_chg_1w") is not None:
        idx.append(f"🇺🇸 SPY {b['us']['index_chg_1w']:+.1f}%")
    if b["kr"].get("index_chg_1w") is not None:
        idx.append(f"🇰🇷 KOSPI {b['kr']['index_chg_1w']:+.1f}%")
    if idx:
        lines.append("지난 1주 " + " · ".join(idx))

    # 테마 레이더 - 이 툴의 중심이라 라벨이 없어도 상태를 한 줄은 쓴다
    tl = b.get("theme_labels") or {}
    counts = tl.get("label_counts") or {}
    lines.append("")
    lines.append(f"<b>📡 테마 레이더</b> ({_md(tl.get('week_start'))} 주)")
    if counts and not any(counts.values()):
        lines.append("  아직 라벨 없음 - 뉴스 기준선(4주)이 쌓이면 붙습니다")
    else:
        lines.append("  라벨 " + " · ".join(f"{MARKET_FLAG[m]} {n}개" for m, n in counts.items()))
        names = load_theme_names()
        for t in tl.get("new_labels", [])[:5]:
            lines.append(f"  + {MARKET_FLAG.get(t.get('market', 'US'), '')} "
                         f"{names.get(t['theme_id'], t['theme_id'])} — {t['label']}")
        if len(tl.get("new_labels", [])) > 5:
            lines.append(f"  외 {len(tl['new_labels']) - 5}개")

    wl = b["watchlist"]
    lines.append("")
    if wl["has_prev"]:
        lines.append(f"<b>🔖 워치리스트</b> {wl['total']}종목 · 신규 {wl['added_count']} · 탈락 {wl['removed_count']}")
        for a in wl["added"][:3]:
            lines.append(f"  + {disp(a)}")
        if wl["added_count"] > 3:
            lines.append(f"  외 {wl['added_count'] - 3}개")
    else:
        lines.append(f"<b>🔖 워치리스트</b> {wl['total']}종목")

    if b["sentiment_heating"]:
        lines.append("")
        lines.append("<b>📈 관심도 상승</b>")
        for h in b["sentiment_heating"][:3]:
            lines.append(f"  {disp(h)} {h['path']}")

    lines += ["", f'<a href="{SITE_URL}/briefing">전체 브리핑 보기</a>']
    return "\n".join(lines)


def send_telegram_summary(b: dict) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.info("텔레그램 미설정 — 발송 건너뜀")
        return

    body = json.dumps({"chat_id": chat_id, "text": build_telegram_summary(b), "parse_mode": "HTML",
                       "disable_web_page_preview": True}).encode()
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
        "theme_labels": get_theme_label_changes(),
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
    logger.info("저장 완료 — 워치리스트 신규 %d·탈락 %d, 관심도 상승 %d, 촉매 %d종목, 테마 라벨 신규 %d·소멸 %d",
                briefing["watchlist"]["added_count"], briefing["watchlist"]["removed_count"],
                len(briefing["sentiment_heating"]), len(briefing["catalysts"]),
                len(briefing["theme_labels"]["new_labels"]), len(briefing["theme_labels"]["dropped_labels"]))

    if not args.no_telegram:
        send_telegram_summary(briefing)


if __name__ == "__main__":
    main()
