import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function PUT(req: Request, { params }: { params: { id: string } }) {
  try {
    const { name, amount, note } = await req.json();
    const client = getClient();
    await client.execute({
      sql: "UPDATE asset_items SET name=?, amount=?, note=?, updated_at=datetime('now') WHERE id=?",
      args: [name, Number(amount), note ?? null, Number(params.id)],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  try {
    const client = getClient();
    await client.execute({ sql: "DELETE FROM asset_items WHERE id=?", args: [Number(params.id)] });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
