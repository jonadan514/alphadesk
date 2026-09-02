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

    // 재무 통과 여부 - 기존 워치리스트 스크리닝(watchlist_candidates)은 트랩필터를
    // "통과"한 종목만 담고 fail/insufficient는 행 자체가 없다(SPEC_fundamentals_cache.md
    // §4의 3분류 중 pass만 구분 가능) - 없다고 "탈락"이라 단정하지 않고 "미확인"으로 둔다.
    const financeByTicker: Record<string, { piotroski: number | null }> = {};
    if (tickers.length > 0) {
      const placeholders = tickers.map(() => "?").join(",");
      try {
        const financeRes = await client.execute({
          sql: `SELECT symbol, piotroski FROM watchlist_candidates WHERE market = 'US' AND symbol IN (${placeholders})`,
          args: tickers,
        });
        financeRes.rows.forEach((r) => {
          financeByTicker[r[0] as string] = { piotroski: r[1] as number | null };
        });
      } catch {
        // watchlist_candidates 조회 실패해도 소속 기업 목록 자체는 보여준다
      }
    }

    const enriched = members.map((m) => ({
      ...m,
      other_themes: crossByTicker[m.ticker] ?? [],
      finance: financeByTicker[m.ticker]
        ? { status: "pass" as const, piotroski: financeByTicker[m.ticker].piotroski }
        : { status: "unknown" as const, piotroski: null },
    }));
    return NextResponse.json({ members: enriched });
  } catch (err) {
    console.error("[api/radar/members] error:", err);
    return NextResponse.json({ members: [] });
  }
}
