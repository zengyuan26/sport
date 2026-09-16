export type SaveDecision = {
  action: "saved" | "show-conflict" | "show-retry";
  preserveLocalDraft: boolean;
};

export function nextSaveAction(
  response: Pick<Response, "status">,
  _snapshot: unknown,
): SaveDecision {
  if (response.status === 409) return { action: "show-conflict", preserveLocalDraft: true };
  if (response.status >= 200 && response.status < 300) return { action: "saved", preserveLocalDraft: false };
  return { action: "show-retry", preserveLocalDraft: true };
}
