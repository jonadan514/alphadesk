import { NextResponse } from "next/server";
import Database from "better-sqlite3";
import path from "path";

function getDb(): Database.Database {
  const dbPath = process.env.PAPER_DB_PATH ?? path.resolve(process.cwd(), "../output/paper_trading.db");
  const db = new Database(dbPath, { fileMustExist: false });
  db.pragma("journal_mode = WAL");
  return db;
}

export const dynamic = "force-dynamic";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    getDb().prepare("DELETE FROM my_watchlist WHERE id = ?").run(Number(id));
    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
