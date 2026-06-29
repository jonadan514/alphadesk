import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS my_trades (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      market     TEXT NOT NULL,
      symbol     TEXT NOT NULL,
      name       TEXT,
      type       TEXT NOT NULL,
      trade_date TEXT NOT NULL,
      price      REAL NOT NULL,
      shares     REAL NOT NULL,
      note       TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const res = await client.execute("SELECT * FROM my_trades ORDER BY trade_date DESC, created_at DESC");
    const trades = res.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj;
    });
    return NextResponse.json(trades);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { market, symbol, name, type, trade_date, price, shares, note } = await request.json();
    if (!market || !symbol || !type || !trade_date || price == null || shares == null) {
      return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: `INSERT INTO my_trades (market, symbol, name, type, trade_date, price, shares, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [market, symbol.toUpperCase(), name ?? null, type, trade_date, Number(price), Number(shares), note ?? null],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
