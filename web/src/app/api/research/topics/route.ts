import { createResearchTopic } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const topic = await createResearchTopic(body);
    return NextResponse.json(topic);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[research/topics] POST failed", msg);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
