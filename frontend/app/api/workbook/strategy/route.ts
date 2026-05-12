import { NextRequest, NextResponse } from "next/server";
import { getStrategyJournal, upsertStrategyJournal, deleteStrategyJournal } from "@/src/lib/paperDb";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(getStrategyJournal());
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { date, market_context, strategy_focus, holdings, concerns } = body;
  if (!date) return NextResponse.json({ error: "date 필수" }, { status: 400 });
  upsertStrategyJournal({ date, market_context, strategy_focus, holdings, concerns });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest) {
  const date = req.nextUrl.searchParams.get("date");
  if (!date) return NextResponse.json({ error: "date 필수" }, { status: 400 });
  deleteStrategyJournal(date);
  return NextResponse.json({ ok: true });
}
