import { NextResponse } from "next/server";
import { querySnapshot } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const regime = await querySnapshot("kr_regime") as any;
  if (!regime || !regime.regime) return NextResponse.json(null);

  const vol   = regime.vol_60d ?? 0;
  const mom   = regime.mom_20d ?? 0;
  const last  = regime.kospi_last ?? 0;
  const s200  = regime.kospi_sma200 ?? last;

  const dailyVol = (vol / 100) / Math.sqrt(252);
  const var95    = -1.645 * dailyVol;
  const drawdownPct = s200 > 0 ? (last - s200) / s200 : 0;

  const riskLevel =
    vol > 35 ? "DANGER" :
    vol > 25 ? "WATCH"  : "NORMAL";

  return NextResponse.json({
    regime:         regime.regime,
    regime_label:   regime.regime_label,
    weighted_score: regime.weighted_score,
    vol_60d:        vol,
    mom_20d:        mom,
    kospi_last:     last,
    kospi_sma200:   s200,
    var95_daily:    parseFloat(var95.toFixed(4)),
    dd_vs_sma200:   parseFloat(drawdownPct.toFixed(4)),
    risk_level:     riskLevel,
    sensor_scores:  regime.sensor_scores ?? {},
    computed_at:    regime.computed_at ?? null,
  });
}
