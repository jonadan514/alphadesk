// Fetches current price from Yahoo Finance for symbols not in analysis DB.
// KR symbols: 6-digit codes get ".KS" suffix (KOSPI). Already-suffixed symbols pass through.

export type YahooQuote = {
  symbol: string;
  name: string | null;
  price: number | null;
};

async function fetchChart(ySym: string): Promise<{ price: number | null; name: string | null }> {
  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ySym)}?interval=1d&range=1d`,
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return { price: null, name: null };
    const json = await res.json();
    const meta = json?.chart?.result?.[0]?.meta;
    if (!meta) return { price: null, name: null };
    return {
      price: meta.regularMarketPrice ?? null,
      name: meta.longName ?? meta.shortName ?? null,
    };
  } catch {
    return { price: null, name: null };
  }
}

export async function fetchYahooPrice(symbol: string, market: string): Promise<YahooQuote> {
  if (market === "KR" && /^\d{6}$/.test(symbol)) {
    // KOSPI(.KS) 우선, 실패하면 KOSDAQ(.KQ)
    const ks = await fetchChart(`${symbol}.KS`);
    if (ks.price !== null) return { symbol, ...ks };
    const kq = await fetchChart(`${symbol}.KQ`);
    return { symbol, ...kq };
  }
  const r = await fetchChart(symbol);
  return { symbol, ...r };
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
