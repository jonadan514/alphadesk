import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS cashflow_fixed (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      type       TEXT NOT NULL,
      name       TEXT NOT NULL,
      amount     REAL NOT NULL,
      note       TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const result = await client.execute("SELECT id, type, name, amount, note FROM cashflow_fixed ORDER BY type, id");
    return NextResponse.json(result.rows.map(r => ({ id: r[0], type: r[1], name: r[2], amount: r[3], note: r[4] })));
  } catch { return NextResponse.json([]); }
}

export async function POST(req: Request) {
  try {
    const { type, name, amount, note } = await req.json();
    if (!type || !name || amount == null) return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    const client = await ensureTable();
    await client.execute({ sql: "INSERT INTO cashflow_fixed (type, name, amount, note) VALUES (?, ?, ?, ?)", args: [type, name, Number(amount), note ?? null] });
    return NextResponse.json({ ok: true });
  } catch (e: any) { return NextResponse.json({ error: e.message }, { status: 500 }); }
}
