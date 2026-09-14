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
import sys
from datetime import datetime, timedelta

# 5000억. watchlist_collector.KR_MIN_CAP(2000억)보다 높게 잡은 이유:
# 2000억이면 910종목으로 미국(S&P500, 503)의 1.8배가 돼 시장 간 비교 기준이
# 어긋나고, 테마 매핑 청크가 4 -> 8로 두 배가 된다. 5000억이면 487종목으로
# 미국과 규모가 비슷해지면서도 얇은 테마의 핵심 후보(솔브레인 2.62조,
# 동진쎄미켐 2.16조, 클래시스 2.02조, 씨젠 1.44조, 경동나비엔 0.88조,
# 루닛 0.63조)는 대부분 포함된다. 2026-09-14 실측 분포에 근거한 선택.
MIN_CAP_DEFAULT = 500_000_000_000
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
        for ticker, row in big.iterrows():
            code = str(ticker)
            try:
                name = ps.get_market_ticker_name(code)
            except Exception:
                name = code
            items.append({
                "market": "KR",
                "symbol": code,
                "yf_symbol": f"{code}{SUFFIX[market]}",
                "name": name,
                "market_cap": int(row["시가총액"]),
                "exchange": market,
            })

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
