import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS my_watchlist (
      id       INTEGER PRIMARY KEY AUTOINCREMENT,
      market   TEXT NOT NULL,
      symbol   TEXT NOT NULL,
      name     TEXT,
      note     TEXT,
      added_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE(market, symbol)
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const res = await client.execute("SELECT * FROM my_watchlist ORDER BY added_at DESC");
    const rows = res.rows.map((r: any) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj;
    });
    return NextResponse.json(rows);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { market, symbol, name, note } = await request.json();
    if (!market || !symbol) {
      return NextResponse.json({ error: "market, symbol 필수" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: `INSERT INTO my_watchlist (market, symbol, name, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(market, symbol) DO UPDATE SET name=excluded.name, note=excluded.note`,
      args: [market, symbol.toUpperCase(), name ?? null, note ?? null],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
