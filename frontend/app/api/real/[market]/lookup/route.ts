import { NextRequest, NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";
import { fetchYahooPrice } from "@/src/lib/yahooPrice";

export const dynamic = "force-dynamic";

type Candidate = {
  symbol: string;
  name: string | null;
  current_price: number | null;
  sector: string | null;
  source: "analysis" | "yahoo";
};

async function searchYahoo(query: string, market: string): Promise<Candidate[]> {
  try {
    const res = await fetch(
      `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&quotesCount=8&newsCount=0&listsCount=0`,
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return [];
    const json = await res.json();
    const quotes: any[] = json?.quotes ?? [];

    const filtered = quotes.filter((q) => {
      if (q.typeDisp !== "Equity" && q.quoteType !== "EQUITY") return false;
      if (market === "KR") return q.exchDisp === "KSC" || q.exchDisp === "KOE" || q.symbol?.endsWith(".KS") || q.symbol?.endsWith(".KQ");
      if (market === "US") return q.exchDisp === "NYSE" || q.exchDisp === "NasdaqGS" || q.exchDisp === "NasdaqCM" || q.exchDisp === "NGM" || (!q.symbol?.includes("."));
      return false;
    }).slice(0, 5);

    const candidates = await Promise.all(
      filtered.map(async (q) => {
        const rawSymbol = q.symbol as string;
        const displaySymbol = market === "KR" ? rawSymbol.replace(/\.(KS|KQ)$/, "") : rawSymbol;
        const yahoo = await fetchYahooPrice(rawSymbol, "");
        return {
          symbol: displaySymbol,
          name: q.longname ?? q.shortname ?? null,
          current_price: yahoo.price,
          sector: q.sector ?? null,
          source: "yahoo" as const,
        };
      })
    );
    return candidates;
  } catch {
    return [];
  }
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const q = req.nextUrl.searchParams.get("q")?.trim();
  if (!q) return NextResponse.json({ error: "q required" }, { status: 400 });

  // 1. Search analysis DB
  const client = getClient();
  let analysisStocks: any[] = [];
  try {
    const table = market === "KR" ? "kr_daily_reports" : "data_daily_reports";
    const result = await client.execute(`SELECT payload FROM ${table} ORDER BY date DESC LIMIT 1`);
    const row = result.rows[0];
    if (row) {
      const clean = (row[0] as string).replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null");
      const parsed = JSON.parse(clean);
      analysisStocks = parsed.stocks ?? parsed.picks ?? [];
    }
  } catch {}

  const qLower = q.toLowerCase();
  const matched = analysisStocks.filter((s: any) => {
    const sym  = (s.symbol ?? "").toLowerCase();
    const name = (s.name ?? s.company_name ?? "").toLowerCase();
    return sym === qLower || sym.startsWith(qLower) || name.includes(qLower);
  }).slice(0, 5);

  if (matched.length > 0) {
    const candidates: Candidate[] = matched.map((s: any) => ({
      symbol: s.symbol,
      name: s.name ?? s.company_name ?? null,
      current_price: s.current_price ?? s.cur_price ?? s.price ?? null,
      sector: s.sector ?? null,
      source: "analysis" as const,
    }));
    return NextResponse.json({ candidates });
  }

  // 2. Exact symbol → Yahoo Finance
  const isCode = market === "KR" ? /^\d{4,6}$/.test(q) : /^[A-Z]{1,5}$/.test(q.toUpperCase());
  if (isCode) {
    const yahoo = await fetchYahooPrice(q.toUpperCase(), market);
    if (yahoo.price != null) {
      return NextResponse.json({
        candidates: [{ symbol: q.toUpperCase(), name: yahoo.name, current_price: yahoo.price, sector: null, source: "yahoo" }],
      });
    }
    return NextResponse.json({ candidates: [] });
  }

  // 3. Name query → Yahoo search
  const yahooCandidates = await searchYahoo(q, market);
  return NextResponse.json({ candidates: yahooCandidates });
}
