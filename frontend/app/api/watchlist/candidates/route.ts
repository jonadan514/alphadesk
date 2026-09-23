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

    // 이번 회차에 새로 통과한 종목 표시 (watchlist_candidate_history 비교).
    //
    // 후보가 275종목이라 목록만으로는 "이번 주에 뭐가 달라졌는지"를 알 수 없었다.
    // 주간 브리핑(generate_weekly_briefing.py)이 같은 계산을 이미 하고 있었지만 그
    // 결과가 텔레그램과 /briefing 화면에만 가고 정작 이 목록에는 오지 않았다.
    //
    // 스냅샷(watchlist_weekly_snapshots) 대신 이력 테이블을 쓰는 이유: 스냅샷은
    // 브리핑이 돌 때 "이번 주 것"까지 덮어써서, 브리핑이 먼저 돌면 신규가 0으로
    // 보인다. 이력 테이블은 스크리닝이 회차마다 쌓고 지우지 않아 순서에 안 흔들린다.
    //
    // 직전 회차가 아예 없으면(첫 스크리닝) is_new를 true가 아니라 **null**로 둔다 -
    // 모르는 것을 "신규"로 단정하면 첫 주에 275종목이 전부 새것처럼 보인다.
    await attachNewFlags(client, candidates, market);

    const lastScreened = (candidates[0] as any)?.screened_at ?? null;
    return NextResponse.json({ candidates, screened_at: lastScreened });
  } catch {
    return NextResponse.json({ candidates: [], screened_at: null });
  }
}

async function attachNewFlags(
  client: ReturnType<typeof getClient>,
  candidates: Record<string, unknown>[],
  market: string | null,
): Promise<void> {
  if (candidates.length === 0) return;
  try {
    const markets = market ? [market] : Array.from(new Set(candidates.map((c) => c.market as string)));

    for (const mkt of markets) {
      const dateRes = await client.execute({
        sql: `SELECT DISTINCT screened_date FROM watchlist_candidate_history
              WHERE market = ? ORDER BY screened_date DESC LIMIT 2`,
        args: [mkt],
      });
      const prevDate = dateRes.rows[1]?.[0] as string | undefined;
      const rowsOfMarket = candidates.filter((c) => c.market === mkt);

      if (!prevDate) {
        rowsOfMarket.forEach((c) => { c.is_new = null; });
        continue;
      }

      const prevRes = await client.execute({
        sql: `SELECT symbol FROM watchlist_candidate_history
              WHERE market = ? AND screened_date = ?`,
        args: [mkt, prevDate],
      });
      const prevSymbols = new Set(prevRes.rows.map((r) => r[0] as string));

      // 처음 등장인지 재진입인지 구분한다 - 둘 다 "신규"지만 의미가 다르다.
      const firstRes = await client.execute({
        sql: `SELECT symbol, MIN(screened_date) FROM watchlist_candidate_history
              WHERE market = ? GROUP BY symbol`,
        args: [mkt],
      });
      const firstSeen = new Map(firstRes.rows.map((r) => [r[0] as string, r[1] as string]));
      const latestDate = dateRes.rows[0]?.[0] as string | undefined;

      rowsOfMarket.forEach((c) => {
        const sym = c.symbol as string;
        c.is_new = !prevSymbols.has(sym);
        c.first_seen = firstSeen.get(sym) ?? null;
        c.is_reentry = c.is_new === true && firstSeen.get(sym) !== undefined
          && firstSeen.get(sym) !== latestDate;
      });
    }
  } catch {
    // 이력 조회가 실패해도 후보 목록 자체는 그대로 보여준다.
    candidates.forEach((c) => { if (c.is_new === undefined) c.is_new = null; });
  }
}
