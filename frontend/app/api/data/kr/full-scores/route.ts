import { NextResponse } from "next/server";
import { querySnapshot } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 한국 전체 채점 결과 — 매수체크 폴백 소스 (US /api/data/full-scores 대응)
export async function GET() {
  return NextResponse.json(await querySnapshot("kr_full_scores"));
}
