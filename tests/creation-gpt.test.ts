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
