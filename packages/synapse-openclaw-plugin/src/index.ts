export const DEFAULT_OPENCLAW_EVENTS = [
  "tool:result",
  "message:received",
  "agent:completed",
  "session:reset"
] as const;

export interface SynapseCaptureInput {
  event_type: "tool_result" | "fact_proposed" | "system_signal" | string;
  payload: Record<string, unknown>;
  agent_id?: string;
  session_id?: string;
  tags?: string[];
}

export interface SynapseDraftClaim {
  id: string;
  schema_version: "v1";
  project_id: string;
  entity_key: string;
  category: string;
  claim_text: string;
  status: "draft";
  confidence?: number;
  metadata?: Record<string, unknown>;
  evidence: SynapseEvidenceRef[];
}

export interface SynapseEvidenceRef {
  source_type: "dialog" | "tool_output" | "file" | "human_note" | "external_event";
  source_id: string;
  observed_at?: string;
  provenance?: SynapseProvenanceRecord;
}

export interface SynapseProvenanceRecord {
  schema: "synapse.openclaw.provenance.v1";
  phase: string;
  integration: "openclaw";
  connector: string;
  agent_id?: string;
  session_id?: string;
  captured_at: string;
  signature_alg: "hmac-sha256" | "sha256";
  signature: string;
  payload_sha256: string;
  key_id?: string;
  mode: "signed" | "digest_only";
}

export interface SynapseLikeClient {
  projectId: string;
  capture(event: SynapseCaptureInput): void;
  proposeFact(claim: SynapseDraftClaim): Promise<void> | void;
  listTasks?: (options?: {
    limit?: number;
    assignee?: string;
    entityKey?: string;
    includeClosed?: boolean;
  }) => Promise<Array<Record<string, unknown>>> | Array<Record<string, unknown>>;
  updateTaskStatus?: (
    taskId: string,
    options: {
      status: string;
      updatedBy: string;
      note?: string;
    }
  ) => Promise<Record<string, unknown>> | Record<string, unknown>;
}

export type SearchKnowledgeResolver = (
  query: string,
  limit: number,
  filters: Record<string, unknown>
) => Promise<unknown> | unknown;

export type ListTasksResolver = (options: {
  limit: number;
  assignee?: string;
  entity_key?: string;
  include_closed: boolean;
}) => Promise<Array<Record<string, unknown>>> | Array<Record<string, unknown>>;

export type UpdateTaskStatusResolver = (
  taskId: string,
  options: {
    status: string;
    updated_by: string;
    note?: string;
  }
) => Promise<Record<string, unknown>> | Record<string, unknown>;

export interface SynapseOpenClawPluginOptions {
  searchKnowledge?: SearchKnowledgeResolver;
  listTasks?: ListTasksResolver;
  updateTaskStatus?: UpdateTaskStatusResolver;
  defaultAgentId?: string;
  defaultSessionId?: string;
  provenanceSecret?: string;
  provenanceKeyId?: string;
}

export interface AttachOptions {
  hookEvents?: readonly string[];
  registerTools?: boolean;
  toolPrefix?: string;
}

export interface OpenClawRuntime {
  on?: (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown;
  register_hook?: (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown;
  register_tool?: (name: string, handler: (...args: unknown[]) => unknown, description?: string) => unknown;
}

type SearchToolArgs = {
  query: string;
  limit: number;
  filters: Record<string, unknown>;
};

type ProposeToolArgs = {
  entity_key: string;
  category: string;
  claim_text: string;
  source_id: string;
  source_type: SynapseEvidenceRef["source_type"];
  confidence?: number;
  metadata: Record<string, unknown>;
};

type GetTasksToolArgs = {
  limit: number;
  assignee?: string;
  entity_key?: string;
};

type UpdateTaskToolArgs = {
  task_id: string;
  status: string;
  updated_by?: string;
  note?: string;
};

export class SynapseOpenClawPlugin {
  constructor(
    private readonly client: SynapseLikeClient,
    private readonly options: SynapseOpenClawPluginOptions = {}
  ) {}

  attach(runtime: OpenClawRuntime, options: AttachOptions = {}): void {
    const hookEvents = options.hookEvents ?? DEFAULT_OPENCLAW_EVENTS;
    const registerTools = options.registerTools ?? true;
    const toolPrefix = options.toolPrefix ?? "synapse";
    this.attachHooks(runtime, hookEvents);
    if (registerTools) {
      this.registerTools(runtime, { toolPrefix });
    }
  }

  registerTools(runtime: OpenClawRuntime, options: { toolPrefix?: string } = {}): void {
    const registerTool = this.resolveToolRegistrar(runtime);
    const toolPrefix = options.toolPrefix ?? "synapse";

    if (this.options.searchKnowledge) {
      registerTool(
        `${toolPrefix}_search_wiki`,
        (...args: unknown[]) => this.searchWiki(this.normalizeSearchArgs(args)),
        "Search approved Synapse knowledge for the current task."
      );
    }

    registerTool(
      `${toolPrefix}_propose_to_wiki`,
      (...args: unknown[]) => this.proposeToWiki(this.normalizeProposeArgs(args)),
      "Propose a new fact to Synapse for human review."
    );

    if (this.canListTasks()) {
      registerTool(
        `${toolPrefix}_get_open_tasks`,
        (...args: unknown[]) => this.getOpenTasks(this.normalizeGetTasksArgs(args)),
        "List active Synapse tasks relevant for the current operation."
      );
    }

    if (this.canUpdateTaskStatus()) {
      registerTool(
        `${toolPrefix}_update_task_status`,
        (...args: unknown[]) => this.setTaskStatus(this.normalizeUpdateTaskArgs(args)),
        "Update Synapse task status after execution progress."
      );
    }
  }

  async searchWiki(input: SearchToolArgs): Promise<unknown> {
    if (!this.options.searchKnowledge) {
      throw new Error("SynapseOpenClawPlugin.searchKnowledge callback is not configured.");
    }
    const result = await Promise.resolve(this.options.searchKnowledge(input.query, input.limit, input.filters));
    this.client.capture({
      event_type: "tool_result",
      payload: {
        integration: "openclaw",
        phase: "search_wiki",
        query: input.query,
        limit: input.limit,
        filters: input.filters,
        result_preview: preview(result)
      },
      agent_id: this.options.defaultAgentId,
      session_id: this.options.defaultSessionId,
      tags: ["integration:openclaw", "tool:search_wiki"]
    });
    return result;
  }

  async proposeToWiki(input: ProposeToolArgs): Promise<{ status: "queued"; claim_id: string }> {
    const claimId = makeUuid();
    const observedAt = new Date().toISOString();
    const provenance = await this.buildProvenance("propose_to_wiki", observedAt, {
      project_id: this.client.projectId,
      entity_key: input.entity_key,
      category: input.category,
      claim_text: input.claim_text,
      source_id: input.source_id,
      source_type: input.source_type,
      agent_id: this.options.defaultAgentId ?? null,
      session_id: this.options.defaultSessionId ?? null
    });
    const claimMetadata: Record<string, unknown> = {
      ...input.metadata,
      synapse_provenance: provenance
    };
    const claim: SynapseDraftClaim = {
      id: claimId,
      schema_version: "v1",
      project_id: this.client.projectId,
      entity_key: input.entity_key,
      category: input.category,
      claim_text: input.claim_text,
      status: "draft",
      confidence: input.confidence,
      metadata: claimMetadata,
      evidence: [
        {
          source_type: input.source_type,
          source_id: input.source_id,
          observed_at: observedAt,
          provenance
        }
      ]
    };

    await Promise.resolve(this.client.proposeFact(claim));
    this.client.capture({
      event_type: "fact_proposed",
      payload: {
        integration: "openclaw",
        phase: "propose_to_wiki",
        claim_id: claimId,
        entity_key: input.entity_key,
        category: input.category,
        provenance: {
          signature_alg: provenance.signature_alg,
          signature: provenance.signature,
          key_id: provenance.key_id,
          mode: provenance.mode,
          payload_sha256: provenance.payload_sha256
        }
      },
      agent_id: this.options.defaultAgentId,
      session_id: this.options.defaultSessionId,
      tags: ["integration:openclaw", "tool:propose_to_wiki"]
    });
    return { status: "queued", claim_id: claimId };
  }

  async getOpenTasks(input: GetTasksToolArgs): Promise<{ tasks: Array<Record<string, unknown>> }> {
    const resolver = this.options.listTasks;
    let tasks: Array<Record<string, unknown>> = [];
    if (resolver) {
      const result = await Promise.resolve(
        resolver({
          limit: input.limit,
          assignee: input.assignee,
          entity_key: input.entity_key,
          include_closed: false
        })
      );
      tasks = Array.isArray(result) ? result : [];
    } else if (typeof this.client.listTasks === "function") {
      const result = await Promise.resolve(
        this.client.listTasks({
          limit: input.limit,
          assignee: input.assignee,
          entityKey: input.entity_key,
          includeClosed: false
        })
      );
      tasks = Array.isArray(result) ? result : [];
    }

    this.client.capture({
      event_type: "tool_result",
      payload: {
        integration: "openclaw",
        phase: "get_open_tasks",
        limit: input.limit,
        assignee: input.assignee ?? null,
        entity_key: input.entity_key ?? null,
        result_count: tasks.length
      },
      agent_id: this.options.defaultAgentId,
      session_id: this.options.defaultSessionId,
      tags: ["integration:openclaw", "tool:get_open_tasks"]
    });
    return { tasks };
  }

  async setTaskStatus(input: UpdateTaskToolArgs): Promise<Record<string, unknown>> {
    const actor = asOptionalString(input.updated_by) ?? this.options.defaultAgentId ?? "openclaw_agent";
    const resolver = this.options.updateTaskStatus;

    let result: unknown;
    if (resolver) {
      result = await Promise.resolve(
        resolver(input.task_id, {
          status: input.status,
          updated_by: actor,
          note: input.note
        })
      );
    } else if (typeof this.client.updateTaskStatus === "function") {
      result = await Promise.resolve(
        this.client.updateTaskStatus(input.task_id, {
          status: input.status,
          updatedBy: actor,
          note: input.note
        })
      );
    } else {
      throw new Error("Task status tool requires updateTaskStatus callback or SDK task API support.");
    }

    this.client.capture({
      event_type: "tool_result",
      payload: {
        integration: "openclaw",
        phase: "update_task_status",
        task_id: input.task_id,
        status: input.status,
        updated_by: actor
      },
      agent_id: this.options.defaultAgentId,
      session_id: this.options.defaultSessionId,
      tags: ["integration:openclaw", "tool:update_task_status"]
    });

    if (isRecord(result)) {
      return result;
    }
    return { status: "ok" };
  }

  private canListTasks(): boolean {
    return typeof this.options.listTasks === "function" || typeof this.client.listTasks === "function";
  }

  private canUpdateTaskStatus(): boolean {
    return typeof this.options.updateTaskStatus === "function" || typeof this.client.updateTaskStatus === "function";
  }

  private attachHooks(runtime: OpenClawRuntime, hookEvents: readonly string[]): void {
    const registerHook = this.resolveHookRegistrar(runtime);
    for (const eventName of hookEvents) {
      registerHook(eventName, (event: Record<string, unknown>) => {
        this.client.capture({
          event_type: "system_signal",
          payload: {
            integration: "openclaw",
            phase: "hook_event",
            event_name: eventName,
            event: preview(event)
          },
          agent_id: this.options.defaultAgentId,
          session_id: this.options.defaultSessionId ?? extractEventSessionId(event),
          tags: ["integration:openclaw", `event:${eventName}`]
        });
      });
    }
  }

  private resolveHookRegistrar(
    runtime: OpenClawRuntime
  ): (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown {
    if (typeof runtime.on === "function") {
      return runtime.on.bind(runtime);
    }
    if (typeof runtime.register_hook === "function") {
      return runtime.register_hook.bind(runtime);
    }
    throw new TypeError("OpenClaw runtime must provide on(event, handler) or register_hook(event, handler).");
  }

  private resolveToolRegistrar(
    runtime: OpenClawRuntime
  ): (name: string, handler: (...args: unknown[]) => unknown, description: string) => unknown {
    if (typeof runtime.register_tool !== "function") {
      throw new TypeError("OpenClaw runtime must provide register_tool(name, handler, description).");
    }
    return (name: string, handler: (...args: unknown[]) => unknown, description: string): unknown => {
      try {
        return runtime.register_tool!(name, handler, description);
      } catch {
        return runtime.register_tool!(name, handler);
      }
    };
  }

  private async buildProvenance(
    phase: string,
    observedAt: string,
    payload: Record<string, unknown>
  ): Promise<SynapseProvenanceRecord> {
    const canonicalPayload = stableStringify(payload);
    const payloadSha = await sha256Hex(canonicalPayload);
    const secret = this.resolveProvenanceSecret();
    if (secret) {
      const signature = await hmacSha256Hex(secret, canonicalPayload);
      return {
        schema: "synapse.openclaw.provenance.v1",
        phase,
        integration: "openclaw",
        connector: "@synapse/openclaw-plugin",
        agent_id: this.options.defaultAgentId,
        session_id: this.options.defaultSessionId,
        captured_at: observedAt,
        signature_alg: "hmac-sha256",
        signature,
        payload_sha256: payloadSha,
        key_id: this.resolveProvenanceKeyId(),
        mode: "signed"
      };
    }
    return {
      schema: "synapse.openclaw.provenance.v1",
      phase,
      integration: "openclaw",
      connector: "@synapse/openclaw-plugin",
      agent_id: this.options.defaultAgentId,
      session_id: this.options.defaultSessionId,
      captured_at: observedAt,
      signature_alg: "sha256",
      signature: payloadSha,
      payload_sha256: payloadSha,
      mode: "digest_only"
    };
  }

  private resolveProvenanceSecret(): string | undefined {
    const fromOptions = asOptionalString(this.options.provenanceSecret);
    if (fromOptions) {
      return fromOptions;
    }
    return readProcessEnv("SYNAPSE_OPENCLAW_PROVENANCE_SECRET") ?? readProcessEnv("SYNAPSE_PROVENANCE_SECRET");
  }

  private resolveProvenanceKeyId(): string {
    const fromOptions = asOptionalString(this.options.provenanceKeyId);
    if (fromOptions) {
      return fromOptions;
    }
    return (
      readProcessEnv("SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID") ??
      readProcessEnv("SYNAPSE_PROVENANCE_KEY_ID") ??
      "openclaw-default"
    );
  }

  private normalizeSearchArgs(args: unknown[]): SearchToolArgs {
    if (args.length === 0) {
      throw new TypeError("search_wiki requires query.");
    }

    if (typeof args[0] === "string") {
      const options = isRecord(args[1]) ? args[1] : {};
      return {
        query: args[0],
        limit: normalizeLimit(options.limit ?? args[1], 1, 100, 5),
        filters: isRecord(options.filters) ? options.filters : {}
      };
    }

    if (isRecord(args[0])) {
      const payload = args[0];
      const query = asOptionalString(payload.query);
      if (!query) {
        throw new TypeError("search_wiki requires non-empty query.");
      }
      return {
        query,
        limit: normalizeLimit(payload.limit, 1, 100, 5),
        filters: isRecord(payload.filters) ? payload.filters : {}
      };
    }
    throw new TypeError("search_wiki requires string query or payload with query.");
  }

  private normalizeProposeArgs(args: unknown[]): ProposeToolArgs {
    if (args.length === 1 && isRecord(args[0])) {
      const payload = args[0];
      return {
        entity_key: requireString(payload.entity_key, "entity_key"),
        category: requireString(payload.category, "category"),
        claim_text: requireString(payload.claim_text, "claim_text"),
        source_id: requireString(payload.source_id, "source_id"),
        source_type: normalizeSourceType(payload.source_type),
        confidence: normalizeConfidence(payload.confidence),
        metadata: isRecord(payload.metadata) ? payload.metadata : {}
      };
    }

    if (args.length >= 4) {
      const options = isRecord(args[4]) ? args[4] : {};
      return {
        entity_key: requireString(args[0], "entity_key"),
        category: requireString(args[1], "category"),
        claim_text: requireString(args[2], "claim_text"),
        source_id: requireString(args[3], "source_id"),
        source_type: normalizeSourceType(options.source_type),
        confidence: normalizeConfidence(options.confidence),
        metadata: isRecord(options.metadata) ? options.metadata : {}
      };
    }

    throw new TypeError(
      "propose_to_wiki requires {entity_key, category, claim_text, source_id} or positional arguments."
    );
  }

  private normalizeGetTasksArgs(args: unknown[]): GetTasksToolArgs {
    if (args.length === 0) {
      return { limit: 20 };
    }
    if (isRecord(args[0])) {
      const payload = args[0];
      return {
        limit: normalizeLimit(payload.limit, 1, 200, 20),
        assignee: asOptionalString(payload.assignee),
        entity_key: asOptionalString(payload.entity_key)
      };
    }
    return { limit: normalizeLimit(args[0], 1, 200, 20) };
  }

  private normalizeUpdateTaskArgs(args: unknown[]): UpdateTaskToolArgs {
    if (args.length === 1 && isRecord(args[0])) {
      const payload = args[0];
      return {
        task_id: requireString(payload.task_id, "task_id"),
        status: requireString(payload.status, "status"),
        updated_by: asOptionalString(payload.updated_by),
        note: asOptionalString(payload.note)
      };
    }
    if (args.length >= 2) {
      const taskId = requireString(args[0], "task_id");
      if (isRecord(args[1])) {
        return {
          task_id: taskId,
          status: requireString(args[1].status, "status"),
          updated_by: asOptionalString(args[1].updated_by),
          note: asOptionalString(args[1].note)
        };
      }
      return {
        task_id: taskId,
        status: requireString(args[1], "status"),
        updated_by: asOptionalString(args[2]),
        note: asOptionalString(args[3])
      };
    }
    throw new TypeError("update_task_status requires task_id and status.");
  }
}

export function createSynapseOpenClawPlugin(
  client: SynapseLikeClient,
  options: SynapseOpenClawPluginOptions = {}
): SynapseOpenClawPlugin {
  return new SynapseOpenClawPlugin(client, options);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function normalizeLimit(value: unknown, minValue: number, maxValue: number, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, Math.trunc(parsed)));
}

function normalizeConfidence(value: unknown): number | undefined {
  if (value == null) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return Math.max(0, Math.min(1, parsed));
}

function normalizeSourceType(value: unknown): SynapseEvidenceRef["source_type"] {
  const candidate = asOptionalString(value);
  const allowed = new Set<SynapseEvidenceRef["source_type"]>([
    "dialog",
    "tool_output",
    "file",
    "human_note",
    "external_event"
  ]);
  if (candidate && allowed.has(candidate as SynapseEvidenceRef["source_type"])) {
    return candidate as SynapseEvidenceRef["source_type"];
  }
  return "external_event";
}

function requireString(value: unknown, label: string): string {
  const normalized = asOptionalString(value);
  if (!normalized) {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  return normalized;
}

function asOptionalString(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function preview(value: unknown, maxLength = 2000): string {
  let text: string;
  try {
    text = JSON.stringify(value);
  } catch {
    text = String(value);
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...(truncated)`;
}

function extractEventSessionId(event: Record<string, unknown>): string {
  const sessionKey = asOptionalString(event.sessionKey);
  if (sessionKey) {
    return sessionKey;
  }
  const sessionId = asOptionalString(event.session_id);
  if (sessionId) {
    return sessionId;
  }
  return `openclaw_${makeUuid()}`;
}

function makeUuid(): string {
  if (typeof globalThis.crypto !== "undefined" && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const template = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx";
  return template.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function stableStringify(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortKeys(item));
  }
  if (isRecord(value)) {
    const entries = Object.keys(value)
      .sort((a, b) => a.localeCompare(b))
      .map((key) => [key, sortKeys(value[key])] as const);
    return Object.fromEntries(entries);
  }
  return value;
}

async function sha256Hex(input: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    return fallbackDigest(input);
  }
  const data = new TextEncoder().encode(input);
  const digest = await subtle.digest("SHA-256", data);
  return bytesToHex(new Uint8Array(digest));
}

async function hmacSha256Hex(secret: string, input: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    return fallbackDigest(`${secret}:${input}`);
  }
  const keyData = new TextEncoder().encode(secret);
  const payload = new TextEncoder().encode(input);
  const key = await subtle.importKey("raw", keyData, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await subtle.sign("HMAC", key, payload);
  return bytesToHex(new Uint8Array(signature));
}

function bytesToHex(bytes: Uint8Array): string {
  let out = "";
  for (let index = 0; index < bytes.length; index += 1) {
    out += bytes[index]!.toString(16).padStart(2, "0");
  }
  return out;
}

function fallbackDigest(input: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  const part = (hash >>> 0).toString(16).padStart(8, "0");
  return `${part}${part}${part}${part}${part}${part}${part}${part}`.slice(0, 64);
}

function readProcessEnv(name: string): string | undefined {
  const maybeProcess = globalThis as unknown as { process?: { env?: Record<string, string | undefined> } };
  const raw = maybeProcess.process?.env?.[name];
  return asOptionalString(raw);
}
