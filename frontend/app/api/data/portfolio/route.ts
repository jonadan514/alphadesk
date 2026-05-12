import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

const PORTFOLIOS = [
  { id: "equal_short",     alloc: "equal",    horizon: "short",  hold_days: 20,  take_profit: 0.15 },
  { id: "equal_medium",    alloc: "equal",    horizon: "medium", hold_days: 60,  take_profit: 0.25 },
  { id: "equal_long",      alloc: "equal",    horizon: "long",   hold_days: 120, take_profit: 0.40 },
  { id: "weighted_short",  alloc: "weighted", horizon: "short",  hold_days: 20,  take_profit: 0.15 },
  { id: "weighted_medium", alloc: "weighted", horizon: "medium", hold_days: 60,  take_profit: 0.25 },
  { id: "weighted_long",   alloc: "weighted", horizon: "long",   hold_days: 120, take_profit: 0.40 },
];

const PF_IDS = PORTFOLIOS.map((p) => p.id);

function groupBy<T extends Record<string, unknown>>(arr: T[], key: keyof T): Record<string, T[]> {
  return arr.reduce<Record<string, T[]>>((acc, item) => {
    const k = String(item[key]);
    (acc[k] ??= []).push(item);
    return acc;
  }, {});
}

export async function GET() {
  try {
    const client = getClient();
    const args: (string | number | null)[] = [...PF_IDS];
    const ph   = PF_IDS.map(() => "?").join(",");

    const [snapsRes, holdRes, histRes, tradeRes, benchRes] = await Promise.all([
      client.execute({ sql: `SELECT s.portfolio_id, s.total_value, s.cash, s.holdings_value, s.pnl_total, s.pnl_pct, s.snap_date FROM pf_snapshots s INNER JOIN (SELECT portfolio_id, MAX(snap_date) AS snap_date FROM pf_snapshots WHERE portfolio_id IN (${ph}) GROUP BY portfolio_id) latest USING (portfolio_id, snap_date)`, args }),
      client.execute({ sql: `SELECT portfolio_id, symbol, grade, shares, entry_price, entry_date, weight FROM pf_holdings WHERE portfolio_id IN (${ph})`, args }),
      client.execute({ sql: `SELECT portfolio_id, snap_date AS date, total_value, pnl_pct FROM pf_snapshots WHERE portfolio_id IN (${ph}) ORDER BY portfolio_id, snap_date ASC`, args }),
      client.execute({ sql: `SELECT portfolio_id, symbol, action, shares, price, value, reason, trade_date AS date, pnl, pnl_pct FROM pf_trades WHERE portfolio_id IN (${ph}) ORDER BY trade_date DESC`, args }),
      client.execute({ sql: `SELECT ticker, snap_date AS date, price, pnl_pct FROM pf_benchmark WHERE ticker IN ('SPY','QQQ') ORDER BY ticker, snap_date ASC`, args: [] }),
    ]);

    const toObj = (res: typeof snapsRes) =>
      res.rows.map((r) => Object.fromEntries(res.columns.map((c, i) => [c, r[i]])));

    const snaps    = toObj(snapsRes);
    const holdings = toObj(holdRes);
    const history  = toObj(histRes);
    const trades   = toObj(tradeRes);
    const benchRows = toObj(benchRes);

    const snapMap  = Object.fromEntries(snaps.map((s) => [s.portfolio_id, s]));
    const holdMap  = groupBy(holdings as any, "portfolio_id");
    const histMap  = groupBy(history  as any, "portfolio_id");
    const tradeMap = groupBy(trades   as any, "portfolio_id");
    const benchmarks = groupBy(benchRows as any, "ticker");

    const result: Record<string, unknown> = {};
    for (const pf of PORTFOLIOS) {
      result[pf.id] = {
        config:   pf,
        snapshot: snapMap[pf.id] ?? { total_value: 100000, cash: 100000, holdings_value: 0, pnl_total: 0, pnl_pct: 0, snap_date: null },
        holdings: holdMap[pf.id]  ?? [],
        history:  histMap[pf.id]  ?? [],
        trades:   tradeMap[pf.id] ?? [],
      };
    }
    result.benchmarks = benchmarks;

    return NextResponse.json(result);
  } catch {
    return NextResponse.json({});
  }
}
