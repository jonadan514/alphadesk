import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 워치리스트 종목 상세 팝업에서 "이 종목이 어느 테마에 속하는지" 보여주기 위한 역방향
// 조회 - radar/members가 테마→종목이라면 이건 종목→테마.
// Phase B에서 한국 추가 - ?market=KR (생략 시 US, 기존 호출 하위호환).
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbol = searchParams.get("symbol");
  if (!symbol) {
    return NextResponse.json({ themes: [] }, { status: 400 });
  }

  try {
    const market = searchParams.get("market") === "KR" ? "KR" : "US";
    const client = getClient();

    // 테마별 최신 승인 run_id 중 이 티커가 속한 것만 (SPEC §5와 동일한 "최신 run_id + approved=1")
    const res = await client.execute({
      sql: `
        WITH latest_runs AS (
          SELECT theme_id, MAX(run_id) AS run_id
          FROM theme_members
          WHERE market = ? AND approved = 1
          GROUP BY theme_id
        )
        SELECT tm.theme_id, ts.label
        FROM theme_members tm
        JOIN latest_runs lr ON lr.theme_id = tm.theme_id AND lr.run_id = tm.run_id
        LEFT JOIN theme_signals ts ON ts.theme_id = tm.theme_id AND ts.market = ?
          AND ts.week_start = (SELECT MAX(week_start) FROM theme_signals WHERE market = ?)
        WHERE tm.ticker = ? AND tm.market = ? AND tm.approved = 1
        ORDER BY tm.theme_id
      `,
      args: [market, market, market, symbol, market],
    });

    const themes = res.rows.map((r) => ({ theme_id: r[0] as string, label: r[1] as string | null }));
    return NextResponse.json({ themes });
  } catch (err) {
    console.error("[api/radar/ticker-themes] error:", err);
    return NextResponse.json({ themes: [] });
  }
}
