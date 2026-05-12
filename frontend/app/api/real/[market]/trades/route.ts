import { NextRequest, NextResponse } from "next/server";
import { getRealTrades } from "@/src/lib/paperDb";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const trades = getRealTrades(market, 200);

  const sells = trades.filter((t) => t.action === "SELL");
  const totalRealizedPnl = sells.reduce((s, t) => s + (t.realized_pnl ?? 0), 0);
  const winCount = sells.filter((t) => (t.realized_pnl ?? 0) > 0).length;
  const winRate = sells.length > 0 ? winCount / sells.length : null;

  return NextResponse.json({ trades, stats: { total_realized_pnl: totalRealizedPnl, win_rate: winRate, sell_count: sells.length } });
}
