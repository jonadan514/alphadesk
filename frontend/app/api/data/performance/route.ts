import { NextResponse } from "next/server";
import { querySnapshot } from "@/src/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(await querySnapshot("data_performance"));
}
