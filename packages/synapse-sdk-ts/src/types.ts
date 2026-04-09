export type SchemaVersion = "v1";
export type DegradationMode = "buffer" | "drop" | "sync_flush";
export type AdoptionMode = "full_loop" | "observe_only" | "draft_only" | "retrieve_only";
export type WikiDraftStatus = "pending_review" | "blocked_conflict" | "approved" | "rejected";
export type WikiDraftFilterMode = "exact" | "prefix" | "regex" | "contains";
export type WikiDraftRiskLevel = "low" | "medium" | "high";

export interface EvidenceRef {
  source_type: "dialog" | "tool_output" | "file" | "human_note" | "external_event";
  source_id: string;
  session_id?: string;
  tool_name?: string;
  snippet?: string;
  url?: string;
  observed_at?: string;
  provenance?: Record<string, unknown>;
}

export interface ObservationEvent {
  id: string;
  schema_version: SchemaVersion;
  project_id: string;
  agent_id?: string;
  session_id?: string;
  trace_id?: string;
  span_id?: string;
  parent_span_id?: string;
  event_type: "tool_result" | "agent_message" | "user_message" | "system_signal" | "fact_proposed" | "memory_backfill";
  payload: Record<string, unknown>;
  tags?: string[];
  observed_at: string;
}

export interface Claim {
  id: string;
  schema_version: SchemaVersion;
  project_id: string;
  entity_key: string;
  category: string;
  claim_text: string;
  status: "draft" | "approved" | "rejected" | "expired";
  confidence?: number;
  valid_from?: string;
  valid_to?: string;
  metadata?: Record<string, unknown>;
  evidence: EvidenceRef[];
}

export interface DraftPage {
  id: string;
  schema_version: SchemaVersion;
  project_id: string;
  title: string;
  path: string;
  markdown: string;
  claims: string[];
  summary?: string;
  created_at?: string;
}

export interface SynapseConfig {
  apiKey?: string;
  apiUrl: string;
  projectId: string;
  flushIntervalMs?: number;
  retry?: RetryPolicyConfig;
  degradationMode?: DegradationMode;
}

export interface MonitorOptions {
  integration?: "generic" | "langgraph" | "langchain" | "crewai" | "openclaw" | string;
  includeMethods?: string[];
  agentId?: string;
  sessionId?: string;
  flushOnSuccess?: boolean;
  flushOnError?: boolean;
  captureArguments?: boolean;
  captureResults?: boolean;
  captureStreamItems?: boolean;
  maxStreamItems?: number;
  adoptionMode?: AdoptionMode | string;
  bootstrapMemory?: AttachBootstrapMemoryOptions;
  openclawBootstrapPreset?: OpenClawBootstrapPreset | string;
  openclawBootstrapMaxRecords?: number;
  openclawBootstrapSourceSystem?: string;
  openclawBootstrapCreatedBy?: string;
  openclawBootstrapCursor?: string;
  openclawBootstrapChunkSize?: number;
  openclawHookEvents?: string[];
  openclawCaptureHookEvents?: boolean;
  openclawRegisterTools?: boolean;
  openclawRegisterSearchTool?: boolean;
  openclawRegisterProposeTool?: boolean;
  openclawRegisterTaskTools?: boolean;
  openclawToolPrefix?: string;
  openclawSearchKnowledge?: OpenClawSearchKnowledgeResolver;
  openclawListTasks?: OpenClawListTasksResolver;
  openclawUpdateTaskStatus?: OpenClawUpdateTaskStatusResolver;
  registerAgentDirectory?: boolean;
  agentProfile?: AgentProfileInput;
  agentDisplayName?: string;
  agentTeam?: string;
  agentRole?: string;
  agentResponsibilities?: string[];
  agentTools?: string[];
  agentDataSources?: string[];
  agentLimits?: string[];
  agentDirectoryStatus?: "active" | "idle" | "paused" | "offline" | "retired";
}

export type AttachOptions = MonitorOptions;

export interface ListWikiDraftsOptions {
  status?: WikiDraftStatus | string;
  limit?: number;
}

export interface WikiDraftBulkReviewFilter {
  statuses?: Array<WikiDraftStatus | string>;
  category?: string;
  category_mode?: WikiDraftFilterMode;
  source_system?: string;
  source_system_mode?: WikiDraftFilterMode;
  connector?: string;
  connector_mode?: WikiDraftFilterMode;
  page_type?: string;
  page_type_mode?: WikiDraftFilterMode;
  assertion_class?: string;
  assertion_class_mode?: WikiDraftFilterMode;
  tier?: string;
  tier_mode?: WikiDraftFilterMode;
  min_confidence?: number;
  max_confidence?: number;
  min_risk_level?: WikiDraftRiskLevel;
  max_risk_level?: WikiDraftRiskLevel;
  include_open_conflicts?: boolean;
  include_archived_pages?: boolean;
  include_published_pages?: boolean;
}

export interface BulkReviewWikiDraftsOptions {
  reviewedBy: string;
  action?: "approve" | "reject" | string;
  dryRun?: boolean;
  limit?: number;
  filter?: WikiDraftBulkReviewFilter;
  note?: string;
  reason?: string;
  force?: boolean;
  dismissConflicts?: boolean;
  idempotencyKey?: string;
}

export interface LangChainCallbackHandler {
  on_chain_start?: (serialized: unknown, inputs: unknown, kwargs?: Record<string, unknown>) => void;
  on_chain_end?: (outputs: unknown, kwargs?: Record<string, unknown>) => void;
  on_chain_error?: (error: unknown, kwargs?: Record<string, unknown>) => void;
  on_tool_start?: (serialized: unknown, input: unknown, kwargs?: Record<string, unknown>) => void;
  on_tool_end?: (output: unknown, kwargs?: Record<string, unknown>) => void;
  on_tool_error?: (error: unknown, kwargs?: Record<string, unknown>) => void;
  on_llm_start?: (serialized: unknown, prompts: unknown, kwargs?: Record<string, unknown>) => void;
  on_llm_end?: (response: unknown, kwargs?: Record<string, unknown>) => void;
  on_llm_error?: (error: unknown, kwargs?: Record<string, unknown>) => void;
  on_agent_action?: (action: unknown, kwargs?: Record<string, unknown>) => void;
  on_agent_finish?: (finish: unknown, kwargs?: Record<string, unknown>) => void;
  handleChainStart?: (serialized: unknown, inputs: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleChainEnd?: (outputs: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleChainError?: (error: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleToolStart?: (serialized: unknown, input: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleToolEnd?: (output: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleToolError?: (error: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleLLMStart?: (serialized: unknown, prompts: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleLLMEnd?: (response: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleLLMError?: (error: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleAgentAction?: (action: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
  handleAgentEnd?: (finish: unknown, runId?: string, parentRunId?: string, kwargs?: Record<string, unknown>) => void;
}

export interface LangChainCallbackHandlerOptions {
  integration?: "langchain" | "langgraph" | string;
  agentId?: string;
  sessionId?: string;
  flushOnSuccess?: boolean;
  flushOnError?: boolean;
  captureInputs?: boolean;
  captureOutputs?: boolean;
}

export interface BindLangChainOptions {
  handler?: LangChainCallbackHandler;
  fallbackMonitor?: boolean;
  monitorIncludeMethods?: string[];
  agentId?: string;
  sessionId?: string;
}

export interface BindLangGraphOptions {
  handler?: LangChainCallbackHandler;
  fallbackMonitor?: boolean;
  monitorIncludeMethods?: string[];
  agentId?: string;
  sessionId?: string;
}

export interface BindCrewAiOptions {
  eventNames?: string[];
  eventHandler?: (eventName: string, payload: unknown) => void;
  monitorRuntime?: boolean;
  monitorIncludeMethods?: string[];
  agentId?: string;
  sessionId?: string;
}

export type OpenClawSearchKnowledgeResolver = (
  query: string,
  limit: number,
  filters: Record<string, unknown>
) => Promise<unknown> | unknown;

export type OpenClawListTasksResolver = (options: {
  limit: number;
  assignee?: string;
  entity_key?: string;
  include_closed: boolean;
}) => Promise<Array<Record<string, unknown>>> | Array<Record<string, unknown>>;

export type OpenClawUpdateTaskStatusResolver = (
  taskId: string,
  options: {
    status: string;
    updated_by: string;
    note?: string;
  }
) => Promise<Record<string, unknown>> | Record<string, unknown>;

export interface OnboardingMetrics {
  projectId: string;
  window: {
    limit: number;
    eventsObserved: number;
  };
  attachEventsTotal: number;
  attachStarted: number;
  attachCompleted: number;
  bootstrapCompleted: number;
  frictionTotal: number;
  frictionEvents: string[];
  eventsByName: Record<string, number>;
}

export interface InsightContext {
  functionName: string;
  integration: string;
  args: unknown[];
  result: unknown;
  categoryHint?: string;
  entityHint?: string;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  sourceId: string;
}

export interface ExtractedInsight {
  claim_text: string;
  category?: string;
  entity_key?: string;
  confidence?: number;
  metadata?: Record<string, unknown>;
  valid_from?: string;
  valid_to?: string;
}

export interface InsightExtractor {
  name: string;
  extract(context: InsightContext): ExtractedInsight[] | Promise<ExtractedInsight[]>;
}

export interface SynthesisContext {
  functionName: string;
  integration: string;
  extractedInsights: ExtractedInsight[];
  args: unknown[];
  result: unknown;
  categoryHint?: string;
  entityHint?: string;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  sourceId: string;
  metadata?: Record<string, unknown>;
}

export interface InsightSynthesizer {
  name: string;
  contractVersion?: "v1" | string;
  synthesize(context: SynthesisContext): ExtractedInsight[] | Promise<ExtractedInsight[]>;
}

export interface CollectInsightOptions {
  category?: string;
  entityKey?: string;
  extractorNames?: string[];
  synthesizerNames?: string[];
  minConfidence?: number;
  integration?: string;
  sourceType?: "dialog" | "tool_output" | "file" | "human_note" | "external_event";
  agentId?: string;
  sessionId?: string;
}

export interface DebugRecord {
  ts: string;
  event: string;
  projectId: string;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  details: Record<string, unknown>;
}

export type DebugSink = (record: DebugRecord) => void;
export type TelemetrySink = (record: DebugRecord) => void;

export interface DebugOptions {
  enabled: boolean;
  sink?: DebugSink;
  maxRecords?: number;
}

export interface OTelCounterLike {
  add(value: number, attributes?: Record<string, unknown>): void;
}

export interface OTelHistogramLike {
  record(value: number, attributes?: Record<string, unknown>): void;
}

export interface OTelSpanLike {
  setAttribute?(key: string, value: unknown): void;
  addEvent?(name: string, attributes?: Record<string, unknown>): void;
  end(): void;
}

export interface OTelTracerLike {
  startSpan(name: string, options?: { attributes?: Record<string, unknown> }): OTelSpanLike;
}

export interface OTelMeterLike {
  createCounter(name: string, options?: { description?: string; unit?: string }): OTelCounterLike;
  createHistogram(name: string, options?: { description?: string; unit?: string }): OTelHistogramLike;
}

export interface RetryPolicyConfig {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  jitterRatio?: number;
  timeoutMs?: number;
  retryableStatusCodes?: number[];
}

export interface RequestOptions {
  idempotencyKey?: string;
}

export interface MemoryBackfillRecord {
  source_id: string;
  content: string;
  observed_at?: string;
  entity_key?: string;
  category?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export type BootstrapMemoryInput =
  | MemoryBackfillRecord
  | string
  | {
      source_id?: string;
      id?: string;
      key?: string;
      memory_id?: string;
      content?: string;
      text?: string;
      fact?: string;
      message?: string;
      summary?: string;
      observed_at?: string;
      timestamp?: string;
      entity_key?: string;
      entity?: string;
      category?: string;
      metadata?: Record<string, unknown>;
      tags?: string[];
    };

export type OpenClawBootstrapPreset = "runtime_memory" | "event_log" | "hybrid";

export interface AttachBootstrapMemoryOptions {
  records?: BootstrapMemoryInput[];
  provider?: (target: unknown) => BootstrapMemoryInput[] | null | undefined;
  sourceSystem?: string;
  createdBy?: string;
  cursor?: string;
  chunkSize?: number;
  maxRecords?: number;
}

export interface MemoryBackfillOptions {
  batchId?: string;
  ingestLane?: "event" | "knowledge";
  sourceSystem?: string;
  agentId?: string;
  sessionId?: string;
  createdBy?: string;
  cursor?: string;
  chunkSize?: number;
  curatedEnabled?: boolean;
  curatedSourceSystems?: string[];
  curatedNamespaces?: string[];
  noisePreset?: "off" | "balanced" | "strict" | "order_snapshots" | "telemetry" | "raw_event_payloads" | string;
  curatedDropEventLike?: boolean;
}

export type TaskStatus = "todo" | "in_progress" | "blocked" | "done" | "canceled";
export type TaskPriority = "low" | "normal" | "high" | "critical";
export type TaskSource = "agent" | "human" | "system";

export interface TaskInput {
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  source?: TaskSource;
  assignee?: string;
  entityKey?: string;
  category?: string;
  dueAt?: string;
  metadata?: Record<string, unknown>;
}

export interface TaskCommentInput {
  comment: string;
  metadata?: Record<string, unknown>;
}

export interface TaskLinkInput {
  linkType: "claim" | "draft" | "page" | "event" | "external";
  linkRef: string;
  note?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentProfileInput {
  agentId: string;
  displayName?: string;
  team?: string;
  role?: string;
  status?: "active" | "idle" | "paused" | "offline" | "retired";
  responsibilities?: string[];
  tools?: string[];
  dataSources?: string[];
  limits?: string[];
  metadata?: Record<string, unknown>;
  ensureScaffold?: boolean;
  includeDailyReportStub?: boolean;
  lastSeenAt?: string;
}

export type WikiSpacePolicyMode = "open" | "owners_only";
export type WikiPublishChecklistPreset = "none" | "ops_standard" | "policy_strict";

export interface WikiSpacePolicyRecord {
  write_mode: WikiSpacePolicyMode;
  comment_mode: WikiSpacePolicyMode;
  review_assignment_required: boolean;
  metadata: Record<string, unknown>;
  exists?: boolean;
  updated_by?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WikiSpacePolicyResponse {
  project_id: string;
  space_key: string;
  status?: "updated" | "no_change";
  policy: WikiSpacePolicyRecord;
  audit?: {
    changed_fields?: string[];
  };
}

export interface WikiSpacePolicyAuditEntry {
  id: string;
  changed_by: string;
  before_policy: Record<string, unknown>;
  after_policy: Record<string, unknown>;
  changed_fields: string[];
  reason?: string | null;
  created_at?: string | null;
}

export interface WikiSpacePolicyAuditResponse {
  project_id: string;
  space_key: string;
  entries: WikiSpacePolicyAuditEntry[];
  available: boolean;
}

export interface SynapseTransport {
  sendEvents(events: ObservationEvent[], options?: RequestOptions): Promise<void>;
  proposeFact(claim: Claim, options?: RequestOptions): Promise<void>;
  ingestMemoryBackfill(payload: Record<string, unknown>, options?: RequestOptions): Promise<void>;
  ingestKnowledgeBackfill?(payload: Record<string, unknown>, options?: RequestOptions): Promise<void>;
}
