import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";

async function readOrEmpty(path: string) {
  try {
    return await readFile(path, "utf8");
  } catch {
    return "";
  }
}

describe("online workbench shell", () => {
  it("ships the workbench with the D1 binding and no source-tree access code", async () => {
    const html = await readOrEmpty("public/workbench.html");
    const manifestText = await readOrEmpty(".openai/hosting.json");
    const manifest = manifestText ? JSON.parse(manifestText) : {};

    expect(html).toContain("蓝脑星球培训讲师工作台");
    expect(html).toContain("teamExit.id='teamExit'");
    expect(html).not.toMatch(/INTERNAL_ACCESS_CODE\s*=\s*[^"']/);
    expect(manifest.d1).toBe("DB");
  });
});
