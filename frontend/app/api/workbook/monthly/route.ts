import { NextRequest, NextResponse } from "next/server";
import { getWorkbookProfile, getWorkbookMonthly, upsertWorkbookMonthly, deleteWorkbookMonthly } from "@/src/lib/paperDb";

export const dynamic = "force-dynamic";

export async function GET() {
  const entries = getWorkbookMonthly();
  const profile = getWorkbookProfile();

  // Annual usage per year — sum allocations from monthly entries
  const annualUsage: Record<number, { pension: number; irp: number; isa: number; general: number; total: number }> = {};
  for (const e of entries) {
    if (!annualUsage[e.year]) annualUsage[e.year] = { pension: 0, irp: 0, isa: 0, general: 0, total: 0 };
    annualUsage[e.year].pension  += e.pension;
    annualUsage[e.year].irp     += e.irp;
    annualUsage[e.year].isa     += e.isa;
    annualUsage[e.year].general += e.general;
    annualUsage[e.year].total   += e.total_amount;
  }

  return NextResponse.json({ entries, annualUsage, profile });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { year, month, total_amount, pension, irp, isa, general, portfolio_value, note } = body;

  if (!year || !month || total_amount == null) {
    return NextResponse.json({ error: "year, month, total_amount 필수" }, { status: 400 });
  }

  const total = Number(total_amount);
  const p = Number(pension ?? 0);
  const i = Number(irp ?? 0);
  const s = Number(isa ?? 0);
  const g = Number(general ?? 0);

  if ([total, p, i, s, g].some(isNaN)) {
    return NextResponse.json({ error: "금액은 숫자여야 합니다" }, { status: 400 });
  }

  upsertWorkbookMonthly({
    year: Number(year), month: Number(month),
    total_amount: total,
    pension: p, irp: i, isa: s, general: g,
    portfolio_value: portfolio_value != null ? Number(portfolio_value) : null,
    note: note ?? null,
  });

  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest) {
  const year = Number(req.nextUrl.searchParams.get("year"));
  const month = Number(req.nextUrl.searchParams.get("month"));
  if (!year || !month) return NextResponse.json({ error: "year, month 필수" }, { status: 400 });
  deleteWorkbookMonthly(year, month);
  return NextResponse.json({ ok: true });
}
