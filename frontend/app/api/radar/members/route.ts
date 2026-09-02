import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 소속 기업 상세 (SPEC §6.4) - theme_id 하나의 최신 승인 매핑을 반환.
// 다른 테마에도 걸린 기업은 other_themes에 그 테마 id들을 담아 함께 표시("동시 소속이 정보다").
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const themeId = searchParams.get("theme_id");
  if (!themeId) {
    return NextResponse.json({ members: [] }, { status: 400 });
  }

  try {
    const client = getClient();

    // SPEC §5 - "최신 run_id + approved=1"
    const runRes = await client.execute({
      sql: "SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = 'US' AND approved = 1",
      args: [themeId],
    });
    const runId = runRes.rows[0]?.[0] as string | null;
    if (!runId) {
      return NextResponse.json({ members: [] });
    }

    const res = await client.execute({
      sql: `
        SELECT ticker, stage, evidence, linkage, confidence, flagged
        FROM theme_members
        WHERE theme_id = ? AND market = 'US' AND run_id = ? AND approved = 1
        ORDER BY CASE linkage WHEN 'direct' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END, ticker
      `,
      args: [themeId, runId],
    });
    const members = res.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj;
    }) as { ticker: string; stage: string | null; evidence: string | null; linkage: string; confidence: string; flagged: number }[];

    const tickers = members.map((m) => m.ticker);
    const crossByTicker: Record<string, string[]> = {};
    if (tickers.length > 0) {
      const placeholders = tickers.map(() => "?").join(",");
      const crossRes = await client.execute({
        sql: `
          SELECT ticker, theme_id FROM theme_members
          WHERE ticker IN (${placeholders}) AND market = 'US' AND approved = 1 AND theme_id != ?
        `,
        args: [...tickers, themeId],
      });
      crossRes.rows.forEach((r) => {
        const ticker = r[0] as string;
        const otherTheme = r[1] as string;
        if (!crossByTicker[ticker]) crossByTicker[ticker] = [];
        if (!crossByTicker[ticker].includes(otherTheme)) crossByTicker[ticker].push(otherTheme);
      });
    }

    const enriched = members.map((m) => ({ ...m, other_themes: crossByTicker[m.ticker] ?? [] }));
    return NextResponse.json({ members: enriched });
  } catch (err) {
    console.error("[api/radar/members] error:", err);
    return NextResponse.json({ members: [] });
  }
}
