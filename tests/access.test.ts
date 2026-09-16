import { describe, expect, it } from "vitest";
import { timingSafeCodeMatch, validateAccessInput } from "../app/lib/server/access";

describe("shared access code", () => {
  it("accepts only a non-empty matching code", async () => {
    expect(validateAccessInput("")).toEqual({ error: "请输入内部入口密码。" });
    await expect(timingSafeCodeMatch("wrong-code", "team-code")).resolves.toBe(false);
    await expect(timingSafeCodeMatch("team-code", "team-code")).resolves.toBe(true);
  });
});
