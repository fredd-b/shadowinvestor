// Server-side proxy: forwards POST /api/admin/run-pipeline to the Railway API.
// We don't expose API_TOKEN to the browser, so the frontend always calls
// these /api/admin/* endpoints which then call Railway with the bearer token.

import { runPipeline } from "@/lib/api";
import { NextResponse } from "next/server";

export async function POST() {
  try {
    const stats = await runPipeline({ windowHours: 48, silent: true });
    return NextResponse.json(stats);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
