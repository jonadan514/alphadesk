import { NextResponse } from "next/server";
import { queryLatestTimeseries } from "@/src/lib/db";

export const dynamic = "force-dynamic";

interface Pick {
  symbol: string;
  grade?: string;
  sector?: string;
  composite_score?: number;
}

export async function GET() {
  try {
    const rows = await queryLatestTimeseries("data_daily_reports", 1);
    const report = (rows[0] ?? {}) as { picks?: Pick[]; verdict?: string };
    const picks: Pick[] = report.picks ?? [];

    const sectorSet = new Set(picks.map((p) => p.sector ?? "Unknown"));
    const sectorNodes = Array.from(sectorSet).map((sector) => ({
      id: `sector:${sector}`,
      label: sector,
      type: "sector",
    }));

    const symbolNodes = picks.map((p) => ({
      id: p.symbol,
      label: p.symbol,
      type: "symbol",
      grade: p.grade ?? "F",
      score: p.composite_score ?? 0,
      sector: p.sector ?? "Unknown",
    }));

    const edges = picks.map((p) => ({
      source: `sector:${p.sector ?? "Unknown"}`,
      target: p.symbol,
      weight: p.composite_score ?? 0,
    }));

    return NextResponse.json({
      nodes: [...sectorNodes, ...symbolNodes],
      edges,
      verdict: report.verdict ?? null,
    });
  } catch {
    return NextResponse.json({ nodes: [], edges: [], verdict: null });
  }
}
