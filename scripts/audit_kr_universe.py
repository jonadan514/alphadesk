"""KR 유니버스의 종목코드 <-> 회사명 짝이 맞는지 검사한다.

왜 필요한가 (2026-09-10):
정적 리스트 최초 커밋부터 4건이 틀려 있었는데 아무 데서도 에러가 안 났다.
- 047050 '포스코홀딩스' -> 실제 포스코인터내셔널
- 018880 '한화'         -> 실제 한온시스템
- 002790 / 090430       -> 아모레퍼시픽홀딩스와 아모레퍼시픽이 뒤바뀜
재무 데이터는 티커 기준이라 정상 값이 오고, 이름을 쓰는 곳은 LLM 테마 매핑
하나뿐인데 LLM은 "한화니까 방산"처럼 **그럴듯한 오답**을 내놓는다. 그래서
틀린 이름이 에러가 아니라 조용한 오염으로 나타난다(방산 테마에 자동차
부품회사가 direct로 들어가 있었다).

왜 yfinance shortName으로 비교하지 않는가:
yfinance는 영문명("Hanon Systems")을 주고 우리는 한글명이라 문자열 비교가
성립하지 않는다. 그래서 한글명-코드 짝을 같은 행에서 제공하는 위키백과
코스피200 표를 기준으로 삼고, 불일치 건에 한해 yfinance 영문명을 함께
출력해 사람이 확인할 수 있게 한다.

사용법:
    python scripts/audit_kr_universe.py            # 검사 (불일치 있으면 exit 1)
    python scripts/audit_kr_universe.py --report-only   # 항상 exit 0
"""
from __future__ import annotations

import argparse
import html
import io
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

WIKI_URL = "https://ko.wikipedia.org/wiki/%EC%BD%94%EC%8A%A4%ED%94%BC_200"

ROW_RE = re.compile(
    r"<td[^>]*>\s*<a[^>]*title=\"([^\"]+)\"[^>]*>([^<]+)</a>\s*</td>"
    r"\s*<td[^>]*>(\d{6})</td>\s*<td[^>]*>([^<]*)</td>",
    re.S,
)

# 같은 회사인데 표기만 다른 경우(사명 변경, 약칭, 한글/영문 혼용).
# 여기 등록된 것만 조용히 통과시킨다 - 새 불일치는 반드시 보고되게 하기 위함.
KNOWN_ALIASES = {
    "009540": {"한국조선해양", "HD한국조선해양"},
    "028050": {"삼성엔지니어링", "삼성E&A"},
    "036570": {"엔씨소프트", "NC"},
    "079550": {"LIG넥스원", "LIG디펜스앤에어로스페이스"},
    "018260": {"삼성SDS", "삼성에스디에스"},
}


def _norm(s: str) -> str:
    return re.sub(r"[\s.\-()]", "", html.unescape(s)).upper()


def fetch_wiki_names() -> dict[str, str]:
    r = requests.get(WIKI_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    return {code: html.unescape(name).strip()
            for _t, name, code, _s in ROW_RE.findall(r.text)}


def yf_short_name(code: str, suffix: str) -> str:
    try:
        import yfinance as yf
        return str(yf.Ticker(f"{code}{suffix}").info.get("shortName") or "?")
    except Exception:
        return "(조회 실패)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="불일치가 있어도 exit 0 (CI 경고용)")
    ap.add_argument("--no-yfinance", action="store_true")
    args = ap.parse_args()

    from src.collectors.kr_kospi_list import KOSPI_STOCKS, yf_suffix

    wiki = fetch_wiki_names()
    lines: list[str] = []
    mismatches: list[tuple[str, str, str]] = []
    aliased = 0
    uncovered = 0

    for code, ours, _sector in KOSPI_STOCKS:
        w = wiki.get(code)
        if not w:
            uncovered += 1
            continue
        if _norm(w) == _norm(ours):
            continue
        if code in KNOWN_ALIASES and {ours, w} <= KNOWN_ALIASES[code]:
            aliased += 1
            continue
        mismatches.append((code, ours, w))

    lines.append(f"검사 대상 {len(KOSPI_STOCKS)}종목")
    lines.append(f"  위키 코스피200에 없어 검사 못 함: {uncovered}종목")
    lines.append(f"  사명 변경/약칭으로 허용(KNOWN_ALIASES): {aliased}건")
    lines.append(f"  불일치: {len(mismatches)}건")

    if mismatches:
        lines.append("")
        lines.append("아래는 코드와 회사명의 짝이 어긋났을 가능성이 있다.")
        lines.append("같은 회사의 표기 차이라면 KNOWN_ALIASES에 등록하고, 실제로")
        lines.append("다른 회사라면 kr_kospi_list.py를 고칠 것.")
        for code, ours, w in mismatches:
            extra = "" if args.no_yfinance else f"  yfinance='{yf_short_name(code, yf_suffix(code))}'"
            lines.append(f"  {code}  우리='{ours}'  위키='{w}'{extra}")

    report = "\n".join(lines)
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "kr_universe_audit.txt").write_text(report, encoding="utf-8")
    # 콘솔 인코딩(cp949)에서 한글이 깨져 보일 수 있어 파일에도 남긴다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)

    if mismatches and not args.report_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
