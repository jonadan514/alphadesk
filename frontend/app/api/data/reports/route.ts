import { NextRequest, NextResponse } from "next/server";
import { queryLatestTimeseries } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const limit = Number(req.nextUrl.searchParams.get("limit") ?? "30");
  const data = await queryLatestTimeseries("data_daily_reports", Math.min(limit, 365));
  return NextResponse.json(data);
}
