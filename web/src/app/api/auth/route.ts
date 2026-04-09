// POST /api/auth { password } → sets the shadow_auth cookie if password matches.
// DELETE /api/auth → clears the cookie.

import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const { password } = (await request.json().catch(() => ({ password: "" }))) as {
    password?: string;
  };
  const expected = process.env.SITE_PASSWORD || "";

  if (!expected) {
    return NextResponse.json(
      { ok: false, error: "SITE_PASSWORD not configured" },
      { status: 500 }
    );
  }

  if (password !== expected) {
    return NextResponse.json({ ok: false, error: "wrong password" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("shadow_auth", expected, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30, // 30 days
    path: "/",
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete("shadow_auth");
  return res;
}
