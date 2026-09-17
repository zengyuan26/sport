import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { readCreationGptUrl } from "../app/lib/server/creation-gpt";

describe("shared creation GPT configuration", () => {
  it("accepts only a published ChatGPT GPT URL", () => {
    expect(readCreationGptUrl(undefined)).toEqual({ available: false, url: null });
    expect(readCreationGptUrl("https://example.com/g/test")).toEqual({ available: false, url: null });
    expect(readCreationGptUrl("https://chatgpt.com/g/g-bluebrain")).toEqual({
      available: true,
      url: "https://chatgpt.com/g/g-bluebrain",
    });
  });
});

it("ships a shared-GPT creative task handoff", async () => {
  const html = await readFile("public/workbench.html", "utf8");
  expect(html).toContain("新闻 / 链接");
  expect(html).toContain("洗稿");
  expect(html).toContain("原创想法");
  expect(html).toContain("把一条素材或一个念头，带进蓝脑星球创作 GPT。");
  expect(html).toContain("带着这条任务去创作");
  expect(html).toContain("function buildCreationBrief");
  expect(html).toContain("function saveCreationResult");
  expect(html).toContain("回来后回填结果");
  expect(html).toContain("returnReady");
  expect(html).toContain("window.open('about:blank','_blank')");
  expect(html).not.toContain("＋ 新增参考风格");
});
