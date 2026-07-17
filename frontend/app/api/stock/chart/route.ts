import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// 종목 차트 + 기술 지표 분해 (Yahoo 1년 일봉 기반)
// GET /api/stock/chart?market=US&symbol=NVDA
//  → { points: [{date, close, sma50, sma200}...최근 126일], indicators: {...} }

async function fetchDaily(ySym: string): Promise<{ dates: string[]; closes: number[] } | null> {
  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ySym)}?range=1y&interval=1d`,
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(8000) }
    );
    if (!res.ok) return null;
    const json = await res.json();
    const result = json?.chart?.result?.[0];
    const ts: number[] = result?.timestamp ?? [];
    const raw: (number | null)[] = result?.indicators?.quote?.[0]?.close ?? [];
    const dates: string[] = [];
    const closes: number[] = [];
    ts.forEach((t, i) => {
      const c = raw[i];
      if (c != null && isFinite(c)) {
        dates.push(new Date(t * 1000).toISOString().slice(0, 10));
        closes.push(c);
      }
    });
    return closes.length >= 30 ? { dates, closes } : null;
  } catch {
    return null;
  }
}

function sma(vals: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(vals.length).fill(null);
  let sum = 0;
  for (let i = 0; i < vals.length; i++) {
    sum += vals[i];
    if (i >= n) sum -= vals[i - n];
    if (i >= n - 1) out[i] = sum / n;
  }
  return out;
}

function ema(vals: number[], n: number): number[] {
  const k = 2 / (n + 1);
  const out: number[] = [];
  vals.forEach((v, i) => out.push(i === 0 ? v : v * k + out[i - 1] * (1 - k)));
  return out;
}

function rsi14(closes: number[]): number | null {
  if (closes.length < 15) return null;
  let gain = 0, loss = 0;
  for (let i = 1; i <= 14; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) gain += d; else loss -= d;
  }
  let avgGain = gain / 14, avgLoss = loss / 14;
  for (let i = 15; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    avgGain = (avgGain * 13 + Math.max(d, 0)) / 14;
    avgLoss = (avgLoss * 13 + Math.max(-d, 0)) / 14;
  }
  if (avgLoss === 0) return 100;
  return 100 - 100 / (1 + avgGain / avgLoss);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const market = (searchParams.get("market") ?? "US").toUpperCase();
  const symbol = (searchParams.get("symbol") ?? "").toUpperCase();
  if (!symbol) return NextResponse.json({ error: "symbol 필수" }, { status: 400 });

  // KR 6자리 코드는 KOSPI(.KS) → KOSDAQ(.KQ) 순서로 시도
  const candidates = market === "KR" && /^\d{6}$/.test(symbol)
    ? [`${symbol}.KS`, `${symbol}.KQ`]
    : [symbol];

  let data: { dates: string[]; closes: number[] } | null = null;
  for (const ySym of candidates) {
    data = await fetchDaily(ySym);
    if (data) break;
  }
  if (!data) return NextResponse.json({ error: "가격 데이터 없음" }, { status: 404 });

  const { dates, closes } = data;
  const sma50 = sma(closes, 50);
  const sma200 = sma(closes, 200);

  // MACD (12, 26, 9)
  const emaFast = ema(closes, 12);
  const emaSlow = ema(closes, 26);
  const macdLine = emaFast.map((v, i) => v - emaSlow[i]);
  const signalLine = ema(macdLine, 9);
  const macd = macdLine[macdLine.length - 1];
  const signal = signalLine[signalLine.length - 1];
  const macdPrev = macdLine[macdLine.length - 2] - signalLine[signalLine.length - 2];

  const last = closes[closes.length - 1];
  const s50 = sma50[sma50.length - 1];
  const s200 = sma200[sma200.length - 1];
  const high52 = Math.max(...closes);
  const rsi = rsi14(closes);

  // 최근 126거래일(약 6개월)만 차트로
  const start = Math.max(0, closes.length - 126);
  const points = [];
  for (let i = start; i < closes.length; i++) {
    points.push({
      date: dates[i],
      close: Math.round(closes[i] * 100) / 100,
      sma50: sma50[i] != null ? Math.round((sma50[i] as number) * 100) / 100 : null,
      sma200: sma200[i] != null ? Math.round((sma200[i] as number) * 100) / 100 : null,
    });
  }

  return NextResponse.json({
    symbol, market, points,
    indicators: {
      rsi14: rsi != null ? Math.round(rsi * 10) / 10 : null,
      macd_cross: macd > signal ? "golden" : "dead",
      macd_turning: (macd - signal) * macdPrev < 0,   // 이번에 크로스가 갓 발생했는지
      above_sma50: s50 != null ? last > s50 : null,
      above_sma200: s200 != null ? last > s200 : null,
      golden_cross: s50 != null && s200 != null ? s50 > s200 : null,
      pct_from_52w_high: Math.round((last / high52 - 1) * 1000) / 10,
    },
  });
}
