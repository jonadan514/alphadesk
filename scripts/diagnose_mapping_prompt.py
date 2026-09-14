"""테마 매핑이 명백한 후보를 놓치는 원인을 A/B로 가린다.

배경(2026-09-14): 유니버스를 474종목으로 넓힌 뒤에도 아래가 편입되지 않았다.
  의료기기: 클래시스(2.09조) 씨젠(1.47조) 루닛(0.63조)
  특수가스: 동진쎄미켐(2.08조) 원익QnC(0.69조) 티씨케이(2.88조)
  데이터센터 냉각: 경동나비엔(0.88조) GST(0.84조)
모두 유니버스 안에 있다. 반면 같은 프롬프트로 medical_device는 US 17종목을
잡았다 - 테마 정의 문제라면 양쪽 다 못 잡아야 하므로, LLM이 한국 기업명만
보고는 사업 내용을 모른다는 가설이 남는다.

검증하는 변형:
  A(현재)  : "- 214150 (KR) 클래시스"
  B(키워드): note가 있어도 keywords_ko를 함께 보낸다
             (현재 코드는 note가 있으면 키워드를 버린다 - 그 note는 테마
              정의가 아니라 "min_articles 하향 조정" 같은 운영 메모다)
  C(산업)  : 후보 목록에 yfinance industry를 붙인다
             "- 214150 (KR) 클래시스 [Medical Devices]"
  D(B+C)
  E(요약)  : industry에 더해 사업요약 한 줄까지 붙인다
             "- 214150 (KR) 클래시스 [Medical Devices] CLASSYS Inc. provides medical aesthetics devices..."

주의: 티씨케이·GST처럼 yfinance에 산업·요약이 아예 없는 종목은 C/D/E로도
보완되지 않는다. 그런 종목이 몇 개나 되는지도 함께 보고한다.

각 변형이 목표 종목을 몇 개나 잡는지, finish_reason이 length인지(2000토큰
절단 여부), 토큰 사용량을 함께 보고한다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

MODEL = "gpt-4o-mini"

# 유니버스 안에 있는데 편입되지 않은 종목들 - 이 실험의 정답지
TARGETS = {
    "medical_device": {"214150": "클래시스", "096530": "씨젠", "328130": "루닛"},
    "specialty_gas": {"005290": "동진쎄미켐", "074600": "원익QnC", "064760": "티씨케이"},
    "datacenter_cooling": {"009450": "경동나비엔", "083450": "GST"},
}


def _log(m: str) -> None:
    print(f"[diag] {m}", flush=True)


def call(prompt: str, api_key: str) -> tuple[dict | None, str, dict]:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "당신은 신중한 산업 분석가입니다. 주어진 목록에 없는 기업은 답하지 않습니다."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    r.raise_for_status()
    d = r.json()
    ch = d["choices"][0]
    try:
        parsed = json.loads(ch["message"]["content"])
    except Exception:
        parsed = None
    return parsed, ch.get("finish_reason", "?"), d.get("usage", {})


def build_prompt(theme: dict, chunk: list[dict], names: dict, profiles: dict,
                 with_keywords: bool, detail: str) -> str:
    """detail: "none" | "industry" | "summary" """
    head = [f"테마명: {theme['name_ko']} ({theme['name_en']})"]
    if theme.get("note"):
        head.append(f"설명: {theme['note']}")
    if with_keywords or not theme.get("note"):
        kws = ", ".join(theme.get("keywords_ko", []))
        if kws:
            head.append(f"관련 키워드: {kws}")
    desc = "\n".join(head)

    lines = []
    for it in chunk:
        s = f"- {it['symbol']} ({it['market']}) {names.get(it['symbol'], '')}"
        if with_sector:
            sec = sectors.get(it["symbol"])
            if sec:
                s += f" [{sec}]"
        lines.append(s)
    listing = "\n".join(lines)

    from scripts.map_theme_companies import MEMBER_FIELDS_INSTRUCTION
    return f"""{desc}

아래 상장기업 목록에서 위 테마에 실제로 속하는 기업만 고르시오. 목록에 없는
기업은 절대 답하지 마시오.

목록:
{listing}

{MEMBER_FIELDS_INSTRUCTION}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="data/kr_universe.json")
    ap.add_argument("--themes", nargs="*", default=None)
    args = ap.parse_args()
    # nargs="*"에 빈 값이 오면 []가 되어 default가 적용되지 않는다.
    # (워크플로에서 --themes 뒤에 아무것도 안 붙는 경우)
    themes = args.themes or list(TARGETS)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        return 1

    payload = json.loads(Path(args.universe).read_text(encoding="utf-8"))
    kr = payload["items"]
    names = {i["symbol"]: i["name"] for i in kr}

    # 섹터는 스크리닝이 이미 받아둔 값을 쓴다(yfinance 재조회 없이).
    profiles: dict[str, dict] = {}
    pf = ROOT / "data" / "kr_profiles.json"
    if pf.exists():
        profiles = json.loads(pf.read_text(encoding="utf-8"))
    _log(f"KR 유니버스 {len(kr)}종목 / 프로필 보유 {len(profiles)}종목")

    themes_yaml = yaml.safe_load((ROOT / "config" / "themes.yaml").read_text(encoding="utf-8"))
    tmap = {t["id"]: t for t in themes_yaml["themes"]}

    VARIANTS = [("A 현재", False, "none"), ("B +키워드", True, "none"),
                ("C +산업", False, "industry"), ("D +키워드+산업", True, "industry"),
                ("E +키워드+요약", True, "summary")]

    for tid in themes:
        theme = tmap[tid]
        targets = TARGETS.get(tid, {})
        # 목표 종목이 들어있는 200종목 청크만 실험한다(전체를 돌릴 필요가 없다).
        idxs = [i for i, it in enumerate(kr) if it["symbol"] in targets]
        if not idxs:
            _log(f"{tid}: 목표 종목이 유니버스에 없음 - 건너뜀")
            continue
        lo = max(0, (min(idxs) // 200) * 200)
        chunk = kr[lo:lo + 200]
        present = [c for c in targets if any(it["symbol"] == c for it in chunk)]
        _log("=" * 60)
        _log(f"{tid} ({theme['name_ko']}) - 청크 {lo}-{lo+len(chunk)} / 목표 {len(present)}종목 포함")

        no_prof = [c for c in present if not (profiles.get(c) or {}).get("industry")]
        if no_prof:
            _log(f"  참고: 목표 중 산업정보 없는 종목 {len(no_prof)}개 {[targets[c] for c in no_prof]}"
                 " - C/D/E로도 보완 불가")

        for label, kw, detail in VARIANTS:
            try:
                parsed, finish, usage = call(
                    build_prompt(theme, chunk, names, profiles, kw, detail), api_key)
            except Exception as e:
                _log(f"  {label}: 호출 실패 {type(e).__name__}: {str(e)[:120]}")
                continue
            got = {str(m.get("ticker")) for m in (parsed or {}).get("members", [])}
            hit = [targets[c] for c in present if c in got]
            _log(f"  {label:14s} 편입 {len(got):3d}개 / 목표적중 {len(hit)}/{len(present)} {hit} "
                 f"| finish={finish} | in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')}")
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
