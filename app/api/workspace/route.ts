import { apiError, database, readJson } from "@/app/lib/server/api";
import { hasSession } from "@/app/lib/server/sessions";
import { parseSaveRequest, readWorkspace, saveWorkspace } from "@/app/lib/server/workspace";

async function requireSession(request: Request): Promise<D1Database | Response> {
  const db = database();
  return (await hasSession(request, db)) ? db : Response.json({ error: "请先输入内部入口密码。" }, { status: 401 });
}

export async function GET(request: Request) {
  try {
    const db = await requireSession(request);
    if (db instanceof Response) return db;
    return Response.json(await readWorkspace(db));
  } catch (error) {
    return apiError(error);
  }
}

export async function PUT(request: Request) {
  try {
    const db = await requireSession(request);
    if (db instanceof Response) return db;
    const input = parseSaveRequest(await readJson(request));
    if ("error" in input) return Response.json(input, { status: 400 });
    const result = await saveWorkspace(db, input.workspace, input.revision);
    return result.ok
      ? Response.json({ ok: true, revision: result.nextRevision })
      : Response.json({ error: "其他同事刚保存了资料，请刷新最新内容后再继续。" }, { status: 409 });
  } catch (error) {
    return apiError(error);
  }
}
