import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";

describe("release readiness", () => {
  it("does not ship credentials and explains update safety", async () => {
    const envExample = await readFile(".env.example", "utf8");
    const readme = await readFile("README.md", "utf8");

    expect(envExample).toBe("INTERNAL_ACCESS_CODE=\n");
    expect(readme).toContain("页面更新不会清空 D1 中的讲师资料");
  });
});
