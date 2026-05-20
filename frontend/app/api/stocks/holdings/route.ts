import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS stock_holdings (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      market        TEXT NOT NULL DEFAULT 'US',
      symbol        TEXT NOT NULL,
      name          TEXT,
      shares        REAL NOT NULL,
      avg_price     REAL NOT NULL,
      current_price REAL,
      note          TEXT,
      updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const res = await client.execute(
      "SELECT id, market, symbol, name, shares, avg_price, current_price, note FROM stock_holdings ORDER BY market, symbol"
    );
    return NextResponse.json(res.rows.map(r => ({
      id: r[0], market: r[1], symbol: r[2], name: r[3],
      shares: r[4], avg_price: r[5], current_price: r[6], note: r[7],
    })));
  } catch { return NextResponse.json([]); }
}

export async function POST(req: Request) {
  try {
    const { market, symbol, name, shares, avg_price, current_price, note } = await req.json();
    if (!symbol || shares == null || avg_price == null) {
      return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: "INSERT INTO stock_holdings (market, symbol, name, shares, avg_price, current_price, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
      args: [market ?? "US", symbol.toUpperCase(), name ?? null, Number(shares), Number(avg_price), current_price != null ? Number(current_price) : null, note ?? null],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) { return NextResponse.json({ error: e.message }, { status: 500 }); }
}
