import { env } from "cloudflare:workers";
import { apiError, database } from "@/app/lib/server/api";
import { readCreationGptUrl } from "@/app/lib/server/creation-gpt";
import { hasSession } from "@/app/lib/server/sessions";

export async function GET(request: Request) {
  try {
    const db = database();
    if (!(await hasSession(request, db))) {
      return Response.json({ error: "请先输入内部入口密码。" }, { status: 401 });
    }
    return Response.json(readCreationGptUrl(env.CREATION_GPT_URL));
  } catch (error) {
    return apiError(error);
  }
}
