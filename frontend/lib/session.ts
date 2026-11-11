export type VovageSession = {
  name: string;
  email: string;
};

const KEY = "vovage-session";
const EVENT = "vovage-session";

export function getSession(): VovageSession | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as VovageSession) : null;
  } catch {
    return null;
  }
}

export function setSession(session: VovageSession) {
  try {
    localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* private mode */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* private mode */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function onSessionChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}
