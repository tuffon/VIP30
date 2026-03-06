export const AUTH_STORAGE_KEY = "vip_auth_session";
export const AUTH_SESSION_CHANGED_EVENT = "vip-auth-session-changed";
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type PersistedSession = {
  email: string;
  timestamp: number;
};

function hasWindow() {
  return typeof window !== "undefined";
}

function emitSessionChanged(): void {
  if (!hasWindow()) return;
  window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
}

export function persistSession(email: string, notify = true): void {
  if (!hasWindow() || !email) return;
  const payload: PersistedSession = { email, timestamp: Date.now() };
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(payload));
  if (notify) {
    emitSessionChanged();
  }
}

export function getPersistedSession(): PersistedSession | null {
  if (!hasWindow()) return null;
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<PersistedSession>;
    if (typeof parsed.email !== "string" || typeof parsed.timestamp !== "number") {
      return null;
    }
    return { email: parsed.email, timestamp: parsed.timestamp };
  } catch {
    return null;
  }
}

export function clearPersistedSession(notify = true): void {
  if (!hasWindow()) return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  if (notify) {
    emitSessionChanged();
  }
}

export function isSessionValid(session: Pick<PersistedSession, "timestamp">): boolean {
  return Date.now() - session.timestamp <= SESSION_TTL_MS;
}
