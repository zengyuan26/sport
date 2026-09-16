const encoder = new TextEncoder();

export type AccessValidation = { code: string } | { error: string };

export function validateAccessInput(value: unknown): AccessValidation {
  const code = typeof value === "string" ? value.trim() : "";
  return code ? { code } : { error: "请输入内部入口密码。" };
}

async function digest(value: string): Promise<Uint8Array> {
  const buffer = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return new Uint8Array(buffer);
}

export async function timingSafeCodeMatch(input: string, expected: string): Promise<boolean> {
  if (!input || !expected) return false;

  const [inputHash, expectedHash] = await Promise.all([digest(input), digest(expected)]);
  let difference = 0;
  for (let index = 0; index < inputHash.length; index += 1) {
    difference |= inputHash[index] ^ expectedHash[index];
  }
  return difference === 0;
}

export function encodeBase64(value: Uint8Array): string {
  let result = "";
  for (const byte of value) result += String.fromCharCode(byte);
  return btoa(result);
}

export function createSessionToken(): string {
  return encodeBase64(crypto.getRandomValues(new Uint8Array(32)));
}

export async function tokenHash(token: string): Promise<string> {
  const bytes = await digest(token);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function readCookie(request: Request, name: string): string | null {
  const prefix = `${name}=`;
  const value = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));
  return value ? value.slice(prefix.length) : null;
}

export function sessionCookie(token: string, maxAgeSeconds: number): string {
  return `bluebrain_session=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${Math.max(0, Math.floor(maxAgeSeconds))}`;
}
