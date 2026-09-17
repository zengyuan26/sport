const PENDING_TASK_KEY = "bluebrainPendingCreationTask";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "bluebrain:store-creation-task") return;

  const brief = typeof message.brief === "string" ? message.brief.trim() : "";
  if (!brief) {
    sendResponse({ ok: false, reason: "empty-task" });
    return;
  }

  chrome.storage.local.set({
    [PENDING_TASK_KEY]: {
      brief,
      createdAt: new Date().toISOString(),
      source: sender.tab?.url ?? ""
    }
  }).then(async () => {
    await chrome.tabs.create({ url: "https://chatgpt.com/" });
    sendResponse({ ok: true });
  }).catch(() => sendResponse({ ok: false, reason: "storage-failed" }));

  return true;
});
