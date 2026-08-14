import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 펀더멘털 장기(1y/3y) 페이퍼 포트폴리오 보유 종목의 큰 폭 하락·재무 훼손 알림.
// scripts/run_integrated_analysis.py의 check_alerts()가 매일 채운다 — 여기선 조회만.
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(Math.max(Number(searchParams.get("days") ?? 30), 1), 365);

    const client = getClient();
    await client.execute(`
      CREATE TABLE IF NOT EXISTS portfolio_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id TEXT NOT NULL, symbol TEXT NOT NULL,
        alert_type TEXT NOT NULL, detail TEXT NOT NULL, alert_date TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(portfolio_id, symbol, alert_type, alert_date)
      )
    `);

    const res = await client.execute({
      sql: `SELECT symbol, alert_type, detail, alert_date, portfolio_id
            FROM portfolio_alerts
            WHERE alert_date >= date('now', ?)
            ORDER BY alert_date DESC, symbol ASC`,
      args: [`-${days} days`],
    });

    // 같은 종목의 여러 포트폴리오(equal_1y/3y, weighted_1y/3y) 중복 알림은 종목당 한 번으로 합친다.
    const seen = new Map<string, { symbol: string; alert_type: string; detail: any; alert_date: string }>();
    for (const r of res.rows) {
      const symbol = r[0] as string;
      const alert_type = r[1] as string;
      let detail: any = {};
      try { detail = JSON.parse(r[2] as string); } catch {}
      const alert_date = r[3] as string;
      const key = `${symbol}:${alert_type}`;
      if (!seen.has(key)) seen.set(key, { symbol, alert_type, detail, alert_date });
    }

    return NextResponse.json({ alerts: Array.from(seen.values()) });
  } catch (e: any) {
    return NextResponse.json({ alerts: [], error: e.message });
  }
}
