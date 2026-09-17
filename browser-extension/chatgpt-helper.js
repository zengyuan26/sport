const PENDING_TASK_KEY = "bluebrainPendingCreationTask";

function findComposer() {
  return document.querySelector('[contenteditable="true"][role="textbox"]')
    || document.querySelector('textarea[placeholder*="Message"]')
    || document.querySelector('textarea');
}

function fillComposer(brief) {
  const composer = findComposer();
  if (!composer) return false;

  composer.focus();
  if (composer instanceof HTMLTextAreaElement) {
    composer.value = brief;
  } else {
    composer.textContent = brief;
  }
  composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: brief }));
  return true;
}

function createPanel(task) {
  if (document.getElementById("bluebrain-companion-panel")) return;
  const panel = document.createElement("section");
  panel.id = "bluebrain-companion-panel";
  panel.innerHTML = `
    <strong>蓝脑星球创作助手</strong>
    <span>本次创作任务已经带到这里。</span>
    <button type="button">填入对话框</button>
    <small>只会填入本次任务，不会自动发送，也不会读取你的聊天记录。</small>
  `;
  Object.assign(panel.style, {
    position: "fixed", right: "20px", bottom: "20px", zIndex: "2147483647", width: "266px",
    padding: "15px", borderRadius: "16px", color: "#243342", background: "rgba(255,255,255,.96)",
    border: "1px solid rgba(120,150,175,.28)", boxShadow: "0 18px 48px rgba(26,51,75,.18)",
    fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif", fontSize: "13px", lineHeight: "1.55"
  });
  panel.querySelector("strong").style.display = "block";
  panel.querySelector("span").style.display = "block";
  panel.querySelector("span").style.margin = "4px 0 11px";
  const button = panel.querySelector("button");
  Object.assign(button.style, { border: "0", borderRadius: "10px", padding: "9px 12px", background: "#245f88", color: "white", cursor: "pointer", fontWeight: "600" });
  panel.querySelector("small").style.display = "block";
  panel.querySelector("small").style.marginTop = "9px";
  panel.querySelector("small").style.color = "#657687";

  button.addEventListener("click", () => {
    if (fillComposer(task.brief)) {
      button.textContent = "已填入，请检查后发送";
      button.disabled = true;
      chrome.storage.local.remove(PENDING_TASK_KEY);
    } else {
      button.textContent = "还没找到输入框，请先新建聊天";
    }
  });
  document.body.append(panel);
}

chrome.storage.local.get(PENDING_TASK_KEY).then((items) => {
  const task = items[PENDING_TASK_KEY];
  if (!task?.brief) return;
  createPanel(task);
});
