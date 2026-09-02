import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 테마 하나의 이번 주 기사 목록 (SPEC §6.3 "기사 보기").
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const themeId = searchParams.get("theme_id");
  if (!themeId) {
    return NextResponse.json({ articles: [] }, { status: 400 });
  }

  try {
    const client = getClient();

    const weekRes = await client.execute(
      "SELECT MAX(week_start) FROM theme_signals WHERE market = 'US'"
    );
    const weekStart = weekRes.rows[0]?.[0] as string | null;
    if (!weekStart) {
      return NextResponse.json({ articles: [] });
    }

    const res = await client.execute({
      sql: `
        SELECT title, url, source, published_at
        FROM theme_news
        WHERE theme_id = ? AND market = 'US' AND week_start = ?
        ORDER BY published_at DESC
        LIMIT 30
      `,
      args: [themeId, weekStart],
    });
    const articles = res.rows.map((r) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((col, i) => { obj[col] = r[i]; });
      return obj;
    });

    return NextResponse.json({ week_start: weekStart, articles });
  } catch (err) {
    console.error("[api/radar/news] error:", err);
    return NextResponse.json({ articles: [] });
  }
}
