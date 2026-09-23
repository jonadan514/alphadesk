import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 분기 소속 기업 카드 (docs/SPEC_quarterly_screen.md 4-2).
// theme_id 하나의 가장 최근 분기 회사별 신호를 반환한다.

function toNum(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}
function toBool(v: unknown): boolean | null {
  if (v === null || v === undefined) return null;
  return Number(v) !== 0;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const themeId = searchParams.get("theme_id");
  if (!themeId) {
    return NextResponse.json({ members: [] }, { status: 400 });
  }

  try {
    const market = searchParams.get("market") === "KR" ? "KR" : "US";
    const client = getClient();

    // 이 테마의 가장 최근 분기 - 연도·분기를 따로 정렬한다(/api/quarterly와 같은 이유).
    const latestRes = await client.execute({
      sql: `
        SELECT fiscal_year, fiscal_quarter FROM quarterly_company_signals
        WHERE theme_id = ? AND market = ?
        ORDER BY fiscal_year DESC, fiscal_quarter DESC
        LIMIT 1
      `,
      args: [themeId, market],
    });
    const latest = latestRes.rows[0];
    if (!latest) {
      return NextResponse.json({ fiscal_year: null, fiscal_quarter: null, members: [] });
    }
    const fiscalYear = toNum(latest[0])!;
    const fiscalQuarter = toNum(latest[1])!;

    const res = await client.execute({
      sql: `
        SELECT ticker, revenue_transition, revenue_flow, profit_transition, changed,
               revenue_recent, revenue_year_ago, psr, per, valuation_tier
        FROM quarterly_company_signals
        WHERE theme_id = ? AND market = ? AND fiscal_year = ? AND fiscal_quarter = ?
        ORDER BY ticker
      `,
      args: [themeId, market, fiscalYear, fiscalQuarter],
    });

    const rows = res.rows.map((r) => ({
      ticker: r[0] as string,
      revenue_transition: toBool(r[1]),
      revenue_flow: toBool(r[2]),
      profit_transition: toBool(r[3]),
      changed: toBool(r[4]),
      revenue_recent: toNum(r[5]),
      revenue_year_ago: toNum(r[6]),
      psr: toNum(r[7]),
      per: toNum(r[8]),
      valuation_tier: (r[9] as string | null) ?? null,
    }));

    // 재무 판정 - SPEC 5-3 "기존 로직 그대로 옆에 표시"(app/api/radar/members/route.ts와
    // 같은 코드). watchlist_screening_results는 주간 파이프라인이 채운다(문서 4-2 참고
    // - 주간 Actions를 끄면 이 배지가 낡는다. 전환 때 다시 볼 것).
    type Fin = { status: string; piotroski: number | null; reasons: string[] };
    const financeByTicker: Record<string, Fin> = {};
    const tickers = rows.map((m) => m.ticker);
    if (tickers.length > 0) {
      const placeholders = tickers.map(() => "?").join(",");
      try {
        const financeRes = await client.execute({
          sql: `SELECT symbol, status, piotroski, red_flags FROM watchlist_screening_results
                WHERE market = ? AND symbol IN (${placeholders})`,
          args: [market, ...tickers],
        });
        financeRes.rows.forEach((r) => {
          let reasons: string[] = [];
          try {
            const parsed = JSON.parse((r[3] as string) || "[]");
            if (Array.isArray(parsed)) reasons = parsed.filter((x) => typeof x === "string");
          } catch {}
          financeByTicker[r[0] as string] = {
            status: (r[1] as string) || "unknown",
            piotroski: r[2] as number | null,
            reasons,
          };
        });
      } catch {
        // 이 표가 없거나 조회가 실패해도 회사별 신호 자체는 보여준다.
      }
    }

    const members = rows.map((m) => ({
      ...m,
      finance: financeByTicker[m.ticker]
        ? {
            status: financeByTicker[m.ticker].status,
            piotroski: financeByTicker[m.ticker].piotroski,
            reasons: financeByTicker[m.ticker].reasons,
          }
        : { status: "unknown", piotroski: null, reasons: [] as string[] },
    }));

    return NextResponse.json({ fiscal_year: fiscalYear, fiscal_quarter: fiscalQuarter, members });
  } catch (err) {
    console.error("[api/quarterly/members] error:", err);
    return NextResponse.json({ fiscal_year: null, fiscal_quarter: null, members: [] });
  }
}
