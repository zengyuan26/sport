import { describe, expect, it } from "vitest";
import { applyWorkspaceWrite, parseSaveRequest } from "../app/lib/server/workspace";

describe("shared workspace revision guard", () => {
  it("rejects a write based on an old revision", () => {
    expect(applyWorkspaceWrite({ revision: 4 }, 3, { teachers: [], activeTeacher: 0, styleCards: [] })).toEqual({
      ok: false,
      status: "conflict",
    });
  });

  it("increments a matching revision", () => {
    expect(applyWorkspaceWrite({ revision: 4 }, 4, { teachers: [], activeTeacher: 0, styleCards: [] })).toMatchObject({
      ok: true,
      nextRevision: 5,
    });
  });

  it("rejects a payload without the shared workspace shape", () => {
    expect(parseSaveRequest({ workspace: { teachers: [] }, revision: 0 })).toEqual({
      error: "保存的数据格式不正确。",
    });
  });
});
