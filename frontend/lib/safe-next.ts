const UNSAFE = /[\u0000-\u0020\u007f\\]/;

export function safeNextPath(raw: string | null, fallback = "/"): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//") || UNSAFE.test(raw)) {
    return fallback;
  }
  return raw;
}
