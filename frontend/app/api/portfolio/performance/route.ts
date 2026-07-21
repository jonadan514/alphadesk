import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

function findPriceAt(dates: string[], closes: (number | null)[], targetDate: string): number | null {
  let result: number | null = null;
  for (let i = 0; i < dates.length; i++) {
    if (dates[i] <= targetDate && closes[i] != null) result = closes[i];
  }
  return result;
}

async function fetchWeeklyPrices(ticker: string): Promise<{ dates: string[]; closes: (number | null)[] }> {
  const toTs = Math.floor(Date.now() / 1000);
  const fromTs = toTs - 2 * 365 * 24 * 3600;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1wk&period1=${fromTs}&period2=${toTs}`;
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { dates: [], closes: [] };
    const data = await res.json();
    const chart = data?.chart?.result?.[0];
    if (!chart) return { dates: [], closes: [] };
    const timestamps: number[] = chart.timestamp ?? [];
    const closes: (number | null)[] = chart.indicators?.quote?.[0]?.close ?? [];
    const dates = timestamps.map((ts) => new Date(ts * 1000).toISOString().split("T")[0]);
    return { dates, closes };
  } catch {
    return { dates: [], closes: [] };
  }
}

export async function GET() {
  try {
    const client = getClient();

    let trades: any[] = [];
    try {
      const res = await client.execute("SELECT * FROM my_trades ORDER BY trade_date ASC");
      trades = res.rows.map((r) => {
        const obj: Record<string, unknown> = {};
        res.columns.forEach((col, i) => { obj[col] = r[i]; });
        return obj;
      });
    } catch {
      return NextResponse.json({ dates: [], myPortfolio: [], benchmark: [], benchmarkLabel: "SPY" });
    }

    if (trades.length === 0) {
      return NextResponse.json({ dates: [], myPortfolio: [], benchmark: [], benchmarkLabel: "SPY" });
    }

    // Collect unique symbols and determine primary market
    const symbolMarket = new Map<string, string>();
    let usCount = 0, krCount = 0;
    for (const t of trades) {
      symbolMarket.set(t.symbol as string, t.market as string);
      if (t.market === "US") usCount++; else krCount++;
    }

    // Fetch all price histories in parallel
    const priceData = new Map<string, { dates: string[]; closes: (number | null)[] }>();
    await Promise.all(
      Array.from(symbolMarket.entries()).map(async ([symbol, market]) => {
        const ticker = market === "KR" ? `${symbol}.KS` : symbol;
        priceData.set(symbol, await fetchWeeklyPrices(ticker));
      })
    );

    // Fetch benchmark
    const benchmarkTicker = krCount > usCount ? "^KS11" : "SPY";
    const benchmarkLabel = krCount > usCount ? "KOSPI" : "SPY";
    const benchmarkData = await fetchWeeklyPrices(benchmarkTicker);

    // US·KR 종목이 섞여 있으면 원화 합산 전 환율로 통일해야 한다 —
    // 그렇지 않으면 달러 숫자와 원화 숫자를 그대로 더하는 오류가 난다.
    const needsFx = usCount > 0 && krCount > 0;
    const fxData = needsFx ? await fetchWeeklyPrices("KRW=X") : { dates: [], closes: [] };
    const fxAt = (date: string): number => {
      if (!needsFx) return 1;
      return findPriceAt(fxData.dates, fxData.closes, date) ?? 1;
    };

    // Build unified weekly date list (from first trade date onward)
    const firstDate = trades[0].trade_date as string;
    const allDatesSet = new Set<string>();
    priceData.forEach((h) => h.dates.forEach((d) => { if (d >= firstDate) allDatesSet.add(d); }));
    benchmarkData.dates.forEach((d) => { if (d >= firstDate) allDatesSet.add(d); });
    const sortedDates = Array.from(allDatesSet).sort();

    if (sortedDates.length === 0) {
      return NextResponse.json({ dates: [], myPortfolio: [], benchmark: [], benchmarkLabel });
    }

    // Calculate portfolio value at each date
    let tradeIdx = 0;
    const holdings = new Map<string, number>(); // symbol -> shares
    let portfolioBase: number | null = null;
    let benchmarkBase: number | null = null;

    const myPortfolio: (number | null)[] = [];
    const benchmark: (number | null)[] = [];

    for (const date of sortedDates) {
      // Apply trades up to this date
      while (tradeIdx < trades.length && (trades[tradeIdx].trade_date as string) <= date) {
        const t = trades[tradeIdx];
        const sym = t.symbol as string;
        const sh = Number(t.shares);
        if (t.type === "buy") {
          holdings.set(sym, (holdings.get(sym) ?? 0) + sh);
        } else {
          holdings.set(sym, Math.max(0, (holdings.get(sym) ?? 0) - sh));
        }
        tradeIdx++;
      }

      // Portfolio value — US·KR 혼합 시 원화 기준으로 통일해 합산한다
      let value = 0;
      let valid = true;
      for (const [sym, sh] of holdings) {
        if (sh <= 0) continue;
        const hist = priceData.get(sym);
        if (!hist) { valid = false; break; }
        const price = findPriceAt(hist.dates, hist.closes, date);
        if (price == null) { valid = false; break; }
        const market = symbolMarket.get(sym);
        const rate = market === "US" && needsFx ? fxAt(date) : 1;
        value += sh * price * rate;
      }

      const hasHoldings = Array.from(holdings.values()).some((s) => s > 0);
      if (hasHoldings && valid && value > 0) {
        if (portfolioBase === null) portfolioBase = value;
        myPortfolio.push(+(( value / portfolioBase) * 100).toFixed(2));
      } else {
        myPortfolio.push(null);
      }

      // Benchmark value
      const bp = findPriceAt(benchmarkData.dates, benchmarkData.closes, date);
      if (bp != null) {
        if (benchmarkBase === null) benchmarkBase = bp;
        benchmark.push(+((bp / benchmarkBase) * 100).toFixed(2));
      } else {
        benchmark.push(null);
      }
    }

    return NextResponse.json({ dates: sortedDates, myPortfolio, benchmark, benchmarkLabel });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
