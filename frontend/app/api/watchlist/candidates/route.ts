import { getDataDb, dbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const db = getDataDb();
  if (!db) return dbUnavailable();

  const { searchParams } = new URL(request.url);
  const market    = searchParams.get("market");    // US | KR | null(전체)
  const regimeFit = searchParams.get("regime_fit"); // growth | dividend | neutral | null

  // watchlist_candidates 테이블이 없으면 빈 배열 반환
  const tableExists = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist_candidates'")
    .get();
  if (!tableExists) return Response.json({ candidates: [], screened_at: null });

  let sql = `
    SELECT market, symbol, name, market_cap, sector,
           piotroski, debt_ratio, interest_coverage,
           cfo_positive_count, red_flags, regime_fit, screened_at
    FROM watchlist_candidates
    WHERE 1=1
  `;
  const params: string[] = [];

  if (market) {
    sql += " AND market = ?";
    params.push(market);
  }
  if (regimeFit) {
    sql += " AND regime_fit = ?";
    params.push(regimeFit);
  }
  sql += " ORDER BY piotroski DESC, market_cap DESC";

  const rows = db.prepare(sql).all(...params) as any[];

  const candidates = rows.map((r) => ({
    ...r,
    red_flags: (() => { try { return JSON.parse(r.red_flags || "[]"); } catch { return []; } })(),
  }));

  const lastScreened = rows[0]?.screened_at ?? null;

  return Response.json({ candidates, screened_at: lastScreened });
}
