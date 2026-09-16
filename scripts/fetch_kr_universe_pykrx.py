"""pykrx로 KR 전종목 유니버스를 받아 JSON으로 떨어뜨린다.

**이 스크립트는 격리된 가상환경에서 실행된다.**
pykrx 1.2.8은 pandas<3.0을 요구하는데 본 저장소는 pandas==3.0.2를 쓴다.
같은 환경에 두면 pip이 에러 대신 pykrx를 1.0.51까지 조용히 낮춰버리고,
그 버전에는 KRX 로그인 기능(auth 모듈)이 아예 없어 모든 조회가 실패한다
(2026-09-14 확인 - 그동안 이 실패가 "GitHub Actions IP 차단"으로 오진돼 있었다).

그래서 이 파일은 저장소의 다른 모듈을 import하지 않는다. 의존성은 pykrx와
pandas뿐이며, 결과는 JSON 파일로만 주고받는다.

사용법:
    python scripts/fetch_kr_universe_pykrx.py --out data/kr_universe.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

# 3000억(2026-09-16 변경, 이전 5000억). 이 파일은 두 곳이 같이 쓴다:
#   테마 매핑  - 넓을수록 좋다. 로봇·특수가스처럼 테마 순수 플레이가 중소형에 몰린
#                테마는 5000억 하한에서 후보 자체가 잘려 나갔다.
#   워치리스트 - 넓힌다고 좋지 않다. 주간 재수집 예산(기본 60-250종목)이 정해져 있어
#                종목이 늘면 한 바퀴 도는 데 걸리는 주가 늘어난다.
# 그래서 파일은 3000억으로 넓게 받고, 스크리닝 쪽만 watchlist_collector.KR_SCREEN_MIN_CAP
# (5000억)으로 다시 거른다. 실측 분포(2026-09-15): 5000억 482 / 3000억 680종목.
MIN_CAP_DEFAULT = 300_000_000_000

# 우선주 제외. KRX 종목코드는 6번째 자리가 보통주면 '0', 우선주면 5/7/K/L/M 등이다.
# 우선주는 보통주와 같은 회사라서 남겨두면 한 회사가 두 번 집계된다 - 실적 축이
# "소속 중 몇 개가 시장 중앙값을 넘나"를 세므로 비율이 그만큼 왜곡된다.
# (2026-09-14 실측: 삼성전자우가 삼성전자와 나란히 워치리스트에 올라와 있었다.
#  테마 매핑에는 0건 편입 - LLM이 이름을 보고 걸러냈지만 규칙으로 막는 게 맞다.)
# 끝자리가 0인 신규/분할 상장 코드(0126Z0 삼성에피스홀딩스, 0009K0 에임드바이오,
# 0220W0 한화머시너리앤서비스홀딩스)는 보통주라 그대로 통과한다.
def _is_common_share(code: str) -> bool:
    return code.endswith("0")


# 코드 규칙과 사명이 어긋나면 조용히 넘기지 않고 보고한다 - KRX가 코드 체계를
# 바꾸면 규칙만 믿다가 보통주를 통째로 버리게 될 수 있다.
_PREF_NAME = re.compile(r"우(B|\(전환\))?$")
SUFFIX = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}


def _log(msg: str) -> None:
    print(f"[kr_universe] {msg}", flush=True)


def _prev_business_date(base: datetime | None = None) -> str:
    """직전 영업일. 당일을 쓰지 않는 이유: 장 마감 전에는 시세가 없어 0행이
    돌아오고, 그것이 조회 실패와 구분되지 않는다."""
    d = (base or datetime.now()) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=None, help="YYYYMMDD (비우면 직전 영업일)")
    ap.add_argument("--min-cap", type=int, default=MIN_CAP_DEFAULT)
    args = ap.parse_args()

    import pykrx
    from pykrx import stock as ps

    ver = getattr(pykrx, "__version__", "unknown")
    _log(f"pykrx 버전 {ver}")
    if not (os.getenv("KRX_ID") and os.getenv("KRX_PW")):
        _log("경고 - KRX_ID/KRX_PW 미설정. 로그인이 필요한 조회는 실패한다.")

    try:
        from pykrx.website.comm import auth
        sess = auth.build_krx_session()
        _log(f"KRX 세션: {'생성됨' if sess else 'None'}")
    except ImportError:
        _log("경고 - pykrx에 auth 모듈이 없다(구버전). 격리 환경 설치를 확인할 것.")
    except Exception as e:
        _log(f"로그인 시도 중 예외: {type(e).__name__}: {str(e)[:200]}")

    date = args.date or _prev_business_date()
    _log(f"기준일 {date} / 시총 하한 {args.min_cap:,}")

    items: list[dict] = []
    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = ps.get_market_cap_by_ticker(date, market=market)
        except Exception as e:
            _log(f"{market} 조회 실패: {type(e).__name__}: {str(e)[:200]}")
            return 2
        if df is None or len(df) == 0:
            _log(f"{market} 0행 - 실패로 간주")
            return 2

        big = df[df["시가총액"] >= args.min_cap]
        # 시총 구간 분포도 남긴다 - 하한을 어디에 둘지는 유니버스 크기와
        # 주간 스크리닝 예산(REFRESH_BUDGET)의 트레이드오프라 실측이 필요하다.
        buckets = [(1_000_000_000_000, "1조+"), (500_000_000_000, "5000억+"),
                   (300_000_000_000, "3000억+"), (200_000_000_000, "2000억+")]
        dist = " / ".join(f"{lbl} {int((df['시가총액'] >= th).sum())}" for th, lbl in buckets)
        _log(f"{market}: 전체 {len(df)} / 하한 통과 {len(big)}   [분포] {dist}")
        dropped_pref = []
        mismatched = []
        for ticker, row in big.iterrows():
            code = str(ticker)
            try:
                name = ps.get_market_ticker_name(code)
            except Exception:
                name = code
            common = _is_common_share(code)
            looks_pref = bool(_PREF_NAME.search(name))
            if common == looks_pref:
                # 코드 규칙과 사명이 불일치 - 어느 쪽이든 사람이 봐야 한다.
                mismatched.append(f"{code} {name}")
            if not common:
                dropped_pref.append(f"{code} {name}")
                continue
            items.append({
                "market": "KR",
                "symbol": code,
                "yf_symbol": f"{code}{SUFFIX[market]}",
                "name": name,
                "market_cap": int(row["시가총액"]),
                "exchange": market,
            })

        if dropped_pref:
            _log(f"  우선주 제외 {len(dropped_pref)}: {', '.join(dropped_pref)}")
        if mismatched:
            _log(f"  경고 - 코드규칙과 사명 불일치 {len(mismatched)}: {', '.join(mismatched)}")

    if not items:
        _log("수집 결과 0건 - 파일을 쓰지 않는다(기존 폴백 유지)")
        return 2

    payload = {
        "fetched_at": datetime.now().isoformat(),
        "base_date": date,
        "min_cap": args.min_cap,
        "pykrx_version": ver,
        "count": len(items),
        "items": items,
    }
    out = args.out
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    _log(f"저장 완료 {out} - 총 {len(items)}종목 "
         f"(KOSPI {sum(1 for i in items if i['exchange']=='KOSPI')}, "
         f"KOSDAQ {sum(1 for i in items if i['exchange']=='KOSDAQ')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
