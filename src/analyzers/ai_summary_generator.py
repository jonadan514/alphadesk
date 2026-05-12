import os
import re
import time
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from src.analyzers.ai_response_parser import parse_ai_response, FALLBACK

load_dotenv()

MODEL = "gemini-2.5-flash"

AI_OUTPUT_SCHEMA = {
    "thesis":         "한 문단 투자 테제 (한국어)",
    "catalysts":      ["상승 촉매 1", "상승 촉매 2", "상승 촉매 3"],
    "bear_cases":     ["하락 리스크 1", "하락 리스크 2"],
    "recommendation": "BUY | HOLD | SELL",
    "confidence":     75,
}

KR_AI_OUTPUT_SCHEMA = {
    "thesis":         "한 문단 투자 테제 (한국어, 2-3문장)",
    "catalysts":      ["상승 촉매 1 (구체적 수치/일정 포함)", "상승 촉매 2", "상승 촉매 3"],
    "bear_cases":     ["하락 리스크 1", "하락 리스크 2"],
    "target_price":   90000,
    "recommendation": "BUY | HOLD | SELL",
    "confidence":     75,
}

PROMPT_TEMPLATE = """
당신은 피터 린치(Peter Lynch)와 윌리엄 오닐(William O'Neil) 투자 철학을 결합한 미국 주식 전문 애널리스트입니다.

[피터 린치 관점]
- PEG 비율(PER ÷ 이익성장률)이 1 미만인 종목을 선호합니다
- 이익 성장 스토리가 명확하고 이해하기 쉬운 비즈니스를 중시합니다
- 성장성 대비 저평가된 종목(성장주, 회복주, 자산주)을 찾습니다

[윌리엄 오닐 CANSLIM 관점]
- 최근 분기 EPS 성장률 +25% 이상을 강하게 선호합니다
- 52주 신고가 근처에서 거래량 동반 돌파하는 종목을 선호합니다
- 손절 원칙: 매수가 대비 -7~8% 하락 시 즉시 손절

Ticker: {ticker}
Stock Data:
{stock_data}

아래 스키마에 맞는 JSON을 반환하세요:
{schema}

Rules:
- thesis: PEG 비율, 이익 성장 스토리, 52주 고점 대비 위치를 중심으로 한 투자 테제 (한국어 2-3문장)
- catalysts: 구체적 수치 포함 상승 촉매 3개 (한국어)
- bear_cases: 하락 리스크 2개 — PEG 재평가 위험, 성장 둔화 가능성 포함 (한국어)
- recommendation: BUY, HOLD, SELL 중 하나 (PEG < 1 + EPS 성장 강할수록 BUY 선호)
- confidence: 0-100 정수

JSON 객체만 반환하고 다른 텍스트는 절대 포함하지 마세요.
""".strip()

KR_PROMPT_TEMPLATE = """
당신은 피터 린치(Peter Lynch)와 윌리엄 오닐(William O'Neil) 투자 철학을 한국 주식시장(KOSPI)에 적용하는 전문 애널리스트입니다.

[피터 린치 관점 — 한국 시장 적용]
- PEG 비율(PER ÷ 이익성장률) 0.7 미만이면 매력적 (한국 시장은 전통적으로 저PER 경향)
- 외국인·기관 수급과 환율 영향을 성장 스토리와 결합해 분석
- 실적 개선이 지속되는 중소형 성장주를 선호

[윌리엄 오닐 CANSLIM 관점 — 한국 시장 적용]
- 최근 분기 EPS 성장률 +25% 이상 종목 우선
- 52주 신고가 근처에서 외국인·기관 동반 매수 확인
- 손절 원칙: 매수가 대비 -7~8% 하락 시 즉시 손절

종목: {ticker} ({name})
섹터: {sector}

=== 시장 컨텍스트 ===
{market_context}

=== 종목 데이터 ===
{stock_data}

아래 스키마에 맞는 JSON을 반환하세요:
{schema}

규칙:
- thesis: 한국 시장 특성(외국인/기관 수급, 환율, 밸류에이션)을 반영한 투자 테제 (한국어 2-3문장)
- catalysts: 구체적 수치나 일정이 포함된 상승 촉매 3개 (한국어)
- bear_cases: 하락 리스크 2개 (한국어), 한국 시장 특유의 리스크(환율, 정치, 외국인 이탈) 포함
- target_price: 현재가 기준 6-12개월 목표 주가 (원화 정수, 너무 보수적이거나 공격적이지 않게)
- recommendation: BUY, HOLD, SELL 중 하나
- confidence: 0-100 정수

JSON 객체만 반환하고 다른 텍스트는 절대 포함하지 마세요.
""".strip()


class GeminiSummaryGenerator:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = None

    def generate(self, ticker: str, stock_data: dict, market: str = "US",
                 market_context: str = "", name: str = "", sector: str = "") -> dict:
        if self._client is None:
            return {**FALLBACK, "_reason": "GOOGLE_API_KEY not set"}

        if market == "KR":
            prompt = KR_PROMPT_TEMPLATE.format(
                ticker=ticker,
                name=name or ticker,
                sector=sector or stock_data.get("sector", ""),
                market_context=market_context or "KOSPI 시장",
                stock_data=json.dumps(stock_data, ensure_ascii=False, default=str),
                schema=json.dumps(KR_AI_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
            )
        else:
            prompt = PROMPT_TEMPLATE.format(
                ticker=ticker,
                stock_data=json.dumps(stock_data, ensure_ascii=False, default=str),
                schema=json.dumps(AI_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
            )

        for attempt in range(4):
            try:
                response = self._client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                text = response.text or ""
                result = parse_ai_response(text)
                result["ticker"] = ticker
                if response.usage_metadata:
                    result["_tokens_in"]  = response.usage_metadata.prompt_token_count or 0
                    result["_tokens_out"] = response.usage_metadata.candidates_token_count or 0
                time.sleep(3)  # RPM 한도 초과 방지
                return result
            except Exception as exc:
                msg = str(exc)
                # 429 rate-limit: parse retryDelay and wait
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    m = re.search(r"retryDelay.*?(\d+)s", msg)
                    wait = int(m.group(1)) + 2 if m else 15 * (attempt + 1)
                    print(f"[GeminiSummaryGenerator] {ticker} rate-limit, {wait}s 대기 후 재시도 ({attempt+1}/3)")
                    time.sleep(wait)
                    continue
                if "503" in msg or "UNAVAILABLE" in msg:
                    wait = 10 * (attempt + 1)
                    print(f"[GeminiSummaryGenerator] {ticker} 서버 과부하, {wait}s 대기 후 재시도 ({attempt+1}/3)")
                    time.sleep(wait)
                    continue
                print(f"[GeminiSummaryGenerator] {ticker} error: {exc}")
                return {**FALLBACK, "ticker": ticker, "_reason": msg}
        return {**FALLBACK, "ticker": ticker, "_reason": "max retries exceeded"}
