import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// Phase B에서 한국 추가 - ?market=KR로 조회(생략 시 US, 기존 호출 하위호환).
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = searchParams.get("market") === "KR" ? "KR" : "US";
    const client = getClient();

    const weekRes = await client.execute({
      sql: "SELECT MAX(week_start) FROM theme_signals WHERE market = ?",
      args: [market],
    });
    const weekStart = weekRes.rows[0]?.[0] as string | null;
    if (!weekStart) {
      return NextResponse.json({ week_start: null, signals: [] });
    }

    const res = await client.execute({
      sql: `
        SELECT theme_id, news_count, news_baseline, news_ratio, news_arrow,
               earn_members, earn_improved, earn_insufficient, earn_ratio, earn_arrow, earn_as_of,
               price_median_ret, price_index_ret, price_excess, price_arrow,
               label, member_count, mapping_run_id
        FROM theme_signals
        WHERE market = ? AND week_start = ?
      `,
      args: [market, weekStart],
    });

    const signals = res.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj;
    });

    return NextResponse.json({ week_start: weekStart, signals });
  } catch (err) {
    console.error("[api/radar] error:", err);
    return NextResponse.json({ week_start: null, signals: [] });
  }
}
