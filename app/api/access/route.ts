import { env } from "cloudflare:workers";
import { apiError, database, readJson } from "@/app/lib/server/api";
import { sessionCookie, timingSafeCodeMatch, validateAccessInput } from "@/app/lib/server/access";
import { createSession, SESSION_MAX_AGE_SECONDS } from "@/app/lib/server/sessions";

export async function POST(request: Request) {
  try {
    const input = validateAccessInput((await readJson(request) as { code?: unknown } | null)?.code);
    if ("error" in input) return Response.json(input, { status: 400 });
    if (!env.INTERNAL_ACCESS_CODE) return Response.json({ error: "内部入口暂未配置，请联系管理员。" }, { status: 503 });
    if (!(await timingSafeCodeMatch(input.code, env.INTERNAL_ACCESS_CODE))) {
      return Response.json({ error: "入口密码不正确，请重试。" }, { status: 401 });
    }
    const token = await createSession(database());
    return Response.json(
      { ok: true },
      { headers: { "set-cookie": sessionCookie(token, SESSION_MAX_AGE_SECONDS) } },
    );
  } catch (error) {
    return apiError(error);
  }
}
