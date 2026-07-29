import { NextResponse } from "next/server";
import { querySnapshot } from "@/src/lib/db";

export const dynamic = "force-dynamic";

// 전체 채점 결과 (top-20 밖 포함) — 매수체크가 임의 종목의 등급/액션을 조회하는 폴백 소스
export async function GET() {
  return NextResponse.json(await querySnapshot("data_full_scores"));
}
