// Fetches current price from Yahoo Finance for symbols not in analysis DB.
// KR symbols: 6-digit codes get ".KS" suffix (KOSPI). Already-suffixed symbols pass through.

export type YahooQuote = {
  symbol: string;
  name: string | null;
  price: number | null;
};

function toYahooSymbol(symbol: string, market: string): string {
  if (market === "KR" && /^\d{6}$/.test(symbol)) return `${symbol}.KS`;
  return symbol;
}

export async function fetchYahooPrice(symbol: string, market: string): Promise<YahooQuote> {
  const ySym = toYahooSymbol(symbol, market);
  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ySym)}?interval=1d&range=1d`,
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return { symbol, name: null, price: null };
    const json = await res.json();
    const meta = json?.chart?.result?.[0]?.meta;
    if (!meta) return { symbol, name: null, price: null };
    const price = meta.regularMarketPrice ?? null;
    const name = meta.longName ?? meta.shortName ?? null;
    return { symbol, name, price };
  } catch {
    return { symbol, name: null, price: null };
  }
}

export async function fetchYahooPrices(
  symbols: string[],
  market: string
): Promise<Record<string, YahooQuote>> {
  if (symbols.length === 0) return {};
  const results = await Promise.all(symbols.map((s) => fetchYahooPrice(s, market)));
  const map: Record<string, YahooQuote> = {};
  for (const r of results) map[r.symbol.toUpperCase()] = r;
  return map;
}
