"""yfinance에 사업정보가 없는 한국 종목을 DART로 채운다 (분기 재설계 4-1 기업개황).

2026-09-17 기준 KR 유니버스 664종목 중 84종목(81개가 코스닥)은 yfinance에 산업분류·사업
설명이 아예 없다. 티씨케이·에코프로·주성엔지니어링 같은 테마 핵심 종목이 포함돼 있어,
매핑이 이 종목들을 이름만 보고 판단하게 된다(사명 기반 추측 오류의 원천).

채우는 값 (data/kr_profiles.json)
  industry      KSIC 중분류 이름 (DART 기업개황의 업종코드 앞 두 자리)
  summary       사업의 개요 앞 140자 (매핑 프롬프트용)
  summary_long  사업의 개요 2500자 (근거 감사용)
  source        "dart" - yfinance 원본과 구별

사업의 개요는 가장 최근 사업보고서 원문(II. 사업의 내용 > 1. 사업의 개요)에서 뽑는다.
한국어 원문이다 - 다른 종목의 요약은 yfinance 영문이지만, 한국 기업을 한국어 원문으로
설명하는 편이 매핑·감사 모두 더 정확하다.

Usage:
  python scripts/fill_kr_profiles_from_dart.py              # 사업정보 없는 종목 전부
  python scripts/fill_kr_profiles_from_dart.py --tickers 064760 086520
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from collectors import dart_client as dart

PROFILES = ROOT / "data" / "kr_profiles.json"
UNIVERSE = ROOT / "data" / "kr_universe.json"
CORP_CACHE = ROOT / "data" / "dart_corp_codes.json"

# 한국표준산업분류(KSIC) 10차 중분류. DART 업종코드 앞 두 자리로 찾는다.
KSIC_DIVISION = {
    "01": "농업", "02": "임업", "03": "어업",
    "05": "석탄, 원유 및 천연가스 광업", "06": "금속 광업", "07": "비금속광물 광업", "08": "광업 지원 서비스업",
    "10": "식료품 제조업", "11": "음료 제조업", "12": "담배 제조업", "13": "섬유제품 제조업",
    "14": "의복 및 모피제품 제조업", "15": "가죽, 가방 및 신발 제조업", "16": "목재 및 나무제품 제조업",
    "17": "펄프, 종이 및 종이제품 제조업", "18": "인쇄 및 기록매체 복제업", "19": "코크스 및 석유정제품 제조업",
    "20": "화학물질 및 화학제품 제조업", "21": "의료용 물질 및 의약품 제조업", "22": "고무 및 플라스틱제품 제조업",
    "23": "비금속 광물제품 제조업", "24": "1차 금속 제조업", "25": "금속 가공제품 제조업",
    "26": "전자부품, 컴퓨터, 영상, 음향 및 통신장비 제조업", "27": "의료, 정밀, 광학 기기 및 시계 제조업",
    "28": "전기장비 제조업", "29": "기타 기계 및 장비 제조업", "30": "자동차 및 트레일러 제조업",
    "31": "기타 운송장비 제조업", "32": "가구 제조업", "33": "기타 제품 제조업", "34": "산업용 기계 및 장비 수리업",
    "35": "전기, 가스, 증기 및 공기 조절 공급업", "36": "수도업", "37": "하수, 폐수 및 분뇨 처리업",
    "38": "폐기물 수집, 운반, 처리 및 원료 재생업", "39": "환경 정화 및 복원업",
    "41": "종합 건설업", "42": "전문직별 공사업",
    "45": "자동차 및 부품 판매업", "46": "도매 및 상품 중개업", "47": "소매업",
    "49": "육상 운송 및 파이프라인 운송업", "50": "수상 운송업", "51": "항공 운송업", "52": "창고 및 운송관련 서비스업",
    "55": "숙박업", "56": "음식점 및 주점업",
    "58": "출판업", "59": "영상·오디오 기록물 제작 및 배급업", "60": "방송업", "61": "우편 및 통신업",
    "62": "컴퓨터 프로그래밍, 시스템 통합 및 관리업", "63": "정보서비스업",
    "64": "금융업", "65": "보험 및 연금업", "66": "금융 및 보험 관련 서비스업", "68": "부동산업",
    "70": "연구개발업", "71": "전문 서비스업", "72": "건축 기술, 엔지니어링 및 기타 과학기술 서비스업",
    "73": "기타 전문, 과학 및 기술 서비스업", "74": "사업시설 관리 및 조경 서비스업", "75": "사업 지원 서비스업",
    "76": "임대업", "84": "공공 행정, 국방 및 사회보장 행정", "85": "교육 서비스업", "86": "보건업",
    "87": "사회복지 서비스업", "90": "창작, 예술 및 여가관련 서비스업", "91": "스포츠 및 오락관련 서비스업",
    "94": "협회 및 단체", "95": "개인 및 소비용품 수리업", "96": "기타 개인 서비스업",
}


def _log(msg: str) -> None:
    print(f"[dart-profile] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", default=None)
    args = ap.parse_args()

    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    universe = {i["symbol"]: i for i in json.loads(UNIVERSE.read_text(encoding="utf-8"))["items"]}
    if args.tickers:
        todo = args.tickers
    else:
        todo = [s for s in universe if not (profiles.get(s) or {}).get("industry")
                or not (profiles.get(s) or {}).get("summary")]
    corp = dart.load_corp_codes(CORP_CACHE)
    _log(f"사업정보 보강 대상 {len(todo)}종목")

    end = date.today()
    bgn = end - timedelta(days=550)  # 최근 사업보고서가 들어오도록 1년 반
    filled = no_corp = no_overview = 0
    for t in todo:
        name = universe.get(t, {}).get("name", "")
        cc = corp.get(t)
        if not cc:
            no_corp += 1
            _log(f"  {t} {name}: DART 기업코드 없음")
            continue
        rec = dict(profiles.get(t) or {})
        info = dart.fetch_company(cc)
        code = str(info.get("induty_code") or "")
        if code and not rec.get("industry"):
            rec["industry"] = KSIC_DIVISION.get(code[:2], f"KSIC {code}")
            rec["industry_code"] = code
        time.sleep(0.15)

        overview = None
        rcept = dart.latest_annual_report_no(cc, bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        time.sleep(0.15)
        if rcept:
            overview = dart.business_overview(rcept)
            time.sleep(0.15)
        if overview:
            rec["summary"] = overview[:140]
            rec["summary_long"] = overview[:2500]
        else:
            no_overview += 1
        if rec != profiles.get(t):
            rec["source"] = "dart"
            profiles[t] = rec
            filled += 1
        _log(f"  {t} {name}: 업종 {rec.get('industry', '-')} / 개요 {len(overview) if overview else 0}자")

    PROFILES.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    _log(f"완료: 보강 {filled} / 기업코드 없음 {no_corp} / 사업의 개요 못 찾음 {no_overview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
