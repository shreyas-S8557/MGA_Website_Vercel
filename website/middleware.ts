import { NextRequest, NextResponse } from "next/server";

// --- Site-wide "coming soon" lock -----------------------------------------
// While content changes are going through approval, every visitor is shown
// the /coming-soon page instead of the real site. Nothing else is deleted
// or changed — this just intercepts the request before it reaches the real
// pages, so removing (or disabling) this file instantly restores the live
// site exactly as it was.
//
// To turn the lock OFF: delete this file (or set COMING_SOON=false in
// Vercel's Environment Variables and redeploy).
//
// To preview the real site yourself while it's locked: visit any page with
// ?bypass=<PREVIEW_BYPASS_SECRET> once. That sets a cookie in your browser
// so you keep seeing the real site on later visits, without affecting
// anyone else.

const COMING_SOON = process.env.COMING_SOON !== "false"; // locked by default
const BYPASS_SECRET = process.env.PREVIEW_BYPASS_SECRET || "mga-preview";
const BYPASS_COOKIE = "mga_bypass";

export function middleware(request: NextRequest) {
  if (!COMING_SOON) return NextResponse.next();

  const { pathname, searchParams } = request.nextUrl;

  // Always let the coming-soon page itself, static assets, and Next.js
  // internals through untouched.
  if (
    pathname.startsWith("/coming-soon") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    /\.(png|jpg|jpeg|gif|svg|ico|webp|css|js|map|txt|xml|json|woff|woff2)$/.test(
      pathname
    )
  ) {
    return NextResponse.next();
  }

  // Team bypass: ?bypass=SECRET sets a cookie so reviewers can keep seeing
  // the real site while everyone else sees "coming soon".
  const bypassParam = searchParams.get("bypass");
  const hasBypassCookie = request.cookies.get(BYPASS_COOKIE)?.value === BYPASS_SECRET;

  if (bypassParam === BYPASS_SECRET) {
    const response = NextResponse.next();
    response.cookies.set(BYPASS_COOKIE, BYPASS_SECRET, {
      maxAge: 60 * 60 * 24 * 30, // 30 days
      httpOnly: true,
      sameSite: "lax",
    });
    return response;
  }

  if (hasBypassCookie) {
    return NextResponse.next();
  }

  // Everyone else: show the coming-soon page, keeping the visited URL in
  // the address bar.
  const url = request.nextUrl.clone();
  url.pathname = "/coming-soon";
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: "/((?!coming-soon).*)",
};
