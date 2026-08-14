import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 일별 체제 점수(weighted_score) 이력 — data_regime/kr_regime은 매일 덮어써지는
// 스냅샷이라 "오늘이 임계값에 얼마나 여유있는 GO/STOP인지"를 추세로 볼 수 없었다.
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "US").toUpperCase() === "KR" ? "KR" : "US";
    const days = Math.min(Math.max(Number(searchParams.get("days") ?? 60), 1), 365);
    const table = market === "KR" ? "kr_regime_history" : "data_regime_history";

    const client = getClient();
    await client.execute(`
      CREATE TABLE IF NOT EXISTS ${table} (
        date TEXT PRIMARY KEY, payload TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `);

    const res = await client.execute({
      sql: `SELECT date, payload FROM ${table} WHERE date >= date('now', ?) ORDER BY date ASC`,
      args: [`-${days} days`],
    });

    const points = res.rows.map((r) => {
      let payload: any = {};
      try { payload = JSON.parse(r[1] as string); } catch {}
      return {
        date: r[0] as string,
        regime: payload.regime ?? null,
        weighted_score: payload.weighted_score ?? null,
        sensor_scores: payload.sensor_scores ?? {},
      };
    });

    return NextResponse.json({ market, days, points });
  } catch (e: any) {
    return NextResponse.json({ market: "US", days: 0, points: [], error: e.message });
  }
}
