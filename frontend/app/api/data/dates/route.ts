import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const client = getClient();
    const result = await client.execute(
      "SELECT date FROM data_daily_reports ORDER BY date DESC LIMIT 365"
    );
    return NextResponse.json(result.rows.map((r) => r[0]));
  } catch {
    return NextResponse.json([]);
  }
}
