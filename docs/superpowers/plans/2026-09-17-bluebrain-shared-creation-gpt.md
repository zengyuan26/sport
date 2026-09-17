# 蓝脑星球共享创作 GPT 交接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 将内容创作改为共享创作 GPT 的任务入口、跳转和结果归档。

**Architecture:** 工作台继续保存讲师资料和创作资产；共享 GPT 负责对话、检索、选题与成稿。工作台把当前讲师、受众、产品和素材组织成任务说明，复制后在新标签打开共享 GPT；创作结束后用固定字段回填到既有 D1 工作区。

**Tech Stack:** Next.js route handlers on Cloudflare Workers, D1, static HTML/CSS/JavaScript, Vitest, ChatGPT custom GPT.

**Spec:** \`docs/superpowers/specs/2026-09-17-bluebrain-shared-creation-gpt-design.md\`

## Global Constraints

- 不接 OpenAI API，也不在工作台内假装已经联网分析或自动出稿。
- 内容创作只保留新闻 / 链接、洗稿、原创想法三种入口。
- 未配置已发布的共享 GPT 时，页面显示清楚的管理员提示，不跳转到假链接。
- 写法固定在共享 GPT；讲师端不再有新增参考风格。
- 保留共同入口密码、D1 保存、冲突保护，并兼容没有新创作字段的旧工作区。
- 不保存 ChatGPT 凭据；不自动向用户的 ChatGPT 对话发送内容。

---

## File Structure

- \`app/lib/server/creation-gpt.ts\` — 验证共享 GPT URL。
- \`app/api/creation-gpt/route.ts\` — 向已进入工作台的成员返回配置。
- \`cloudflare-env.d.ts\`、\`.env.example\` — 声明不带真实值的 \`CREATION_GPT_URL\`。
- \`public/workbench.html\` — 创作任务入口、复制与跳转、回填结果。
- \`docs/bluebrain-creation-gpt-instructions.md\` — 可直接放进 GPT Builder 的配置文本。
- \`tests/creation-gpt.test.ts\` — URL、页面交接和方法库断言。
- \`tests/release-readiness.test.ts\` — 环境模板安全断言。

### Task 1: Add protected shared-GPT configuration

**Files:**
- Create: \`app/lib/server/creation-gpt.ts\`
- Create: \`app/api/creation-gpt/route.ts\`
- Create: \`tests/creation-gpt.test.ts\`
- Modify: \`cloudflare-env.d.ts\`, \`.env.example\`, \`tests/release-readiness.test.ts\`

**Interfaces:**
- Consumes: \`hasSession(request, database())\` and \`env.CREATION_GPT_URL\`.
- Produces: \`readCreationGptUrl(value?: string): { available: boolean; url: string | null }\` and \`GET /api/creation-gpt\`.

- [ ] **Step 1: Write the failing unit test**

\`\`\`ts
import { expect, it } from "vitest";
import { readCreationGptUrl } from "../app/lib/server/creation-gpt";

it("accepts only a published ChatGPT GPT URL", () => {
  expect(readCreationGptUrl(undefined)).toEqual({ available: false, url: null });
  expect(readCreationGptUrl("https://example.com/g/test")).toEqual({ available: false, url: null });
  expect(readCreationGptUrl("https://chatgpt.com/g/g-bluebrain")).toEqual({
    available: true, url: "https://chatgpt.com/g/g-bluebrain",
  });
});
\`\`\`

- [ ] **Step 2: Verify it fails**

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts\`

Expected: FAIL because \`app/lib/server/creation-gpt.ts\` is missing.

- [ ] **Step 3: Implement validation and the protected route**

\`\`\`ts
export function readCreationGptUrl(value?: string) {
  const url = value?.trim() ?? "";
  return /^https:\\/\\/chatgpt\\.com\\/g\\/[^/?#]+\\/?$/.test(url)
    ? { available: true, url }
    : { available: false, url: null };
}
\`\`\`

The route returns HTTP 401 with \`请先输入内部入口密码。\` when \`hasSession()\` is false; otherwise it returns \`readCreationGptUrl(env.CREATION_GPT_URL)\`. Extend \`Cloudflare.Env\` with \`CREATION_GPT_URL?: string\`; make \`.env.example\` exactly:

\`\`\`dotenv
INTERNAL_ACCESS_CODE=
CREATION_GPT_URL=
\`\`\`

- [ ] **Step 4: Update and run focused tests**

Update \`tests/release-readiness.test.ts\` to expect the two empty environment keys and to reject \`chatgpt.com/g/\` in the template.

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts tests/release-readiness.test.ts\`

Expected: PASS.

- [ ] **Step 5: Commit**

\`\`\`bash
git add app/lib/server/creation-gpt.ts app/api/creation-gpt/route.ts cloudflare-env.d.ts .env.example tests/creation-gpt.test.ts tests/release-readiness.test.ts && git commit -m "feat: expose shared creation gpt safely"
\`\`\`

### Task 2: Replace the local creator with a creative-task launcher

**Files:**
- Modify: \`public/workbench.html\`
- Modify: \`tests/creation-gpt.test.ts\`

**Interfaces:**
- Consumes: \`GET /api/creation-gpt\`, \`teachers[activeTeacher]\`, \`audienceCampaigns[campaignIndex]\`, \`scheduleTeamSave()\`.
- Produces: \`creationTask\`, \`buildCreationBrief()\`, \`openCreationGpt()\`, \`saveCreationResult()\`.

- [ ] **Step 1: Write the failing page contract test**

\`\`\`ts
import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("ships a shared-GPT creative task handoff", async () => {
  const html = await readFile("public/workbench.html", "utf8");
  expect(html).toContain("新闻 / 链接");
  expect(html).toContain("洗稿");
  expect(html).toContain("原创想法");
  expect(html).toContain("进入蓝脑星球创作 GPT");
  expect(html).toContain("function buildCreationBrief");
  expect(html).toContain("function saveCreationResult");
  expect(html).not.toContain("＋ 新增参考风格");
});
\`\`\`

- [ ] **Step 2: Verify it fails**

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts\`

Expected: FAIL because the current page still has user-created style cards.

- [ ] **Step 3: Implement the one-screen task surface**

Replace \`renderCreate()\` with current-teacher context plus three source cards. Show only one material textarea and, for 原创想法, an optional audience picker. Use these exact labels:

\`\`\`text
内容创作
把一条素材或一个念头，带进蓝脑星球创作 GPT。
新闻 / 链接
洗稿
原创想法
这次先说给谁听（可选）
带着这条任务去创作
\`\`\`

Mode helpers are respectively: \`粘贴新闻、热点链接或一段原始素材；先找可讲的角度，不急着复述新闻。\`, \`粘贴参考图文、长文或口播稿；先提取观点与结构，再重写成自己的内容。\`, and \`写下你想到的概念、观察或想聊的事；系统会先陪你把它聊清楚，再找素材与角度。\`.

- [ ] **Step 4: Implement handoff, persistence and unavailable state**

Add backwards-safe \`creationTask\` to \`teamSnapshot()\` and \`restoreTeamWorkspace()\`. \`buildCreationBrief()\` includes teacher name, identity line, selected audience, product, input type and raw material, followed by: \`请先补找必要素材，给我 3—5 个角度卡；每张写清受众张力、讲师进入位置、新判断、建议选题、身份 / 商业 / 双重目的、事实边界与来源。等我选定角度后，再进入情绪结构、内容形态、固定写法和成稿。\`

On the explicit launch click, request \`/api/creation-gpt\`, copy the brief with \`navigator.clipboard.writeText\`, then \`window.open(url, "_blank", "noopener")\`. If copy fails, show the brief in a selectable modal. If the API returns unavailable, show \`创作 GPT 还没有发布。请联系管理员完成内部发布后再开始。\` and never open a new tab.

- [ ] **Step 5: Add a fixed-field return modal**

After a launch attempt, show \`回来后回填结果\` with exactly: 最终选题, 内容目的（身份信号强化 / 商业目的强化 / 双重强化 / 暂不采用）, 内容形态（长文 / 口播 / 图文）, 使用方法（小德写法 / 朱莉娅写法 / 图文方法名称）, 最终稿. \`saveCreationResult()\` stores these in \`creationTask.result\`, calls \`scheduleTeamSave()\`, and shows \`创作结果已归档到<老师名>的工作台\`.

- [ ] **Step 6: Verify and commit**

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts tests/site-shell.test.ts tests/workspace.test.ts\`

Expected: PASS.

\`\`\`bash
git add public/workbench.html tests/creation-gpt.test.ts && git commit -m "feat: hand creative tasks to shared gpt"
\`\`\`

### Task 3: Create the shared GPT method library

**Files:**
- Create: \`docs/bluebrain-creation-gpt-instructions.md\`
- Modify: \`tests/creation-gpt.test.ts\`

**Interfaces:**
- Consumes: the copied brief from Task 2.
- Produces: a \`工作台回填包\` with the five Task 2 fields.

- [ ] **Step 1: Write the failing method-library test**

\`\`\`ts
it("documents the fixed shared creation methods", async () => {
  const instructions = await readFile("docs/bluebrain-creation-gpt-instructions.md", "utf8");
  expect(instructions).toContain("小德写法");
  expect(instructions).toContain("朱莉娅写法");
  expect(instructions).toContain("资料压缩型");
  expect(instructions).toContain("工作台回填包");
  expect(instructions).toContain("不要直接写完整稿");
});
\`\`\`

- [ ] **Step 2: Verify it fails**

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts\`

Expected: FAIL because the instruction document is missing.

- [ ] **Step 3: Write the ready-to-paste Builder document**

Name the assistant \`蓝脑星球创作 GPT\`; describe it as \`把新闻、参考稿和原创念头，变成能服务讲师身份与招生目标的内容。\`; include four starters: \`给我一条新闻或链接\`, \`我想洗一篇稿\`, \`我有一个原创念头\`, \`继续完善这条选题\`.

Require input → source / high-loss-decision check → 3–5 angle cards → user choice → purpose label → 苦欲怕罪事物框心行留 → form → fixed method → draft. Include citation / uncertainty boundaries and no copying of supplied reference text. Specify 小德、朱莉娅 and all four image-text groups: 资料与结构、判断与行动、观点与叙事、体验与证明. End with the exact five-field \`工作台回填包\`.

- [ ] **Step 4: Verify and commit**

Run: \`npx vitest run --config vitest.config.ts tests/creation-gpt.test.ts\`

Expected: PASS.

\`\`\`bash
git add docs/bluebrain-creation-gpt-instructions.md tests/creation-gpt.test.ts && git commit -m "docs: add shared creation gpt instructions"
\`\`\`

### Task 4: Publish, configure and release

**Files:**
- Modify: hosted \`CREATION_GPT_URL\` only after GPT publication.
- Modify: no source file unless a verification failure needs a fix.

**Interfaces:**
- Consumes: Task 1 endpoint and Task 3 Builder document.
- Produces: an internal shared GPT link and a working production handoff.

- [ ] **Step 1: Prepare the GPT Builder without publishing**

Enter Task 3’s name, description, starters and full instructions in ChatGPT’s GPT Builder. Select the internal-only option compatible with the team workspace, but do not publish or change sharing yet.

- [ ] **Step 2: Ask immediately before publishing**

Ask exactly: \`共享 GPT 已配置好。现在将把“蓝脑星球创作 GPT”发布给内部团队使用，并生成一个可放进工作台的 ChatGPT 链接；这会改变其 ChatGPT 共享权限。确认发布吗？\`

Expected: explicit user confirmation.

- [ ] **Step 3: Publish and configure**

After confirmation, publish at the internal-only scope; copy the exact \`https://chatgpt.com/g/...\` URL; set hosted \`CREATION_GPT_URL\` to that exact value while preserving \`INTERNAL_ACCESS_CODE\`. Verify signed-in \`/api/creation-gpt\` returns \`{ available: true, url: "<exact published URL>" }\` and signed-out access returns HTTP 401.

- [ ] **Step 4: Run complete checks, deploy and verify**

\`\`\`bash
npm test && npm run typecheck && npm run build
git add public/workbench.html app cloudflare-env.d.ts .env.example docs tests && git commit -m "feat: launch shared creation gpt handoff"
git push origin HEAD:main
git rev-parse --verify HEAD
\`\`\`

Package that exact pushed commit, save a version of \`appgprj_6aaaaff1e4bc8191ac1b910e4d911229\`, deploy it while preserving the D1 binding and access settings, then verify: enter the workbench, select all three modes, launch a populated task, return a five-field result, refresh, and confirm the result persists.

## Self-Review

- Tasks 1–2 cover no-API handoff, protected configuration, three sources, task copy, redirect, fallback and D1 persistence.
- Task 3 covers fixed methods, research boundaries, angle-first workflow and the exact result schema.
- Task 4 covers internal sharing confirmation, runtime configuration, production release and real user journey.
- \`readCreationGptUrl()\` returns the same \`{ available, url }\` shape from route to page; Task 2 and Task 3 use the same five result fields.
- Every implementation and verification step has a concrete file, action and expected result.
