import type { CookieOptions } from "@supabase/ssr";

export const supabaseCookieOptions: CookieOptions = {
  path: "/",
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
};
