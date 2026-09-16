export type WorkspaceSnapshot = Record<string, unknown> & {
  teachers: unknown[];
  activeTeacher: number;
  styleCards: unknown[];
};

export type WorkspaceState = {
  workspace: WorkspaceSnapshot;
  revision: number;
};

type WorkspaceRow = {
  payload_json: string;
  revision: number;
};

export type WorkspaceWriteResult =
  | { ok: true; nextRevision: number; workspace: WorkspaceSnapshot }
  | { ok: false; status: "conflict" };

export type SaveRequest =
  | { workspace: WorkspaceSnapshot; revision: number }
  | { error: string };

export function emptyWorkspace(): WorkspaceSnapshot {
  return { teachers: [], activeTeacher: 0, styleCards: [] };
}

export function isWorkspaceSnapshot(value: unknown): value is WorkspaceSnapshot {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Partial<WorkspaceSnapshot>;
  return Array.isArray(candidate.teachers) && Array.isArray(candidate.styleCards);
}

export function parseSaveRequest(value: unknown): SaveRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { error: "保存的数据格式不正确。" };
  }
  const candidate = value as { workspace?: unknown; revision?: unknown };
  if (
    !isWorkspaceSnapshot(candidate.workspace) ||
    !Number.isSafeInteger(candidate.revision) ||
    (candidate.revision as number) < 0 ||
    JSON.stringify(candidate.workspace).length > 2_000_000
  ) {
    return { error: "保存的数据格式不正确。" };
  }
  return { workspace: candidate.workspace, revision: candidate.revision as number };
}

export function applyWorkspaceWrite(
  current: Pick<WorkspaceState, "revision">,
  expectedRevision: number,
  workspace: WorkspaceSnapshot,
): WorkspaceWriteResult {
  if (current.revision !== expectedRevision) return { ok: false, status: "conflict" };
  return { ok: true, nextRevision: current.revision + 1, workspace };
}

function parseWorkspace(row: WorkspaceRow | null): WorkspaceState {
  if (!row) return { workspace: emptyWorkspace(), revision: 0 };
  try {
    const workspace = JSON.parse(row.payload_json);
    if (isWorkspaceSnapshot(workspace)) return { workspace, revision: row.revision };
  } catch {
    // A malformed row must not be served as a valid teacher workspace.
  }
  throw new Error("线上资料暂时无法读取，请联系管理员检查数据库记录。");
}

export async function readWorkspace(db: D1Database): Promise<WorkspaceState> {
  const row = await db
    .prepare("SELECT payload_json, revision FROM team_workspace WHERE id = 1")
    .first<WorkspaceRow>();
  return parseWorkspace(row);
}

export async function saveWorkspace(
  db: D1Database,
  workspace: WorkspaceSnapshot,
  expectedRevision: number,
): Promise<WorkspaceWriteResult> {
  const current = await readWorkspace(db);
  const next = applyWorkspaceWrite(current, expectedRevision, workspace);
  if (!next.ok) return next;

  if (current.revision === 0) {
    const inserted = await db
      .prepare(
        "INSERT OR IGNORE INTO team_workspace (id, payload_json, revision, updated_at) VALUES (1, ?, 1, CURRENT_TIMESTAMP)",
      )
      .bind(JSON.stringify(workspace))
      .run();
    return inserted.meta.changes === 1 ? next : { ok: false, status: "conflict" };
  }

  const updated = await db
    .prepare(
      "UPDATE team_workspace SET payload_json = ?, revision = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1 AND revision = ?",
    )
    .bind(JSON.stringify(workspace), next.nextRevision, expectedRevision)
    .run();
  return updated.meta.changes === 1 ? next : { ok: false, status: "conflict" };
}
