import { NextRequest, NextResponse } from "next/server";
import { getWorkbookProfile, saveWorkbookProfile } from "@/src/lib/paperDb";

export const dynamic = "force-dynamic";

export async function GET() {
  const profile = getWorkbookProfile();
  return NextResponse.json(profile ?? null);
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { birth_year, target_year, target_amount, current_assets,
          annual_capacity, pension_limit, irp_limit, isa_limit, expected_rate } = body;

  if (!birth_year || !target_year || !target_amount) {
    return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
  }

  saveWorkbookProfile({
    birth_year: Number(birth_year),
    target_year: Number(target_year),
    target_amount: Number(target_amount),
    current_assets: Number(current_assets ?? 0),
    annual_capacity: Number(annual_capacity ?? 0),
    pension_limit: Number(pension_limit ?? 12000000),
    irp_limit: Number(irp_limit ?? 6000000),
    isa_limit: Number(isa_limit ?? 20000000),
    expected_rate: Number(expected_rate ?? 0.15),
  });

  return NextResponse.json({ ok: true });
}
