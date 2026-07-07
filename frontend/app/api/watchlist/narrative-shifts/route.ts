import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 오늘 관심도가 상승(COLD→WARM/HOT, WARM→HOT)한 종목 목록.
// generate_narratives.py가 매일 계산해 저장한 trend 필드를 그대로 읽는다.
export async function GET() {
  try {
    const client = getClient();
    const res = await client.execute(
      "SELECT market, symbol, payload, updated_at FROM narrative_briefs " +
      "WHERE updated_at > datetime('now', '-20 hours')"
    );

    const shifts = res.rows
      .map((r) => {
        try {
          const payload = JSON.parse(r[2] as string);
          return {
            market: r[0] as string,
            symbol: r[1] as string,
            sentiment: payload.sentiment,
            prev_sentiment: payload.prev_sentiment,
            trend: payload.trend,
          };
        } catch {
          return null;
        }
      })
      .filter((x): x is NonNullable<typeof x> => x != null && x.trend === "up");

    return NextResponse.json({ shifts });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "알 수 없는 오류";
    if (msg.includes("no such table")) return NextResponse.json({ shifts: [] });
    return NextResponse.json({ shifts: [], error: msg }, { status: 500 });
  }
}
