import createMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";

import { routing } from "./i18n/routing";

// Redirects "/" to the visitor's locale (from the browser language, e.g. "/pl") and keeps the
// locale prefix on all routes.
const intl = createMiddleware(routing);

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // German is switched off for now (see i18n/routing.ts): its pages go to English, and so do
  // visitors whose browser speaks German first. Temporary redirects, so German can come back.
  const german = pathname === "/de" || pathname.startsWith("/de/");
  const germanBrowser =
    pathname === "/" &&
    !request.cookies.has("NEXT_LOCALE") &&
    /^de\b/i.test(request.headers.get("accept-language") ?? "");
  if (german || germanBrowser) {
    const url = request.nextUrl.clone();
    url.pathname = german ? `/en${pathname.slice(3)}` : "/en";
    return NextResponse.redirect(url, 307);
  }
  return intl(request);
}

export const config = {
  // Skip API routes, Next.js internals and files with an extension (favicon.ico, images, ...).
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
