import { NextRequest, NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const market = params.get("market") ?? "US";
  const sector = params.get("sector") ?? "";
  const days   = Math.min(Math.max(1, Number(params.get("days") ?? "7")), 30);
  const limit  = Math.min(Math.max(1, Number(params.get("limit") ?? "60")), 200);

  const client = getClient();
  try {
    const cutoff = new Date(Date.now() - days * 86_400_000)
      .toISOString()
      .slice(0, 16);

    const conditions = ["market = ?"];
    const bindings: (string | number | null)[] = [market];

    if (sector) {
      conditions.push("sector = ?");
      bindings.push(sector);
    }
    conditions.push("(published_at >= ? OR published_at IS NULL)");
    bindings.push(cutoff);

    const where = conditions.join(" AND ");

    const [itemsRes, sectorsRes] = await Promise.all([
      client.execute({
        sql:  `SELECT id, title, title_ko, url, source, market, sector, published_at, fetched_at FROM news_items WHERE ${where} ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?`,
        args: [...bindings, limit],
      }),
      client.execute({
        sql:  `SELECT sector, COUNT(*) as cnt FROM news_items WHERE market = ? AND (published_at >= ? OR published_at IS NULL) GROUP BY sector ORDER BY cnt DESC`,
        args: [market, cutoff],
      }),
    ]);

    const toObj = (res: typeof itemsRes) =>
      res.rows.map((r) => Object.fromEntries(res.columns.map((c, i) => [c, r[i]])));

    return NextResponse.json({
      items:   toObj(itemsRes),
      sectors: toObj(sectorsRes),
    });
  } catch (err) {
    console.error("[news] query error:", err);
    return NextResponse.json({ items: [], sectors: [] });
  }
}
