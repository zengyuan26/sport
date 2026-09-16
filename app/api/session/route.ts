import { apiError, database } from "@/app/lib/server/api";
import { hasSession } from "@/app/lib/server/sessions";

export async function GET(request: Request) {
  try {
    return Response.json({ signedIn: await hasSession(request, database()) });
  } catch (error) {
    return apiError(error);
  }
}
