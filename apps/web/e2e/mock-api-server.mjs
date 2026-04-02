import http from "node:http";
import { randomUUID } from "node:crypto";

const port = Number(process.env.SYNAPSE_E2E_API_PORT || 18180);
const projectIdDefault = "omega_demo";
const INCIDENT_SECRET_MASK = "********";
const INCIDENT_SECRET_CLEAR_TOKEN = "__clear__";
const INCIDENT_SECRET_EDIT_ROLES_DEFAULT = ["incident_admin", "security_admin", "admin"];
const INCIDENT_SECRET_RBAC_MODE = String(process.env.SYNAPSE_INCIDENT_SECRET_RBAC_MODE || "open")
  .trim()
  .toLowerCase();
const TASK_STATUS_ORDER = {
  in_progress: 0,
  blocked: 1,
  todo: 2,
  done: 3,
  canceled: 4,
};
const TASK_PRIORITY_ORDER = {
  critical: 0,
  high: 1,
  normal: 2,
  low: 3,
};
const TASK_STATUS_SET = new Set(["todo", "in_progress", "blocked", "done", "canceled"]);
const TASK_ACTIVE_STATUS_SET = new Set(["todo", "in_progress", "blocked"]);
const TASK_PRIORITY_SET = new Set(["low", "normal", "high", "critical"]);
const TASK_SOURCE_SET = new Set(["agent", "human", "system"]);
const TASK_LINK_TYPE_SET = new Set(["claim", "draft", "page", "event", "external"]);

const snapshots = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    project_id: projectIdDefault,
    source: "calibration_cycle",
    approved_by: "ops_manager",
    note: "nightly calibration",
    config: {
      min_score_for_golden: 0.72,
      llm_score_weight: 0.35,
      llm_min_confidence: 0.65,
      llm_model: "gpt-4.1-mini",
    },
    guardrails_met: true,
    holdout_meta: {},
    calibration_report: {},
    artifact_refs: {},
    created_at: "2026-03-31T08:00:00Z",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    project_id: projectIdDefault,
    source: "manual",
    approved_by: "qa_manager",
    note: "manual tune",
    config: {
      min_score_for_golden: 0.7,
      llm_score_weight: 0.4,
      llm_min_confidence: 0.68,
      llm_model: "gpt-4.1-mini",
    },
    guardrails_met: false,
    holdout_meta: {},
    calibration_report: {},
    artifact_refs: {},
    created_at: "2026-03-30T08:00:00Z",
  },
];

const state = {
  schedules: [
    {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      project_id: projectIdDefault,
      name: "omega-nightly",
      enabled: true,
      preset: "nightly",
      interval_hours: 24,
      lookback_days: 60,
      limit_rows: 20000,
      holdout_ratio: 0.3,
      split_seed: "synapse-gatekeeper-prod-holdout-v1",
      weights: [0.2, 0.3, 0.4, 0.5],
      confidences: [0.6, 0.7, 0.8],
      score_thresholds: [0.58, 0.66, 0.74],
      top_k: 5,
      allow_guardrail_fail: false,
      snapshot_note: "nightly automation",
      updated_by: "system",
      last_run_at: "2026-03-31T05:00:00Z",
      last_status: "ok",
      last_run_summary: {},
      created_at: "2026-03-28T05:00:00Z",
      updated_at: "2026-03-31T05:10:00Z",
    },
  ],
  alertTargets: [],
  rollbackRequests: [],
  operationRuns: [],
  operationEventSeq: 1,
  queueControls: [],
  queueOwnerships: [],
  queueAuditEvents: [],
  queueAuditSeq: 1,
  queueAuditAnnotations: [],
  queueIncidentHooks: [],
  queueIncidentPolicies: [],
  queueIncidentPreflightPresets: [],
  queueIncidents: [],
  queueIncidentSyncSchedules: [
    {
      id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      project_id: projectIdDefault,
      name: "default",
      enabled: true,
      preset: "every_4h",
      interval_minutes: 240,
      window_hours: 24,
      batch_size: 50,
      sync_limit: 50,
      dry_run: false,
      force_resolve: false,
      preflight_enforcement_mode: "inherit",
      preflight_pause_hours: null,
      preflight_critical_fail_threshold: null,
      preflight_include_run_before_live_sync_only: true,
      preflight_record_audit: true,
      requested_by: "system",
      next_run_at: new Date(Date.now() + 90 * 60 * 1000).toISOString(),
      last_run_at: null,
      last_status: null,
      last_run_summary: {},
      updated_by: "system",
      created_at: nowIso(),
      updated_at: nowIso(),
    },
  ],
  tasks: [
    {
      id: "f95adf62-e390-4f8f-b7f4-79a0cb87a3fd",
      project_id: projectIdDefault,
      title: "Validate Omega gate access policy",
      description: "Agents reported card-only access after 10:00 at BC Omega.",
      status: "in_progress",
      priority: "high",
      source: "human",
      assignee: "ops_manager",
      entity_key: "bc_omega",
      category: "access_policy",
      due_at: "2026-04-05T15:00:00Z",
      created_by: "ops_manager",
      updated_by: "ops_manager",
      metadata: {},
      created_at: "2026-04-01T09:10:00Z",
      updated_at: "2026-04-01T11:05:00Z",
    },
  ],
  taskEvents: [
    {
      id: "11fd5ddf-4f6b-420a-873c-f020ad27885c",
      task_id: "f95adf62-e390-4f8f-b7f4-79a0cb87a3fd",
      project_id: projectIdDefault,
      event_type: "created",
      actor: "ops_manager",
      payload: {
        task: {
          id: "f95adf62-e390-4f8f-b7f4-79a0cb87a3fd",
          project_id: projectIdDefault,
          title: "Validate Omega gate access policy",
          description: "Agents reported card-only access after 10:00 at BC Omega.",
          status: "in_progress",
          priority: "high",
          source: "human",
          assignee: "ops_manager",
          entity_key: "bc_omega",
          category: "access_policy",
          due_at: "2026-04-05T15:00:00Z",
          created_by: "ops_manager",
          updated_by: "ops_manager",
          metadata: {},
          created_at: "2026-04-01T09:10:00Z",
          updated_at: "2026-04-01T11:05:00Z",
        },
      },
      created_at: "2026-04-01T09:10:00Z",
    },
  ],
  taskLinks: [],
  wikiPages: [
    {
      id: "8f9f1ea2-18ea-4d3d-bf7d-4ebaf2cb5e0e",
      project_id: projectIdDefault,
      title: "BC Omega Access Policy",
      slug: "operations/bc-omega-access-policy",
      entity_key: "bc_omega",
      page_type: "operations",
      status: "published",
      current_version: 2,
      created_at: "2026-03-31T09:00:00Z",
      updated_at: "2026-04-01T10:20:00Z",
    },
  ],
  wikiPageVersions: [
    {
      id: "ad6e31de-77f8-4b16-9df8-4ee9a50b5fbe",
      page_id: "8f9f1ea2-18ea-4d3d-bf7d-4ebaf2cb5e0e",
      version: 1,
      markdown: "# BC Omega Access Policy\n\n## Access Rules\n- Entry requires card after 10:00.\n",
      source: "human",
      created_by: "ops_manager",
      change_summary: "Initial publication",
      created_at: "2026-03-31T09:00:00Z",
    },
    {
      id: "2f56d7f6-2917-48f2-b52a-377b4508a196",
      page_id: "8f9f1ea2-18ea-4d3d-bf7d-4ebaf2cb5e0e",
      version: 2,
      markdown:
        "# BC Omega Access Policy\n\n## Access Rules\n- Entry requires card after 10:00.\n- Notify driver before dispatch.\n",
      source: "human",
      created_by: "qa_reviewer",
      change_summary: "Added driver notice",
      created_at: "2026-04-01T10:20:00Z",
    },
  ],
};

function sendJson(res, statusCode, payload, extraHeaders = {}) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Idempotency-Key,X-Synapse-Roles",
    ...extraHeaders,
  });
  res.end(JSON.stringify(payload));
}

function notFound(res) {
  sendJson(res, 404, { detail: "not_found" });
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      try {
        const raw = Buffer.concat(chunks).toString("utf-8").trim();
        resolve(raw ? JSON.parse(raw) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function nowIso() {
  return new Date().toISOString();
}

function toTaskObjectMetadata(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
}

function parseTaskDate(value) {
  if (value == null) {
    return null;
  }
  const parsed = new Date(String(value));
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("task_due_at_invalid");
  }
  return parsed.toISOString();
}

function normalizeTaskStatus(value, fallback = "todo") {
  const normalized = String(value || fallback).trim().toLowerCase();
  if (!TASK_STATUS_SET.has(normalized)) {
    throw new Error("task_status_invalid");
  }
  return normalized;
}

function normalizeTaskPriority(value, fallback = "normal") {
  const normalized = String(value || fallback).trim().toLowerCase();
  if (!TASK_PRIORITY_SET.has(normalized)) {
    throw new Error("task_priority_invalid");
  }
  return normalized;
}

function normalizeTaskSource(value, fallback = "human") {
  const normalized = String(value || fallback).trim().toLowerCase();
  if (!TASK_SOURCE_SET.has(normalized)) {
    throw new Error("task_source_invalid");
  }
  return normalized;
}

function normalizeTaskLinkType(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!TASK_LINK_TYPE_SET.has(normalized)) {
    throw new Error("task_link_type_invalid");
  }
  return normalized;
}

function cloneTaskRow(task) {
  return {
    ...task,
    metadata: toTaskObjectMetadata(task.metadata),
  };
}

function cloneTaskEventRow(event) {
  return {
    ...event,
    payload: toTaskObjectMetadata(event.payload),
  };
}

function cloneTaskLinkRow(link) {
  return {
    ...link,
    metadata: toTaskObjectMetadata(link.metadata),
  };
}

function compareTaskRows(a, b) {
  const aStatus = TASK_STATUS_ORDER[String(a.status || "").trim().toLowerCase()] ?? 99;
  const bStatus = TASK_STATUS_ORDER[String(b.status || "").trim().toLowerCase()] ?? 99;
  if (aStatus !== bStatus) {
    return aStatus - bStatus;
  }
  const aPriority = TASK_PRIORITY_ORDER[String(a.priority || "").trim().toLowerCase()] ?? 99;
  const bPriority = TASK_PRIORITY_ORDER[String(b.priority || "").trim().toLowerCase()] ?? 99;
  if (aPriority !== bPriority) {
    return aPriority - bPriority;
  }
  const aUpdated = String(a.updated_at || "");
  const bUpdated = String(b.updated_at || "");
  if (aUpdated !== bUpdated) {
    return bUpdated.localeCompare(aUpdated);
  }
  return String(a.id || "").localeCompare(String(b.id || ""));
}

function taskFieldEqual(left, right) {
  const leftIsObj = left && typeof left === "object" && !Array.isArray(left);
  const rightIsObj = right && typeof right === "object" && !Array.isArray(right);
  if (leftIsObj && rightIsObj) {
    return JSON.stringify(left) === JSON.stringify(right);
  }
  return left === right;
}

function appendTaskEvent({ taskId, projectId, eventType, actor = null, payload = {} }) {
  const event = {
    id: randomUUID(),
    task_id: String(taskId || ""),
    project_id: String(projectId || ""),
    event_type: String(eventType || ""),
    actor: actor == null ? null : String(actor || ""),
    payload: toTaskObjectMetadata(payload),
    created_at: nowIso(),
  };
  state.taskEvents.unshift(event);
  state.taskEvents = state.taskEvents.slice(0, 5000);
  return event;
}

function touchTaskRow(task, updatedBy = null) {
  const now = nowIso();
  task.updated_by = updatedBy == null ? task.updated_by : String(updatedBy || "").trim() || null;
  task.updated_at = now;
}

function findTaskIndex(taskId, projectId) {
  const normalizedTaskId = String(taskId || "").trim();
  const normalizedProjectId = String(projectId || "").trim();
  return state.tasks.findIndex(
    (item) =>
      String(item.id || "").trim() === normalizedTaskId && String(item.project_id || "").trim() === normalizedProjectId,
  );
}

function upsertTaskRow(payload) {
  const projectId = String(payload.project_id || "").trim();
  if (!projectId) {
    throw new Error("task_project_id_required");
  }
  const title = String(payload.title || "").trim();
  if (!title) {
    throw new Error("task_title_required");
  }
  const taskId = String(payload.task_id || "").trim() || randomUUID();
  const status = normalizeTaskStatus(payload.status, "todo");
  const priority = normalizeTaskPriority(payload.priority, "normal");
  const source = normalizeTaskSource(payload.source, "human");
  const dueAt = parseTaskDate(payload.due_at);
  const metadata = toTaskObjectMetadata(payload.metadata);
  const description = trimOptional(payload.description, 4000);
  const assignee = trimOptional(payload.assignee, 256);
  const entityKey = trimOptional(payload.entity_key, 256);
  const category = trimOptional(payload.category, 256);
  const createdBy = trimOptional(payload.created_by, 256);
  const updatedByRaw = trimOptional(payload.updated_by, 256);
  const updatedBy = updatedByRaw || createdBy;
  const now = nowIso();
  const idx = findTaskIndex(taskId, projectId);

  if (idx < 0) {
    const task = {
      id: taskId,
      project_id: projectId,
      title,
      description,
      status,
      priority,
      source,
      assignee,
      entity_key: entityKey,
      category,
      due_at: dueAt,
      created_by: createdBy,
      metadata,
      updated_by: updatedBy,
      created_at: now,
      updated_at: now,
    };
    state.tasks.push(task);
    appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "created",
      actor: createdBy,
      payload: { task: cloneTaskRow(task) },
    });
    return { status: "created", task: cloneTaskRow(task) };
  }

  const task = state.tasks[idx];
  const previous = cloneTaskRow(task);
  task.title = title;
  task.description = description;
  task.status = status;
  task.priority = priority;
  task.source = source;
  task.assignee = assignee;
  task.entity_key = entityKey;
  task.category = category;
  task.due_at = dueAt;
  task.metadata = metadata;
  task.updated_by = updatedBy;
  task.updated_at = now;

  const next = cloneTaskRow(task);
  const changed = {};
  for (const key of [
    "title",
    "description",
    "status",
    "priority",
    "source",
    "assignee",
    "entity_key",
    "category",
    "due_at",
    "metadata",
  ]) {
    if (!taskFieldEqual(previous[key], next[key])) {
      changed[key] = { from: previous[key], to: next[key] };
    }
  }

  const changedKeys = Object.keys(changed);
  if (changedKeys.length > 0) {
    appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "updated",
      actor: updatedBy,
      payload: { changes: changed },
    });
  }
  if (previous.status !== next.status) {
    appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "status_changed",
      actor: updatedBy,
      payload: {
        from: previous.status,
        to: next.status,
      },
    });
  }
  return { status: changedKeys.length > 0 ? "updated" : "noop", task: next };
}

function listTaskRows({
  projectId,
  status = null,
  assignee = null,
  entityKey = null,
  includeClosed = false,
  limit = 100,
}) {
  const normalizedProjectId = String(projectId || "").trim();
  const normalizedStatus = status == null ? null : String(status || "").trim().toLowerCase();
  const normalizedAssignee = assignee == null ? null : String(assignee || "").trim();
  const normalizedEntityKey = entityKey == null ? null : String(entityKey || "").trim().toLowerCase();
  const cap = Math.max(1, Math.min(500, Number(limit || 100)));

  return state.tasks
    .filter((item) => String(item.project_id || "").trim() === normalizedProjectId)
    .filter((item) => {
      const rowStatus = String(item.status || "").trim().toLowerCase();
      if (normalizedStatus != null) {
        return rowStatus === normalizedStatus;
      }
      if (!includeClosed && !TASK_ACTIVE_STATUS_SET.has(rowStatus)) {
        return false;
      }
      return true;
    })
    .filter((item) => {
      if (normalizedAssignee == null || !normalizedAssignee) {
        return true;
      }
      return String(item.assignee || "") === normalizedAssignee;
    })
    .filter((item) => {
      if (normalizedEntityKey == null || !normalizedEntityKey) {
        return true;
      }
      return String(item.entity_key || "").toLowerCase() === normalizedEntityKey;
    })
    .sort((a, b) => compareTaskRows(a, b))
    .slice(0, cap)
    .map((item) => cloneTaskRow(item));
}

function listTaskEvents(taskId, projectId, limit = 100) {
  const normalizedTaskId = String(taskId || "").trim();
  const normalizedProjectId = String(projectId || "").trim();
  const cap = Math.max(0, Math.min(500, Number(limit || 100)));
  if (cap === 0) {
    return [];
  }
  return state.taskEvents
    .filter(
      (item) =>
        String(item.task_id || "").trim() === normalizedTaskId &&
        String(item.project_id || "").trim() === normalizedProjectId,
    )
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, cap)
    .map((item) => cloneTaskEventRow(item));
}

function listTaskLinks(taskId, projectId, limit = 100) {
  const normalizedTaskId = String(taskId || "").trim();
  const normalizedProjectId = String(projectId || "").trim();
  const cap = Math.max(0, Math.min(500, Number(limit || 100)));
  if (cap === 0) {
    return [];
  }
  return state.taskLinks
    .filter(
      (item) =>
        String(item.task_id || "").trim() === normalizedTaskId &&
        String(item.project_id || "").trim() === normalizedProjectId,
    )
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, cap)
    .map((item) => cloneTaskLinkRow(item));
}

function normalizeWikiSlugSegment(value) {
  const normalized = String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized || "page";
}

function normalizeWikiSlug(rawSlug, fallbackTitle = "page") {
  const candidate = String(rawSlug || "").trim().replace(/\\/g, "/");
  if (!candidate) {
    return normalizeWikiSlugSegment(fallbackTitle);
  }
  const parts = candidate
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => normalizeWikiSlugSegment(part));
  if (parts.length === 0) {
    return normalizeWikiSlugSegment(fallbackTitle);
  }
  return parts.join("/");
}

function findWikiPageBySlug(projectId, slug) {
  const pid = String(projectId || "").trim();
  const target = String(slug || "").trim();
  return state.wikiPages.find(
    (item) => String(item.project_id || "").trim() === pid && String(item.slug || "").trim() === target,
  );
}

function listWikiPageVersions(pageId) {
  const pid = String(pageId || "").trim();
  return state.wikiPageVersions
    .filter((item) => String(item.page_id || "").trim() === pid)
    .sort((a, b) => Number(b.version || 0) - Number(a.version || 0));
}

function getQueueControl(projectId) {
  const existing = state.queueControls.find((item) => item.project_id === projectId);
  const now = Date.now();
  if (existing) {
    const pausedUntilMs = existing.paused_until ? new Date(existing.paused_until).getTime() : NaN;
    return {
      ...existing,
      pause_active: Number.isFinite(pausedUntilMs) && pausedUntilMs > now,
    };
  }
  return {
    project_id: projectId,
    paused_until: null,
    pause_reason: null,
    pause_active: false,
    worker_lag_sla_minutes: 20,
    queue_depth_warn: 12,
    incident_preflight_enforcement_mode: "off",
    incident_preflight_pause_hours: 4,
    incident_preflight_critical_fail_threshold: 1,
    updated_by: "system",
    created_at: null,
    updated_at: null,
  };
}

function upsertQueueControl(projectId, patch = {}) {
  const now = nowIso();
  const current = getQueueControl(projectId);
  const merged = {
    ...current,
    ...patch,
    project_id: projectId,
    worker_lag_sla_minutes: Math.max(1, Math.min(1440, Number(patch.worker_lag_sla_minutes ?? current.worker_lag_sla_minutes ?? 20))),
    queue_depth_warn: Math.max(1, Math.min(50000, Number(patch.queue_depth_warn ?? current.queue_depth_warn ?? 12))),
    incident_preflight_enforcement_mode: ["off", "block", "pause"].includes(
      String(patch.incident_preflight_enforcement_mode ?? current.incident_preflight_enforcement_mode ?? "off"),
    )
      ? String(patch.incident_preflight_enforcement_mode ?? current.incident_preflight_enforcement_mode ?? "off")
      : "off",
    incident_preflight_pause_hours: Math.max(
      1,
      Math.min(168, Number(patch.incident_preflight_pause_hours ?? current.incident_preflight_pause_hours ?? 4)),
    ),
    incident_preflight_critical_fail_threshold: Math.max(
      1,
      Math.min(
        100,
        Number(
          patch.incident_preflight_critical_fail_threshold ??
            current.incident_preflight_critical_fail_threshold ??
            1,
        ),
      ),
    ),
    updated_by: String(patch.updated_by ?? current.updated_by ?? "web_ui"),
    created_at: current.created_at || now,
    updated_at: now,
  };
  const pausedUntilMs = merged.paused_until ? new Date(merged.paused_until).getTime() : NaN;
  merged.pause_active = Number.isFinite(pausedUntilMs) && pausedUntilMs > Date.now();
  const idx = state.queueControls.findIndex((item) => item.project_id === projectId);
  if (idx >= 0) {
    state.queueControls[idx] = merged;
  } else {
    state.queueControls.push(merged);
  }
  return merged;
}

function appendQueueAuditEvent({ projectId, action, actor, reason, pausedUntil, payload = {} }) {
  const event = {
    id: state.queueAuditSeq,
    project_id: projectId,
    action: String(action || "unknown"),
    actor: String(actor || "web_ui"),
    reason: reason == null ? null : String(reason),
    paused_until: pausedUntil == null ? null : String(pausedUntil),
    payload: payload && typeof payload === "object" ? payload : {},
    created_at: nowIso(),
  };
  state.queueAuditSeq += 1;
  state.queueAuditEvents.unshift(event);
  state.queueAuditEvents = state.queueAuditEvents.slice(0, 1000);
  return event;
}

function appendQueueAuditAnnotation({ eventId, projectId, status, createdBy, note, followUpOwner }) {
  const annotation = {
    id: randomUUID(),
    event_id: Number(eventId),
    project_id: String(projectId || ""),
    status: String(status || "acknowledged"),
    note: note == null ? null : String(note),
    follow_up_owner: followUpOwner == null ? null : String(followUpOwner),
    created_by: String(createdBy || "web_ui"),
    created_at: nowIso(),
  };
  state.queueAuditAnnotations.unshift(annotation);
  state.queueAuditAnnotations = state.queueAuditAnnotations.slice(0, 5000);
  return annotation;
}

function latestQueueAuditAnnotation(eventId) {
  const key = Number(eventId);
  return (
    state.queueAuditAnnotations
      .filter((item) => Number(item.event_id) === key)
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0] || null
  );
}

function getQueueOwnership(projectId) {
  const existing = state.queueOwnerships.find((item) => item.project_id === projectId);
  if (existing) {
    return { ...existing };
  }
  return {
    project_id: projectId,
    owner_name: null,
    owner_contact: null,
    oncall_channel: null,
    escalation_channel: null,
    updated_by: "system",
    created_at: null,
    updated_at: null,
  };
}

function upsertQueueOwnership(projectId, patch = {}) {
  const now = nowIso();
  const current = getQueueOwnership(projectId);
  const merged = {
    ...current,
    ...patch,
    project_id: projectId,
    owner_name: patch.owner_name == null ? current.owner_name : String(patch.owner_name || "").trim() || null,
    owner_contact: patch.owner_contact == null ? current.owner_contact : String(patch.owner_contact || "").trim() || null,
    oncall_channel: patch.oncall_channel == null ? current.oncall_channel : String(patch.oncall_channel || "").trim() || null,
    escalation_channel:
      patch.escalation_channel == null ? current.escalation_channel : String(patch.escalation_channel || "").trim() || null,
    updated_by: String(patch.updated_by || current.updated_by || "web_ui"),
    created_at: current.created_at || now,
    updated_at: now,
  };
  const idx = state.queueOwnerships.findIndex((item) => item.project_id === projectId);
  if (idx >= 0) {
    state.queueOwnerships[idx] = merged;
  } else {
    state.queueOwnerships.push(merged);
  }
  return merged;
}

function normalizeIncidentOpenOnHealth(values) {
  const allowed = new Set(["healthy", "watch", "critical"]);
  const rows = Array.isArray(values) ? values : [];
  const out = [];
  for (const raw of rows) {
    const value = String(raw || "").trim().toLowerCase();
    if (!value || !allowed.has(value) || out.includes(value)) {
      continue;
    }
    out.push(value);
  }
  return out.length ? out : ["critical"];
}

function normalizeIncidentSecretRoles(values) {
  const rows = Array.isArray(values) ? values : INCIDENT_SECRET_EDIT_ROLES_DEFAULT;
  const out = [];
  for (const raw of rows) {
    const role = String(raw || "").trim().toLowerCase();
    if (!role || out.includes(role)) continue;
    out.push(role.slice(0, 64));
  }
  return out.length ? out.slice(0, 16) : [...INCIDENT_SECRET_EDIT_ROLES_DEFAULT];
}

function parseIncidentActorRoles(raw) {
  if (!raw) return new Set();
  return new Set(
    String(raw)
      .split(",")
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  );
}

function incidentProviderSecretKeys(provider) {
  if (provider === "pagerduty") return ["routing_key"];
  if (provider === "jira") return ["api_token"];
  return [];
}

function isIncidentSecretMask(value) {
  const text = String(value || "").trim();
  return text === INCIDENT_SECRET_MASK || text.toLowerCase() === "__unchanged__";
}

function isIncidentSecretClear(value) {
  return String(value || "").trim().toLowerCase() === INCIDENT_SECRET_CLEAR_TOKEN;
}

function canEditIncidentSecrets(requiredRoles, actorRoles) {
  const required = new Set((Array.isArray(requiredRoles) ? requiredRoles : []).map((item) => String(item || "").trim().toLowerCase()));
  if (required.size === 0) return true;
  if (actorRoles && actorRoles.size > 0) {
    for (const role of actorRoles) {
      if (required.has(role)) return true;
    }
    return false;
  }
  return INCIDENT_SECRET_RBAC_MODE !== "enforce";
}

function maskIncidentProviderConfig(provider, configRaw = {}, includeSecrets = false) {
  const config = normalizeIncidentProviderConfig(provider, configRaw);
  if (includeSecrets) return config;
  for (const key of incidentProviderSecretKeys(provider)) {
    const value = String(config[key] || "").trim();
    config[key] = value ? INCIDENT_SECRET_MASK : null;
  }
  return config;
}

function resolveIncidentProviderConfigSecrets(provider, incomingConfigRaw, existingConfigRaw) {
  const incoming = normalizeIncidentProviderConfig(provider, incomingConfigRaw || {});
  const existing = normalizeIncidentProviderConfig(provider, existingConfigRaw || {});
  let secretChanged = false;
  for (const key of incidentProviderSecretKeys(provider)) {
    const nextValue = incoming[key];
    const currentValue = existing[key];
    if (nextValue == null || isIncidentSecretMask(nextValue)) {
      incoming[key] = currentValue ?? null;
      continue;
    }
    if (isIncidentSecretClear(nextValue)) {
      if (currentValue) secretChanged = true;
      incoming[key] = null;
      continue;
    }
    if (String(nextValue || "") !== String(currentValue || "")) {
      secretChanged = true;
    }
  }
  return { providerConfig: incoming, secretChanged };
}

function normalizeIncidentProvider(value) {
  const provider = String(value || "webhook")
    .trim()
    .toLowerCase();
  if (["webhook", "pagerduty", "jira"].includes(provider)) {
    return provider;
  }
  throw new Error("incident_provider_unsupported");
}

function trimOptional(value, maxLen) {
  const text = String(value || "").trim();
  if (!text) return null;
  return text.slice(0, Math.max(1, Number(maxLen || 1)));
}

function normalizeIncidentProviderConfig(provider, configRaw = {}) {
  const raw = configRaw && typeof configRaw === "object" && !Array.isArray(configRaw) ? configRaw : {};
  if (provider === "webhook") {
    const headers = {};
    const src = raw.headers && typeof raw.headers === "object" && !Array.isArray(raw.headers) ? raw.headers : {};
    for (const [key, value] of Object.entries(src)) {
      const name = trimOptional(key, 128);
      const headerValue = trimOptional(value, 2048);
      if (!name || !headerValue) continue;
      headers[name] = headerValue;
    }
    return { headers };
  }
  if (provider === "pagerduty") {
    return {
      routing_key: trimOptional(raw.routing_key, 512),
      source: trimOptional(raw.source, 256) || "synapse",
      component: trimOptional(raw.component, 256),
      group: trimOptional(raw.group, 256),
      class: trimOptional(raw.class, 256) || "queue-operations",
      dedup_key_prefix: trimOptional(raw.dedup_key_prefix, 256) || "synapse-queue",
      incident_url_template: trimOptional(raw.incident_url_template, 2048),
      severity_by_health: {
        healthy: "warning",
        watch: "warning",
        critical: "critical",
        ...(raw.severity_by_health && typeof raw.severity_by_health === "object" && !Array.isArray(raw.severity_by_health)
          ? raw.severity_by_health
          : {}),
      },
    };
  }
  if (provider === "jira") {
    const labels = Array.isArray(raw.labels)
      ? raw.labels
          .map((item) => trimOptional(item, 64))
          .filter(Boolean)
          .slice(0, 12)
      : [];
    return {
      base_url: (trimOptional(raw.base_url, 2048) || "").replace(/\/+$/, "") || null,
      project_key: trimOptional(raw.project_key, 64),
      issue_type: trimOptional(raw.issue_type, 128) || "Incident",
      auth_mode: ["basic", "bearer"].includes(String(raw.auth_mode || "").toLowerCase())
        ? String(raw.auth_mode || "").toLowerCase()
        : "basic",
      email: trimOptional(raw.email, 256),
      api_token: trimOptional(raw.api_token, 2048),
      resolve_transition_id: trimOptional(raw.resolve_transition_id, 64),
      title_prefix: trimOptional(raw.title_prefix, 256) || "[Synapse Queue]",
      labels,
      browse_url_template: trimOptional(raw.browse_url_template, 2048),
      priority_by_health:
        raw.priority_by_health && typeof raw.priority_by_health === "object" && !Array.isArray(raw.priority_by_health)
          ? raw.priority_by_health
          : {},
    };
  }
  return {};
}

function validateIncidentHookRequirements({
  provider,
  enabled,
  autoResolve,
  openWebhookUrl,
  resolveWebhookUrl,
  providerConfig,
}) {
  if (!enabled) return;
  if (provider === "webhook" && !openWebhookUrl) {
    throw new Error("incident_open_webhook_url_required");
  }
  if (provider === "pagerduty" && !String(providerConfig?.routing_key || "").trim()) {
    throw new Error("pagerduty_routing_key_required");
  }
  if (provider === "jira") {
    if (!String(providerConfig?.base_url || "").trim()) throw new Error("jira_base_url_required");
    if (!String(providerConfig?.project_key || "").trim()) throw new Error("jira_project_key_required");
    if (!String(providerConfig?.api_token || "").trim()) throw new Error("jira_api_token_required");
    if (String(providerConfig?.auth_mode || "basic") === "basic" && !String(providerConfig?.email || "").trim()) {
      throw new Error("jira_email_required");
    }
    if (autoResolve && !String(providerConfig?.resolve_transition_id || "").trim() && !resolveWebhookUrl) {
      throw new Error("jira_resolve_transition_or_webhook_required");
    }
  }
}

function normalizeIncidentSeverityByHealth(values) {
  if (!values || typeof values !== "object" || Array.isArray(values)) {
    return {};
  }
  const out = {};
  for (const key of ["healthy", "watch", "critical"]) {
    const value = trimOptional(values[key], 64);
    if (!value) continue;
    out[key] = value;
  }
  return out;
}

function normalizeIncidentOpenOnHealthOptional(values) {
  if (!Array.isArray(values)) return [];
  const allowed = new Set(["healthy", "watch", "critical"]);
  const out = [];
  for (const raw of values) {
    const value = String(raw || "").trim().toLowerCase();
    if (!value || !allowed.has(value) || out.includes(value)) continue;
    out.push(value);
  }
  return out;
}

function listQueueIncidentPolicies(projectIdsRaw, limit = 500, singleProject = "", includeSecrets = false, actorRoles = new Set()) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedCsv] : requestedCsv;
  const dedupRequested = requested.filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
  const rows = state.queueIncidentPolicies.filter((item) => {
    if (dedupRequested.length > 0 && !dedupRequested.includes(String(item.project_id || ""))) {
      return false;
    }
    return true;
  });
  return rows
    .sort((a, b) => {
      if (String(a.project_id || "") !== String(b.project_id || "")) {
        return String(a.project_id || "").localeCompare(String(b.project_id || ""));
      }
      const aprio = Number(a.priority || 100);
      const bprio = Number(b.priority || 100);
      if (aprio !== bprio) return aprio - bprio;
      return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
    })
    .slice(0, Math.max(1, Math.min(1000, Number(limit || 500))))
    .map((item) => {
      const provider = item.provider_override ? normalizeIncidentProvider(item.provider_override) : null;
      const secretEditRoles = normalizeIncidentSecretRoles(item.secret_edit_roles);
      return {
        ...item,
        provider_config_override: provider
          ? maskIncidentProviderConfig(provider, item.provider_config_override || {}, includeSecrets)
          : {},
        secret_edit_roles: secretEditRoles,
        secret_access: {
          required_roles: secretEditRoles,
          can_edit: canEditIncidentSecrets(secretEditRoles, actorRoles),
        },
        provider_config_override_secret_keys: provider
          ? incidentProviderSecretKeys(provider).filter((key) => Boolean(item.provider_config_override?.[key]))
          : [],
      };
    });
}

function policiesByProject(projectId) {
  return listQueueIncidentPolicies(projectId, 200, projectId, true);
}

function upsertQueueIncidentPolicy(projectId, patch = {}, actorRoles = new Set()) {
  const now = nowIso();
  const alertCode = String(patch.alert_code || "").trim().toLowerCase().slice(0, 128);
  if (!alertCode) throw new Error("incident_policy_alert_code_required");
  const current = state.queueIncidentPolicies.find(
    (item) => String(item.project_id || "") === projectId && String(item.alert_code || "") === alertCode,
  );
  const secretEditRoles = normalizeIncidentSecretRoles(patch.secret_edit_roles ?? current?.secret_edit_roles);
  const providerOverrideRaw = trimOptional(patch.provider_override, 32);
  const providerOverride = providerOverrideRaw ? normalizeIncidentProvider(providerOverrideRaw) : null;
  let providerConfigOverride = providerOverride
    ? normalizeIncidentProviderConfig(providerOverride, patch.provider_config_override || {})
    : {};
  let secretChanged = false;
  if (providerOverride) {
    const resolved = resolveIncidentProviderConfigSecrets(
      providerOverride,
      patch.provider_config_override || {},
      current?.provider_override === providerOverride ? current?.provider_config_override || {} : {},
    );
    providerConfigOverride = resolved.providerConfig;
    secretChanged = resolved.secretChanged;
  }
  if (!providerOverride && patch.provider_config_override && Object.keys(patch.provider_config_override || {}).length > 0) {
    throw new Error("incident_policy_provider_override_required");
  }
  if (secretChanged && !canEditIncidentSecrets(secretEditRoles, actorRoles)) {
    throw new Error("incident_secret_edit_forbidden");
  }
  const merged = {
    id: randomUUID(),
    project_id: projectId,
    alert_code: alertCode,
    enabled: Boolean(patch.enabled ?? true),
    priority: Math.max(1, Math.min(1000, Number(patch.priority || 100))),
    provider_override: providerOverride,
    open_webhook_url: trimOptional(patch.open_webhook_url, 2048),
    resolve_webhook_url: trimOptional(patch.resolve_webhook_url, 2048),
    provider_config_override: providerConfigOverride,
    secret_edit_roles: secretEditRoles,
    severity_by_health: normalizeIncidentSeverityByHealth(patch.severity_by_health),
    open_on_health: normalizeIncidentOpenOnHealthOptional(patch.open_on_health),
    updated_by: trimOptional(patch.updated_by, 256) || "web_ui",
    created_at: now,
    updated_at: now,
  };
  const idx = state.queueIncidentPolicies.findIndex(
    (item) => String(item.project_id || "") === projectId && String(item.alert_code || "") === alertCode,
  );
  if (idx >= 0) {
    merged.id = state.queueIncidentPolicies[idx].id;
    merged.created_at = state.queueIncidentPolicies[idx].created_at || now;
    state.queueIncidentPolicies[idx] = merged;
  } else {
    state.queueIncidentPolicies.push(merged);
  }
  return { ...merged };
}

function normalizeIncidentAlertCode(value) {
  const code = String(value || "").trim().toLowerCase().slice(0, 128);
  if (!code) throw new Error("incident_policy_alert_code_required");
  return code;
}

function normalizeIncidentPreflightPresetKey(value, fallback = "preset") {
  let text = String(value || "").trim().toLowerCase();
  if (!text) text = String(fallback || "preset").trim().toLowerCase();
  let normalized = text.replace(/[^a-z0-9._-]+/g, "-");
  normalized = normalized.replace(/^-+/, "").replace(/-+$/, "");
  normalized = normalized.replace(/-{2,}/g, "-");
  if (!normalized) throw new Error("incident_preflight_preset_key_required");
  return normalized.slice(0, 128);
}

function normalizeIncidentPreflightExpectedDecision(value) {
  const decision = String(value || "open").trim().toLowerCase();
  if (!["open", "skip", "invalid_ok"].includes(decision)) {
    throw new Error("incident_preflight_expected_decision_invalid");
  }
  return decision;
}

function normalizeIncidentPreflightSeverity(value) {
  const severity = String(value || "warning").trim().toLowerCase();
  if (!["info", "warning", "critical"].includes(severity)) {
    throw new Error("incident_preflight_severity_invalid");
  }
  return severity;
}

function normalizeIncidentPreflightRequiredProvider(value) {
  if (value == null) return null;
  const raw = String(value || "").trim().toLowerCase();
  if (!raw || ["inherit", "none", "null"].includes(raw)) {
    return null;
  }
  return normalizeIncidentProvider(raw);
}

function normalizeIncidentPreflightAlertCodes(primary, additional = []) {
  const out = [normalizeIncidentAlertCode(primary)];
  for (const item of Array.isArray(additional) ? additional : []) {
    const code = normalizeIncidentAlertCode(item);
    if (!out.includes(code)) out.push(code);
  }
  return out;
}

function listQueueIncidentPreflightPresets({
  projectIdsRaw = "",
  projectId = "",
  presetIds = [],
  includeDisabled = true,
  includeRunBeforeLiveSyncOnly = false,
  limit = 1000,
} = {}) {
  const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIdsRaw)]
    .map((item) => String(item || "").trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
  const presetFilter = (Array.isArray(presetIds) ? presetIds : [])
    .map((item) => String(item || "").trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
  const severityRank = { critical: 0, warning: 1, info: 2 };
  return state.queueIncidentPreflightPresets
    .filter((item) => {
      const itemProject = String(item.project_id || "");
      const itemId = String(item.id || "");
      if (requested.length > 0 && !requested.includes(itemProject)) return false;
      if (presetFilter.length > 0 && !presetFilter.includes(itemId)) return false;
      if (!includeDisabled && !Boolean(item.enabled)) return false;
      if (includeRunBeforeLiveSyncOnly && !Boolean(item.run_before_live_sync)) return false;
      return true;
    })
    .sort((a, b) => {
      const aproj = String(a.project_id || "");
      const bproj = String(b.project_id || "");
      if (aproj !== bproj) return aproj.localeCompare(bproj);
      if (Boolean(a.enabled) !== Boolean(b.enabled)) return Boolean(a.enabled) ? -1 : 1;
      if (Boolean(a.run_before_live_sync) !== Boolean(b.run_before_live_sync)) return Boolean(a.run_before_live_sync) ? -1 : 1;
      const as = severityRank[normalizeIncidentPreflightSeverity(a.severity)] ?? 10;
      const bs = severityRank[normalizeIncidentPreflightSeverity(b.severity)] ?? 10;
      if (as !== bs) return as - bs;
      const at = String(a.updated_at || "");
      const bt = String(b.updated_at || "");
      if (at !== bt) return bt.localeCompare(at);
      return String(a.preset_key || "").localeCompare(String(b.preset_key || ""));
    })
    .slice(0, Math.max(1, Math.min(5000, Number(limit || 1000))))
    .map((item) => ({
      id: String(item.id || ""),
      project_id: String(item.project_id || ""),
      preset_key: String(item.preset_key || ""),
      name: String(item.name || ""),
      enabled: Boolean(item.enabled),
      alert_code: normalizeIncidentAlertCode(item.alert_code),
      health: ["healthy", "watch", "critical"].includes(String(item.health || "").toLowerCase())
        ? String(item.health || "").toLowerCase()
        : "critical",
      additional_alert_codes: (Array.isArray(item.additional_alert_codes) ? item.additional_alert_codes : [])
        .map((code) => normalizeIncidentAlertCode(code))
        .filter((code, index, all) => all.indexOf(code) === index),
      expected_decision: normalizeIncidentPreflightExpectedDecision(item.expected_decision),
      required_provider: normalizeIncidentPreflightRequiredProvider(item.required_provider),
      run_before_live_sync: Boolean(item.run_before_live_sync),
      severity: normalizeIncidentPreflightSeverity(item.severity),
      strict_mode: Boolean(item.strict_mode),
      metadata:
        item.metadata && typeof item.metadata === "object" && !Array.isArray(item.metadata)
          ? item.metadata
          : {},
      updated_by: String(item.updated_by || "web_ui"),
      created_at: item.created_at || null,
      updated_at: item.updated_at || null,
    }));
}

function upsertQueueIncidentPreflightPreset(projectId, patch = {}) {
  const now = nowIso();
  const alertCodes = normalizeIncidentPreflightAlertCodes(
    patch.alert_code,
    Array.isArray(patch.additional_alert_codes) ? patch.additional_alert_codes : [],
  );
  const health = String(patch.health || "critical").trim().toLowerCase();
  if (!["healthy", "watch", "critical"].includes(health)) throw new Error("incident_health_unsupported");
  const expectedDecision = normalizeIncidentPreflightExpectedDecision(patch.expected_decision);
  const requiredProvider = normalizeIncidentPreflightRequiredProvider(patch.required_provider);
  const severity = normalizeIncidentPreflightSeverity(patch.severity);
  const normalizedName = String(patch.name || "").trim().slice(0, 256);
  if (!normalizedName) throw new Error("incident_preflight_name_required");
  const presetKey = normalizeIncidentPreflightPresetKey(patch.preset_key, `${alertCodes[0]}-${health}`);
  const metadata = patch.metadata && typeof patch.metadata === "object" && !Array.isArray(patch.metadata) ? patch.metadata : {};
  const idx = state.queueIncidentPreflightPresets.findIndex(
    (item) => String(item.project_id || "") === projectId && String(item.preset_key || "") === presetKey,
  );
  const current = idx >= 0 ? state.queueIncidentPreflightPresets[idx] : null;
  const merged = {
    id: current?.id || randomUUID(),
    project_id: projectId,
    preset_key: presetKey,
    name: normalizedName,
    enabled: Boolean(patch.enabled ?? true),
    alert_code: alertCodes[0],
    health,
    additional_alert_codes: alertCodes.slice(1),
    expected_decision: expectedDecision,
    required_provider: requiredProvider,
    run_before_live_sync: Boolean(patch.run_before_live_sync ?? true),
    severity,
    strict_mode: Boolean(patch.strict_mode ?? true),
    metadata,
    updated_by: String(patch.updated_by || "web_ui").trim().slice(0, 256) || "web_ui",
    created_at: current?.created_at || now,
    updated_at: now,
  };
  if (idx >= 0) {
    state.queueIncidentPreflightPresets[idx] = merged;
  } else {
    state.queueIncidentPreflightPresets.push(merged);
  }
  return { ...merged };
}

function suggestIncidentPreflightRecommendation(reason) {
  if (reason === "simulation_invalid") {
    return "Review incident hook/provider configuration and required secrets before live sync.";
  }
  if (reason === "expected_open_but_skipped") {
    return "Check policy priority or open_on_health so critical signals route to incident opening.";
  }
  if (reason === "expected_skip_but_opened") {
    return "Tighten policy open_on_health and alert routing to avoid undesired ticket storms.";
  }
  if (reason === "expected_invalid_but_valid") {
    return "Preset expects invalid route; update expectation or deliberately enforce stricter hook validation.";
  }
  if (reason === "required_provider_mismatch") {
    return "Align provider override/hook provider with preflight required provider.";
  }
  return "Inspect simulation route trace and policy ordering for this alert.";
}

function evaluateQueueIncidentPreflightCheck({ preset, simulation }) {
  const expected = normalizeIncidentPreflightExpectedDecision(preset.expected_decision);
  const requiredProvider = normalizeIncidentPreflightRequiredProvider(preset.required_provider);
  const strictMode = Boolean(preset.strict_mode);
  const simStatus = String(simulation?.status || "invalid");
  const decision = simulation && typeof simulation.decision === "object" ? simulation.decision : {};
  const shouldOpen = Boolean(decision.should_open_incident);
  const skipReason = decision.skip_reason == null ? null : String(decision.skip_reason);
  const effectiveHook = simulation && typeof simulation.effective_hook === "object" ? simulation.effective_hook : {};
  const providerAfter = normalizeIncidentProvider(effectiveHook.provider || "webhook");
  const failReasons = [];

  if (requiredProvider != null && providerAfter !== requiredProvider) failReasons.push("required_provider_mismatch");
  if (expected === "open" && !shouldOpen) failReasons.push("expected_open_but_skipped");
  if (expected === "skip" && shouldOpen) failReasons.push("expected_skip_but_opened");
  if (expected === "invalid_ok") {
    if (simStatus !== "invalid") failReasons.push("expected_invalid_but_valid");
  } else if (strictMode && simStatus !== "ok") {
    failReasons.push("simulation_invalid");
  }

  const passed = failReasons.length === 0;
  const severity = normalizeIncidentPreflightSeverity(preset.severity);
  const firstReason = failReasons.length > 0 ? failReasons[0] : null;
  return {
    preset_id: String(preset.id || ""),
    project_id: String(preset.project_id || ""),
    preset_key: String(preset.preset_key || ""),
    preset_name: String(preset.name || ""),
    enabled: Boolean(preset.enabled),
    run_before_live_sync: Boolean(preset.run_before_live_sync),
    alert_code: String(preset.alert_code || ""),
    health: String(preset.health || "critical"),
    additional_alert_codes: Array.isArray(preset.additional_alert_codes) ? preset.additional_alert_codes : [],
    expected_decision: expected,
    required_provider: requiredProvider,
    severity,
    strict_mode: strictMode,
    status: passed ? "passed" : "failed",
    fail_reasons: failReasons,
    recommendation: passed || firstReason == null ? null : suggestIncidentPreflightRecommendation(firstReason),
    simulation: {
      status: simStatus,
      decision: {
        should_open_incident: shouldOpen,
        skip_reason: skipReason,
      },
      provider_after_policy: providerAfter,
      provider_before_policy: simulation?.route_trace?.provider_before_policy || null,
      matched_policy_id: simulation?.route_trace?.matched_policy_id || null,
      matched_policy_alert_code: simulation?.route_trace?.matched_policy_alert_code || null,
      generated_at: simulation?.generated_at || null,
    },
  };
}

function runQueueIncidentPreflightChecks({
  projectIds = [],
  presetIds = [],
  includeDisabled = false,
  includeRunBeforeLiveSyncOnly = true,
  actor = "web_ui",
  actorRoles = new Set(),
  recordAudit = true,
  limit = 100,
} = {}) {
  const requestedProjects = (Array.isArray(projectIds) ? projectIds : [])
    .map((item) => String(item || "").trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index)
    .slice(0, Math.max(1, Math.min(200, Number(limit || 100))));
  const presetIdFilter = (Array.isArray(presetIds) ? presetIds : [])
    .map((item) => String(item || "").trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);

  const presets = listQueueIncidentPreflightPresets({
    projectIdsRaw: requestedProjects.join(","),
    presetIds: presetIdFilter,
    includeDisabled,
    includeRunBeforeLiveSyncOnly,
    limit: Math.max(200, Math.min(5000, Number(limit || 100) * 20)),
  });

  const targets = [...requestedProjects];
  for (const preset of presets) {
    const projectId = String(preset.project_id || "").trim();
    if (projectId && !targets.includes(projectId)) {
      targets.push(projectId);
    }
  }
  if (targets.length === 0) {
    const fallbackProjects = [...new Set(state.schedules.map((item) => String(item.project_id || "").trim()).filter(Boolean))];
    for (const projectId of fallbackProjects.slice(0, Math.max(1, Math.min(200, Number(limit || 100))))) {
      targets.push(projectId);
    }
  }

  const grouped = new Map();
  for (const preset of presets) {
    const projectId = String(preset.project_id || "").trim();
    if (!projectId) continue;
    if (!grouped.has(projectId)) grouped.set(projectId, []);
    grouped.get(projectId).push(preset);
  }

  const checks = [];
  const bySeverity = { info: 0, warning: 0, critical: 0 };
  const projectRollups = [];
  for (const projectId of grouped.keys()) {
    const rows = grouped.get(projectId) || [];
    const rollup = {
      project_id: projectId,
      checks_total: 0,
      passed: 0,
      failed: 0,
      critical_alerts: 0,
      warning_alerts: 0,
      info_alerts: 0,
    };
    for (const preset of rows) {
      const simulation = simulateIncidentPolicyRoute({
        projectId,
        alertCode: String(preset.alert_code || ""),
        health: String(preset.health || "critical"),
        additionalAlertCodes: Array.isArray(preset.additional_alert_codes) ? preset.additional_alert_codes : [],
        includeSecrets: false,
        actor,
        actorRoles,
        appendAuditEvent: false,
      });
      const check = evaluateQueueIncidentPreflightCheck({ preset, simulation });
      checks.push(check);
      rollup.checks_total += 1;
      if (check.status === "passed") {
        rollup.passed += 1;
      } else {
        rollup.failed += 1;
        const severity = normalizeIncidentPreflightSeverity(check.severity);
        bySeverity[severity] += 1;
        if (severity === "critical") rollup.critical_alerts += 1;
        else if (severity === "warning") rollup.warning_alerts += 1;
        else rollup.info_alerts += 1;
        if (recordAudit) {
          appendQueueAuditEvent({
            projectId,
            action: "incident_preflight_alert",
            actor: String(actor || "web_ui"),
            reason: `preflight:${check.preset_key}:${(Array.isArray(check.fail_reasons) ? check.fail_reasons.join(",") : "").slice(0, 128)}`.slice(
              0,
              2000,
            ),
            pausedUntil: null,
            payload: {
              preset_id: check.preset_id,
              preset_key: check.preset_key,
              preset_name: check.preset_name,
              expected_decision: check.expected_decision,
              fail_reasons: check.fail_reasons,
              severity,
              provider_after_policy: check.simulation?.provider_after_policy || null,
              skip_reason: check.simulation?.decision?.skip_reason || null,
            },
          });
        }
      }
    }
    projectRollups.push(rollup);
    if (recordAudit && rollup.checks_total > 0) {
      appendQueueAuditEvent({
        projectId,
        action: "incident_preflight_run",
        actor: String(actor || "web_ui"),
        reason: "queue_incident_preflight_run",
        pausedUntil: null,
        payload: {
          checks_total: rollup.checks_total,
          passed: rollup.passed,
          failed: rollup.failed,
          critical_alerts: rollup.critical_alerts,
          warning_alerts: rollup.warning_alerts,
          info_alerts: rollup.info_alerts,
        },
      });
    }
  }

  const severityRank = { critical: 0, warning: 1, info: 2 };
  checks.sort((a, b) => {
    const aFailed = String(a.status || "") === "failed";
    const bFailed = String(b.status || "") === "failed";
    if (aFailed !== bFailed) return aFailed ? -1 : 1;
    const as = severityRank[String(a.severity || "warning")] ?? 10;
    const bs = severityRank[String(b.severity || "warning")] ?? 10;
    if (as !== bs) return as - bs;
    if (String(a.project_id || "") !== String(b.project_id || "")) {
      return String(a.project_id || "").localeCompare(String(b.project_id || ""));
    }
    return String(a.preset_key || "").localeCompare(String(b.preset_key || ""));
  });
  projectRollups.sort((a, b) => {
    if (a.failed !== b.failed) return b.failed - a.failed;
    if (a.critical_alerts !== b.critical_alerts) return b.critical_alerts - a.critical_alerts;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });

  const summary = {
    projects_total: projectRollups.length,
    presets_total: presets.length,
    checks_total: checks.length,
    passed: checks.filter((item) => String(item.status || "") === "passed").length,
    failed: checks.filter((item) => String(item.status || "") === "failed").length,
    alerts_total: Number(bySeverity.info || 0) + Number(bySeverity.warning || 0) + Number(bySeverity.critical || 0),
    alerts_by_severity: bySeverity,
  };
  const alerts = checks.filter((item) => String(item.status || "") === "failed");
  return {
    requested_projects: requestedProjects,
    preset_ids: presetIdFilter,
    include_disabled: Boolean(includeDisabled),
    include_run_before_live_sync_only: Boolean(includeRunBeforeLiveSyncOnly),
    record_audit: Boolean(recordAudit),
    generated_at: nowIso(),
    summary,
    project_rollups: projectRollups,
    alerts: alerts.slice(0, 200),
    results: checks.slice(0, 1000),
  };
}

function resolveIncidentHookPolicy(hook, policies, health, alertCodes, options = {}) {
  const normalizedAlerts = new Set(
    (Array.isArray(alertCodes) ? alertCodes : [])
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  );
  const matched = (Array.isArray(policies) ? policies : [])
    .filter((item) => item && item.enabled && normalizedAlerts.has(String(item.alert_code || "").trim().toLowerCase()))
    .sort((a, b) => Number(a.priority || 100) - Number(b.priority || 100))[0];
  if (!matched) {
    return { hook, matchedPolicy: null };
  }
  const baseProvider = normalizeIncidentProvider(hook.provider);
  const provider = matched.provider_override ? normalizeIncidentProvider(matched.provider_override) : baseProvider;
  const baseConfig = provider === baseProvider ? normalizeIncidentProviderConfig(provider, hook.provider_config || {}) : {};
  const overrideConfig = normalizeIncidentProviderConfig(provider, matched.provider_config_override || {});
  const providerConfig = { ...baseConfig, ...overrideConfig };
  const severity = normalizeIncidentSeverityByHealth(matched.severity_by_health);
  if (Object.keys(severity).length > 0) {
    if (provider === "pagerduty") {
      providerConfig.severity_by_health = { ...(providerConfig.severity_by_health || {}), ...severity };
    } else if (provider === "jira") {
      providerConfig.priority_by_health = { ...(providerConfig.priority_by_health || {}), ...severity };
    } else {
      providerConfig.severity_by_health = severity;
    }
  }
  const effectiveHook = {
    ...hook,
    provider,
    provider_config: normalizeIncidentProviderConfig(provider, providerConfig),
    open_webhook_url: matched.open_webhook_url || hook.open_webhook_url,
    resolve_webhook_url: matched.resolve_webhook_url || hook.resolve_webhook_url,
    open_on_health: matched.open_on_health && matched.open_on_health.length > 0 ? matched.open_on_health : hook.open_on_health,
    matched_policy_id: matched.id,
    matched_policy_alert_code: matched.alert_code,
  };
  if (options.validate !== false) {
    validateIncidentHookRequirements({
      provider,
      enabled: Boolean(effectiveHook.enabled),
      autoResolve: Boolean(effectiveHook.auto_resolve),
      openWebhookUrl: effectiveHook.open_webhook_url,
      resolveWebhookUrl: effectiveHook.resolve_webhook_url,
      providerConfig: effectiveHook.provider_config,
    });
  }
  return { hook: effectiveHook, matchedPolicy: { ...matched } };
}

function simulateIncidentPolicyRoute({
  projectId,
  alertCode,
  health = "critical",
  additionalAlertCodes = [],
  includeSecrets = false,
  actor = "web_ui",
  actorRoles = new Set(),
  appendAuditEvent = true,
}) {
  const normalizedAlertCode = String(alertCode || "").trim().toLowerCase().slice(0, 128);
  if (!normalizedAlertCode) throw new Error("incident_policy_alert_code_required");
  const normalizedHealth = String(health || "critical").trim().toLowerCase();
  if (!["healthy", "watch", "critical"].includes(normalizedHealth)) throw new Error("incident_health_unsupported");
  const hook = getQueueIncidentHook(projectId);
  const policyRows = listQueueIncidentPolicies(projectId, 500, projectId, true, actorRoles);
  const alertCodes = [normalizedAlertCode];
  for (const rawCode of Array.isArray(additionalAlertCodes) ? additionalAlertCodes : []) {
    const normalized = String(rawCode || "").trim().toLowerCase().slice(0, 128);
    if (!normalized || alertCodes.includes(normalized)) continue;
    alertCodes.push(normalized);
  }
  const { hook: effectiveHook, matchedPolicy } = resolveIncidentHookPolicy(
    hook,
    policyRows,
    normalizedHealth,
    alertCodes,
    { validate: false },
  );
  const provider = normalizeIncidentProvider(effectiveHook.provider);
  const providerConfig = normalizeIncidentProviderConfig(provider, effectiveHook.provider_config || {});
  const openOnHealth = normalizeIncidentOpenOnHealth(effectiveHook.open_on_health);
  const shouldOpen = openOnHealth.includes(normalizedHealth);
  let validationError = null;
  try {
    validateIncidentHookRequirements({
      provider,
      enabled: Boolean(effectiveHook.enabled),
      autoResolve: Boolean(effectiveHook.auto_resolve),
      openWebhookUrl: effectiveHook.open_webhook_url,
      resolveWebhookUrl: effectiveHook.resolve_webhook_url,
      providerConfig,
    });
  } catch (error) {
    validationError = error instanceof Error ? error.message : String(error);
  }
  const hookSecretRoles = normalizeIncidentSecretRoles(effectiveHook.secret_edit_roles);
  const matchedPolicySecretRoles = normalizeIncidentSecretRoles(matchedPolicy?.secret_edit_roles);
  const canIncludeHookSecrets = Boolean(includeSecrets && canEditIncidentSecrets(hookSecretRoles, actorRoles));
  const canIncludePolicySecrets = Boolean(
    includeSecrets && (!matchedPolicy || canEditIncidentSecrets(matchedPolicySecretRoles, actorRoles)),
  );
  const includeSecretsEffective = Boolean(canIncludeHookSecrets && canIncludePolicySecrets);
  const maskedProviderConfig = maskIncidentProviderConfig(provider, providerConfig, includeSecretsEffective);
  let matchedPolicyResponse = null;
  if (matchedPolicy) {
    const policyProvider = matchedPolicy.provider_override ? normalizeIncidentProvider(matchedPolicy.provider_override) : null;
    const policyConfigOverride =
      policyProvider == null
        ? {}
        : maskIncidentProviderConfig(
            policyProvider,
            normalizeIncidentProviderConfig(policyProvider, matchedPolicy.provider_config_override || {}),
            Boolean(includeSecrets && canIncludePolicySecrets),
          );
    matchedPolicyResponse = {
      id: matchedPolicy.id || null,
      project_id: String(matchedPolicy.project_id || projectId),
      alert_code: String(matchedPolicy.alert_code || ""),
      enabled: Boolean(matchedPolicy.enabled),
      priority: Math.max(1, Math.min(1000, Number(matchedPolicy.priority || 100))),
      provider_override: policyProvider,
      open_webhook_url: trimOptional(matchedPolicy.open_webhook_url, 2048),
      resolve_webhook_url: trimOptional(matchedPolicy.resolve_webhook_url, 2048),
      provider_config_override: policyConfigOverride,
      severity_by_health: normalizeIncidentSeverityByHealth(matchedPolicy.severity_by_health),
      open_on_health: normalizeIncidentOpenOnHealthOptional(matchedPolicy.open_on_health),
      secret_edit_roles: matchedPolicySecretRoles,
      secret_access: {
        required_roles: matchedPolicySecretRoles,
        can_edit: canEditIncidentSecrets(matchedPolicySecretRoles, actorRoles),
      },
      provider_config_override_secret_keys: Array.isArray(matchedPolicy.provider_config_override_secret_keys)
        ? matchedPolicy.provider_config_override_secret_keys
        : [],
      updated_by: String(matchedPolicy.updated_by || "web_ui"),
      created_at: matchedPolicy.created_at || null,
      updated_at: matchedPolicy.updated_at || null,
    };
  }
  const alertCodeSet = new Set(alertCodes);
  const traceCandidates = policyRows
    .filter((item) => alertCodeSet.has(String(item.alert_code || "").trim().toLowerCase()))
    .map((item) => ({
      id: item.id || null,
      alert_code: String(item.alert_code || "").trim().toLowerCase(),
      enabled: Boolean(item.enabled),
      priority: Math.max(1, Math.min(1000, Number(item.priority || 100))),
      provider_override: item.provider_override || null,
      matched: Boolean(matchedPolicy && String(matchedPolicy.id || "") === String(item.id || "")),
    }))
    .sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority;
      return String(a.alert_code).localeCompare(String(b.alert_code));
    })
    .slice(0, 50);
  if (appendAuditEvent) {
    appendQueueAuditEvent({
      projectId,
      action: "incident_policy_simulated",
      actor: String(actor || "web_ui"),
      reason: "queue_incident_policy_simulation",
      pausedUntil: null,
      payload: {
        alert_codes: alertCodes,
        health: normalizedHealth,
        matched_policy_id: matchedPolicyResponse?.id || null,
        matched_policy_alert_code: matchedPolicyResponse?.alert_code || null,
        provider,
        validation_error: validationError,
        should_open: Boolean(shouldOpen),
        include_secrets_requested: Boolean(includeSecrets),
        include_secrets_effective: includeSecretsEffective,
      },
    });
  }
  return {
    status: validationError ? "invalid" : "ok",
    project_id: projectId,
    health: normalizedHealth,
    alert_codes: alertCodes,
    dry_run: true,
    generated_at: nowIso(),
    matched_policy: matchedPolicyResponse,
    secrets: {
      requested: Boolean(includeSecrets),
      included: includeSecretsEffective,
      hook_access_granted: canIncludeHookSecrets,
      policy_access_granted: canIncludePolicySecrets,
    },
    effective_hook: {
      enabled: Boolean(effectiveHook.enabled),
      provider,
      open_webhook_url: trimOptional(effectiveHook.open_webhook_url, 2048),
      resolve_webhook_url: trimOptional(effectiveHook.resolve_webhook_url, 2048),
      provider_config: maskedProviderConfig,
      provider_config_keys: Object.keys(maskedProviderConfig).sort(),
      open_on_health: openOnHealth,
      auto_resolve: Boolean(effectiveHook.auto_resolve),
      cooldown_minutes: Math.max(1, Math.min(1440, Number(effectiveHook.cooldown_minutes || 30))),
      timeout_sec: Math.max(1, Math.min(60, Number(effectiveHook.timeout_sec || 10))),
    },
    route_trace: {
      matched_policy_id: matchedPolicyResponse?.id || null,
      matched_policy_alert_code: matchedPolicyResponse?.alert_code || null,
      provider_before_policy: normalizeIncidentProvider(hook.provider),
      provider_after_policy: provider,
      candidate_policies: traceCandidates,
    },
    decision: {
      should_open_incident: Boolean(shouldOpen && Boolean(effectiveHook.enabled) && validationError == null),
      skip_reason:
        validationError ||
        (!effectiveHook.enabled ? "hook_disabled" : !shouldOpen ? "health_not_in_open_on" : null),
      ticket_side_effects: false,
    },
  };
}

function getQueueIncidentHook(projectId) {
  const existing = state.queueIncidentHooks.find((item) => item.project_id === projectId);
  if (existing) {
    return { ...existing };
  }
  return {
    project_id: projectId,
    enabled: false,
    provider: "webhook",
    open_webhook_url: null,
    resolve_webhook_url: null,
    provider_config: { headers: {} },
    open_on_health: ["critical"],
    auto_resolve: true,
    cooldown_minutes: 30,
    timeout_sec: 10,
    secret_edit_roles: [...INCIDENT_SECRET_EDIT_ROLES_DEFAULT],
    updated_by: "system",
    created_at: null,
    updated_at: null,
  };
}

function upsertQueueIncidentHook(projectId, patch = {}, actorRoles = new Set()) {
  const now = nowIso();
  const current = getQueueIncidentHook(projectId);
  const provider = normalizeIncidentProvider(patch.provider ?? current.provider ?? "webhook");
  const resolvedConfig = resolveIncidentProviderConfigSecrets(
    provider,
    patch.provider_config ?? current.provider_config ?? {},
    current.provider === provider ? current.provider_config || {} : {},
  );
  const providerConfig = resolvedConfig.providerConfig;
  const secretEditRoles = normalizeIncidentSecretRoles(patch.secret_edit_roles ?? current.secret_edit_roles);
  if (resolvedConfig.secretChanged && !canEditIncidentSecrets(secretEditRoles, actorRoles)) {
    throw new Error("incident_secret_edit_forbidden");
  }
  const merged = {
    ...current,
    ...patch,
    project_id: projectId,
    enabled: Boolean(patch.enabled ?? current.enabled ?? false),
    provider,
    open_webhook_url:
      patch.open_webhook_url == null ? current.open_webhook_url : String(patch.open_webhook_url || "").trim() || null,
    resolve_webhook_url:
      patch.resolve_webhook_url == null
        ? current.resolve_webhook_url
        : String(patch.resolve_webhook_url || "").trim() || null,
    provider_config: providerConfig,
    open_on_health: normalizeIncidentOpenOnHealth(patch.open_on_health ?? current.open_on_health),
    auto_resolve: Boolean(patch.auto_resolve ?? current.auto_resolve ?? true),
    cooldown_minutes: Math.max(1, Math.min(1440, Number(patch.cooldown_minutes ?? current.cooldown_minutes ?? 30))),
    timeout_sec: Math.max(1, Math.min(60, Number(patch.timeout_sec ?? current.timeout_sec ?? 10))),
    secret_edit_roles: secretEditRoles,
    updated_by: String(patch.updated_by || current.updated_by || "web_ui"),
    created_at: current.created_at || now,
    updated_at: now,
  };
  validateIncidentHookRequirements({
    provider,
    enabled: merged.enabled,
    autoResolve: merged.auto_resolve,
    openWebhookUrl: merged.open_webhook_url,
    resolveWebhookUrl: merged.resolve_webhook_url,
    providerConfig: merged.provider_config,
  });
  const idx = state.queueIncidentHooks.findIndex((item) => item.project_id === projectId);
  if (idx >= 0) {
    state.queueIncidentHooks[idx] = merged;
  } else {
    state.queueIncidentHooks.push(merged);
  }
  return merged;
}

function getOpenQueueIncident(projectId) {
  const rows = state.queueIncidents
    .filter((item) => item.project_id === projectId && item.status === "open" && !item.resolved_at)
    .sort((a, b) => String(b.opened_at || "").localeCompare(String(a.opened_at || "")));
  return rows.length ? { ...rows[0] } : null;
}

function getLatestQueueIncident(projectId) {
  const rows = state.queueIncidents
    .filter((item) => item.project_id === projectId)
    .sort((a, b) =>
      String(b.resolved_at || b.opened_at || "").localeCompare(String(a.resolved_at || a.opened_at || "")),
    );
  return rows.length ? { ...rows[0] } : null;
}

function touchQueueIncidentSync(incidentId, updatedBy = "system") {
  const idx = state.queueIncidents.findIndex((item) => String(item.id) === String(incidentId));
  if (idx < 0) return null;
  state.queueIncidents[idx] = {
    ...state.queueIncidents[idx],
    last_sync_at: nowIso(),
    updated_by: String(updatedBy || "system"),
  };
  return { ...state.queueIncidents[idx] };
}

function createQueueIncidentOpen({
  projectId,
  triggerHealth,
  triggerAlertCodes,
  openReason,
  externalProvider = "webhook",
  externalTicketId = null,
  externalTicketUrl = null,
  openPayload = {},
  createdBy = "system",
}) {
  const now = nowIso();
  const incident = {
    id: randomUUID(),
    project_id: projectId,
    status: "open",
    trigger_health: String(triggerHealth || "critical"),
    trigger_alert_codes: Array.isArray(triggerAlertCodes)
      ? triggerAlertCodes.map((item) => String(item || "").trim()).filter(Boolean)
      : [],
    open_reason: openReason == null ? null : String(openReason),
    resolve_reason: null,
    external_provider: String(externalProvider || "webhook"),
    external_ticket_id: externalTicketId == null ? null : String(externalTicketId),
    external_ticket_url: externalTicketUrl == null ? null : String(externalTicketUrl),
    open_payload: openPayload && typeof openPayload === "object" ? openPayload : {},
    resolve_payload: {},
    opened_at: now,
    resolved_at: null,
    last_sync_at: now,
    created_by: String(createdBy || "system"),
    updated_by: String(createdBy || "system"),
  };
  state.queueIncidents.unshift(incident);
  state.queueIncidents = state.queueIncidents.slice(0, 5000);
  return { ...incident };
}

function resolveQueueIncident({ incidentId, resolveReason, resolvePayload = {}, updatedBy = "system" }) {
  const idx = state.queueIncidents.findIndex((item) => String(item.id) === String(incidentId));
  if (idx < 0) return null;
  const current = state.queueIncidents[idx];
  if (current.status !== "open" || current.resolved_at) {
    return { ...current };
  }
  const resolved = {
    ...current,
    status: "resolved",
    resolve_reason: resolveReason == null ? null : String(resolveReason),
    resolve_payload: resolvePayload && typeof resolvePayload === "object" ? resolvePayload : {},
    resolved_at: nowIso(),
    last_sync_at: nowIso(),
    updated_by: String(updatedBy || "system"),
  };
  state.queueIncidents[idx] = resolved;
  return { ...resolved };
}

function listQueueIncidentHooks(projectIdsRaw, limit = 200, singleProject = "", includeSecrets = false, actorRoles = new Set()) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedCsv] : requestedCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  if (dedupRequested.length > 0) {
    return state.queueIncidentHooks
      .filter((item) => dedupRequested.includes(String(item.project_id || "")))
      .sort((a, b) => String(a.project_id || "").localeCompare(String(b.project_id || "")))
      .slice(0, Math.max(1, Math.min(200, Number(limit || 200))))
      .map((item) => {
        const provider = normalizeIncidentProvider(item.provider);
        const secretEditRoles = normalizeIncidentSecretRoles(item.secret_edit_roles);
        return {
          ...item,
          provider_config: maskIncidentProviderConfig(provider, item.provider_config || {}, includeSecrets),
          secret_edit_roles: secretEditRoles,
          secret_access: {
            required_roles: secretEditRoles,
            can_edit: canEditIncidentSecrets(secretEditRoles, actorRoles),
          },
          provider_config_secret_keys: incidentProviderSecretKeys(provider).filter((key) => Boolean(item.provider_config?.[key])),
        };
      });
  }
  return [...state.queueIncidentHooks]
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))
    .slice(0, Math.max(1, Math.min(200, Number(limit || 200))))
    .map((item) => {
      const provider = normalizeIncidentProvider(item.provider);
      const secretEditRoles = normalizeIncidentSecretRoles(item.secret_edit_roles);
      return {
        ...item,
        provider_config: maskIncidentProviderConfig(provider, item.provider_config || {}, includeSecrets),
        secret_edit_roles: secretEditRoles,
        secret_access: {
          required_roles: secretEditRoles,
          can_edit: canEditIncidentSecrets(secretEditRoles, actorRoles),
        },
        provider_config_secret_keys: incidentProviderSecretKeys(provider).filter((key) => Boolean(item.provider_config?.[key])),
      };
    });
}

function listQueueIncidents(projectIdsRaw, { status = null, limit = 120, singleProject = "" } = {}) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedCsv] : requestedCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const rows = state.queueIncidents.filter((item) => {
    if (dedupRequested.length > 0 && !dedupRequested.includes(String(item.project_id || ""))) {
      return false;
    }
    if (status && String(item.status || "") !== String(status)) {
      return false;
    }
    return true;
  });
  return rows
    .sort((a, b) =>
      String(b.resolved_at || b.opened_at || "").localeCompare(String(a.resolved_at || a.opened_at || "")),
    )
    .slice(0, Math.max(1, Math.min(500, Number(limit || 120))))
    .map((item) => ({ ...item }));
}

function syncQueueIncidentHooks({
  projectIdsRaw,
  singleProject = "",
  actor = "web_ui",
  windowHours = 24,
  dryRun = false,
  forceResolve = false,
  preflightEnforcementMode = "inherit",
  preflightPauseHours = null,
  preflightCriticalFailThreshold = null,
  preflightIncludeRunBeforeLiveSyncOnly = true,
  preflightRecordAudit = true,
  limit = 50,
}) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedCsv] : requestedCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const fallbackProjects = [...new Set(state.schedules.map((item) => String(item.project_id || "")).filter(Boolean))];
  const targets = (dedupRequested.length ? dedupRequested : fallbackProjects).slice(
    0,
    Math.max(1, Math.min(200, Number(limit || 50))),
  );
  const summary = { opened: 0, resolved: 0, failed: 0, noop: 0, blocked: 0, paused: 0 };
  const results = [];
  for (const projectId of targets) {
    const throughput = buildQueueThroughput(projectId, Number(windowHours || 24));
    const control = throughput?.control && typeof throughput.control === "object" ? throughput.control : getQueueControl(projectId);
    const ownership = getQueueOwnership(projectId);
    const hook = getQueueIncidentHook(projectId);
    const health = String(throughput.health || "healthy");
    const alertCodes = Array.isArray(throughput.alerts)
      ? throughput.alerts.map((item) => String(item?.code || "").trim()).filter(Boolean)
      : [];
    const existingOpen = getOpenQueueIncident(projectId);
    const latestIncident = getLatestQueueIncident(projectId);
    const projectMode = ["off", "block", "pause"].includes(String(control.incident_preflight_enforcement_mode || "off"))
      ? String(control.incident_preflight_enforcement_mode || "off")
      : "off";
    const modeOverride = String(preflightEnforcementMode || "inherit").trim().toLowerCase();
    const effectivePreflightMode = ["off", "block", "pause"].includes(modeOverride) ? modeOverride : projectMode;
    const effectivePreflightPauseHours = Math.max(
      1,
      Math.min(
        168,
        Number(
          preflightPauseHours == null ? control.incident_preflight_pause_hours || 4 : preflightPauseHours,
        ),
      ),
    );
    const effectivePreflightCriticalThreshold = Math.max(
      1,
      Math.min(
        100,
        Number(
          preflightCriticalFailThreshold == null
            ? control.incident_preflight_critical_fail_threshold || 1
            : preflightCriticalFailThreshold,
        ),
      ),
    );
    const preflightMeta = {
      mode: effectivePreflightMode,
      project_mode: projectMode,
      pause_hours: effectivePreflightPauseHours,
      critical_fail_threshold: effectivePreflightCriticalThreshold,
      include_run_before_live_sync_only: Boolean(preflightIncludeRunBeforeLiveSyncOnly),
      record_audit: Boolean(preflightRecordAudit),
    };
    if (effectivePreflightMode !== "off") {
      const preflight = runQueueIncidentPreflightChecks({
        projectIdsRaw: projectId,
        singleProject: projectId,
        presetIdsRaw: "",
        includeDisabled: false,
        includeRunBeforeLiveSyncOnly: Boolean(preflightIncludeRunBeforeLiveSyncOnly),
        actor,
        recordAudit: Boolean(preflightRecordAudit),
        limit: 50,
      });
      const rollup = Array.isArray(preflight.project_rollups)
        ? preflight.project_rollups.find((item) => String(item?.project_id || "") === projectId) || null
        : null;
      const checksTotal = Number(rollup?.checks_total || 0);
      const failedChecks = Number(rollup?.failed || 0);
      const criticalAlerts = Number(rollup?.critical_alerts || 0);
      const shouldGate = checksTotal > 0 && criticalAlerts >= effectivePreflightCriticalThreshold;
      Object.assign(preflightMeta, {
        checks_total: checksTotal,
        failed_checks: failedChecks,
        critical_alerts: criticalAlerts,
        should_gate: shouldGate,
        generated_at: preflight.generated_at,
      });
      if (shouldGate) {
        const gateActionBase = effectivePreflightMode === "block" ? "blocked_by_preflight" : "paused_by_preflight";
        const gateAction = Boolean(dryRun) ? `would_${gateActionBase}` : gateActionBase;
        const gateRow = {
          project_id: projectId,
          health,
          provider: normalizeIncidentProvider(hook.provider),
          hook_enabled: Boolean(hook.enabled),
          matched_policy: null,
          incident_before: existingOpen,
          incident_after: existingOpen,
          action: gateAction,
          preflight: preflightMeta,
        };
        if (dryRun) {
          summary.noop += 1;
          if (effectivePreflightMode === "block") {
            summary.blocked += 1;
          } else {
            summary.paused += 1;
          }
        } else if (effectivePreflightMode === "block") {
          summary.failed += 1;
          summary.blocked += 1;
          appendQueueAuditEvent({
            projectId,
            action: "incident_sync_blocked_preflight",
            actor,
            reason: `critical preflight failures: ${criticalAlerts}`,
            pausedUntil: null,
            payload: {
              mode: effectivePreflightMode,
              critical_alerts: criticalAlerts,
              checks_total: checksTotal,
              failed_checks: failedChecks,
              critical_fail_threshold: effectivePreflightCriticalThreshold,
            },
          });
        } else {
          summary.failed += 1;
          summary.paused += 1;
          const pausedUntil = new Date(Date.now() + effectivePreflightPauseHours * 60 * 60 * 1000).toISOString();
          const controlAfter = upsertQueueControl(projectId, {
            paused_until: pausedUntil,
            pause_reason: `incident sync paused by preflight: ${criticalAlerts} critical alerts (threshold ${effectivePreflightCriticalThreshold})`,
            incident_preflight_enforcement_mode: effectivePreflightMode,
            incident_preflight_pause_hours: effectivePreflightPauseHours,
            incident_preflight_critical_fail_threshold: effectivePreflightCriticalThreshold,
            updated_by: actor,
          });
          gateRow.control_after = controlAfter;
          appendQueueAuditEvent({
            projectId,
            action: "incident_sync_paused_preflight",
            actor,
            reason: `critical preflight failures: ${criticalAlerts}`,
            pausedUntil,
            payload: {
              mode: effectivePreflightMode,
              pause_hours: effectivePreflightPauseHours,
              critical_alerts: criticalAlerts,
              checks_total: checksTotal,
              failed_checks: failedChecks,
              critical_fail_threshold: effectivePreflightCriticalThreshold,
            },
          });
        }
        results.push(gateRow);
        continue;
      }
    }
    let effectiveHook = hook;
    let matchedPolicy = null;
    try {
      const resolved = resolveIncidentHookPolicy(hook, policiesByProject(projectId), health, alertCodes);
      effectiveHook = resolved.hook;
      matchedPolicy = resolved.matchedPolicy;
    } catch (error) {
      results.push({
        project_id: projectId,
        health,
        provider: normalizeIncidentProvider(hook.provider),
        hook_enabled: Boolean(hook.enabled),
        matched_policy: null,
        incident_before: existingOpen,
        incident_after: existingOpen,
        action: "policy_invalid",
        error: error instanceof Error ? error.message : String(error),
      });
      summary.failed += 1;
      continue;
    }
    const provider = normalizeIncidentProvider(effectiveHook.provider);
    const providerConfig = normalizeIncidentProviderConfig(provider, effectiveHook.provider_config || {});
    const openOn = new Set(normalizeIncidentOpenOnHealth(effectiveHook.open_on_health));
    const row = {
      project_id: projectId,
      health,
      provider,
      hook_enabled: Boolean(hook.enabled),
      matched_policy: matchedPolicy,
      incident_before: existingOpen,
      action: "noop",
    };
    if (!hook.enabled) {
      row.action = "hook_disabled";
      row.incident_after = existingOpen;
      results.push(row);
      summary.noop += 1;
      continue;
    }
    try {
      validateIncidentHookRequirements({
        provider,
        enabled: Boolean(effectiveHook.enabled),
        autoResolve: Boolean(effectiveHook.auto_resolve),
        openWebhookUrl: effectiveHook.open_webhook_url,
        resolveWebhookUrl: effectiveHook.resolve_webhook_url,
        providerConfig,
      });
    } catch (error) {
      row.action = "hook_invalid";
      row.error = error instanceof Error ? error.message : String(error);
      row.incident_after = existingOpen;
      results.push(row);
      summary.failed += 1;
      continue;
    }

    const shouldOpen = openOn.has(health);
    if (shouldOpen) {
      if (existingOpen) {
        touchQueueIncidentSync(existingOpen.id, actor);
        row.action = "already_open";
        row.incident_after = getOpenQueueIncident(projectId);
        results.push(row);
        summary.noop += 1;
        continue;
      }

      const cooldownMinutes = Math.max(1, Math.min(1440, Number(effectiveHook.cooldown_minutes || 30)));
      const markerRaw = latestIncident?.resolved_at || latestIncident?.opened_at || null;
      const marker = markerRaw ? new Date(markerRaw).getTime() : NaN;
      const cooldownUntil = Number.isFinite(marker) ? marker + cooldownMinutes * 60 * 1000 : NaN;
      if (Number.isFinite(cooldownUntil) && cooldownUntil > Date.now()) {
        row.action = "cooldown_active";
        row.cooldown_until = new Date(cooldownUntil).toISOString();
        row.incident_after = null;
        results.push(row);
        summary.noop += 1;
        continue;
      }

      const openPayload = {
        event: "queue_incident_opened",
        generated_at: nowIso(),
        actor,
        project_id: projectId,
        health,
        alert_codes: alertCodes,
        throughput,
        ownership,
      };
      if (dryRun) {
        row.action = "would_open";
        row.payload_preview = openPayload;
        row.incident_after = null;
        results.push(row);
        summary.noop += 1;
        continue;
      }

      const providerOpenUrl =
        provider === "pagerduty"
          ? String(effectiveHook.open_webhook_url || "").trim() || "https://events.pagerduty.com/v2/enqueue"
          : provider === "jira"
            ? String(effectiveHook.open_webhook_url || "").trim() ||
              `${String(providerConfig.base_url || "").replace(/\/+$/, "")}/rest/api/2/issue`
            : String(effectiveHook.open_webhook_url || "").trim();
      let externalTicketId = `INC-${projectId}-${Date.now().toString(36)}`;
      let externalTicketUrl = `https://incidents.example.com/${encodeURIComponent(projectId)}/${Date.now().toString(36)}`;
      if (provider === "pagerduty") {
        externalTicketId = `${String(providerConfig.dedup_key_prefix || "synapse-queue")}:${projectId}`;
        externalTicketUrl = providerConfig.incident_url_template
          ? String(providerConfig.incident_url_template).replace("{dedup_key}", externalTicketId)
          : `https://pagerduty.example.com/incidents/${encodeURIComponent(externalTicketId)}`;
      } else if (provider === "jira") {
        const jiraKeyPrefix = String(providerConfig.project_key || "OPS").toUpperCase();
        externalTicketId = `${jiraKeyPrefix}-${Math.max(1, Math.trunc(Math.random() * 9000))}`;
        externalTicketUrl = providerConfig.browse_url_template
          ? String(providerConfig.browse_url_template).replace("{issue_key}", externalTicketId)
          : `${String(providerConfig.base_url || "https://jira.example.com").replace(/\/+$/, "")}/browse/${encodeURIComponent(externalTicketId)}`;
      }
      const incident = createQueueIncidentOpen({
        projectId,
        triggerHealth: health,
        triggerAlertCodes: alertCodes,
        openReason: "critical_queue_state",
        externalProvider: provider,
        externalTicketId,
        externalTicketUrl,
        openPayload: {
          provider,
          request: {
            method: "POST",
            url: providerOpenUrl,
          },
          webhook_status: 200,
          response_json: { ticket_id: externalTicketId },
          response_preview: "mock_ok",
        },
        createdBy: actor,
      });
      appendQueueAuditEvent({
        projectId,
        action: "incident_ticket_opened",
        actor,
        reason: `${provider}:${String(providerOpenUrl || "").slice(0, 180)}`,
        pausedUntil: null,
        payload: {
          incident_id: incident.id,
          external_ticket_id: incident.external_ticket_id,
          provider,
          health,
          alert_codes: alertCodes,
          webhook_status: 200,
        },
      });
      row.action = "opened";
      row.incident_after = incident;
      results.push(row);
      summary.opened += 1;
      continue;
    }

    if (!existingOpen) {
      row.action = "no_incident";
      row.incident_after = null;
      results.push(row);
      summary.noop += 1;
      continue;
    }

    if (!effectiveHook.auto_resolve && !forceResolve) {
      touchQueueIncidentSync(existingOpen.id, actor);
      row.action = "open_retained";
      row.incident_after = getOpenQueueIncident(projectId);
      results.push(row);
      summary.noop += 1;
      continue;
    }

    const resolvePayload = {
      event: "queue_incident_resolved",
      generated_at: nowIso(),
      actor,
      project_id: projectId,
      resolution_reason: "queue_health_recovered",
      current_health: health,
      alert_codes: alertCodes,
      throughput,
      ownership,
      incident: existingOpen,
    };
    if (dryRun) {
      row.action = "would_resolve";
      row.payload_preview = resolvePayload;
      row.incident_after = existingOpen;
      results.push(row);
      summary.noop += 1;
      continue;
    }

    const providerResolveUrl =
      provider === "pagerduty"
        ? String(effectiveHook.resolve_webhook_url || effectiveHook.open_webhook_url || "").trim() ||
          "https://events.pagerduty.com/v2/enqueue"
        : provider === "jira"
          ? String(effectiveHook.resolve_webhook_url || "").trim() ||
            `${String(providerConfig.base_url || "").replace(/\/+$/, "")}/rest/api/2/issue/${encodeURIComponent(String(existingOpen.external_ticket_id || "UNKNOWN"))}/transitions`
          : String(effectiveHook.resolve_webhook_url || effectiveHook.open_webhook_url || "").trim();
    const resolved = resolveQueueIncident({
      incidentId: existingOpen.id,
      resolveReason: "queue_health_recovered",
      resolvePayload: {
        provider,
        request: {
          method: "POST",
          url: providerResolveUrl,
        },
        webhook_status: 200,
        response_json: { status: "resolved" },
        response_preview: "mock_ok",
        health,
        alert_codes: alertCodes,
      },
      updatedBy: actor,
    });
    appendQueueAuditEvent({
      projectId,
      action: "incident_ticket_resolved",
      actor,
      reason: `${provider}:${String(providerResolveUrl || "").slice(0, 180)}`,
      pausedUntil: null,
      payload: {
        incident_id: resolved?.id || existingOpen.id,
        external_ticket_id: resolved?.external_ticket_id || existingOpen.external_ticket_id,
        provider,
        health,
        webhook_status: 200,
      },
    });
    row.action = "resolved";
    row.incident_after = resolved || null;
    results.push(row);
    summary.resolved += 1;
  }

  return {
    requested_projects: dedupRequested,
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    dry_run: Boolean(dryRun),
    force_resolve: Boolean(forceResolve),
    preflight_enforcement_mode: String(preflightEnforcementMode || "inherit").trim().toLowerCase() || "inherit",
    preflight_include_run_before_live_sync_only: Boolean(preflightIncludeRunBeforeLiveSyncOnly),
    preflight_record_audit: Boolean(preflightRecordAudit),
    projects_total: targets.length,
    summary,
    results,
    generated_at: nowIso(),
  };
}

const INCIDENT_SYNC_SCHEDULE_PRESET_INTERVAL_MINUTES = {
  hourly: 60,
  every_4h: 240,
  daily: 1440,
  weekly: 10080,
};

function normalizeIncidentSyncSchedulePreset(value) {
  const preset = String(value || "every_4h").trim().toLowerCase();
  if (preset === "custom") return "custom";
  if (Object.prototype.hasOwnProperty.call(INCIDENT_SYNC_SCHEDULE_PRESET_INTERVAL_MINUTES, preset)) {
    return preset;
  }
  return "every_4h";
}

function resolveIncidentSyncScheduleIntervalMinutes(preset, intervalMinutes) {
  if (preset !== "custom") {
    return Number(INCIDENT_SYNC_SCHEDULE_PRESET_INTERVAL_MINUTES[preset] || 240);
  }
  return Math.max(5, Math.min(10080, Number(intervalMinutes || 60)));
}

function filterQueueIncidentSyncSchedules({
  projectIdsRaw = "",
  singleProject = "",
  scheduleIdsRaw = "",
  enabled = null,
  dueOnly = false,
  projectContains = "",
  nameContains = "",
  status = null,
} = {}) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedProjects = parseCsvProjects(projectIdsRaw);
  const targets = explicitSingle ? [explicitSingle, ...requestedProjects] : requestedProjects;
  const dedupTargets = targets.filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
  const projectContainsNormalized = String(projectContains || "").trim().toLowerCase();
  const nameContainsNormalized = String(nameContains || "").trim().toLowerCase();
  const statusNormalized = String(status || "").trim().toLowerCase();
  const scheduleIds = String(scheduleIdsRaw || "")
    .split(",")
    .map((item) => String(item || "").trim())
    .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
  const now = Date.now();
  return state.queueIncidentSyncSchedules.filter((item) => {
    if (dedupTargets.length > 0 && !dedupTargets.includes(String(item.project_id || ""))) {
      return false;
    }
    if (scheduleIds.length > 0 && !scheduleIds.includes(String(item.id || ""))) {
      return false;
    }
    if (typeof enabled === "boolean" && Boolean(item.enabled) !== enabled) {
      return false;
    }
    if (projectContainsNormalized && !String(item.project_id || "").toLowerCase().includes(projectContainsNormalized)) {
      return false;
    }
    if (nameContainsNormalized && !String(item.name || "").toLowerCase().includes(nameContainsNormalized)) {
      return false;
    }
    const rowStatus = String(item.last_status || "").trim().toLowerCase();
    if (statusNormalized) {
      if (statusNormalized === "never") {
        if (rowStatus) {
          return false;
        }
      } else if (rowStatus !== statusNormalized) {
        return false;
      }
    }
    if (dueOnly) {
      const ts = item.next_run_at ? new Date(item.next_run_at).getTime() : NaN;
      if (!Number.isFinite(ts) || ts > now) {
        return false;
      }
    }
    return true;
  });
}

function compareQueueIncidentSyncScheduleRows(a, b, sortBy = "next_run_at", sortDir = "asc") {
  const resolvedSortBy = String(sortBy || "next_run_at").trim().toLowerCase();
  const resolvedSortDir = String(sortDir || "asc").trim().toLowerCase() === "desc" ? "desc" : "asc";
  const parseNullableDate = (value) => {
    if (!value) return null;
    const ts = new Date(value).getTime();
    return Number.isFinite(ts) ? ts : null;
  };
  const compareNullableDateAscNullsLast = (left, right) => {
    const aTs = parseNullableDate(left);
    const bTs = parseNullableDate(right);
    if (aTs == null && bTs == null) return 0;
    if (aTs == null) return 1;
    if (bTs == null) return -1;
    if (aTs === bTs) return 0;
    return aTs < bTs ? -1 : 1;
  };
  const compareString = (left, right) => {
    const l = String(left || "").toLowerCase();
    const r = String(right || "").toLowerCase();
    if (l === r) return 0;
    return l < r ? -1 : 1;
  };

  let primary = 0;
  if (resolvedSortBy === "next_run_at") {
    primary = compareNullableDateAscNullsLast(a.next_run_at, b.next_run_at);
  } else if (resolvedSortBy === "updated_at") {
    primary = compareString(a.updated_at, b.updated_at);
  } else if (resolvedSortBy === "last_run_at") {
    primary = compareNullableDateAscNullsLast(a.last_run_at, b.last_run_at);
  } else if (resolvedSortBy === "name") {
    primary = compareString(a.name, b.name);
  } else if (resolvedSortBy === "project_id") {
    primary = compareString(a.project_id, b.project_id);
  } else if (resolvedSortBy === "status") {
    primary = compareString(a.last_status || "never", b.last_status || "never");
  } else {
    primary = compareNullableDateAscNullsLast(a.next_run_at, b.next_run_at);
  }
  if (resolvedSortDir === "desc") {
    primary *= -1;
  }
  if (primary !== 0) {
    return primary;
  }
  const updatedAtFallback = compareString(b.updated_at, a.updated_at);
  if (updatedAtFallback !== 0) return updatedAtFallback;
  const nameFallback = compareString(a.name, b.name);
  if (nameFallback !== 0) return nameFallback;
  return compareString(a.id, b.id);
}

function listQueueIncidentSyncSchedules({
  projectIdsRaw = "",
  singleProject = "",
  scheduleIdsRaw = "",
  enabled = null,
  dueOnly = false,
  projectContains = "",
  nameContains = "",
  status = null,
  sortBy = "next_run_at",
  sortDir = "asc",
  offset = 0,
  limit = 200,
} = {}) {
  const filteredRows = filterQueueIncidentSyncSchedules({
    projectIdsRaw,
    singleProject,
    scheduleIdsRaw,
    enabled,
    dueOnly,
    projectContains,
    nameContains,
    status,
  });
  const cap = Math.max(1, Math.min(500, Number(limit || 200)));
  const safeOffset = Math.max(0, Number(offset || 0));
  return filteredRows
    .sort((a, b) => compareQueueIncidentSyncScheduleRows(a, b, sortBy, sortDir))
    .slice(safeOffset, safeOffset + cap)
    .map((item) => ({ ...item }));
}

function encodeIncidentSyncScheduleFleetCursor(offset) {
  const safeOffset = Math.max(0, Number(offset || 0));
  const raw = JSON.stringify({ offset: safeOffset });
  return Buffer.from(raw, "utf8").toString("base64url");
}

function decodeIncidentSyncScheduleFleetCursor(cursor) {
  const rawCursor = String(cursor || "").trim();
  if (!rawCursor) {
    return null;
  }
  try {
    const decoded = Buffer.from(rawCursor, "base64url").toString("utf8");
    const payload = JSON.parse(decoded);
    return Math.max(0, Number(payload && typeof payload === "object" ? payload.offset : 0));
  } catch {
    throw new Error("incident_sync_schedule_cursor_invalid");
  }
}

function upsertQueueIncidentSyncSchedule(projectId, payload = {}) {
  const normalizedProjectId = String(projectId || "").trim() || projectIdDefault;
  const normalizedName = String(payload.name || "").trim();
  if (!normalizedName) {
    throw new Error("incident_sync_schedule_name_required");
  }
  const preset = normalizeIncidentSyncSchedulePreset(payload.preset);
  const intervalMinutes = resolveIncidentSyncScheduleIntervalMinutes(preset, payload.interval_minutes);
  const now = nowIso();
  const nextRunRaw = payload.next_run_at == null ? null : String(payload.next_run_at).trim();
  const nextRunAt = nextRunRaw ? new Date(nextRunRaw).toISOString() : now;
  const existingIdx = state.queueIncidentSyncSchedules.findIndex(
    (item) => String(item.project_id || "") === normalizedProjectId && String(item.name || "") === normalizedName,
  );
  const existing = existingIdx >= 0 ? state.queueIncidentSyncSchedules[existingIdx] : null;
  const preflightModeRaw = String(payload.preflight_enforcement_mode || "inherit").trim().toLowerCase();
  const preflightMode = ["inherit", "off", "block", "pause"].includes(preflightModeRaw) ? preflightModeRaw : "inherit";
  const normalized = {
    id: existing?.id || randomUUID(),
    project_id: normalizedProjectId,
    name: normalizedName,
    enabled: Boolean(payload.enabled ?? existing?.enabled ?? true),
    preset,
    interval_minutes: intervalMinutes,
    window_hours: Math.max(1, Math.min(168, Number(payload.window_hours ?? existing?.window_hours ?? 24))),
    batch_size: Math.max(1, Math.min(200, Number(payload.batch_size ?? existing?.batch_size ?? 50))),
    sync_limit: Math.max(1, Math.min(200, Number(payload.sync_limit ?? existing?.sync_limit ?? 200))),
    dry_run: Boolean(payload.dry_run ?? existing?.dry_run ?? false),
    force_resolve: Boolean(payload.force_resolve ?? existing?.force_resolve ?? false),
    preflight_enforcement_mode: preflightMode,
    preflight_pause_hours:
      payload.preflight_pause_hours == null
        ? null
        : Math.max(1, Math.min(168, Number(payload.preflight_pause_hours))),
    preflight_critical_fail_threshold:
      payload.preflight_critical_fail_threshold == null
        ? null
        : Math.max(1, Math.min(100, Number(payload.preflight_critical_fail_threshold))),
    preflight_include_run_before_live_sync_only: Boolean(
      payload.preflight_include_run_before_live_sync_only ?? existing?.preflight_include_run_before_live_sync_only ?? true,
    ),
    preflight_record_audit: Boolean(payload.preflight_record_audit ?? existing?.preflight_record_audit ?? true),
    requested_by: String(payload.requested_by || existing?.requested_by || "incident_sync_scheduler"),
    next_run_at: nextRunAt,
    last_run_at: existing?.last_run_at || null,
    last_status: existing?.last_status || null,
    last_run_summary:
      existing?.last_run_summary && typeof existing.last_run_summary === "object" ? existing.last_run_summary : {},
    updated_by: String(payload.updated_by || existing?.updated_by || "web_ui"),
    created_at: existing?.created_at || now,
    updated_at: now,
  };
  if (existingIdx >= 0) {
    state.queueIncidentSyncSchedules[existingIdx] = normalized;
  } else {
    state.queueIncidentSyncSchedules.unshift(normalized);
  }
  return { ...normalized };
}

function runQueueIncidentSyncSchedules({
  projectIdsRaw = "",
  singleProject = "",
  scheduleIdsRaw = "",
  actor = "incident_sync_scheduler",
  forceRun = false,
  skipDueCheck = false,
  limit = 200,
} = {}) {
  const selected = listQueueIncidentSyncSchedules({
    projectIdsRaw,
    singleProject,
    scheduleIdsRaw,
    enabled: true,
    dueOnly: !forceRun && !skipDueCheck,
    limit,
  });
  const summary = {
    schedules_total: selected.length,
    executed: 0,
    ok: 0,
    partial_failure: 0,
    failed: 0,
    skipped: 0,
    opened: 0,
    resolved: 0,
    sync_failed: 0,
    noop: 0,
    blocked: 0,
    paused: 0,
  };
  const results = [];
  for (const schedule of selected) {
    const intervalMinutes = Math.max(5, Math.min(10080, Number(schedule.interval_minutes || 240)));
    const startedAt = new Date();
    const nextRunAt = new Date(startedAt.getTime() + intervalMinutes * 60 * 1000).toISOString();
    try {
      const syncResult = syncQueueIncidentHooks({
        projectIdsRaw: String(schedule.project_id || ""),
        singleProject: String(schedule.project_id || ""),
        actor: String(actor || schedule.requested_by || "incident_sync_scheduler"),
        windowHours: Math.max(1, Math.min(168, Number(schedule.window_hours || 24))),
        dryRun: Boolean(schedule.dry_run),
        forceResolve: Boolean(schedule.force_resolve),
        preflightEnforcementMode: String(schedule.preflight_enforcement_mode || "inherit"),
        preflightPauseHours: schedule.preflight_pause_hours,
        preflightCriticalFailThreshold: schedule.preflight_critical_fail_threshold,
        preflightIncludeRunBeforeLiveSyncOnly: Boolean(schedule.preflight_include_run_before_live_sync_only),
        preflightRecordAudit: Boolean(schedule.preflight_record_audit),
        limit: Math.max(1, Math.min(200, Number(schedule.sync_limit || 50))),
      });
      const syncSummary = syncResult?.summary && typeof syncResult.summary === "object" ? syncResult.summary : {};
      const syncOpened = Number(syncSummary.opened || 0);
      const syncResolved = Number(syncSummary.resolved || 0);
      const syncFailed = Number(syncSummary.failed || 0);
      const syncNoop = Number(syncSummary.noop || 0);
      const syncBlocked = Number(syncSummary.blocked || 0);
      const syncPaused = Number(syncSummary.paused || 0);
      let status = "ok";
      if (syncFailed > 0) status = "failed";
      else if (syncBlocked > 0 || syncPaused > 0) status = "partial_failure";
      else if (syncOpened === 0 && syncResolved === 0 && syncNoop > 0) status = "skipped";
      const failureClasses = [];
      if (syncFailed > 0) failureClasses.push("sync_failed");
      if (syncBlocked > 0) failureClasses.push("preflight_blocked");
      if (syncPaused > 0) failureClasses.push("preflight_paused");
      if (status === "skipped" && syncNoop > 0) failureClasses.push("noop");
      const dedupFailureClasses = Array.from(new Set(failureClasses));
      const idx = state.queueIncidentSyncSchedules.findIndex((item) => String(item.id) === String(schedule.id));
      const updated = {
        ...(idx >= 0 ? state.queueIncidentSyncSchedules[idx] : schedule),
        last_run_at: startedAt.toISOString(),
        last_status: status,
        last_run_summary: {
          status,
          sync_summary: {
            opened: syncOpened,
            resolved: syncResolved,
            failed: syncFailed,
            noop: syncNoop,
            blocked: syncBlocked,
            paused: syncPaused,
            projects_total: Number(syncSummary.projects_total || 0),
          },
          failure_classes: dedupFailureClasses,
          sync_generated_at: syncResult.generated_at || nowIso(),
          run_actor: String(actor || schedule.requested_by || "incident_sync_scheduler"),
          force_run: Boolean(forceRun),
          skip_due_check: Boolean(skipDueCheck),
        },
        next_run_at: nextRunAt,
        updated_by: String(actor || "incident_sync_scheduler"),
        updated_at: nowIso(),
      };
      if (idx >= 0) {
        state.queueIncidentSyncSchedules[idx] = updated;
      }
      const auditEvent = appendQueueAuditEvent({
        projectId: String(schedule.project_id || projectIdDefault),
        action: "incident_sync_schedule_run",
        actor: String(actor || "incident_sync_scheduler"),
        reason: `schedule:${String(schedule.name || schedule.id)}`,
        pausedUntil: null,
        payload: {
          schedule_id: schedule.id,
          schedule_name: schedule.name,
          schedule_status: status,
          next_run_at: nextRunAt,
          sync_summary: updated.last_run_summary.sync_summary,
          failure_classes: dedupFailureClasses,
          force_run: Boolean(forceRun),
          skip_due_check: Boolean(skipDueCheck),
        },
      });
      summary.executed += 1;
      if (status === "ok") summary.ok += 1;
      else if (status === "partial_failure") summary.partial_failure += 1;
      else if (status === "failed") summary.failed += 1;
      else if (status === "skipped") summary.skipped += 1;
      summary.opened += syncOpened;
      summary.resolved += syncResolved;
      summary.sync_failed += syncFailed;
      summary.noop += syncNoop;
      summary.blocked += syncBlocked;
      summary.paused += syncPaused;
      results.push({
        schedule_id: schedule.id,
        project_id: schedule.project_id,
        name: schedule.name,
        status,
        audit_event_id: Number(auditEvent.id || 0),
        updated_schedule: { ...updated },
        sync_summary: updated.last_run_summary.sync_summary,
        sync_generated_at: syncResult.generated_at || nowIso(),
        failure_classes: dedupFailureClasses,
        sync_trace: {
          requested_projects: syncResult.requested_projects,
          window_hours: syncResult.window_hours,
          dry_run: syncResult.dry_run,
          force_resolve: syncResult.force_resolve,
          preflight_enforcement_mode: syncResult.preflight_enforcement_mode,
          summary: syncResult.summary,
          results: Array.isArray(syncResult.results) ? syncResult.results : [],
          generated_at: syncResult.generated_at || nowIso(),
        },
        run_actor: String(actor || schedule.requested_by || "incident_sync_scheduler"),
      });
    } catch (error) {
      const idx = state.queueIncidentSyncSchedules.findIndex((item) => String(item.id) === String(schedule.id));
      const message = error instanceof Error ? error.message : String(error);
      const normalizedError = String(message || "").toLowerCase();
      const failureClasses = ["sync_exception"];
      if (normalizedError.includes("timeout")) failureClasses.push("timeout");
      if (normalizedError.includes("network") || normalizedError.includes("connection") || normalizedError.includes("http")) {
        failureClasses.push("transport_error");
      }
      const dedupFailureClasses = Array.from(new Set(failureClasses));
      const updated = {
        ...(idx >= 0 ? state.queueIncidentSyncSchedules[idx] : schedule),
        last_run_at: startedAt.toISOString(),
        last_status: "failed",
        last_run_summary: {
          status: "failed",
          error: message,
          failure_classes: dedupFailureClasses,
          run_actor: String(actor || schedule.requested_by || "incident_sync_scheduler"),
          force_run: Boolean(forceRun),
          skip_due_check: Boolean(skipDueCheck),
        },
        next_run_at: nextRunAt,
        updated_by: String(actor || "incident_sync_scheduler"),
        updated_at: nowIso(),
      };
      if (idx >= 0) {
        state.queueIncidentSyncSchedules[idx] = updated;
      }
      const auditEvent = appendQueueAuditEvent({
        projectId: String(schedule.project_id || projectIdDefault),
        action: "incident_sync_schedule_failed",
        actor: String(actor || "incident_sync_scheduler"),
        reason: `schedule:${String(schedule.name || schedule.id)}`,
        pausedUntil: null,
        payload: {
          schedule_id: schedule.id,
          schedule_name: schedule.name,
          error: message,
          failure_classes: dedupFailureClasses,
          next_run_at: nextRunAt,
          force_run: Boolean(forceRun),
          skip_due_check: Boolean(skipDueCheck),
        },
      });
      summary.executed += 1;
      summary.failed += 1;
      results.push({
        schedule_id: schedule.id,
        project_id: schedule.project_id,
        name: schedule.name,
        status: "failed",
        error: message,
        audit_event_id: Number(auditEvent.id || 0),
        failure_classes: dedupFailureClasses,
        updated_schedule: { ...updated },
        run_actor: String(actor || schedule.requested_by || "incident_sync_scheduler"),
      });
    }
  }
  return {
    status: summary.failed > 0 ? "partial_failure" : "ok",
    requested_projects: parseCsvProjects(projectIdsRaw),
    requested_schedule_ids: String(scheduleIdsRaw || "")
      .split(",")
      .map((item) => String(item || "").trim())
      .filter(Boolean),
    force_run: Boolean(forceRun),
    skip_due_check: Boolean(skipDueCheck),
    summary,
    results,
    generated_at: nowIso(),
  };
}

function normalizeIncidentSyncScheduleRunStatus(value, fallback = "unknown") {
  const status = String(value || "").trim().toLowerCase();
  if (["ok", "partial_failure", "failed", "skipped"].includes(status)) {
    return status;
  }
  return String(fallback || "unknown").trim().toLowerCase() || "unknown";
}

function deriveIncidentSyncScheduleFailureClasses({ action, status, payload }) {
  const classes = new Set();
  const rawClasses = Array.isArray(payload?.failure_classes) ? payload.failure_classes : [];
  for (const raw of rawClasses) {
    const code = String(raw || "").trim().toLowerCase();
    if (code) classes.add(code.slice(0, 128));
  }
  const syncSummary = payload && typeof payload.sync_summary === "object" && payload.sync_summary != null ? payload.sync_summary : {};
  if (Number(syncSummary.failed || 0) > 0) classes.add("sync_failed");
  if (Number(syncSummary.blocked || 0) > 0) classes.add("preflight_blocked");
  if (Number(syncSummary.paused || 0) > 0) classes.add("preflight_paused");
  if (status === "skipped" && Number(syncSummary.noop || 0) > 0) classes.add("noop");
  const errorText = String(payload?.error || "").trim().toLowerCase();
  if (errorText) {
    if (errorText.includes("timeout")) classes.add("timeout");
    if (errorText.includes("network") || errorText.includes("connection") || errorText.includes("http")) {
      classes.add("transport_error");
    }
    if (errorText.includes("preflight") && errorText.includes("block")) classes.add("preflight_blocked");
    if (errorText.includes("preflight") && errorText.includes("pause")) classes.add("preflight_paused");
    if (classes.size === 0) classes.add("sync_exception");
  }
  if (String(action || "").trim().toLowerCase() === "incident_sync_schedule_failed") {
    classes.add("sync_exception");
  }
  if (classes.size === 0 && ["failed", "partial_failure"].includes(status)) {
    classes.add("unknown_failure");
  }
  return Array.from(classes).sort((a, b) => a.localeCompare(b));
}

function buildQueueIncidentSyncScheduleTimeline({ scheduleId, projectId = "", days = 30, limit = 120 } = {}) {
  const normalizedScheduleId = String(scheduleId || "").trim();
  if (!normalizedScheduleId) {
    return null;
  }
  const schedule = state.queueIncidentSyncSchedules.find((item) => String(item.id || "") === normalizedScheduleId);
  if (!schedule) {
    return null;
  }
  const targetProjectId = String(schedule.project_id || "").trim();
  const requestedProjectId = String(projectId || "").trim();
  if (requestedProjectId && requestedProjectId !== targetProjectId) {
    return null;
  }
  const sinceMs = Date.now() - Math.max(1, Number(days || 30)) * 24 * 60 * 60 * 1000;
  const rows = state.queueAuditEvents
    .filter((event) => {
      const action = String(event.action || "").trim().toLowerCase();
      if (!["incident_sync_schedule_run", "incident_sync_schedule_failed"].includes(action)) {
        return false;
      }
      if (String(event.project_id || "") !== targetProjectId) {
        return false;
      }
      const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
      if (String(payload.schedule_id || "") !== normalizedScheduleId) {
        return false;
      }
      const ts = new Date(event.created_at).getTime();
      return Number.isFinite(ts) && ts >= sinceMs;
    })
    .sort((a, b) => {
      const at = new Date(a.created_at).getTime();
      const bt = new Date(b.created_at).getTime();
      if (at !== bt) return bt - at;
      return Number(b.id || 0) - Number(a.id || 0);
    })
    .slice(0, Math.max(1, Math.min(500, Number(limit || 120))));

  const summary = {
    runs_total: 0,
    ok: 0,
    partial_failure: 0,
    failed: 0,
    skipped: 0,
    unknown: 0,
    latest_status: null,
    latest_run_at: null,
  };
  const trend = new Map();
  const failureClassCounts = new Map();
  const runs = rows.map((event, index) => {
    const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
    const action = String(event.action || "").trim().toLowerCase();
    const status = normalizeIncidentSyncScheduleRunStatus(
      action === "incident_sync_schedule_failed" ? "failed" : payload.schedule_status,
      "unknown",
    );
    const failureClasses = deriveIncidentSyncScheduleFailureClasses({ action, status, payload });
    const createdAt = String(event.created_at || nowIso());
    const day = createdAt.slice(0, 10);
    const syncSummary =
      payload.sync_summary && typeof payload.sync_summary === "object"
        ? payload.sync_summary
        : {};
    const normalizedSyncSummary = {
      opened: Number(syncSummary.opened || 0),
      resolved: Number(syncSummary.resolved || 0),
      failed: Number(syncSummary.failed || 0),
      noop: Number(syncSummary.noop || 0),
      blocked: Number(syncSummary.blocked || 0),
      paused: Number(syncSummary.paused || 0),
      projects_total: Number(syncSummary.projects_total || 0),
    };
    summary.runs_total += 1;
    if (status === "ok") summary.ok += 1;
    else if (status === "partial_failure") summary.partial_failure += 1;
    else if (status === "failed") summary.failed += 1;
    else if (status === "skipped") summary.skipped += 1;
    else summary.unknown += 1;
    if (index === 0) {
      summary.latest_status = status;
      summary.latest_run_at = createdAt;
    }
    const bucket = trend.get(day) || {
      day,
      runs: 0,
      ok: 0,
      partial_failure: 0,
      failed: 0,
      skipped: 0,
      unknown: 0,
    };
    bucket.runs += 1;
    if (status === "ok") bucket.ok += 1;
    else if (status === "partial_failure") bucket.partial_failure += 1;
    else if (status === "failed") bucket.failed += 1;
    else if (status === "skipped") bucket.skipped += 1;
    else bucket.unknown += 1;
    trend.set(day, bucket);
    for (const code of failureClasses) {
      failureClassCounts.set(code, Number(failureClassCounts.get(code) || 0) + 1);
    }
    return {
      audit_event_id: Number(event.id || 0),
      project_id: String(event.project_id || ""),
      action,
      status,
      actor: String(event.actor || "incident_sync_scheduler"),
      reason: event.reason == null ? null : String(event.reason),
      created_at: createdAt,
      next_run_at: payload.next_run_at == null ? null : String(payload.next_run_at),
      force_run: Boolean(payload.force_run),
      skip_due_check: Boolean(payload.skip_due_check),
      sync_summary: normalizedSyncSummary,
      error: payload.error == null ? null : String(payload.error),
      failure_classes: failureClasses,
    };
  });

  return {
    schedule_id: normalizedScheduleId,
    project_id: targetProjectId,
    days: Math.max(1, Number(days || 30)),
    since: new Date(sinceMs).toISOString(),
    schedule: { ...schedule },
    summary,
    trend: Array.from(trend.values()).sort((a, b) => String(a.day).localeCompare(String(b.day))),
    failure_classes: Array.from(failureClassCounts.entries())
      .sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return String(a[0]).localeCompare(String(b[0]));
      })
      .map(([code, count]) => ({ code, count: Number(count || 0) })),
    runs,
    generated_at: nowIso(),
  };
}

function buildQueueThroughput(projectId, windowHours = 24) {
  const control = getQueueControl(projectId);
  const runs = state.operationRuns.filter((item) => item.project_id === projectId && item.mode === "async");
  const queue = {
    queued: runs.filter((item) => item.status === "queued").length,
    running: runs.filter((item) => item.status === "running").length,
    cancel_requested: runs.filter((item) => item.status === "cancel_requested").length,
    succeeded: runs.filter((item) => item.status === "succeeded").length,
    failed: runs.filter((item) => item.status === "failed").length,
    canceled: runs.filter((item) => item.status === "canceled").length,
  };
  queue.depth_total = queue.queued + queue.running + queue.cancel_requested;
  const queuedRows = runs
    .filter((item) => item.status === "queued")
    .map((item) => new Date(item.created_at).getTime())
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b);
  const now = Date.now();
  const queuedAges = queuedRows.map((value) => Math.max(0, (now - value) / (1000 * 60)));
  const oldestQueuedMs = queuedRows.length ? queuedRows[0] : null;
  const newestQueuedMs = queuedRows.length ? queuedRows[queuedRows.length - 1] : null;
  queue.oldest_queued_at = oldestQueuedMs ? new Date(oldestQueuedMs).toISOString() : null;
  queue.newest_queued_at = newestQueuedMs ? new Date(newestQueuedMs).toISOString() : null;
  queue.oldest_queued_age_minutes = oldestQueuedMs ? Number(((now - oldestQueuedMs) / (1000 * 60)).toFixed(3)) : null;
  queue.queued_age_minutes = latencyStats(queuedAges);

  const runningLags = runs
    .filter((item) => item.status === "running" || item.status === "cancel_requested")
    .map((item) => {
      const ts = item.heartbeat_at || item.updated_at || item.created_at;
      const value = new Date(ts).getTime();
      if (!Number.isFinite(value)) return null;
      return Math.max(0, (now - value) / (1000 * 60));
    })
    .filter((item) => item != null);
  const staleWorkers = runningLags.filter((item) => item > control.worker_lag_sla_minutes).length;

  const sinceMs = now - Math.max(1, windowHours) * 60 * 60 * 1000;
  const terminalRows = runs.filter((item) => ["succeeded", "failed", "canceled"].includes(item.status)).filter((item) => {
    const ts = new Date(item.finished_at || item.updated_at || item.created_at).getTime();
    return Number.isFinite(ts) && ts >= sinceMs;
  });
  const durations = terminalRows
    .map((item) => {
      const start = new Date(item.started_at || item.created_at).getTime();
      const end = new Date(item.finished_at || item.updated_at || item.created_at).getTime();
      if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
      return Math.max(0, (end - start) / (1000 * 60));
    })
    .filter((item) => item != null);

  let health = "healthy";
  const alerts = [];
  if (queue.depth_total >= control.queue_depth_warn * 2) {
    health = "critical";
    alerts.push({
      code: "queue_depth_critical",
      severity: "critical",
      message: `Queue depth ${queue.depth_total} is above critical threshold ${control.queue_depth_warn * 2}.`,
    });
  } else if (queue.depth_total > control.queue_depth_warn) {
    health = "watch";
    alerts.push({
      code: "queue_depth_warn",
      severity: "warning",
      message: `Queue depth ${queue.depth_total} is above warning threshold ${control.queue_depth_warn}.`,
    });
  }
  if (staleWorkers > 0) {
    health = "critical";
    alerts.push({
      code: "worker_lag_stale",
      severity: "critical",
      message: `${staleWorkers} running workers are above lag SLA (${control.worker_lag_sla_minutes}m).`,
    });
  }
  if (control.pause_active) {
    alerts.push({
      code: "queue_paused",
      severity: "info",
      message: `Queue paused until ${control.paused_until}.`,
    });
  }

  return {
    project_id: projectId,
    window_hours: windowHours,
    generated_at: nowIso(),
    control,
    queue,
    worker_lag: {
      sla_minutes: control.worker_lag_sla_minutes,
      stale_workers: staleWorkers,
      lag_minutes: latencyStats(runningLags),
    },
    throughput_window: {
      since: new Date(sinceMs).toISOString(),
      terminal_total: terminalRows.length,
      succeeded: terminalRows.filter((item) => item.status === "succeeded").length,
      failed: terminalRows.filter((item) => item.status === "failed").length,
      canceled: terminalRows.filter((item) => item.status === "canceled").length,
      duration_minutes: latencyStats(durations),
    },
    health,
    alerts,
  };
}

function parseCsvProjects(raw) {
  return String(raw || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, all) => all.indexOf(item) === index);
}

function buildQueueThroughputCompare(projectIdsRaw, windowHours = 24, limit = 12) {
  const requested = parseCsvProjects(projectIdsRaw);
  const fallbackProjects = [...new Set(state.schedules.map((item) => String(item.project_id)))];
  const targets = (requested.length ? requested : fallbackProjects).slice(0, Math.max(1, Math.min(200, Number(limit || 12))));
  const rows = targets.map((projectId) => ({
    ...buildQueueThroughput(projectId, windowHours),
    ownership: getQueueOwnership(projectId),
    incident: getOpenQueueIncident(projectId),
  }));
  rows.sort((a, b) => {
    const rank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
    const rankDelta = rank(String(a.health || "healthy")) - rank(String(b.health || "healthy"));
    if (rankDelta !== 0) return rankDelta;
    const depthDelta = Number(b.queue?.depth_total || 0) - Number(a.queue?.depth_total || 0);
    if (depthDelta !== 0) return depthDelta;
    return String(a.project_id).localeCompare(String(b.project_id));
  });
  return {
    window_hours: windowHours,
    requested_projects: requested,
    projects: rows,
    generated_at: nowIso(),
  };
}

function toCsvField(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function serializeQueueThroughputCompareCsv(payload) {
  const rows = Array.isArray(payload?.projects) ? payload.projects : [];
  const generatedAt = String(payload?.generated_at || nowIso());
  const windowHours = Number(payload?.window_hours || 24);
  const header = [
    "generated_at",
    "window_hours",
    "project_id",
    "health",
    "pause_active",
    "paused_until",
    "incident_preflight_enforcement_mode",
    "incident_preflight_pause_hours",
    "incident_preflight_critical_fail_threshold",
    "queue_depth_total",
    "queue_queued",
    "queue_running",
    "queue_cancel_requested",
    "queue_depth_warn",
    "worker_lag_sla_minutes",
    "worker_lag_p90_minutes",
    "worker_lag_stale_workers",
    "queued_wait_p90_minutes",
    "terminal_total",
    "succeeded",
    "failed",
    "canceled",
    "owner_name",
    "owner_contact",
    "oncall_channel",
    "escalation_channel",
    "incident_status",
    "incident_ticket_id",
    "incident_ticket_url",
    "incident_opened_at",
  ];
  const lines = [header.map((item) => toCsvField(item)).join(",")];
  for (const item of rows) {
    const queue = item?.queue || {};
    const control = item?.control || {};
    const workerLag = item?.worker_lag || {};
    const throughputWindow = item?.throughput_window || {};
    const ownership = item?.ownership || {};
    const incident = item?.incident || {};
    const lagStats = workerLag?.lag_minutes || {};
    const queuedStats = queue?.queued_age_minutes || {};
    const line = [
      generatedAt,
      windowHours,
      item?.project_id || "",
      item?.health || "healthy",
      Boolean(control?.pause_active),
      control?.paused_until || "",
      ["off", "block", "pause"].includes(String(control?.incident_preflight_enforcement_mode || "off"))
        ? String(control?.incident_preflight_enforcement_mode || "off")
        : "off",
      Math.max(1, Math.min(168, Number(control?.incident_preflight_pause_hours || 4))),
      Math.max(1, Math.min(100, Number(control?.incident_preflight_critical_fail_threshold || 1))),
      Number(queue?.depth_total || 0),
      Number(queue?.queued || 0),
      Number(queue?.running || 0),
      Number(queue?.cancel_requested || 0),
      Number(control?.queue_depth_warn || 0),
      Number(control?.worker_lag_sla_minutes || 0),
      lagStats?.p90 ?? "",
      Number(workerLag?.stale_workers || 0),
      queuedStats?.p90 ?? "",
      Number(throughputWindow?.terminal_total || 0),
      Number(throughputWindow?.succeeded || 0),
      Number(throughputWindow?.failed || 0),
      Number(throughputWindow?.canceled || 0),
      ownership?.owner_name || "",
      ownership?.owner_contact || "",
      ownership?.oncall_channel || "",
      ownership?.escalation_channel || "",
      incident?.status || "",
      incident?.external_ticket_id || "",
      incident?.external_ticket_url || "",
      incident?.opened_at || "",
    ];
    lines.push(line.map((value) => toCsvField(value)).join(","));
  }
  return `${lines.join("\n")}\n`;
}

function buildQueueAutoscalingRecommendation(projectId, windowHours = 24, historyHours = 72) {
  const throughput = buildQueueThroughput(projectId, windowHours);
  const control = throughput.control || {};
  const queue = throughput.queue || {};
  const workerLag = throughput.worker_lag || {};

  const sinceMs = Date.now() - Math.max(24, Math.min(720, Number(historyHours || 72))) * 60 * 60 * 1000;
  const runs = state.operationRuns.filter((item) => item.project_id === projectId && item.mode === "async");
  const createdRows = runs.filter((item) => {
    const ts = new Date(item.created_at).getTime();
    return Number.isFinite(ts) && ts >= sinceMs;
  });
  const startedRows = runs.filter((item) => {
    const ts = new Date(item.started_at || "").getTime();
    return Number.isFinite(ts) && ts >= sinceMs;
  });
  const terminalRows = runs.filter((item) => {
    if (!["succeeded", "failed", "canceled"].includes(String(item.status || ""))) return false;
    const ts = new Date(item.finished_at || item.updated_at || item.created_at).getTime();
    return Number.isFinite(ts) && ts >= sinceMs;
  });
  const durationValues = terminalRows
    .map((item) => {
      const start = new Date(item.started_at || item.created_at).getTime();
      const end = new Date(item.finished_at || item.updated_at || item.created_at).getTime();
      if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
      return Math.max(0, (end - start) / (1000 * 60));
    })
    .filter((value) => value != null);

  const createdByHour = new Map();
  for (const row of createdRows) {
    const ts = new Date(row.created_at).getTime();
    if (!Number.isFinite(ts)) continue;
    const key = new Date(Math.floor(ts / 3600000) * 3600000).toISOString();
    createdByHour.set(key, (createdByHour.get(key) || 0) + 1);
  }
  const completedByHour = new Map();
  for (const row of terminalRows) {
    const ts = new Date(row.finished_at || row.updated_at || row.created_at).getTime();
    if (!Number.isFinite(ts)) continue;
    const key = new Date(Math.floor(ts / 3600000) * 3600000).toISOString();
    completedByHour.set(key, (completedByHour.get(key) || 0) + 1);
  }
  const createdHourly = [...createdByHour.values()];
  const completedHourly = [...completedByHour.values()];

  const createdTotal = createdRows.length;
  const startedTotal = startedRows.length;
  const terminalTotal = terminalRows.length;
  const durationAvg = durationValues.length
    ? Number((durationValues.reduce((acc, value) => acc + value, 0) / durationValues.length).toFixed(3))
    : null;
  const durationP50 = quantile(durationValues, 0.5);
  const durationP90 = quantile(durationValues, 0.9);
  const arrivalRatePerHour = Number((createdTotal / Math.max(1, Number(historyHours || 72))).toFixed(4));
  const completionRatePerHour = Number((terminalTotal / Math.max(1, Number(historyHours || 72))).toFixed(4));
  const arrivalPeakPerHour = createdHourly.length ? Math.max(...createdHourly) : 0;
  const completionPeakPerHour = completedHourly.length ? Math.max(...completedHourly) : 0;
  const arrivalsPerActiveHour = createdHourly.length
    ? Number((createdHourly.reduce((acc, value) => acc + value, 0) / createdHourly.length).toFixed(4))
    : 0;
  const completionsPerActiveHour = completedHourly.length
    ? Number((completedHourly.reduce((acc, value) => acc + value, 0) / completedHourly.length).toFixed(4))
    : 0;
  const queueDepth = Number(queue.depth_total || 0);
  const activeWorkersEstimate = Number(queue.running || 0) + Number(queue.cancel_requested || 0);
  const queueWaitP90 = queue.queued_age_minutes?.p90 == null ? null : Number(queue.queued_age_minutes.p90);
  const workerLagP90 = workerLag.lag_minutes?.p90 == null ? null : Number(workerLag.lag_minutes.p90);
  const lagBudgetCurrent = Math.max(1, Number(control.worker_lag_sla_minutes || 20));
  const depthWarnCurrent = Math.max(1, Number(control.queue_depth_warn || 12));

  let observedDuration = durationP50;
  if (observedDuration == null) observedDuration = durationP90;
  if (observedDuration == null) observedDuration = throughput?.throughput_window?.duration_minutes?.p50 ?? 12;
  observedDuration = Math.max(1, Math.min(180, Number(observedDuration || 12)));
  const singleWorkerCapacity = 60 / observedDuration;
  let demandRate = Math.max(arrivalRatePerHour, completionRatePerHour);
  demandRate = Math.max(demandRate, Math.min(arrivalPeakPerHour, arrivalRatePerHour * 2.5 + 1));
  const baselineWorkers = Math.ceil(demandRate / Math.max(0.000001, singleWorkerCapacity));
  const lagBudgetHours = Math.max(1, lagBudgetCurrent / 60);
  const backlogWorkers = queueDepth > 0 ? Math.ceil((queueDepth / lagBudgetHours) / Math.max(0.000001, singleWorkerCapacity)) : 0;
  let workerTarget = Math.max(1, baselineWorkers, backlogWorkers, activeWorkersEstimate);
  if (String(throughput.health || "healthy") === "critical") {
    workerTarget = Math.ceil(workerTarget * 1.2);
  } else if (String(throughput.health || "healthy") === "watch") {
    workerTarget = Math.ceil(workerTarget * 1.1);
  }
  if (queueWaitP90 != null && queueWaitP90 > lagBudgetCurrent) {
    workerTarget = Math.max(workerTarget, activeWorkersEstimate + 1, baselineWorkers + 1);
  }
  workerTarget = Math.max(1, Math.min(128, workerTarget));
  const workerDelta = workerTarget - Math.max(1, activeWorkersEstimate);

  let lagBudgetTarget = lagBudgetCurrent;
  if (queueWaitP90 != null && queueWaitP90 > lagBudgetCurrent * 1.5) {
    lagBudgetTarget = Math.min(240, Math.max(lagBudgetCurrent, Math.ceil(queueWaitP90 * 1.15)));
  } else if (queueWaitP90 != null && queueWaitP90 < lagBudgetCurrent * 0.5 && queueDepth <= 2) {
    lagBudgetTarget = Math.max(5, Math.ceil(Math.max(queueWaitP90 * 1.35, 5)));
  } else if (workerLagP90 != null && Number(workerLag.stale_workers || 0) > 0 && workerLagP90 > lagBudgetCurrent * 1.05) {
    lagBudgetTarget = Math.min(240, Math.max(lagBudgetCurrent, Math.ceil(workerLagP90 * 1.2)));
  }
  lagBudgetTarget = Math.max(1, Math.min(1440, lagBudgetTarget));

  const sustainableDepth = Math.ceil(workerTarget * singleWorkerCapacity * (lagBudgetTarget / 60));
  const expectedWaitDepth = Math.ceil(arrivalRatePerHour * (lagBudgetTarget / 60));
  let depthWarnTarget = Math.max(4, sustainableDepth + Math.max(2, workerTarget), expectedWaitDepth + Math.max(2, workerTarget));
  if (queueDepth >= depthWarnCurrent * 2 && depthWarnTarget < depthWarnCurrent) {
    depthWarnTarget = depthWarnCurrent;
  }
  depthWarnTarget = Math.max(1, Math.min(50000, depthWarnTarget));

  const rationale = [
    `Current queue depth is ${queueDepth}; target workers account for backlog drain within lag budget.`,
    `Rolling demand over ${historyHours}h: arrivals ${arrivalRatePerHour.toFixed(2)}/h, completions ${completionRatePerHour.toFixed(2)}/h.`,
    `Median terminal runtime is ${observedDuration.toFixed(2)}m, so one worker handles about ${singleWorkerCapacity.toFixed(2)} ops/hour.`,
  ];
  if (queueWaitP90 != null) {
    rationale.splice(1, 0, `Queued wait p90 is ${queueWaitP90.toFixed(2)}m versus lag budget ${lagBudgetCurrent}m.`);
  }

  const actions = [];
  if (workerDelta >= 2) {
    actions.push({
      id: "increase_workers",
      priority: "high",
      title: `Increase worker concurrency to ${workerTarget}`,
      detail: `Current active estimate is ${activeWorkersEstimate}; backlog and demand require +${workerDelta} workers.`,
    });
  } else if (workerDelta === 1) {
    actions.push({
      id: "raise_workers_minor",
      priority: "medium",
      title: `Increase worker concurrency to ${workerTarget}`,
      detail: "Small backlog pressure detected; one extra worker should stabilize queue lag.",
    });
  } else if (workerDelta <= -2) {
    actions.push({
      id: "reduce_workers",
      priority: "medium",
      title: `Reduce worker concurrency to ${workerTarget}`,
      detail: `Observed demand is below current active estimate (${activeWorkersEstimate}); reclaim capacity safely.`,
    });
  }
  if (lagBudgetTarget !== lagBudgetCurrent) {
    actions.push({
      id: "tune_lag_budget",
      priority: "medium",
      title: `Adjust lag budget to ${lagBudgetTarget}m`,
      detail: `Current lag budget is ${lagBudgetCurrent}m; update worker lag SLA to match observed queue behavior.`,
    });
  }
  if (depthWarnTarget !== depthWarnCurrent) {
    actions.push({
      id: "tune_depth_warn",
      priority: "low",
      title: `Set queue depth warning to ${depthWarnTarget}`,
      detail: `Current warning threshold ${depthWarnCurrent} is misaligned with projected capacity envelope.`,
    });
  }
  if (Boolean(control.pause_active) && queueDepth > 0) {
    actions.push({
      id: "review_pause_window",
      priority: "medium",
      title: "Review active pause window",
      detail: "Queue is paused while backlog exists; resume earlier if maintenance allows.",
    });
  }

  let confidence = 0.35;
  confidence += Math.min(0.35, (terminalTotal / 120) * 0.35);
  confidence += Math.min(0.2, (createdTotal / 160) * 0.2);
  confidence += Math.min(0.1, (Math.max(createdHourly.length, completedHourly.length) / 24) * 0.1);
  if (createdTotal < 5) confidence = Math.min(confidence, 0.45);
  confidence = Number(Math.max(0.05, Math.min(0.99, confidence)).toFixed(3));

  return {
    project_id: projectId,
    window_hours: windowHours,
    history_hours: Math.max(24, Math.min(720, Number(historyHours || 72))),
    generated_at: nowIso(),
    health: String(throughput.health || "healthy"),
    current: {
      worker_concurrency_estimate: activeWorkersEstimate,
      worker_lag_sla_minutes: lagBudgetCurrent,
      queue_depth_warn: depthWarnCurrent,
    },
    observed: {
      history_since: new Date(sinceMs).toISOString(),
      created_total: createdTotal,
      started_total: startedTotal,
      terminal_total: terminalTotal,
      duration_count: durationValues.length,
      duration_minutes: {
        avg: durationAvg,
        p50: durationP50,
        p90: durationP90,
      },
      arrival_rate_per_hour: arrivalRatePerHour,
      completion_rate_per_hour: completionRatePerHour,
      arrival_peak_per_hour: arrivalPeakPerHour,
      completion_peak_per_hour: completionPeakPerHour,
      arrivals_per_active_hour: arrivalsPerActiveHour,
      completions_per_active_hour: completionsPerActiveHour,
      queue_depth: queueDepth,
      queue_wait_p90_minutes: queueWaitP90,
      worker_lag_p90_minutes: workerLagP90,
      single_worker_capacity_per_hour: Number(singleWorkerCapacity.toFixed(4)),
    },
    recommendation: {
      worker_concurrency_target: workerTarget,
      worker_concurrency_delta: workerDelta,
      worker_lag_sla_minutes: lagBudgetTarget,
      queue_depth_warn: depthWarnTarget,
      confidence,
      rationale: rationale.slice(0, 8),
    },
    actions,
  };
}

function buildQueueAutoscalingRecommendations(projectIdsRaw, windowHours = 24, historyHours = 72, limit = 20, singleProject = "") {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const fallbackProjects = [...new Set(state.schedules.map((item) => String(item.project_id)))];
  const targets = (dedupRequested.length ? dedupRequested : fallbackProjects).slice(
    0,
    Math.max(1, Math.min(200, Number(limit || 20))),
  );
  const rows = targets.map((projectId) => buildQueueAutoscalingRecommendation(projectId, windowHours, historyHours));
  rows.sort((a, b) => {
    const rank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
    const rankDelta = rank(String(a.health || "healthy")) - rank(String(b.health || "healthy"));
    if (rankDelta !== 0) return rankDelta;
    const delta = Number(b.recommendation?.worker_concurrency_delta || 0) - Number(a.recommendation?.worker_concurrency_delta || 0);
    if (delta !== 0) return delta;
    const depthDelta = Number(b.observed?.queue_depth || 0) - Number(a.observed?.queue_depth || 0);
    if (depthDelta !== 0) return depthDelta;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });
  return {
    window_hours: windowHours,
    history_hours: Math.max(24, Math.min(720, Number(historyHours || 72))),
    requested_projects: dedupRequested,
    recommendations: rows,
    generated_at: nowIso(),
  };
}

function buildQueueGovernanceDigest(projectIdsRaw, windowHours = 24, auditDays = 7, limit = 30, topN = 5, singleProject = "") {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const compare = buildQueueThroughputCompare(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(200, Number(limit || 30))),
  );
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  const sinceMs = Date.now() - Math.max(1, Math.min(365, Number(auditDays || 7))) * 24 * 60 * 60 * 1000;

  const latestActions = new Map();
  for (const event of state.queueAuditEvents) {
    if (!event || typeof event !== "object") continue;
    const projectId = String(event.project_id || "");
    const ts = new Date(event.created_at).getTime();
    if (!projectId || !Number.isFinite(ts) || ts < sinceMs) continue;
    if (!["pause", "bulk_pause", "resume", "bulk_resume"].includes(String(event.action || ""))) continue;
    const prev = latestActions.get(projectId);
    if (!prev || String(event.created_at) > String(prev.created_at)) {
      latestActions.set(projectId, event);
    }
  }

  const healthRank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
  const topCongestion = [...projects]
    .sort((a, b) => {
      const rankDelta = healthRank(String(a.health || "healthy")) - healthRank(String(b.health || "healthy"));
      if (rankDelta !== 0) return rankDelta;
      const depthDelta = Number(b.queue?.depth_total || 0) - Number(a.queue?.depth_total || 0);
      if (depthDelta !== 0) return depthDelta;
      const waitDelta = Number(b.queue?.queued_age_minutes?.p90 || 0) - Number(a.queue?.queued_age_minutes?.p90 || 0);
      if (waitDelta !== 0) return waitDelta;
      return String(a.project_id || "").localeCompare(String(b.project_id || ""));
    })
    .slice(0, Math.max(1, Math.min(20, Number(topN || 5))))
    .map((item) => ({
      project_id: String(item.project_id || ""),
      health: String(item.health || "healthy"),
      queue_depth: Number(item.queue?.depth_total || 0),
      queued: Number(item.queue?.queued || 0),
      running: Number(item.queue?.running || 0),
      queued_wait_p90_minutes: item.queue?.queued_age_minutes?.p90 ?? null,
      worker_lag_p90_minutes: item.worker_lag?.lag_minutes?.p90 ?? null,
      stale_workers: Number(item.worker_lag?.stale_workers || 0),
      pause_active: Boolean(item.control?.pause_active),
      ownership: item.ownership || getQueueOwnership(String(item.project_id || "")),
      incident: item.incident || null,
    }));

  const unreviewedPauses = [];
  for (const item of projects) {
    const projectId = String(item.project_id || "");
    if (!projectId || !Boolean(item.control?.pause_active)) continue;
    const latest = latestActions.get(projectId);
    const action = String(latest?.action || "");
    if (!["pause", "bulk_pause"].includes(action)) continue;
    const eventTime = latest?.created_at ? new Date(latest.created_at).getTime() : NaN;
    const pauseAgeMinutes = Number.isFinite(eventTime) ? Number(((Date.now() - eventTime) / (1000 * 60)).toFixed(3)) : null;
    unreviewedPauses.push({
      project_id: projectId,
      paused_until: item.control?.paused_until || null,
      pause_reason: item.control?.pause_reason || null,
      pause_updated_by: item.control?.updated_by || null,
      latest_action: action,
      latest_actor: latest?.actor || null,
      latest_reason: latest?.reason || null,
      latest_event_at: latest?.created_at || null,
      pause_age_minutes: pauseAgeMinutes,
      queue_depth: Number(item.queue?.depth_total || 0),
      health: String(item.health || "healthy"),
      ownership: item.ownership || getQueueOwnership(projectId),
    });
  }
  unreviewedPauses.sort((a, b) => {
    const rankDelta = healthRank(String(a.health || "healthy")) - healthRank(String(b.health || "healthy"));
    if (rankDelta !== 0) return rankDelta;
    const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
    if (depthDelta !== 0) return depthDelta;
    const ageDelta = Number(b.pause_age_minutes || 0) - Number(a.pause_age_minutes || 0);
    if (ageDelta !== 0) return ageDelta;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });

  const summary = {
    projects_total: projects.length,
    critical_projects: projects.filter((item) => String(item.health || "healthy") === "critical").length,
    watch_projects: projects.filter((item) => String(item.health || "healthy") === "watch").length,
    paused_projects: projects.filter((item) => Boolean(item.control?.pause_active)).length,
    unreviewed_pauses: unreviewedPauses.length,
    congested_projects: projects.filter((item) => Number(item.queue?.depth_total || 0) > 0).length,
    open_incidents: projects.filter((item) => String(item?.incident?.status || "") === "open").length,
  };

  return {
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    audit_days: Math.max(1, Math.min(365, Number(auditDays || 7))),
    requested_projects: dedupRequested,
    generated_at: nowIso(),
    summary,
    top_congestion: topCongestion,
    unreviewed_pauses: unreviewedPauses.slice(0, Math.max(1, Math.min(30, Number(topN || 5) * 3))),
  };
}

function queueIncidentAgeBucket(ageMinutes) {
  if (ageMinutes == null || !Number.isFinite(Number(ageMinutes))) return "unknown";
  const age = Number(ageMinutes);
  if (age < 60) return "under_1h";
  if (age < 240) return "between_1h_4h";
  if (age < 720) return "between_4h_12h";
  if (age < 1440) return "between_12h_24h";
  if (age < 4320) return "between_24h_72h";
  return "over_72h";
}

const INCIDENT_MTTA_PROXY_KEYS = [
  "acknowledged_at",
  "ack_at",
  "accepted_at",
  "created_at",
  "incident_created_at",
  "provider_created_at",
  "first_response_at",
];

function queueIncidentMttaProxyTimestamp(openedAtIso, lastSyncAtIso, openPayloadRaw) {
  const openedMs = openedAtIso ? new Date(openedAtIso).getTime() : NaN;
  if (!Number.isFinite(openedMs)) return null;
  const openPayload = openPayloadRaw && typeof openPayloadRaw === "object" ? openPayloadRaw : {};
  const candidateValues = [];
  for (const key of INCIDENT_MTTA_PROXY_KEYS) {
    const value = openPayload?.[key];
    if (value) candidateValues.push(value);
  }
  const nested = [openPayload?.delivery, openPayload?.provider_response, openPayload?.provider_payload];
  for (const row of nested) {
    if (!row || typeof row !== "object") continue;
    for (const key of INCIDENT_MTTA_PROXY_KEYS) {
      const value = row?.[key];
      if (value) candidateValues.push(value);
    }
  }
  if (lastSyncAtIso) candidateValues.push(lastSyncAtIso);
  const valid = candidateValues
    .map((value) => new Date(String(value)).getTime())
    .filter((value) => Number.isFinite(value) && value >= openedMs);
  if (valid.length === 0) return null;
  return new Date(Math.min(...valid)).toISOString();
}

function buildQueueIncidentEscalationDigest(
  projectIdsRaw,
  windowHours = 24,
  incidentSlaHours = 24,
  limit = 30,
  topN = 10,
  singleProject = "",
) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const compare = buildQueueThroughputCompare(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(200, Number(limit || 30))),
  );
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  const incidentSlaMinutes = Math.max(1, Math.min(168, Number(incidentSlaHours || 24))) * 60;
  const ageBuckets = {
    under_1h: 0,
    between_1h_4h: 0,
    between_4h_12h: 0,
    between_12h_24h: 0,
    between_24h_72h: 0,
    over_72h: 0,
    unknown: 0,
  };
  const escalationCandidates = [];
  const ownershipGaps = [];
  let overSla = 0;
  let criticalOpen = 0;
  let missingOwner = 0;
  let missingOncall = 0;
  let missingEscalation = 0;
  let incidentsWithoutTicket = 0;
  let routingReady = 0;
  let gapWithOpenIncident = 0;

  for (const item of projects) {
    const projectId = String(item?.project_id || "");
    if (!projectId) continue;
    const health = String(item?.health || "healthy");
    const ownership = item?.ownership || getQueueOwnership(projectId);
    const ownerName = String(ownership?.owner_name || "").trim();
    const oncallChannel = String(ownership?.oncall_channel || "").trim();
    const escalationChannel = String(ownership?.escalation_channel || "").trim();
    const ownerContact = String(ownership?.owner_contact || "").trim();
    const queueDepth = Number(item?.queue?.depth_total || 0);
    const incident = item?.incident || null;
    const incidentOpen = String(incident?.status || "") === "open";
    const missingFields = [];
    if (!ownerName) missingFields.push("owner_name");
    if (!oncallChannel) missingFields.push("oncall_channel");
    if (!escalationChannel) missingFields.push("escalation_channel");

    const openedAtIso = incident?.opened_at ? String(incident.opened_at) : null;
    const openedMs = openedAtIso ? new Date(openedAtIso).getTime() : NaN;
    const ageMinutes =
      Number.isFinite(openedMs) && incidentOpen ? Number(((Date.now() - openedMs) / (1000 * 60)).toFixed(3)) : null;
    const ticketId = String(incident?.external_ticket_id || "").trim();
    const ticketUrl = String(incident?.external_ticket_url || "").trim();
    const hasTicket = Boolean(ticketId || ticketUrl);

    if (missingFields.length > 0) {
      let gapScore = missingFields.length;
      if (health === "critical") gapScore += 3;
      else if (health === "watch") gapScore += 1;
      if (incidentOpen) gapScore += 2;
      if (queueDepth > 0) gapScore += 1;
      if (ageMinutes != null && ageMinutes >= incidentSlaMinutes) gapScore += 2;
      if (incidentOpen) gapWithOpenIncident += 1;
      ownershipGaps.push({
        project_id: projectId,
        health,
        queue_depth: queueDepth,
        incident_open: incidentOpen,
        incident_age_minutes: ageMinutes,
        missing_fields: missingFields,
        ownership: {
          owner_name: ownerName || null,
          owner_contact: ownerContact || null,
          oncall_channel: oncallChannel || null,
          escalation_channel: escalationChannel || null,
        },
        gap_score: gapScore,
      });
    }

    if (!incidentOpen) continue;

    const bucket = queueIncidentAgeBucket(ageMinutes);
    ageBuckets[bucket] += 1;
    const isOverSla = ageMinutes != null && ageMinutes >= incidentSlaMinutes;
    if (isOverSla) overSla += 1;
    if (health === "critical") criticalOpen += 1;
    if (missingFields.includes("owner_name")) missingOwner += 1;
    if (missingFields.includes("oncall_channel")) missingOncall += 1;
    if (missingFields.includes("escalation_channel")) missingEscalation += 1;
    if (!hasTicket) incidentsWithoutTicket += 1;
    if (missingFields.length === 0 && hasTicket) routingReady += 1;

    let riskScore = 0;
    if (health === "critical") riskScore += 4;
    else if (health === "watch") riskScore += 2;
    if (queueDepth > 0) riskScore += 1;
    if (queueDepth >= 20) riskScore += 1;
    if (ageMinutes != null && ageMinutes >= 60) riskScore += 1;
    if (ageMinutes != null && ageMinutes >= 240) riskScore += 2;
    if (ageMinutes != null && ageMinutes >= 1440) riskScore += 2;
    if (isOverSla) riskScore += 2;
    if (Boolean(item?.control?.pause_active)) riskScore += 1;
    riskScore += missingFields.length;
    if (!hasTicket) riskScore += 2;

    let recommendedAction = "monitor_until_next_sync";
    if (missingFields.includes("owner_name")) recommendedAction = "assign_owner_now";
    else if (missingFields.includes("oncall_channel")) recommendedAction = "set_oncall_channel";
    else if (missingFields.includes("escalation_channel")) recommendedAction = "set_escalation_channel";
    else if (!hasTicket) recommendedAction = "attach_or_create_ticket";
    else if (isOverSla && escalationChannel) recommendedAction = "escalate_to_escalation_channel";
    else if (isOverSla && oncallChannel) recommendedAction = "escalate_to_oncall_channel";

    escalationCandidates.push({
      project_id: projectId,
      health,
      queue_depth: queueDepth,
      pause_active: Boolean(item?.control?.pause_active),
      over_sla: isOverSla,
      risk_score: riskScore,
      recommended_action: recommendedAction,
      incident: {
        id: String(incident?.id || ""),
        status: String(incident?.status || ""),
        external_provider: String(incident?.external_provider || ""),
        trigger_health: String(incident?.trigger_health || ""),
        ticket_id: ticketId || null,
        ticket_url: ticketUrl || null,
        opened_at: openedAtIso,
        age_minutes: ageMinutes,
        last_sync_at: incident?.last_sync_at || null,
      },
      ownership: {
        owner_name: ownerName || null,
        owner_contact: ownerContact || null,
        oncall_channel: oncallChannel || null,
        escalation_channel: escalationChannel || null,
      },
      missing_fields: missingFields,
    });
  }

  const healthRank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
  escalationCandidates.sort((a, b) => {
    const slaDelta = Number(Boolean(b.over_sla)) - Number(Boolean(a.over_sla));
    if (slaDelta !== 0) return slaDelta;
    const riskDelta = Number(b.risk_score || 0) - Number(a.risk_score || 0);
    if (riskDelta !== 0) return riskDelta;
    const rankDelta = healthRank(String(a.health || "healthy")) - healthRank(String(b.health || "healthy"));
    if (rankDelta !== 0) return rankDelta;
    const ageDelta = Number(b?.incident?.age_minutes || 0) - Number(a?.incident?.age_minutes || 0);
    if (ageDelta !== 0) return ageDelta;
    const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
    if (depthDelta !== 0) return depthDelta;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });
  ownershipGaps.sort((a, b) => {
    const gapDelta = Number(b.gap_score || 0) - Number(a.gap_score || 0);
    if (gapDelta !== 0) return gapDelta;
    const rankDelta = healthRank(String(a.health || "healthy")) - healthRank(String(b.health || "healthy"));
    if (rankDelta !== 0) return rankDelta;
    const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
    if (depthDelta !== 0) return depthDelta;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });

  const openIncidents = escalationCandidates.length;
  return {
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    incident_sla_hours: Math.max(1, Math.min(168, Number(incidentSlaHours || 24))),
    requested_projects: dedupRequested,
    generated_at: nowIso(),
    summary: {
      projects_total: projects.length,
      open_incidents: openIncidents,
      open_incidents_over_sla: overSla,
      critical_open_incidents: criticalOpen,
      incidents_missing_owner: missingOwner,
      incidents_missing_oncall_channel: missingOncall,
      incidents_missing_escalation_channel: missingEscalation,
      incidents_without_ticket: incidentsWithoutTicket,
      routing_ready_open_incidents: routingReady,
      routing_ready_rate: openIncidents ? Number((routingReady / openIncidents).toFixed(4)) : 0,
      ownership_gap_projects: ownershipGaps.length,
      ownership_gap_with_open_incident: gapWithOpenIncident,
    },
    age_buckets: ageBuckets,
    escalation_candidates: escalationCandidates.slice(0, Math.max(1, Math.min(50, Number(topN || 10)))),
    ownership_gaps: ownershipGaps.slice(0, Math.max(10, Math.min(100, Number(topN || 10) * 2))),
  };
}

function buildQueueOwnerRollups(projectIdsRaw, windowHours = 24, slaHours = 24, limit = 50, singleProject = "") {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const compare = buildQueueThroughputCompare(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(200, Number(limit || 50))),
  );
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  const now = Date.now();
  const sinceMs = now - Math.max(1, Math.min(168 * 14, Number(windowHours || 24))) * 60 * 60 * 1000;
  const bucketMap = new Map();
  const projectToOwner = new Map();

  for (const item of projects) {
    const projectId = String(item?.project_id || "");
    if (!projectId) continue;
    const ownership = item?.ownership || getQueueOwnership(projectId);
    const ownerName = String(ownership?.owner_name || "").trim() || "unassigned";
    const oncallChannel = String(ownership?.oncall_channel || "").trim() || "unassigned";
    const ownerKey = `${ownerName}::${oncallChannel}`;
    projectToOwner.set(projectId, ownerKey);
    const queueDepth = Number(item?.queue?.depth_total || 0);
    const queueWaitP90 = item?.queue?.queued_age_minutes?.p90 == null ? null : Number(item.queue.queued_age_minutes.p90);
    const health = String(item?.health || "healthy");
    if (!bucketMap.has(ownerKey)) {
      bucketMap.set(ownerKey, {
        owner_key: ownerKey,
        owner_name: ownerName,
        oncall_channel: oncallChannel,
        owner_contact: ownership?.owner_contact || null,
        escalation_channel: ownership?.escalation_channel || null,
        projects_total: 0,
        health: { critical: 0, watch: 0, healthy: 0 },
        queue_depth_total: 0,
        queue_wait_values: [],
        open_incidents: 0,
        paused_projects: 0,
        governance_events_total: 0,
        governance_resolved_events: 0,
        governance_pending_events: 0,
        governance_mttr_values: [],
        governance_pending_age_values: [],
        governance_sla_breaches: 0,
        projects: [],
      });
    }
    const bucket = bucketMap.get(ownerKey);
    bucket.projects_total += 1;
    if (["critical", "watch", "healthy"].includes(health)) {
      bucket.health[health] += 1;
    } else {
      bucket.health.healthy += 1;
    }
    bucket.queue_depth_total += queueDepth;
    if (queueWaitP90 != null && Number.isFinite(queueWaitP90)) {
      bucket.queue_wait_values.push(Math.max(0, queueWaitP90));
    }
    if (String(item?.incident?.status || "") === "open") {
      bucket.open_incidents += 1;
    }
    if (Boolean(item?.control?.pause_active)) {
      bucket.paused_projects += 1;
    }
    bucket.projects.push({
      project_id: projectId,
      health,
      queue_depth: queueDepth,
      queued_wait_p90_minutes: queueWaitP90,
      pause_active: Boolean(item?.control?.pause_active),
      incident_open: String(item?.incident?.status || "") === "open",
    });
  }

  for (const event of state.queueAuditEvents) {
    const projectId = String(event?.project_id || "");
    const ownerKey = projectToOwner.get(projectId);
    if (!ownerKey) continue;
    const bucket = bucketMap.get(ownerKey);
    if (!bucket) continue;
    const eventMs = new Date(event.created_at).getTime();
    if (!Number.isFinite(eventMs) || eventMs < sinceMs) continue;
    bucket.governance_events_total += 1;
    const annotation = latestQueueAuditAnnotation(event.id);
    if (String(annotation?.status || "") === "resolved") {
      const resolvedMs = new Date(annotation.created_at).getTime();
      if (Number.isFinite(resolvedMs)) {
        bucket.governance_resolved_events += 1;
        bucket.governance_mttr_values.push(Math.max(0, (resolvedMs - eventMs) / (1000 * 60)));
      }
      continue;
    }
    const ageMinutes = Math.max(0, (now - eventMs) / (1000 * 60));
    bucket.governance_pending_events += 1;
    bucket.governance_pending_age_values.push(ageMinutes);
    if (ageMinutes >= Math.max(1, Math.min(168, Number(slaHours || 24))) * 60) {
      bucket.governance_sla_breaches += 1;
    }
  }

  const owners = [...bucketMap.values()]
    .map((bucket) => {
      const queueWaitStats = latencyStats(bucket.queue_wait_values);
      const mttrStats = latencyStats(bucket.governance_mttr_values);
      const pendingAgeStats = latencyStats(bucket.governance_pending_age_values);
      return {
        owner_key: bucket.owner_key,
        owner_name: bucket.owner_name,
        oncall_channel: bucket.oncall_channel,
        owner_contact: bucket.owner_contact,
        escalation_channel: bucket.escalation_channel,
        projects_total: bucket.projects_total,
        health: bucket.health,
        queue_depth_total: bucket.queue_depth_total,
        queue_depth_avg: Number((bucket.queue_depth_total / Math.max(1, bucket.projects_total)).toFixed(3)),
        queue_wait_p90_minutes: queueWaitStats,
        open_incidents: bucket.open_incidents,
        paused_projects: bucket.paused_projects,
        governance: {
          events_total: bucket.governance_events_total,
          resolved_events: bucket.governance_resolved_events,
          pending_events: bucket.governance_pending_events,
          sla_breaches: bucket.governance_sla_breaches,
          mttr_minutes: mttrStats,
          pending_age_minutes: {
            ...pendingAgeStats,
            max: bucket.governance_pending_age_values.length
              ? Number(Math.max(...bucket.governance_pending_age_values).toFixed(3))
              : null,
          },
        },
        projects: [...bucket.projects].sort((a, b) => {
          const rank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
          const rankDelta = rank(String(a.health || "healthy")) - rank(String(b.health || "healthy"));
          if (rankDelta !== 0) return rankDelta;
          const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
          if (depthDelta !== 0) return depthDelta;
          return String(a.project_id || "").localeCompare(String(b.project_id || ""));
        }),
      };
    })
    .sort((a, b) => {
      const criticalDelta = Number(b.health?.critical || 0) - Number(a.health?.critical || 0);
      if (criticalDelta !== 0) return criticalDelta;
      const breachDelta = Number(b.governance?.sla_breaches || 0) - Number(a.governance?.sla_breaches || 0);
      if (breachDelta !== 0) return breachDelta;
      const depthDelta = Number(b.queue_depth_total || 0) - Number(a.queue_depth_total || 0);
      if (depthDelta !== 0) return depthDelta;
      return String(a.owner_name || "").localeCompare(String(b.owner_name || ""));
    });

  return {
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    sla_hours: Math.max(1, Math.min(168, Number(slaHours || 24))),
    requested_projects: dedupRequested,
    generated_at: nowIso(),
    summary: {
      owners_total: owners.length,
      projects_total: projects.length,
      critical_projects: owners.reduce((acc, item) => acc + Number(item.health?.critical || 0), 0),
      watch_projects: owners.reduce((acc, item) => acc + Number(item.health?.watch || 0), 0),
      open_incidents: owners.reduce((acc, item) => acc + Number(item.open_incidents || 0), 0),
      pending_events: owners.reduce((acc, item) => acc + Number(item.governance?.pending_events || 0), 0),
      sla_breaches: owners.reduce((acc, item) => acc + Number(item.governance?.sla_breaches || 0), 0),
    },
    owners,
  };
}

function buildQueueGovernanceDrift(projectIdsRaw, windowHours = 24, auditDays = 7, limit = 50, singleProject = "") {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const compare = buildQueueThroughputCompare(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(200, Number(limit || 50))),
  );
  const digest = buildQueueGovernanceDigest(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(365, Number(auditDays || 7))),
    Math.max(1, Math.min(200, Number(limit || 50))),
    Math.max(5, Math.min(20, Number(limit || 50))),
    explicitSingle,
  );
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  const unreviewedPauses = Array.isArray(digest.unreviewed_pauses) ? digest.unreviewed_pauses : [];

  const pauseAgeBuckets = {
    under_1h: 0,
    between_1h_4h: 0,
    between_4h_12h: 0,
    between_12h_24h: 0,
    over_24h: 0,
  };
  for (const pause of unreviewedPauses) {
    const age = Number(pause?.pause_age_minutes || 0);
    if (age < 60) pauseAgeBuckets.under_1h += 1;
    else if (age < 240) pauseAgeBuckets.between_1h_4h += 1;
    else if (age < 720) pauseAgeBuckets.between_4h_12h += 1;
    else if (age < 1440) pauseAgeBuckets.between_12h_24h += 1;
    else pauseAgeBuckets.over_24h += 1;
  }

  let missingOwner = 0;
  let missingOncall = 0;
  let missingEscalation = 0;
  let criticalWithoutOwner = 0;
  let openIncidentsWithoutOwner = 0;

  const driftProjects = projects
    .map((item) => {
      const projectId = String(item?.project_id || "");
      const ownership = item?.ownership || getQueueOwnership(projectId);
      const ownerName = String(ownership?.owner_name || "").trim();
      const oncallChannel = String(ownership?.oncall_channel || "").trim();
      const escalationChannel = String(ownership?.escalation_channel || "").trim();
      const health = String(item?.health || "healthy");
      const incidentOpen = String(item?.incident?.status || "") === "open";
      const queueDepth = Number(item?.queue?.depth_total || 0);
      const pauseEntry = unreviewedPauses.find((row) => String(row?.project_id || "") === projectId) || null;
      const pauseAgeMinutes = pauseEntry?.pause_age_minutes == null ? null : Number(pauseEntry.pause_age_minutes);
      const missingFields = [];
      if (!ownerName) {
        missingOwner += 1;
        missingFields.push("owner_name");
      }
      if (!oncallChannel) {
        missingOncall += 1;
        missingFields.push("oncall_channel");
      }
      if (!escalationChannel) {
        missingEscalation += 1;
        missingFields.push("escalation_channel");
      }
      if (health === "critical" && !ownerName) criticalWithoutOwner += 1;
      if (incidentOpen && !ownerName) openIncidentsWithoutOwner += 1;
      let riskScore = 0;
      if (health === "critical") riskScore += 3;
      else if (health === "watch") riskScore += 1;
      if (incidentOpen) riskScore += 2;
      if (Boolean(item?.control?.pause_active)) riskScore += 1;
      if (pauseAgeMinutes != null && pauseAgeMinutes >= 240) riskScore += 2;
      riskScore += missingFields.length;
      return {
        project_id: projectId,
        health,
        queue_depth: queueDepth,
        pause_active: Boolean(item?.control?.pause_active),
        pause_age_minutes: pauseAgeMinutes,
        incident_open: incidentOpen,
        ownership: {
          owner_name: ownerName || null,
          oncall_channel: oncallChannel || null,
          escalation_channel: escalationChannel || null,
        },
        missing_fields: missingFields,
        risk_score: riskScore,
      };
    })
    .sort((a, b) => {
      const riskDelta = Number(b.risk_score || 0) - Number(a.risk_score || 0);
      if (riskDelta !== 0) return riskDelta;
      const rank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
      const rankDelta = rank(String(a.health || "healthy")) - rank(String(b.health || "healthy"));
      if (rankDelta !== 0) return rankDelta;
      const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
      if (depthDelta !== 0) return depthDelta;
      return String(a.project_id || "").localeCompare(String(b.project_id || ""));
    });

  const projectsTotal = projects.length;
  return {
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    audit_days: Math.max(1, Math.min(365, Number(auditDays || 7))),
    requested_projects: dedupRequested,
    generated_at: nowIso(),
    summary: {
      projects_total: projectsTotal,
      ownership_coverage: {
        owner_name_rate: projectsTotal ? Number(((projectsTotal - missingOwner) / projectsTotal).toFixed(4)) : 0,
        oncall_channel_rate: projectsTotal ? Number(((projectsTotal - missingOncall) / projectsTotal).toFixed(4)) : 0,
        escalation_channel_rate: projectsTotal ? Number(((projectsTotal - missingEscalation) / projectsTotal).toFixed(4)) : 0,
        missing_owner_name: missingOwner,
        missing_oncall_channel: missingOncall,
        missing_escalation_channel: missingEscalation,
      },
      unresolved_pauses: unreviewedPauses.length,
      critical_without_owner: criticalWithoutOwner,
      open_incidents_without_owner: openIncidentsWithoutOwner,
    },
    pause_age_buckets: pauseAgeBuckets,
    drift_projects: driftProjects,
  };
}

function buildQueueIncidentSloBoard(
  projectIdsRaw,
  windowHours = 24,
  incidentWindowDays = 30,
  mttrSlaHours = 24,
  mttaProxySlaMinutes = 15,
  rotationLagSlaHours = 168,
  secretMaxAgeDays = 30,
  limit = 50,
  topN = 12,
  singleProject = "",
) {
  const explicitSingle = String(singleProject || "").trim();
  const requestedFromCsv = parseCsvProjects(projectIdsRaw);
  const requested = explicitSingle ? [explicitSingle, ...requestedFromCsv] : requestedFromCsv;
  const dedupRequested = requested.filter((item, index, all) => all.indexOf(item) === index);
  const compare = buildQueueThroughputCompare(
    dedupRequested.join(","),
    Math.max(1, Math.min(168, Number(windowHours || 24))),
    Math.max(1, Math.min(200, Number(limit || 50))),
  );
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  const nowMs = Date.now();
  const incidentWindowMs = Math.max(1, Math.min(180, Number(incidentWindowDays || 30))) * 24 * 60 * 60 * 1000;
  const incidentSinceMs = nowMs - incidentWindowMs;
  const mttrSlaMinutesNorm = Math.max(1, Math.min(168, Number(mttrSlaHours || 24))) * 60;
  const mttaProxySlaMinutesNorm = Math.max(1, Math.min(1440, Number(mttaProxySlaMinutes || 15)));
  const rotationLagSlaHoursNorm = Math.max(1, Math.min(2160, Number(rotationLagSlaHours || 168)));
  const secretMaxAgeHoursNorm = Math.max(1, Math.min(365, Number(secretMaxAgeDays || 30))) * 24;
  const trendDays = Math.max(7, Math.min(30, Number(incidentWindowDays || 30)));
  const trendStartMs = nowMs - (trendDays - 1) * 24 * 60 * 60 * 1000;
  const trendBuckets = new Map();
  for (let idx = 0; idx < trendDays; idx += 1) {
    const day = new Date(trendStartMs + idx * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    trendBuckets.set(day, {
      day,
      opened_incidents: 0,
      resolved_incidents: 0,
      mtta_values: [],
      mttr_values: [],
    });
  }

  const globalMtta = [];
  const globalMttr = [];
  let openIncidents = 0;
  let openOverMttrSla = 0;
  let resolvedWindow = 0;
  let rotationLagOver = 0;
  let secretRequiredTotal = 0;
  let secretMissingTotal = 0;
  let secretStaleTotal = 0;
  const secretPosture = { healthy: 0, watch: 0, critical: 0 };
  const sloStatusCounts = { healthy: 0, watch: 0, critical: 0 };
  const rows = [];

  for (const item of projects) {
    const projectId = String(item?.project_id || "");
    if (!projectId) continue;
    const health = String(item?.health || "healthy");
    const queueDepth = Number(item?.queue?.depth_total || 0);
    const ownership = item?.ownership || getQueueOwnership(projectId);
    const ownerName = String(ownership?.owner_name || "").trim();
    const oncallChannel = String(ownership?.oncall_channel || "").trim();
    const escalationChannel = String(ownership?.escalation_channel || "").trim();
    const ownerContact = String(ownership?.owner_contact || "").trim();
    const ownershipUpdatedMs = ownership?.updated_at ? new Date(ownership.updated_at).getTime() : NaN;
    const rotationLagHours =
      Number.isFinite(ownershipUpdatedMs) ? Number(((nowMs - ownershipUpdatedMs) / (1000 * 60 * 60)).toFixed(3)) : null;
    const rotationLagOverSla = rotationLagHours != null && rotationLagHours >= rotationLagSlaHoursNorm;
    if (rotationLagOverSla) rotationLagOver += 1;

    const incidents = state.queueIncidents.filter((row) => String(row.project_id || "") === projectId);
    const projectMtta = [];
    const projectMttr = [];
    let resolvedCountWindow = 0;
    let latestResolvedTs = null;
    let latestResolvedMttr = null;
    for (const incident of incidents) {
      const openedAtIso = incident?.opened_at ? String(incident.opened_at) : null;
      const openedMs = openedAtIso ? new Date(openedAtIso).getTime() : NaN;
      if (!Number.isFinite(openedMs)) continue;
      const mttaProxyIso = queueIncidentMttaProxyTimestamp(openedAtIso, incident?.last_sync_at || null, incident?.open_payload || {});
      const mttaProxyMs = mttaProxyIso ? new Date(mttaProxyIso).getTime() : NaN;
      let mttaMinutes = null;
      if (openedMs >= incidentSinceMs && Number.isFinite(mttaProxyMs)) {
        mttaMinutes = Number(Math.max(0, (mttaProxyMs - openedMs) / (1000 * 60)).toFixed(3));
        projectMtta.push(mttaMinutes);
        globalMtta.push(mttaMinutes);
      }
      const openedDay = new Date(openedMs).toISOString().slice(0, 10);
      if (trendBuckets.has(openedDay)) {
        const bucket = trendBuckets.get(openedDay);
        bucket.opened_incidents += 1;
        if (mttaMinutes != null) bucket.mtta_values.push(mttaMinutes);
      }
      const resolvedMs = incident?.resolved_at ? new Date(incident.resolved_at).getTime() : NaN;
      if (!Number.isFinite(resolvedMs) || resolvedMs < incidentSinceMs) continue;
      const mttrMinutes = Number(Math.max(0, (resolvedMs - openedMs) / (1000 * 60)).toFixed(3));
      projectMttr.push(mttrMinutes);
      globalMttr.push(mttrMinutes);
      resolvedCountWindow += 1;
      resolvedWindow += 1;
      if (latestResolvedTs == null || resolvedMs > latestResolvedTs) {
        latestResolvedTs = resolvedMs;
        latestResolvedMttr = mttrMinutes;
      }
      const resolvedDay = new Date(resolvedMs).toISOString().slice(0, 10);
      if (trendBuckets.has(resolvedDay)) {
        const bucket = trendBuckets.get(resolvedDay);
        bucket.resolved_incidents += 1;
        bucket.mttr_values.push(mttrMinutes);
      }
    }

    const projectMttaStats = latencyStats(projectMtta);
    const projectMttrStats = latencyStats(projectMttr);

    const openIncident = item?.incident && item.incident.status === "open" ? item.incident : null;
    let openIncidentAgeMinutes = null;
    let openMttaProxyMinutes = null;
    if (openIncident) {
      openIncidents += 1;
      const openedMs = openIncident?.opened_at ? new Date(openIncident.opened_at).getTime() : NaN;
      if (Number.isFinite(openedMs)) {
        openIncidentAgeMinutes = Number(Math.max(0, (nowMs - openedMs) / (1000 * 60)).toFixed(3));
      }
      const openMttaIso = queueIncidentMttaProxyTimestamp(
        openIncident?.opened_at || null,
        openIncident?.last_sync_at || null,
        openIncident?.open_payload || {},
      );
      const openMttaMs = openMttaIso ? new Date(openMttaIso).getTime() : NaN;
      if (Number.isFinite(openMttaMs) && Number.isFinite(openedMs)) {
        openMttaProxyMinutes = Number(Math.max(0, (openMttaMs - openedMs) / (1000 * 60)).toFixed(3));
      }
    }

    let mttrOverSla = false;
    if (openIncidentAgeMinutes != null && openIncidentAgeMinutes >= mttrSlaMinutesNorm) {
      mttrOverSla = true;
      openOverMttrSla += 1;
    } else if (projectMttrStats?.p90 != null && Number(projectMttrStats.p90) >= mttrSlaMinutesNorm) {
      mttrOverSla = true;
    }
    const mttaSloValue = openMttaProxyMinutes != null ? openMttaProxyMinutes : projectMttaStats?.p90 ?? null;
    const mttaOverSla = mttaSloValue != null && Number(mttaSloValue) >= mttaProxySlaMinutesNorm;

    const hook = getQueueIncidentHook(projectId);
    const policies = state.queueIncidentPolicies.filter((row) => String(row.project_id || "") === projectId);
    const requiredSecretRefs = [];
    if (hook.enabled) {
      for (const key of incidentProviderSecretKeys(normalizeIncidentProvider(hook.provider))) {
        requiredSecretRefs.push({
          scope: "hook",
          scope_ref: projectId,
          provider: normalizeIncidentProvider(hook.provider),
          secret_key: key,
          value: hook?.provider_config?.[key],
          updated_at: hook?.updated_at || hook?.created_at || null,
        });
      }
    }
    for (const policy of policies) {
      if (!policy.enabled) continue;
      const provider = normalizeIncidentProvider(policy.provider_override);
      if (provider === "webhook") continue;
      for (const key of incidentProviderSecretKeys(provider)) {
        requiredSecretRefs.push({
          scope: "policy",
          scope_ref: String(policy.id || ""),
          provider,
          secret_key: key,
          value: policy?.provider_config_override?.[key],
          updated_at: policy?.updated_at || policy?.created_at || null,
        });
      }
    }

    secretRequiredTotal += requiredSecretRefs.length;
    let secretConfigured = 0;
    let secretMissing = 0;
    let secretStale = 0;
    let oldestSecretAgeHours = null;
    const staleKeys = [];
    for (const ref of requiredSecretRefs) {
      const value = String(ref.value || "").trim();
      if (!value) {
        secretMissing += 1;
        continue;
      }
      secretConfigured += 1;
      const updatedMs = ref.updated_at ? new Date(ref.updated_at).getTime() : NaN;
      if (!Number.isFinite(updatedMs)) {
        secretStale += 1;
        staleKeys.push({ ...ref, age_hours: null });
        continue;
      }
      const ageHours = Number(Math.max(0, (nowMs - updatedMs) / (1000 * 60 * 60)).toFixed(3));
      if (oldestSecretAgeHours == null || ageHours > oldestSecretAgeHours) {
        oldestSecretAgeHours = ageHours;
      }
      if (ageHours >= secretMaxAgeHoursNorm) {
        secretStale += 1;
        staleKeys.push({
          scope: ref.scope,
          scope_ref: ref.scope_ref,
          provider: ref.provider,
          secret_key: ref.secret_key,
          age_hours: ageHours,
        });
      }
    }
    secretMissingTotal += secretMissing;
    secretStaleTotal += secretStale;
    let secretPostureStatus = "healthy";
    if (secretMissing > 0) secretPostureStatus = "critical";
    else if (secretStale > 0) secretPostureStatus = "watch";
    secretPosture[secretPostureStatus] += 1;

    let riskScore = 0;
    if (health === "critical") riskScore += 3;
    else if (health === "watch") riskScore += 1;
    if (queueDepth >= 20) riskScore += 2;
    else if (queueDepth > 0) riskScore += 1;
    if (mttrOverSla) riskScore += 3;
    if (mttaOverSla) riskScore += 1;
    if (rotationLagOverSla) riskScore += 1;
    if (!ownerName) riskScore += 1;
    if (!oncallChannel) riskScore += 1;
    if (!escalationChannel) riskScore += 1;
    riskScore += secretMissing * 2;
    riskScore += secretStale;
    const sloStatus = riskScore >= 8 ? "critical" : riskScore >= 4 ? "watch" : "healthy";
    sloStatusCounts[sloStatus] += 1;

    rows.push({
      project_id: projectId,
      health,
      queue_depth: queueDepth,
      slo_status: sloStatus,
      risk_score: riskScore,
      incident: {
        open: Boolean(openIncident),
        external_provider: String(openIncident?.external_provider || ""),
        open_age_minutes: openIncidentAgeMinutes,
        mtta_proxy_minutes: openMttaProxyMinutes,
        mtta_proxy_p90_minutes: projectMttaStats?.p90 ?? null,
        mttr_last_minutes: latestResolvedMttr,
        mttr_p90_minutes: projectMttrStats?.p90 ?? null,
        resolved_incidents_window: resolvedCountWindow,
      },
      ownership: {
        owner_name: ownerName || null,
        owner_contact: ownerContact || null,
        oncall_channel: oncallChannel || null,
        escalation_channel: escalationChannel || null,
        updated_at: ownership?.updated_at || null,
        rotation_lag_hours: rotationLagHours,
        rotation_lag_over_sla: Boolean(rotationLagOverSla),
      },
      secrets: {
        required: requiredSecretRefs.length,
        configured: secretConfigured,
        missing_required: secretMissing,
        stale_required: secretStale,
        oldest_age_hours: oldestSecretAgeHours,
        posture: secretPostureStatus,
        stale_keys: staleKeys.slice(0, 8),
      },
      slo: {
        mtta_proxy_sla_minutes: mttaProxySlaMinutesNorm,
        mtta_proxy_value_minutes: mttaSloValue,
        mtta_proxy_over_sla: Boolean(mttaOverSla),
        mttr_sla_minutes: mttrSlaMinutesNorm,
        mttr_value_minutes: openIncidentAgeMinutes != null ? openIncidentAgeMinutes : projectMttrStats?.p90 ?? null,
        mttr_over_sla: Boolean(mttrOverSla),
        rotation_lag_sla_hours: rotationLagSlaHoursNorm,
        rotation_lag_over_sla: Boolean(rotationLagOverSla),
        secret_max_age_hours: secretMaxAgeHoursNorm,
        secret_missing_required: secretMissing,
        secret_stale_required: secretStale,
      },
    });
  }

  const healthRank = (value) => (value === "critical" ? 0 : value === "watch" ? 1 : 2);
  rows.sort((a, b) => {
    const statusDelta = healthRank(String(a.slo_status || "healthy")) - healthRank(String(b.slo_status || "healthy"));
    if (statusDelta !== 0) return statusDelta;
    const riskDelta = Number(b.risk_score || 0) - Number(a.risk_score || 0);
    if (riskDelta !== 0) return riskDelta;
    const healthDelta = healthRank(String(a.health || "healthy")) - healthRank(String(b.health || "healthy"));
    if (healthDelta !== 0) return healthDelta;
    const ageDelta = Number(b?.incident?.open_age_minutes || 0) - Number(a?.incident?.open_age_minutes || 0);
    if (ageDelta !== 0) return ageDelta;
    const depthDelta = Number(b.queue_depth || 0) - Number(a.queue_depth || 0);
    if (depthDelta !== 0) return depthDelta;
    return String(a.project_id || "").localeCompare(String(b.project_id || ""));
  });

  const trends = [...trendBuckets.values()]
    .sort((a, b) => String(a.day).localeCompare(String(b.day)))
    .map((bucket) => {
      const mttaStats = latencyStats(bucket.mtta_values);
      const mttrStats = latencyStats(bucket.mttr_values);
      return {
        day: bucket.day,
        opened_incidents: bucket.opened_incidents,
        resolved_incidents: bucket.resolved_incidents,
        mtta_proxy_minutes_avg: mttaStats.avg,
        mtta_proxy_minutes_p90: mttaStats.p90,
        mttr_minutes_avg: mttrStats.avg,
        mttr_minutes_p90: mttrStats.p90,
      };
    });

  return {
    window_hours: Math.max(1, Math.min(168, Number(windowHours || 24))),
    incident_window_days: Math.max(1, Math.min(180, Number(incidentWindowDays || 30))),
    mttr_sla_hours: Math.max(1, Math.min(168, Number(mttrSlaHours || 24))),
    mtta_proxy_sla_minutes: mttaProxySlaMinutesNorm,
    rotation_lag_sla_hours: rotationLagSlaHoursNorm,
    secret_max_age_days: Math.max(1, Math.min(365, Number(secretMaxAgeDays || 30))),
    requested_projects: dedupRequested,
    generated_at: nowIso(),
    summary: {
      projects_total: rows.length,
      open_incidents: openIncidents,
      open_incidents_over_mttr_sla: openOverMttrSla,
      resolved_incidents_window: resolvedWindow,
      mtta_proxy_minutes: latencyStats(globalMtta),
      mttr_minutes: latencyStats(globalMttr),
      projects_mtta_over_sla: rows.filter((item) => Boolean(item?.slo?.mtta_proxy_over_sla)).length,
      projects_mttr_over_sla: rows.filter((item) => Boolean(item?.slo?.mttr_over_sla)).length,
      rotation_lag_projects_over_sla: rotationLagOver,
      secret_required_total: secretRequiredTotal,
      secret_missing_required: secretMissingTotal,
      secret_stale_required: secretStaleTotal,
      secret_posture: secretPosture,
      slo_status: sloStatusCounts,
    },
    trends,
    leaderboard: rows.slice(0, Math.max(1, Math.min(50, Number(topN || 12)))),
    projects: rows,
  };
}

function queryParam(url, key) {
  return url.searchParams.get(key);
}

function makeRollbackPreview(projectId, snapshotId) {
  const snapshot = snapshots.find((item) => item.id === snapshotId && item.project_id === projectId) || snapshots[0];
  return {
    project_id: projectId,
    snapshot_id: snapshot?.id || snapshotId,
    snapshot: snapshot || null,
    lookback_days: 30,
    limit: 5000,
    config_diff: {
      min_score_for_golden: {
        current: 0.72,
        target: snapshot?.config?.min_score_for_golden ?? 0.7,
      },
    },
    impact: {
      decisions_scanned: 120,
      changed_total: 22,
      changed_ratio: 0.1833,
      changed_from_golden: 6,
      changed_to_golden: 2,
      risk_level: "medium",
      tier_counts_current: {
        operational_memory: 20,
        insight_candidate: 70,
        golden_candidate: 30,
      },
      tier_counts_target_estimated: {
        operational_memory: 24,
        insight_candidate: 72,
        golden_candidate: 24,
      },
      transitions: {
        "golden_candidate->insight_candidate": 5,
        "insight_candidate->golden_candidate": 2,
      },
    },
    changed_samples: [
      {
        claim_id: "claim-1",
        from_tier: "golden_candidate",
        to_tier: "insight_candidate",
        score_current: 0.78,
        score_estimated: 0.68,
        updated_at: "2026-03-31T03:00:00Z",
        reason: "threshold delta on score floor",
      },
    ],
    generated_at: nowIso(),
  };
}

function quantile(values, q) {
  if (!values.length) {
    return null;
  }
  const points = [...values].sort((a, b) => a - b);
  if (points.length === 1) {
    return Number(points[0].toFixed(3));
  }
  const rank = (points.length - 1) * Math.max(0, Math.min(1, q));
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) {
    return Number(points[low].toFixed(3));
  }
  const weight = rank - low;
  return Number((points[low] * (1 - weight) + points[high] * weight).toFixed(3));
}

function latencyStats(values) {
  if (!values.length) {
    return { count: 0, avg: null, p50: null, p90: null };
  }
  const avg = Number((values.reduce((acc, item) => acc + item, 0) / values.length).toFixed(3));
  return {
    count: values.length,
    avg,
    p50: quantile(values, 0.5),
    p90: quantile(values, 0.9),
  };
}

function ratio(numerator, denominator) {
  if (!denominator) {
    return 0;
  }
  return Number((numerator / denominator).toFixed(4));
}

function rankCounter(counter, keyName, total, top) {
  return [...counter.entries()]
    .sort((a, b) => (b[1] - a[1]) || String(a[0]).localeCompare(String(b[0])))
    .slice(0, top)
    .map(([key, count]) => ({
      [keyName]: key,
      count,
      share: ratio(count, total || 1),
    }));
}

function computeRollbackMetrics(projectId, days, slaHours) {
  const now = Date.now();
  const since = new Date(now - Math.max(1, days) * 24 * 60 * 60 * 1000);
  const requests = state.rollbackRequests.filter((item) => {
    if (item.project_id !== projectId) {
      return false;
    }
    const createdAt = new Date(item.created_at);
    return Number.isFinite(createdAt.getTime()) && createdAt.getTime() >= since.getTime();
  });

  const statusCounts = new Map([
    ["pending_approval", 0],
    ["applied", 0],
    ["rejected", 0],
    ["failed", 0],
    ["other", 0],
  ]);
  const rejectionCauses = new Map();
  const riskLevels = new Map();
  const riskDrivers = new Map();
  const transitionDrivers = new Map();
  const firstApprovalHours = [];
  const resolutionHours = [];
  const pendingSlaBreaches = [];

  for (const request of requests) {
    const status = String(request.status || "other");
    statusCounts.set(statusCounts.has(status) ? status : "other", (statusCounts.get(status) || 0) + 1);

    if (status === "rejected") {
      const reason = String(request.rejection_reason || "").trim() || "unspecified";
      rejectionCauses.set(reason, (rejectionCauses.get(reason) || 0) + 1);
    }

    const riskLevel = String(request.preview?.impact?.risk_level || "unknown");
    riskLevels.set(riskLevel, (riskLevels.get(riskLevel) || 0) + 1);

    const configDiff = request.preview?.config_diff;
    if (configDiff && typeof configDiff === "object") {
      for (const key of Object.keys(configDiff)) {
        riskDrivers.set(key, (riskDrivers.get(key) || 0) + 1);
      }
    }

    const transitions = request.preview?.impact?.transitions;
    if (transitions && typeof transitions === "object") {
      for (const [transition, countRaw] of Object.entries(transitions)) {
        const count = Number(countRaw || 0);
        if (Number.isFinite(count) && count > 0) {
          transitionDrivers.set(transition, (transitionDrivers.get(transition) || 0) + count);
        }
      }
    }

    const createdAt = new Date(request.created_at);
    if (!Number.isFinite(createdAt.getTime())) {
      continue;
    }
    const approvalEvents = Array.isArray(request.approvals)
      ? request.approvals.filter((item) => item && item.action === "approved")
      : [];
    const approvalTimes = approvalEvents
      .map((item) => new Date(item.created_at))
      .filter((item) => Number.isFinite(item.getTime()))
      .map((item) => item.getTime());
    if (approvalTimes.length > 0) {
      const first = Math.min(...approvalTimes);
      firstApprovalHours.push(Math.max(0, (first - createdAt.getTime()) / (1000 * 60 * 60)));
    }
    if (request.resolved_at) {
      const resolvedAt = new Date(request.resolved_at);
      if (Number.isFinite(resolvedAt.getTime())) {
        resolutionHours.push(Math.max(0, (resolvedAt.getTime() - createdAt.getTime()) / (1000 * 60 * 60)));
      }
    }
    if (status === "pending_approval") {
      const ageHours = Math.max(0, (Date.now() - createdAt.getTime()) / (1000 * 60 * 60));
      if (ageHours >= slaHours) {
        pendingSlaBreaches.push({
          request_id: request.id,
          age_hours: Number(ageHours.toFixed(3)),
          risk_level,
          created_at: request.created_at,
        });
      }
    }
  }

  const total = requests.length;
  const applied = statusCounts.get("applied") || 0;
  const rejected = statusCounts.get("rejected") || 0;
  const failed = statusCounts.get("failed") || 0;
  const resolvedTotal = applied + rejected + failed;

  const rejectionTotal = [...rejectionCauses.values()].reduce((acc, item) => acc + item, 0);
  const riskTotal = [...riskLevels.values()].reduce((acc, item) => acc + item, 0);
  const riskDriverTotal = [...riskDrivers.values()].reduce((acc, item) => acc + item, 0);
  const transitionTotal = [...transitionDrivers.values()].reduce((acc, item) => acc + item, 0);
  pendingSlaBreaches.sort((a, b) => (b.age_hours - a.age_hours) || String(a.request_id).localeCompare(String(b.request_id)));
  const maxPendingAge = pendingSlaBreaches.length ? pendingSlaBreaches[0].age_hours : null;

  return {
    project_id: projectId,
    days,
    sla_hours: slaHours,
    limit: 5000,
    sampled_requests: total,
    since: since.toISOString(),
    summary: {
      total_requests: total,
      pending_approval: statusCounts.get("pending_approval") || 0,
      applied,
      rejected,
      failed,
      other: statusCounts.get("other") || 0,
      resolved_total: resolvedTotal,
      approval_rate: ratio(applied, total),
      rejection_rate: ratio(rejected, total),
      failure_rate: ratio(failed, total),
      resolution_rate: ratio(resolvedTotal, total),
      pending_sla_breaches: pendingSlaBreaches.length,
      max_pending_age_hours: maxPendingAge,
    },
    lead_time_hours: {
      first_approval: latencyStats(firstApprovalHours),
      resolution: latencyStats(resolutionHours),
    },
    rejection_causes: rankCounter(rejectionCauses, "reason", rejectionTotal, 6),
    risk_levels: rankCounter(riskLevels, "risk_level", riskTotal || total, 6),
    top_risk_drivers: rankCounter(riskDrivers, "driver", riskDriverTotal, 8),
    transition_drivers: rankCounter(transitionDrivers, "transition", transitionTotal, 8),
    pending_sla_breaches: pendingSlaBreaches.slice(0, 20),
    generated_at: nowIso(),
  };
}

function computeRollbackAttribution(projectId, days, groupBy) {
  const since = new Date(Date.now() - Math.max(1, days) * 24 * 60 * 60 * 1000);
  const requests = state.rollbackRequests.filter((item) => {
    if (item.project_id !== projectId) return false;
    const createdAt = new Date(item.created_at);
    return Number.isFinite(createdAt.getTime()) && createdAt >= since;
  });
  const cohorts = new Map();
  const timeline = new Map();

  for (const request of requests) {
    const approvals = Array.isArray(request.approvals)
      ? request.approvals.filter((item) => item && item.action === "approved")
      : [];
    const createdAt = new Date(request.created_at);
    const firstApprovedAt = approvals
      .map((item) => new Date(item.created_at))
      .filter((item) => Number.isFinite(item.getTime()))
      .sort((a, b) => a.getTime() - b.getTime())[0];
    const firstLead = firstApprovedAt
      ? Math.max(0, (firstApprovedAt.getTime() - createdAt.getTime()) / (1000 * 60 * 60))
      : null;

    for (const approval of approvals) {
      const actor = String(approval.actor || "unknown");
      const cohortKey =
        groupBy === "actor"
          ? actor
          : (actor.split(/[@:\/_-]/)[0] || actor || "unknown").toLowerCase();
      const current = cohorts.get(cohortKey) || {
        cohort: cohortKey,
        approvals: 0,
        requests_involved: new Set(),
        applied_involved: 0,
        rejected_involved: 0,
        failed_involved: 0,
        first_leads: [],
        latest_approval_at: null,
      };
      current.approvals += 1;
      current.requests_involved.add(request.id);
      if (request.status === "applied") current.applied_involved += 1;
      if (request.status === "rejected") current.rejected_involved += 1;
      if (request.status === "failed") current.failed_involved += 1;
      if (firstLead != null && approval.created_at === firstApprovedAt?.toISOString()) {
        current.first_leads.push(firstLead);
      }
      current.latest_approval_at = approval.created_at || current.latest_approval_at;
      cohorts.set(cohortKey, current);
    }

    if (request.resolved_at && ["applied", "rejected", "failed"].includes(request.status)) {
      const day = String(request.resolved_at).slice(0, 10);
      const bucket = timeline.get(day) || { applied: 0, rejected: 0, failed: 0, resolved_total: 0 };
      bucket[request.status] += 1;
      bucket.resolved_total += 1;
      timeline.set(day, bucket);
    }
  }

  const cohortsOut = [...cohorts.values()]
    .map((item) => {
      const totalDecisions = item.applied_involved + item.rejected_involved + item.failed_involved;
      const avgLead = item.first_leads.length
        ? Number((item.first_leads.reduce((acc, value) => acc + value, 0) / item.first_leads.length).toFixed(3))
        : null;
      return {
        cohort: item.cohort,
        approvals: item.approvals,
        requests_involved: item.requests_involved.size,
        applied_involved: item.applied_involved,
        rejected_involved: item.rejected_involved,
        failed_involved: item.failed_involved,
        applied_rate: totalDecisions ? Number((item.applied_involved / totalDecisions).toFixed(4)) : 0,
        avg_first_approval_lead_hours: avgLead,
        p50_first_approval_lead_hours: avgLead,
        latest_approval_at: item.latest_approval_at,
      };
    })
    .sort((a, b) => (b.approvals - a.approvals) || String(a.cohort).localeCompare(String(b.cohort)));

  const timelineOut = [...timeline.entries()]
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([day, item]) => ({ day, ...item }));
  const resolvedTotal = timelineOut.reduce((acc, item) => acc + item.resolved_total, 0);
  const appliedTotal = timelineOut.reduce((acc, item) => acc + item.applied, 0);

  return {
    project_id: projectId,
    days,
    group_by: groupBy,
    sampled_requests: requests.length,
    since: since.toISOString(),
    cohorts: cohortsOut,
    timeline: timelineOut,
    summary: {
      cohorts_total: cohortsOut.length,
      resolved_total: resolvedTotal,
      applied_total: appliedTotal,
      applied_rate: resolvedTotal ? Number((appliedTotal / resolvedTotal).toFixed(4)) : 0,
    },
    generated_at: nowIso(),
  };
}

function rollbackAttributionGroupKey(actor, groupBy) {
  const text = String(actor || "").trim();
  if (!text) {
    return "unknown";
  }
  if (groupBy === "cohort") {
    return (text.split(/[@:\/_-]/)[0] || text || "unknown").toLowerCase();
  }
  return text;
}

function computeRollbackAttributionDrilldown(projectId, days, groupBy, cohort, requestLimit = 120) {
  const target = String(cohort || "").trim();
  const since = new Date(Date.now() - Math.max(1, days) * 24 * 60 * 60 * 1000);
  const requests = state.rollbackRequests.filter((item) => {
    if (item.project_id !== projectId) {
      return false;
    }
    const createdAt = new Date(item.created_at);
    return Number.isFinite(createdAt.getTime()) && createdAt >= since;
  });

  const rows = [];
  const timeline = new Map();
  const statusCounts = new Map([
    ["pending_approval", 0],
    ["applied", 0],
    ["rejected", 0],
    ["failed", 0],
    ["other", 0],
  ]);
  const firstLeadHours = [];
  const resolutionLeadHours = [];
  let approvalsTotal = 0;
  let latestApprovalAt = null;

  for (const request of requests) {
    const createdAt = new Date(request.created_at);
    if (!Number.isFinite(createdAt.getTime())) {
      continue;
    }
    const status = String(request.status || "other");
    const approvalEvents = Array.isArray(request.approvals)
      ? request.approvals.filter((event) => event && typeof event === "object")
      : [];
    const approved = [];
    const trace = [];
    let rejectedActor = null;
    for (const event of approvalEvents) {
      const action = String(event.action || "unknown").trim() || "unknown";
      const actor = String(event.actor || "").trim() || null;
      const eventAtRaw = event.created_at == null ? null : String(event.created_at);
      const eventAt = eventAtRaw ? new Date(eventAtRaw) : null;
      const eventIso = eventAt && Number.isFinite(eventAt.getTime()) ? eventAt.toISOString() : null;
      if (action === "approved" && actor && eventIso) {
        approved.push({ actor, created_at: eventIso });
      }
      if (action === "rejected" && actor) {
        rejectedActor = actor;
      }
      trace.push({
        event_type: action,
        actor,
        created_at: eventIso,
        note: event.note == null ? null : String(event.note),
        matched: action === "approved" && actor ? rollbackAttributionGroupKey(actor, groupBy) === target : false,
      });
    }
    approved.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
    const matched = approved.filter((item) => rollbackAttributionGroupKey(item.actor, groupBy) === target);
    if (matched.length === 0) {
      continue;
    }

    approvalsTotal += matched.length;
    statusCounts.set(statusCounts.has(status) ? status : "other", (statusCounts.get(status) || 0) + 1);
    for (const item of matched) {
      if (!latestApprovalAt || String(item.created_at) > String(latestApprovalAt)) {
        latestApprovalAt = item.created_at;
      }
    }

    const firstApproved = approved[0] || null;
    const firstLead =
      firstApproved && firstApproved.created_at
        ? Math.max(0, (new Date(firstApproved.created_at).getTime() - createdAt.getTime()) / (1000 * 60 * 60))
        : null;
    if (firstLead != null && rollbackAttributionGroupKey(firstApproved.actor, groupBy) === target) {
      firstLeadHours.push(firstLead);
    }

    let resolutionLead = null;
    if (request.resolved_at) {
      const resolvedAt = new Date(request.resolved_at);
      if (Number.isFinite(resolvedAt.getTime())) {
        resolutionLead = Math.max(0, (resolvedAt.getTime() - createdAt.getTime()) / (1000 * 60 * 60));
        resolutionLeadHours.push(resolutionLead);
        if (["applied", "rejected", "failed"].includes(status)) {
          const day = String(request.resolved_at).slice(0, 10);
          const bucket = timeline.get(day) || { applied: 0, rejected: 0, failed: 0, resolved_total: 0 };
          bucket[status] += 1;
          bucket.resolved_total += 1;
          timeline.set(day, bucket);
        }
      }
    }

    if (request.resolved_at && ["applied", "rejected", "failed"].includes(status)) {
      const hasTerminal = trace.some(
        (item) => item.event_type === status && String(item.created_at || "") === String(request.resolved_at),
      );
      if (!hasTerminal) {
        trace.push({
          event_type: status,
          actor: status === "applied" ? String(request.applied_by || "") || null : rejectedActor,
          created_at: String(request.resolved_at),
          note:
            status === "rejected"
              ? String(request.rejection_reason || "") || null
              : String(request.error_message || "") || null,
          matched: false,
        });
      }
    }
    trace.sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));

    const transitions = request.preview?.impact?.transitions && typeof request.preview.impact.transitions === "object"
      ? request.preview.impact.transitions
      : {};
    const topTransitions = Object.entries(transitions)
      .map(([transition, count]) => ({ transition, count: Number(count || 0) }))
      .filter((item) => Number.isFinite(item.count) && item.count > 0)
      .sort((a, b) => (b.count - a.count) || String(a.transition).localeCompare(String(b.transition)))
      .slice(0, 6);

    rows.push({
      request_id: request.id,
      snapshot_id: request.snapshot_id,
      status,
      requested_by: request.requested_by,
      required_approvals: Number(request.required_approvals || 0),
      approval_count: approved.length,
      matched_approvals: matched.length,
      matched_actors: [...new Set(matched.map((item) => item.actor))].sort(),
      approvers: [...new Set(approved.map((item) => item.actor))].sort(),
      cohorts: [...new Set(approved.map((item) => rollbackAttributionGroupKey(item.actor, "cohort")))].sort(),
      created_at: request.created_at,
      resolved_at: request.resolved_at || null,
      first_approval_at: firstApproved ? firstApproved.created_at : null,
      first_approval_lead_hours: firstLead == null ? null : Number(firstLead.toFixed(4)),
      resolution_lead_hours: resolutionLead == null ? null : Number(resolutionLead.toFixed(4)),
      risk_level: String(request.preview?.impact?.risk_level || "unknown"),
      changed_ratio: Number(request.preview?.impact?.changed_ratio || 0),
      changed_total: Number(request.preview?.impact?.changed_total || 0),
      decisions_scanned: Number(request.preview?.impact?.decisions_scanned || 0),
      config_diff_keys:
        request.preview?.config_diff && typeof request.preview.config_diff === "object"
          ? Object.keys(request.preview.config_diff).slice(0, 8)
          : [],
      top_transitions: topTransitions,
      note: request.note == null ? null : String(request.note),
      rejection_reason: request.rejection_reason == null ? null : String(request.rejection_reason),
      error_message: request.error_message == null ? null : String(request.error_message),
      causal_trace: trace.slice(0, 30),
    });
  }

  rows.sort((a, b) => String(b.resolved_at || b.created_at).localeCompare(String(a.resolved_at || a.created_at)));
  const timelineOut = [...timeline.entries()]
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([day, item]) => ({ day, ...item }));
  const applied = statusCounts.get("applied") || 0;
  const rejected = statusCounts.get("rejected") || 0;
  const failed = statusCounts.get("failed") || 0;
  const resolvedTotal = applied + rejected + failed;

  return {
    project_id: projectId,
    cohort: target,
    group_by: groupBy,
    days,
    since: since.toISOString(),
    sample_limit: 5000,
    request_limit: requestLimit,
    sampled_requests: requests.length,
    summary: {
      approvals: approvalsTotal,
      requests_involved: rows.length,
      pending_approval: statusCounts.get("pending_approval") || 0,
      applied,
      rejected,
      failed,
      other: statusCounts.get("other") || 0,
      resolved_total: resolvedTotal,
      applied_rate: resolvedTotal ? Number((applied / resolvedTotal).toFixed(4)) : 0,
      resolution_rate: rows.length ? Number((resolvedTotal / rows.length).toFixed(4)) : 0,
      avg_first_approval_lead_hours: latencyStats(firstLeadHours).avg,
      p50_first_approval_lead_hours: latencyStats(firstLeadHours).p50,
      p90_first_approval_lead_hours: latencyStats(firstLeadHours).p90,
      avg_resolution_lead_hours: latencyStats(resolutionLeadHours).avg,
      p50_resolution_lead_hours: latencyStats(resolutionLeadHours).p50,
      p90_resolution_lead_hours: latencyStats(resolutionLeadHours).p90,
      latest_approval_at: latestApprovalAt,
    },
    timeline: timelineOut,
    requests: rows.slice(0, requestLimit),
    generated_at: nowIso(),
  };
}

function buildCalibrationOperationPayload(projectId, { dryRun, forceRun, skipDueCheck }) {
  const now = nowIso();
  const results = state.schedules
    .filter((item) => item.project_id === projectId && item.enabled)
    .map((item) => {
      const intervalHours = Number(item.interval_hours || (item.preset === "weekly" ? 168 : 24));
      const lastSnapshotAt = item.last_run_at || "2026-03-31T05:00:00Z";
      const lastRunMs = new Date(lastSnapshotAt).getTime();
      const dueAtMs = Number.isFinite(lastRunMs) ? lastRunMs + intervalHours * 60 * 60 * 1000 : Date.now();
      const due = skipDueCheck ? true : Date.now() >= dueAtMs;
      let status = "skipped_not_due";
      if (dryRun && forceRun) {
        status = "would_run";
      } else if (dryRun && due) {
        status = "would_run";
      } else if (!dryRun && forceRun) {
        status = "executed";
      } else if (!dryRun && due) {
        status = "executed";
      }
      return {
        schedule_id: item.id,
        schedule_name: item.name,
        project_id: item.project_id,
        status,
        due,
        due_at: new Date(dueAtMs).toISOString(),
        last_snapshot_at: lastSnapshotAt,
        interval_hours: intervalHours,
        force_run: forceRun,
        skip_due_check: skipDueCheck,
      };
    });

  const executedCount = results.filter((item) => item.status === "executed").length;
  const summaryStatus = dryRun ? "preview" : "ok";
  const runId = `manual-${Date.now()}`;
  return {
    project_id: projectId,
    dry_run: dryRun,
    force_run: forceRun,
    skip_due_check: skipDueCheck,
    command_preview: `python scripts/run_gatekeeper_calibration_scheduler.py --use-api-schedules --project-id ${projectId} --api-url http://127.0.0.1:${port}${dryRun ? " --dry-run" : ""}${forceRun ? " --force-run" : ""}${skipDueCheck ? " --skip-due-check" : ""}`,
    process: {
      returncode: 0,
      duration_ms: dryRun ? 180 : 730,
      stderr_tail: null,
    },
    summary: {
      status: summaryStatus,
      run_id: runId,
      started_at: now,
      finished_at: now,
      total_schedules: results.length,
      executed_count: executedCount,
      alerts_count: 0,
      results,
      artifacts_dir: `/tmp/synapse/${runId}`,
    },
    generated_at: now,
  };
}

function serializeOperationRun(run) {
  const { _events, _ticks, ...publicRun } = run;
  const events = Array.isArray(_events) ? _events : [];
  return {
    ...publicRun,
    events_count: events.length,
    last_event_id: events.length ? events[events.length - 1].id : null,
  };
}

function appendOperationEvent(run, eventType, phase, message, progressPercent, payload = {}) {
  const event = {
    id: state.operationEventSeq,
    operation_run_id: run.id,
    project_id: run.project_id,
    event_type: eventType,
    phase,
    message,
    progress_percent: progressPercent,
    payload,
    created_at: nowIso(),
  };
  state.operationEventSeq += 1;
  run._events.push(event);
  run.progress_phase = phase;
  if (typeof progressPercent === "number" && Number.isFinite(progressPercent)) {
    run.progress_percent = Number(progressPercent.toFixed(2));
  }
  run.updated_at = event.created_at;
  run.heartbeat_at = event.created_at;
}

function createQueuedOperationRun(projectId, body) {
  const now = nowIso();
  const dryRun = Boolean(body.dry_run ?? false);
  const token = String(body.operation_token || `${dryRun ? "dryrun" : "run"}-${randomUUID().slice(0, 10)}`);
  const run = {
    id: randomUUID(),
    project_id: projectId,
    operation_token: token,
    requested_by: String(body.requested_by || "web_ui"),
    dry_run: dryRun,
    status: "queued",
    mode: "async",
    progress_percent: 0,
    progress_phase: "queued",
    attempt_no: Number(body.retry_attempt_no || 1),
    max_attempts: Number(body.max_attempts || 3),
    retry_of: body.retry_parent_run_id ? String(body.retry_parent_run_id) : null,
    cancel_requested: false,
    cancel_requested_by: null,
    cancel_requested_at: null,
    started_at: null,
    finished_at: null,
    heartbeat_at: now,
    worker_id: null,
    error_message: null,
    request_payload: {
      ...body,
      operation_token: token,
      project_id: projectId,
    },
    result_payload: {},
    created_at: now,
    updated_at: now,
    _events: [],
    _ticks: 0,
    _pause_notice_emitted: false,
  };
  appendOperationEvent(
    run,
    "queued",
    "queued",
    "Calibration operation queued for async worker execution.",
    0,
    { requested_by: run.requested_by },
  );
  return run;
}

function maybeAdvanceOperationRun(run) {
  if (!run || run.status === "succeeded" || run.status === "failed" || run.status === "canceled") {
    return;
  }
  const control = getQueueControl(run.project_id);
  if (run.status === "cancel_requested") {
    run.status = "canceled";
    run.finished_at = nowIso();
    run.error_message = run.error_message || "cancel_requested";
    appendOperationEvent(run, "canceled", "canceled", "Operation canceled by request.", 100, {});
    return;
  }
  if (run.status === "queued" && control.pause_active) {
    if (!run._pause_notice_emitted) {
      appendOperationEvent(
        run,
        "paused",
        "queued",
        `Queue paused until ${control.paused_until}.`,
        0,
        { paused_until: control.paused_until, pause_reason: control.pause_reason || null },
      );
      run._pause_notice_emitted = true;
    }
    return;
  }
  run._ticks += 1;
  if (run.status === "queued" && run._ticks >= 1) {
    run.status = "running";
    run.started_at = run.started_at || nowIso();
    run.worker_id = "mock_worker";
    appendOperationEvent(run, "started", "running", "Mock worker picked the queued operation.", 18, {});
    return;
  }
  if (run.status === "running" && run._ticks >= 2) {
    const dryRun = Boolean(run.dry_run);
    const forceRun = Boolean(run.request_payload?.force_run ?? true);
    const skipDueCheck = Boolean(run.request_payload?.skip_due_check ?? false);
    run.status = "succeeded";
    run.finished_at = nowIso();
    run.result_payload = buildCalibrationOperationPayload(run.project_id, {
      dryRun,
      forceRun,
      skipDueCheck,
    });
    appendOperationEvent(run, "completed", "completed", "Mock worker completed calibration operation.", 100, {
      scheduler_status: "ok",
    });
  }
}

function buildScheduleObservability(projectId, days) {
  const now = new Date();
  const dayCount = Math.max(1, Math.min(30, Number(days || 30)));
  const schedules = state.schedules.filter((item) => item.project_id === projectId);
  const out = schedules.map((item, idx) => {
    const timeline = [];
    for (let i = dayCount - 1; i >= 0; i -= 1) {
      const day = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
      const dayIso = day.toISOString().slice(0, 10);
      timeline.push({
        day: dayIso,
        ok: i % 5 === 0 ? 0 : 1,
        alert: i % 5 === 0 ? 1 : 0,
        failed: 0,
        skipped: 0,
      });
    }
    const ok = timeline.reduce((acc, row) => acc + row.ok, 0);
    const alert = timeline.reduce((acc, row) => acc + row.alert, 0);
    const executed = ok + alert;
    const successRate = executed > 0 ? Number((ok / executed).toFixed(4)) : 0;
    const alertRate = executed > 0 ? Number((alert / executed).toFixed(4)) : 0;
    const health = successRate >= 0.95 && alertRate <= 0.1 ? "healthy" : "watch";
    return {
      schedule_id: item.id,
      schedule_name: item.name,
      enabled: item.enabled,
      preset: item.preset,
      last_run_at: item.last_run_at,
      last_status: item.last_status,
      slo: {
        health,
        success_rate: successRate,
        alert_rate: alertRate,
        failure_rate: 0,
      },
      window: {
        total: dayCount,
        executed,
        ok,
        alert,
        failed: 0,
        skipped: 0,
        preview: 0,
        unknown: 0,
      },
      trend: timeline.slice(-14),
      top_failure_classes: idx % 2 === 0 ? [{ code: "accuracy_drop_exceeded", count: alert }] : [],
    };
  });
  return {
    project_id: projectId,
    days: dayCount,
    since: new Date(now.getTime() - dayCount * 24 * 60 * 60 * 1000).toISOString(),
    schedules: out,
    generated_at: now.toISOString(),
  };
}

function buildObservabilityCompare(days, requestedProjectsRaw) {
  const requested = String(requestedProjectsRaw || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const projectIds = requested.length
    ? requested
    : [...new Set(state.schedules.map((item) => String(item.project_id)))];
  const projects = projectIds.map((projectId, idx) => {
    const schedules = state.schedules.filter((item) => item.project_id === projectId);
    const enabled = schedules.filter((item) => item.enabled).length;
    const executed = Math.max(1, enabled);
    const ok = Math.max(0, executed - (idx % 2));
    const alert = idx % 2;
    const failed = 0;
    const successRate = Number((ok / executed).toFixed(4));
    const alertRate = Number((alert / executed).toFixed(4));
    const failureRate = Number((failed / executed).toFixed(4));
    return {
      project_id: projectId,
      schedules_total: schedules.length,
      enabled_schedules: enabled,
      window: {
        executed,
        ok,
        alert,
        failed,
        skipped: 0,
        preview: 0,
        unknown: 0,
      },
      slo: {
        health: alert > 0 ? "watch" : "healthy",
        success_rate: successRate,
        alert_rate: alertRate,
        failure_rate: failureRate,
        drift_index: Number((failureRate * 100 + alertRate * 20).toFixed(2)),
      },
      last_run_at: schedules[0]?.last_run_at || null,
      top_failure_classes: alert > 0 ? [{ code: "accuracy_drop_exceeded", count: alert }] : [],
    };
  });
  return {
    days,
    since: new Date(Date.now() - Math.max(1, days) * 24 * 60 * 60 * 1000).toISOString(),
    requested_projects: requested,
    projects,
    generated_at: nowIso(),
  };
}

function buildObservabilityCompareDrilldown(projectId, days) {
  const compare = buildObservabilityCompare(days, null);
  const projects = Array.isArray(compare.projects) ? compare.projects : [];
  let selectedIndex = projects.findIndex((item) => item.project_id === projectId);
  if (selectedIndex < 0) {
    selectedIndex = 0;
  }
  const selected = selectedIndex >= 0 ? projects[selectedIndex] : null;
  const left = Math.max(0, selectedIndex - 2);
  const right = Math.min(projects.length, selectedIndex + 3);
  return {
    project_id: projectId,
    days: Number(days),
    since: compare.since,
    rank_position: selected ? selectedIndex + 1 : null,
    total_projects: projects.length,
    selected_project: selected,
    neighbors: projects.slice(left, right),
    schedule_observability: buildScheduleObservability(projectId, Number(days)),
    generated_at: nowIso(),
  };
}

const server = http.createServer(async (req, res) => {
  if (!req.url) {
    notFound(res);
    return;
  }
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  if (req.method === "OPTIONS") {
    sendJson(res, 200, { status: "ok" });
    return;
  }
  if (url.pathname === "/health") {
    sendJson(res, 200, { status: "ok" });
    return;
  }

  if (url.pathname === "/v1/wiki/pages/search" && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    const query = String(queryParam(url, "q") || "").trim().toLowerCase();
    if (!projectId) {
      sendJson(res, 422, { detail: "project_id_required" });
      return;
    }
    if (!query) {
      sendJson(res, 200, { results: [] });
      return;
    }
    const limitRaw = Number(queryParam(url, "limit") || 20);
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(100, Math.trunc(limitRaw))) : 20;
    const results = state.wikiPages
      .filter((item) => String(item.project_id || "").trim() === projectId)
      .filter((item) => {
        const haystack = `${item.title || ""} ${item.slug || ""} ${item.entity_key || ""}`.toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, limit)
      .map((item) => ({
        id: item.id,
        title: item.title,
        slug: item.slug,
        entity_key: item.entity_key,
        page_type: item.page_type,
        status: item.status,
        score: String(item.slug || "").toLowerCase() === query ? 0.95 : 0.7,
      }));
    sendJson(res, 200, { results });
    return;
  }

  if (url.pathname === "/v1/mcp/retrieval/explain" && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    const query = String(queryParam(url, "q") || "").trim().toLowerCase();
    const relatedEntityKey = String(queryParam(url, "related_entity_key") || "").trim().toLowerCase() || null;
    const policyModeRaw = String(queryParam(url, "context_policy_mode") || "advisory")
      .trim()
      .toLowerCase();
    const policyMode = policyModeRaw === "off" || policyModeRaw === "enforced" ? policyModeRaw : "advisory";
    const minConfidenceRaw = Number.parseFloat(String(queryParam(url, "min_retrieval_confidence") || "0.45"));
    const minTotalScoreRaw = Number.parseFloat(String(queryParam(url, "min_total_score") || "0.20"));
    const minLexicalScoreRaw = Number.parseFloat(String(queryParam(url, "min_lexical_score") || "0.08"));
    const minOverlapRaw = Number.parseFloat(String(queryParam(url, "min_token_overlap_ratio") || "0.15"));
    const contextPolicy = {
      mode: policyMode,
      min_confidence: Number.isFinite(minConfidenceRaw) ? Math.max(0, Math.min(1, minConfidenceRaw)) : 0.45,
      min_total_score: Number.isFinite(minTotalScoreRaw) ? Math.max(0, Math.min(2, minTotalScoreRaw)) : 0.2,
      min_lexical_score: Number.isFinite(minLexicalScoreRaw) ? Math.max(0, Math.min(2, minLexicalScoreRaw)) : 0.08,
      min_token_overlap_ratio: Number.isFinite(minOverlapRaw) ? Math.max(0, Math.min(1, minOverlapRaw)) : 0.15,
    };
    const graphConfig = {
      max_graph_hops: 3,
      boost_hop1: 0.2,
      boost_hop2: 0.12,
      boost_hop3: 0.06,
      boost_other: 0.03,
    };
    const graphHeaders = {
      "X-Synapse-Retrieval-Graph-Max-Hops": String(graphConfig.max_graph_hops),
      "X-Synapse-Retrieval-Graph-Boost-Hop1": graphConfig.boost_hop1.toFixed(4),
      "X-Synapse-Retrieval-Graph-Boost-Hop2": graphConfig.boost_hop2.toFixed(4),
      "X-Synapse-Retrieval-Graph-Boost-Hop3": graphConfig.boost_hop3.toFixed(4),
      "X-Synapse-Retrieval-Graph-Boost-Other": graphConfig.boost_other.toFixed(4),
      "X-Synapse-Retrieval-Context-Policy-Mode": policyMode,
      "X-Synapse-Retrieval-Context-Min-Confidence": contextPolicy.min_confidence.toFixed(4),
      "X-Synapse-Retrieval-Context-Min-Total-Score": contextPolicy.min_total_score.toFixed(4),
      "X-Synapse-Retrieval-Context-Min-Lexical-Score": contextPolicy.min_lexical_score.toFixed(4),
      "X-Synapse-Retrieval-Context-Min-Token-Overlap-Ratio": contextPolicy.min_token_overlap_ratio.toFixed(4),
    };
    if (!projectId) {
      sendJson(res, 422, { detail: "project_id_required" });
      return;
    }
    if (!query) {
      sendJson(res, 200, {
        project_id: projectId,
        query: "",
        source: "api_mcp_compatible_retrieval_explain",
        filters: {
          entity_key: null,
          category: null,
          page_type: null,
          related_entity_key: relatedEntityKey,
        },
        results: [],
        graph_config: graphConfig,
        context_policy: contextPolicy,
        policy_filtered_out: 0,
        explainability: {
          version: "v1",
          query_tokens: [],
          related_entity_key: relatedEntityKey,
          context_policy: contextPolicy,
        },
      }, graphHeaders);
      return;
    }
    const limitRaw = Number(queryParam(url, "limit") || 10);
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(100, Math.trunc(limitRaw))) : 10;
    const tokens = query.split(/\s+/).filter(Boolean);
    const rows = state.wikiPages
      .filter((item) => String(item.project_id || "").trim() === projectId)
      .map((item) => {
        const statementText = `Operational note for ${item.title}.`;
        const blob = `${statementText} ${item.title || ""} ${item.slug || ""} ${item.entity_key || ""}`.toLowerCase();
        const tokenHits = tokens.reduce((acc, token) => (blob.includes(token) ? acc + 1 : acc), 0);
        const lexical = tokens.length > 0 ? tokenHits / tokens.length : 0;
        const graphHops = relatedEntityKey && String(item.entity_key || "").toLowerCase() !== relatedEntityKey ? 1 : null;
        const graphBoost = graphHops != null ? graphConfig.boost_hop1 : 0.0;
        const score = Number((lexical + graphBoost).toFixed(4));
        const exactMatchSignal = String(item.entity_key || "").toLowerCase() === query ? 1 : 0;
        const lexicalNorm = Math.max(0, Math.min(1, lexical / 1.1));
        const graphSupport = graphHops != null ? 0.82 : 0;
        const confidence = Number(
          Math.max(
            0,
            Math.min(1, 0.06 + 0.5 * lexical + 0.22 * lexicalNorm + 0.15 * exactMatchSignal + 0.07 * graphSupport),
          ).toFixed(4),
        );
        const blockedBy = [];
        if (policyMode !== "off") {
          if (score < contextPolicy.min_total_score) blockedBy.push("min_total_score");
          if (lexical < contextPolicy.min_lexical_score) blockedBy.push("min_lexical_score");
          if (tokens.length > 0 && tokenHits / tokens.length < contextPolicy.min_token_overlap_ratio) {
            blockedBy.push("min_token_overlap_ratio");
          }
          if (confidence < contextPolicy.min_confidence) blockedBy.push("min_confidence");
        }
        return {
          statement_id: `mock-statement-${item.id}`,
          statement_text: statementText,
          section_key: "overview",
          category: "operations",
          page: {
            id: item.id,
            title: item.title,
            slug: item.slug,
            entity_key: item.entity_key,
            page_type: item.page_type,
          },
          score,
          graph_hops: graphHops,
          graph_boost: graphBoost,
          retrieval_confidence: confidence,
          confidence_breakdown: {
            overall: confidence,
            lexical_overlap: Number(lexical.toFixed(4)),
            lexical_score_norm: Number(lexicalNorm.toFixed(4)),
            exact_match_signal: exactMatchSignal,
            phrase_signal: blob.includes(query) ? 1 : 0,
            graph_support: Number(graphSupport.toFixed(4)),
          },
          context_policy: {
            mode: policyMode,
            eligible: blockedBy.length === 0,
            blocked_by: blockedBy,
            thresholds: {
              mode: policyMode,
              min_confidence: contextPolicy.min_confidence,
              min_total_score: contextPolicy.min_total_score,
              min_lexical_score: contextPolicy.min_lexical_score,
              min_token_overlap_ratio: contextPolicy.min_token_overlap_ratio,
            },
          },
          retrieval_reason:
            graphHops != null
              ? `token overlap ${tokenHits}/${tokens.length}; graph relation from \`${relatedEntityKey}\` in ${graphHops} hop(s) (+0.20)`
              : `token overlap ${tokenHits}/${tokens.length}`,
          score_breakdown: {
            total: score,
            lexical: Number(lexical.toFixed(4)),
            graph: Number(graphBoost.toFixed(4)),
            lexical_components: {
              query_tokens_total: tokens.length,
              token_overlap_hits: tokenHits,
              token_overlap_ratio: tokens.length > 0 ? Number((tokenHits / tokens.length).toFixed(4)) : 0,
              statement_token_hits: tokenHits,
              statement_token_ratio: tokens.length > 0 ? Number((tokenHits / tokens.length).toFixed(4)) : 0,
              title_token_hits: tokenHits,
              title_token_ratio: tokens.length > 0 ? Number((tokenHits / tokens.length).toFixed(4)) : 0,
              slug_token_hits: tokenHits,
              slug_token_ratio: tokens.length > 0 ? Number((tokenHits / tokens.length).toFixed(4)) : 0,
              entity_exact_match: String(item.entity_key || "").toLowerCase() === query,
              slug_exact_match: String(item.slug || "").toLowerCase() === query.replace(/\s+/g, "-"),
              title_phrase_match: String(item.title || "").toLowerCase().includes(query),
              phrase_match: blob.includes(query),
            },
          },
        };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    const filteredRows =
      policyMode === "enforced" ? rows.filter((item) => item.context_policy && item.context_policy.eligible) : rows;
    const policyFilteredOut = Math.max(0, rows.length - filteredRows.length);

    sendJson(res, 200, {
      project_id: projectId,
      query,
      source: "api_mcp_compatible_retrieval_explain",
      filters: {
        entity_key: null,
        category: null,
        page_type: null,
        related_entity_key: relatedEntityKey,
      },
      results: filteredRows,
      graph_config: graphConfig,
      context_policy: contextPolicy,
      policy_filtered_out: policyFilteredOut,
      explainability: {
        version: "v1",
        query_tokens: tokens,
        related_entity_key: relatedEntityKey,
        context_policy: contextPolicy,
      },
    }, graphHeaders);
    return;
  }

  const wikiPageHistoryMatch = url.pathname.match(/^\/v1\/wiki\/pages\/([^/]+(?:\/[^/]+)*)\/history$/);
  if (wikiPageHistoryMatch && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "project_id_required" });
      return;
    }
    const slug = decodeURIComponent(wikiPageHistoryMatch[1]);
    const page = findWikiPageBySlug(projectId, slug);
    if (!page) {
      sendJson(res, 404, { error: "page_not_found" });
      return;
    }
    const includeMarkdown = String(queryParam(url, "include_markdown") || "true")
      .trim()
      .toLowerCase() !== "false";
    const limitRaw = Number(queryParam(url, "limit") || 20);
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(100, Math.trunc(limitRaw))) : 20;
    const versions = listWikiPageVersions(page.id)
      .slice(0, limit)
      .map((item) => ({
        version: item.version,
        source: item.source,
        created_by: item.created_by,
        change_summary: item.change_summary,
        created_at: item.created_at,
        markdown_length: String(item.markdown || "").length,
        ...(includeMarkdown ? { markdown: item.markdown } : {}),
      }));
    sendJson(res, 200, {
      page: {
        id: page.id,
        title: page.title,
        slug: page.slug,
        entity_key: page.entity_key,
        page_type: page.page_type,
        status: page.status,
        current_version: page.current_version,
      },
      versions,
    });
    return;
  }

  const wikiPageMatch = url.pathname.match(/^\/v1\/wiki\/pages\/([^/]+(?:\/[^/]+)*)$/);
  if (wikiPageMatch && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "project_id_required" });
      return;
    }
    const slug = decodeURIComponent(wikiPageMatch[1]);
    const page = findWikiPageBySlug(projectId, slug);
    if (!page) {
      sendJson(res, 404, { error: "page_not_found" });
      return;
    }
    const latestVersion = listWikiPageVersions(page.id)[0] || null;
    sendJson(res, 200, {
      page: {
        id: page.id,
        title: page.title,
        slug: page.slug,
        entity_key: page.entity_key,
        page_type: page.page_type,
        status: page.status,
        current_version: page.current_version,
      },
      latest_version: latestVersion
        ? {
            version: latestVersion.version,
            markdown: latestVersion.markdown,
            source: latestVersion.source,
            created_by: latestVersion.created_by,
            created_at: latestVersion.created_at,
          }
        : null,
      sections: [
        {
          section_key: "access_rules",
          heading: "Access Rules",
          order_index: 0,
          statement_count: 2,
        },
      ],
      statements: [
        {
          id: randomUUID(),
          section_key: "access_rules",
          statement_text: "Entry requires card after 10:00.",
          claim_fingerprint: "mock-fingerprint-1",
          valid_from: "2026-03-31T09:00:00Z",
          valid_to: null,
          created_at: "2026-03-31T09:00:00Z",
        },
      ],
    });
    return;
  }

  if (url.pathname === "/v1/wiki/pages" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    const createdBy = String(body.created_by || "").trim();
    const title = String(body.title || "").trim();
    if (!projectId || !createdBy || !title) {
      sendJson(res, 422, { detail: "project_id_created_by_title_required" });
      return;
    }
    const normalizedSlug = normalizeWikiSlug(body.slug || "", title);
    const existing = findWikiPageBySlug(projectId, normalizedSlug);
    if (existing) {
      if (Boolean(body.allow_existing)) {
        sendJson(res, 200, {
          status: "existing",
          page: {
            id: existing.id,
            title: existing.title,
            slug: existing.slug,
            entity_key: existing.entity_key,
            page_type: existing.page_type,
            status: existing.status,
            current_version: existing.current_version,
          },
        });
        return;
      }
      sendJson(res, 409, {
        error: "page_slug_exists",
        existing_page: {
          id: existing.id,
          title: existing.title,
          slug: existing.slug,
          entity_key: existing.entity_key,
          page_type: existing.page_type,
          status: existing.status,
          current_version: existing.current_version,
        },
      });
      return;
    }
    const pageId = randomUUID();
    const now = nowIso();
    const markdownRaw = String(body.initial_markdown || "").trim();
    const markdown = markdownRaw
      ? markdownRaw.endsWith("\n")
        ? markdownRaw
        : `${markdownRaw}\n`
      : `# ${title}\n\n## Overview\n- Add first approved fact.\n`;
    const page = {
      id: pageId,
      project_id: projectId,
      title,
      slug: normalizedSlug,
      entity_key: String(body.entity_key || "").trim() || normalizedSlug,
      page_type: String(body.page_type || "operations").trim() || "operations",
      status: String(body.status || "published").trim() || "published",
      current_version: 1,
      created_at: now,
      updated_at: now,
    };
    state.wikiPages.unshift(page);
    state.wikiPageVersions.unshift({
      id: randomUUID(),
      page_id: pageId,
      version: 1,
      markdown,
      source: "human",
      created_by: createdBy,
      change_summary: String(body.change_summary || "").trim() || `Page created by ${createdBy}`,
      created_at: now,
    });
    sendJson(res, 200, {
      status: "created",
      page: {
        id: page.id,
        title: page.title,
        slug: page.slug,
        entity_key: page.entity_key,
        page_type: page.page_type,
        status: page.status,
        current_version: page.current_version,
      },
      latest_version: {
        version: 1,
        markdown,
        source: "human",
        created_by: createdBy,
      },
      snapshot_id: randomUUID(),
      inserted_statements: markdown.includes("- ") ? 1 : 0,
    });
    return;
  }

  if (url.pathname === "/v1/wiki/drafts" && req.method === "GET") {
    sendJson(res, 200, { drafts: [] });
    return;
  }

  if (url.pathname === "/v1/wiki/moderation/throughput" && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "project_id_required" });
      return;
    }
    const windowHoursRaw = Number(queryParam(url, "window_hours") || 24);
    const windowHours = Number.isFinite(windowHoursRaw) ? Math.max(1, Math.min(24 * 30, Math.trunc(windowHoursRaw))) : 24;
    sendJson(res, 200, {
      project_id: projectId,
      window_hours: windowHours,
      since: new Date(Date.now() - windowHours * 60 * 60 * 1000).toISOString(),
      generated_at: nowIso(),
      health: "watch",
      alerts: ["Blocked conflicts are high; prioritize conflict resolution queue."],
      metrics: {
        actions_total: 14,
        approvals: 10,
        rejections: 4,
        approval_rate: 10 / 14,
        reviewers_active: 3,
        processed_per_hour: Number((14 / windowHours).toFixed(3)),
        drafts_created: 18,
        net_backlog_delta: 4,
        conflict_unblocks: 3,
        latency_minutes: {
          avg: 172.4,
          p50: 95.0,
          p90: 480.0,
        },
      },
      backlog: {
        open_total: 9,
        pending_review: 6,
        blocked_conflict: 3,
      },
      top_reviewers: [
        { reviewed_by: "ops_manager", actions_total: 7, approvals: 5, rejections: 2 },
        { reviewed_by: "qa_reviewer", actions_total: 4, approvals: 3, rejections: 1 },
        { reviewed_by: "logistics_lead", actions_total: 3, approvals: 2, rejections: 1 },
      ],
    });
    return;
  }

  if (url.pathname === "/v1/tasks" && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "task_project_id_required" });
      return;
    }
    let status = null;
    const statusRaw = queryParam(url, "status");
    if (statusRaw != null && String(statusRaw).trim()) {
      try {
        status = normalizeTaskStatus(statusRaw);
      } catch (error) {
        sendJson(res, 422, { detail: error instanceof Error ? error.message : String(error) });
        return;
      }
    }
    const assignee = queryParam(url, "assignee");
    const entityKey = queryParam(url, "entity_key");
    const includeClosed = String(queryParam(url, "include_closed") || "false").trim().toLowerCase() === "true";
    const limitRaw = Number(queryParam(url, "limit") || 100);
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(500, Math.trunc(limitRaw))) : 100;
    sendJson(
      res,
      200,
      {
        tasks: listTaskRows({
          projectId,
          status,
          assignee,
          entityKey,
          includeClosed,
          limit,
        }),
      },
    );
    return;
  }

  if (url.pathname === "/v1/tasks" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    try {
      const payload = upsertTaskRow(body);
      sendJson(res, 200, payload);
    } catch (error) {
      sendJson(res, 422, { detail: error instanceof Error ? error.message : String(error) });
    }
    return;
  }

  const taskStatusMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/status$/);
  if (taskStatusMatch && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "task_project_id_required" });
      return;
    }
    const taskId = decodeURIComponent(taskStatusMatch[1]);
    const idx = findTaskIndex(taskId, projectId);
    if (idx < 0) {
      sendJson(res, 404, { error: "task_not_found" });
      return;
    }
    let status = null;
    try {
      status = normalizeTaskStatus(body.status);
    } catch (error) {
      sendJson(res, 422, { detail: error instanceof Error ? error.message : String(error) });
      return;
    }
    const updatedBy = trimOptional(body.updated_by, 256);
    if (!updatedBy) {
      sendJson(res, 422, { detail: "task_updated_by_required" });
      return;
    }
    const note = trimOptional(body.note, 4000);
    const task = state.tasks[idx];
    const previousStatus = String(task.status || "todo");
    task.status = status;
    touchTaskRow(task, updatedBy);
    appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "status_changed",
      actor: updatedBy,
      payload: {
        from: previousStatus,
        to: status,
        note,
      },
    });
    sendJson(res, 200, {
      status: "ok",
      changed: previousStatus !== status,
      task: cloneTaskRow(task),
    });
    return;
  }

  const taskCommentMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/comments$/);
  if (taskCommentMatch && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "task_project_id_required" });
      return;
    }
    const createdBy = trimOptional(body.created_by, 256);
    if (!createdBy) {
      sendJson(res, 422, { detail: "task_created_by_required" });
      return;
    }
    const comment = String(body.comment || "").trim();
    if (!comment) {
      sendJson(res, 422, { detail: "task_comment_required" });
      return;
    }
    const taskId = decodeURIComponent(taskCommentMatch[1]);
    const idx = findTaskIndex(taskId, projectId);
    if (idx < 0) {
      sendJson(res, 404, { error: "task_not_found" });
      return;
    }
    const task = state.tasks[idx];
    const event = appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "comment",
      actor: createdBy,
      payload: {
        comment,
        metadata: toTaskObjectMetadata(body.metadata),
      },
    });
    touchTaskRow(task, createdBy);
    sendJson(res, 200, { status: "ok", event_id: event.id });
    return;
  }

  const taskLinkMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/links$/);
  if (taskLinkMatch && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "task_project_id_required" });
      return;
    }
    const createdBy = trimOptional(body.created_by, 256);
    if (!createdBy) {
      sendJson(res, 422, { detail: "task_created_by_required" });
      return;
    }
    const linkRef = String(body.link_ref || "").trim();
    if (!linkRef) {
      sendJson(res, 422, { detail: "task_link_ref_required" });
      return;
    }
    const taskId = decodeURIComponent(taskLinkMatch[1]);
    const idx = findTaskIndex(taskId, projectId);
    if (idx < 0) {
      sendJson(res, 404, { error: "task_not_found" });
      return;
    }
    let linkType = null;
    try {
      linkType = normalizeTaskLinkType(body.link_type);
    } catch (error) {
      sendJson(res, 422, { detail: error instanceof Error ? error.message : String(error) });
      return;
    }
    const task = state.tasks[idx];
    const existingLinkIdx = state.taskLinks.findIndex(
      (item) =>
        String(item.task_id || "") === String(task.id) &&
        String(item.project_id || "") === String(task.project_id) &&
        String(item.link_type || "") === linkType &&
        String(item.link_ref || "") === linkRef,
    );
    const note = trimOptional(body.note, 4000);
    const metadata = toTaskObjectMetadata(body.metadata);
    if (existingLinkIdx >= 0) {
      state.taskLinks[existingLinkIdx] = {
        ...state.taskLinks[existingLinkIdx],
        note,
        metadata,
        created_by: createdBy,
      };
    } else {
      state.taskLinks.unshift({
        id: randomUUID(),
        task_id: task.id,
        project_id: task.project_id,
        link_type: linkType,
        link_ref: linkRef,
        note,
        metadata,
        created_by: createdBy,
        created_at: nowIso(),
      });
    }
    const link = state.taskLinks[existingLinkIdx >= 0 ? existingLinkIdx : 0];
    appendTaskEvent({
      taskId: task.id,
      projectId: task.project_id,
      eventType: "link_added",
      actor: createdBy,
      payload: {
        link_type: linkType,
        link_ref: linkRef,
        note,
      },
    });
    touchTaskRow(task, createdBy);
    sendJson(res, 200, { status: "ok", link: cloneTaskLinkRow(link) });
    return;
  }

  const taskDetailMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)$/);
  if (taskDetailMatch && req.method === "GET") {
    const projectId = String(queryParam(url, "project_id") || "").trim();
    if (!projectId) {
      sendJson(res, 422, { detail: "task_project_id_required" });
      return;
    }
    const taskId = decodeURIComponent(taskDetailMatch[1]);
    const idx = findTaskIndex(taskId, projectId);
    if (idx < 0) {
      sendJson(res, 404, { error: "task_not_found" });
      return;
    }
    const eventsLimitRaw = Number(queryParam(url, "events_limit") || 100);
    const linksLimitRaw = Number(queryParam(url, "links_limit") || 100);
    const eventsLimit = Number.isFinite(eventsLimitRaw) ? Math.max(0, Math.min(500, Math.trunc(eventsLimitRaw))) : 100;
    const linksLimit = Number.isFinite(linksLimitRaw) ? Math.max(0, Math.min(500, Math.trunc(linksLimitRaw))) : 100;
    sendJson(res, 200, {
      task: cloneTaskRow(state.tasks[idx]),
      events: listTaskEvents(taskId, projectId, eventsLimit),
      links: listTaskLinks(taskId, projectId, linksLimit),
    });
    return;
  }

  if (url.pathname === "/v1/intelligence/metrics/daily" && req.method === "GET") {
    sendJson(res, 200, {
      metrics: [
        {
          metric_date: "2026-03-31",
          claims_created: 20,
          drafts_created: 10,
          drafts_approved: 7,
          drafts_rejected: 1,
          statements_added: 9,
          conflicts_opened: 2,
          conflicts_resolved: 1,
          pending_drafts: 3,
          open_conflicts: 4,
          pages_touched: 8,
          knowledge_velocity: 1.31,
          computed_at: "2026-03-31T08:30:00Z",
        },
        {
          metric_date: "2026-03-30",
          claims_created: 17,
          drafts_created: 9,
          drafts_approved: 6,
          drafts_rejected: 2,
          statements_added: 8,
          conflicts_opened: 1,
          conflicts_resolved: 2,
          pending_drafts: 2,
          open_conflicts: 3,
          pages_touched: 6,
          knowledge_velocity: 1.1,
          computed_at: "2026-03-30T08:30:00Z",
        },
      ],
    });
    return;
  }
  if (url.pathname === "/v1/intelligence/trends/weekly" && req.method === "GET") {
    sendJson(res, 200, {
      project_id: queryParam(url, "project_id") || projectIdDefault,
      anchor_date: "2026-03-31",
      weeks: [
        {
          week_start: "2026-03-24",
          week_end: "2026-03-31",
          days_covered: 7,
          claims_created: 105,
          drafts_created: 52,
          drafts_approved: 40,
          drafts_rejected: 6,
          statements_added: 47,
          conflicts_opened: 11,
          conflicts_resolved: 8,
          pages_touched: 30,
          pending_drafts_end: 9,
          open_conflicts_end: 6,
          knowledge_velocity_sum: 7.4,
          knowledge_velocity_avg: 1.06,
        },
      ],
      wow: {
        week_start: "2026-03-24",
        comparisons: {
          drafts_approved: { current: 40, previous: 34, delta_abs: 6, delta_pct: 17.6 },
          statements_added: { current: 47, previous: 41, delta_abs: 6, delta_pct: 14.6 },
          conflicts_opened: { current: 11, previous: 8, delta_abs: 3, delta_pct: 37.5 },
          open_conflicts_end: { current: 6, previous: 5, delta_abs: 1, delta_pct: 20.0 },
          knowledge_velocity_avg: { current: 1.06, previous: 0.91, delta_abs: 0.15, delta_pct: 16.5 },
        },
      },
    });
    return;
  }
  if (url.pathname === "/v1/intelligence/queue/governance_digest" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const auditDays = Math.max(1, Math.min(365, Number(queryParam(url, "audit_days") || 7)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 30)));
    const topN = Math.max(1, Math.min(20, Number(queryParam(url, "top_n") || 5)));
    sendJson(res, 200, buildQueueGovernanceDigest(projectIds, windowHours, auditDays, limit, topN, projectId));
    return;
  }
  if (url.pathname === "/v1/intelligence/queue/incident_escalation_digest" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const incidentSlaHours = Math.max(1, Math.min(168, Number(queryParam(url, "incident_sla_hours") || 24)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 30)));
    const topN = Math.max(1, Math.min(50, Number(queryParam(url, "top_n") || 10)));
    sendJson(res, 200, buildQueueIncidentEscalationDigest(projectIds, windowHours, incidentSlaHours, limit, topN, projectId));
    return;
  }
  if (url.pathname === "/v1/intelligence/digests/latest" && req.method === "GET") {
    sendJson(res, 200, {
      digest: {
        id: "digest-1",
        digest_kind: "daily",
        digest_date: "2026-03-31",
        period_start: "2026-03-30",
        period_end: "2026-03-31",
        status: "generated",
        headline: "Agents learned 9 stable changes",
        summary_markdown: "Top risk: warehouse access variance.",
        payload: { highlights: ["Omega gate card after 10:00", "2 unresolved route conflicts"] },
        generated_by: "intelligence_digest",
        generated_at: nowIso(),
        sent_at: null,
      },
    });
    return;
  }
  if (url.pathname === "/v1/intelligence/conflicts/drilldown" && req.method === "GET") {
    sendJson(res, 200, {
      project_id: queryParam(url, "project_id") || projectIdDefault,
      anchor_date: "2026-03-31",
      weeks: [
        {
          week_start: "2026-03-24",
          week_end: "2026-03-31",
          opened_total: 11,
          resolved_total: 8,
          dismissed_total: 1,
          open_total: 2,
          mttr_hours_avg: 7.1,
          conflict_classes: [
            {
              conflict_type: "temporal_overlap",
              opened_total: 6,
              resolved_total: 5,
              dismissed_total: 0,
              open_total: 1,
              mttr_hours_avg: 6.2,
            },
          ],
        },
      ],
      top_conflict_types: [
        {
          conflict_type: "temporal_overlap",
          opened_total: 6,
          resolved_total: 5,
          resolution_rate_pct: 83.3,
          mttr_hours_avg: 6.2,
        },
      ],
      overall: {
        opened_total: 11,
        resolved_total: 8,
        dismissed_total: 1,
        open_total: 2,
        mttr_hours_avg: 7.1,
      },
    });
    return;
  }
  if (url.pathname === "/v1/intelligence/delivery/targets" && req.method === "GET") {
    sendJson(res, 200, { targets: [] });
    return;
  }
  if (url.pathname === "/v1/intelligence/delivery/attempts" && req.method === "GET") {
    sendJson(res, 200, { attempts: [] });
    return;
  }

  if (url.pathname === "/v1/gatekeeper/config/snapshots" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    sendJson(res, 200, { snapshots: snapshots.filter((item) => item.project_id === projectId) });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/trends" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    sendJson(res, 200, {
      project_id: projectId,
      points: [
        {
          snapshot_id: snapshots[0].id,
          created_at: snapshots[0].created_at,
          source: snapshots[0].source,
          guardrails_met: snapshots[0].guardrails_met,
          gate_status: "pass",
          metrics: { accuracy: 0.92, macro_f1: 0.88, golden_precision: 0.85 },
          approval_gate: { approvals_last_7d: 11, rejections_last_7d: 2, approval_rate_last_7d: 84.6 },
          holdout_meta: {},
        },
      ],
      summary: {
        latest_snapshot_id: snapshots[0].id,
        latest_created_at: snapshots[0].created_at,
        latest_gate_status: "pass",
        latest_guardrails_met: true,
        latest_metrics: { accuracy: 0.92, macro_f1: 0.88, golden_precision: 0.85 },
        latest_approval_gate: { approvals_last_7d: 11, rejections_last_7d: 2, approval_rate_last_7d: 84.6 },
        deltas_vs_previous: { accuracy: 0.01, macro_f1: 0.02, golden_precision: -0.01 },
      },
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/runs" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    sendJson(res, 200, {
      runs: [
        {
          run_id: "run-20260331",
          status: "alert",
          started_at: "2026-03-31T05:00:00Z",
          finished_at: "2026-03-31T05:11:00Z",
          total_schedules: 1,
          executed_count: 1,
          alerts_count: 2,
          summary: {},
          projects: [
            {
              project_id: projectId,
              schedule_id: state.schedules[0]?.id ?? null,
              schedule_name: state.schedules[0]?.name ?? null,
              status: "alert",
              project_cycle_status: "ok",
              returncode: 0,
              alerts: [{ code: "accuracy_drop_exceeded" }, { code: "guardrails_regressed" }],
              result: {},
              created_at: "2026-03-31T05:11:00Z",
            },
          ],
        },
      ],
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/runs/trends" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    sendJson(res, 200, {
      project_id: projectId,
      days: 30,
      since: "2026-03-01T00:00:00Z",
      timeline: [
        { day: "03-29", ok: 1, alert: 0, partial_failure: 0, executed: 1, alerts_total: 0 },
        { day: "03-30", ok: 0, alert: 1, partial_failure: 0, executed: 1, alerts_total: 1 },
        { day: "03-31", ok: 0, alert: 1, partial_failure: 0, executed: 1, alerts_total: 2 },
      ],
      summary: {
        executed_total: 3,
        alert_total: 2,
        partial_failure_total: 0,
        alert_ratio: 0.6667,
        top_alert_codes: [
          { code: "accuracy_drop_exceeded", count: 2 },
          { code: "guardrails_regressed", count: 1 },
        ],
      },
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/preview" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const skipDueCheck = String(queryParam(url, "skip_due_check") || "false") === "true";
    const forceRun = String(queryParam(url, "force_run") || "false") === "true";
    sendJson(res, 200, {
      status: "ok",
      operation: buildCalibrationOperationPayload(projectId, {
        dryRun: true,
        forceRun,
        skipDueCheck,
      }),
      safety: {
        required_confirmation_phrase: `RUN ${projectId}`,
        lock_scope: `project:${projectId}`,
        idempotency_required_for_live_run: true,
      },
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    sendJson(res, 200, buildQueueThroughput(projectId, windowHours));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/compare" && req.method === "GET") {
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 12)));
    sendJson(res, 200, buildQueueThroughputCompare(projectIds, windowHours, limit));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/owners" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const slaHours = Math.max(1, Math.min(168, Number(queryParam(url, "sla_hours") || 24)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 50)));
    sendJson(res, 200, buildQueueOwnerRollups(projectIds, windowHours, slaHours, limit, projectId));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/governance/drift" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const auditDays = Math.max(1, Math.min(365, Number(queryParam(url, "audit_days") || 7)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 50)));
    sendJson(res, 200, buildQueueGovernanceDrift(projectIds, windowHours, auditDays, limit, projectId));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/slo_board" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const incidentWindowDays = Math.max(1, Math.min(180, Number(queryParam(url, "incident_window_days") || 30)));
    const mttrSlaHours = Math.max(1, Math.min(168, Number(queryParam(url, "mttr_sla_hours") || 24)));
    const mttaProxySlaMinutes = Math.max(1, Math.min(1440, Number(queryParam(url, "mtta_proxy_sla_minutes") || 15)));
    const rotationLagSlaHours = Math.max(1, Math.min(2160, Number(queryParam(url, "rotation_lag_sla_hours") || 168)));
    const secretMaxAgeDays = Math.max(1, Math.min(365, Number(queryParam(url, "secret_max_age_days") || 30)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 50)));
    const topN = Math.max(1, Math.min(50, Number(queryParam(url, "top_n") || 12)));
    sendJson(
      res,
      200,
      buildQueueIncidentSloBoard(
        projectIds,
        windowHours,
        incidentWindowDays,
        mttrSlaHours,
        mttaProxySlaMinutes,
        rotationLagSlaHours,
        secretMaxAgeDays,
        limit,
        topN,
        projectId,
      ),
    );
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/compare/export" && req.method === "GET") {
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 30)));
    const format = String(queryParam(url, "format") || "csv");
    const payload = buildQueueThroughputCompare(projectIds, windowHours, limit);
    if (format === "json") {
      sendJson(res, 200, payload);
      return;
    }
    const csv = serializeQueueThroughputCompareCsv(payload);
    res.writeHead(200, {
      "Content-Type": "text/csv; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type,Idempotency-Key,X-Synapse-Roles",
      "Content-Disposition": `attachment; filename="queue-command-center-${Date.now()}.csv"`,
    });
    res.end(csv);
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/compare/export/webhook" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const requestedBy = String(body.requested_by || "web_ui");
    const projectIds = Array.isArray(body.project_ids) ? body.project_ids.join(",") : "";
    const windowHours = Math.max(1, Math.min(168, Number(body.window_hours || 24)));
    const limit = Math.max(1, Math.min(200, Number(body.limit || 30)));
    const payload = buildQueueThroughputCompare(projectIds, windowHours, limit);
    const includeCsv = Boolean(body.include_csv);
    for (const row of payload.projects || []) {
      appendQueueAuditEvent({
        projectId: String(row.project_id || projectIdDefault),
        action: "export_snapshot",
        actor: requestedBy,
        reason: `webhook:${String(body.webhook_url || "").slice(0, 180)}`,
        pausedUntil: null,
        payload: {
          channel: "webhook",
          window_hours: windowHours,
          http_status: 200,
        },
      });
    }
    sendJson(res, 200, {
      status: "ok",
      channel: "webhook",
      webhook_url: String(body.webhook_url || ""),
      http_status: 200,
      response_preview: "accepted",
      projects_total: Array.isArray(payload.projects) ? payload.projects.length : 0,
      window_hours: windowHours,
      generated_at: nowIso(),
      include_csv: includeCsv,
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/recommendations" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const windowHours = Math.max(1, Math.min(168, Number(queryParam(url, "window_hours") || 24)));
    const historyHours = Math.max(24, Math.min(720, Number(queryParam(url, "history_hours") || 72)));
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 20)));
    sendJson(res, 200, buildQueueAutoscalingRecommendations(projectIds, windowHours, historyHours, limit, projectId));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/recommendations/apply" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const windowHours = Math.max(1, Math.min(168, Number(body.window_hours || 24)));
    const historyHours = Math.max(24, Math.min(720, Number(body.history_hours || 72)));
    const recommendation = buildQueueAutoscalingRecommendation(projectId, windowHours, historyHours);
    const existing = getQueueControl(projectId);
    const applyLag = Boolean(body.apply_worker_lag_sla ?? true);
    const applyDepth = Boolean(body.apply_queue_depth_warn ?? true);
    const recommended = recommendation?.recommendation || {};
    const control = upsertQueueControl(projectId, {
      worker_lag_sla_minutes: applyLag
        ? Number(recommended.worker_lag_sla_minutes || existing.worker_lag_sla_minutes || 20)
        : Number(existing.worker_lag_sla_minutes || 20),
      queue_depth_warn: applyDepth
        ? Number(recommended.queue_depth_warn || existing.queue_depth_warn || 12)
        : Number(existing.queue_depth_warn || 12),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "apply_recommendation",
      actor: String(body.updated_by || "web_ui"),
      reason: body.reason == null ? "autoscaling_recommendation_apply" : String(body.reason),
      pausedUntil: control.paused_until || null,
      payload: {
        window_hours: windowHours,
        history_hours: historyHours,
        apply_worker_lag_sla: applyLag,
        apply_queue_depth_warn: applyDepth,
        recommended_worker_lag_sla_minutes: Number(recommended.worker_lag_sla_minutes || 0),
        recommended_queue_depth_warn: Number(recommended.queue_depth_warn || 0),
        applied_worker_lag_sla_minutes: Number(control.worker_lag_sla_minutes || 0),
        applied_queue_depth_warn: Number(control.queue_depth_warn || 0),
        recommended_worker_concurrency_target: Number(recommended.worker_concurrency_target || 0),
        recommended_worker_concurrency_delta: Number(recommended.worker_concurrency_delta || 0),
      },
    });
    sendJson(res, 200, {
      status: "ok",
      project_id: projectId,
      control,
      throughput: buildQueueThroughput(projectId, windowHours),
      recommendation,
      applied: {
        worker_lag_sla_minutes: Number(control.worker_lag_sla_minutes || 0),
        queue_depth_warn: Number(control.queue_depth_warn || 0),
      },
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/ownership" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 200)));
    const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const fallback = state.queueOwnerships.map((item) => String(item.project_id || "")).filter(Boolean);
    const targets = (requested.length ? requested : fallback).slice(0, limit);
    const ownership = targets.map((item) => getQueueOwnership(item));
    sendJson(res, 200, {
      requested_projects: requested,
      ownership,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/ownership" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const ownership = upsertQueueOwnership(projectId, {
      owner_name: body.owner_name == null ? null : String(body.owner_name),
      owner_contact: body.owner_contact == null ? null : String(body.owner_contact),
      oncall_channel: body.oncall_channel == null ? null : String(body.oncall_channel),
      escalation_channel: body.escalation_channel == null ? null : String(body.escalation_channel),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "ownership_updated",
      actor: String(body.updated_by || "web_ui"),
      reason: "queue_ownership_routing_update",
      pausedUntil: null,
      payload: {
        owner_name: ownership.owner_name,
        owner_contact: ownership.owner_contact,
        oncall_channel: ownership.oncall_channel,
        escalation_channel: ownership.escalation_channel,
      },
    });
    sendJson(res, 200, {
      status: "ok",
      ownership,
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/hooks" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const limit = Math.max(1, Math.min(200, Number(queryParam(url, "limit") || 200)));
    const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    const hooks = listQueueIncidentHooks(projectIds, limit, projectId, false, actorRoles);
    sendJson(res, 200, {
      requested_projects: requested,
      hooks,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/policies" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const limit = Math.max(1, Math.min(1000, Number(queryParam(url, "limit") || 500)));
    const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    const policies = listQueueIncidentPolicies(projectIds, limit, projectId, false, actorRoles);
    sendJson(res, 200, {
      requested_projects: requested,
      policies,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/preflight/presets" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const includeDisabled = String(queryParam(url, "include_disabled") || "true") === "true";
    const runBeforeOnly = String(queryParam(url, "run_before_live_sync_only") || "false") === "true";
    const limit = Math.max(1, Math.min(2000, Number(queryParam(url, "limit") || 500)));
    const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const presets = listQueueIncidentPreflightPresets({
      projectId,
      projectIdsRaw: projectIds,
      includeDisabled,
      includeRunBeforeLiveSyncOnly: runBeforeOnly,
      limit,
    });
    sendJson(res, 200, {
      requested_projects: requested,
      include_disabled: includeDisabled,
      run_before_live_sync_only: runBeforeOnly,
      presets,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/preflight/presets" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    try {
      const preset = upsertQueueIncidentPreflightPreset(projectId, {
        preset_key: body.preset_key == null ? null : String(body.preset_key),
        name: String(body.name || ""),
        enabled: Boolean(body.enabled ?? true),
        alert_code: String(body.alert_code || ""),
        health: body.health == null ? "critical" : String(body.health),
        additional_alert_codes: Array.isArray(body.additional_alert_codes) ? body.additional_alert_codes : [],
        expected_decision: body.expected_decision == null ? "open" : String(body.expected_decision),
        required_provider: body.required_provider == null ? null : String(body.required_provider),
        run_before_live_sync: Boolean(body.run_before_live_sync ?? true),
        severity: body.severity == null ? "warning" : String(body.severity),
        strict_mode: Boolean(body.strict_mode ?? true),
        metadata:
          body.metadata && typeof body.metadata === "object" && !Array.isArray(body.metadata)
            ? body.metadata
            : {},
        updated_by: String(body.updated_by || "web_ui"),
      });
      appendQueueAuditEvent({
        projectId,
        action: "incident_preflight_preset_updated",
        actor: String(body.updated_by || "web_ui"),
        reason: "queue_incident_preflight_preset_update",
        pausedUntil: null,
        payload: {
          preset_id: preset.id,
          preset_key: preset.preset_key,
          name: preset.name,
          enabled: preset.enabled,
          alert_code: preset.alert_code,
          health: preset.health,
          expected_decision: preset.expected_decision,
          required_provider: preset.required_provider,
          run_before_live_sync: preset.run_before_live_sync,
          severity: preset.severity,
          strict_mode: preset.strict_mode,
        },
      });
      sendJson(res, 200, { status: "ok", preset });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, 422, { detail });
    }
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/preflight/run" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    const requested = [...parseCsvProjects(body.project_ids), ...(body.project_id ? [String(body.project_id)] : [])]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const payload = runQueueIncidentPreflightChecks({
      projectIds: requested,
      presetIds: Array.isArray(body.preset_ids) ? body.preset_ids : [],
      includeDisabled: Boolean(body.include_disabled ?? false),
      includeRunBeforeLiveSyncOnly: Boolean(body.include_run_before_live_sync_only ?? true),
      actor: String(body.actor || "web_ui"),
      actorRoles,
      recordAudit: Boolean(body.record_audit ?? true),
      limit: Math.max(1, Math.min(200, Number(body.limit || 100))),
    });
    sendJson(res, 200, payload);
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/policies" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    try {
      const policy = upsertQueueIncidentPolicy(projectId, {
        alert_code: String(body.alert_code || ""),
        enabled: Boolean(body.enabled ?? true),
        priority: Number(body.priority || 100),
        provider_override: body.provider_override == null ? null : String(body.provider_override),
        open_webhook_url: body.open_webhook_url == null ? null : String(body.open_webhook_url),
        resolve_webhook_url: body.resolve_webhook_url == null ? null : String(body.resolve_webhook_url),
        provider_config_override:
          body.provider_config_override &&
          typeof body.provider_config_override === "object" &&
          !Array.isArray(body.provider_config_override)
            ? body.provider_config_override
            : {},
        severity_by_health:
          body.severity_by_health && typeof body.severity_by_health === "object" && !Array.isArray(body.severity_by_health)
            ? body.severity_by_health
            : {},
        open_on_health: Array.isArray(body.open_on_health) ? body.open_on_health : [],
        secret_edit_roles: Array.isArray(body.secret_edit_roles) ? body.secret_edit_roles : undefined,
        updated_by: String(body.updated_by || "web_ui"),
      }, actorRoles);
      appendQueueAuditEvent({
        projectId,
        action: "incident_policy_updated",
        actor: String(body.updated_by || "web_ui"),
        reason: "queue_incident_policy_update",
        pausedUntil: null,
        payload: {
          policy_id: policy.id,
          alert_code: policy.alert_code,
          enabled: policy.enabled,
          priority: policy.priority,
          provider_override: policy.provider_override,
          open_on_health: policy.open_on_health,
          severity_by_health: policy.severity_by_health,
        },
      });
      sendJson(res, 200, { status: "ok", policy });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, detail === "incident_secret_edit_forbidden" ? 403 : 422, { detail });
    }
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/policies/simulate" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    try {
      const payload = simulateIncidentPolicyRoute({
        projectId,
        alertCode: String(body.alert_code || ""),
        health: body.health == null ? "critical" : String(body.health),
        additionalAlertCodes: Array.isArray(body.additional_alert_codes) ? body.additional_alert_codes : [],
        includeSecrets: Boolean(body.include_secrets ?? false),
        actor: String(body.actor || "web_ui"),
        actorRoles,
      });
      sendJson(res, 200, payload);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, 422, { detail });
    }
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/hooks" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const actorRoles = parseIncidentActorRoles(req.headers["x-synapse-roles"]);
    try {
      const hook = upsertQueueIncidentHook(projectId, {
        enabled: Boolean(body.enabled ?? false),
        provider: body.provider == null ? "webhook" : String(body.provider),
        open_webhook_url: body.open_webhook_url == null ? null : String(body.open_webhook_url),
        resolve_webhook_url: body.resolve_webhook_url == null ? null : String(body.resolve_webhook_url),
        provider_config:
          body.provider_config && typeof body.provider_config === "object" && !Array.isArray(body.provider_config)
            ? body.provider_config
            : {},
        open_on_health: Array.isArray(body.open_on_health) ? body.open_on_health : ["critical"],
        auto_resolve: Boolean(body.auto_resolve ?? true),
        cooldown_minutes: Number(body.cooldown_minutes || 30),
        timeout_sec: Number(body.timeout_sec || 10),
        secret_edit_roles: Array.isArray(body.secret_edit_roles) ? body.secret_edit_roles : undefined,
        updated_by: String(body.updated_by || "web_ui"),
      }, actorRoles);
      appendQueueAuditEvent({
        projectId,
        action: "incident_hook_updated",
        actor: String(body.updated_by || "web_ui"),
        reason: "queue_incident_hook_update",
        pausedUntil: null,
        payload: {
          enabled: hook.enabled,
          provider: hook.provider,
          open_on_health: hook.open_on_health,
          auto_resolve: hook.auto_resolve,
          cooldown_minutes: hook.cooldown_minutes,
          timeout_sec: hook.timeout_sec,
          has_open_webhook_url: Boolean(hook.open_webhook_url),
          has_resolve_webhook_url: Boolean(hook.resolve_webhook_url),
          provider_config_keys:
            hook.provider_config && typeof hook.provider_config === "object"
              ? Object.keys(hook.provider_config).sort()
              : [],
        },
      });
      sendJson(res, 200, { status: "ok", hook });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, detail === "incident_secret_edit_forbidden" ? 403 : 422, { detail });
    }
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const statusFilter = queryParam(url, "status") || null;
    const limit = Math.max(1, Math.min(500, Number(queryParam(url, "limit") || 120)));
    const requested = [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)]
      .map((item) => String(item || "").trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const incidents = listQueueIncidents(projectIds, {
      status: statusFilter && ["open", "resolved"].includes(statusFilter) ? statusFilter : null,
      limit,
      singleProject: projectId,
    });
    sendJson(res, 200, {
      requested_projects: requested,
      status_filter: statusFilter && ["open", "resolved"].includes(statusFilter) ? statusFilter : null,
      incidents,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/sync/schedules" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || "";
    const projectIds = queryParam(url, "project_ids") || "";
    const scheduleIds = queryParam(url, "schedule_ids") || "";
    const enabledRaw = queryParam(url, "enabled");
    const statusRaw = String(queryParam(url, "status") || "").trim().toLowerCase();
    const status = ["ok", "partial_failure", "failed", "skipped", "never"].includes(statusRaw) ? statusRaw : null;
    const projectContains = String(queryParam(url, "project_contains") || "").trim().slice(0, 256);
    const nameContains = String(queryParam(url, "name_contains") || "").trim().slice(0, 256);
    const dueOnly = String(queryParam(url, "due_only") || "false").trim().toLowerCase() === "true";
    const sortByRaw = String(queryParam(url, "sort_by") || "next_run_at").trim().toLowerCase();
    const sortBy = ["next_run_at", "updated_at", "last_run_at", "name", "project_id", "status"].includes(sortByRaw)
      ? sortByRaw
      : "next_run_at";
    const sortDir = String(queryParam(url, "sort_dir") || "asc").trim().toLowerCase() === "desc" ? "desc" : "asc";
    const cursorRaw = String(queryParam(url, "cursor") || "").trim();
    let resolvedOffset = Math.max(0, Number(queryParam(url, "offset") || 0));
    try {
      const decodedOffset = decodeIncidentSyncScheduleFleetCursor(cursorRaw);
      if (decodedOffset != null) {
        resolvedOffset = decodedOffset;
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, 422, { detail });
      return;
    }
    const limit = Math.max(1, Math.min(500, Number(queryParam(url, "limit") || 200)));
    const enabled =
      enabledRaw == null
        ? null
        : String(enabledRaw).trim().toLowerCase() === "true"
          ? true
          : String(enabledRaw).trim().toLowerCase() === "false"
            ? false
            : null;
    const effectiveEnabled = dueOnly && enabled == null ? true : enabled;
    const allRows = filterQueueIncidentSyncSchedules({
      projectIdsRaw: projectIds,
      singleProject: projectId,
      scheduleIdsRaw: scheduleIds,
      enabled: effectiveEnabled,
      dueOnly,
      projectContains,
      nameContains,
      status,
    }).sort((a, b) => compareQueueIncidentSyncScheduleRows(a, b, sortBy, sortDir));
    const total = allRows.length;
    const rows = allRows.slice(resolvedOffset, resolvedOffset + limit).map((item) => ({ ...item }));
    const hasMore = resolvedOffset + rows.length < total;
    const nextCursor = hasMore ? encodeIncidentSyncScheduleFleetCursor(resolvedOffset + rows.length) : null;
    sendJson(res, 200, {
      requested_projects: [...(projectId ? [projectId] : []), ...parseCsvProjects(projectIds)].filter(
        (item, index, all) => item.length > 0 && all.indexOf(item) === index,
      ),
      requested_schedule_ids: String(scheduleIds || "")
        .split(",")
        .map((item) => String(item || "").trim())
        .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index),
      enabled_filter: effectiveEnabled,
      status_filter: status,
      project_contains_filter: projectContains || null,
      name_contains_filter: nameContains || null,
      due_only: dueOnly,
      sort_by: sortBy,
      sort_dir: sortDir,
      paging: {
        limit,
        offset: resolvedOffset,
        cursor: cursorRaw || null,
        next_cursor: nextCursor,
        has_more: hasMore,
        total,
      },
      schedules: rows,
      generated_at: nowIso(),
    });
    return;
  }
  if (
    url.pathname.startsWith("/v1/gatekeeper/calibration/operations/incidents/sync/schedules/") &&
    url.pathname.endsWith("/timeline") &&
    req.method === "GET"
  ) {
    const pathParts = url.pathname.split("/").filter(Boolean);
    const scheduleId = String(pathParts[pathParts.length - 2] || "").trim();
    const projectId = String(queryParam(url, "project_id") || "").trim();
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const limit = Math.max(1, Math.min(500, Number(queryParam(url, "limit") || 120)));
    const payload = buildQueueIncidentSyncScheduleTimeline({
      scheduleId,
      projectId,
      days,
      limit,
    });
    if (!payload) {
      sendJson(res, 404, { detail: "incident_sync_schedule_not_found" });
      return;
    }
    sendJson(res, 200, payload);
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/sync/schedules" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    try {
      const schedule = upsertQueueIncidentSyncSchedule(projectId, body);
      appendQueueAuditEvent({
        projectId,
        action: "incident_sync_schedule_updated",
        actor: String(body.updated_by || "web_ui"),
        reason: `schedule:${String(schedule.name || schedule.id)}`,
        pausedUntil: null,
        payload: {
          schedule_id: schedule.id,
          enabled: schedule.enabled,
          preset: schedule.preset,
          interval_minutes: schedule.interval_minutes,
          window_hours: schedule.window_hours,
          batch_size: schedule.batch_size,
          sync_limit: schedule.sync_limit,
          dry_run: schedule.dry_run,
          force_resolve: schedule.force_resolve,
          preflight_enforcement_mode: schedule.preflight_enforcement_mode,
          preflight_pause_hours: schedule.preflight_pause_hours,
          preflight_critical_fail_threshold: schedule.preflight_critical_fail_threshold,
          preflight_include_run_before_live_sync_only: schedule.preflight_include_run_before_live_sync_only,
          preflight_record_audit: schedule.preflight_record_audit,
          requested_by: schedule.requested_by,
          next_run_at: schedule.next_run_at,
        },
      });
      sendJson(res, 200, { status: "ok", schedule });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      sendJson(res, 422, { detail });
    }
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/sync/schedules/run" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const payload = runQueueIncidentSyncSchedules({
      projectIdsRaw: Array.isArray(body.project_ids) ? body.project_ids.join(",") : "",
      singleProject: String(body.project_id || ""),
      scheduleIdsRaw: Array.isArray(body.schedule_ids) ? body.schedule_ids.join(",") : "",
      actor: String(body.actor || "incident_sync_scheduler"),
      forceRun: Boolean(body.force_run ?? false),
      skipDueCheck: Boolean(body.skip_due_check ?? false),
      limit: Math.max(1, Math.min(200, Number(body.limit || 200))),
    });
    sendJson(res, 200, payload);
    return;
  }
  if (url.pathname.startsWith("/v1/gatekeeper/calibration/operations/incidents/sync/schedules/") && req.method === "DELETE") {
    const id = String(url.pathname.split("/").pop() || "").trim();
    const projectId = String(queryParam(url, "project_id") || "");
    const updatedBy = String(queryParam(url, "updated_by") || "web_ui");
    const index = state.queueIncidentSyncSchedules.findIndex(
      (item) => String(item.id) === id && (!projectId || String(item.project_id) === projectId),
    );
    if (index < 0) {
      sendJson(res, 404, { detail: "incident_sync_schedule_not_found" });
      return;
    }
    const [removed] = state.queueIncidentSyncSchedules.splice(index, 1);
    appendQueueAuditEvent({
      projectId: String(removed.project_id || projectIdDefault),
      action: "incident_sync_schedule_deleted",
      actor: updatedBy,
      reason: `schedule:${String(removed.name || removed.id)}`,
      pausedUntil: null,
      payload: {
        schedule_id: String(removed.id || ""),
        schedule_name: String(removed.name || ""),
      },
    });
    sendJson(res, 200, {
      status: "ok",
      deleted_schedule_id: String(removed.id || ""),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/sync" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || "").trim();
    const projectIds = Array.isArray(body.project_ids) ? body.project_ids.join(",") : "";
    const actor = String(body.actor || "web_ui");
    const windowHours = Math.max(1, Math.min(168, Number(body.window_hours || 24)));
    const limit = Math.max(1, Math.min(200, Number(body.limit || 50)));
    const dryRun = Boolean(body.dry_run ?? false);
    const forceResolve = Boolean(body.force_resolve ?? false);
    const preflightEnforcementMode = String(body.preflight_enforcement_mode || "inherit").trim().toLowerCase();
    const preflightPauseHours =
      body.preflight_pause_hours == null ? null : Math.max(1, Math.min(168, Number(body.preflight_pause_hours)));
    const preflightCriticalFailThreshold =
      body.preflight_critical_fail_threshold == null
        ? null
        : Math.max(1, Math.min(100, Number(body.preflight_critical_fail_threshold)));
    const preflightIncludeRunBeforeLiveSyncOnly = Boolean(body.preflight_include_run_before_live_sync_only ?? true);
    const preflightRecordAudit = Boolean(body.preflight_record_audit ?? true);
    const payload = syncQueueIncidentHooks({
      projectIdsRaw: projectIds,
      singleProject: projectId,
      actor,
      windowHours,
      dryRun,
      forceResolve,
      preflightEnforcementMode,
      preflightPauseHours,
      preflightCriticalFailThreshold,
      preflightIncludeRunBeforeLiveSyncOnly,
      preflightRecordAudit,
      limit,
    });
    sendJson(res, 200, payload);
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/incidents/sync/enforcement" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const control = upsertQueueControl(projectId, {
      incident_preflight_enforcement_mode: String(body.incident_preflight_enforcement_mode || "off").trim().toLowerCase(),
      incident_preflight_pause_hours: Math.max(1, Math.min(168, Number(body.incident_preflight_pause_hours || 4))),
      incident_preflight_critical_fail_threshold: Math.max(
        1,
        Math.min(100, Number(body.incident_preflight_critical_fail_threshold || 1)),
      ),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "incident_sync_enforcement_updated",
      actor: String(body.updated_by || "web_ui"),
      reason: "queue_incident_sync_enforcement_update",
      pausedUntil: control.paused_until,
      payload: {
        incident_preflight_enforcement_mode: control.incident_preflight_enforcement_mode,
        incident_preflight_pause_hours: control.incident_preflight_pause_hours,
        incident_preflight_critical_fail_threshold: control.incident_preflight_critical_fail_threshold,
      },
    });
    sendJson(res, 200, {
      status: "ok",
      control,
      throughput: buildQueueThroughput(projectId, 24),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/control" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const control = upsertQueueControl(projectId, {
      worker_lag_sla_minutes: Number(body.worker_lag_sla_minutes || 20),
      queue_depth_warn: Number(body.queue_depth_warn || 12),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "control_updated",
      actor: String(body.updated_by || "web_ui"),
      reason: null,
      pausedUntil: control.paused_until,
      payload: {
        worker_lag_sla_minutes: control.worker_lag_sla_minutes,
        queue_depth_warn: control.queue_depth_warn,
      },
    });
    sendJson(res, 200, {
      status: "ok",
      control,
      throughput: buildQueueThroughput(projectId, 24),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/pause" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const pauseHours = Math.max(1, Math.min(168, Number(body.pause_hours || 1)));
    const pausedUntil =
      body.paused_until && String(body.paused_until).trim()
        ? new Date(String(body.paused_until)).toISOString()
        : new Date(Date.now() + pauseHours * 60 * 60 * 1000).toISOString();
    const control = upsertQueueControl(projectId, {
      paused_until: pausedUntil,
      pause_reason: body.reason == null ? null : String(body.reason),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "pause",
      actor: String(body.updated_by || "web_ui"),
      reason: body.reason == null ? null : String(body.reason),
      pausedUntil,
      payload: { pause_hours: pauseHours },
    });
    sendJson(res, 200, {
      status: "ok",
      control,
      throughput: buildQueueThroughput(projectId, 24),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/resume" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const control = upsertQueueControl(projectId, {
      paused_until: null,
      pause_reason: body.reason == null ? null : String(body.reason),
      updated_by: String(body.updated_by || "web_ui"),
    });
    appendQueueAuditEvent({
      projectId,
      action: "resume",
      actor: String(body.updated_by || "web_ui"),
      reason: body.reason == null ? null : String(body.reason),
      pausedUntil: null,
      payload: {},
    });
    sendJson(res, 200, {
      status: "ok",
      control,
      throughput: buildQueueThroughput(projectId, 24),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/bulk_pause" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const targets = parseCsvProjects(Array.isArray(body.project_ids) ? body.project_ids.join(",") : "");
    const pauseHours = Math.max(1, Math.min(168, Number(body.pause_hours || 1)));
    const pausedUntil =
      body.paused_until && String(body.paused_until).trim()
        ? new Date(String(body.paused_until)).toISOString()
        : new Date(Date.now() + pauseHours * 60 * 60 * 1000).toISOString();
    const results = targets.map((projectId) => ({
      project_id: projectId,
      status: "ok",
      control: upsertQueueControl(projectId, {
        paused_until: pausedUntil,
        pause_reason: body.reason == null ? null : String(body.reason),
        updated_by: String(body.updated_by || "web_ui"),
      }),
    }));
    for (const item of results) {
      appendQueueAuditEvent({
        projectId: item.project_id,
        action: "bulk_pause",
        actor: String(body.updated_by || "web_ui"),
        reason: body.reason == null ? null : String(body.reason),
        pausedUntil,
        payload: { pause_hours: pauseHours, bulk_size: results.length },
      });
    }
    sendJson(res, 200, {
      status: "ok",
      paused_until: pausedUntil,
      projects_total: results.length,
      results,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/bulk_resume" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const targets = parseCsvProjects(Array.isArray(body.project_ids) ? body.project_ids.join(",") : "");
    const results = targets.map((projectId) => ({
      project_id: projectId,
      status: "ok",
      control: upsertQueueControl(projectId, {
        paused_until: null,
        pause_reason: body.reason == null ? null : String(body.reason),
        updated_by: String(body.updated_by || "web_ui"),
      }),
    }));
    for (const item of results) {
      appendQueueAuditEvent({
        projectId: item.project_id,
        action: "bulk_resume",
        actor: String(body.updated_by || "web_ui"),
        reason: body.reason == null ? null : String(body.reason),
        pausedUntil: null,
        payload: { bulk_size: results.length },
      });
    }
    sendJson(res, 200, {
      status: "ok",
      projects_total: results.length,
      results,
      generated_at: nowIso(),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/throughput/audit" && req.method === "GET") {
    const projectId = queryParam(url, "project_id");
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const limit = Math.max(1, Math.min(1000, Number(queryParam(url, "limit") || 120)));
    const sinceMs = Date.now() - days * 24 * 60 * 60 * 1000;
    const events = state.queueAuditEvents
      .filter((item) => {
        if (projectId && item.project_id !== projectId) return false;
        const ts = new Date(item.created_at).getTime();
        return Number.isFinite(ts) && ts >= sinceMs;
      })
      .slice(0, limit)
      .map((item) => ({
        ...item,
        annotation: latestQueueAuditAnnotation(item.id),
      }));
    sendJson(res, 200, {
      project_id: projectId || null,
      days,
      since: new Date(sinceMs).toISOString(),
      events,
      generated_at: nowIso(),
    });
    return;
  }
  {
    const match = url.pathname.match(/^\/v1\/gatekeeper\/calibration\/operations\/throughput\/audit\/(\d+)\/(acknowledge|resolve)$/);
    if (match && req.method === "POST") {
      const eventId = Number(match[1]);
      const mode = String(match[2] || "");
      const body = await readJsonBody(req).catch(() => ({}));
      const projectId = String(body.project_id || projectIdDefault);
      const event = state.queueAuditEvents.find((item) => Number(item.id) === eventId && item.project_id === projectId) || null;
      if (!event) {
        sendJson(res, 404, { detail: "queue_audit_event_not_found" });
        return;
      }
      const annotation = appendQueueAuditAnnotation({
        eventId,
        projectId,
        status: mode === "resolve" ? "resolved" : "acknowledged",
        createdBy: String(body.created_by || "web_ui"),
        note: body.note == null ? null : String(body.note),
        followUpOwner: body.follow_up_owner == null ? null : String(body.follow_up_owner),
      });
      sendJson(res, 200, {
        status: "ok",
        event: {
          ...event,
          annotation,
        },
        annotation,
      });
      return;
    }
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/queue" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const dryRun = Boolean(body.dry_run ?? false);
    if (!dryRun) {
      const requiredPhrase = `RUN ${projectId}`;
      if (!Boolean(body.confirm)) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_required" });
        return;
      }
      if (String(body.confirmation_phrase || "") !== requiredPhrase) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_phrase_mismatch" });
        return;
      }
      if (!String(body.operation_token || "").trim()) {
        sendJson(res, 422, { detail: "calibration_operation_token_required" });
        return;
      }
    }
    const token = String(body.operation_token || `${dryRun ? "dryrun" : "run"}-${randomUUID().slice(0, 10)}`);
    const existing = state.operationRuns.find((item) => item.project_id === projectId && item.operation_token === token);
    if (existing) {
      maybeAdvanceOperationRun(existing);
      sendJson(res, 200, {
        status: existing.status === "succeeded" ? "ok" : existing.status,
        run: serializeOperationRun(existing),
        idempotent_replay: true,
      });
      return;
    }
    const run = createQueuedOperationRun(projectId, body);
    state.operationRuns.unshift(run);
    const control = getQueueControl(projectId);
    sendJson(res, 200, {
      status: "queued",
      run: serializeOperationRun(run),
      next_action: control.pause_active ? "queue_paused" : "run_gatekeeper_calibration_operation_queue_worker",
      queue_paused: Boolean(control.pause_active),
      queue_resume_at: control.paused_until || null,
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/runs" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const status = queryParam(url, "status");
    const mode = queryParam(url, "mode");
    const limit = Math.max(1, Math.min(500, Number(queryParam(url, "limit") || 50)));
    const rows = state.operationRuns
      .filter((item) => item.project_id === projectId)
      .filter((item) => (status ? item.status === status : true))
      .filter((item) => (mode ? item.mode === mode : true));
    rows.forEach((item) => maybeAdvanceOperationRun(item));
    sendJson(res, 200, {
      project_id: projectId,
      runs: rows.slice(0, limit).map((item) => serializeOperationRun(item)),
    });
    return;
  }
  if (url.pathname.startsWith("/v1/gatekeeper/calibration/operations/runs/") && req.method === "GET") {
    const parts = url.pathname.split("/");
    const runId = parts[parts.length - 1];
    const eventsMode = runId === "events";
    if (!eventsMode) {
      const projectId = queryParam(url, "project_id") || projectIdDefault;
      const run = state.operationRuns.find((item) => item.id === runId && item.project_id === projectId);
      if (!run) {
        sendJson(res, 404, { error: "calibration_operation_run_not_found" });
        return;
      }
      maybeAdvanceOperationRun(run);
      const eventLimit = Math.max(0, Math.min(1000, Number(queryParam(url, "event_limit") || 100)));
      const events = run._events.slice(Math.max(0, run._events.length - eventLimit));
      sendJson(res, 200, {
        run: serializeOperationRun(run),
        events,
        terminal: ["succeeded", "failed", "canceled"].includes(run.status),
      });
      return;
    }
  }
  if (url.pathname.match(/^\/v1\/gatekeeper\/calibration\/operations\/runs\/[^/]+\/events$/) && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const runId = url.pathname.split("/")[6];
    const run = state.operationRuns.find((item) => item.id === runId && item.project_id === projectId);
    if (!run) {
      sendJson(res, 404, { error: "calibration_operation_run_not_found" });
      return;
    }
    maybeAdvanceOperationRun(run);
    const afterEventId = Number(queryParam(url, "after_event_id") || 0);
    const limit = Math.max(1, Math.min(1000, Number(queryParam(url, "limit") || 200)));
    const events = run._events.filter((item) => Number(item.id) > afterEventId).slice(0, limit);
    sendJson(res, 200, {
      run_id: run.id,
      project_id: projectId,
      events,
      next_event_id: events.length ? events[events.length - 1].id : afterEventId,
      terminal: ["succeeded", "failed", "canceled"].includes(run.status),
      run: serializeOperationRun(run),
    });
    return;
  }
  if (url.pathname.match(/^\/v1\/gatekeeper\/calibration\/operations\/runs\/[^/]+\/stream$/) && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const runId = url.pathname.split("/")[6];
    const run = state.operationRuns.find((item) => item.id === runId && item.project_id === projectId);
    if (!run) {
      sendJson(res, 404, { error: "calibration_operation_run_not_found" });
      return;
    }
    maybeAdvanceOperationRun(run);
    const afterEventId = Number(queryParam(url, "after_event_id") || 0);
    const events = run._events.filter((item) => Number(item.id) > afterEventId);
    const terminal = ["succeeded", "failed", "canceled"].includes(run.status);
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "Access-Control-Allow-Origin": "*",
    });
    for (const event of events) {
      res.write(`event: progress\ndata: ${JSON.stringify(event)}\n\n`);
    }
    const statusPayload = {
      run_id: run.id,
      project_id: projectId,
      status: run.status,
      progress_percent: run.progress_percent,
      progress_phase: run.progress_phase,
      terminal,
      cursor: events.length ? events[events.length - 1].id : afterEventId,
      updated_at: run.updated_at,
    };
    res.write(`event: status\ndata: ${JSON.stringify(statusPayload)}\n\n`);
    res.write(`event: ${terminal ? "done" : "timeout"}\ndata: ${JSON.stringify(statusPayload)}\n\n`);
    res.end();
    return;
  }
  if (url.pathname.match(/^\/v1\/gatekeeper\/calibration\/operations\/runs\/[^/]+\/cancel$/) && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const runId = url.pathname.split("/")[6];
    const run = state.operationRuns.find((item) => item.id === runId && item.project_id === projectId);
    if (!run) {
      sendJson(res, 404, { error: "calibration_operation_run_not_found" });
      return;
    }
    if (["succeeded", "failed", "canceled"].includes(run.status)) {
      sendJson(res, 200, { status: "already_terminal", run: serializeOperationRun(run) });
      return;
    }
    const actor = String(body.requested_by || "web_ui");
    const reason = String(body.reason || "");
    if (run.status === "queued") {
      run.status = "canceled";
      run.cancel_requested = true;
      run.cancel_requested_by = actor;
      run.cancel_requested_at = nowIso();
      run.finished_at = nowIso();
      run.error_message = reason || "canceled_before_start";
      appendOperationEvent(run, "canceled", "canceled", "Operation canceled before worker start.", 100, { reason });
    } else {
      run.status = "cancel_requested";
      run.cancel_requested = true;
      run.cancel_requested_by = actor;
      run.cancel_requested_at = nowIso();
      run.error_message = reason || null;
      appendOperationEvent(run, "cancel_requested", "cancel_requested", "Cancel requested by operator.", run.progress_percent, { reason });
    }
    sendJson(res, 200, { status: "ok", run: serializeOperationRun(run) });
    return;
  }
  if (url.pathname.match(/^\/v1\/gatekeeper\/calibration\/operations\/runs\/[^/]+\/retry$/) && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const runId = url.pathname.split("/")[6];
    const source = state.operationRuns.find((item) => item.id === runId && item.project_id === projectId);
    if (!source) {
      sendJson(res, 404, { error: "calibration_operation_run_not_found" });
      return;
    }
    if (!["failed", "canceled"].includes(source.status)) {
      sendJson(res, 409, { detail: `calibration_operation_retry_not_allowed:${source.status}` });
      return;
    }
    const attemptNo = Number(source.attempt_no || 1) + 1;
    const maxAttempts = Number(source.max_attempts || 1);
    if (attemptNo > maxAttempts) {
      sendJson(res, 409, { detail: "calibration_operation_retry_attempts_exhausted" });
      return;
    }
    if (!source.dry_run) {
      const requiredPhrase = `RUN ${projectId}`;
      if (!Boolean(body.confirm)) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_required" });
        return;
      }
      if (String(body.confirmation_phrase || "") !== requiredPhrase) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_phrase_mismatch" });
        return;
      }
      if (!String(body.operation_token || "").trim()) {
        sendJson(res, 422, { detail: "calibration_operation_token_required" });
        return;
      }
    }
    const retryBody = {
      ...(source.request_payload || {}),
      ...body,
      project_id: projectId,
      retry_parent_run_id: source.id,
      retry_attempt_no: attemptNo,
      max_attempts: maxAttempts,
    };
    const run = createQueuedOperationRun(projectId, retryBody);
    run.attempt_no = attemptNo;
    run.max_attempts = maxAttempts;
    run.retry_of = source.id;
    state.operationRuns.unshift(run);
    sendJson(res, 200, {
      status: "queued",
      run: serializeOperationRun(run),
      next_action: "run_gatekeeper_calibration_operation_queue_worker",
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/operations/run" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const dryRun = Boolean(body.dry_run ?? false);
    const forceRun = Boolean(body.force_run ?? true);
    const skipDueCheck = Boolean(body.skip_due_check ?? false);
    if (!dryRun) {
      const requiredPhrase = `RUN ${projectId}`;
      if (!Boolean(body.confirm)) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_required" });
        return;
      }
      if (String(body.confirmation_phrase || "") !== requiredPhrase) {
        sendJson(res, 422, { detail: "calibration_operation_confirmation_phrase_mismatch" });
        return;
      }
      if (!String(body.operation_token || "").trim()) {
        sendJson(res, 422, { detail: "calibration_operation_token_required" });
        return;
      }
    }
    sendJson(res, 200, {
      status: "ok",
      operation: buildCalibrationOperationPayload(projectId, {
        dryRun,
        forceRun,
        skipDueCheck,
      }),
    });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/schedules/observability" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    sendJson(res, 200, buildScheduleObservability(projectId, days));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/observability/compare" && req.method === "GET") {
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const projectIds = queryParam(url, "project_ids");
    sendJson(res, 200, buildObservabilityCompare(days, projectIds));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/observability/compare/drilldown" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    sendJson(res, 200, buildObservabilityCompareDrilldown(projectId, days));
    return;
  }

  if (url.pathname === "/v1/gatekeeper/calibration/schedules" && req.method === "GET") {
    const projectId = queryParam(url, "project_id");
    const schedules = projectId ? state.schedules.filter((item) => item.project_id === projectId) : state.schedules;
    sendJson(res, 200, { schedules });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/calibration/schedules" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    const name = String(body.name || "").trim();
    if (!projectId || !name) {
      sendJson(res, 422, { detail: "project_id_and_name_required" });
      return;
    }
    const now = nowIso();
    const existing = state.schedules.find((item) => item.project_id === projectId && item.name === name);
    const normalized = {
      id: existing?.id || randomUUID(),
      project_id: projectId,
      name,
      enabled: Boolean(body.enabled ?? true),
      preset: String(body.preset || "nightly"),
      interval_hours:
        body.interval_hours == null || body.interval_hours === ""
          ? null
          : Number(body.interval_hours),
      lookback_days: Number(body.lookback_days ?? 60),
      limit_rows: Number(body.limit_rows ?? 20000),
      holdout_ratio: Number(body.holdout_ratio ?? 0.3),
      split_seed: String(body.split_seed || "synapse-gatekeeper-prod-holdout-v1"),
      weights: Array.isArray(body.weights) ? body.weights.map((item) => Number(item)) : [],
      confidences: Array.isArray(body.confidences) ? body.confidences.map((item) => Number(item)) : [],
      score_thresholds: Array.isArray(body.score_thresholds) ? body.score_thresholds.map((item) => Number(item)) : [],
      top_k: Number(body.top_k ?? 5),
      allow_guardrail_fail: Boolean(body.allow_guardrail_fail ?? false),
      snapshot_note: body.snapshot_note == null ? null : String(body.snapshot_note),
      updated_by: body.updated_by == null ? null : String(body.updated_by),
      last_run_at: existing?.last_run_at || null,
      last_status: existing?.last_status || null,
      last_run_summary: existing?.last_run_summary || {},
      created_at: existing?.created_at || now,
      updated_at: now,
    };
    if (existing) {
      Object.assign(existing, normalized);
    } else {
      state.schedules.unshift(normalized);
    }
    sendJson(res, 200, { status: "ok", schedule: normalized });
    return;
  }
  if (url.pathname.startsWith("/v1/gatekeeper/calibration/schedules/") && req.method === "DELETE") {
    const id = decodeURIComponent(url.pathname.split("/").pop() || "");
    const projectId = queryParam(url, "project_id");
    const index = state.schedules.findIndex((item) => item.id === id && (!projectId || item.project_id === projectId));
    if (index < 0) {
      sendJson(res, 404, { detail: "calibration_schedule_not_found" });
      return;
    }
    state.schedules.splice(index, 1);
    sendJson(res, 200, { status: "ok", deleted_schedule_id: id });
    return;
  }

  if (url.pathname === "/v1/gatekeeper/alerts/targets" && req.method === "GET") {
    const projectId = queryParam(url, "project_id");
    const targets = projectId ? state.alertTargets.filter((item) => item.project_id === projectId) : state.alertTargets;
    sendJson(res, 200, { targets });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/alerts/targets" && req.method === "PUT") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || "").trim();
    const channel = String(body.channel || "").trim();
    const targetValue = String(body.target || "").trim();
    if (!projectId || !channel || !targetValue) {
      sendJson(res, 422, { detail: "project_id_channel_target_required" });
      return;
    }
    const now = nowIso();
    const existing = state.alertTargets.find(
      (item) => item.project_id === projectId && item.channel === channel && item.target === targetValue,
    );
    const normalized = {
      id: existing?.id || randomUUID(),
      project_id: projectId,
      channel,
      target: targetValue,
      enabled: Boolean(body.enabled ?? true),
      config: body.config && typeof body.config === "object" ? body.config : {},
      created_by: existing?.created_by || String(body.updated_by || "web_ui"),
      updated_by: String(body.updated_by || "web_ui"),
      created_at: existing?.created_at || now,
      updated_at: now,
    };
    if (existing) {
      Object.assign(existing, normalized);
    } else {
      state.alertTargets.unshift(normalized);
    }
    sendJson(res, 200, { status: "ok", target: normalized });
    return;
  }
  if (url.pathname.startsWith("/v1/gatekeeper/alerts/targets/") && req.method === "DELETE") {
    const id = decodeURIComponent(url.pathname.split("/").pop() || "");
    const projectId = queryParam(url, "project_id");
    const index = state.alertTargets.findIndex((item) => item.id === id && (!projectId || item.project_id === projectId));
    if (index < 0) {
      sendJson(res, 404, { detail: "gatekeeper_alert_target_not_found" });
      return;
    }
    state.alertTargets.splice(index, 1);
    sendJson(res, 200, { status: "ok", deleted_target_id: id });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/alerts/attempts" && req.method === "GET") {
    sendJson(res, 200, {
      attempts: [
        {
          id: "att-1",
          run_id: "run-20260331",
          project_id: projectIdDefault,
          channel: "slack_webhook",
          target: "https://hooks.slack.com/services/test",
          status: "failed",
          alert_codes: ["accuracy_drop_exceeded"],
          error_message: "webhook timeout",
          response_payload: {},
          attempted_at: "2026-03-31T05:12:00Z",
        },
      ],
    });
    return;
  }

  if (url.pathname === "/v1/gatekeeper/config/rollback/preview" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => ({}));
    const projectId = String(body.project_id || projectIdDefault);
    const snapshotId = String(body.snapshot_id || snapshots[0].id);
    sendJson(res, 200, { status: "ok", preview: makeRollbackPreview(projectId, snapshotId) });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/config/rollback/metrics" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const slaHours = Math.max(1, Math.min(720, Number(queryParam(url, "sla_hours") || 24)));
    sendJson(res, 200, computeRollbackMetrics(projectId, days, slaHours));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/config/rollback/attribution" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const groupBy = String(queryParam(url, "group_by") || "cohort");
    sendJson(res, 200, computeRollbackAttribution(projectId, days, groupBy));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/config/rollback/attribution/drilldown" && req.method === "GET") {
    const projectId = queryParam(url, "project_id") || projectIdDefault;
    const days = Math.max(1, Math.min(365, Number(queryParam(url, "days") || 30)));
    const groupBy = String(queryParam(url, "group_by") || "cohort");
    const cohort = String(queryParam(url, "cohort") || "").trim();
    const limit = Math.max(1, Math.min(500, Number(queryParam(url, "limit") || 120)));
    if (!cohort) {
      sendJson(res, 422, { detail: "attribution_cohort_required" });
      return;
    }
    sendJson(res, 200, computeRollbackAttributionDrilldown(projectId, days, groupBy, cohort, limit));
    return;
  }
  if (url.pathname === "/v1/gatekeeper/config/rollback/requests" && req.method === "GET") {
    const projectId = queryParam(url, "project_id");
    const status = queryParam(url, "status");
    let requests = state.rollbackRequests;
    if (projectId) {
      requests = requests.filter((item) => item.project_id === projectId);
    }
    if (status) {
      requests = requests.filter((item) => item.status === status);
    }
    sendJson(res, 200, { requests });
    return;
  }
  if (url.pathname === "/v1/gatekeeper/config/rollback/requests" && req.method === "POST") {
    const body = await readJsonBody(req).catch(() => null);
    if (!body || typeof body !== "object") {
      sendJson(res, 400, { detail: "invalid_json" });
      return;
    }
    const projectId = String(body.project_id || projectIdDefault);
    const snapshotId = String(body.snapshot_id || snapshots[0].id);
    const requestedBy = String(body.requested_by || "web_ui");
    const preview = makeRollbackPreview(projectId, snapshotId);
    const createdAt = nowIso();
    const request = {
      id: randomUUID(),
      project_id: projectId,
      snapshot_id: snapshotId,
      status: "pending_approval",
      requested_by: requestedBy,
      required_approvals: Number(body.required_approvals || 2),
      approvals: [
        {
          actor: requestedBy,
          action: "request_created",
          note: body.note == null ? null : String(body.note),
          created_at: createdAt,
        },
      ],
      preview,
      note: body.note == null ? null : String(body.note),
      rejection_reason: null,
      applied_by: null,
      applied_snapshot_id: null,
      error_message: null,
      created_at: createdAt,
      updated_at: createdAt,
      resolved_at: null,
    };
    state.rollbackRequests.unshift(request);
    sendJson(res, 200, {
      status: "ok",
      request: {
        id: request.id,
        project_id: projectId,
        snapshot_id: snapshotId,
        state: request.status,
        requested_by: request.requested_by,
        required_approvals: request.required_approvals,
        approval_events: request.approvals,
        preview,
        created_at: request.created_at,
        updated_at: request.updated_at,
      },
    });
    return;
  }
  if (url.pathname.startsWith("/v1/gatekeeper/config/rollback/requests/") && req.method === "POST") {
    const segments = url.pathname.split("/");
    const requestId = segments[segments.length - 2];
    const action = segments[segments.length - 1];
    const request = state.rollbackRequests.find((item) => item.id === requestId);
    if (!request) {
      sendJson(res, 404, { detail: "rollback_request_not_found" });
      return;
    }
    const body = await readJsonBody(req).catch(() => ({}));
    const now = nowIso();

    if (action === "approve") {
      const actor = String(body.approved_by || "web_ui");
      if (request.approvals.some((item) => item.actor === actor && item.action === "approved")) {
        sendJson(res, 409, { detail: "approver_already_recorded" });
        return;
      }
      request.approvals.push({
        actor,
        action: "approved",
        note: body.note == null ? null : String(body.note),
        created_at: now,
      });
      const approvalCount = request.approvals.filter((item) => item.action === "approved").length;
      if (approvalCount >= request.required_approvals) {
        request.status = "applied";
        request.applied_by = actor;
        request.applied_snapshot_id = randomUUID();
        request.resolved_at = now;
      }
      request.updated_at = now;
      sendJson(res, 200, { status: "ok", request: { id: request.id, state: request.status } });
      return;
    }

    if (action === "reject") {
      request.status = "rejected";
      request.rejection_reason = String(body.reason || "rejected");
      request.approvals.push({
        actor: String(body.rejected_by || "web_ui"),
        action: "rejected",
        note: request.rejection_reason,
        created_at: now,
      });
      request.updated_at = now;
      request.resolved_at = now;
      sendJson(res, 200, { status: "ok", request: { id: request.id, state: request.status } });
      return;
    }
  }

  notFound(res);
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(`[mock-api] listening on http://127.0.0.1:${port}\n`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
