import { getDb } from "@/src/lib/board-db";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function ensureTable() {
  getDb().exec(`
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
}

export async function GET() {
  try {
    ensureTable();
    const rows = getDb()
      .prepare("SELECT * FROM my_watchlist ORDER BY added_at DESC")
      .all();
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
    ensureTable();
    getDb()
      .prepare(
        `INSERT INTO my_watchlist (market, symbol, name, note)
         VALUES (?, ?, ?, ?)
         ON CONFLICT(market, symbol) DO UPDATE SET name=excluded.name, note=excluded.note`
      )
      .run(market, symbol.toUpperCase(), name ?? null, note ?? null);
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
