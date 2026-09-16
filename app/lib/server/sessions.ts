import { createSessionToken, readCookie, tokenHash } from "./access";

export const SESSION_COOKIE = "bluebrain_session";
export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

export async function createSession(db: D1Database): Promise<string> {
  const token = createSessionToken();
  const expiresAt = new Date(Date.now() + SESSION_MAX_AGE_SECONDS * 1000).toISOString();
  const now = new Date().toISOString();
  await db.batch([
    db.prepare("DELETE FROM access_sessions WHERE expires_at <= ?").bind(now),
    db
      .prepare("INSERT INTO access_sessions (id, token_hash, expires_at) VALUES (?, ?, ?)")
      .bind(crypto.randomUUID(), await tokenHash(token), expiresAt),
  ]);
  return token;
}

export async function hasSession(request: Request, db: D1Database): Promise<boolean> {
  const token = readCookie(request, SESSION_COOKIE);
  if (!token) return false;
  const row = await db
    .prepare("SELECT id FROM access_sessions WHERE token_hash = ? AND expires_at > ?")
    .bind(await tokenHash(token), new Date().toISOString())
    .first<{ id: string }>();
  return Boolean(row);
}

export async function deleteSession(request: Request, db: D1Database): Promise<void> {
  const token = readCookie(request, SESSION_COOKIE);
  if (!token) return;
  await db.prepare("DELETE FROM access_sessions WHERE token_hash = ?").bind(await tokenHash(token)).run();
}
