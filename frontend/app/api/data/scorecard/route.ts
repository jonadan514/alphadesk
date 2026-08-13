import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

type Bucket = { fwd_30d: number | null; fwd_60d: number | null; fwd_90d: number | null; n: number };

function avg(values: (number | null)[]): number | null {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function bucket(rows: { fwd_30d_ret: number | null; fwd_60d_ret: number | null; fwd_90d_ret: number | null }[]): Bucket {
  return {
    fwd_30d: avg(rows.map((r) => r.fwd_30d_ret)),
    fwd_60d: avg(rows.map((r) => r.fwd_60d_ret)),
    fwd_90d: avg(rows.map((r) => r.fwd_90d_ret)),
    n: rows.filter((r) => r.fwd_30d_ret != null).length,
  };
}

// scripts/compute_pick_returns.py가 아직 한 번도 안 돌았으면(첫 배포 직후, 매주 일요일 전)
// 이 테이블들이 Turso에 아직 없다 — 없는 테이블을 SELECT하면 500이 나서 화면이 깨지므로
// 여기서도 방어적으로 생성해둔다 (다른 라우트들의 ensureTable() 패턴과 동일).
async function ensureTables(client: ReturnType<typeof getClient>, picksTable: string, benchTable: string) {
  await Promise.all([
    client.execute(`
      CREATE TABLE IF NOT EXISTS ${picksTable} (
        date TEXT NOT NULL, symbol TEXT NOT NULL, grade TEXT, gate TEXT, regime TEXT, action TEXT,
        entry_price REAL, fwd_30d_ret REAL, fwd_60d_ret REAL, fwd_90d_ret REAL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (date, symbol)
      )
    `),
    client.execute(`
      CREATE TABLE IF NOT EXISTS ${benchTable} (
        date TEXT NOT NULL PRIMARY KEY, ticker TEXT NOT NULL, entry_price REAL,
        fwd_30d_ret REAL, fwd_60d_ret REAL, fwd_90d_ret REAL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `),
    client.execute(`
      CREATE TABLE IF NOT EXISTS my_trade_returns (
        trade_id INTEGER PRIMARY KEY, market TEXT NOT NULL, symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
        entry_price REAL, fwd_30d_ret REAL, fwd_60d_ret REAL, fwd_90d_ret REAL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `),
  ]);
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "US").toUpperCase() === "KR" ? "KR" : "US";
    const picksTable = market === "KR" ? "kr_pick_returns" : "data_pick_returns";
    const benchTable = market === "KR" ? "kr_benchmark_returns" : "data_benchmark_returns";

    const client = getClient();
    await ensureTables(client, picksTable, benchTable);

    const [picksRes, benchRes, tradesRes] = await Promise.all([
      client.execute(
        `SELECT date, symbol, grade, gate, regime, action, fwd_30d_ret, fwd_60d_ret, fwd_90d_ret FROM ${picksTable}`
      ),
      client.execute(`SELECT date, fwd_30d_ret, fwd_60d_ret, fwd_90d_ret FROM ${benchTable}`),
      client.execute({
        sql: `SELECT symbol, trade_date, fwd_30d_ret, fwd_60d_ret, fwd_90d_ret FROM my_trade_returns WHERE market = ?`,
        args: [market],
      }),
    ]);

    const picks = picksRes.rows.map((r) => ({
      date: r[0] as string,
      symbol: r[1] as string,
      grade: r[2] as string | null,
      gate: r[3] as string | null,
      regime: r[4] as string | null,
      action: r[5] as string | null,
      fwd_30d_ret: r[6] as number | null,
      fwd_60d_ret: r[7] as number | null,
      fwd_90d_ret: r[8] as number | null,
    }));
    const bench = benchRes.rows.map((r) => ({
      date: r[0] as string,
      fwd_30d_ret: r[1] as number | null,
      fwd_60d_ret: r[2] as number | null,
      fwd_90d_ret: r[3] as number | null,
    }));
    const trades = tradesRes.rows.map((r) => ({
      symbol: r[0] as string,
      trade_date: r[1] as string,
      fwd_30d_ret: r[2] as number | null,
      fwd_60d_ret: r[3] as number | null,
      fwd_90d_ret: r[4] as number | null,
    }));

    const comparison = {
      benchmark: bucket(bench),
      filtered_equal_weight: bucket(picks),
      actual_trades: bucket(trades),
    };

    const byGrade: Record<string, Bucket> = {};
    for (const grade of ["A", "B", "C", "D", "F"]) {
      byGrade[grade] = bucket(picks.filter((p) => p.grade === grade));
    }

    const byGate: Record<string, Bucket> = {};
    for (const gate of ["GO", "CAUTION", "STOP"]) {
      byGate[gate] = bucket(picks.filter((p) => p.gate === gate));
    }

    const dates = picks.map((p) => p.date).sort();

    return NextResponse.json({
      market,
      comparison,
      by_grade: byGrade,
      by_gate: byGate,
      total_picks: picks.length,
      total_trades: trades.length,
      earliest_date: dates[0] ?? null,
      latest_date: dates[dates.length - 1] ?? null,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
