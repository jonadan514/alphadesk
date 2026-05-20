import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const year = searchParams.get("year") ?? new Date().getFullYear().toString();

    const client = getClient();

    const [fixedRes, entriesRes] = await Promise.all([
      client.execute("SELECT type, amount FROM cashflow_fixed"),
      client.execute({
        sql: "SELECT month, type, amount FROM cashflow_entries WHERE month LIKE ?",
        args: [`${year}-%`],
      }),
    ]);

    const fixedIncome = fixedRes.rows.filter(r => r[0] === "income").reduce((s, r) => s + (r[1] as number), 0);
    const fixedExpense = fixedRes.rows.filter(r => r[0] === "expense").reduce((s, r) => s + (r[1] as number), 0);

    const varByMonth: Record<string, { income: number; expense: number }> = {};
    for (const row of entriesRes.rows) {
      const m = row[0] as string;
      const t = row[1] as string;
      const a = row[2] as number;
      if (!varByMonth[m]) varByMonth[m] = { income: 0, expense: 0 };
      if (t === "income") varByMonth[m].income += a;
      else varByMonth[m].expense += a;
    }

    const months = Array.from({ length: 12 }, (_, i) => {
      const m = `${year}-${String(i + 1).padStart(2, "0")}`;
      const v = varByMonth[m] ?? { income: 0, expense: 0 };
      const income = fixedIncome + v.income;
      const expense = fixedExpense + v.expense;
      return { month: m, income, expense, net: income - expense };
    });

    return NextResponse.json(months);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
