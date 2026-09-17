document.documentElement.dataset.bluebrainCompanion = "ready";

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== window.location.origin) return;
  const message = event.data;
  if (message?.source !== "bluebrain-workbench" || message?.type !== "bluebrain:creation-task") return;

  chrome.runtime.sendMessage({
    type: "bluebrain:store-creation-task",
    brief: message.brief
  }).then((result) => {
    window.postMessage({
      source: "bluebrain-companion",
      type: "bluebrain:creation-task-result",
      ok: Boolean(result?.ok)
    }, window.location.origin);
  }).catch(() => {
    window.postMessage({
      source: "bluebrain-companion",
      type: "bluebrain:creation-task-result",
      ok: false
    }, window.location.origin);
  });
});
