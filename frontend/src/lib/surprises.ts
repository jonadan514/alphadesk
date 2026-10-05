import type { getClient } from "@/src/lib/db";

// 종목별 최근 실적 서프라이즈 (2026-10-05). earnings_surprise는 종목당 가장 최근 발표 한 줄이라,
// 한국은 몇 년 전 발표가 남아 있는 종목도 있다 - 테마 요약(earnings_surprise_collector.summarize_theme)과
// 같은 100일 창으로 "최근 발표"만 쓴다. 표가 없거나 실패하면 빈 객체(화면은 그 칸만 비운다).
export const SURPRISE_WINDOW_DAYS = 100;

export interface Surprise {
  pct: number;                // EPS 추정치 대비 % (예: 12.3)
  date: string;               // 발표일
  estimate: number | null;
  reported: number | null;
}

export async function recentSurprises(
  client: ReturnType<typeof getClient>, market: string, tickers: string[],
): Promise<Record<string, Surprise>> {
  const out: Record<string, Surprise> = {};
  const uniq = Array.from(new Set(tickers));
  try {
    for (let i = 0; i < uniq.length; i += 200) {
      const chunk = uniq.slice(i, i + 200);
      const res = await client.execute({
        sql: `SELECT ticker, report_date, surprise_pct, eps_estimate, eps_reported FROM earnings_surprise
              WHERE market = ? AND surprise_pct IS NOT NULL AND ticker IN (${chunk.map(() => "?").join(",")})
                AND report_date >= date('now', '-${SURPRISE_WINDOW_DAYS} days')`,
        args: [market, ...chunk],
      });
      res.rows.forEach((r) => {
        out[r[0] as string] = {
          pct: Number(r[2]), date: String(r[1]).slice(0, 10),
          estimate: r[3] == null ? null : Number(r[3]), reported: r[4] == null ? null : Number(r[4]),
        };
      });
    }
  } catch { /* 표 없음 - 빈 결과 */ }
  return out;
}
