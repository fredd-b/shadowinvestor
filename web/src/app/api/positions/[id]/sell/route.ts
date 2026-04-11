import { sellPosition } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    await sellPosition(parseInt(id, 10), body.shares, body.note);
    return NextResponse.json({ ok: true, ...body });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[positions/sell] failed", msg);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
