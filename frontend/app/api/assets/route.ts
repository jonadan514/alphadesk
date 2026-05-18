import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS asset_items (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      category   TEXT NOT NULL,
      name       TEXT NOT NULL,
      amount     REAL NOT NULL,
      note       TEXT,
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const result = await client.execute("SELECT id, category, name, amount, note, updated_at FROM asset_items ORDER BY category, id");
    const items = result.rows.map((r) => ({
      id: r[0], category: r[1], name: r[2], amount: r[3], note: r[4], updated_at: r[5],
    }));
    return NextResponse.json(items);
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(req: Request) {
  try {
    const { category, name, amount, note } = await req.json();
    if (!category || !name || amount == null) {
      return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: "INSERT INTO asset_items (category, name, amount, note) VALUES (?, ?, ?, ?)",
      args: [category, name, Number(amount), note ?? null],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
