import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

const CACHE_HOURS = 24;

interface NarrativeBrief {
  story: string;
  catalysts: string[];
  risks: string[];
  sentiment: "HOT" | "WARM" | "COLD";
  sentiment_reason: string;
  sources: string[];
  cached_at: string;
}

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS narrative_briefs (
      market     TEXT NOT NULL,
      symbol     TEXT NOT NULL,
      payload    TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (market, symbol)
    )
  `);
  return client;
}

function extractJson(text: string): Record<string, unknown> | null {
  const fence = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
  const raw = fence ? fence[1] : text.match(/\{[\s\S]*\}/)?.[0];
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function fetchNarrative(
  market: string,
  symbol: string,
  name: string
): Promise<Omit<NarrativeBrief, "cached_at" | "sources"> & { sources: string[] }> {
  const apiKey = process.env.PERPLEXITY_API_KEY?.trim();
  if (!apiKey) throw new Error("PERPLEXITY_API_KEY 환경변수가 설정되지 않았습니다.");

  const marketLabel = market === "KR" ? "한국(KOSPI/KOSDAQ)" : "미국(NYSE/NASDAQ)";
  const prompt = `종목: ${name || symbol} (티커/코드: ${symbol}, ${marketLabel} 상장)

이 종목에 대해 최근 1개월간 시장에서 형성된 투자 네러티브(스토리)를 웹에서 조사한 뒤, 아래 JSON 형식으로만 답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{
  "story": "현재 이 종목에 붙어 있는 핵심 투자 스토리를 2~3문장으로. 시장이 왜 이 종목에 관심을 갖는지(또는 안 갖는지)",
  "catalysts": ["다가오는 촉매 최대 3개 — 실적발표·신제품·정책·계약 등, 시기를 알면 함께"],
  "risks": ["이 스토리가 깨질 수 있는 리스크 최대 3개"],
  "sentiment": "HOT 또는 WARM 또는 COLD",
  "sentiment_reason": "시장 관심도 판단 근거 한 문장"
}

sentiment 기준: HOT=지금 시장이 활발히 이야기하는 인기 테마 소속, WARM=꾸준한 관심 유지, COLD=시장의 관심 밖. 모든 내용은 한국어로 작성하세요.`;

  const resp = await fetch("https://api.perplexity.ai/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "sonar",
      messages: [
        {
          role: "system",
          content:
            "당신은 주식 시장 네러티브 분석가입니다. 웹 검색 결과를 바탕으로 반드시 유효한 JSON만 출력합니다.",
        },
        { role: "user", content: prompt },
      ],
      temperature: 0.2,
      max_tokens: 800,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Perplexity API 오류 (${resp.status})`);
  }
  const data = await resp.json();
  const text: string = data?.choices?.[0]?.message?.content ?? "";
  const parsed = extractJson(text);
  if (!parsed || typeof parsed.story !== "string") {
    throw new Error("Perplexity 응답 파싱 실패");
  }

  let citations: string[] = [];
  if (Array.isArray(data?.citations)) {
    citations = data.citations.filter((c: unknown): c is string => typeof c === "string");
  } else if (Array.isArray(data?.search_results)) {
    citations = data.search_results
      .map((s: { url?: string }) => s?.url)
      .filter((u: unknown): u is string => typeof u === "string");
  }

  const sentiment = ["HOT", "WARM", "COLD"].includes(parsed.sentiment as string)
    ? (parsed.sentiment as "HOT" | "WARM" | "COLD")
    : "WARM";

  return {
    story: parsed.story as string,
    catalysts: Array.isArray(parsed.catalysts) ? (parsed.catalysts as string[]).slice(0, 3) : [],
    risks: Array.isArray(parsed.risks) ? (parsed.risks as string[]).slice(0, 3) : [],
    sentiment,
    sentiment_reason: typeof parsed.sentiment_reason === "string" ? parsed.sentiment_reason : "",
    sources: citations.slice(0, 5),
  };
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "US").toUpperCase();
    const symbol = (searchParams.get("symbol") ?? "").toUpperCase();
    const name = searchParams.get("name") ?? "";
    const refresh = searchParams.get("refresh") === "1";
    if (!symbol) {
      return NextResponse.json({ error: "symbol 필수" }, { status: 400 });
    }

    const client = await ensureTable();

    if (!refresh) {
      const cached = await client.execute({
        sql: `SELECT payload, updated_at FROM narrative_briefs
              WHERE market = ? AND symbol = ?
                AND updated_at > datetime('now', '-${CACHE_HOURS} hours')`,
        args: [market, symbol],
      });
      const row = cached.rows[0];
      if (row) {
        const payload = JSON.parse(row[0] as string);
        return NextResponse.json({ ...payload, cached_at: row[1] as string });
      }
    }

    const brief = await fetchNarrative(market, symbol, name);
    const payload = JSON.stringify(brief);
    await client.execute({
      sql: `INSERT INTO narrative_briefs (market, symbol, payload, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(market, symbol) DO UPDATE SET
              payload = excluded.payload, updated_at = excluded.updated_at`,
      args: [market, symbol, payload],
    });
    return NextResponse.json({ ...brief, cached_at: new Date().toISOString() });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "알 수 없는 오류";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
