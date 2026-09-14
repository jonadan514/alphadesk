"""KR 유니버스를 어느 소스에서 받을 수 있는지 실측한다.

배경 (2026-09-14):
저장소 주석은 오랫동안 "공공데이터포털·pykrx 둘 다 GitHub Actions에서 IP 차단"
이라고 단정해 왔으나, 실제 실패 메시지는 아래였다.

    KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다.

pykrx 1.2.8은 KRX 웹사이트 로그인을 요구한다(website/comm/auth.py). 한국 IP인
로컬 PC에서도 동일하게 실패하므로 IP 차단이 원인이라는 진단은 성립하지 않는다.
이 스크립트는 자격증명을 넣은 상태에서 각 소스가 실제로 되는지 확인해 그
주석을 사실로 교체하기 위한 것이다.

자격증명은 절대 출력하지 않는다(설정 여부와 길이만 보고).
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

MIN_CAP = 200_000_000_000  # 2000억 - watchlist_collector.KR_MIN_CAP 과 동일


def _log(msg: str) -> None:
    print(f"[probe] {msg}", flush=True)


def _recent_business_date() -> str:
    """직전 영업일 추정. 당일을 쓰지 않는 이유: 장 마감 전에는 그날 시세가
    아직 없어 0행이 돌아오고, 그것이 '조회 실패'와 구분되지 않는다."""
    d = datetime.now() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def probe_credentials() -> bool:
    ok = True
    for k in ("KRX_ID", "KRX_PW"):
        v = os.getenv(k)
        _log(f"{k}: {'설정됨(길이 ' + str(len(v)) + ')' if v else '미설정'}")
        if not v:
            ok = False
    return ok


def probe_pykrx(date: str) -> None:
    _log("=" * 50)
    _log(f"pykrx 조회 시도 (기준일 {date})")
    try:
        from pykrx import stock as ps
    except Exception as e:
        _log(f"  import 실패: {type(e).__name__}: {e}")
        return

    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = ps.get_market_cap_by_ticker(date, market=market)
            if df is None or len(df) == 0:
                _log(f"  {market}: 0행 - 실패")
                continue
            big = df[df["시가총액"] >= MIN_CAP]
            _log(f"  {market}: 전체 {len(df)}종목 / 시총 2000억 이상 {len(big)}종목")
        except Exception as e:
            _log(f"  {market}: 실패 {type(e).__name__}: {str(e)[:160]}")


def probe_data_go_kr() -> None:
    _log("=" * 50)
    key = os.getenv("DATA_GO_KR_API_KEY")
    _log(f"공공데이터포털 조회 시도 (키 {'있음' if key else '없음'})")
    if not key:
        return
    try:
        from src.collectors.watchlist_collector import _kr_universe_public_api
        u = _kr_universe_public_api()
        _log(f"  결과: {len(u) if u else 0}종목")
    except Exception as e:
        _log(f"  실패 {type(e).__name__}: {str(e)[:160]}")


def probe_static() -> None:
    _log("=" * 50)
    from src.collectors.kr_kospi_list import KOSPI_STOCKS, CORE_STOCKS
    _log(f"정적 리스트(현재 폴백): {len(KOSPI_STOCKS)}종목 "
         f"(손작성 {len(CORE_STOCKS)} + 코스피200 생성분 {len(KOSPI_STOCKS) - len(CORE_STOCKS)})")


def main() -> int:
    _log(f"실행 시각 {datetime.now().isoformat()}")
    probe_credentials()
    date = os.getenv("PROBE_DATE") or _recent_business_date()
    try:
        probe_pykrx(date)
    except Exception:
        traceback.print_exc()
    try:
        probe_data_go_kr()
    except Exception:
        traceback.print_exc()
    probe_static()
    _log("=" * 50)
    _log("완료 - 위 결과로 kr_kospi_list.py / watchlist_collector.py 주석을 갱신할 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
