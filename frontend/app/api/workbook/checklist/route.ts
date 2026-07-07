import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 기본 체크리스트 — 시스템이 자동 검증하는 항목(재무 필터 등)은 넣지 않고,
// 사람의 판단이 필요한 것만 담는다. id는 안정적으로 유지할 것 (토글 매칭에 사용).
const DEFAULTS: Record<string, { id: string; text: string; checked: boolean }[]> = {
  strategy: [
    { id: "st-regime",   text: "시장 체제(Regime)가 Risk-On 또는 Neutral인가?", checked: false },
    { id: "st-gate",     text: "마켓 게이트가 GO인가?", checked: false },
    { id: "st-sector",   text: "진입하려는 섹터가 선행 섹터이거나 현재 경기 사이클과 맞는가?", checked: false },
    { id: "st-size",     text: "단일 종목 비중 15% 이내로 수량을 계산했는가? (매수 체크 탭 계산기)", checked: false },
    { id: "st-stop",     text: "체제별 손절선을 확인하고 매도 규칙을 정했는가?", checked: false },
    { id: "st-horizon",  text: "매수 후 최소 6개월 보유 가능한 여유 자금인가?", checked: false },
  ],
  sector: [
    { id: "se-watch",    text: "워치리스트 후보(적합 점수 상위 50)에 있는 종목인가? — 재무 함정 필터는 자동 통과됨", checked: false },
    { id: "se-fit",      text: "시장 적합 점수가 60점 이상인가?", checked: false },
    { id: "se-cross",    text: "오늘 종목 분석(top-picks)에도 등장하는가? (교차 신호 = 강한 근거)", checked: false },
    { id: "se-story",    text: "네러티브 브리프를 읽고, 이 종목의 스토리를 한 문장으로 말할 수 있는가?", checked: false },
    { id: "se-catalyst", text: "6개월 내 촉매(실적발표·신제품·정책·계약)가 있는가?", checked: false },
    { id: "se-risk",     text: "이 스토리가 깨지는 조건을 알고 있는가? (브리프의 리스크 항목 확인)", checked: false },
    { id: "se-heat",     text: "시장 관심도가 COLD → WARM/HOT으로 살아나고 있는가? (식어가는 종목 아닌지)", checked: false },
    { id: "se-memo",     text: "왜 사는지 워치리스트 메모에 기록했는가?", checked: false },
  ],
};

function backfillIds(sectionId: string, items: any[]): any[] {
  // 과거 저장분에 id가 없으면 부여 (id 없으면 토글 시 전 항목이 함께 토글되는 버그 원인)
  return items.map((it, i) => ({ id: it.id ?? `${sectionId}-legacy-${i}`, ...it }));
}

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
      try {
        const parsed = JSON.parse(row[1] as string);
        if (Array.isArray(parsed)) data[id] = backfillIds(id, parsed);
      } catch {}
    }
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { id, items, reset } = await request.json();
    if (!id) {
      return NextResponse.json({ error: "id 필수" }, { status: 400 });
    }
    const client = await ensureTable();

    // reset: 해당 섹션을 최신 기본 항목으로 교체
    const toSave = reset === true ? (DEFAULTS[id] ?? []) : items;
    if (!Array.isArray(toSave)) {
      return NextResponse.json({ error: "items 필수" }, { status: 400 });
    }

    await client.execute({
      sql: `INSERT INTO workbook_checklist (id, items) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET items = excluded.items`,
      args: [id, JSON.stringify(toSave)],
    });
    return NextResponse.json({ ok: true, items: toSave });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
