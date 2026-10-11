import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

/**
 * Redirect-only route protection.
 *
 * Unauthenticated visitors to /candidate/*, /employer/* and /control-center/*
 * are redirected to the sign-in page. Everything else — role checks, org
 * membership checks, per-action authorization — happens SERVER-SIDE in pages
 * and server actions via lib/rbac.ts. Never rely on this middleware alone.
 */
const SIGN_IN_PATH = "/login";

const PROTECTED_PREFIXES = ["/candidate", "/employer", "/control-center"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const needsAuth = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!needsAuth) return NextResponse.next();

  // Build a minimal Supabase client bound to this request's cookies.
  // Env is read lazily here (request time, never build time).
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    const signInUrl = request.nextUrl.clone();
    signInUrl.pathname = SIGN_IN_PATH;
    signInUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(signInUrl);
  }

  return response;
}

export const config = {
  matcher: ["/candidate/:path*", "/employer/:path*", "/control-center/:path*"],
};
