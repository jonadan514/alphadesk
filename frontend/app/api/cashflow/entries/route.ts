import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS cashflow_entries (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      month      TEXT NOT NULL,
      type       TEXT NOT NULL,
      name       TEXT NOT NULL,
      amount     REAL NOT NULL,
      note       TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  return client;
}

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const month = searchParams.get("month");
    const client = await ensureTable();
    const result = month
      ? await client.execute({ sql: "SELECT id, month, type, name, amount, note FROM cashflow_entries WHERE month=? ORDER BY type, id", args: [month] })
      : await client.execute("SELECT id, month, type, name, amount, note FROM cashflow_entries ORDER BY month DESC, type, id");
    return NextResponse.json(result.rows.map(r => ({ id: r[0], month: r[1], type: r[2], name: r[3], amount: r[4], note: r[5] })));
  } catch { return NextResponse.json([]); }
}

export async function POST(req: Request) {
  try {
    const { month, type, name, amount, note } = await req.json();
    if (!month || !type || !name || amount == null) return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    const client = await ensureTable();
    await client.execute({ sql: "INSERT INTO cashflow_entries (month, type, name, amount, note) VALUES (?, ?, ?, ?, ?)", args: [month, type, name, Number(amount), note ?? null] });
    return NextResponse.json({ ok: true });
  } catch (e: any) { return NextResponse.json({ error: e.message }, { status: 500 }); }
}
