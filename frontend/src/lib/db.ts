import { createClient } from "@libsql/client";

const ALLOWED_TABLES = new Set([
  "data_regime",
  "data_market_gate",
  "data_ai_summaries",
  "data_gbm_predictions",
  "data_index_prediction",
  "data_risk",
  "data_performance",
  "data_costs",
  "data_daily_reports",
  "data_risk_alerts",
  "data_prediction_history",
  "sector_analysis",
  "pf_snapshots",
  "pf_holdings",
  "pf_trades",
  "pf_benchmark",
  "risk_portfolio",
  "kr_regime",
  "kr_market_gate",
  "kr_daily_reports",
  "kr_sector_analysis",
  "kr_ai_summaries",
  "news_items",
]);

const MAX_LIMIT = 500;

export function getClient() {
  const url = process.env.TURSO_DATA_URL?.trim();
  const authToken = process.env.TURSO_DATA_TOKEN?.trim();
  if (!url || !authToken) {
    throw new Error("TURSO_DATA_URL / TURSO_DATA_TOKEN 환경변수가 설정되지 않았습니다.");
  }
  return createClient({ url, authToken });
}

function assertTable(table: string): void {
  if (!ALLOWED_TABLES.has(table)) {
    throw new Error(`Table "${table}" is not in the allowed list`);
  }
}

export async function querySnapshot(table: string): Promise<Record<string, unknown>> {
  assertTable(table);
  const client = getClient();
  try {
    const result = await client.execute(`SELECT payload FROM ${table} WHERE id = 1`);
    const row = result.rows[0];
    if (!row) return {};
    const raw = row[0] as string;
    const clean = raw.replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null");
    return JSON.parse(clean);
  } catch {
    return {};
  }
}

export async function queryLatestTimeseries(
  table: string,
  limit = 100
): Promise<Record<string, unknown>[]> {
  assertTable(table);
  const safeLimit = Math.min(Math.max(1, limit), MAX_LIMIT);
  const client = getClient();
  try {
    const result = await client.execute({
      sql:  `SELECT date, payload FROM ${table} ORDER BY date DESC LIMIT ?`,
      args: [safeLimit],
    });
    return result.rows.map((r) => ({
      date: r[0] as string,
      ...JSON.parse((r[1] as string).replace(/\bNaN\b/g, "null").replace(/\bInfinity\b/g, "null").replace(/\b-Infinity\b/g, "null")),
    }));
  } catch (err) {
    console.error(`[db] queryLatestTimeseries(${table}) error:`, err);
    return [];
  }
}

export async function queryRaw<T = unknown>(
  table: string,
  sql: string,
  params: (string | number | null)[] = []
): Promise<T[]> {
  assertTable(table);
  const client = getClient();
  try {
    const result = await client.execute({ sql, args: params });
    return result.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      result.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj as T;
    });
  } catch {
    return [];
  }
}
