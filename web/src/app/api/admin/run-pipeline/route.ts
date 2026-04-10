import { runPipeline } from "@/lib/api";
import { NextResponse } from "next/server";

export async function POST() {
  try {
    const stats = await runPipeline({ windowHours: 48, silent: true });
    return NextResponse.json(stats);
  } catch (e) {
    console.error("[admin/run-pipeline] upstream failed", e);
    return NextResponse.json(
      { error: "pipeline failed — see server logs" },
      { status: 502 }
    );
  }
}
