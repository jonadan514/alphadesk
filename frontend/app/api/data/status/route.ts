import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const client = getClient();

    const [report, sector, regime, krReport] = await Promise.allSettled([
      client.execute("SELECT date FROM data_daily_reports ORDER BY date DESC LIMIT 1"),
      client.execute("SELECT date FROM sector_analysis ORDER BY id DESC LIMIT 1"),
      client.execute("SELECT updated_at FROM data_regime ORDER BY id DESC LIMIT 1"),
      client.execute("SELECT date FROM kr_daily_reports ORDER BY date DESC LIMIT 1"),
    ]);

    return NextResponse.json({
      lastAnalysis:   report.status   === "fulfilled" ? (report.value.rows[0]?.[0]   ?? null) : null,
      lastSector:     sector.status   === "fulfilled" ? (sector.value.rows[0]?.[0]   ?? null) : null,
      lastRegime:     regime.status   === "fulfilled" ? ((regime.value.rows[0]?.[0] as string)?.slice(0, 10) ?? null) : null,
      lastKrAnalysis: krReport.status === "fulfilled" ? (krReport.value.rows[0]?.[0] ?? null) : null,
    });
  } catch {
    return NextResponse.json({ lastAnalysis: null, lastSector: null, lastRegime: null, lastKrAnalysis: null });
  }
}
