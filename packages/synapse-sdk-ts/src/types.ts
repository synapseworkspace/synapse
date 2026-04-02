export type SchemaVersion = "v1";
export type DegradationMode = "buffer" | "drop" | "sync_flush";

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
  integration?: "generic" | "langgraph" | "crewai" | "openclaw" | string;
  includeMethods?: string[];
  agentId?: string;
  sessionId?: string;
  flushOnSuccess?: boolean;
  flushOnError?: boolean;
  captureArguments?: boolean;
  captureResults?: boolean;
  captureStreamItems?: boolean;
  maxStreamItems?: number;
  bootstrapMemory?: AttachBootstrapMemoryOptions;
  openclawBootstrapPreset?: OpenClawBootstrapPreset | string;
  openclawBootstrapMaxRecords?: number;
  openclawBootstrapSourceSystem?: string;
  openclawBootstrapCreatedBy?: string;
  openclawBootstrapCursor?: string;
  openclawBootstrapChunkSize?: number;
}

export type AttachOptions = MonitorOptions;

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
  sourceSystem?: string;
  agentId?: string;
  sessionId?: string;
  createdBy?: string;
  cursor?: string;
  chunkSize?: number;
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

export interface SynapseTransport {
  sendEvents(events: ObservationEvent[], options?: RequestOptions): Promise<void>;
  proposeFact(claim: Claim, options?: RequestOptions): Promise<void>;
  ingestMemoryBackfill(payload: Record<string, unknown>, options?: RequestOptions): Promise<void>;
}
