import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function PUT(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const { symbol, name, shares, avg_price, current_price, note } = await req.json();
    const client = getClient();
    await client.execute({
      sql: "UPDATE stock_holdings SET symbol=?, name=?, shares=?, avg_price=?, current_price=?, note=?, updated_at=datetime('now') WHERE id=?",
      args: [symbol.toUpperCase(), name ?? null, Number(shares), Number(avg_price), current_price != null ? Number(current_price) : null, note ?? null, Number(id)],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) { return NextResponse.json({ error: e.message }, { status: 500 }); }
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const client = getClient();
    await client.execute({ sql: "DELETE FROM stock_holdings WHERE id=?", args: [Number(id)] });
    return NextResponse.json({ ok: true });
  } catch (e: any) { return NextResponse.json({ error: e.message }, { status: 500 }); }
}
