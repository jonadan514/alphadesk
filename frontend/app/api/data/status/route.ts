import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const client = getClient();

    const [analysis, sector, krSector] = await Promise.allSettled([
      client.execute("SELECT updated_at FROM data_costs WHERE id = 1"),
      client.execute("SELECT date FROM sector_analysis ORDER BY id DESC LIMIT 1"),
      client.execute("SELECT date FROM kr_sector_analysis ORDER BY id DESC LIMIT 1"),
    ]);

    return NextResponse.json({
      lastAnalysis:   analysis.status === "fulfilled" ? (analysis.value.rows[0]?.[0] ?? null) : null,
      lastSector:     sector.status   === "fulfilled" ? (sector.value.rows[0]?.[0]   ?? null) : null,
      lastKrAnalysis: krSector.status === "fulfilled" ? (krSector.value.rows[0]?.[0] ?? null) : null,
    });
  } catch {
    return NextResponse.json({ lastAnalysis: null, lastSector: null, lastKrAnalysis: null });
  }
}
