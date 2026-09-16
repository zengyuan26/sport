import { env } from "cloudflare:workers";

export function database(): D1Database {
  if (!env.DB) throw new Error("资料库暂时不可用，请稍后重试。");
  return env.DB;
}

export async function readJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

export function apiError(error: unknown): Response {
  const message = error instanceof Error ? error.message : "服务暂时不可用，请稍后重试。";
  const safeMessage = /no such table|D1|SQLITE/i.test(message)
    ? "资料库正在准备中，请稍后重试。"
    : message;
  return Response.json({ error: safeMessage }, { status: 500 });
}
