import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// Phase A는 미국 시장만 (SPEC_phase_a_signals.md 범위) - market='US' 고정.
export async function GET() {
  try {
    const client = getClient();

    const weekRes = await client.execute(
      "SELECT MAX(week_start) FROM theme_signals WHERE market = 'US'"
    );
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
        WHERE market = 'US' AND week_start = ?
      `,
      args: [weekStart],
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
