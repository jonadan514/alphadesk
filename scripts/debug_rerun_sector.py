"""섹터 분석 재실행 확인용 임시 스크립트 - watchlist_candidates 연결 검증 후 삭제."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analyzers.sector_analyzer import analyze as analyze_us
from src.analyzers.kr_sector_analyzer import analyze as analyze_kr

print("=== US ===")
r = analyze_us()
total = sum(len(v) for v in r["sector_stocks"].values())
print(f"섹터 수: {len(r['sector_stocks'])}, 총 종목: {total}")
for etf, stocks in list(r["sector_stocks"].items())[:3]:
    print(f"  {etf}: {stocks[:3]}")

print("=== KR ===")
r2 = analyze_kr()
total2 = sum(len(v) for v in r2["sector_stocks"].values())
print(f"섹터 수: {len(r2['sector_stocks'])}, 총 종목: {total2}")
for sec, stocks in list(r2["sector_stocks"].items())[:3]:
    print(f"  {sec}: {stocks[:3]}")
