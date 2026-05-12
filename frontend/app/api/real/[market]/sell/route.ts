import { NextRequest, NextResponse } from "next/server";
import { sellRealPosition } from "@/src/lib/paperDb";

export async function POST(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }

  const body = await req.json();
  const { symbol, shares, sell_price, note } = body;

  if (!symbol || !shares || !sell_price) {
    return NextResponse.json({ error: "symbol, shares, sell_price 필수" }, { status: 400 });
  }
  if (shares <= 0 || sell_price <= 0) {
    return NextResponse.json({ error: "수량과 가격은 0보다 커야 합니다" }, { status: 400 });
  }

  const result = sellRealPosition({
    market,
    symbol: symbol.toUpperCase(),
    shares: Number(shares),
    sell_price: Number(sell_price),
    note: note ?? null,
  });

  if (!result.ok) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json({ ok: true });
}
