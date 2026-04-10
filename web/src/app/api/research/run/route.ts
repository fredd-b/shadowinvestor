import { runResearch } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const sector =
      request.nextUrl.searchParams.get("sector") || undefined;
    const result = await runResearch(sector);
    return NextResponse.json(result);
  } catch (e) {
    console.error("[research/run] upstream failed", e);
    return NextResponse.json(
      { error: "research query failed — see server logs" },
      { status: 502 }
    );
  }
}
