"""테마 → 기업 매핑 (Phase A-2).

SPEC: docs/radar/SPEC_theme_company_mapping.md

경로 A(유니버스 제약 선택) + 경로 B(자유 생성)를 합쳐 후보를 만들고, 코드
검증(§4)을 통과한 것만 theme_members에 저장한다. approved=0으로 저장되며
사람이 검토해서 승인하기 전까지는 화면에 반영되지 않는다(§7).

Usage:
  python scripts/map_theme_companies.py                                    # 전체 테마
  python scripts/map_theme_companies.py --theme-id nuclear_smr physical_ai  # 특정 테마만(파일럿용)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_mapping import ensure_schema, start_mapping_run, finish_mapping_run, insert_theme_member
from collectors.watchlist_collector import get_us_universe, get_kr_universe, US_MIN_CAP, KR_MIN_CAP

THEMES_YAML = ROOT / "config" / "themes.yaml"
OPENAI_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "2026-09-01-v2"
UNIVERSE_CHUNK_SIZE = 200
MIN_EVIDENCE_LEN = 15
BANNED_EVIDENCE_PHRASES = ["관련 사업", "수혜 예상", "테마주", "관련주"]
HALLUCINATION_WARN_RATE = 0.30  # SPEC §4 — 경로 B 폐기율 30% 넘으면 로그로 경고


def _log(msg: str) -> None:
    print(f"[map_theme] {msg}")


def load_themes(theme_ids: list[str] | None) -> list[dict]:
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    themes = [t for t in data["themes"] if t.get("status") == "active"]
    if theme_ids:
        wanted = set(theme_ids)
        themes = [t for t in themes if t["id"] in wanted]
    return themes


def build_universe_and_names() -> tuple[list[dict], dict[str, str]]:
    """유니버스(경로 A 제약용)와 티커→회사명 매핑을 만든다.
    US 이름은 sp500_list.csv(이미 있음)에서, KR은 get_kr_universe()가 이미 포함."""
    us_items = get_us_universe()
    kr_items = get_kr_universe()

    names: dict[str, str] = {}
    sp500_csv = ROOT / "data" / "sp500_list.csv"
    if sp500_csv.exists():
        df = pd.read_csv(sp500_csv)
        sym_col = next((c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()), df.columns[0])
        name_col = next((c for c in df.columns if c.lower() in ("security", "name")), None)
        if name_col:
            for _, row in df.iterrows():
                sym = str(row[sym_col]).replace(".", "-")
                names[sym] = str(row[name_col])

    for it in kr_items:
        if it.get("name"):
            names[it["symbol"]] = it["name"]

    return us_items + kr_items, names


def _openai_json(prompt: str, system: str, api_key: str) -> dict | None:
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return json.loads(text)
    except Exception as e:
        _log(f"  OpenAI 호출 실패: {type(e).__name__}: {e}")
        return None


def _theme_description(theme: dict) -> str:
    lines = [f"테마명: {theme['name_ko']} ({theme['name_en']})"]
    if theme.get("note"):
        lines.append(f"설명: {theme['note']}")
    else:
        kws = ", ".join(theme.get("keywords_ko", []))
        lines.append(f"관련 키워드: {kws}")
    return "\n".join(lines)


MEMBER_FIELDS_INSTRUCTION = """각 기업에 대해 다음 필드를 답하시오:
- ticker: 정확한 티커/코드
- name: 회사명
- market: "US" 또는 "KR"
- value_chain_stage: 이 기업이 테마 내에서 어떤 역할·위치인지 (한 단어~짧은 구)
- evidence: 왜 이 테마에 속하는지 구체적 근거 한 문장 (막연한 표현 금지, 구체적 제품·사업부 명시. 15자 이상)
- linkage: "direct"(주력 사업) / "partial"(일부 사업부) / "peripheral"(간접 노출) 중 하나

명확히 속하지 않으면 포함하지 마시오. 반드시 아래 JSON 형식으로만 답하시오:
{"members": [{"ticker": "...", "name": "...", "market": "US|KR", "value_chain_stage": "...", "evidence": "...", "linkage": "direct|partial|peripheral"}]}"""


def path_a_universe_constrained(theme: dict, universe: list[dict], names: dict[str, str], api_key: str) -> list[dict]:
    """유니버스를 청크로 나눠 그 안에서만 고르게 한다 — 환각 티커 원천 차단."""
    results: list[dict] = []
    desc = _theme_description(theme)
    n_chunks = (len(universe) + UNIVERSE_CHUNK_SIZE - 1) // UNIVERSE_CHUNK_SIZE
    for i in range(0, len(universe), UNIVERSE_CHUNK_SIZE):
        chunk = universe[i:i + UNIVERSE_CHUNK_SIZE]
        listing = "\n".join(f"- {it['symbol']} ({it['market']}) {names.get(it['symbol'], '')}" for it in chunk)
        prompt = f"""{desc}

아래 상장기업 목록에서 위 테마에 실제로 속하는 기업만 고르시오. 목록에 없는
기업은 절대 답하지 마시오.

목록:
{listing}

{MEMBER_FIELDS_INSTRUCTION}"""
        parsed = _openai_json(prompt, "당신은 신중한 산업 분석가입니다. 주어진 목록에 없는 기업은 답하지 않습니다.", api_key)
        if parsed and isinstance(parsed.get("members"), list):
            results.extend(parsed["members"])
        _log(f"  경로 A 청크 {i // UNIVERSE_CHUNK_SIZE + 1}/{n_chunks} 완료")
        time.sleep(0.5)
    return results


def path_b_free_generation(theme: dict, api_key: str) -> list[dict]:
    """목록 없이 자유 생성 — 유니버스 밖 신규 상장 종목 포착용. 결과는 §4 검증을 반드시 통과해야 함."""
    desc = _theme_description(theme)
    prompt = f"""{desc}

위 테마에 해당하는 실제 상장기업(미국 또는 한국 증시)을 아는 대로 답하시오.
확실하지 않은 기업은 포함하지 마시오.

{MEMBER_FIELDS_INSTRUCTION}"""
    parsed = _openai_json(prompt, "당신은 신중한 산업 분석가입니다. 확실하지 않으면 답하지 않습니다.", api_key)
    if parsed and isinstance(parsed.get("members"), list):
        return parsed["members"]
    return []


def validate_members(raw_a: list[dict], raw_b: list[dict], valid_tickers: set[str],
                      cap_lookup: dict[str, float]) -> tuple[list[dict], dict]:
    """SPEC §4 코드 검증. (통과 목록, 통계) 반환.

    재무 데이터(fundamentals_cache) 존재 여부는 여기서 탈락시키지 않는다 — 그건
    나중에 실적 축 계산(Phase A-4)이 그 시점 캐시로 판단할 몫이고, 매핑 단계는
    "테마에 속하는 기업 목록"만 정하는 단계라서(SPEC §4 step3 의도: 없으면
    insufficient_data로 "구분"하되 탈락은 아님 — theme_members 자체엔 그 상태를
    담는 컬럼이 없으므로 그냥 포함시켜 후속 단계에서 자연히 데이터부족으로
    처리되게 한다).
    """
    # LLM이 대소문자를 안 지킬 수 있어 정규화 — KR 코드는 숫자라 upper()가 no-op.
    def _norm(m: dict) -> str:
        return str(m.get("ticker", "")).strip().upper()

    tickers_a = {_norm(m) for m in raw_a}
    tickers_b = {_norm(m) for m in raw_b}
    merged_by_ticker: dict[str, dict] = {}
    for m in raw_a + raw_b:
        t = _norm(m)
        if t and t not in merged_by_ticker:
            merged_by_ticker[t] = m

    stats = {"입력": len(merged_by_ticker), "티커실재실패": 0, "시가총액미달": 0,
              "evidence품질실패": 0, "통과": 0}
    out = []

    for ticker, m in merged_by_ticker.items():
        if ticker not in valid_tickers:
            stats["티커실재실패"] += 1
            continue

        market = m.get("market") or ("KR" if ticker.isdigit() else "US")
        min_cap = US_MIN_CAP if market == "US" else KR_MIN_CAP
        cap = cap_lookup.get(ticker)
        if cap is not None and cap < min_cap:
            stats["시가총액미달"] += 1
            continue

        evidence = str(m.get("evidence", "")).strip()
        if len(evidence) < MIN_EVIDENCE_LEN:
            stats["evidence품질실패"] += 1
            continue
        flagged = any(p in evidence for p in BANNED_EVIDENCE_PHRASES)

        linkage = m.get("linkage")
        if linkage not in ("direct", "partial", "peripheral"):
            linkage = "partial"

        out.append({
            "ticker": ticker,
            "market": market,
            "stage": m.get("value_chain_stage"),
            "evidence": evidence,
            "linkage": linkage,
            "confidence": "high" if ticker in tickers_a and ticker in tickers_b else "normal",
            "flagged": flagged,
        })
        stats["통과"] += 1

    # 경로 B 환각 폐기율 — 유니버스에 아예 없는 티커 비율 (§4 "1번 폐기율 로그" 요구사항)
    b_not_in_universe = sum(1 for t in tickers_b if t and t not in valid_tickers)
    stats["경로B_폐기율"] = round(b_not_in_universe / len(tickers_b) * 100, 1) if tickers_b else 0.0

    return out, stats


def critique_pass(theme: dict, members: list[dict], names: dict[str, str], api_key: str) -> dict[str, str]:
    """SPEC §3.4 2차 비판 패스. 1차 통과 목록을 같은 LLM에게 다시 보여주고 근거가
    약한 후보를 지적하게 한다. 삭제하지 않고 flagged=1만 세팅해 사람 검토 우선순위를
    올린다 (§7). 반환값은 {ticker: reason}."""
    if not members:
        return {}
    desc = _theme_description(theme)
    listing = "\n".join(
        f"- {m['ticker']} ({names.get(m['ticker'], '')}): {m['evidence']}" for m in members
    )
    prompt = f"""{desc}

아래는 위 테마의 1차 통과 후보 목록과 각각의 근거다.

{listing}

이 중 해당 테마 관련 매출이 전체의 10% 미만일 것으로 보이는 기업, 또는 근거가
막연하거나 사실관계가 의심스러워 제외를 검토해야 할 기업을 지적하시오. 확실히
문제없는 기업은 포함하지 마시오.

반드시 아래 JSON 형식으로만 답하시오:
{{"flag": [{{"ticker": "...", "reason": "..."}}]}}"""
    parsed = _openai_json(
        prompt,
        "당신은 까다로운 산업 분석가입니다. 근거가 약하거나 사실과 다른 후보를 엄격히 지적합니다.",
        api_key,
    )
    if not parsed or not isinstance(parsed.get("flag"), list):
        return {}
    out: dict[str, str] = {}
    for item in parsed["flag"]:
        ticker = str(item.get("ticker", "")).strip().upper()
        if ticker:
            out[ticker] = str(item.get("reason", "")).strip()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme-id", nargs="*", default=None, help="특정 테마만 (비우면 전체)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        sys.exit(1)

    themes = load_themes(args.theme_id)
    if not themes:
        _log("대상 테마 없음")
        sys.exit(1)
    _log(f"대상 테마 {len(themes)}개: {', '.join(t['id'] for t in themes)}")

    universe, names = build_universe_and_names()
    valid_tickers = {it["symbol"].upper() for it in universe}
    _log(f"유니버스 {len(universe)}종목 (경로 A 제약용)")

    conn = get_db()
    ensure_schema(conn)

    # 시가총액 확인은 Phase 0이 이미 캐시해둔 info_payload를 재사용 (SPEC §4 step2)
    cap_lookup: dict[str, float] = {}
    for ticker, info_payload in conn.execute("SELECT ticker, info_payload FROM fetch_status").fetchall():
        if not info_payload:
            continue
        try:
            cap = json.loads(info_payload).get("marketCap")
            if cap:
                cap_lookup[ticker] = float(cap)
        except (TypeError, ValueError):
            continue
    _log(f"시가총액 캐시 {len(cap_lookup)}종목")

    run_id = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    start_mapping_run(conn, run_id, datetime.utcnow().isoformat(), OPENAI_MODEL, PROMPT_VERSION)

    overall_stats: dict[str, dict] = {}
    for theme in themes:
        theme_id = theme["id"]
        _log(f"=== {theme_id} ({theme['name_ko']}) ===")

        raw_a = path_a_universe_constrained(theme, universe, names, api_key)
        _log(f"  경로 A 후보: {len(raw_a)}개")
        raw_b = path_b_free_generation(theme, api_key)
        _log(f"  경로 B 후보: {len(raw_b)}개")

        validated, stats = validate_members(raw_a, raw_b, valid_tickers, cap_lookup)
        _log(f"  검증 결과: {stats}")
        if stats["경로B_폐기율"] > HALLUCINATION_WARN_RATE * 100:
            _log(f"  ⚠ 경로 B 환각 폐기율 {stats['경로B_폐기율']}% — 30% 초과, 프롬프트 재검토 필요")

        critique = critique_pass(theme, validated, names, api_key)
        newly_flagged = 0
        for m in validated:
            if m["ticker"] in critique:
                if not m["flagged"]:
                    newly_flagged += 1
                m["flagged"] = True
                _log(f"  비판 패스 flagged: {m['ticker']} — {critique[m['ticker']]}")
        stats["비판패스_flagged"] = len(critique)
        overall_stats[theme_id] = stats

        created_at = datetime.utcnow().isoformat()
        for m in validated:
            insert_theme_member(conn, theme_id, m["ticker"], m["market"], m["stage"],
                                 m["evidence"], m["linkage"], m["confidence"], m["flagged"],
                                 run_id, created_at)

    finish_mapping_run(conn, run_id, datetime.utcnow().isoformat(), overall_stats)
    conn.close()

    print("\n" + "=" * 60)
    print(f"  테마 매핑 완료 — run_id={run_id}")
    print("=" * 60)
    for theme_id, stats in overall_stats.items():
        print(f"  {theme_id:25s} 통과 {stats['통과']:>3d}  "
              f"(티커실패 {stats['티커실재실패']} / 시총미달 {stats['시가총액미달']} / "
              f"evidence탈락 {stats['evidence품질실패']} / 경로B폐기율 {stats['경로B_폐기율']}% / "
              f"비판패스flagged {stats.get('비판패스_flagged', 0)})")
    print("=" * 60)
    print("이 run은 approved=0 상태입니다 — 사람이 검토 후 승인해야 테마 보드에 반영됩니다.")


if __name__ == "__main__":
    main()
