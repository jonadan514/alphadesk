import { NextRequest, NextResponse } from "next/server";
import { sellStock } from "@/src/lib/paperDb";

export async function POST(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }
  const body = await req.json().catch(() => ({}));
  const { symbol, shares, price, note } = body;
  const s = Number(shares), p = Number(price);
  if (!symbol || !s || !p || isNaN(s) || isNaN(p) || s <= 0 || p <= 0) {
    return NextResponse.json({ error: "symbol, shares, price are required" }, { status: 400 });
  }
  const result = sellStock({ market, symbol, shares: s, price: p, note });
  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json({ ok: true });
}
