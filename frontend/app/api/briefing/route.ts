import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 주간 브리핑 아카이브 — scripts/generate_weekly_briefing.py가 매주 생성
export async function GET() {
  try {
    const client = getClient();
    const res = await client.execute(
      "SELECT week, payload, created_at FROM weekly_briefings ORDER BY week DESC LIMIT 12"
    );
    const briefings = res.rows
      .map((r) => {
        try {
          return { week: r[0] as string, created_at: r[2] as string, ...JSON.parse(r[1] as string) };
        } catch {
          return null;
        }
      })
      .filter(Boolean);
    return NextResponse.json({ briefings });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "알 수 없는 오류";
    if (msg.includes("no such table")) return NextResponse.json({ briefings: [] });
    return NextResponse.json({ briefings: [], error: msg }, { status: 500 });
  }
}
