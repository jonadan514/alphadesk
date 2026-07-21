import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 종목별 정성 체크리스트 — 워치리스트 상세 팝업에 흡수된 워크북 기능.
// 전역 상태였던 옛 workbook_checklist와 달리 (market, symbol)별로 독립 저장된다.
const DEFAULT_ITEMS = [
  { id: "cl-story",    text: "네러티브를 읽고, 이 종목의 스토리를 한 문장으로 말할 수 있는가?", checked: false },
  { id: "cl-catalyst", text: "6개월 내 촉매(실적발표·신제품·정책·계약)가 있는가?", checked: false },
  { id: "cl-risk",     text: "스토리가 깨지는 조건을 알고 있는가?", checked: false },
  { id: "cl-heat",     text: "관심도가 상승 중인가? (식어가는 종목은 아닌지)", checked: false },
  { id: "cl-cross",    text: "오늘 종목 분석(top-picks)에도 등장하는가? (교차 신호)", checked: false },
];

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS stock_checklist (
      market     TEXT NOT NULL,
      symbol     TEXT NOT NULL,
      items      TEXT NOT NULL DEFAULT '[]',
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (market, symbol)
    )
  `);
  return client;
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "").toUpperCase();
    const symbol = (searchParams.get("symbol") ?? "").toUpperCase();
    if (!market || !symbol) {
      return NextResponse.json({ error: "market, symbol 필수" }, { status: 400 });
    }
    const client = await ensureTable();
    const res = await client.execute({
      sql: "SELECT items FROM stock_checklist WHERE market = ? AND symbol = ?",
      args: [market, symbol],
    });
    const row = res.rows[0];
    let items = DEFAULT_ITEMS;
    if (row) {
      try {
        const parsed = JSON.parse(row[0] as string);
        if (Array.isArray(parsed) && parsed.length > 0) items = parsed;
      } catch {}
    }
    return NextResponse.json({ items });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { market, symbol, items } = await request.json();
    if (!market || !symbol || !Array.isArray(items)) {
      return NextResponse.json({ error: "market, symbol, items 필수" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: `INSERT INTO stock_checklist (market, symbol, items, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(market, symbol) DO UPDATE SET
              items = excluded.items, updated_at = excluded.updated_at`,
      args: [market.toUpperCase(), symbol.toUpperCase(), JSON.stringify(items)],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
