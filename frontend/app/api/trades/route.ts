import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS my_trades (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      market     TEXT NOT NULL,
      symbol     TEXT NOT NULL,
      name       TEXT,
      type       TEXT NOT NULL,
      trade_date TEXT NOT NULL,
      price      REAL NOT NULL,
      shares     REAL NOT NULL,
      note       TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  // 매수 시점의 체크리스트·메모·등급·게이트를 불변으로 잠가두는 스냅샷.
  // 이 테이블에는 UPDATE 라우트가 없다 — 한 번 쓰이면 다시는 안 바뀐다.
  await client.execute(`
    CREATE TABLE IF NOT EXISTS trade_decision_snapshots (
      trade_id        INTEGER PRIMARY KEY,
      market          TEXT NOT NULL,
      symbol          TEXT NOT NULL,
      snapshot_at     TEXT NOT NULL DEFAULT (datetime('now')),
      checklist       TEXT,
      checklist_note  TEXT,
      trade_note      TEXT,
      grade           TEXT,
      composite_score REAL,
      gate            TEXT,
      regime          TEXT
    )
  `);
  return client;
}

async function readSnapshotSource(
  client: ReturnType<typeof getClient>,
  market: string,
  symbol: string
) {
  const [clRes, noteRes] = await Promise.all([
    client.execute({
      sql: "SELECT items FROM stock_checklist WHERE market = ? AND symbol = ?",
      args: [market, symbol],
    }).catch(() => null),
    client.execute({
      sql: "SELECT note FROM my_watchlist WHERE market = ? AND symbol = ?",
      args: [market, symbol],
    }).catch(() => null),
  ]);
  const checklist = clRes?.rows[0] ? (clRes.rows[0][0] as string) : null;
  const checklistNote = noteRes?.rows[0] ? (noteRes.rows[0][0] as string | null) : null;

  const scoresTable = market === "KR" ? "kr_full_scores" : "data_full_scores";
  let grade: string | null = null;
  let compositeScore: number | null = null;
  try {
    const sRes = await client.execute(`SELECT payload FROM ${scoresTable} WHERE id = 1`);
    if (sRes.rows[0]) {
      const payload = JSON.parse(sRes.rows[0][0] as string);
      const entry = (payload.scores ?? []).find((s: any) => s.symbol === symbol);
      if (entry) {
        grade = entry.grade ?? null;
        compositeScore = entry.composite_score ?? null;
      }
    }
  } catch {}

  const gateTable = market === "KR" ? "kr_market_gate" : "data_market_gate";
  const regimeTable = market === "KR" ? "kr_regime" : "data_regime";
  let gate: string | null = null;
  let regime: string | null = null;
  try {
    const gRes = await client.execute(`SELECT payload FROM ${gateTable} WHERE id = 1`);
    if (gRes.rows[0]) gate = JSON.parse(gRes.rows[0][0] as string).gate ?? null;
  } catch {}
  try {
    const rRes = await client.execute(`SELECT payload FROM ${regimeTable} WHERE id = 1`);
    if (rRes.rows[0]) regime = JSON.parse(rRes.rows[0][0] as string).regime ?? null;
  } catch {}

  return { checklist, checklistNote, grade, compositeScore, gate, regime };
}

export async function GET() {
  try {
    const client = await ensureTable();
    const [tradesRes, snapRes] = await Promise.all([
      client.execute("SELECT * FROM my_trades ORDER BY trade_date DESC, created_at DESC"),
      client.execute("SELECT * FROM trade_decision_snapshots"),
    ]);

    const snapByTradeId: Record<number, Record<string, unknown>> = {};
    snapRes.rows.forEach((r) => {
      const obj: Record<string, unknown> = {};
      snapRes.columns.forEach((col, i) => { obj[col] = r[i]; });
      snapByTradeId[Number(obj.trade_id)] = obj;
    });

    const trades = tradesRes.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      tradesRes.columns.forEach((col, i) => { obj[col] = r[i]; });
      return { ...obj, decision_snapshot: snapByTradeId[Number(obj.id)] ?? null };
    });
    return NextResponse.json(trades);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { market, symbol, name, type, trade_date, price, shares, note } = await request.json();
    if (!market || !symbol || !type || !trade_date || price == null || shares == null) {
      return NextResponse.json({ error: "필수 항목 누락" }, { status: 400 });
    }
    const client = await ensureTable();
    const upperSymbol = symbol.toUpperCase();
    const result = await client.execute({
      sql: `INSERT INTO my_trades (market, symbol, name, type, trade_date, price, shares, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [market, upperSymbol, name ?? null, type, trade_date, Number(price), Number(shares), note ?? null],
    });

    // 매수일 때만 그 순간의 판단 근거를 스냅샷으로 잠금 (매도는 청산일 뿐 신규 판단이 아님)
    if (type === "buy" && result.lastInsertRowid != null) {
      const tradeId = Number(result.lastInsertRowid);
      const src = await readSnapshotSource(client, market, upperSymbol);
      await client.execute({
        sql: `INSERT INTO trade_decision_snapshots
                (trade_id, market, symbol, checklist, checklist_note, trade_note, grade, composite_score, gate, regime)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        args: [
          tradeId, market, upperSymbol,
          src.checklist, src.checklistNote, note ?? null,
          src.grade, src.compositeScore, src.gate, src.regime,
        ],
      });
    }

    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
