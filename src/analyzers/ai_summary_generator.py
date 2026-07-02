import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

try:
    from analyzers.ai_response_parser import parse_ai_response, validate_ai_response
except ImportError:
    try:
        from src.analyzers.ai_response_parser import parse_ai_response, validate_ai_response
    except ImportError:
        from .ai_response_parser import parse_ai_response, validate_ai_response

load_dotenv()

logger = logging.getLogger(__name__)


def _get_fallback_json(ticker: str = "", error_type: str = "unknown") -> dict:
    """안전한 fallback 응답. 에러 메시지를 절대 노출하지 않는다."""
    return {
        "thesis": "AI 분석을 완료하지 못했습니다. 데이터를 확인해주세요.",
        "catalysts": [],
        "bear_cases": [],
        "data_conflicts": [],
        "key_metrics": {},
        "recommendation": "HOLD",
        "confidence": 0,
    }


def build_analysis_prompt(ticker: str, data: dict, news: list,
                          macro_context: dict = None, lang: str = "ko") -> str:
    """모든 AI 프로바이더가 공통으로 사용하는 프롬프트 빌더."""
    if lang == "ko":
        lang_instruction = "모든 분석 내용을 한국어로 작성하세요."
    else:
        lang_instruction = "Write all analysis in English."

    # 매크로 컨텍스트
    if macro_context:
        regime = macro_context.get("regime", "N/A")
        regime_score = macro_context.get("regime_score", 0)
        vix = macro_context.get("vix", macro_context.get("vix_level", "N/A"))
        yield_spread = macro_context.get("yield_spread", "N/A")
        risk_warning = ""
        if regime in ("risk_off", "crisis"):
            risk_warning = "\n⚠️ 현재 RISK_OFF/CRISIS 환경: BUY 기준을 높이고, 하락 시나리오 비중을 강화하세요."

        macro_section = f"""
## 1. 매크로 환경
- 시장 체제: {regime} (점수: {regime_score:.2f})
- VIX: {vix}
- 10Y 금리: {macro_context.get('dgs10', 'N/A')}%
- 장단기 금리차 (10Y-2Y): {yield_spread}%
- 수익률 곡선 스프레드 (10Y-13W): {macro_context.get('yield_spread_10y13w', yield_spread)}
- 시장 Breadth: {macro_context.get('breadth', 'N/A')}
- 크레딧 리스크: {macro_context.get('credit', 'N/A')}
- Fear & Greed: {macro_context.get('fear_greed', 'N/A')}
- 실질금리: {macro_context.get('real_rate', 'N/A')}%
- 구리/금 신호: {macro_context.get('copper_gold', 'N/A')}
- 적응형 손절: {macro_context.get('stop_loss', 'N/A')}{risk_warning}
"""
    else:
        macro_section = "\n## 1. 매크로 환경\n매크로 데이터 미제공 (분석 참고)\n"

    # 뉴스
    news_text = ""
    for n in news[:5]:
        news_text += f"- [{n.get('published', '')}] {n.get('title', '')} ({n.get('source', '')})\n"

    return f"""당신은 월가의 시니어 애널리스트입니다. 데이터 기반으로 엄격하게 분석하여 투자 요약을 JSON으로 작성하세요.
{lang_instruction}
{macro_section}
## 2. 종목 정보
- Ticker: {ticker}
- 회사명: {data.get('company_name', ticker)}
- 현재가: ${data.get('current_price', 'N/A')}
- 등급: {data.get('grade', 'N/A')} ({data.get('grade_label', '')})
- 종합 점수: {data.get('composite_score', 'N/A')}/100

## 3. 수급/기술적 분석
- 수급 점수 (SD): {data.get('sd_score', 'N/A')}
- 기관 보유율: {data.get('inst_pct', 'N/A')}%
- RSI: {data.get('rsi', 'N/A')}
- MA Signal: {data.get('ma_signal', 'N/A')}
- Cross Signal: {data.get('cross_signal', 'N/A')}

## 4. 펀더멘털
- P/E: {data.get('pe_trailing', 'N/A')}
- 매출 성장률: {data.get('revenue_growth', 'N/A')}%
- 목표가 대비: {data.get('upside_pct', 'N/A')}%
- S&P 500 대비 20일 수익률: {data.get('rs_vs_spy', 'N/A')}%

## 5. 최근 뉴스
{news_text}

## 응답 규칙
1. Evidence: 모든 주장에 반드시 [출처, 날짜]를 명시하세요.
2. Bear Cases: BUY 추천이라도 반드시 3개의 하락 리스크를 제시하세요.
3. Data Conflicts: 기술적 vs 펀더멘털 vs 뉴스 간 충돌이 있으면 명시하세요.
4. 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트는 절대 포함하지 마세요.

```json
{{
  "thesis": "2-3문장 핵심 투자 논거",
  "catalysts": [
    {{"point": "상승 촉매", "evidence": "[출처, 날짜]"}},
    {{"point": "상승 촉매", "evidence": "[출처, 날짜]"}}
  ],
  "bear_cases": [
    {{"point": "하락 리스크 1", "evidence": "[출처, 날짜]"}},
    {{"point": "하락 리스크 2", "evidence": "[출처, 날짜]"}},
    {{"point": "하락 리스크 3", "evidence": "[출처, 날짜]"}}
  ],
  "data_conflicts": ["기술적 vs 펀더멘털 충돌 내용"],
  "key_metrics": {{
    "pe": {data.get('pe_trailing', 0)},
    "growth": {data.get('revenue_growth', 0)},
    "rsi": {data.get('rsi', 50)},
    "inst_pct": {data.get('inst_pct', 0)}
  }},
  "recommendation": "STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL",
  "confidence": 50
}}
```"""


class APIUsageTracker:
    """API 호출별 토큰 사용량과 예상 비용을 추적한다."""

    PRICING = {
        "gemini": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000, "label": "Gemini Flash (무료 한도 초과 시)"},
        "openai": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000, "label": "GPT-4o mini"},
        "perplexity": {"per_request": 3.0 / 1000, "label": "Perplexity Sonar"},
    }

    def __init__(self):
        self.records: list[dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    def record(self, provider: str, ticker: str, input_tokens: int = 0, output_tokens: int = 0):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_requests += 1
        self.records.append({
            "provider": provider,
            "ticker": ticker,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })
        logger.info("  토큰 사용: %s %s — input=%d, output=%d", provider, ticker, input_tokens, output_tokens)

    def estimate_cost(self) -> dict:
        cost_by_provider: dict[str, float] = {}
        requests_by_provider: dict[str, int] = {}
        tokens_by_provider: dict[str, dict] = {}

        for r in self.records:
            p = r["provider"]
            requests_by_provider[p] = requests_by_provider.get(p, 0) + 1
            if p not in tokens_by_provider:
                tokens_by_provider[p] = {"input": 0, "output": 0}
            tokens_by_provider[p]["input"] += r["input_tokens"]
            tokens_by_provider[p]["output"] += r["output_tokens"]

        for p, tokens in tokens_by_provider.items():
            pricing = self.PRICING.get(p, {})
            if "per_request" in pricing:
                cost_by_provider[p] = requests_by_provider[p] * pricing["per_request"]
            else:
                cost_by_provider[p] = (
                    tokens["input"] * pricing.get("input", 0)
                    + tokens["output"] * pricing.get("output", 0)
                )

        return {
            "by_provider": cost_by_provider,
            "tokens_by_provider": tokens_by_provider,
            "requests_by_provider": requests_by_provider,
            "total_cost": sum(cost_by_provider.values()),
        }

    def print_summary(self):
        if not self.records:
            return
        cost = self.estimate_cost()
        print(f"\n{'─' * 60}")
        print("  💰 API 비용 요약")
        print(f"{'─' * 60}")
        for p, tokens in cost["tokens_by_provider"].items():
            label = self.PRICING.get(p, {}).get("label", p)
            reqs = cost["requests_by_provider"][p]
            provider_cost = cost["by_provider"][p]
            print(f"  {label}:")
            print(f"    요청 수: {reqs}")
            if "per_request" in self.PRICING.get(p, {}):
                print(f"    예상 비용: ${provider_cost:.4f}")
            else:
                print(f"    입력 토큰: {tokens['input']:,}")
                print(f"    출력 토큰: {tokens['output']:,}")
                print(f"    예상 비용: ${provider_cost:.4f}")
        print(f"{'─' * 60}")
        print(f"  총 요청: {self.total_requests}건")
        print(f"  총 토큰: {self.total_input_tokens + self.total_output_tokens:,} (입력 {self.total_input_tokens:,} + 출력 {self.total_output_tokens:,})")
        print(f"  총 예상 비용: ${cost['total_cost']:.4f}")
        print(f"{'─' * 60}")


# 모듈 레벨 트래커 (전역 싱글턴)
usage_tracker = APIUsageTracker()


class NewsCollector:
    def __init__(self, finnhub_key: str = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.finnhub_key = finnhub_key or os.environ.get("FINNHUB_API_KEY")

    def _is_recent(self, published_date, days: int = 7) -> bool:
        """7일 이내 뉴스만 허용."""
        if published_date is None:
            return True  # 날짜 없으면 허용 (삭제보다 포함 우선)
        try:
            if isinstance(published_date, str):
                if not published_date.strip():
                    return True
                from email.utils import parsedate_to_datetime as _parse_rfc
                try:
                    published_date = _parse_rfc(published_date)
                except Exception:
                    published_date = datetime.fromisoformat(
                        published_date.replace("Z", "+00:00")
                    )
            if isinstance(published_date, (int, float)):
                published_date = datetime.fromtimestamp(published_date, tz=timezone.utc)
            if published_date.tzinfo is None:
                published_date = published_date.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            return published_date >= cutoff
        except Exception:
            return True  # 파싱 실패 시 허용

    def get_yahoo_news(self, ticker: str, limit: int = 3) -> list[dict]:
        try:
            stock = yf.Ticker(ticker)
            news = stock.news or []
            results = []
            for item in news[:limit]:
                content = item.get("content", item)
                title = content.get("title", "")
                publisher = content.get("provider", {})
                if isinstance(publisher, dict):
                    publisher = publisher.get("displayName", "")
                pub_date = content.get("pubDate", "")
                if pub_date:
                    try:
                        pub_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass
                link = ""
                canonical = content.get("canonicalUrl", {})
                if isinstance(canonical, dict):
                    link = canonical.get("url", "")
                elif isinstance(canonical, str):
                    link = canonical
                if not self._is_recent(pub_date):
                    continue
                results.append({
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "published": pub_date,
                    "source": "Yahoo",
                })
            return results
        except Exception:
            logger.debug("%s Yahoo 뉴스 수집 실패", ticker, exc_info=True)
            return []

    def get_google_news(self, ticker: str, company_name: str = None, limit: int = 3) -> list[dict]:
        import xml.etree.ElementTree as ET
        from email.utils import parsedate_to_datetime
        from urllib.parse import quote

        import requests

        try:
            if company_name:
                query = f'"{company_name}" OR {ticker} stock'
            else:
                query = f"{ticker} stock"
            url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"

            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            root = ET.fromstring(resp.text)
            results = []
            for item in root.iter("item"):
                if len(results) >= limit:
                    break
                pub_date = ""
                pub_el = item.find("pubDate")
                if pub_el is not None and pub_el.text:
                    try:
                        pub_date = parsedate_to_datetime(pub_el.text).strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass
                source_el = item.find("source")
                if not self._is_recent(pub_date):
                    continue
                results.append({
                    "title": (item.find("title").text or "") if item.find("title") is not None else "",
                    "publisher": source_el.text if source_el is not None else "",
                    "link": (item.find("link").text or "") if item.find("link") is not None else "",
                    "published": pub_date,
                    "source": "Google",
                })
            return results
        except Exception:
            logger.debug("%s Google 뉴스 수집 실패", ticker, exc_info=True)
            return []

    def get_finnhub_news(self, ticker: str, limit: int = 3) -> list[dict]:
        if not self.finnhub_key:
            return []

        import requests
        from datetime import timedelta

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            resp = requests.get(
                "https://finnhub.io/api/v1/company-news",
                params={"symbol": ticker, "from": week_ago, "to": today, "token": self.finnhub_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data[:limit]:
                pub_date = ""
                if "datetime" in item:
                    try:
                        pub_date = datetime.fromtimestamp(item["datetime"]).strftime("%Y-%m-%d")
                    except (ValueError, TypeError, OSError):
                        pass
                if not self._is_recent(pub_date):
                    continue
                summary = item.get("summary", "")
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                results.append({
                    "title": item.get("headline", ""),
                    "publisher": item.get("source", ""),
                    "link": item.get("url", ""),
                    "published": pub_date,
                    "summary": summary,
                    "source": "Finnhub",
                })
            return results
        except Exception:
            logger.debug("%s Finnhub 뉴스 수집 실패", ticker, exc_info=True)
            return []


    def _deduplicate_news(self, news: list[dict]) -> list[dict]:
        seen_titles = set()
        unique = []
        for item in news:
            key = item.get("title", "")[:50].lower()
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique.append(item)
        return unique

    def get_news_for_ticker(self, ticker: str, company_name: str = None) -> list[dict]:
        all_news = []
        all_news.extend(self.get_yahoo_news(ticker, limit=3))
        all_news.extend(self.get_google_news(ticker, company_name, limit=3))
        if self.finnhub_key:
            all_news.extend(self.get_finnhub_news(ticker, limit=3))

        all_news = self._deduplicate_news(all_news)
        all_news.sort(key=lambda x: x.get("published", ""), reverse=True)
        return all_news[:8]


class GeminiSummaryGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        logger.info("Gemini 초기화: %s", model)

    def generate_summary(self, ticker: str, data: dict, news: list,
                         lang: str = "ko", macro_context: dict = None) -> str:
        import requests

        prompt = build_analysis_prompt(ticker, data, news, macro_context, lang)

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 4000,
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()

            # 토큰 사용량 추출
            usage_meta = result.get("usageMetadata", {})
            usage_tracker.record(
                "gemini", ticker,
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
            )

            candidates = result.get("candidates", [])
            if not candidates:
                logger.warning("%s Gemini 응답 없음 (safety filter?)", ticker)
                return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)

            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
            text = "\n".join(text_parts).strip()

            # parse_ai_response로 JSON 추출 및 검증
            parsed = parse_ai_response(text)
            if parsed:
                valid, reasons = validate_ai_response(parsed)
                if not valid:
                    logger.warning("%s Gemini 응답 검증 실패: %s", ticker, reasons)
                return json.dumps(parsed, ensure_ascii=False)

            logger.warning("%s Gemini JSON 파싱 실패", ticker)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)

        except Exception as e:
            logger.warning("%s Gemini 요청 실패: %s", ticker, type(e).__name__)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)


class OpenAISummaryGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"
        logger.info("OpenAI 초기화: %s", self.model)

    def generate_summary(self, ticker: str, data: dict, news: list,
                         lang: str = "ko", macro_context: dict = None) -> str:
        import requests

        prompt = build_analysis_prompt(ticker, data, news, macro_context, lang)

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a professional hedge fund analyst. Always respond with valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                timeout=90,
            )
            resp.raise_for_status()
            result = resp.json()

            # 토큰 사용량 추출
            usage = result.get("usage", {})
            usage_tracker.record(
                "openai", ticker,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )

            text = result["choices"][0]["message"]["content"].strip()

            # parse_ai_response로 JSON 추출 및 검증
            parsed = parse_ai_response(text)
            if parsed:
                valid, reasons = validate_ai_response(parsed)
                if not valid:
                    logger.warning("%s OpenAI 응답 검증 실패: %s", ticker, reasons)
                return json.dumps(parsed, ensure_ascii=False)

            logger.warning("%s OpenAI JSON 파싱 실패", ticker)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)

        except Exception as e:
            logger.warning("%s OpenAI 요청 실패: %s", ticker, type(e).__name__)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)

    def generate(self, ticker: str, data: dict, *,
                 market: str = "US", market_context=None,
                 name: str = "", sector: str = "") -> dict:
        merged = dict(data)
        if name:
            merged.setdefault("company_name", name)
        if sector:
            merged.setdefault("sector", sector)
        raw = self.generate_summary(ticker, merged, news=[], macro_context=None)
        try:
            result = json.loads(raw) if isinstance(raw, str) else raw
            return result or _get_fallback_json(ticker)
        except Exception:
            return _get_fallback_json(ticker)


class PerplexitySummaryGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY가 설정되지 않았습니다")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.model = "sonar"
        logger.info("Perplexity 초기화: %s", self.model)

    def generate_summary(self, ticker: str, data: dict, news: list,
                         lang: str = "ko", macro_context: dict = None) -> str:
        import requests

        prompt = build_analysis_prompt(ticker, data, news, macro_context, lang)

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a professional hedge fund analyst. Always respond with valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
                timeout=90,
            )
            resp.raise_for_status()
            result = resp.json()

            # 토큰 사용량 추출
            usage = result.get("usage", {})
            usage_tracker.record(
                "perplexity", ticker,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )

            text = result["choices"][0]["message"]["content"].strip()

            # parse_ai_response로 JSON 추출 및 검증
            parsed = parse_ai_response(text)
            if parsed:
                valid, reasons = validate_ai_response(parsed)
                if not valid:
                    logger.warning("%s Perplexity 응답 검증 실패: %s", ticker, reasons)
                return json.dumps(parsed, ensure_ascii=False)

            logger.warning("%s Perplexity JSON 파싱 실패", ticker)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)

        except Exception as e:
            logger.warning("%s Perplexity 요청 실패: %s", ticker, type(e).__name__)
            return json.dumps(_get_fallback_json(ticker), ensure_ascii=False)


def get_ai_provider(provider: str = "gemini"):
    providers = {
        "gemini": GeminiSummaryGenerator,
        "openai": OpenAISummaryGenerator,
        "perplexity": PerplexitySummaryGenerator,
    }
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}. 사용 가능: {list(providers.keys())}")
    return providers[provider]()


def get_ai_summary(ticker: str, data: dict, news: list,
                   macro_context: dict = None, lang: str = "ko",
                   preferred_provider: str = "openai") -> dict:
    """3-tier fallback: gemini -> openai -> perplexity"""
    providers = ["gemini", "openai", "perplexity"]
    # preferred를 첫번째로
    if preferred_provider in providers:
        providers.remove(preferred_provider)
        providers.insert(0, preferred_provider)

    last_error = None
    fallback = _get_fallback_json(ticker)
    for provider_name in providers:
        try:
            provider = get_ai_provider(provider_name)
            raw = provider.generate_summary(ticker, data, news,
                                            lang=lang, macro_context=macro_context)
            result = json.loads(raw) if isinstance(raw, str) else raw
            # 유효한 결과인지 확인
            if (result
                    and result.get("thesis")
                    and result["thesis"] != fallback["thesis"]):
                logging.info("[%s] AI 분석 성공: %s", ticker, provider_name)
                return result
            logging.warning("[%s] %s 빈 결과, 다음 provider 시도", ticker, provider_name)
        except Exception as e:
            last_error = e
            logging.warning("[%s] %s 실패: %s, 다음 provider 시도",
                            ticker, provider_name, type(e).__name__)
            continue

    logging.error("[%s] 모든 provider 실패. last_error: %s",
                  ticker, type(last_error).__name__ if last_error else "unknown")
    return fallback


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    parser = argparse.ArgumentParser(description="AI Summary Generator")
    parser.add_argument("--provider", default="openai", choices=["gemini", "openai", "perplexity"])
    parser.add_argument("--top", type=int, default=20, help="분석할 종목 수")
    parser.add_argument("--ticker", type=str, help="특정 종목만 분석")
    parser.add_argument("--lang", default="ko", choices=["ko", "en"])
    parser.add_argument("--refresh", action="store_true", help="캐시 무시")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # CSV 로드
    csv_path = Path("output/smart_money_picks_v2.csv")
    if not csv_path.exists():
        csv_path = Path("result") / sorted(Path("result").glob("smart_money_picks_*.csv"))[-1].name if Path("result").exists() and list(Path("result").glob("smart_money_picks_*.csv")) else None
    if not csv_path or not csv_path.exists():
        logger.error("smart_money_picks CSV 파일 없음. run_screening.py를 먼저 실행하세요.")
        sys.exit(1)

    import pandas as pd
    df = pd.read_csv(csv_path)

    # 종목 선택
    if args.ticker:
        tickers = [args.ticker]
    else:
        col = "종목" if "종목" in df.columns else "ticker"
        tickers = df[col].head(args.top).tolist()

    logger.info("분석 대상: %d종목, provider=%s, lang=%s", len(tickers), args.provider, args.lang)

    # AI 초기화
    collector = NewsCollector()
    ai = get_ai_provider(args.provider)
    results = {}

    try:
        from tqdm import tqdm
        iterator = tqdm(tickers, desc="AI 분석")
    except ImportError:
        iterator = tickers

    for ticker in iterator:
        news = collector.get_news_for_ticker(ticker)
        row = df[df.get("종목", df.get("ticker", pd.Series())) == ticker]
        data = row.iloc[0].to_dict() if not row.empty else {}

        summary = ai.generate_summary(ticker, data, news, lang=args.lang)
        try:
            results[ticker] = json.loads(summary)
        except json.JSONDecodeError:
            results[ticker] = {"raw": summary}
        logger.info("%s: %s", ticker, results[ticker].get("recommendation", "N/A"))

    # 저장
    out_path = Path("output/ai_summaries.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("저장 완료: %s (%d종목)", out_path, len(results))

    # SQLite 쓰기
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from db.data_store import get_db, upsert_ai_summaries
        _conn = get_db()
        upsert_ai_summaries(_conn, results)
        _conn.close()
        logger.info("SQLite data_ai_summaries 갱신 완료 (%d종목)", len(results))
    except Exception as _e:
        logger.warning("SQLite 쓰기 실패: %s", _e)

    # 요약 출력
    print(f"\n{'=' * 60}")
    print(f"  AI 분석 결과 ({args.provider}, {len(results)}종목)")
    print(f"{'=' * 60}")
    for ticker, data in results.items():
        rec = data.get("recommendation", "N/A")
        conf = data.get("confidence", 0)
        thesis = data.get("thesis", "")[:80]
        print(f"  {ticker:6} [{rec:4}] (신뢰도 {conf}%) {thesis}")
    print(f"{'=' * 60}")

    # API 비용 요약
    usage_tracker.print_summary()
