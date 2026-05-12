import { NextRequest, NextResponse } from "next/server";
import { getTrades } from "@/src/lib/paperDb";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, { params }: { params: Promise<{ market: string }> }) {
  const { market: rawMarket } = await params;
  const market = rawMarket.toUpperCase();
  if (market !== "US" && market !== "KR") {
    return NextResponse.json({ error: "Invalid market" }, { status: 400 });
  }
  const limit = Number(req.nextUrl.searchParams.get("limit") ?? "100");
  const trades = getTrades(market, Math.min(limit, 200));
  return NextResponse.json(trades);
}
