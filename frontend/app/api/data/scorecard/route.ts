import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// scripts/compute_pick_returns.py의 HORIZONS와 반드시 일치해야 함.
// 30/60/90일 = 스윙 검증용, 180/365/730일 = 장기(6개월/1년/2년) 펀더멘털 검증용.
const HORIZONS = [30, 60, 90, 180, 365, 730] as const;
const RET_COLS = HORIZONS.map((h) => `fwd_${h}d_ret`);

type Bucket = Record<string, number | null> & { n: number };

function avg(values: (number | null)[]): number | null {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function bucket(rows: Record<string, number | null>[]): Bucket {
  const out: Bucket = { n: rows.filter((r) => r[RET_COLS[0]] != null).length };
  for (const col of RET_COLS) {
    out[col] = avg(rows.map((r) => r[col]));
  }
  return out;
}

// scripts/compute_pick_returns.py가 아직 한 번도 안 돌았으면(첫 배포 직후, 매주 일요일 전)
// 이 테이블들이 Turso에 아직 없다 — 없는 테이블을 SELECT하면 500이 나서 화면이 깨지므로
// 여기서도 방어적으로 생성해둔다 (다른 라우트들의 ensureTable() 패턴과 동일).
async function ensureTables(client: ReturnType<typeof getClient>, picksTable: string, benchTable: string) {
  const retCols = RET_COLS.map((c) => `${c} REAL`).join(", ");
  await Promise.all([
    client.execute(`
      CREATE TABLE IF NOT EXISTS ${picksTable} (
        date TEXT NOT NULL, symbol TEXT NOT NULL, grade TEXT, gate TEXT, regime TEXT, action TEXT,
        entry_price REAL, ${retCols},
        updated_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (date, symbol)
      )
    `),
    client.execute(`
      CREATE TABLE IF NOT EXISTS ${benchTable} (
        date TEXT NOT NULL PRIMARY KEY, ticker TEXT NOT NULL, entry_price REAL,
        ${retCols},
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `),
  ]);
  // 이미 배포되어 있던(30/60/90일 컬럼만 있는) 테이블에 새 기간 컬럼을 뒤늦게 추가.
  // 컬럼이 이미 있으면 에러 — 하나씩 개별 실행하고 실패는 무시(멱등적).
  for (const table of [picksTable, benchTable]) {
    for (const col of RET_COLS) {
      try {
        await client.execute(`ALTER TABLE ${table} ADD COLUMN ${col} REAL`);
      } catch {
        // 컬럼이 이미 존재 — 무시
      }
    }
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const market = (searchParams.get("market") ?? "US").toUpperCase() === "KR" ? "KR" : "US";
    const picksTable = market === "KR" ? "kr_pick_returns" : "data_pick_returns";
    const benchTable = market === "KR" ? "kr_benchmark_returns" : "data_benchmark_returns";

    const client = getClient();
    await ensureTables(client, picksTable, benchTable);

    const retColList = RET_COLS.join(", ");

    const [picksRes, benchRes] = await Promise.all([
      client.execute(
        `SELECT date, symbol, grade, gate, regime, action, ${retColList} FROM ${picksTable}`
      ),
      client.execute(`SELECT date, ${retColList} FROM ${benchTable}`),
    ]);

    // 앞쪽 6개 컬럼(date/symbol/grade/gate/regime/action) 뒤로 RET_COLS가 이어지는 고정 순서
    const picks = picksRes.rows.map((r) => {
      const row: any = {
        date: r[0] as string, symbol: r[1] as string, grade: r[2] as string | null,
        gate: r[3] as string | null, regime: r[4] as string | null, action: r[5] as string | null,
      };
      RET_COLS.forEach((c, i) => { row[c] = r[6 + i] as number | null; });
      return row;
    });
    const bench = benchRes.rows.map((r) => {
      const row: any = { date: r[0] as string };
      RET_COLS.forEach((c, i) => { row[c] = r[1 + i] as number | null; });
      return row;
    });

    const comparison = {
      benchmark: bucket(bench),
      filtered_equal_weight: bucket(picks),
    };

    // "grade" 컬럼은 예전엔 A~F 문자 등급이었지만, 순위 없는 리스트업 도구로
    // 전환하며 compute_pick_returns.py가 Piotroski F-Score(0~9)를 그대로 저장하도록
    // 바뀌었다(scripts/compute_pick_returns.py 참고). 문자 등급으로 필터링하면
    // 숫자와 절대 안 맞아 항상 빈 결과였던 걸 발견해 구간 필터로 교체 - 워치리스트
    // 페이지의 PiotroskiBadge와 동일한 경계값(7+/5+/그 미만)을 쓴다.
    // 리팩터링 이전 날짜의 옛 문자 등급 행은 숫자로 안 읽히므로 이 구간 통계에서는
    // 자연히 제외된다(이력 자체는 테이블에 그대로 남아있음).
    const PIOTROSKI_TIERS: { key: string; test: (g: number) => boolean }[] = [
      { key: "7-9 (우수)", test: (g) => g >= 7 },
      { key: "5-6 (보통)", test: (g) => g >= 5 && g < 7 },
      { key: "0-4 (취약)", test: (g) => g < 5 },
    ];
    const byPiotroski: Record<string, Bucket> = {};
    for (const tier of PIOTROSKI_TIERS) {
      byPiotroski[tier.key] = bucket(picks.filter((p) => {
        const g = p.grade != null ? Number(p.grade) : NaN;
        return Number.isFinite(g) && tier.test(g);
      }));
    }

    const dates = picks.map((p) => p.date).sort();

    return NextResponse.json({
      market,
      horizons: HORIZONS,
      comparison,
      by_piotroski: byPiotroski,
      total_picks: picks.length,
      earliest_date: dates[0] ?? null,
      latest_date: dates[dates.length - 1] ?? null,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
