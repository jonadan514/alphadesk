import { NextRequest, NextResponse } from "next/server";
import { getPortfolio, getPositions } from "@/src/lib/paperDb";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function getLatestPrices(market: string): Promise<Record<string, number>> {
  const client = getClient();
  try {
    const table = market === "KR" ? "kr_daily_reports" : "data_daily_reports";
    const result = await client.execute(`SELECT payload FROM ${table} ORDER BY date DESC LIMIT 1`);
    const row = result.rows[0];
    if (!row) return {};
    const clean = (row[0] as string).replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null");
    const parsed = JSON.parse(clean);
    const stocks: any[] = parsed.stocks ?? parsed.picks ?? [];
    const prices: Record<string, number> = {};
    for (const s of stocks) {
      const p = s.current_price ?? s.cur_price ?? s.price;
      if (s.symbol && p != null) prices[s.symbol] = p;
    }
    return prices;
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

  const pf = getPortfolio(market);
  if (!pf) return NextResponse.json({ exists: false });

  const positions = getPositions(market);
  const prices = await getLatestPrices(market);

  const positionsWithPnl = positions.map((pos) => {
    const currentPrice = prices[pos.symbol] ?? pos.avg_price;
    const marketValue = pos.shares * currentPrice;
    const costBasis = pos.shares * pos.avg_price;
    const unrealized_pnl = marketValue - costBasis;
    const unrealized_pnl_pct = unrealized_pnl / costBasis;
    const stop_loss_hit = currentPrice <= pos.stop_loss;
    return { ...pos, current_price: currentPrice, market_value: marketValue, unrealized_pnl, unrealized_pnl_pct, stop_loss_hit };
  });

  const totalMarketValue = positionsWithPnl.reduce((s, p) => s + p.market_value, 0);
  const totalValue = pf.cash + totalMarketValue;
  const totalPnl = totalValue - pf.initial_capital;
  const totalPnlPct = totalPnl / pf.initial_capital;

  return NextResponse.json({
    exists: true,
    portfolio: pf,
    positions: positionsWithPnl,
    summary: { total_value: totalValue, total_pnl: totalPnl, total_pnl_pct: totalPnlPct, cash: pf.cash, invested: totalMarketValue },
  });
}
