import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS buy_check_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      market      TEXT NOT NULL,
      symbol      TEXT NOT NULL,
      checked_at  TEXT NOT NULL DEFAULT (datetime('now')),
      conditions  TEXT NOT NULL,
      pass_count  INTEGER NOT NULL,
      total_count INTEGER NOT NULL,
      verdict     TEXT NOT NULL
    )
  `);
  return client;
}

export async function POST(request: Request) {
  try {
    const { market, symbol, conditions, pass_count, total_count, verdict } = await request.json();
    if (!market || !symbol || !Array.isArray(conditions) || pass_count == null || total_count == null || !verdict) {
      return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: `INSERT INTO buy_check_log (market, symbol, conditions, pass_count, total_count, verdict)
            VALUES (?, ?, ?, ?, ?, ?)`,
      args: [market, String(symbol).toUpperCase(), JSON.stringify(conditions), Number(pass_count), Number(total_count), verdict],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "US").toUpperCase();
    const days = Math.min(Math.max(Number(searchParams.get("days") ?? 90), 1), 365);

    const client = await ensureTable();
    const res = await client.execute({
      sql: `SELECT symbol, checked_at, conditions, pass_count, total_count, verdict
            FROM buy_check_log
            WHERE market = ? AND checked_at >= datetime('now', ?)
            ORDER BY checked_at DESC`,
      args: [market, `-${days} days`],
    });

    const rows = res.rows.map((r) => {
      let conditions: { id: string; status: string }[] = [];
      try { conditions = JSON.parse(r[2] as string); } catch {}
      return {
        symbol: r[0] as string,
        checked_at: r[1] as string,
        conditions,
        pass_count: r[3] as number,
        total_count: r[4] as number,
        verdict: r[5] as string,
      };
    });

    const total = rows.length;
    const passed = rows.filter((row) => row.verdict === "PASS").length;

    const byCondition: Record<string, { fail: number; warn: number; total: number }> = {};
    for (const row of rows) {
      for (const c of row.conditions) {
        if (!byCondition[c.id]) byCondition[c.id] = { fail: 0, warn: 0, total: 0 };
        byCondition[c.id].total += 1;
        if (c.status === "FAIL") byCondition[c.id].fail += 1;
        if (c.status === "WARN") byCondition[c.id].warn += 1;
      }
    }

    return NextResponse.json({
      market,
      days,
      total_checks: total,
      passed_checks: passed,
      pass_rate: total > 0 ? passed / total : null,
      by_condition: byCondition,
      recent: rows.slice(0, 20).map((row) => ({
        symbol: row.symbol, checked_at: row.checked_at, verdict: row.verdict,
        pass_count: row.pass_count, total_count: row.total_count,
      })),
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
