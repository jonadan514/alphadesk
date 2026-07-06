import { NextResponse } from "next/server";
import { fetchYahooPrice } from "@/src/lib/yahooPrice";

export const dynamic = "force-dynamic";

// GET /api/portfolio/prices?symbols=US:AAPL,KR:005930
// → { "US:AAPL": 231.5, "KR:005930": 61200 }
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const raw = searchParams.get("symbols") ?? "";
  const pairs = raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => /^(US|KR):[A-Z0-9.\-]+$/i.test(s))
    .slice(0, 50);

  const entries = await Promise.all(
    pairs.map(async (pair) => {
      const [market, symbol] = pair.split(":");
      const quote = await fetchYahooPrice(symbol.toUpperCase(), market.toUpperCase());
      return [`${market.toUpperCase()}:${symbol.toUpperCase()}`, quote.price] as const;
    })
  );

  return NextResponse.json(Object.fromEntries(entries));
}
