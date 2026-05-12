import { NextRequest, NextResponse } from "next/server";
import { queryLatestTimeseries } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const limit = Number(req.nextUrl.searchParams.get("limit") ?? "100");
  const data = await queryLatestTimeseries("data_prediction_history", Math.min(limit, 100));
  return NextResponse.json(data);
}
