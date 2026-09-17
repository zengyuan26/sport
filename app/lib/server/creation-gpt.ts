export type CreationGptConfig = { available: boolean; url: string | null };

export function readCreationGptUrl(value?: string): CreationGptConfig {
  const url = value?.trim() ?? "";
  return /^https:\/\/chatgpt\.com\/g\/[^/?#]+\/?$/.test(url)
    ? { available: true, url }
    : { available: false, url: null };
}
