import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

const DEFAULTS: Record<string, { text: string; checked: boolean }[]> = {
  strategy: [
    { text: "시장 체제(Regime)가 Risk-On 또는 Neutral인가?", checked: false },
    { text: "마켓 게이트가 GO 또는 CAUTION인가?", checked: false },
    { text: "진입하려는 섹터가 현재 경기 사이클과 맞는가?", checked: false },
    { text: "분산 투자 원칙을 지키고 있는가? (단일 종목 비중 < 15%)", checked: false },
    { text: "손절 기준을 미리 정했는가?", checked: false },
    { text: "매수 후 최소 6개월 보유 가능한 자금인가?", checked: false },
  ],
  sector: [
    { text: "워치리스트 스크리닝을 통과한 종목인가?", checked: false },
    { text: "섹터 분석에서 RS(상대강도) 상위권인가?", checked: false },
    { text: "해당 섹터 ETF가 상승 추세인가?", checked: false },
    { text: "Piotroski F-Score ≥ 5인가?", checked: false },
    { text: "ROE ≥ 8%인가? (자본 효율성)", checked: false },
    { text: "이자보상배율 ≥ 1.5인가? (부채 부담 없음)", checked: false },
    { text: "최근 2년 중 1년 이상 매출 성장인가?", checked: false },
    { text: "부채비율 ≤ 150%인가? (금융업 제외)", checked: false },
    { text: "영업현금흐름이 2년 연속 플러스인가?", checked: false },
  ],
};

async function ensureTable() {
  const client = getClient();
  await client.execute(`
    CREATE TABLE IF NOT EXISTS workbook_checklist (
      id    TEXT PRIMARY KEY,
      items TEXT NOT NULL DEFAULT '[]'
    )
  `);
  return client;
}

export async function GET() {
  try {
    const client = await ensureTable();
    const res = await client.execute("SELECT id, items FROM workbook_checklist");

    const data: Record<string, any[]> = { strategy: DEFAULTS.strategy, sector: DEFAULTS.sector };
    for (const row of res.rows) {
      const id = row[0] as string;
      try { data[id] = JSON.parse(row[1] as string); } catch {}
    }
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { id, items } = await request.json();
    if (!id || !Array.isArray(items)) {
      return NextResponse.json({ error: "id, items 필수" }, { status: 400 });
    }
    const client = await ensureTable();
    await client.execute({
      sql: `INSERT INTO workbook_checklist (id, items) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET items = excluded.items`,
      args: [id, JSON.stringify(items)],
    });
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
