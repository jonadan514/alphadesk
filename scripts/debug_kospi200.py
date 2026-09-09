"""KOSPI 200 구성종목을 Wikipedia에서 받아올 수 있는지 검증 (읽기 전용) - 확인 후 삭제.

한국 유니버스가 정적 98종목이라 테마별 표본이 얇은 문제의 해법 후보.
pykrx·공공데이터포털은 GitHub Actions IP에서 막힌 것이 확인됐지만, Wikipedia는
한국 인프라가 아니라 차단 대상이 아닐 가능성이 있다(미국 S&P500도 같은 방식).
"""
import re
import sys
import urllib.request

URL = "https://en.wikipedia.org/wiki/KOSPI_200"
UA = "Mozilla/5.0 (compatible; alphadesk-research/1.0)"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
            print(f"HTTP {r.status}, {len(html):,} bytes")
    except Exception as e:
        print(f"접근 실패: {type(e).__name__}: {e}")
        sys.exit(1)

    # 6자리 종목코드 추출 - 표 구조에 의존하지 않게 코드 패턴으로만 센다
    codes = re.findall(r"\b(\d{6})\b", html)
    uniq = sorted(set(codes))
    print(f"6자리 코드 후보: 총 {len(codes)}개, 고유 {len(uniq)}개")
    print(f"샘플 10개: {uniq[:10]}")

    # 알려진 대형주가 포함되는지로 진짜 구성종목 표인지 확인
    known = {"005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차",
             "035420": "NAVER", "051910": "LG화학"}
    hit = {c: n for c, n in known.items() if c in uniq}
    print(f"알려진 대형주 포함: {len(hit)}/{len(known)} -> {hit}")

    # 현재 정적 리스트와 비교
    sys.path.insert(0, ".")
    from src.collectors.kr_kospi_list import KOSPI_STOCKS
    cur = {c for c, _, _ in KOSPI_STOCKS}
    print(f"\n현재 정적 리스트: {len(cur)}종목")
    print(f"위키에만 있는 코드(신규 확보 가능): {len(set(uniq) - cur)}개")
    print(f"현재 리스트에만 있는 코드(위키 미포함): {len(cur - set(uniq))}개")
    print(f"  -> {sorted(cur - set(uniq))[:15]}")


if __name__ == "__main__":
    main()
