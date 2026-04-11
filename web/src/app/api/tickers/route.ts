import { addTicker } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const ticker = await addTicker(body);
    return NextResponse.json(ticker);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[api/tickers] POST failed", msg);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
