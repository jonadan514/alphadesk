import { NextRequest, NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const client = getClient();
  try {
    const table = market === "KR" ? "kr_daily_reports" : "data_daily_reports";
    const result = await client.execute(`SELECT date, payload FROM ${table} ORDER BY date DESC LIMIT 1`);
    const row = result.rows[0];
    if (!row) return NextResponse.json({ date: null, candidates: [] });

    const clean = (row[1] as string).replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null");
    const parsed = JSON.parse(clean);
    const stocks: any[] = parsed.stocks ?? parsed.picks ?? [];

    const candidates = stocks
      .filter((s) => s.action === "BUY" || s.action === "SMALL BUY")
      .map((s) => {
        const price = s.current_price ?? s.cur_price ?? s.price ?? null;
        const epsGrowth = s.earnings_growth != null ? s.earnings_growth / 100 : (s.eps_growth ?? null);
        const priceVs52w = s.pct_from_52h != null ? s.pct_from_52h / 100 : (s.price_vs_52w_high ?? null);
        return {
          symbol: s.symbol,
          name: s.name ?? s.symbol,
          action: s.action,
          grade: s.grade ?? null,
          sector: s.sector ?? null,
          price,
          target_price: s.target_price ?? null,
          composite_score: s.composite_score ?? s.score ?? null,
          peg_ratio: s.peg_ratio ?? null,
          eps_growth: epsGrowth,
          price_vs_52w_high: priceVs52w,
          technical: s.technical ?? null,
          fundamental: s.fundamental ?? null,
          analyst: s.analyst ?? null,
          relative_strength: s.relative_strength ?? null,
          volume: s.volume ?? null,
          institutional: s.institutional ?? null,
          thesis: s.thesis ?? null,
          catalysts: s.catalysts ?? null,
          bear_cases: s.bear_cases ?? null,
          confidence: s.confidence ?? null,
        };
      })
      .sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0));

    return NextResponse.json({ date: row[0], candidates });
  } catch {
    return NextResponse.json({ date: null, candidates: [] });
  }
}
