import { setSignalAction } from "@/lib/api";
import { NextRequest, NextResponse } from "next/server";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    await setSignalAction(parseInt(id, 10), body.action, body.note);
    return NextResponse.json({ ok: true });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[signals/action] failed", msg);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
