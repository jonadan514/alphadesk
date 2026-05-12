import { NextRequest, NextResponse } from "next/server";
import { buyStock } from "@/src/lib/paperDb";

export async function POST(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }
  const body = await req.json().catch(() => ({}));
  const { symbol, name, shares, price, grade, sector } = body;
  const s = Number(shares), p = Number(price);
  if (!symbol || !s || !p || isNaN(s) || isNaN(p) || s <= 0 || p <= 0) {
    return NextResponse.json({ error: "symbol, shares, price are required" }, { status: 400 });
  }
  const result = buyStock({ market, symbol, name, shares: s, price: p, grade, sector });
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json({ ok: true });
}
