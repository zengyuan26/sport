import { apiError, database } from "@/app/lib/server/api";
import { sessionCookie } from "@/app/lib/server/access";
import { deleteSession } from "@/app/lib/server/sessions";

export async function POST(request: Request) {
  try {
    await deleteSession(request, database());
    return Response.json({ ok: true }, { headers: { "set-cookie": sessionCookie("", 0) } });
  } catch (error) {
    return apiError(error);
  }
}
