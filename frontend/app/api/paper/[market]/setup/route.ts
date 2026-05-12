import { NextRequest, NextResponse } from "next/server";
import { setupPortfolio } from "@/src/lib/paperDb";

export async function POST(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }
  const body = await req.json().catch(() => ({}));
  const initial_capital = Number(body.initial_capital);
  if (!initial_capital || initial_capital < 1000) {
    return NextResponse.json({ error: "initial_capital must be >= 1000" }, { status: 400 });
  }
  const pf = setupPortfolio(market, initial_capital);
  return NextResponse.json(pf);
}
