import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market    = searchParams.get("market");
    const regimeFit = searchParams.get("regime_fit");

    const client = getClient();

    const args: (string | null)[] = [];
    let sql = `
      SELECT market, symbol, name, market_cap, sector,
             piotroski, debt_ratio, interest_coverage,
             cfo_positive_count, red_flags, regime_fit,
             roe, current_price, data_notes, screened_at
      FROM watchlist_candidates
      WHERE 1=1
    `;
    if (market)    { sql += " AND market = ?";     args.push(market); }
    if (regimeFit) { sql += " AND regime_fit = ?"; args.push(regimeFit); }
    // 순위 없는 후보 목록 — 모멘텀/품질 점수 정렬 없음. 알파벳 순으로만 안정적 표시.
    sql += " ORDER BY market, symbol";

    const res = await client.execute({ sql, args }).catch(() => ({ rows: [], columns: [] }));

    const candidates = res.rows.map((r: any) => {
      const obj: Record<string, unknown> = {};
      (res as any).columns?.forEach((col: string, i: number) => { obj[col] = r[i]; });
      obj.red_flags = (() => { try { return JSON.parse((obj.red_flags as string) || "[]"); } catch { return []; } })();
      obj.data_notes = (() => { try { return JSON.parse((obj.data_notes as string) || "{}"); } catch { return {}; } })();
      return obj;
    });

    const lastScreened = (candidates[0] as any)?.screened_at ?? null;
    return NextResponse.json({ candidates, screened_at: lastScreened });
  } catch {
    return NextResponse.json({ candidates: [], screened_at: null });
  }
}
