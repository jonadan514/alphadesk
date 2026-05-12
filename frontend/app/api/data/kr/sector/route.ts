import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const client = getClient();
    const result = await client.execute(
      "SELECT payload FROM kr_sector_analysis ORDER BY id DESC LIMIT 1"
    );
    const row = result.rows[0];
    if (!row) return NextResponse.json(null);
    return NextResponse.json(JSON.parse(row[0] as string));
  } catch {
    return NextResponse.json(null);
  }
}
