import { NextResponse } from "next/server";
import { querySnapshot } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  let pred: any = null;
  try { pred = await querySnapshot("kr_index_prediction"); } catch {}
  if (pred?.direction) return NextResponse.json(pred);

  let regime: any = null;
  try { regime = await querySnapshot("kr_regime"); } catch {}
  if (!regime?.regime) return NextResponse.json(null);

  const w   = regime.weighted_score ?? 0;
  const mom = regime.mom_20d ?? 0;
  const vol = regime.vol_60d ?? 20;
  const sensors = regime.sensor_scores ?? {};

  const normalised = Math.max(0, Math.min(1, (w + 1) / 4));
  const bullProb   = parseFloat((1 - normalised).toFixed(3));
  const direction  = bullProb >= 0.5 ? "bullish" : "bearish";
  const confidence = parseFloat(Math.max(0.45, Math.min(0.90,
    Math.abs(w - 1) / 2 + 0.45
  )).toFixed(3));

  return NextResponse.json({
    market:      "KR",
    index:       "KOSPI",
    direction,
    probability: bullProb,
    confidence,
    key_drivers: [
      { name: "KOSPI 추세 (vs SMA200)", label: "TREND vs SMA200", desc: "KOSPI가 200일 이동평균선 위에 있으면 중장기 강세 추세로 판단합니다.", direction: (sensors.trend ?? 0) >= 1 ? "bullish" : "bearish", importance_pct: 0.35, value: sensors.trend ?? 0 },
      { name: "20일 모멘텀", label: "MOMENTUM 20D", desc: "최근 20일 가격 변화율. 양수면 단기 상승 추세를 나타냅니다.", direction: mom > 0 ? "bullish" : "bearish", importance_pct: 0.25, value: parseFloat((mom / 100).toFixed(4)) },
      { name: "변동성 (60일)", label: "VOLATILITY 60D", desc: "60일 실현 변동성. 20% 초과 시 불안정한 시장으로 약세 신호입니다.", direction: vol < 20 ? "bullish" : "bearish", importance_pct: 0.25, value: parseFloat((vol / 100).toFixed(4)) },
      { name: "시장 브레드스", label: "BREADTH", desc: "상승 종목 비율 등 시장 전반의 건강도 지표. 높을수록 광범위한 강세장입니다.", direction: (sensors.breadth ?? 0) >= 1 ? "bullish" : "bearish", importance_pct: 0.15, value: sensors.breadth ?? 0 },
    ],
    model_type:  "rule_based",
  });
}
