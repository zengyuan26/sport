import { describe, expect, it } from "vitest";
import { nextSaveAction } from "../app/lib/workbench-sync";

describe("workbench save feedback", () => {
  it("preserves the editor state when the server reports a conflict", () => {
    expect(nextSaveAction({ status: 409 }, { teachers: [{ name: "吕老师" }] })).toEqual({
      action: "show-conflict",
      preserveLocalDraft: true,
    });
  });
});
