import { NextResponse } from "next/server";
import { getClient } from "@/src/lib/db";

export const dynamic = "force-dynamic";

async function ensureTable(client: ReturnType<typeof getClient>) {
  await client.execute(`
    CREATE TABLE IF NOT EXISTS ai_advice (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      content    TEXT NOT NULL,
      snapshot   TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
}

export async function GET() {
  try {
    const client = getClient();
    await ensureTable(client);
    const res = await client.execute("SELECT content, snapshot, created_at FROM ai_advice ORDER BY id DESC LIMIT 1");
    if (res.rows.length === 0) return NextResponse.json(null);
    const row = res.rows[0];
    return NextResponse.json({ content: row[0], snapshot: JSON.parse(row[1] as string), created_at: row[2] });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST() {
  try {
    const apiKey = process.env.GOOGLE_API_KEY;
    if (!apiKey) return NextResponse.json({ error: "GOOGLE_API_KEY not configured" }, { status: 500 });

    const client = getClient();
    await ensureTable(client);

    // collect data
    const [assetsRes, fixedRes, entriesRes] = await Promise.all([
      client.execute("SELECT category, name, amount, note FROM asset_items ORDER BY category"),
      client.execute("SELECT type, name, amount FROM cashflow_fixed"),
      client.execute("SELECT month, type, amount FROM cashflow_entries ORDER BY month DESC LIMIT 60"),
    ]);

    const assets = assetsRes.rows.map(r => ({ category: r[0], name: r[1], amount: r[2], note: r[3] }));
    const fixed = fixedRes.rows.map(r => ({ type: r[0], name: r[1], amount: r[2] }));
    const entries = entriesRes.rows.map(r => ({ month: r[0], type: r[1], amount: r[2] }));

    // compute summary
    const ASSET_CATS = ["stocks","savings","real_estate","pension","bitcoin"];
    const DEBT_CATS  = ["mortgage","credit_loan","other_debt"];
    const totalAssets = assets.filter(a => ASSET_CATS.includes(a.category as string)).reduce((s, a) => s + (a.amount as number), 0);
    const totalDebts  = assets.filter(a => DEBT_CATS.includes(a.category as string)).reduce((s, a) => s + (a.amount as number), 0);
    const netWorth = totalAssets - totalDebts;

    const fixedIncome  = fixed.filter(f => f.type === "income").reduce((s, f) => s + (f.amount as number), 0);
    const fixedExpense = fixed.filter(f => f.type === "expense").reduce((s, f) => s + (f.amount as number), 0);
    const savingsRate  = fixedIncome > 0 ? Math.round(((fixedIncome - fixedExpense) / fixedIncome) * 100) : 0;

    const snapshot = { assets, fixed, entries: entries.slice(0, 20), totalAssets, totalDebts, netWorth, fixedIncome, fixedExpense, savingsRate };

    const prompt = `당신은 한국의 개인 재무 컨설턴트입니다. 아래 사용자의 실제 재무 데이터를 분석하고 구체적인 조언을 제공해주세요.

## 자산 현황
- 총 자산: ${(totalAssets / 1e4).toFixed(0)}만원
- 총 부채: ${(totalDebts / 1e4).toFixed(0)}만원
- 순 자산: ${(netWorth / 1e4).toFixed(0)}만원
- 부채비율: ${totalAssets > 0 ? Math.round((totalDebts / totalAssets) * 100) : 0}%

자산 구성:
${assets.map(a => `- ${a.category}/${a.name}: ${Math.round(a.amount as number / 1e4)}만원`).join("\n") || "데이터 없음"}

## 현금흐름
- 월 고정 수입: ${(fixedIncome / 1e4).toFixed(0)}만원
- 월 고정 지출: ${(fixedExpense / 1e4).toFixed(0)}만원
- 월 순 저축: ${((fixedIncome - fixedExpense) / 1e4).toFixed(0)}만원
- 저축률: ${savingsRate}%

고정 수입: ${fixed.filter(f => f.type === "income").map(f => `${f.name}(${Math.round(f.amount as number / 1e4)}만원)`).join(", ") || "없음"}
고정 지출: ${fixed.filter(f => f.type === "expense").map(f => `${f.name}(${Math.round(f.amount as number / 1e4)}만원)`).join(", ") || "없음"}

---
다음 4가지 항목으로 분석해주세요. 각 항목은 **볼드 제목**으로 구분하고, 구체적인 수치를 포함하세요:

**1. 자산 배분 진단**
현재 자산 구성의 특징과 문제점을 분석해주세요.

**2. 현금흐름 분석**
저축률 및 수입/지출 구조의 강점과 개선 포인트를 분석해주세요.

**3. 리스크 평가**
부채 수준, 자산 집중도, 유동성 측면에서 리스크를 평가해주세요.

**4. 우선순위 행동 제안 3가지**
지금 당장 실행 가능한 구체적인 행동 3가지를 제안해주세요.

분석은 한국어로, 친절하고 전문적으로, 500자 이내로 간결하게 작성해주세요.`;

    const geminiRes = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.4, maxOutputTokens: 1024 },
        }),
      }
    );

    if (!geminiRes.ok) {
      const err = await geminiRes.text();
      return NextResponse.json({ error: `Gemini API error: ${err}` }, { status: 500 });
    }

    const geminiData = await geminiRes.json();
    const content = geminiData.candidates?.[0]?.content?.parts?.[0]?.text ?? "분석 결과를 받지 못했습니다.";

    await client.execute({
      sql: "INSERT INTO ai_advice (content, snapshot) VALUES (?, ?)",
      args: [content, JSON.stringify(snapshot)],
    });

    return NextResponse.json({ content, snapshot, created_at: new Date().toISOString() });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
