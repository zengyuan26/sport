# 蓝脑星球培训讲师工作台线上版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把本地讲师 IP 工作台变成一个由共同入口密码保护、共享保存、可持续发布的内部线上系统。

**Architecture:** 保留现有单页工作台的交互和视觉，作为托管站点的静态工作台页面；使用 Cloudflare Worker API 负责共同入口验证、会话和共享工作空间读写。D1 只保存一份团队工作空间及安全会话记录，代码发布和数据存储相互独立；保存采用乐观版本号，拒绝无提示覆盖。

**Tech Stack:** Vinext/React 站点壳、现有 HTML/JavaScript 工作台、Cloudflare Workers、D1、Drizzle 迁移、Vitest、Sites 托管。

**Spec:** `docs/superpowers/specs/2026-09-16-bluebrain-workbench-online-design.md`

## Global Constraints

- 仅供内部使用；老师不注册、不登录。
- 共同入口密码只存在部署环境机密配置 `INTERNAL_ACCESS_CODE`，绝不提交到 Git 或写入浏览器存储。
- D1 绑定固定为 `DB`；不在第一期引入 R2、上传、录音文件或外部大模型。
- 讲师资料的唯一权威来源是 D1；浏览器存储只能做临时界面用途。
- 原型的四个主模块、讲师卡、新增老师引导与内容创作流程必须保留。
- 所有可见中文文案保持面向内部运营人员的自然语言，不出现“证据补全”“缺资料”等强迫补充话术。
- 数据库迁移只新增，不修改已部署迁移。
- 实现时在空目录 `work/bluebrain-online-site` 初始化站点，并从 `sport` 创建 `codex/online-workbench-v1` 分支；现有 `work/online-system` 仅作为原型和设计参考，不直接发布。

---

### Task 1: 建立可发布的站点壳与线上配置

**Files:**
- Create: `.openai/hosting.json`
- Create: `.env.example`
- Create: `public/workbench.html`
- Modify: `app/page.tsx`
- Modify: `app/layout.tsx`
- Modify: `vite.config.ts`
- Modify: `package.json`
- Test: `tests/site-shell.test.ts`

**Interfaces:**
- Consumes: 现有 `index.html` 的所有界面、样例数据与交互脚本。
- Produces: `/` 进入 `public/workbench.html`，并在产物中保留 Cloudflare Worker、静态资源和 D1 的逻辑绑定 `DB`。

- [ ] **Step 1: 创建失败的站点壳测试**

```ts
import { describe, expect, it } from 'vitest';
import { readFile } from 'node:fs/promises';

describe('online workbench shell', () => {
  it('ships the workbench without a source-tree API key', async () => {
    const html = await readFile('public/workbench.html', 'utf8');
    const manifest = JSON.parse(await readFile('.openai/hosting.json', 'utf8'));
    expect(html).toContain('蓝脑星球培训讲师工作台');
    expect(html).not.toMatch(/INTERNAL_ACCESS_CODE\s*=\s*[^"']/);
    expect(manifest.d1).toEqual([{ binding: 'DB' }]);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `npm test -- tests/site-shell.test.ts`

Expected: FAIL，因为站点壳和托管配置尚未建立。

- [ ] **Step 3: 建立最小站点壳**

在空目录 `work/bluebrain-online-site` 运行 Sites 的 Vinext starter 初始化，初始化 Git 后从 `sport` 创建 `codex/online-workbench-v1` 分支。将当前 `work/online-system/index.html` 原样迁入 `public/workbench.html`，确保内联资源和现有交互在新路径仍正常工作；根页面只提供直接进入该工作台的入口。添加：

```json
{
  "d1": [{ "binding": "DB" }]
}
```

到 `.openai/hosting.json`。在 `.env.example` 仅声明：

```dotenv
INTERNAL_ACCESS_CODE=
```

保留 starter 的 `sites()` 构建插件，并为 `test` 添加 Vitest 脚本；不把真实密码写进任何文件。

- [ ] **Step 4: 运行站点壳测试与构建**

Run: `npm test -- tests/site-shell.test.ts && node /Users/zengyuan/.codex/plugins/cache/openai-curated-remote/sites/0.1.62/scripts/build-site.mjs`

Expected: PASS；构建输出包含站点静态资源、Worker 入口和托管清单。

- [ ] **Step 5: 提交站点壳**

```bash
git add .openai/hosting.json .env.example public/workbench.html app/page.tsx app/layout.tsx vite.config.ts package.json tests/site-shell.test.ts
git commit -m "feat: create hosted workbench shell"
```

### Task 2: 用共同入口密码替换个人注册/登录

**Files:**
- Create: `app/lib/server/access.ts`
- Create: `app/api/access/route.ts`
- Create: `app/api/session/route.ts`
- Modify: `public/workbench.html`
- Test: `tests/access.test.ts`

**Interfaces:**
- Consumes: `INTERNAL_ACCESS_CODE`、D1 `DB`、浏览器的 `/api/access` 和 `/api/session` 请求。
- Produces: `verifyAccessCode(code, expectedCode): Promise<boolean>`、`createSession(db): Promise<string>`、`getSession(request, db): Promise<Session | null>`、`clearSession(request, db): Promise<void>`。

- [ ] **Step 1: 创建失败的访问控制测试**

```ts
import { describe, expect, it } from 'vitest';
import { timingSafeCodeMatch, validateAccessInput } from '../app/lib/server/access';

describe('shared access code', () => {
  it('accepts only a non-empty matching code', async () => {
    expect(validateAccessInput('')).toEqual({ error: '请输入内部入口密码。' });
    await expect(timingSafeCodeMatch('wrong-code', 'team-code')).resolves.toBe(false);
    await expect(timingSafeCodeMatch('team-code', 'team-code')).resolves.toBe(true);
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `npm test -- tests/access.test.ts`

Expected: FAIL，因为访问控制模块尚不存在。

- [ ] **Step 3: 实现访问控制与会话 API**

实现常量时间比较；入口码验证成功后生成 32 字节随机 token，只在数据库保存 token 的 SHA-256 摘要。设置带 `HttpOnly; Secure; SameSite=Lax; Path=/` 的 30 天 Cookie。

`POST /api/access` 请求体为 `{ "code": string }`，成功时返回 `{ "ok": true }`；错误时返回中文可恢复错误。`GET /api/session` 返回 `{ "signedIn": boolean }`；`POST /api/session/logout` 删除当前会话并清 Cookie。所有数据库操作使用单条 prepared statement。

把现有 `cloudAuth` 邮箱/注册 UI 改成只有“输入内部入口密码”的开屏，移除“创建工作空间”、邮箱和个人账号文案；登录后调用 `GET /api/workspace`。为登出保留一个低调的顶部操作。

- [ ] **Step 4: 运行访问控制测试与 Worker 类型检查**

Run: `npm test -- tests/access.test.ts && npm run typecheck`

Expected: PASS；错误密码不能建立会话，正确密码会建立只读 Cookie 会话。

- [ ] **Step 5: 提交访问控制**

```bash
git add app/lib/server/access.ts app/api/access/route.ts app/api/session/route.ts public/workbench.html tests/access.test.ts
git commit -m "feat: add shared internal access gate"
```

### Task 3: 创建共享工作空间数据库与版本保护保存

**Files:**
- Create: `db/schema.ts`
- Create: `drizzle.config.ts`
- Create: `drizzle/0000_*.sql`
- Create: `drizzle/meta/_journal.json`
- Create: `drizzle/meta/0000_snapshot.json`
- Create: `app/lib/server/workspace.ts`
- Create: `app/api/workspace/route.ts`
- Test: `tests/workspace.test.ts`

**Interfaces:**
- Consumes: 通过 `getSession` 验证后的请求、D1 `DB` 和客户端 `{ workspace, revision }`。
- Produces: `readWorkspace(db): Promise<{workspace: WorkspaceSnapshot, revision: number}>` 和 `saveWorkspace(db, workspace, expectedRevision): Promise<SaveResult>`。

- [ ] **Step 1: 创建失败的共享保存测试**

```ts
import { describe, expect, it } from 'vitest';
import { applyWorkspaceWrite } from '../app/lib/server/workspace';

describe('shared workspace revision guard', () => {
  it('rejects a write based on an old revision', () => {
    expect(applyWorkspaceWrite({ revision: 4 }, 3, { teachers: [] }))
      .toEqual({ ok: false, status: 'conflict' });
  });

  it('increments a matching revision', () => {
    expect(applyWorkspaceWrite({ revision: 4 }, 4, { teachers: [] }))
      .toMatchObject({ ok: true, nextRevision: 5 });
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `npm test -- tests/workspace.test.ts`

Expected: FAIL，因为共享工作空间模块尚不存在。

- [ ] **Step 3: 添加迁移、仓储与 API**

在 `db/schema.ts` 用 Drizzle 表定义生成初始迁移（`npm run db:generate`）；保存生成的 SQL、journal 与 snapshot。迁移只能包含 schema，逻辑等效于：

```sql
CREATE TABLE team_workspace (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  payload_json TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE access_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_access_sessions_token_hash ON access_sessions(token_hash);
```

首次读取时若没有 `team_workspace` 行，返回空的初始状态 `{ teachers: [], activeTeacher: 0, styleCards: [] }`，但不把样例数据写进迁移。保存时以一次带 revision 条件的更新完成比较并写入；若更新行数为零，返回 HTTP 409 与最新 revision。`GET /api/workspace` 和 `PUT /api/workspace` 都要求有效会话；限制 JSON 请求小于 2 MB，并拒绝数组或无效对象。

- [ ] **Step 4: 运行保存测试与迁移检查**

Run: `npm test -- tests/workspace.test.ts && npm run db:check && npm run typecheck`

Expected: PASS；迁移包含两张表与唯一的会话摘要索引；旧版本保存返回冲突而不是覆盖资料。

- [ ] **Step 5: 提交数据库与共享保存接口**

```bash
git add db/schema.ts drizzle.config.ts drizzle app/lib/server/workspace.ts app/api/workspace/route.ts tests/workspace.test.ts
git commit -m "feat: persist shared teacher workspace"
```

### Task 4: 将工作台接入共享保存、异常提示与样例迁移

**Files:**
- Modify: `public/workbench.html`
- Create: `tests/workbench-sync.test.ts`

**Interfaces:**
- Consumes: `GET /api/session`、`POST /api/access`、`GET /api/workspace`、`PUT /api/workspace`。
- Produces: `loadWorkspace()`、`scheduleWorkspaceSave()`、`saveWorkspace()` 和全局 `workspaceRevision`，不再使用旧的个人工作空间/注册接口。

- [ ] **Step 1: 创建失败的浏览器同步测试**

```ts
import { describe, expect, it } from 'vitest';
import { nextSaveAction } from '../app/lib/workbench-sync';

describe('workbench save feedback', () => {
  it('preserves the editor state when the server reports a conflict', () => {
    expect(nextSaveAction({ status: 409 }, { teachers: [{ name: '吕老师' }] }))
      .toEqual({ action: 'show-conflict', preserveLocalDraft: true });
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `npm test -- tests/workbench-sync.test.ts`

Expected: FAIL，因为同步决策模块尚不存在。

- [ ] **Step 3: 实现共享工作台同步**

将复用的请求/同步决策移到 `app/lib/workbench-sync.ts`，由 `public/workbench.html` 调用。工作台加载后先验证会话：已验证则读取共享工作空间；若服务器尚为空，则保留并显示原型的吕老师等示例卡，只有首次成功保存时才成为团队初始资料。

每次有效编辑后以 900 ms 防抖保存 `{ workspace: snapshot, revision: workspaceRevision }`。成功后刷新 `workspaceRevision` 并显示短暂“已保存”；网络错误显示“暂未同步，内容仍在当前页面，可稍后重试”；409 冲突显示“其他同事刚保存了资料，为避免覆盖，请刷新最新资料后再决定保留哪一版”，并保留当前编辑内容，不自动丢弃或覆盖。删除 `sendBeacon` 保存，避免未带 revision 的卸载请求覆盖别人刚保存的资料。

- [ ] **Step 4: 运行同步测试、脚本语法检查和完整测试**

Run: `npm test -- tests/workbench-sync.test.ts && npm test && npm run typecheck && npm run check:workbench`

Expected: PASS；工作台脚本可解析；冲突和离线错误均保留当前输入。

- [ ] **Step 5: 提交工作台同步**

```bash
git add public/workbench.html app/lib/workbench-sync.ts tests/workbench-sync.test.ts package.json
git commit -m "feat: sync shared workbench safely"
```

### Task 5: 上线前验证、私有发布与更新说明

**Files:**
- Create: `README.md`
- Modify: `.openai/hosting.json`
- Test: `tests/release-readiness.test.ts`

**Interfaces:**
- Consumes: 完整构建产物、D1 迁移、Sites 机密 `INTERNAL_ACCESS_CODE`。
- Produces: 可访问的内部网址和一份不包含任何密码或真实讲师资料的维护说明。

- [ ] **Step 1: 创建失败的发布准备测试**

```ts
import { describe, expect, it } from 'vitest';
import { readFile } from 'node:fs/promises';

describe('release readiness', () => {
  it('does not ship credentials or teacher payloads in source configuration', async () => {
    const envExample = await readFile('.env.example', 'utf8');
    const readme = await readFile('README.md', 'utf8');
    expect(envExample).toBe('INTERNAL_ACCESS_CODE=\n');
    expect(readme).toContain('页面更新不会清空 D1 中的讲师资料');
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `npm test -- tests/release-readiness.test.ts`

Expected: FAIL，因为维护说明尚不存在。

- [ ] **Step 3: 编写最小维护说明并配置托管**

README 只说明内部使用者需要设置共同入口密码、如何日后更新站点、如何确认资料没有被覆盖，以及未来升级为多人账号时的方向。不得在 README、HTML、测试样例或 Git 提交中放入真实密码、会话 token 或真实老师对话。

检查 `.openai/hosting.json` 仅包含 `project_id`、D1 逻辑绑定和所需能力；在 Sites 的运行时机密配置中设置 `INTERNAL_ACCESS_CODE`。创建并保存首个站点版本，保持私有发布；部署后仅把内部网址交给用户。

- [ ] **Step 4: 运行完整验证与发布构建**

Run: `npm test && npm run typecheck && npm run check:workbench && node /Users/zengyuan/.codex/plugins/cache/openai-curated-remote/sites/0.1.62/scripts/build-site.mjs`

Expected: PASS；产物含 Worker、静态页面、D1 迁移和托管清单；无机密进入产物源文件。

- [ ] **Step 5: 提交并发布**

```bash
git add README.md .openai/hosting.json tests/release-readiness.test.ts
git commit -m "docs: prepare internal workbench release"
git push -u origin codex/online-workbench-v1
git checkout main
git merge --ff-only codex/online-workbench-v1
git push origin main
```

通过 Sites 保存并部署该提交对应的版本；部署后在两个独立浏览器会话中验证：错误密码拒绝、正确密码可进入、第一处修改刷新后仍在、另一会话的旧版本保存得到冲突提示。
