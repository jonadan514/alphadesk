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
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) return NextResponse.json({ error: "OPENAI_API_KEY not configured" }, { status: 500 });

    const client = getClient();
    await ensureTable(client);

    // collect data
    const [assetsRes, fixedRes, entriesRes, holdingsRes, usReportRes, krReportRes, regimeRes] = await Promise.all([
      client.execute("SELECT category, name, amount, note FROM asset_items ORDER BY category"),
      client.execute("SELECT type, name, amount FROM cashflow_fixed"),
      client.execute("SELECT month, type, amount FROM cashflow_entries ORDER BY month DESC LIMIT 60"),
      client.execute("SELECT market, symbol, name, shares, avg_price, current_price, note FROM stock_holdings ORDER BY market, symbol").catch(() => ({ rows: [] })),
      client.execute("SELECT payload FROM data_daily_reports ORDER BY date DESC LIMIT 1").catch(() => ({ rows: [] })),
      client.execute("SELECT payload FROM kr_daily_reports ORDER BY date DESC LIMIT 1").catch(() => ({ rows: [] })),
      client.execute("SELECT payload FROM data_regime WHERE id=1").catch(() => ({ rows: [] })),
    ]);

    const assets = assetsRes.rows.map(r => ({ category: r[0], name: r[1], amount: r[2], note: r[3] }));
    const fixed = fixedRes.rows.map(r => ({ type: r[0], name: r[1], amount: r[2] }));
    const entries = entriesRes.rows.map(r => ({ month: r[0], type: r[1], amount: r[2] }));
    const holdings = holdingsRes.rows.map(r => ({
      market: r[0] as string, symbol: r[1] as string, name: r[2] as string | null,
      shares: r[3] as number, avg_price: r[4] as number, current_price: r[5] as number | null, note: r[6] as string | null,
    }));

    // parse AlphaDesk analysis
    const parsePayload = (res: { rows: any[] }) => {
      try { return res.rows[0] ? JSON.parse((res.rows[0][0] as string).replace(/\bNaN\b/g, "null")) : null; } catch { return null; }
    };
    const usReport = parsePayload(usReportRes);
    const krReport = parsePayload(krReportRes);
    const regime   = parsePayload(regimeRes);

    const usPicks: any[] = usReport?.picks ?? [];
    const krPicks: any[] = krReport?.picks ?? [];
    const regimeLabel: string = regime?.regime_label ?? regime?.label ?? "데이터 없음";
    const regimeScore: number | null = regime?.score ?? null;

    // match holdings against AlphaDesk picks
    const holdingAnalysis = holdings.map(h => {
      const pickList = h.market === "KR" ? krPicks : usPicks;
      const pick = pickList.find((p: any) => p.symbol === h.symbol || p.name === h.symbol);
      const costBasis = h.shares * h.avg_price;
      const evalValue = h.shares * (h.current_price ?? h.avg_price);
      const pnlPct = h.current_price != null ? ((h.current_price - h.avg_price) / h.avg_price * 100).toFixed(1) : null;
      return {
        ...h, costBasis, evalValue, pnlPct,
        alphaAction: pick?.action ?? null,
        alphaGrade: pick?.grade ?? null,
        alphaSector: pick?.sector ?? null,
        alphaScore: pick ? Math.round((((pick.technical ?? 0) + (pick.fundamental ?? 0) + (pick.volume ?? 0)) / 3)) : null,
      };
    });

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

    const prompt = `당신은 냉철하고 직설적인 한국의 개인 재무 분석가입니다. 사용자의 실제 재무 데이터를 보고 듣기 좋은 말 대신 사실 그대로 분석해주세요.

## 사용자 투자 철학
- 한 번에 큰 돈을 버는 것보다 꾸준히 모으고 투자해서 장기적으로 자산 규모를 키우는 것이 목표
- 근거 없는 투기는 하지 않고, 데이터와 논리에 기반한 투자를 지향
- 투자와 절약 두 축을 모두 중요하게 생각함

## 현재 재무 데이터

### 자산 현황
- 총 자산: ${(totalAssets / 1e4).toFixed(0)}만원
- 총 부채: ${(totalDebts / 1e4).toFixed(0)}만원
- 순 자산: ${(netWorth / 1e4).toFixed(0)}만원
- 부채비율: ${totalAssets > 0 ? Math.round((totalDebts / totalAssets) * 100) : 0}%

자산 구성:
${assets.map(a => `- ${a.category}/${a.name}: ${Math.round(a.amount as number / 1e4)}만원`).join("\n") || "데이터 없음"}

### 현금흐름
- 월 고정 수입: ${(fixedIncome / 1e4).toFixed(0)}만원
- 월 고정 지출: ${(fixedExpense / 1e4).toFixed(0)}만원
- 월 순 저축: ${((fixedIncome - fixedExpense) / 1e4).toFixed(0)}만원
- 저축률: ${savingsRate}%

고정 수입 항목: ${fixed.filter(f => f.type === "income").map(f => `${f.name}(${Math.round(f.amount as number / 1e4)}만원)`).join(", ") || "없음"}
고정 지출 항목: ${fixed.filter(f => f.type === "expense").map(f => `${f.name}(${Math.round(f.amount as number / 1e4)}만원)`).join(", ") || "없음"}

${holdingAnalysis.length > 0 ? `## 보유 주식 (AlphaDesk 분석 연동)
현재 시장 체제: ${regimeLabel}${regimeScore != null ? ` (점수: ${regimeScore})` : ""}

${holdingAnalysis.map(h => {
  const lines = [
    `- [${h.market}] ${h.symbol}${h.name ? ` (${h.name})` : ""}: ${h.shares}주, 평균단가 ${h.market === "US" ? "$" : "₩"}${h.avg_price.toLocaleString()}, 투자금액 ${Math.round(h.costBasis / 1e4)}만원${h.pnlPct != null ? `, 수익률 ${h.pnlPct}%` : ""}`,
  ];
  if (h.alphaAction) lines.push(`  → AlphaDesk 판단: ${h.alphaAction} / Grade ${h.alphaGrade}${h.alphaSector ? ` / 섹터: ${h.alphaSector}` : ""}${h.alphaScore != null ? ` / 종합점수: ${h.alphaScore}` : ""}`);
  else lines.push(`  → AlphaDesk 분석 대상 외 종목 (데이터 없음)`);
  return lines.join("\n");
}).join("\n")}` : "## 보유 주식\n개별 종목 데이터 없음 (자산현황 > 보유 주식 상세에 입력하면 분석 가능)"}

---
아래 5가지 항목으로 분석해주세요. 각 항목은 **볼드 제목**으로 구분하고, 구체적인 수치와 근거를 포함하세요. 문제가 있으면 솔직하게 지적하고, 잘 하고 있는 부분도 명확히 짚어주세요.

**1. 자산 배분 진단**
현재 자산 구성 비율을 분석하세요. 특정 자산에 지나치게 집중돼 있거나 빠진 자산 클래스가 있으면 직접적으로 말해주세요. 장기 복리 성장 관점에서 이 구성이 적절한지 평가해주세요.

**2. 현금흐름 & 절약 분석**
저축률이 충분한지, 지출 구조에서 줄일 수 있는 부분이 있는지 수치 기반으로 평가해주세요. 월 저축액이 목표 자산 성장 속도에 기여하고 있는지도 함께 분석해주세요.

**3. 보유 주식 종목 분석**
${holdingAnalysis.length > 0
  ? `각 보유 종목에 대해 AlphaDesk 판단(${regimeLabel} 체제 기준)과 사용자의 장기 적립식 철학이 맞는지 평가해주세요. AlphaDesk가 SKIP/WATCH인 종목을 보유 중이면 이유를 따져주세요. 분석 대상 외 종목은 어떤 근거로 보유하는지 질문하고, 장기 보유 적합성을 판단해주세요.`
  : `보유 주식 데이터가 없습니다. 현재 투자 자산(주식 등)이 장기 적립식 철학에 맞는지 일반적 관점에서 평가해주세요.`}

**4. 투자 전략 평가**
전체 자산 구성에서 성장 자산의 비중, 분산 수준이 장기 복리 성장 철학과 맞는지 평가해주세요. 근거 없는 자산이 포함돼 있다면 지적해주세요.

**5. 리스크 진단**
부채 수준, 유동성(비상금), 자산 집중도 측면에서 현재 재무 구조의 취약점을 짚어주세요.

**6. 지금 당장 해야 할 행동 3가지**
우선순위 순서로, 실행 가능한 구체적인 행동을 제시해주세요. "검토해보세요" 같은 모호한 표현은 쓰지 말고, 무엇을 얼마나 어떻게 할지 명확히 말해주세요.

분석은 한국어로 작성하되, 직설적이고 솔직하게 써주세요. 분량 제한 없이 충분히 분석해주세요.`;

    const gptRes = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${apiKey}` },
      body: JSON.stringify({
        model: "gpt-4o",
        messages: [{ role: "user", content: prompt }],
        max_tokens: 4096,
        temperature: 0.4,
      }),
    });

    if (!gptRes.ok) {
      const err = await gptRes.text();
      return NextResponse.json({ error: `OpenAI API error: ${err}` }, { status: 500 });
    }

    const gptData = await gptRes.json();
    const content = gptData.choices?.[0]?.message?.content ?? "분석 결과를 받지 못했습니다.";

    await client.execute({
      sql: "INSERT INTO ai_advice (content, snapshot) VALUES (?, ?)",
      args: [content, JSON.stringify(snapshot)],
    });

    return NextResponse.json({ content, snapshot, created_at: new Date().toISOString() });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
