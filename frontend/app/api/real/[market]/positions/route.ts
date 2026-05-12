import { NextRequest, NextResponse } from "next/server";
import { getRealPositions, upsertRealPosition, deleteRealPosition } from "@/src/lib/paperDb";
import { getClient } from "@/src/lib/db";
import { fetchYahooPrices } from "@/src/lib/yahooPrice";

export const dynamic = "force-dynamic";

async function getLatestPrices(market: string): Promise<Record<string, { price: number; name: string | null }>> {
  const client = getClient();
  try {
    const table = market === "KR" ? "kr_daily_reports" : "data_daily_reports";
    const result = await client.execute(`SELECT payload FROM ${table} ORDER BY date DESC LIMIT 1`);
    const row = result.rows[0];
    if (!row) return {};
    const clean = (row[0] as string).replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null");
    const parsed = JSON.parse(clean);
    const stocks: any[] = parsed.stocks ?? parsed.picks ?? [];
    const out: Record<string, { price: number; name: string | null }> = {};
    for (const s of stocks) {
      const p = s.current_price ?? s.cur_price ?? s.price;
      if (s.symbol && p != null) {
        out[s.symbol.toUpperCase()] = { price: p, name: s.name ?? s.company_name ?? null };
      }
    }
    return out;
  } catch {
    return {};
  }
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const positions = getRealPositions(market);
  const priceMap = await getLatestPrices(market);

  const missingSymbols = positions
    .map((p) => p.symbol.toUpperCase())
    .filter((s) => priceMap[s] == null);
  const yahooMap = await fetchYahooPrices(missingSymbols, market);

  const enriched = positions.map((pos) => {
    const sym = pos.symbol.toUpperCase();
    const latest = priceMap[sym];
    const yahoo  = yahooMap[sym];
    const current_price = latest?.price ?? yahoo?.price ?? null;
    const cost_basis    = pos.shares * pos.avg_price;
    const market_value  = current_price != null ? pos.shares * current_price : null;
    const unrealized_pnl     = market_value != null ? market_value - cost_basis : null;
    const unrealized_pnl_pct = unrealized_pnl != null ? unrealized_pnl / cost_basis : null;
    return {
      ...pos,
      name: pos.name ?? latest?.name ?? yahoo?.name ?? null,
      current_price,
      price_source: latest ? "analysis" : (yahoo?.price != null ? "yahoo" : null),
      cost_basis,
      market_value,
      unrealized_pnl,
      unrealized_pnl_pct,
    };
  });

  const totalCost  = enriched.reduce((s, p) => s + p.cost_basis, 0);
  const totalValue = enriched.reduce((s, p) => s + (p.market_value ?? p.cost_basis), 0);
  const totalPnl   = totalValue - totalCost;
  const totalPnlPct = totalCost > 0 ? totalPnl / totalCost : 0;

  return NextResponse.json({
    positions: enriched,
    summary: { total_cost: totalCost, total_value: totalValue, total_pnl: totalPnl, total_pnl_pct: totalPnlPct },
  });
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const body = await req.json();
  const { symbol, name, shares, avg_price, sector, note } = body;

  if (!symbol || !shares || !avg_price) {
    return NextResponse.json({ error: "symbol, shares, avg_price 필수" }, { status: 400 });
  }
  if (shares <= 0 || avg_price <= 0) {
    return NextResponse.json({ error: "수량과 가격은 0보다 커야 합니다" }, { status: 400 });
  }

  const result = upsertRealPosition({
    market,
    symbol: symbol.toUpperCase(),
    name: name ?? null,
    shares: Number(shares),
    avg_price: Number(avg_price),
    sector: sector ?? null,
    note: note ?? null,
  });

  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase();
  if (!symbol) return NextResponse.json({ error: "symbol required" }, { status: 400 });

  deleteRealPosition(market, symbol);
  return NextResponse.json({ ok: true });
}
