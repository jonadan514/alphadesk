import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// 실시간 원/달러 환율 — 매수 체크의 포지션 사이징이 원화 입력을 달러로
// 환산할 때 사용한다. Yahoo Finance KRW=X 시세를 그대로 가져온다.
export async function GET() {
  try {
    const res = await fetch(
      "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=1d",
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) throw new Error(`Yahoo ${res.status}`);
    const json = await res.json();
    const rate = json?.chart?.result?.[0]?.meta?.regularMarketPrice;
    if (!rate || typeof rate !== "number") throw new Error("환율 데이터 없음");
    return NextResponse.json({ rate });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "환율 조회 실패";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
