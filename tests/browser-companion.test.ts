import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (path: string) => readFileSync(resolve(root, path), "utf8");

describe("browser creation companion", () => {
  it("limits its browser access to the workbench and ChatGPT", () => {
    const manifest = JSON.parse(read("browser-extension/manifest.json"));
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.host_permissions).toEqual([
      "https://bluebrain-teacher-workbench.tommybarrios823.chatgpt.site/*",
      "https://chatgpt.com/*"
    ]);
    expect(manifest.permissions).toEqual(["storage", "tabs"]);
  });

  it("requires an explicit click before putting the brief in ChatGPT", () => {
    const helper = read("browser-extension/chatgpt-helper.js");
    expect(helper).toContain('button.addEventListener("click"');
    expect(helper).toContain("不会自动发送，也不会读取你的聊天记录");
    expect(helper).not.toContain("fetch(");
  });

  it("keeps a copy-and-paste fallback for people without the extension", () => {
    const workbench = read("public/workbench.html");
    expect(workbench).toContain("bluebrainCompanionReady");
    expect(workbench).toContain("复制任务并打开 ChatGPT");
    expect(workbench).toContain("bluebrain:creation-task");
  });
});
