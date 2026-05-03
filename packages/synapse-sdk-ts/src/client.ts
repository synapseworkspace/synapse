import { AsyncLocalStorage } from "node:async_hooks";
import { HttpTransport } from "./transports/http.js";
import { buildOpenClawBootstrapOptions } from "./openclaw.js";
import type {
  AgentReflectionInput,
  AgentRuntimeSurfaceAgentInput,
  AttachBootstrapMemoryOptions,
  AgentProfileInput,
  AttachOptions,
  AdoptionProjectResetOptions,
  AdoptionSyncPresetExecuteOptions,
  BindCrewAiOptions,
  BindLangChainOptions,
  BindLangGraphOptions,
  BootstrapMemoryInput,
  Claim,
  EvidenceRef,
  CollectInsightOptions,
  DebugOptions,
  DebugRecord,
  DebugSink,
  AdoptionMode,
  ExtractedInsight,
  InsightContext,
  InsightExtractor,
  InsightSynthesizer,
  ListWikiDraftsOptions,
  MemoryBackfillOptions,
  MemoryBackfillRecord,
  MonitorOptions,
  ObservationEvent,
  LangChainCallbackHandler,
  LangChainCallbackHandlerOptions,
  SynthesisContext,
  SynapseConfig,
  SynapseTransport,
  RequestOptions,
  DegradationMode,
  OpenClawBootstrapPreset,
  OpenClawListTasksResolver,
  OpenClawSearchKnowledgeResolver,
  OpenClawUpdateTaskStatusResolver,
  OnboardingMetrics,
  TaskCommentInput,
  TaskInput,
  TaskLinkInput,
  TaskStatus,
  BulkReviewWikiDraftsOptions,
  WikiPublishChecklistPreset,
  WikiSpacePolicyAuditResponse,
  WikiSpacePolicyMode,
  WikiSpacePolicyResponse,
  TelemetrySink
} from "./types.js";

const DEFAULT_METHODS: Record<string, string[]> = {
  generic: ["invoke", "run", "execute", "stream"],
  langgraph: ["invoke", "ainvoke", "stream", "astream", "batch", "abatch"],
  langchain: ["invoke", "ainvoke", "stream", "astream", "batch", "abatch", "call", "acall"],
  crewai: ["kickoff", "kickoff_async", "run", "execute", "execute_async"],
  openclaw: ["run", "runTask", "executeAction", "invokeTool", "dispatch"]
};

const DEFAULT_OPENCLAW_EVENTS = ["tool:result", "message:received", "agent:completed", "session:reset"] as const;
const DEFAULT_CREWAI_NATIVE_EVENTS = [
  "crew_started",
  "crew_completed",
  "crew_failed",
  "task_started",
  "task_completed",
  "task_failed",
  "agent_step"
] as const;

type TraceContext = {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
};

class StructuredResultExtractor implements InsightExtractor {
  name = "structured_result";

  extract(context: InsightContext): ExtractedInsight[] {
    if (!isPlainObject(context.result)) {
      return [];
    }
    const claimTextRaw = context.result.claim_text ?? context.result.fact;
    if (typeof claimTextRaw !== "string" || !claimTextRaw.trim()) {
      return [];
    }
    const confidenceRaw = context.result.confidence;
    const confidence = typeof confidenceRaw === "number" ? clamp(confidenceRaw, 0, 1) : undefined;
    return [
      {
        claim_text: claimTextRaw.trim(),
        category: asOptionalString(context.result.category) ?? context.categoryHint,
        entity_key: asOptionalString(context.result.entity_key) ?? context.entityHint,
        confidence,
        valid_from: asOptionalString(context.result.valid_from),
        valid_to: asOptionalString(context.result.valid_to),
        metadata: isPlainObject(context.result.metadata) ? context.result.metadata : {}
      }
    ];
  }
}

class KeywordInsightExtractor implements InsightExtractor {
  name = "keyword";
  private readonly keywords = ["closed", "open", "required", "forbidden", "only", "policy", "quarantine", "gate", "card", "access"];

  extract(context: InsightContext): ExtractedInsight[] {
    const text = coerceResultText(context.result);
    if (!text) {
      return [];
    }
    const normalized = text.toLowerCase();
    const matched = this.keywords.filter((keyword) => normalized.includes(keyword));
    if (!matched.length) {
      return [];
    }
    return [
      {
        claim_text: text,
        category: context.categoryHint,
        entity_key: context.entityHint,
        confidence: 0.7,
        metadata: { extractor: this.name, keywords: matched.slice(0, 5) }
      }
    ];
  }
}

class ConfidenceClampSynthesizer implements InsightSynthesizer {
  name = "confidence_clamp";
  contractVersion = "v1";

  synthesize(context: SynthesisContext): ExtractedInsight[] {
    return context.extractedInsights.map((item) => ({
      ...item,
      confidence: item.confidence == null ? item.confidence : clamp(item.confidence, 0, 1),
      metadata: {
        ...(item.metadata ?? {}),
        synthesizer: (item.metadata as Record<string, unknown> | undefined)?.synthesizer ?? this.name
      }
    }));
  }
}

function makeId(): string {
  return makeUuid();
}

export class SynapseClient {
  private readonly queue: ObservationEvent[] = [];
  private readonly transport: SynapseTransport;
  private degradationMode: DegradationMode;
  private readonly traceStorage: AsyncLocalStorage<TraceContext> = new AsyncLocalStorage<TraceContext>();
  private readonly extractors: Map<string, InsightExtractor> = new Map();
  private readonly synthesizers: Map<string, InsightSynthesizer> = new Map();
  private readonly pendingClaims: Claim[] = [];
  private readonly pendingBackfill: Array<{ payload: Record<string, unknown>; idempotencyKey?: string }> = [];
  private debugMode = false;
  private readonly debugRecords: DebugRecord[] = [];
  private debugSink?: DebugSink;
  private telemetrySink?: TelemetrySink;
  private debugMaxRecords = 1000;
  private flushPromise: Promise<void> | null = null;

  constructor(private readonly config: SynapseConfig, transport?: SynapseTransport) {
    this.transport = transport ?? new HttpTransport(config.apiUrl, config.apiKey, config.retry);
    this.degradationMode = normalizeDegradationMode(config.degradationMode);
    for (const extractor of [new StructuredResultExtractor(), new KeywordInsightExtractor()]) {
      this.extractors.set(extractor.name, extractor);
    }
    for (const synthesizer of [new ConfidenceClampSynthesizer()]) {
      this.synthesizers.set(synthesizer.name, synthesizer);
    }
  }

  get projectId(): string {
    return this.config.projectId;
  }

  getDegradationMode(): DegradationMode {
    return this.degradationMode;
  }

  setDegradationMode(mode: DegradationMode): void {
    this.degradationMode = normalizeDegradationMode(mode);
  }

  setDebugMode(options: boolean | DebugOptions): void {
    if (typeof options === "boolean") {
      this.debugMode = options;
      return;
    }
    this.debugMode = options.enabled;
    if (options.sink) {
      this.debugSink = options.sink;
    }
    if (typeof options.maxRecords === "number") {
      this.debugMaxRecords = Math.max(10, Math.trunc(options.maxRecords));
    }
  }

  getDebugRecords(limit?: number): DebugRecord[] {
    if (!limit || limit <= 0) {
      return this.debugRecords.slice();
    }
    return this.debugRecords.slice(-limit);
  }

  clearDebugRecords(): void {
    this.debugRecords.splice(0, this.debugRecords.length);
  }

  getOnboardingMetrics(limit = 500): OnboardingMetrics {
    const safeLimit = Math.max(1, Math.trunc(limit));
    const records = this.getDebugRecords(safeLimit);
    const eventsByName: Record<string, number> = {};
    const frictionNames = new Set([
      "attach_bootstrap_failed",
      "attach_bootstrap_provider_failed",
      "attach_bootstrap_skipped",
      "attach_openclaw_bootstrap_preset_failed",
      "attach_openclaw_bootstrap_preset_skipped",
      "attach_openclaw_search_disabled"
    ]);
    const frictionEvents: string[] = [];
    let attachEventsTotal = 0;

    for (const record of records) {
      const eventName = String(record.event || "");
      if (!eventName.startsWith("attach_")) {
        continue;
      }
      attachEventsTotal += 1;
      eventsByName[eventName] = (eventsByName[eventName] ?? 0) + 1;
      if (frictionNames.has(eventName)) {
        frictionEvents.push(eventName);
      }
    }

    return {
      projectId: this.config.projectId,
      window: {
        limit: safeLimit,
        eventsObserved: records.length
      },
      attachEventsTotal,
      attachStarted: eventsByName["attach_started"] ?? 0,
      attachCompleted: eventsByName["attach_completed"] ?? 0,
      bootstrapCompleted: eventsByName["attach_bootstrap_completed"] ?? 0,
      frictionTotal: frictionEvents.length,
      frictionEvents,
      eventsByName
    };
  }

  setTelemetrySink(sink?: TelemetrySink): void {
    this.telemetrySink = sink;
  }

  getTelemetrySink(): TelemetrySink | undefined {
    return this.telemetrySink;
  }

  async searchKnowledge(
    query: string,
    options: {
      limit?: number;
      relatedEntityKey?: string;
      contextPolicyMode?: "off" | "advisory" | "enforced";
      minRetrievalConfidence?: number;
      minTotalScore?: number;
      minLexicalScore?: number;
      minTokenOverlapRatio?: number;
    } = {}
  ): Promise<Record<string, unknown>[]> {
    const normalizedQuery = String(query ?? "").trim();
    if (!normalizedQuery) {
      return [];
    }
    const params: Record<string, string | number | boolean | null | undefined> = {
      project_id: this.config.projectId,
      q: normalizedQuery,
      limit: normalizeInt(options.limit ?? 5, 1, 100)
    };
    if (options.relatedEntityKey) {
      params.related_entity_key = options.relatedEntityKey;
    }
    if (options.contextPolicyMode) {
      params.context_policy_mode = options.contextPolicyMode;
    }
    if (typeof options.minRetrievalConfidence === "number") {
      params.min_retrieval_confidence = options.minRetrievalConfidence;
    }
    if (typeof options.minTotalScore === "number") {
      params.min_total_score = options.minTotalScore;
    }
    if (typeof options.minLexicalScore === "number") {
      params.min_lexical_score = options.minLexicalScore;
    }
    if (typeof options.minTokenOverlapRatio === "number") {
      params.min_token_overlap_ratio = options.minTokenOverlapRatio;
    }

    const payload = await this.requestJson("/v1/mcp/retrieval/explain", {
      method: "GET",
      params
    });
    const rows = Array.isArray(payload.results)
      ? payload.results
      : Array.isArray(payload.ranked)
        ? payload.ranked
        : [];
    return rows.filter((item): item is Record<string, unknown> => isPlainObject(item));
  }

  capture(
    event: Omit<ObservationEvent, "id" | "schema_version" | "project_id" | "observed_at"> & {
      id?: string;
      observed_at?: string;
    }
  ): void {
    const traceContext = this.currentTraceContext();
    const traceId = event.trace_id ?? traceContext?.traceId;
    const spanId = event.span_id ?? traceContext?.spanId;
    const parentSpanId = event.parent_span_id ?? traceContext?.parentSpanId;
    const payloadWithTrace = this.payloadWithTrace(event.payload, {
      traceId,
      spanId,
      parentSpanId
    });
    this.queue.push({
      ...event,
      id: event.id ?? makeId(),
      schema_version: "v1",
      project_id: this.config.projectId,
      payload: payloadWithTrace,
      trace_id: traceId,
      span_id: spanId,
      parent_span_id: parentSpanId,
      observed_at: event.observed_at ?? new Date().toISOString()
    });
    this.emitDebug("capture_queued", {
      event_type: event.event_type,
      queue_size: this.queue.length,
      agent_id: event.agent_id,
      session_id: event.session_id
    }, { traceId, spanId, parentSpanId });
    if (this.degradationMode === "sync_flush") {
      void this.flush().catch(() => undefined);
    }
  }

  async proposeFact(claim: Omit<Claim, "schema_version" | "project_id">): Promise<void> {
    const prepared: Claim = {
      ...claim,
      schema_version: "v1",
      project_id: this.config.projectId
    };
    const traceContext = {
      traceId: asOptionalString(prepared.metadata?.trace_id),
      spanId: asOptionalString(prepared.metadata?.span_id),
      parentSpanId: asOptionalString(prepared.metadata?.parent_span_id)
    };
    this.emitDebug("propose_fact_attempt", {
      claim_id: prepared.id,
      entity_key: prepared.entity_key,
      category: prepared.category,
      confidence: prepared.confidence ?? null
    }, traceContext);
    try {
      await this.transport.proposeFact(prepared, { idempotencyKey: makeClaimIdempotencyKey(prepared.id) });
      this.emitDebug("propose_fact_sent", { claim_id: prepared.id }, traceContext);
    } catch (error) {
      const errorType = error instanceof Error ? error.name : "Error";
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (this.degradationMode === "drop") {
        this.emitDebug("propose_fact_dropped", {
          claim_id: prepared.id,
          error_type: errorType,
          error_message: errorMessage
        }, traceContext);
        return;
      }
      this.pendingClaims.push(prepared);
      this.emitDebug("propose_fact_buffered", {
        claim_id: prepared.id,
        pending_claims: this.pendingClaims.length,
        error_type: errorType,
        error_message: errorMessage
      }, traceContext);
    }
  }

  async flush(): Promise<void> {
    if (this.flushPromise) {
      return this.flushPromise;
    }
    this.flushPromise = this.flushInternal().finally(() => {
      this.flushPromise = null;
    });
    return this.flushPromise;
  }

  async backfillMemory(records: MemoryBackfillRecord[], options: MemoryBackfillOptions = {}): Promise<string> {
    const chunkSize = options.chunkSize ?? 100;
    const ingestLane = options.ingestLane ?? "knowledge";
    if (ingestLane !== "event" && ingestLane !== "knowledge") {
      throw new Error("ingestLane must be either 'event' or 'knowledge'");
    }
    if (chunkSize <= 0) {
      throw new Error("chunkSize must be greater than 0");
    }
    const batchId = options.batchId ?? makeUuid();
    if (!records.length) {
      return batchId;
    }

    for (let start = 0; start < records.length; start += chunkSize) {
      const chunk = records.slice(start, start + chunkSize);
      const isLast = start + chunk.length >= records.length;
      const payload = {
        batch: {
          batch_id: batchId,
          project_id: this.config.projectId,
          source_system: options.sourceSystem ?? "sdk_bootstrap",
          ingest_lane: ingestLane,
          agent_id: options.agentId,
          session_id: options.sessionId,
          cursor: isLast ? options.cursor : undefined,
          finalize: isLast,
          created_by: options.createdBy,
          records: chunk.map((record) => ({
            source_id: record.source_id,
            content: record.content,
            observed_at: record.observed_at,
            entity_key: record.entity_key,
            category: record.category,
            metadata: record.metadata ?? {},
            tags: record.tags ?? []
          })),
          curated:
            options.curatedEnabled !== undefined ||
            options.curatedSourceSystems !== undefined ||
            options.curatedNamespaces !== undefined ||
            options.noisePreset !== undefined ||
            options.curatedDropEventLike !== undefined
              ? {
                  enabled: options.curatedEnabled,
                  source_systems: options.curatedSourceSystems,
                  namespaces: options.curatedNamespaces,
                  noise_preset:
                    options.noisePreset !== undefined && String(options.noisePreset).trim()
                      ? String(options.noisePreset).trim().toLowerCase()
                      : undefined,
                  drop_event_like: options.curatedDropEventLike
                }
              : undefined
        }
      };
      const idempotencyKey = makeBackfillIdempotencyKey(batchId, start, chunk.length, isLast);
      try {
        await this.transportIngestBackfill(payload, ingestLane, { idempotencyKey });
        this.emitDebug("backfill_chunk_sent", {
          batch_id: batchId,
          ingest_lane: ingestLane,
          start,
          size: chunk.length,
          finalized: isLast
        });
      } catch (error) {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (this.degradationMode === "drop") {
          this.emitDebug("backfill_chunk_dropped", {
            batch_id: batchId,
            ingest_lane: ingestLane,
            start,
            size: chunk.length,
            finalized: isLast,
            error_type: errorType,
            error_message: errorMessage
          });
          continue;
        }
        this.pendingBackfill.push({ payload, idempotencyKey });
        this.emitDebug("backfill_chunk_buffered", {
          batch_id: batchId,
          ingest_lane: ingestLane,
          start,
          size: chunk.length,
          finalized: isLast,
          pending_backfill: this.pendingBackfill.length,
          error_type: errorType,
          error_message: errorMessage
        });
      }
    }

    return batchId;
  }

  async backfillKnowledge(records: MemoryBackfillRecord[], options: Omit<MemoryBackfillOptions, "ingestLane"> = {}): Promise<string> {
    return this.backfillMemory(records, { ...options, ingestLane: "knowledge" });
  }

  async explainCuratedBackfill(
    records: MemoryBackfillRecord[],
    options: Omit<MemoryBackfillOptions, "batchId" | "chunkSize" | "cursor"> & {
      sampleLimit?: number;
    } = {}
  ): Promise<Record<string, unknown>> {
    const ingestLane = options.ingestLane ?? "knowledge";
    if (ingestLane !== "event" && ingestLane !== "knowledge") {
      throw new Error("ingestLane must be either 'event' or 'knowledge'");
    }
    if (!records.length) {
      throw new Error("records must not be empty");
    }
    return this.requestJson<Record<string, unknown>>("/v1/backfill/curated-explain", {
      method: "POST",
      params: {
        sample_limit: normalizeInt(options.sampleLimit ?? 12, 1, 100)
      },
      payload: {
        batch: {
          project_id: this.projectId,
          source_system: options.sourceSystem ?? "sdk_bootstrap",
          ingest_lane: ingestLane,
          agent_id: options.agentId,
          session_id: options.sessionId,
          finalize: true,
          created_by: options.createdBy,
          records: records.map((record) => ({
            source_id: record.source_id,
            content: record.content,
            observed_at: record.observed_at,
            entity_key: record.entity_key,
            category: record.category,
            metadata: record.metadata ?? {},
            tags: record.tags ?? []
          })),
          curated:
            options.curatedEnabled !== undefined ||
            options.curatedSourceSystems !== undefined ||
            options.curatedNamespaces !== undefined ||
            options.noisePreset !== undefined ||
            options.curatedDropEventLike !== undefined
              ? {
                  enabled: options.curatedEnabled,
                  source_systems: options.curatedSourceSystems,
                  namespaces: options.curatedNamespaces,
                  noise_preset:
                    options.noisePreset !== undefined && String(options.noisePreset).trim()
                      ? String(options.noisePreset).trim().toLowerCase()
                      : undefined,
                  drop_event_like: options.curatedDropEventLike
                }
              : undefined
        }
      }
    });
  }

  async listAdoptionImportConnectors(options: {
    sourceType?: "postgres_sql" | string;
    profile?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/import-connectors", {
      method: "GET",
      params: {
        source_type: String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql",
        profile: asOptionalString(options.profile) ?? undefined
      }
    });
  }

  async resolveAdoptionImportConnector(options: {
    connectorId: string;
    sourceType?: "postgres_sql" | string;
    fieldOverrides?: Record<string, unknown>;
  }): Promise<Record<string, unknown>> {
    const connectorId = String(options.connectorId ?? "").trim();
    if (!connectorId) {
      throw new Error("connectorId is required");
    }
    return this.requestJson<Record<string, unknown>>("/v1/adoption/import-connectors/resolve", {
      method: "POST",
      payload: {
        source_type: String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql",
        connector_id: connectorId,
        project_id: this.projectId,
        field_overrides: options.fieldOverrides ?? {}
      }
    });
  }

  async validateAdoptionImportConnector(options: {
    connectorId: string;
    sourceType?: "postgres_sql" | "memory_api" | string;
    sourceRef?: string;
    fieldOverrides?: Record<string, unknown>;
    liveConnect?: boolean;
  }): Promise<Record<string, unknown>> {
    const connectorId = String(options.connectorId ?? "").trim();
    if (!connectorId) {
      throw new Error("connectorId is required");
    }
    const sourceType = String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql";
    if (!["postgres_sql", "memory_api"].includes(sourceType)) {
      throw new Error("sourceType must be one of: postgres_sql, memory_api");
    }
    return this.requestJson<Record<string, unknown>>("/v1/adoption/import-connectors/validate", {
      method: "POST",
      payload: {
        source_type: sourceType,
        connector_id: connectorId,
        project_id: this.projectId,
        source_ref: asOptionalString(options.sourceRef) ?? undefined,
        field_overrides: options.fieldOverrides ?? {},
        live_connect: options.liveConnect ?? true
      }
    });
  }

  async bootstrapAdoptionImportConnector(options: {
    updatedBy: string;
    connectorId: string;
    sourceType?: "postgres_sql" | "memory_api" | string;
    sourceRef?: string;
    fieldOverrides?: Record<string, unknown>;
    enabled?: boolean;
    syncIntervalMinutes?: number;
    queueSync?: boolean;
    dryRun?: boolean;
    syncProcessorLookbackMinutes?: number;
    failOnSyncProcessorUnavailable?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const connectorId = String(options.connectorId ?? "").trim();
    if (!connectorId) {
      throw new Error("connectorId is required");
    }
    const sourceType = String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql";
    if (!["postgres_sql", "memory_api"].includes(sourceType)) {
      throw new Error("sourceType must be one of: postgres_sql, memory_api");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/import-connectors/bootstrap", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        source_type: sourceType,
        connector_id: connectorId,
        source_ref: asOptionalString(options.sourceRef) ?? undefined,
        field_overrides: options.fieldOverrides ?? {},
        enabled: options.enabled ?? true,
        sync_interval_minutes: normalizeInt(options.syncIntervalMinutes ?? 60, 1, 10080),
        queue_sync: options.queueSync ?? true,
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId,
        sync_processor_lookback_minutes: normalizeInt(options.syncProcessorLookbackMinutes ?? 30, 1, 1440),
        fail_on_sync_processor_unavailable: options.failOnSyncProcessorUnavailable ?? false
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAdoptionNoisePresets(options: {
    lane?: "event" | "knowledge";
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/noise-presets", {
      method: "GET",
      params: {
        lane: options.lane
      }
    });
  }

  async getAdoptionKpi(options: {
    days?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/kpi", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 30, 1, 180)
      }
    });
  }

  async getAdoptionKnowledgeGaps(options: {
    days?: number;
    maxItemsPerBucket?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/knowledge-gaps", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        max_items_per_bucket: normalizeInt(options.maxItemsPerBucket ?? 8, 1, 50)
      }
    });
  }

  async syncAdoptionKnowledgeGapTasks(options: {
    createdBy: string;
    updatedBy?: string;
    assignee?: string;
    dryRun?: boolean;
    confirmProjectId?: string;
    days?: number;
    limitPerKind?: number;
    includeCandidateBundles?: boolean;
    includePageEnrichmentGaps?: boolean;
    includeUnresolvedQuestions?: boolean;
    includeRepeatedEscalations?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const createdBy = String(options.createdBy ?? "").trim();
    if (!createdBy) {
      throw new Error("createdBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/knowledge-gaps/tasks/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        created_by: createdBy,
        updated_by: asOptionalString(options.updatedBy) ?? undefined,
        assignee: asOptionalString(options.assignee) ?? undefined,
        dry_run: dryRun,
        confirm_project_id: dryRun ? (asOptionalString(options.confirmProjectId) ?? undefined) : (asOptionalString(options.confirmProjectId) ?? this.projectId),
        days: normalizeInt(options.days ?? 14, 1, 90),
        limit_per_kind: normalizeInt(options.limitPerKind ?? 6, 1, 25),
        include_candidate_bundles: options.includeCandidateBundles ?? true,
        include_page_enrichment_gaps: options.includePageEnrichmentGaps ?? true,
        include_unresolved_questions: options.includeUnresolvedQuestions ?? true,
        include_repeated_escalations: options.includeRepeatedEscalations ?? true
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAdoptionSignalNoiseAudit(options: {
    days?: number;
    maxItemsPerBucket?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/signal-noise/audit", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        max_items_per_bucket: normalizeInt(options.maxItemsPerBucket ?? 8, 1, 50)
      }
    });
  }

  async listAdoptionEvidenceLedger(options: {
    sourceShape?: string;
    volatilityClass?: string;
    piiLevel?: string;
    evidenceRole?: string;
    ingestionClassification?: string;
    knowledgeTaxonomyClass?: string;
    normalizedTargetType?: string;
    bundleStatus?: string;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/evidence-ledger", {
      method: "GET",
      params: {
        project_id: this.projectId,
        source_shape: asOptionalString(options.sourceShape)?.toLowerCase(),
        volatility_class: asOptionalString(options.volatilityClass)?.toLowerCase(),
        pii_level: asOptionalString(options.piiLevel)?.toLowerCase(),
        evidence_role: asOptionalString(options.evidenceRole)?.toLowerCase(),
        ingestion_classification: asOptionalString(options.ingestionClassification)?.toLowerCase(),
        knowledge_taxonomy_class: asOptionalString(options.knowledgeTaxonomyClass)?.toLowerCase(),
        normalized_target_type: asOptionalString(options.normalizedTargetType)?.toLowerCase(),
        bundle_status: asOptionalString(options.bundleStatus)?.toLowerCase(),
        limit: normalizeInt(options.limit ?? 50, 1, 200)
      }
    });
  }

  async getAdoptionEvidenceLedgerStats(options: {
    days?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/evidence-ledger/stats", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 30, 1, 365)
      }
    });
  }

  async getAdoptionStabilityMonitor(options: {
    days?: number;
    maxItemsPerBucket?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/stability-monitor", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        max_items_per_bucket: normalizeInt(options.maxItemsPerBucket ?? 8, 1, 50)
      }
    });
  }

  async getAdoptionSynthesisPrompts(options: {
    days?: number;
    maxItems?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/synthesis-prompts", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        max_items: normalizeInt(options.maxItems ?? 8, 1, 50)
      }
    });
  }

  async runAdoptionBundlePromotion(options: {
    updatedBy: string;
    dryRun?: boolean;
    confirmProjectId?: string;
    publish?: boolean;
    bootstrapPublishCore?: boolean;
    spaceKey?: string;
    includeDataSourcesCatalog?: boolean;
    includeAgentCapabilityProfile?: boolean;
    includeProcessPlaybooks?: boolean;
    includeDecisionsLog?: boolean;
    includeCompanyOperatingContext?: boolean;
    includeOperationalLogicMap?: boolean;
    maxSources?: number;
    maxAgents?: number;
    maxSignals?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/bundle-promotion/run", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        dry_run: dryRun,
        confirm_project_id: dryRun ? (asOptionalString(options.confirmProjectId) ?? undefined) : (asOptionalString(options.confirmProjectId) ?? this.projectId),
        publish: options.publish ?? true,
        bootstrap_publish_core: options.bootstrapPublishCore ?? true,
        space_key: normalizeWikiSpaceKey(options.spaceKey ?? "operations"),
        include_data_sources_catalog: options.includeDataSourcesCatalog ?? true,
        include_agent_capability_profile: options.includeAgentCapabilityProfile ?? true,
        include_process_playbooks: options.includeProcessPlaybooks ?? true,
        include_decisions_log: options.includeDecisionsLog ?? true,
        include_company_operating_context: options.includeCompanyOperatingContext ?? true,
        include_operational_logic_map: options.includeOperationalLogicMap ?? true,
        max_sources: normalizeInt(options.maxSources ?? 20, 1, 200),
        max_agents: normalizeInt(options.maxAgents ?? 12, 1, 100),
        max_signals: normalizeInt(options.maxSignals ?? 50, 1, 500)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAdoptionPolicyCalibrationQuickLoop(options: {
    days?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/policy-calibration/quick-loop", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90)
      }
    });
  }

  async applyAdoptionPolicyCalibrationQuickLoop(options: {
    updatedBy: string;
    presetKey?: string;
    dryRun?: boolean;
    note?: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/policy-calibration/quick-loop/apply", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        preset_key: asOptionalString(options.presetKey) ?? undefined,
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId,
        note: asOptionalString(options.note) ?? undefined
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getSelfhostConsistencyGate(options: {
    webBuild?: string;
    uiProfile?: string;
    routePath?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/selfhost/consistency", {
      method: "GET",
      params: {
        web_build: asOptionalString(options.webBuild) ?? undefined,
        ui_profile: asOptionalString(options.uiProfile) ?? undefined,
        route_path: asOptionalString(options.routePath) ?? undefined
      }
    });
  }

  async getEnterpriseReadiness(options: {
    projectId?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/enterprise/readiness", {
      method: "GET",
      params: {
        project_id: asOptionalString(options.projectId) ?? undefined
      }
    });
  }

  async listAdoptionBusinessProfiles(): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/business-profiles", {
      method: "GET"
    });
  }

  async runAdoptionFirstRunBootstrap(options: {
    createdBy: string;
    profile?: "standard" | "support_ops" | "logistics_ops" | "sales_ops" | "compliance_ops" | "ai_employee_org" | string;
    businessProfileKey?: string;
    spaceKey?: string;
    dryRun?: boolean;
    publish?: boolean;
    includeStateSnapshot?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const createdBy = String(options.createdBy ?? "").trim();
    if (!createdBy) {
      throw new Error("createdBy is required");
    }
    const profileRaw = String(options.profile ?? "standard").trim().toLowerCase() || "standard";
    if (!["standard", "support_ops", "logistics_ops", "sales_ops", "compliance_ops", "ai_employee_org"].includes(profileRaw)) {
      throw new Error("profile must be one of: standard, support_ops, logistics_ops, sales_ops, compliance_ops, ai_employee_org");
    }
    const dryRun = options.dryRun ?? false;
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      created_by: createdBy,
      profile: profileRaw,
      business_profile_key: asOptionalString(options.businessProfileKey) ?? undefined,
      dry_run: dryRun,
      confirm_project_id: dryRun ? undefined : this.projectId,
      publish: options.publish ?? true,
      include_state_snapshot: options.includeStateSnapshot ?? true
    };
    if (asOptionalString(options.spaceKey) !== null) {
      payload.space_key = String(options.spaceKey).trim();
    }
    return this.requestJson<Record<string, unknown>>("/v1/adoption/first-run/bootstrap", {
      method: "POST",
      payload,
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAdoptionWikiSpaceTemplates(): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/wiki-space-templates", {
      method: "GET"
    });
  }

  async applyAdoptionWikiSpaceTemplate(options: {
    updatedBy: string;
    templateKey: "support_ops" | "logistics_ops" | "sales_ops" | "compliance_ops" | string;
    spaceKey?: string;
    publish?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const templateKey = String(options.templateKey ?? "").trim().toLowerCase();
    if (!["support_ops", "logistics_ops", "sales_ops", "compliance_ops"].includes(templateKey)) {
      throw new Error("templateKey must be one of: support_ops, logistics_ops, sales_ops, compliance_ops");
    }
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      updated_by: updatedBy,
      template_key: templateKey,
      publish: options.publish ?? true
    };
    if (asOptionalString(options.spaceKey) !== null) {
      payload.space_key = String(options.spaceKey).trim();
    }
    return this.requestJson<Record<string, unknown>>("/v1/adoption/wiki-space-templates/apply", {
      method: "POST",
      payload,
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async executeAdoptionSyncPreset(options: AdoptionSyncPresetExecuteOptions): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    const starterProfile = String(options.starterProfile ?? "support_ops").trim().toLowerCase() || "support_ops";
    if (!["standard", "support_ops", "logistics_ops", "sales_ops", "compliance_ops", "ai_employee_org"].includes(starterProfile)) {
      throw new Error("starterProfile is invalid");
    }
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      updated_by: updatedBy,
      reviewed_by: asOptionalString(options.reviewedBy) ?? undefined,
      preset_key: "enterprise_curated_safe",
      business_profile_key: asOptionalString(options.businessProfileKey) ?? undefined,
      dry_run: dryRun,
      confirm_project_id: dryRun ? undefined : this.projectId,
      apply_bootstrap_profile: options.applyBootstrapProfile ?? true,
      queue_enabled_sources: options.queueEnabledSources ?? true,
      run_bootstrap_approve: options.runBootstrapApprove ?? true,
      include_starter_pages: options.includeStarterPages ?? true,
      starter_profile: starterProfile,
      include_role_template: options.includeRoleTemplate ?? false,
      role_template_key: asOptionalString(options.roleTemplateKey)?.toLowerCase() ?? undefined,
      role_template_space_key: asOptionalString(options.roleTemplateSpaceKey) ?? undefined,
      run_bundle_promotion: options.runBundlePromotion ?? true,
      bundle_promotion_space_key: normalizeWikiSpaceKey(options.bundlePromotionSpaceKey ?? "operations"),
      bundle_promotion_publish: options.bundlePromotionPublish ?? true,
      bundle_promotion_bootstrap_publish_core: options.bundlePromotionBootstrapPublishCore ?? true,
      sync_processor_lookback_minutes: normalizeInt(options.syncProcessorLookbackMinutes ?? 30, 1, 1440),
      fail_on_sync_processor_unavailable: options.failOnSyncProcessorUnavailable ?? false,
      auto_apply_safe_mode_on_critical: options.autoApplySafeModeOnCritical ?? true
    };
    return this.requestJson<Record<string, unknown>>("/v1/adoption/sync-presets/execute", {
      method: "POST",
      payload,
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async runAdoptionProjectReset(options: AdoptionProjectResetOptions): Promise<Record<string, unknown>> {
    const requestedBy = String(options.requestedBy ?? "").trim();
    if (!requestedBy) {
      throw new Error("requestedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    const scopes = Array.isArray(options.scopes)
      ? options.scopes.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean)
      : [];
    return this.requestJson<Record<string, unknown>>("/v1/adoption/project-reset", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        requested_by: requestedBy,
        reason: asOptionalString(options.reason) ?? undefined,
        scopes: scopes.length > 0 ? scopes : undefined,
        cascade_cleanup_orphan_draft_pages: options.cascadeCleanupOrphanDraftPages ?? false,
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAdoptionSyncCursorHealth(options: {
    staleAfterHours?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/sync/cursor-health", {
      method: "GET",
      params: {
        project_id: this.projectId,
        stale_after_hours: normalizeInt(options.staleAfterHours ?? 24, 1, 24 * 30)
      }
    });
  }

  async enableAdoptionSafeMode(options: {
    updatedBy: string;
    dryRun?: boolean;
    note?: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/safe-mode/enable", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId,
        note: asOptionalString(options.note) ?? undefined
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async recommendAdoptionSafeMode(options: {
    recommendedBy: string;
    days?: number;
    dryRun?: boolean;
    note?: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const recommendedBy = String(options.recommendedBy ?? "").trim();
    if (!recommendedBy) {
      throw new Error("recommendedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/safe-mode/recommend", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        recommended_by: recommendedBy,
        days: normalizeInt(options.days ?? 14, 1, 90),
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId,
        note: asOptionalString(options.note) ?? undefined
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listWikiDrafts(options: ListWikiDraftsOptions = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/wiki/drafts", {
      method: "GET",
      params: {
        project_id: this.projectId,
        status: asOptionalString(options.status)?.toLowerCase(),
        limit: normalizeInt(options.limit ?? 50, 1, 200)
      }
    });
  }

  async bulkReviewWikiDrafts(options: BulkReviewWikiDraftsOptions): Promise<Record<string, unknown>> {
    const reviewedBy = String(options.reviewedBy ?? "").trim();
    if (!reviewedBy) {
      throw new Error("reviewedBy is required");
    }
    const action = String(options.action ?? "approve").trim().toLowerCase();
    if (!["approve", "reject"].includes(action)) {
      throw new Error("action must be one of: approve, reject");
    }
    return this.requestJson<Record<string, unknown>>("/v1/wiki/drafts/bulk-review", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        reviewed_by: reviewedBy,
        action,
        dry_run: options.dryRun ?? true,
        limit: normalizeInt(options.limit ?? 200, 1, 2000),
        filter: options.filter ?? {},
        note: asOptionalString(options.note) ?? undefined,
        reason: asOptionalString(options.reason) ?? undefined,
        force: options.force ?? false,
        dismiss_conflicts: options.dismissConflicts ?? true
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async runAdoptionAgentWikiBootstrap(options: {
    updatedBy: string;
    dryRun?: boolean;
    publish?: boolean;
    bootstrapPublishCore?: boolean;
    spaceKey?: string;
    includeDataSourcesCatalog?: boolean;
    includeAgentCapabilityProfile?: boolean;
    includeToolingMap?: boolean;
    includeProcessPlaybooks?: boolean;
    includeCompanyOperatingContext?: boolean;
    includeOperationalLogic?: boolean;
    includeFirstRunStarter?: boolean;
    includeStateSnapshot?: boolean;
    maxSources?: number;
    maxAgents?: number;
    maxSignals?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const dryRun = options.dryRun ?? true;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/agent-wiki-bootstrap", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        dry_run: dryRun,
        confirm_project_id: dryRun ? undefined : this.projectId,
        publish: options.publish ?? true,
        bootstrap_publish_core: options.bootstrapPublishCore ?? true,
        space_key: asOptionalString(options.spaceKey) ?? "operations",
        include_data_sources_catalog: options.includeDataSourcesCatalog ?? true,
        include_agent_capability_profile: options.includeAgentCapabilityProfile ?? true,
        include_tooling_map: options.includeToolingMap ?? true,
        include_process_playbooks: options.includeProcessPlaybooks ?? true,
        include_company_operating_context: options.includeCompanyOperatingContext ?? true,
        include_operational_logic: options.includeOperationalLogic ?? true,
        include_first_run_starter: options.includeFirstRunStarter ?? true,
        include_state_snapshot: options.includeStateSnapshot ?? true,
        max_sources: normalizeInt(options.maxSources ?? 25, 1, 150),
        max_agents: normalizeInt(options.maxAgents ?? 100, 1, 5000),
        max_signals: normalizeInt(options.maxSignals ?? 40, 1, 200)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getBootstrapMigrationRecommendation(): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/wiki/drafts/bootstrap-approve/recommendation", {
      method: "GET",
      params: {
        project_id: this.projectId
      }
    });
  }

  async getWikiStateSnapshot(options: {
    spaceKey?: string;
    maxWorkstreams?: number;
    maxOpenItems?: number;
    maxPeopleWatch?: number;
    maxMetrics?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/wiki/state", {
      method: "GET",
      params: {
        project_id: this.projectId,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        max_workstreams: normalizeInt(options.maxWorkstreams ?? 12, 1, 50),
        max_open_items: normalizeInt(options.maxOpenItems ?? 25, 1, 200),
        max_people_watch: normalizeInt(options.maxPeopleWatch ?? 15, 1, 100),
        max_metrics: normalizeInt(options.maxMetrics ?? 12, 1, 100)
      }
    });
  }

  async getWikiChangeFeed(options: {
    spaceKey?: string;
    since?: string;
    sinceHours?: number;
    limit?: number;
    includeReviewed?: boolean;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/wiki/change-feed", {
      method: "GET",
      params: {
        project_id: this.projectId,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        since: asOptionalString(options.since) ?? undefined,
        since_hours: normalizeInt(options.sinceHours ?? 24, 1, 24 * 30),
        limit: normalizeInt(options.limit ?? 20, 1, 100),
        include_reviewed: Boolean(options.includeReviewed ?? false)
      }
    });
  }

  async syncWikiStateSnapshot(options: {
    updatedBy: string;
    spaceKey?: string;
    status?: "draft" | "reviewed" | "published" | "archived" | string;
    maxWorkstreams?: number;
    maxOpenItems?: number;
    maxPeopleWatch?: number;
    maxMetrics?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    const status = String(options.status ?? "published").trim().toLowerCase() || "published";
    if (!["draft", "reviewed", "published", "archived"].includes(status)) {
      throw new Error("status must be one of: draft, reviewed, published, archived");
    }
    return this.requestJson<Record<string, unknown>>("/v1/wiki/state/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        status,
        max_workstreams: normalizeInt(options.maxWorkstreams ?? 12, 1, 50),
        max_open_items: normalizeInt(options.maxOpenItems ?? 25, 1, 200),
        max_people_watch: normalizeInt(options.maxPeopleWatch ?? 15, 1, 100),
        max_metrics: normalizeInt(options.maxMetrics ?? 12, 1, 100)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async hydrateAgentSharedMemory(options: {
    agentId?: string;
    role?: string;
    spaceKey?: string;
    since?: string;
    sinceHours?: number;
    limit?: number;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
    maxWorkstreams?: number;
    maxOpenItems?: number;
    maxPeopleWatch?: number;
    maxMetrics?: number;
    maxItemsPerSection?: number;
    freshnessDays?: number;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/hydrate", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        since: asOptionalString(options.since) ?? undefined,
        since_hours: normalizeInt(options.sinceHours ?? 24, 1, 24 * 30),
        limit: normalizeInt(options.limit ?? 20, 1, 100),
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto",
        max_workstreams: normalizeInt(options.maxWorkstreams ?? 12, 1, 50),
        max_open_items: normalizeInt(options.maxOpenItems ?? 25, 1, 200),
        max_people_watch: normalizeInt(options.maxPeopleWatch ?? 15, 1, 100),
        max_metrics: normalizeInt(options.maxMetrics ?? 12, 1, 100),
        max_items_per_section: normalizeInt(options.maxItemsPerSection ?? 5, 1, 20),
        freshness_days: normalizeInt(options.freshnessDays ?? 14, 1, 90)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentSharedMemoryInvalidation(options: {
    agentId?: string;
    role?: string;
    spaceKey?: string;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/invalidation", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto"
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentSharedMemoryImpact(options: {
    spaceKey?: string;
    since?: string;
    sinceHours?: number;
    limit?: number;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/impact", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        since: asOptionalString(options.since) ?? undefined,
        since_hours: normalizeInt(options.sinceHours ?? 24, 1, 24 * 30),
        limit: normalizeInt(options.limit ?? 20, 1, 100),
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto"
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async previewAgentSharedMemoryPublishImpact(options: {
    agentId?: string;
    role?: string;
    spaceKey?: string;
    pageSlug?: string;
    pageTitle?: string;
    pageType?: string;
    entityKey?: string;
    changeSummary?: string;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
    limit?: number;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/publish-impact-preview", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        page_slug: asOptionalString(options.pageSlug) ?? undefined,
        page_title: asOptionalString(options.pageTitle) ?? undefined,
        page_type: asOptionalString(options.pageType) ?? undefined,
        entity_key: asOptionalString(options.entityKey) ?? undefined,
        change_summary: asOptionalString(options.changeSummary) ?? undefined,
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto",
        limit: normalizeInt(options.limit ?? 25, 1, 100)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentSharedMemoryHealth(options: {
    agentId?: string;
    role?: string;
    spaceKey?: string;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/health", {
      method: "GET",
      params: {
        project_id: this.projectId,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto"
      }
    });
  }

  async upsertAgentSharedMemoryEntry(options: {
    updatedBy: string;
    title: string;
    summary: string;
    content?: string;
    visibilityTier?: "reviewed_team" | "draft_private" | string;
    status?: "active" | "archived" | string;
    entryId?: number;
    spaceKey?: string;
    ownerAgentId?: string;
    roleScope?: string;
    teamScope?: string;
    entityKey?: string;
    pageSlug?: string;
    deltaKind?: string;
    actionHint?: string;
    importance?: "low" | "medium" | "high" | string;
    sourceKind?: string;
    sourceRef?: string;
    metadata?: Record<string, unknown>;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/entries", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: String(options.updatedBy || "").trim(),
        entry_id: options.entryId == null ? undefined : normalizeInt(options.entryId, 1, Number.MAX_SAFE_INTEGER),
        title: String(options.title || "").trim(),
        summary: String(options.summary || "").trim(),
        content: asOptionalString(options.content) ?? undefined,
        visibility_tier: String(options.visibilityTier ?? "reviewed_team").trim().toLowerCase() || "reviewed_team",
        status: String(options.status ?? "active").trim().toLowerCase() || "active",
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        owner_agent_id: asOptionalString(options.ownerAgentId) ?? undefined,
        role_scope: asOptionalString(options.roleScope) ?? undefined,
        team_scope: asOptionalString(options.teamScope) ?? undefined,
        entity_key: asOptionalString(options.entityKey) ?? undefined,
        page_slug: asOptionalString(options.pageSlug) ?? undefined,
        delta_kind: String(options.deltaKind ?? "knowledge_change").trim().toLowerCase() || "knowledge_change",
        action_hint: asOptionalString(options.actionHint) ?? undefined,
        importance: String(options.importance ?? "medium").trim().toLowerCase() || "medium",
        source_kind: String(options.sourceKind ?? "agent_note").trim().toLowerCase() || "agent_note",
        source_ref: asOptionalString(options.sourceRef) ?? undefined,
        metadata: options.metadata ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAgentSharedMemoryEntries(options: {
    agentId?: string;
    role?: string;
    spaceKey?: string;
    visibilityTier?: "reviewed_team" | "draft_private" | string;
    includeArchived?: boolean;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/entries", {
      method: "GET",
      params: {
        project_id: this.projectId,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        visibility_tier: asOptionalString(options.visibilityTier)?.toLowerCase() ?? undefined,
        include_archived: Boolean(options.includeArchived ?? false),
        limit: normalizeInt(options.limit ?? 50, 1, 200)
      }
    });
  }

  async upsertAgentSharedMemoryFanoutHook(options: {
    updatedBy: string;
    name: string;
    endpointUrl: string;
    enabled?: boolean;
    hookId?: number;
    spaceKey?: string;
    deliveryMode?: "invalidation" | "impact" | "publish_preview" | string;
    headers?: Record<string, string>;
    timeoutSeconds?: number;
    retryMaxAttempts?: number;
    retryBackoffSeconds?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/fanout-hooks", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: String(options.updatedBy || "").trim(),
        hook_id: options.hookId == null ? undefined : normalizeInt(options.hookId, 1, Number.MAX_SAFE_INTEGER),
        name: String(options.name || "").trim(),
        endpoint_url: String(options.endpointUrl || "").trim(),
        enabled: Boolean(options.enabled ?? true),
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        delivery_mode: String(options.deliveryMode ?? "invalidation").trim().toLowerCase() || "invalidation",
        headers: options.headers ?? {},
        timeout_seconds: normalizeInt(options.timeoutSeconds ?? 5, 1, 60),
        retry_max_attempts: normalizeInt(options.retryMaxAttempts ?? 3, 1, 10),
        retry_backoff_seconds: normalizeInt(options.retryBackoffSeconds ?? 300, 30, 86400)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAgentSharedMemoryFanoutHooks(options: {
    spaceKey?: string;
    enabledOnly?: boolean;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/fanout-hooks", {
      method: "GET",
      params: {
        project_id: this.projectId,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        enabled_only: Boolean(options.enabledOnly ?? false),
        limit: normalizeInt(options.limit ?? 50, 1, 200)
      }
    });
  }

  async dispatchAgentSharedMemoryFanout(options: {
    updatedBy?: string;
    agentId?: string;
    role?: string;
    spaceKey?: string;
    includeReviewed?: boolean;
    reviewPolicyMode?: "auto" | "published_only" | "reviewed_plus_published" | string;
    memoryTierMode?: "auto" | "published_org" | "reviewed_team" | "draft_private" | string;
    dispatchMode?: "invalidation" | "impact" | "publish_preview" | string;
    dryRun?: boolean;
    pageSlug?: string;
    pageTitle?: string;
    pageType?: string;
    entityKey?: string;
    changeSummary?: string;
    limit?: number;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/fanout-dispatch", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: asOptionalString(options.updatedBy) ?? undefined,
        agent_id: asOptionalString(options.agentId) ?? undefined,
        role: asOptionalString(options.role) ?? undefined,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        include_reviewed: Boolean(options.includeReviewed ?? false),
        review_policy_mode: String(options.reviewPolicyMode ?? "auto").trim().toLowerCase() || "auto",
        memory_tier_mode: String(options.memoryTierMode ?? "auto").trim().toLowerCase() || "auto",
        dispatch_mode: String(options.dispatchMode ?? "invalidation").trim().toLowerCase() || "invalidation",
        dry_run: Boolean(options.dryRun ?? true),
        page_slug: asOptionalString(options.pageSlug) ?? undefined,
        page_title: asOptionalString(options.pageTitle) ?? undefined,
        page_type: asOptionalString(options.pageType) ?? undefined,
        entity_key: asOptionalString(options.entityKey) ?? undefined,
        change_summary: asOptionalString(options.changeSummary) ?? undefined,
        limit: normalizeInt(options.limit ?? 25, 1, 100)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAgentSharedMemoryFanoutDeliveries(options: {
    spaceKey?: string;
    hookId?: number;
    status?: "planned" | "pending" | "delivered" | "failed" | string;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/fanout-deliveries", {
      method: "GET",
      params: {
        project_id: this.projectId,
        space_key: asOptionalString(options.spaceKey) ?? undefined,
        hook_id: options.hookId == null ? undefined : normalizeInt(options.hookId, 1, Number.MAX_SAFE_INTEGER),
        status: asOptionalString(options.status)?.toLowerCase() ?? undefined,
        limit: normalizeInt(options.limit ?? 50, 1, 200)
      }
    });
  }

  async retryAgentSharedMemoryFanoutDelivery(options: {
    deliveryId: number;
    updatedBy?: string;
    dryRun?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(
      `/v1/agents/shared-memory/fanout-deliveries/${normalizeInt(options.deliveryId, 1, Number.MAX_SAFE_INTEGER)}/retry`,
      {
        method: "POST",
        payload: {
          project_id: this.projectId,
          updated_by: asOptionalString(options.updatedBy) ?? undefined,
          dry_run: Boolean(options.dryRun ?? false)
        },
        idempotencyKey: options.idempotencyKey ?? makeUuid()
      }
    );
  }

  async processDueAgentSharedMemoryFanoutRetries(options: {
    updatedBy?: string;
    dryRun?: boolean;
    limit?: number;
    spaceKey?: string;
    idempotencyKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/shared-memory/fanout-deliveries/process-due-retries", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: asOptionalString(options.updatedBy) ?? undefined,
        dry_run: Boolean(options.dryRun ?? true),
        limit: normalizeInt(options.limit ?? 20, 1, 100),
        space_key: asOptionalString(options.spaceKey) ?? undefined
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAdoptionPipelineVisibility(options: {
    days?: number;
    sourceSystems?: string[];
    namespaces?: string[];
  } = {}): Promise<Record<string, unknown>> {
    const sourceSystems = Array.isArray(options.sourceSystems)
      ? options.sourceSystems.map((value) => String(value).trim().toLowerCase()).filter((value) => value.length > 0)
      : [];
    const namespaces = Array.isArray(options.namespaces)
      ? options.namespaces.map((value) => String(value).trim().toLowerCase()).filter((value) => value.length > 0)
      : [];
    return this.requestJson<Record<string, unknown>>("/v1/adoption/pipeline/visibility", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        source_systems: sourceSystems.length > 0 ? sourceSystems.join(",") : undefined,
        namespaces: namespaces.length > 0 ? namespaces.join(",") : undefined
      }
    });
  }

  async getAdoptionWikiQualityReport(options: {
    days?: number;
    placeholderRatioMax?: number;
    dailySummaryDraftRatioMax?: number;
    minCorePublished?: number;
  } = {}): Promise<Record<string, unknown>> {
    const placeholderRatioMax = Number.isFinite(options.placeholderRatioMax)
      ? Number(options.placeholderRatioMax)
      : 0.1;
    const dailySummaryDraftRatioMax = Number.isFinite(options.dailySummaryDraftRatioMax)
      ? Number(options.dailySummaryDraftRatioMax)
      : 0.2;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/wiki-quality/report", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        placeholder_ratio_max: Math.max(0, Math.min(1, placeholderRatioMax)),
        daily_summary_draft_ratio_max: Math.max(0, Math.min(1, dailySummaryDraftRatioMax)),
        min_core_published: normalizeInt(options.minCorePublished ?? 6, 1, 50)
      }
    });
  }

  async getAdoptionWikiRichnessBenchmark(options: {
    days?: number;
    placeholderRatioMax?: number;
    dailySummaryDraftRatioMax?: number;
    minCorePublished?: number;
    minContractPassRatio?: number;
    minAveragePageScore?: number;
  } = {}): Promise<Record<string, unknown>> {
    const placeholderRatioMax = Number.isFinite(options.placeholderRatioMax)
      ? Number(options.placeholderRatioMax)
      : 0.1;
    const dailySummaryDraftRatioMax = Number.isFinite(options.dailySummaryDraftRatioMax)
      ? Number(options.dailySummaryDraftRatioMax)
      : 0.2;
    const minContractPassRatio = Number.isFinite(options.minContractPassRatio)
      ? Number(options.minContractPassRatio)
      : 0.8;
    const minAveragePageScore = Number.isFinite(options.minAveragePageScore)
      ? Number(options.minAveragePageScore)
      : 0.72;
    return this.requestJson<Record<string, unknown>>("/v1/adoption/wiki-richness/benchmark", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        placeholder_ratio_max: Math.max(0, Math.min(1, placeholderRatioMax)),
        daily_summary_draft_ratio_max: Math.max(0, Math.min(1, dailySummaryDraftRatioMax)),
        min_core_published: normalizeInt(options.minCorePublished ?? 6, 1, 50),
        min_contract_pass_ratio: Math.max(0, Math.min(1, minContractPassRatio)),
        min_average_page_score: Math.max(0, Math.min(1, minAveragePageScore))
      }
    });
  }

  async getAdoptionRejectionDiagnostics(options: {
    days?: number;
    sampleLimit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/adoption/rejections/diagnostics", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 14, 1, 90),
        sample_limit: normalizeInt(options.sampleLimit ?? 5, 1, 25)
      }
    });
  }

  async listLegacyImportProfiles(options: {
    sourceType?: "postgres_sql" | string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/profiles", {
      method: "GET",
      params: {
        source_type: String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql"
      }
    });
  }

  async listLegacyImportMapperTemplates(options: {
    sourceType?: "postgres_sql" | string;
    profile?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/mapper-templates", {
      method: "GET",
      params: {
        source_type: String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql",
        profile: options.profile ? String(options.profile).trim() : undefined
      }
    });
  }

  async listLegacyImportSyncContracts(options: {
    sourceType?: "postgres_sql" | string;
    profile?: string;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/sync-contracts", {
      method: "GET",
      params: {
        source_type: String(options.sourceType ?? "postgres_sql").trim().toLowerCase() || "postgres_sql",
        profile: options.profile ? String(options.profile).trim() : undefined
      }
    });
  }

  async listLegacyImportSources(options: {
    enabled?: boolean;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/sources", {
      method: "GET",
      params: {
        project_id: this.projectId,
        enabled: typeof options.enabled === "boolean" ? options.enabled : undefined,
        limit: normalizeInt(options.limit ?? 100, 1, 500)
      }
    });
  }

  async upsertLegacyImportSource(options: {
    sourceType: "local_dir" | "notion_root_page" | "postgres_sql" | "memory_api" | string;
    sourceRef: string;
    updatedBy: string;
    enabled?: boolean;
    syncIntervalMinutes?: number;
    nextRunAt?: string | null;
    config?: Record<string, unknown>;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const sourceType = String(options.sourceType ?? "").trim().toLowerCase();
    const sourceRef = String(options.sourceRef ?? "").trim();
    const updatedBy = String(options.updatedBy ?? "").trim();
    if (!sourceType) {
      throw new Error("sourceType is required");
    }
    if (!sourceRef) {
      throw new Error("sourceRef is required");
    }
    if (!updatedBy) {
      throw new Error("updatedBy is required");
    }
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/sources", {
      method: "PUT",
      payload: {
        project_id: this.projectId,
        source_type: sourceType,
        source_ref: sourceRef,
        enabled: options.enabled ?? true,
        sync_interval_minutes: normalizeInt(options.syncIntervalMinutes ?? 60, 1, 10080),
        next_run_at: options.nextRunAt ?? null,
        updated_by: updatedBy,
        config: options.config ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async queueLegacyImportSourceSync(options: {
    sourceId: string;
    requestedBy: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const sourceId = String(options.sourceId ?? "").trim();
    const requestedBy = String(options.requestedBy ?? "").trim();
    if (!sourceId) {
      throw new Error("sourceId is required");
    }
    if (!requestedBy) {
      throw new Error("requestedBy is required");
    }
    return this.requestJson<Record<string, unknown>>(`/v1/legacy-import/sources/${encodeURIComponent(sourceId)}/sync`, {
      method: "POST",
      payload: {
        project_id: this.projectId,
        requested_by: requestedBy
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listLegacyImportSyncRuns(options: {
    sourceId?: string;
    status?: "queued" | "running" | "completed" | "failed" | "skipped" | string;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/legacy-import/runs", {
      method: "GET",
      params: {
        project_id: this.projectId,
        source_id: options.sourceId ? String(options.sourceId).trim() : undefined,
        status: options.status ? String(options.status).trim().toLowerCase() : undefined,
        limit: normalizeInt(options.limit ?? 100, 1, 500)
      }
    });
  }

  async listTasks(options: {
    status?: TaskStatus;
    assignee?: string;
    entityKey?: string;
    includeClosed?: boolean;
    limit?: number;
  } = {}): Promise<Array<Record<string, unknown>>> {
    const response = await this.requestJson<{ tasks?: Array<Record<string, unknown>> }>("/v1/tasks", {
      method: "GET",
      params: {
        project_id: this.projectId,
        status: options.status,
        assignee: options.assignee,
        entity_key: options.entityKey,
        include_closed: options.includeClosed ?? false,
        limit: normalizeInt(options.limit ?? 100, 1, 500)
      }
    });
    return Array.isArray(response.tasks) ? response.tasks : [];
  }

  async getTask(taskId: string, options: { eventsLimit?: number; linksLimit?: number } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(`/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "GET",
      params: {
        project_id: this.projectId,
        events_limit: normalizeInt(options.eventsLimit ?? 100, 0, 500),
        links_limit: normalizeInt(options.linksLimit ?? 100, 0, 500)
      }
    });
  }

  async upsertTask(
    task: TaskInput,
    options: { taskId?: string; createdBy: string; updatedBy?: string; idempotencyKey?: string }
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/tasks", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        task_id: options.taskId,
        title: task.title,
        description: task.description ?? null,
        status: task.status ?? "todo",
        priority: task.priority ?? "normal",
        source: task.source ?? "human",
        assignee: task.assignee ?? null,
        entity_key: task.entityKey ?? null,
        category: task.category ?? null,
        due_at: task.dueAt ?? null,
        metadata: task.metadata ?? {},
        created_by: options.createdBy,
        updated_by: options.updatedBy ?? null
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async updateTaskStatus(
    taskId: string,
    options: { status: TaskStatus; updatedBy: string; note?: string; idempotencyKey?: string }
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(`/v1/tasks/${encodeURIComponent(taskId)}/status`, {
      method: "POST",
      payload: {
        project_id: this.projectId,
        status: options.status,
        updated_by: options.updatedBy,
        note: options.note ?? null
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async commentTask(
    taskId: string,
    comment: TaskCommentInput,
    options: { createdBy: string; idempotencyKey?: string }
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(`/v1/tasks/${encodeURIComponent(taskId)}/comments`, {
      method: "POST",
      payload: {
        project_id: this.projectId,
        created_by: options.createdBy,
        comment: comment.comment,
        metadata: comment.metadata ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async linkTask(
    taskId: string,
    link: TaskLinkInput,
    options: { createdBy: string; idempotencyKey?: string }
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(`/v1/tasks/${encodeURIComponent(taskId)}/links`, {
      method: "POST",
      payload: {
        project_id: this.projectId,
        created_by: options.createdBy,
        link_type: link.linkType,
        link_ref: link.linkRef,
        note: link.note ?? null,
        metadata: link.metadata ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAgents(options: {
    status?: "active" | "idle" | "paused" | "offline" | "retired";
    team?: string;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents", {
      method: "GET",
      params: {
        project_id: this.projectId,
        status: options.status,
        team: options.team,
        limit: normalizeInt(options.limit ?? 100, 1, 500)
      }
    });
  }

  async getAgentPublishPolicy(agentId: string): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/publish-policy", {
      method: "GET",
      params: {
        project_id: this.projectId,
        agent_id: agentId
      }
    });
  }

  async upsertAgentPublishPolicy(options: {
    agentId: string;
    updatedBy: string;
    defaultMode?: "auto_publish" | "conditional" | "human_required";
    byPageType?: Record<string, "auto_publish" | "conditional" | "human_required">;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/publish-policy", {
      method: "PUT",
      payload: {
        project_id: this.projectId,
        agent_id: options.agentId,
        updated_by: options.updatedBy,
        default_mode: options.defaultMode ?? "auto_publish",
        by_page_type: options.byPageType ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getWikiSpacePolicy(spaceKey: string): Promise<WikiSpacePolicyResponse> {
    const normalizedSpaceKey = normalizeWikiSpaceKey(spaceKey);
    return this.requestJson<WikiSpacePolicyResponse>(`/v1/wiki/spaces/${encodeURIComponent(normalizedSpaceKey)}/policy`, {
      method: "GET",
      params: {
        project_id: this.projectId
      }
    });
  }

  async listWikiSpacePolicyAudit(
    spaceKey: string,
    options: {
      limit?: number;
    } = {}
  ): Promise<WikiSpacePolicyAuditResponse> {
    const normalizedSpaceKey = normalizeWikiSpaceKey(spaceKey);
    return this.requestJson<WikiSpacePolicyAuditResponse>(`/v1/wiki/spaces/${encodeURIComponent(normalizedSpaceKey)}/policy/audit`, {
      method: "GET",
      params: {
        project_id: this.projectId,
        limit: normalizeInt(options.limit ?? 40, 1, 200)
      }
    });
  }

  async upsertWikiSpacePolicy(
    spaceKey: string,
    options: {
      updatedBy: string;
      writeMode?: WikiSpacePolicyMode;
      commentMode?: WikiSpacePolicyMode;
      reviewAssignmentRequired?: boolean;
      metadata?: Record<string, unknown>;
      idempotencyKey?: string;
    }
  ): Promise<WikiSpacePolicyResponse> {
    const normalizedSpaceKey = normalizeWikiSpaceKey(spaceKey);
    const writeMode = normalizeWikiSpacePolicyMode(options.writeMode ?? "open");
    const commentMode = normalizeWikiSpacePolicyMode(options.commentMode ?? "open");
    return this.requestJson<WikiSpacePolicyResponse>(`/v1/wiki/spaces/${encodeURIComponent(normalizedSpaceKey)}/policy`, {
      method: "PUT",
      payload: {
        project_id: this.projectId,
        space_key: normalizedSpaceKey,
        updated_by: String(options.updatedBy ?? "").trim(),
        write_mode: writeMode,
        comment_mode: commentMode,
        review_assignment_required: options.reviewAssignmentRequired ?? false,
        metadata: options.metadata ?? {}
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getWikiSpacePublishChecklistPreset(
    spaceKey: string,
    options: {
      fallback?: WikiPublishChecklistPreset;
    } = {}
  ): Promise<WikiPublishChecklistPreset> {
    const fallback = normalizeWikiPublishChecklistPreset(options.fallback ?? "none");
    const response = await this.getWikiSpacePolicy(spaceKey);
    const metadata =
      response?.policy?.metadata && isPlainObject(response.policy.metadata)
        ? (response.policy.metadata as Record<string, unknown>)
        : {};
    return normalizeWikiPublishChecklistPreset(metadata.publish_checklist_preset, fallback);
  }

  async setWikiSpacePublishChecklistPreset(
    spaceKey: string,
    options: {
      preset: WikiPublishChecklistPreset;
      updatedBy: string;
      reason?: string;
      metadataPatch?: Record<string, unknown>;
      idempotencyKey?: string;
    }
  ): Promise<WikiSpacePolicyResponse> {
    const normalizedPreset = normalizeWikiPublishChecklistPreset(options.preset);
    const current = await this.getWikiSpacePolicy(spaceKey);
    const currentPolicy = current?.policy && isPlainObject(current.policy)
      ? (current.policy as Record<string, unknown>)
      : {};
    const currentMetadata =
      currentPolicy.metadata && isPlainObject(currentPolicy.metadata)
        ? (currentPolicy.metadata as Record<string, unknown>)
        : {};
    const nextMetadata: Record<string, unknown> = {
      ...currentMetadata,
      ...(options.metadataPatch ?? {}),
      publish_checklist_preset: normalizedPreset
    };
    if (asOptionalString(options.reason)) {
      nextMetadata.policy_change_reason = String(options.reason).trim();
    }

    return this.upsertWikiSpacePolicy(spaceKey, {
      updatedBy: options.updatedBy,
      writeMode: normalizeWikiSpacePolicyMode(asOptionalString(currentPolicy.write_mode) ?? "open"),
      commentMode: normalizeWikiSpacePolicyMode(asOptionalString(currentPolicy.comment_mode) ?? "open"),
      reviewAssignmentRequired: Boolean(currentPolicy.review_assignment_required),
      metadata: nextMetadata,
      idempotencyKey: options.idempotencyKey
    });
  }

  async getWikiLifecycleStats(options: {
    staleDays?: number;
    criticalDays?: number;
    staleLimit?: number;
    spaceKey?: string;
    pageTypeAware?: boolean;
  } = {}): Promise<Record<string, unknown>> {
    const staleDays = normalizeInt(options.staleDays ?? 21, 1, 365);
    const criticalDays = normalizeInt(options.criticalDays ?? 45, staleDays, 365);
    const staleLimit = normalizeInt(options.staleLimit ?? 20, 1, 200);
    return this.requestJson<Record<string, unknown>>("/v1/wiki/lifecycle/stats", {
      method: "GET",
      params: {
        project_id: this.projectId,
        stale_days: staleDays,
        critical_days: criticalDays,
        stale_limit: staleLimit,
        space_key: asOptionalString(options.spaceKey) ? normalizeWikiSpaceKey(String(options.spaceKey)) : undefined,
        page_type_aware: options.pageTypeAware ?? true
      }
    });
  }

  async getWikiLifecycleTelemetry(options: {
    days?: number;
    actionKey?: string;
  } = {}): Promise<Record<string, unknown>> {
    const normalizedActionKey = normalizeLifecycleActionKey(options.actionKey);
    return this.requestJson<Record<string, unknown>>("/v1/wiki/lifecycle/telemetry", {
      method: "GET",
      params: {
        project_id: this.projectId,
        days: normalizeInt(options.days ?? 7, 1, 90),
        action_key: normalizedActionKey || undefined
      }
    });
  }

  async snapshotWikiLifecycleTelemetry(options: {
    sessionId: string;
    emptyScopeActionShown?: Record<string, number>;
    emptyScopeActionApplied?: Record<string, number>;
    observedAt?: string;
    source?: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    const sessionId = asOptionalString(options.sessionId);
    if (!sessionId) {
      throw new Error("sessionId is required");
    }
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      session_id: sessionId,
      source: asOptionalString(options.source) ?? "sdk_client",
      empty_scope_action_shown: normalizeLifecycleActionCounts(options.emptyScopeActionShown),
      empty_scope_action_applied: normalizeLifecycleActionCounts(options.emptyScopeActionApplied)
    };
    if (asOptionalString(options.observedAt)) {
      payload.observed_at = String(options.observedAt).trim();
    }
    return this.requestJson<Record<string, unknown>>("/v1/wiki/lifecycle/telemetry/snapshot", {
      method: "POST",
      payload,
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async registerAgentProfile(
    profile: AgentProfileInput,
    options: {
      updatedBy: string;
      idempotencyKey?: string;
    }
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/register", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        agent_id: profile.agentId,
        updated_by: options.updatedBy,
        display_name: profile.displayName ?? null,
        team: profile.team ?? null,
        role: profile.role ?? null,
        status: profile.status ?? "active",
        responsibilities: profile.responsibilities ?? [],
        tools: profile.tools ?? [],
        data_sources: profile.dataSources ?? [],
        limits: profile.limits ?? [],
        metadata: profile.metadata ?? {},
        ensure_scaffold: profile.ensureScaffold ?? true,
        include_daily_report_stub: profile.includeDailyReportStub ?? true,
        last_seen_at: profile.lastSeenAt ?? new Date().toISOString()
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async syncAgentRuntimeSurface(
    agents: AgentRuntimeSurfaceAgentInput[],
    options: {
      updatedBy: string;
      ensureScaffold?: boolean;
      includeDailyReportStub?: boolean;
      refreshBootstrapPages?: boolean;
      refreshSpaceKeys?: string[];
      bootstrapPublishCore?: boolean;
      idempotencyKey?: string;
    }
  ): Promise<Record<string, unknown>> {
    const updatedBy = asOptionalString(options.updatedBy);
    if (!updatedBy) {
      throw new Error("options.updatedBy is required");
    }
    return this.requestJson<Record<string, unknown>>("/v1/agents/runtime-surface/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        updated_by: updatedBy,
        agents: (agents ?? []).map((agent) => ({
          agent_id: asOptionalString(agent.agentId),
          display_name: asOptionalString(agent.displayName) ?? null,
          team: asOptionalString(agent.team) ?? null,
          role: asOptionalString(agent.role) ?? null,
          runtime_overview: agent.runtimeOverview ?? {},
          scheduled_tasks: agent.scheduledTasks ?? [],
          standing_orders: agent.standingOrders ?? [],
          capability_registry: agent.capabilityRegistry ?? [],
          action_surface: agent.actionSurface ?? [],
          tool_manifest: agent.toolManifest ?? [],
          source_hints: agent.sourceHints ?? [],
          model_routing: agent.modelRouting ?? null,
          approvals: agent.approvals ?? [],
          limits: agent.limits ?? [],
          metadata: agent.metadata ?? {}
        })),
        ensure_scaffold: options.ensureScaffold ?? true,
        include_daily_report_stub: options.includeDailyReportStub ?? true,
        refresh_bootstrap_pages: options.refreshBootstrapPages ?? true,
        refresh_space_keys: options.refreshSpaceKeys ?? [],
        bootstrap_publish_core: options.bootstrapPublishCore ?? true
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async submitAgentReflection(
    reflection: AgentReflectionInput,
    options: {
      idempotencyKey?: string;
    } = {}
  ): Promise<Record<string, unknown>> {
    const agentId = asOptionalString(reflection.agentId);
    const reflectedBy = asOptionalString(reflection.reflectedBy);
    if (!agentId) {
      throw new Error("reflection.agentId is required");
    }
    if (!reflectedBy) {
      throw new Error("reflection.reflectedBy is required");
    }
    return this.requestJson<Record<string, unknown>>("/v1/agents/reflections", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        agent_id: agentId,
        reflected_by: reflectedBy,
        task_id: asOptionalString(reflection.taskId) ?? null,
        session_id: asOptionalString(reflection.sessionId) ?? null,
        trace_id: asOptionalString(reflection.traceId) ?? null,
        outcome: asOptionalString(reflection.outcome) ?? null,
        summary: asOptionalString(reflection.summary) ?? null,
        learned_rules: (reflection.learnedRules ?? []).map((item) => String(item).trim()).filter(Boolean),
        decisions_made: (reflection.decisionsMade ?? []).map((item) => String(item).trim()).filter(Boolean),
        tools_used: (reflection.toolsUsed ?? []).map((item) => String(item).trim()).filter(Boolean),
        data_sources_used: (reflection.dataSourcesUsed ?? []).map((item) => String(item).trim()).filter(Boolean),
        follow_up_actions: (reflection.followUpActions ?? []).map((item) => String(item).trim()).filter(Boolean),
        uncertainties: (reflection.uncertainties ?? []).map((item) => String(item).trim()).filter(Boolean),
        insights: (reflection.insights ?? []).map((item) => ({
          claim_text: String(item.claimText ?? "").trim(),
          category: asOptionalString(item.category) ?? null,
          confidence: typeof item.confidence === "number" ? clamp(item.confidence, 0, 1) : null,
          temporary: item.temporary ?? false,
          evidence: item.evidence ?? [],
          metadata: item.metadata ?? {}
        })),
        metadata: reflection.metadata ?? {},
        observed_at: asOptionalString(reflection.observedAt) ?? null
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async syncAgentWorklogs(options: {
    generatedBy: string;
    worklogDate?: string;
    timezone?: string;
    daysBack?: number;
    maxAgents?: number;
    includeRetired?: boolean;
    includeIdleDays?: boolean;
    minActivityScore?: number;
    triggerMode?: "daily_batch" | "session_close" | "task_close" | "manual";
    triggerReason?: string;
    maxLogsPerAgentPage?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/worklogs/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        generated_by: options.generatedBy,
        worklog_date: options.worklogDate ?? null,
        timezone: asOptionalString(options.timezone) ?? null,
        days_back: normalizeInt(options.daysBack ?? 1, 1, 30),
        max_agents: normalizeInt(options.maxAgents ?? 200, 1, 2000),
        include_retired: options.includeRetired ?? false,
        include_idle_days: options.includeIdleDays ?? false,
        min_activity_score: normalizeInt(options.minActivityScore ?? 1, 0, 1000),
        trigger_mode: options.triggerMode ?? "daily_batch",
        trigger_reason: asOptionalString(options.triggerReason) ?? null,
        max_logs_per_agent_page: normalizeInt(options.maxLogsPerAgentPage ?? 14, 1, 60)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentCapabilityMatrix(options: {
    minConfidence?: number;
    maxAgents?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/capability-matrix", {
      method: "GET",
      params: {
        project_id: this.projectId,
        min_confidence: clamp(options.minConfidence ?? 0, 0, 1),
        max_agents: normalizeInt(options.maxAgents ?? 500, 1, 5000)
      }
    });
  }

  async syncAgentCapabilityMatrix(options: {
    generatedBy: string;
    minConfidence?: number;
    maxAgents?: number;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/capability-matrix/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        generated_by: options.generatedBy,
        min_confidence: clamp(options.minConfidence ?? 0, 0, 1),
        max_agents: normalizeInt(options.maxAgents ?? 500, 1, 5000)
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentHandoffs(options: {
    maxEdges?: number;
    includeRetired?: boolean;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/handoffs", {
      method: "GET",
      params: {
        project_id: this.projectId,
        max_edges: normalizeInt(options.maxEdges ?? 1000, 1, 10000),
        include_retired: options.includeRetired ?? false
      }
    });
  }

  async syncAgentHandoffs(options: {
    generatedBy: string;
    maxEdges?: number;
    includeRetired?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/handoffs/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        generated_by: options.generatedBy,
        max_edges: normalizeInt(options.maxEdges ?? 1000, 1, 10000),
        include_retired: options.includeRetired ?? false
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async getAgentScorecards(options: {
    maxAgents?: number;
    lookbackDays?: number;
    includeRetired?: boolean;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/scorecards", {
      method: "GET",
      params: {
        project_id: this.projectId,
        max_agents: normalizeInt(options.maxAgents ?? 500, 1, 5000),
        lookback_days: normalizeInt(options.lookbackDays ?? 14, 1, 90),
        include_retired: options.includeRetired ?? false
      }
    });
  }

  async syncAgentScorecards(options: {
    generatedBy: string;
    maxAgents?: number;
    lookbackDays?: number;
    includeRetired?: boolean;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/scorecards/sync", {
      method: "POST",
      payload: {
        project_id: this.projectId,
        generated_by: options.generatedBy,
        max_agents: normalizeInt(options.maxAgents ?? 500, 1, 5000),
        lookback_days: normalizeInt(options.lookbackDays ?? 14, 1, 90),
        include_retired: options.includeRetired ?? false
      },
      idempotencyKey: options.idempotencyKey ?? makeUuid()
    });
  }

  async listAgentProvenance(options: {
    agentId?: string;
    pageSlug?: string;
    limit?: number;
  } = {}): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("/v1/agents/provenance", {
      method: "GET",
      params: {
        project_id: this.projectId,
        agent_id: options.agentId,
        page_slug: options.pageSlug,
        limit: normalizeInt(options.limit ?? 100, 1, 500)
      }
    });
  }

  async rollbackAgentActivity(options: {
    activityId: string;
    rolledBackBy: string;
    requireLatestActivity?: boolean;
    status?: "draft" | "reviewed" | "published" | "archived";
    changeSummary?: string;
    idempotencyKey?: string;
  }): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(
      `/v1/agents/provenance/${encodeURIComponent(options.activityId)}/rollback`,
      {
        method: "POST",
        payload: {
          project_id: this.projectId,
          rolled_back_by: options.rolledBackBy,
          require_latest_activity: options.requireLatestActivity ?? true,
          status: options.status ?? null,
          change_summary: options.changeSummary ?? null
        },
        idempotencyKey: options.idempotencyKey ?? makeUuid()
      }
    );
  }

  monitor<T extends object>(target: T, options: MonitorOptions = {}): T {
    const integration = options.integration ?? "generic";
    const includeMethods = new Set(options.includeMethods ?? defaultMethodsForIntegration(integration));
    const captureArguments = options.captureArguments ?? true;
    const captureResults = options.captureResults ?? true;
    const captureStreamItems = options.captureStreamItems ?? true;
    const maxStreamItems = options.maxStreamItems ?? 25;
    const flushOnSuccess = options.flushOnSuccess ?? false;
    const flushOnError = options.flushOnError ?? true;
    const agentId = options.agentId;

    return new Proxy(target, {
      get: (obj, prop, receiver) => {
        const value = Reflect.get(obj, prop, receiver);
        if (typeof prop !== "string" || typeof value !== "function" || !includeMethods.has(prop)) {
          return value;
        }

        return (...args: unknown[]) => {
          const parentContext = this.currentTraceContext();
          const callId = makeId();
          const sessionId = options.sessionId ?? callId;
          const traceContext: TraceContext = {
            traceId: parentContext?.traceId ?? makeUuid(),
            spanId: callId,
            parentSpanId: parentContext?.spanId
          };

          return this.withTraceContext(traceContext, () => {
            this.captureMonitorEvent({
              event_type: "system_signal",
              payload: {
                integration,
                phase: "call_started",
                method: prop,
                call_id: callId,
                args: captureArguments ? safeSerialize(args) : undefined
              },
              agent_id: agentId,
              session_id: sessionId,
              tags: [`integration:${integration}`]
            });

            try {
              const result = value.apply(obj, args);
              if (isPromiseLike(result)) {
                return result
                  .then((resolved) => this.handleMonitorSuccess({
                    integration,
                    method: prop,
                    callId,
                    sessionId,
                    result: resolved,
                    captureResults,
                    captureStreamItems,
                    maxStreamItems,
                    flushOnSuccess,
                    agentId,
                    traceContext
                  }))
                  .catch((error) => {
                    this.handleMonitorError({
                      integration,
                      method: prop,
                      callId,
                      sessionId,
                      error,
                      flushOnError,
                      agentId,
                      traceContext
                    });
                    throw error;
                  });
              }
              return this.handleMonitorSuccess({
                integration,
                method: prop,
                callId,
                sessionId,
                result,
                captureResults,
                captureStreamItems,
                maxStreamItems,
                flushOnSuccess,
                agentId,
                traceContext
              });
            } catch (error) {
              this.handleMonitorError({
                integration,
                method: prop,
                callId,
                sessionId,
                error,
                flushOnError,
                agentId,
                traceContext
              });
              throw error;
            }
          });
        };
      }
    });
  }

  registerExtractor(extractor: InsightExtractor, options: { replace?: boolean } = {}): void {
    const replace = options.replace ?? true;
    if (!replace && this.extractors.has(extractor.name)) {
      throw new Error(`extractor already registered: ${extractor.name}`);
    }
    this.extractors.set(extractor.name, extractor);
    this.emitDebug("extractor_registered", { name: extractor.name, replace });
  }

  unregisterExtractor(name: string): boolean {
    const removed = this.extractors.delete(name);
    this.emitDebug("extractor_unregistered", { name, removed });
    return removed;
  }

  listExtractors(): string[] {
    const names = Array.from(this.extractors.keys()).sort();
    this.emitDebug("extractor_listed", { count: names.length });
    return names;
  }

  registerSynthesizer(synthesizer: InsightSynthesizer, options: { replace?: boolean } = {}): void {
    const replace = options.replace ?? true;
    if (!replace && this.synthesizers.has(synthesizer.name)) {
      throw new Error(`synthesizer already registered: ${synthesizer.name}`);
    }
    this.synthesizers.set(synthesizer.name, synthesizer);
    this.emitDebug("synthesizer_registered", {
      name: synthesizer.name,
      replace,
      contract_version: synthesizer.contractVersion ?? "v1"
    });
  }

  unregisterSynthesizer(name: string): boolean {
    const removed = this.synthesizers.delete(name);
    this.emitDebug("synthesizer_unregistered", { name, removed });
    return removed;
  }

  listSynthesizers(): string[] {
    const names = Array.from(this.synthesizers.keys()).sort();
    this.emitDebug("synthesizer_listed", { count: names.length });
    return names;
  }

  collectInsight<T extends (...args: any[]) => any>(fn: T, options: CollectInsightOptions = {}): T {
    const integration = options.integration ?? "collect_insight";
    const minConfidence = clamp(options.minConfidence ?? 0, 0, 1);
    const self = this;
    const functionName = fn.name || "anonymous";

    const wrapped = function (this: unknown, ...args: unknown[]) {
      const parent = self.currentTraceContext();
      const callId = makeUuid();
      const traceContext: TraceContext = {
        traceId: parent?.traceId ?? makeUuid(),
        spanId: callId,
        parentSpanId: parent?.spanId
      };
      const sessionId = options.sessionId ?? callId;
      const sourceId = `${functionName}:${callId}`;
      const entityKey = options.entityKey ?? inferEntityKey(args, functionName);

      return self.withTraceContext(traceContext, () => {
        self.emitDebug("collect_insight_started", {
          function: functionName,
          integration,
          source_id: sourceId
        }, traceContext);
        self.capture({
          event_type: "system_signal",
          payload: {
            integration,
            phase: "collect_insight_started",
            function: functionName,
            source_id: sourceId
          },
          agent_id: options.agentId,
          session_id: sessionId,
          tags: [`integration:${integration}`, "collect_insight"]
        });
        try {
          const result = fn.apply(this, args);
          if (isPromiseLike(result)) {
            return result
              .then((resolved) => {
                void self
                  .proposeInsightsFromResult({
                    functionName,
                    integration,
                    result: resolved,
                    args,
                    category: options.category,
                    entityKey,
                    sourceType: options.sourceType ?? "tool_output",
                    sourceId,
                    agentId: options.agentId,
                    sessionId,
                    extractorNames: options.extractorNames,
                    synthesizerNames: options.synthesizerNames,
                    minConfidence,
                    traceContext
                  })
                  .catch((error) => {
                    self.emitDebug("collect_insight_failed", {
                      function: functionName,
                      integration,
                      error_type: error instanceof Error ? error.name : "Error",
                      error_message: error instanceof Error ? error.message : String(error)
                    }, traceContext);
                    self.capture({
                      event_type: "system_signal",
                      payload: {
                        integration,
                        phase: "collect_insight_failed",
                        function: functionName,
                        error_type: error instanceof Error ? error.name : "Error",
                        error_message: error instanceof Error ? error.message : String(error)
                      },
                      agent_id: options.agentId,
                      session_id: sessionId,
                      tags: [`integration:${integration}`, "collect_insight"]
                    });
                  });
                return resolved;
              })
              .catch((error) => {
                self.emitDebug("collect_insight_failed", {
                  function: functionName,
                  integration,
                  error_type: error instanceof Error ? error.name : "Error",
                  error_message: error instanceof Error ? error.message : String(error)
                }, traceContext);
                self.capture({
                  event_type: "system_signal",
                  payload: {
                    integration,
                    phase: "collect_insight_failed",
                    function: functionName,
                    error_type: error instanceof Error ? error.name : "Error",
                    error_message: error instanceof Error ? error.message : String(error)
                  },
                  agent_id: options.agentId,
                  session_id: sessionId,
                  tags: [`integration:${integration}`, "collect_insight"]
                });
                throw error;
              });
          }
          void self
            .proposeInsightsFromResult({
              functionName,
              integration,
              result,
              args,
              category: options.category,
              entityKey,
              sourceType: options.sourceType ?? "tool_output",
              sourceId,
              agentId: options.agentId,
              sessionId,
              extractorNames: options.extractorNames,
              synthesizerNames: options.synthesizerNames,
              minConfidence,
              traceContext
            })
            .catch((error) => {
              self.emitDebug("collect_insight_failed", {
                function: functionName,
                integration,
                error_type: error instanceof Error ? error.name : "Error",
                error_message: error instanceof Error ? error.message : String(error)
              }, traceContext);
              self.capture({
                event_type: "system_signal",
                payload: {
                  integration,
                  phase: "collect_insight_failed",
                  function: functionName,
                  error_type: error instanceof Error ? error.name : "Error",
                  error_message: error instanceof Error ? error.message : String(error)
                },
                agent_id: options.agentId,
                session_id: sessionId,
                tags: [`integration:${integration}`, "collect_insight"]
              });
            });
          return result;
        } catch (error) {
          self.emitDebug("collect_insight_failed", {
            function: functionName,
            integration,
            error_type: error instanceof Error ? error.name : "Error",
            error_message: error instanceof Error ? error.message : String(error)
          }, traceContext);
          self.capture({
            event_type: "system_signal",
            payload: {
              integration,
              phase: "collect_insight_failed",
              function: functionName,
              error_type: error instanceof Error ? error.name : "Error",
              error_message: error instanceof Error ? error.message : String(error)
            },
            agent_id: options.agentId,
            session_id: sessionId,
            tags: [`integration:${integration}`, "collect_insight"]
          });
          throw error;
        }
      });
    };

    return wrapped as T;
  }

  private handleMonitorSuccess(input: {
    integration: string;
    method: string;
    callId: string;
    sessionId: string;
    result: unknown;
    captureResults: boolean;
    captureStreamItems: boolean;
    maxStreamItems: number;
    flushOnSuccess: boolean;
    agentId?: string;
    traceContext: TraceContext;
  }): unknown {
    const { integration, method, callId, sessionId, result, captureResults, captureStreamItems, maxStreamItems, flushOnSuccess, agentId, traceContext } = input;
    if (isAsyncIteratorLike(result)) {
      return this.wrapAsyncIterator({
        integration,
        method,
        callId,
        sessionId,
        iterator: result,
        captureStreamItems,
        maxStreamItems,
        flushOnSuccess,
        agentId,
        traceContext
      });
    }
    if (isIteratorLike(result)) {
      return this.wrapIterator({
        integration,
        method,
        callId,
        sessionId,
        iterator: result,
        captureStreamItems,
        maxStreamItems,
        flushOnSuccess,
        agentId,
        traceContext
      });
    }

    this.withTraceContext(traceContext, () => {
      this.captureMonitorEvent({
        event_type: "tool_result",
        payload: {
          integration,
          phase: "call_succeeded",
          method,
          call_id: callId,
          result: captureResults ? safeSerialize(result) : undefined
        },
        agent_id: agentId,
        session_id: sessionId,
        tags: [`integration:${integration}`]
      });
      if (flushOnSuccess) {
        void this.flush().catch(() => undefined);
      }
    });
    return result;
  }

  private handleMonitorError(input: {
    integration: string;
    method: string;
    callId: string;
    sessionId: string;
    error: unknown;
    flushOnError: boolean;
    agentId?: string;
    traceContext: TraceContext;
  }): void {
    const { integration, method, callId, sessionId, error, flushOnError, agentId, traceContext } = input;
    this.withTraceContext(traceContext, () => {
      const message = error instanceof Error ? error.message : String(error);
      const errorType = error instanceof Error ? error.name : "Error";
      this.captureMonitorEvent({
        event_type: "system_signal",
        payload: {
          integration,
          phase: "call_failed",
          method,
          call_id: callId,
          error_type: errorType,
          error_message: message
        },
        agent_id: agentId,
        session_id: sessionId,
        tags: [`integration:${integration}`]
      });
      if (flushOnError) {
        void this.flush().catch(() => undefined);
      }
    });
  }

  private async proposeInsightsFromResult(input: {
    functionName: string;
    integration: string;
    result: unknown;
    args: unknown[];
    category?: string;
    entityKey: string;
    sourceType: "dialog" | "tool_output" | "file" | "human_note" | "external_event";
    sourceId: string;
    agentId?: string;
    sessionId: string;
    extractorNames?: string[];
    synthesizerNames?: string[];
    minConfidence: number;
    traceContext: TraceContext;
  }): Promise<void> {
    const {
      functionName,
      integration,
      result,
      args,
      category,
      entityKey,
      sourceType,
      sourceId,
      agentId,
      sessionId,
      extractorNames,
      synthesizerNames,
      minConfidence,
      traceContext
    } = input;

    const context: InsightContext = {
      functionName,
      integration,
      args,
      result,
      categoryHint: category,
      entityHint: entityKey,
      traceId: traceContext.traceId,
      spanId: traceContext.spanId,
      parentSpanId: traceContext.parentSpanId,
      sourceId
    };

    const extracted = await this.runExtractors(context, extractorNames);
    const synthesized = await this.runSynthesizers(context, extracted, synthesizerNames);
    const dedup = new Set<string>();
    let proposedCount = 0;
    let skippedLowConfidence = 0;
    let skippedDuplicate = 0;
    let skippedEmpty = 0;
    this.emitDebug("collect_insight_extracted", {
      function: functionName,
      integration,
      extracted_count: extracted.length,
      extractor_names: extractorNames?.length ? extractorNames : Array.from(this.extractors.keys())
    }, traceContext);
    this.emitDebug("collect_insight_synthesized", {
      function: functionName,
      integration,
      input_count: extracted.length,
      output_count: synthesized.length,
      synthesizer_names: synthesizerNames?.length ? synthesizerNames : Array.from(this.synthesizers.keys())
    }, traceContext);
    for (const item of synthesized) {
      const claimText = (item.claim_text || "").trim();
      if (!claimText) {
        skippedEmpty += 1;
        this.emitDebug("collect_insight_skipped_empty_claim", {
          function: functionName,
          integration,
          extractor: item.metadata?.extractor
        }, traceContext);
        continue;
      }
      const confidence = clamp(item.confidence ?? 0.65, 0, 1);
      if (confidence < minConfidence) {
        skippedLowConfidence += 1;
        this.emitDebug("collect_insight_skipped_low_confidence", {
          function: functionName,
          integration,
          extractor: item.metadata?.extractor,
          confidence,
          min_confidence: minConfidence
        }, traceContext);
        continue;
      }
      const resolvedCategory = (item.category || category || "general").trim() || "general";
      const resolvedEntity = (item.entity_key || entityKey || "unknown_entity").trim() || "unknown_entity";
      const dedupKey = `${resolvedEntity.toLowerCase()}|${resolvedCategory.toLowerCase()}|${claimText.toLowerCase()}`;
      if (dedup.has(dedupKey)) {
        skippedDuplicate += 1;
        this.emitDebug("collect_insight_skipped_duplicate", {
          function: functionName,
          integration,
          extractor: item.metadata?.extractor,
          entity_key: resolvedEntity,
          category: resolvedCategory
        }, traceContext);
        continue;
      }
      dedup.add(dedupKey);

      const claimId = makeUuid();
      const metadata: Record<string, unknown> = {
        integration,
        function: functionName,
        source_id: sourceId,
        trace_id: traceContext.traceId,
        span_id: traceContext.spanId,
        parent_span_id: traceContext.parentSpanId,
        ...(item.metadata ?? {})
      };
      await this.proposeFact({
        id: claimId,
        entity_key: resolvedEntity,
        category: resolvedCategory,
        claim_text: claimText,
        status: "draft",
        confidence,
        valid_from: item.valid_from,
        valid_to: item.valid_to,
        metadata,
        evidence: [
          {
            source_type: sourceType,
            source_id: sourceId,
            session_id: sessionId,
            tool_name: functionName,
            snippet: claimText.slice(0, 280),
            observed_at: new Date().toISOString()
          }
        ]
      });
      this.withTraceContext(traceContext, () => {
        this.capture({
          event_type: "fact_proposed",
          payload: {
            integration,
            phase: "collect_insight_proposed",
            function: functionName,
            claim_id: claimId,
            category: resolvedCategory,
            entity_key: resolvedEntity,
            confidence,
            source_id: sourceId,
            extractor: item.metadata?.extractor
          },
          agent_id: agentId,
          session_id: sessionId,
          tags: [`integration:${integration}`, "collect_insight"]
        });
      });
      proposedCount += 1;
      this.emitDebug("collect_insight_proposed", {
        function: functionName,
        integration,
        claim_id: claimId,
        extractor: item.metadata?.extractor,
        entity_key: resolvedEntity,
        category: resolvedCategory,
        confidence
      }, traceContext);
    }
    this.emitDebug("collect_insight_completed", {
      function: functionName,
      integration,
      proposed_count: proposedCount,
      skipped_low_confidence: skippedLowConfidence,
      skipped_duplicate: skippedDuplicate,
      skipped_empty: skippedEmpty
    }, traceContext);
  }

  private async runExtractors(context: InsightContext, extractorNames?: string[]): Promise<ExtractedInsight[]> {
    const selected: InsightExtractor[] = [];
    if (extractorNames?.length) {
      for (const name of extractorNames) {
        const extractor = this.extractors.get(name);
        if (!extractor) {
          throw new Error(`unknown extractor: ${name}`);
        }
        selected.push(extractor);
      }
    } else {
      selected.push(...this.extractors.values());
    }
    const out: ExtractedInsight[] = [];
    for (const extractor of selected) {
      this.emitDebug("extractor_started", {
        extractor: extractor.name,
        integration: context.integration,
        function: context.functionName
      }, {
        traceId: context.traceId,
        spanId: context.spanId,
        parentSpanId: context.parentSpanId
      });
      let extracted: ExtractedInsight[] = [];
      try {
        extracted = await extractor.extract(context);
      } catch (error) {
        this.emitDebug("extractor_failed", {
          extractor: extractor.name,
          integration: context.integration,
          function: context.functionName,
          error_type: error instanceof Error ? error.name : "Error",
          error_message: error instanceof Error ? error.message : String(error)
        }, {
          traceId: context.traceId,
          spanId: context.spanId,
          parentSpanId: context.parentSpanId
        });
        continue;
      }
      this.emitDebug("extractor_completed", {
        extractor: extractor.name,
        integration: context.integration,
        function: context.functionName,
        produced_count: extracted.length
      }, {
        traceId: context.traceId,
        spanId: context.spanId,
        parentSpanId: context.parentSpanId
      });
      for (const item of extracted) {
        out.push({
          ...item,
          metadata: {
            extractor: extractor.name,
            ...(item.metadata ?? {})
          }
        });
      }
    }
    return out;
  }

  private async runSynthesizers(
    context: InsightContext,
    extracted: ExtractedInsight[],
    synthesizerNames?: string[]
  ): Promise<ExtractedInsight[]> {
    const selected: InsightSynthesizer[] = [];
    if (synthesizerNames?.length) {
      for (const name of synthesizerNames) {
        const synthesizer = this.synthesizers.get(name);
        if (!synthesizer) {
          throw new Error(`unknown synthesizer: ${name}`);
        }
        selected.push(synthesizer);
      }
    } else {
      selected.push(...this.synthesizers.values());
    }

    let current = extracted.slice();
    for (const synthesizer of selected) {
      this.emitDebug("synthesizer_started", {
        synthesizer: synthesizer.name,
        contract_version: synthesizer.contractVersion ?? "v1",
        integration: context.integration,
        function: context.functionName,
        input_count: current.length
      }, {
        traceId: context.traceId,
        spanId: context.spanId,
        parentSpanId: context.parentSpanId
      });
      let synthesized: ExtractedInsight[] = [];
      try {
        synthesized = await synthesizer.synthesize({
          functionName: context.functionName,
          integration: context.integration,
          extractedInsights: current.slice(),
          args: context.args,
          result: context.result,
          categoryHint: context.categoryHint,
          entityHint: context.entityHint,
          traceId: context.traceId,
          spanId: context.spanId,
          parentSpanId: context.parentSpanId,
          sourceId: context.sourceId
        });
      } catch (error) {
        this.emitDebug("synthesizer_failed", {
          synthesizer: synthesizer.name,
          integration: context.integration,
          function: context.functionName,
          error_type: error instanceof Error ? error.name : "Error",
          error_message: error instanceof Error ? error.message : String(error)
        }, {
          traceId: context.traceId,
          spanId: context.spanId,
          parentSpanId: context.parentSpanId
        });
        this.capture({
          event_type: "system_signal",
          payload: {
            integration: context.integration,
            phase: "synthesizer_failed",
            synthesizer: synthesizer.name,
            error_type: error instanceof Error ? error.name : "Error",
            error_message: error instanceof Error ? error.message : String(error)
          },
          session_id: context.sourceId || makeUuid(),
          tags: [`integration:${context.integration}`, "collect_insight", "synthesizer_failed"]
        });
        continue;
      }
      current = synthesized.map((item) => ({
        ...item,
        metadata: {
          synthesizer: synthesizer.name,
          ...(item.metadata ?? {})
        }
      }));
      this.emitDebug("synthesizer_completed", {
        synthesizer: synthesizer.name,
        integration: context.integration,
        function: context.functionName,
        output_count: current.length
      }, {
        traceId: context.traceId,
        spanId: context.spanId,
        parentSpanId: context.parentSpanId
      });
    }
    return current;
  }

  private wrapIterator(input: {
    integration: string;
    method: string;
    callId: string;
    sessionId: string;
    iterator: Iterator<unknown>;
    captureStreamItems: boolean;
    maxStreamItems: number;
    flushOnSuccess: boolean;
    agentId?: string;
    traceContext: TraceContext;
  }): Iterator<unknown> {
    const { integration, method, callId, sessionId, iterator, captureStreamItems, maxStreamItems, flushOnSuccess, agentId, traceContext } = input;
    const self = this;

    function* wrapped(): Generator<unknown, void, unknown> {
      let index = 0;
      while (true) {
        const next = self.withTraceContext(traceContext, () => iterator.next());
        if (next.done) {
          self.withTraceContext(traceContext, () => {
            self.captureMonitorEvent({
              event_type: "system_signal",
              payload: {
                integration,
                phase: "stream_completed",
                method,
                call_id: callId,
                emitted_items: index
              },
              agent_id: agentId,
              session_id: sessionId,
              tags: [`integration:${integration}`]
            });
            if (flushOnSuccess) {
              void self.flush().catch(() => undefined);
            }
          });
          return;
        }
        if (captureStreamItems && index < maxStreamItems) {
          self.withTraceContext(traceContext, () => {
            self.captureMonitorEvent({
              event_type: "tool_result",
              payload: {
                integration,
                phase: "stream_item",
                method,
                call_id: callId,
                index,
                item: safeSerialize(next.value)
              },
              agent_id: agentId,
              session_id: sessionId,
              tags: [`integration:${integration}`]
            });
          });
        }
        index += 1;
        yield next.value;
      }
    }

    return wrapped();
  }

  private wrapAsyncIterator(input: {
    integration: string;
    method: string;
    callId: string;
    sessionId: string;
    iterator: AsyncIterator<unknown>;
    captureStreamItems: boolean;
    maxStreamItems: number;
    flushOnSuccess: boolean;
    agentId?: string;
    traceContext: TraceContext;
  }): AsyncIterator<unknown> {
    const { integration, method, callId, sessionId, iterator, captureStreamItems, maxStreamItems, flushOnSuccess, agentId, traceContext } = input;
    const self = this;

    async function* wrapped(): AsyncGenerator<unknown, void, unknown> {
      let index = 0;
      while (true) {
        const next = await self.withTraceContext(traceContext, () => iterator.next());
        if (next.done) {
          self.withTraceContext(traceContext, () => {
            self.captureMonitorEvent({
              event_type: "system_signal",
              payload: {
                integration,
                phase: "stream_completed",
                method,
                call_id: callId,
                emitted_items: index
              },
              agent_id: agentId,
              session_id: sessionId,
              tags: [`integration:${integration}`]
            });
            if (flushOnSuccess) {
              void self.flush().catch(() => undefined);
            }
          });
          return;
        }
        if (captureStreamItems && index < maxStreamItems) {
          self.withTraceContext(traceContext, () => {
            self.captureMonitorEvent({
              event_type: "tool_result",
              payload: {
                integration,
                phase: "stream_item",
                method,
                call_id: callId,
                index,
                item: safeSerialize(next.value)
              },
              agent_id: agentId,
              session_id: sessionId,
              tags: [`integration:${integration}`]
            });
          });
        }
        index += 1;
        yield next.value;
      }
    }

    return wrapped();
  }

  private async flushInternal(): Promise<void> {
    await this.flushPendingBackfill();
    await this.flushPendingClaims();

    if (!this.queue.length) {
      this.emitDebug("flush_skipped_empty", {});
      return;
    }
    const batch = this.queue.splice(0, this.queue.length);
    this.emitDebug("flush_start", { batch_size: batch.length });
    try {
      await this.transport.sendEvents(batch, {
        idempotencyKey: makeBatchIdempotencyKey(batch)
      });
      this.emitDebug("flush_success", { batch_size: batch.length });
    } catch (error) {
      const errorType = error instanceof Error ? error.name : "Error";
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (this.degradationMode === "drop") {
        this.emitDebug("flush_failed_dropped", {
          batch_size: batch.length,
          error_type: errorType,
          error_message: errorMessage
        });
        return;
      }
      this.queue.unshift(...batch);
      this.emitDebug("flush_failed_requeued", {
        batch_size: batch.length,
        error_type: errorType,
        error_message: errorMessage
      });
      return;
    }
  }

  private async flushPendingBackfill(): Promise<void> {
    if (!this.pendingBackfill.length) {
      return;
    }
    const pending = this.pendingBackfill.splice(0, this.pendingBackfill.length);
    this.emitDebug("flush_pending_backfill_start", { count: pending.length });
    for (let index = 0; index < pending.length; index += 1) {
      const item = pending[index];
      const ingestLane = this.resolveBackfillIngestLaneFromPayload(item.payload);
      try {
        await this.transportIngestBackfill(item.payload, ingestLane, { idempotencyKey: item.idempotencyKey });
      } catch (error) {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (this.degradationMode === "drop") {
          this.emitDebug("flush_pending_backfill_dropped", {
            ingest_lane: ingestLane,
            error_type: errorType,
            error_message: errorMessage
          });
          continue;
        }
        const rest = pending.slice(index);
        this.pendingBackfill.unshift(...rest);
        this.emitDebug("flush_pending_backfill_requeued", {
          ingest_lane: ingestLane,
          error_type: errorType,
          error_message: errorMessage,
          pending_backfill: this.pendingBackfill.length
        });
        return;
      }
    }
    this.emitDebug("flush_pending_backfill_success", { count: pending.length });
  }

  private resolveBackfillIngestLaneFromPayload(payload: Record<string, unknown>): "event" | "knowledge" {
    const batch = payload.batch;
    if (!isPlainObject(batch)) {
      return "event";
    }
    const lane = String(batch.ingest_lane ?? "").trim().toLowerCase();
    if (lane === "knowledge") {
      return "knowledge";
    }
    return "event";
  }

  private async transportIngestBackfill(
    payload: Record<string, unknown>,
    ingestLane: "event" | "knowledge",
    options?: RequestOptions
  ): Promise<void> {
    if (ingestLane === "knowledge" && typeof this.transport.ingestKnowledgeBackfill === "function") {
      try {
        await this.transport.ingestKnowledgeBackfill(payload, options);
        return;
      } catch (error) {
        const statusCode = this.transportErrorStatusCode(error);
        if (statusCode !== 404 && statusCode !== 405) {
          throw error;
        }
        this.emitDebug("backfill_knowledge_endpoint_fallback", {
          status_code: statusCode,
          fallback_endpoint: "/v1/backfill/memory"
        });
      }
    }
    await this.transport.ingestMemoryBackfill(payload, options);
  }

  private transportErrorStatusCode(error: unknown): number | null {
    if (error == null || (typeof error !== "object" && typeof error !== "function")) {
      return null;
    }
    const maybeStatusCode = (error as { statusCode?: unknown; status_code?: unknown }).statusCode;
    const maybeSnakeStatusCode = (error as { statusCode?: unknown; status_code?: unknown }).status_code;
    const value = maybeStatusCode ?? maybeSnakeStatusCode;
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.trunc(value);
    }
    return null;
  }

  private async flushPendingClaims(): Promise<void> {
    if (!this.pendingClaims.length) {
      return;
    }
    const pending = this.pendingClaims.splice(0, this.pendingClaims.length);
    this.emitDebug("flush_pending_claims_start", { count: pending.length });
    for (let index = 0; index < pending.length; index += 1) {
      const claim = pending[index];
      try {
        await this.transport.proposeFact(claim, { idempotencyKey: makeClaimIdempotencyKey(claim.id) });
      } catch (error) {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (this.degradationMode === "drop") {
          this.emitDebug("flush_pending_claim_dropped", {
            claim_id: claim.id,
            error_type: errorType,
            error_message: errorMessage
          });
          continue;
        }
        const rest = pending.slice(index);
        this.pendingClaims.unshift(...rest);
        this.emitDebug("flush_pending_claim_requeued", {
          claim_id: claim.id,
          error_type: errorType,
          error_message: errorMessage,
          pending_claims: this.pendingClaims.length
        });
        return;
      }
    }
    this.emitDebug("flush_pending_claims_success", { count: pending.length });
  }

  private captureMonitorEvent(event: Omit<ObservationEvent, "id" | "schema_version" | "project_id" | "observed_at"> & { observed_at?: string }): void {
    this.capture({
      ...event,
      observed_at: event.observed_at ?? new Date().toISOString()
    });
  }

  private currentTraceContext(): TraceContext | undefined {
    return this.traceStorage.getStore();
  }

  private withTraceContext<T>(context: TraceContext, fn: () => T): T {
    return this.traceStorage.run(context, fn);
  }

  private payloadWithTrace(
    payload: Record<string, unknown>,
    trace: { traceId?: string; spanId?: string; parentSpanId?: string }
  ): Record<string, unknown> {
    const { traceId, spanId, parentSpanId } = trace;
    if (!traceId && !spanId && !parentSpanId) {
      return { ...payload };
    }
    const out: Record<string, unknown> = { ...payload };
    const synapseMeta =
      out._synapse && typeof out._synapse === "object" && !Array.isArray(out._synapse)
        ? { ...(out._synapse as Record<string, unknown>) }
        : {};
    if (traceId) {
      synapseMeta.trace_id = traceId;
    }
    if (spanId) {
      synapseMeta.span_id = spanId;
    }
    if (parentSpanId) {
      synapseMeta.parent_span_id = parentSpanId;
    }
    out._synapse = synapseMeta;
    return out;
  }

  private async requestJson<T = Record<string, unknown>>(
    path: string,
    options: {
      method?: "GET" | "POST" | "PUT";
      payload?: unknown;
      params?: Record<string, string | number | boolean | null | undefined>;
      idempotencyKey?: string;
    } = {}
  ): Promise<T> {
    const maybeTransport = this.transport as { requestJson?: unknown };
    if (typeof maybeTransport.requestJson !== "function") {
      throw new Error("Task API helpers require HttpTransport-compatible transport with requestJson.");
    }
    return maybeTransport.requestJson(path, options) as Promise<T>;
  }

  protected emitDebug(
    event: string,
    details: Record<string, unknown>,
    trace?: { traceId?: string; spanId?: string; parentSpanId?: string }
  ): void {
    if (!this.debugMode && !this.telemetrySink) {
      return;
    }
    const context = trace ?? this.currentTraceContext();
    const record: DebugRecord = {
      ts: new Date().toISOString(),
      event,
      projectId: this.config.projectId,
      traceId: context?.traceId,
      spanId: context?.spanId,
      parentSpanId: context?.parentSpanId,
      details
    };
    if (this.telemetrySink) {
      try {
        this.telemetrySink(record);
      } catch {
        // Swallow telemetry sink errors to keep SDK side effects non-blocking.
      }
    }
    if (!this.debugMode) {
      return;
    }
    this.debugRecords.push(record);
    if (this.debugRecords.length > this.debugMaxRecords) {
      this.debugRecords.splice(0, this.debugRecords.length - this.debugMaxRecords);
    }
    if (this.debugSink) {
      try {
        this.debugSink(record);
      } catch {
        return;
      }
    }
  }
}

export class Synapse extends SynapseClient {
  static fromEnv(
    overrides: Partial<SynapseConfig> = {},
    transport?: SynapseTransport
  ): Synapse {
    const envApiUrl = readProcessEnv("SYNAPSE_API_URL");
    const envProjectId = readProcessEnv("SYNAPSE_PROJECT_ID");
    const envApiKey = readProcessEnv("SYNAPSE_API_KEY");
    const envDegradationMode = readProcessEnv("SYNAPSE_DEGRADATION_MODE");
    const apiUrl = asOptionalString(overrides.apiUrl) ?? envApiUrl ?? "http://localhost:8080";
    const projectId = asOptionalString(overrides.projectId) ?? envProjectId ?? inferProjectIdFromCwd();
    const apiKey = asOptionalString(overrides.apiKey) ?? envApiKey;
    const degradationMode = asOptionalString(overrides.degradationMode) ?? envDegradationMode ?? "buffer";
    return new Synapse(
      {
        ...overrides,
        apiUrl,
        projectId,
        apiKey,
        degradationMode: degradationMode as DegradationMode
      },
      transport
    );
  }

  langchainCallbackHandler(options: LangChainCallbackHandlerOptions = {}): LangChainCallbackHandler {
    const integration = options.integration ?? "langchain";
    const agentId = options.agentId;
    const sessionId = options.sessionId;
    const flushOnSuccess = options.flushOnSuccess ?? false;
    const flushOnError = options.flushOnError ?? true;
    const captureInputs = options.captureInputs ?? true;
    const captureOutputs = options.captureOutputs ?? true;

    const emit = (
      phase: string,
      payload: Record<string, unknown>,
      context: { runId?: string; parentRunId?: string },
      eventType: ObservationEvent["event_type"] = "system_signal"
    ): void => {
      const resolvedSessionId = sessionId ?? context.runId ?? makeId();
      const mergedPayload: Record<string, unknown> = {
        integration,
        phase,
        ...payload
      };
      if (context.runId) {
        mergedPayload.run_id = context.runId;
      }
      if (context.parentRunId) {
        mergedPayload.parent_run_id = context.parentRunId;
      }
      this.capture({
        event_type: eventType,
        payload: safeSerialize(mergedPayload) as Record<string, unknown>,
        agent_id: agentId,
        session_id: resolvedSessionId,
        tags: [`integration:${integration}`, "native_callback"]
      });
    };

    const maybeFlush = (mode: "success" | "error"): void => {
      if ((mode === "success" && flushOnSuccess) || (mode === "error" && flushOnError)) {
        void this.flush().catch(() => undefined);
      }
    };

    const handler: LangChainCallbackHandler = {
      on_chain_start: (serialized, inputs, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "chain_started",
          {
            serialized: captureInputs ? serialized : undefined,
            inputs: captureInputs ? inputs : undefined
          },
          meta
        );
      },
      on_chain_end: (outputs, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "chain_completed",
          { outputs: captureOutputs ? outputs : undefined },
          meta,
          "tool_result"
        );
        maybeFlush("success");
      },
      on_chain_error: (error, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "chain_failed",
          {
            error_type: error instanceof Error ? error.name : "Error",
            error_message: error instanceof Error ? error.message : String(error)
          },
          meta
        );
        maybeFlush("error");
      },
      on_tool_start: (serialized, input, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "tool_started",
          {
            serialized: captureInputs ? serialized : undefined,
            tool_input: captureInputs ? input : undefined
          },
          meta
        );
      },
      on_tool_end: (output, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "tool_completed",
          { tool_output: captureOutputs ? output : undefined },
          meta,
          "tool_result"
        );
      },
      on_tool_error: (error, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "tool_failed",
          {
            error_type: error instanceof Error ? error.name : "Error",
            error_message: error instanceof Error ? error.message : String(error)
          },
          meta
        );
      },
      on_llm_start: (serialized, prompts, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "llm_started",
          {
            serialized: captureInputs ? serialized : undefined,
            prompts: captureInputs ? prompts : undefined
          },
          meta
        );
      },
      on_llm_end: (response, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "llm_completed",
          { response: captureOutputs ? response : undefined },
          meta,
          "tool_result"
        );
      },
      on_llm_error: (error, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "llm_failed",
          {
            error_type: error instanceof Error ? error.name : "Error",
            error_message: error instanceof Error ? error.message : String(error)
          },
          meta
        );
      },
      on_agent_action: (action, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "agent_action",
          { action: captureOutputs ? action : undefined },
          meta,
          "tool_result"
        );
      },
      on_agent_finish: (finish, kwargs = {}) => {
        const meta = normalizeCallbackMeta(kwargs);
        emit(
          "agent_finished",
          { finish: captureOutputs ? finish : undefined },
          meta,
          "tool_result"
        );
      },
      handleChainStart: (serialized, inputs, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_chain_start?.(serialized, inputs, meta);
      },
      handleChainEnd: (outputs, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_chain_end?.(outputs, meta);
      },
      handleChainError: (error, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_chain_error?.(error, meta);
      },
      handleToolStart: (serialized, input, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_tool_start?.(serialized, input, meta);
      },
      handleToolEnd: (output, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_tool_end?.(output, meta);
      },
      handleToolError: (error, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_tool_error?.(error, meta);
      },
      handleLLMStart: (serialized, prompts, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_llm_start?.(serialized, prompts, meta);
      },
      handleLLMEnd: (response, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_llm_end?.(response, meta);
      },
      handleLLMError: (error, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_llm_error?.(error, meta);
      },
      handleAgentAction: (action, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_agent_action?.(action, meta);
      },
      handleAgentEnd: (finish, runId, parentRunId, kwargs = {}) => {
        const meta = mergeCallbackMeta(runId, parentRunId, kwargs);
        handler.on_agent_finish?.(finish, meta);
      }
    };

    return handler;
  }

  buildLangchainConfig(handler: LangChainCallbackHandler): { callbacks: LangChainCallbackHandler[] } {
    return { callbacks: [handler] };
  }

  bindLangchain<T extends object>(target: T, options: BindLangChainOptions = {}): T {
    const handler = options.handler ?? this.langchainCallbackHandler({
      integration: "langchain",
      agentId: options.agentId,
      sessionId: options.sessionId
    });
    const bound = bindLangChainLikeTarget(target, handler);
    if (bound.mode) {
      this.emitDebug("native_framework_bound", {
        framework: "langchain",
        binding_mode: bound.mode,
        target_type: getAttachTargetType(target)
      });
      return bound.target;
    }

    if (options.fallbackMonitor ?? true) {
      this.emitDebug("native_framework_fallback_monitor", {
        framework: "langchain",
        target_type: getAttachTargetType(target)
      });
      return this.monitor(target, {
        integration: "langchain",
        includeMethods: options.monitorIncludeMethods,
        agentId: options.agentId,
        sessionId: options.sessionId
      });
    }

    throw new Error("Unable to bind native LangChain callbacks; no supported callback surface found on target.");
  }

  bindLanggraph<T extends object>(target: T, options: BindLangGraphOptions = {}): T {
    const handler = options.handler ?? this.langchainCallbackHandler({
      integration: "langgraph",
      agentId: options.agentId,
      sessionId: options.sessionId
    });
    const bound = bindLangChainLikeTarget(target, handler);
    if (bound.mode) {
      this.emitDebug("native_framework_bound", {
        framework: "langgraph",
        binding_mode: bound.mode,
        target_type: getAttachTargetType(target)
      });
      return bound.target;
    }

    if (options.fallbackMonitor ?? true) {
      this.emitDebug("native_framework_fallback_monitor", {
        framework: "langgraph",
        target_type: getAttachTargetType(target)
      });
      return this.monitor(target, {
        integration: "langgraph",
        includeMethods: options.monitorIncludeMethods,
        agentId: options.agentId,
        sessionId: options.sessionId
      });
    }

    throw new Error("Unable to bind native LangGraph callbacks; no supported callback surface found on target.");
  }

  bindCrewAi<T extends object>(target: T, options: BindCrewAiOptions = {}): T {
    const eventNames = options.eventNames?.length ? options.eventNames : Array.from(DEFAULT_CREWAI_NATIVE_EVENTS);
    const defaultHandler = (eventName: string, payload: unknown): void => {
      this.capture({
        event_type: "system_signal",
        payload: safeSerialize({
          integration: "crewai",
          phase: "event_bus_signal",
          event_name: eventName,
          payload
        }) as Record<string, unknown>,
        agent_id: options.agentId,
        session_id: options.sessionId ?? makeId(),
        tags: ["integration:crewai", "native_callback"]
      });
    };
    const eventHandler = options.eventHandler ?? defaultHandler;

    let registeredHooks = 0;
    const targets: unknown[] = [target];
    const asRecord = target as unknown as Record<string, unknown>;
    if (asRecord.eventBus != null) {
      targets.push(asRecord.eventBus);
    }
    if (asRecord.event_bus != null) {
      targets.push(asRecord.event_bus);
    }

    for (const name of eventNames) {
      let bound = false;
      for (const item of targets) {
        if (registerNativeEventListener(item, name, (payload: unknown) => eventHandler(name, payload))) {
          bound = true;
          break;
        }
      }
      if (bound) {
        registeredHooks += 1;
      }
    }

    const stepKeys = ["stepCallback", "step_callback"] as const;
    for (const key of stepKeys) {
      if (!Object.prototype.hasOwnProperty.call(asRecord, key) && typeof asRecord[key] !== "function") {
        continue;
      }
      const existing = typeof asRecord[key] === "function" ? (asRecord[key] as (...args: unknown[]) => unknown) : undefined;
      const wrapped = (...args: unknown[]): unknown => {
        this.capture({
          event_type: "system_signal",
          payload: safeSerialize({
            integration: "crewai",
            phase: "step_callback",
            args
          }) as Record<string, unknown>,
          agent_id: options.agentId,
          session_id: options.sessionId ?? makeId(),
          tags: ["integration:crewai", "native_callback"]
        });
        return existing ? existing(...args) : undefined;
      };
      try {
        (asRecord as Record<string, unknown>)[key] = wrapped;
        registeredHooks += 1;
      } catch {
        // ignore immutable runtime objects
      }
      break;
    }

    this.emitDebug("native_framework_bound", {
      framework: "crewai",
      binding_mode: "event_bus_or_callbacks",
      target_type: getAttachTargetType(target),
      registered_hooks: registeredHooks
    });

    if (options.monitorRuntime ?? true) {
      return this.monitor(target, {
        integration: "crewai",
        includeMethods: options.monitorIncludeMethods,
        agentId: options.agentId,
        sessionId: options.sessionId
      });
    }
    return target;
  }

  attach<T extends object>(target: T, options: AttachOptions = {}): T {
    const integration = options.integration ?? detectIntegration(target);
    const optionsWithDefaults = this.applyAttachDefaults(target, integration, options);
    const adoptionMode = normalizeAdoptionMode(
      asOptionalString(optionsWithDefaults.adoptionMode) ?? readProcessEnv("SYNAPSE_ADOPTION_MODE")
    );
    const autoRegisterDefault = normalizeBooleanEnv(readProcessEnv("SYNAPSE_AGENT_DIRECTORY_AUTO_REGISTER")) ?? true;
    const shouldAutoRegisterAgentDirectory = Boolean(
      optionsWithDefaults.agentId
      && (optionsWithDefaults.registerAgentDirectory ?? autoRegisterDefault)
    );
    this.emitDebug("attach_started", {
      integration,
      target_type: getAttachTargetType(target),
      auto_bootstrap_enabled: optionsWithDefaults.openclawAutoBootstrapEnabled,
      openclaw_bootstrap_preset: optionsWithDefaults.openclawBootstrapPreset ?? null,
      adoption_mode: adoptionMode,
      agent_directory_auto_register: shouldAutoRegisterAgentDirectory
    });
    const resolvedBootstrapMemory = this.resolveAttachBootstrapMemory(target, integration, optionsWithDefaults);
    if (adoptionMode === "retrieve_only") {
      this.emitDebug("attach_bootstrap_skipped", {
        integration,
        reason: "adoption_mode_retrieve_only",
        adoption_mode: adoptionMode
      });
    } else {
      this.bootstrapMemoryOnAttach(target, integration, resolvedBootstrapMemory, {
        agentId: optionsWithDefaults.agentId,
        sessionId: optionsWithDefaults.sessionId
      });
    }
    if (shouldAutoRegisterAgentDirectory) {
      this.triggerAgentDirectoryRegistration({
        integration,
        options: optionsWithDefaults
      });
    }
    if (integration === "openclaw" && looksLikeOpenClawRuntime(target)) {
      this.attachOpenClawRuntime(target, optionsWithDefaults, resolvedBootstrapMemory, adoptionMode);
      return target;
    }
    if (adoptionMode === "retrieve_only") {
      this.emitDebug("attach_completed", {
        integration,
        mode: "noop_retrieve_only",
        bootstrap_requested: Boolean(resolvedBootstrapMemory),
        openclaw_bootstrap_preset: optionsWithDefaults.openclawBootstrapPreset ?? null,
        adoption_mode: adoptionMode
      });
      return target;
    }
    const monitored = this.monitor(target, {
      ...optionsWithDefaults,
      integration
    });
    this.emitDebug("attach_completed", {
      integration,
      mode: "monitor",
      bootstrap_requested: Boolean(resolvedBootstrapMemory),
      openclaw_bootstrap_preset: optionsWithDefaults.openclawBootstrapPreset ?? null,
      adoption_mode: adoptionMode
    });
    return monitored;
  }

  private attachOpenClawRuntime(
    target: unknown,
    options: AttachOptions,
    bootstrapMemory: AttachBootstrapMemoryOptions | undefined,
    adoptionMode: AdoptionMode
  ): void {
    if (!looksLikeOpenClawRuntime(target)) {
      return;
    }
    const runtime = target as OpenClawRuntime;
    const captureHookEvents = options.openclawCaptureHookEvents ?? adoptionMode !== "retrieve_only";
    const hookEvents = captureHookEvents && Array.isArray(options.openclawHookEvents) && options.openclawHookEvents.length > 0
      ? options.openclawHookEvents
      : captureHookEvents
        ? Array.from(DEFAULT_OPENCLAW_EVENTS)
        : [];
    const registerTools = options.openclawRegisterTools ?? adoptionMode !== "observe_only";
    const registerSearchTool = options.openclawRegisterSearchTool ?? (adoptionMode === "full_loop" || adoptionMode === "retrieve_only");
    const registerProposeTool = options.openclawRegisterProposeTool ?? (adoptionMode === "full_loop" || adoptionMode === "draft_only");
    const registerTaskTools = options.openclawRegisterTaskTools ?? adoptionMode === "full_loop";
    const toolPrefix = asOptionalString(options.openclawToolPrefix) ?? "synapse";
    if (hookEvents.length > 0) {
      this.attachOpenClawHooks(runtime, hookEvents, {
        agentId: options.agentId,
        sessionId: options.sessionId
      });
    }
    const connector = this.registerOpenClawTools(runtime, {
      registerTools,
      registerSearchTool,
      registerProposeTool,
      registerTaskTools,
      toolPrefix,
      searchKnowledge: options.openclawSearchKnowledge,
      listTasks: options.openclawListTasks,
      updateTaskStatus: options.openclawUpdateTaskStatus,
      defaultAgentId: options.agentId,
      defaultSessionId: options.sessionId
    });
    const searchMode = options.openclawSearchKnowledge
      ? "callback"
      : connector.autoSearchEnabled
        ? "auto"
        : "disabled";
    this.emitDebug("attach_completed", {
      integration: "openclaw",
      mode: "openclaw_connector",
      registered_tools: connector.registeredTools,
      bootstrap_requested: Boolean(bootstrapMemory),
      adoption_mode: adoptionMode,
      capture_hooks: captureHookEvents,
      register_tools: registerTools,
      register_search_tool: registerSearchTool,
      register_propose_tool: registerProposeTool,
      register_task_tools: registerTaskTools,
      search_mode: searchMode
    });
  }

  private triggerAgentDirectoryRegistration(input: {
    integration: string;
    options: AttachOptions;
  }): void {
    const agentId = asOptionalString(input.options.agentId);
    if (!agentId) {
      return;
    }
    const profile: AgentProfileInput = {
      agentId,
      displayName: asOptionalString(input.options.agentProfile?.displayName) ?? asOptionalString(input.options.agentDisplayName),
      team: asOptionalString(input.options.agentProfile?.team) ?? asOptionalString(input.options.agentTeam),
      role: asOptionalString(input.options.agentProfile?.role) ?? asOptionalString(input.options.agentRole),
      status: input.options.agentProfile?.status ?? input.options.agentDirectoryStatus ?? "active",
      responsibilities: normalizeStringList(input.options.agentProfile?.responsibilities ?? input.options.agentResponsibilities),
      tools: normalizeStringList(input.options.agentProfile?.tools ?? input.options.agentTools),
      dataSources: normalizeStringList(input.options.agentProfile?.dataSources ?? input.options.agentDataSources),
      limits: normalizeStringList(input.options.agentProfile?.limits ?? input.options.agentLimits),
      metadata: {
        integration: input.integration,
        attached_via: "synapse_sdk_ts",
        ...(isPlainObject(input.options.agentProfile?.metadata) ? input.options.agentProfile?.metadata : {})
      },
      ensureScaffold: input.options.agentProfile?.ensureScaffold ?? true,
      includeDailyReportStub: input.options.agentProfile?.includeDailyReportStub ?? true,
      lastSeenAt: asOptionalString(input.options.agentProfile?.lastSeenAt) ?? new Date().toISOString()
    };
    void this.registerAgentProfile(profile, {
      updatedBy: agentId
    })
      .then(() => {
        this.emitDebug("attach_agent_directory_registered", {
          integration: input.integration,
          agent_id: agentId,
          status: profile.status ?? "active"
        });
      })
      .catch((error: unknown) => {
        this.emitDebug("attach_agent_directory_register_failed", {
          integration: input.integration,
          agent_id: agentId,
          error_type: error instanceof Error ? error.name : "Error",
          error_message: error instanceof Error ? error.message : String(error)
        });
      });
  }

  private applyAttachDefaults<T extends object>(target: T, integration: string, options: AttachOptions): AttachOptions & {
    openclawAutoBootstrapEnabled: boolean;
  } {
    const explicitPreset = asOptionalString(options.openclawBootstrapPreset);
    const autoBootstrapDisabled = normalizeBooleanEnv(readProcessEnv("SYNAPSE_OPENCLAW_AUTO_BOOTSTRAP")) === false;
    const autoBootstrapEnabled = integration === "openclaw" && looksLikeOpenClawRuntime(target) && !autoBootstrapDisabled;
    if (!explicitPreset && autoBootstrapEnabled && !options.bootstrapMemory) {
      const envPreset = asOptionalString(readProcessEnv("SYNAPSE_OPENCLAW_BOOTSTRAP_PRESET"));
      const resolvedPreset = envPreset ?? "hybrid";
      this.emitDebug("attach_openclaw_bootstrap_auto_enabled", {
        integration,
        preset: resolvedPreset,
        source: envPreset ? "env" : "default"
      });
      return {
        ...options,
        openclawBootstrapPreset: resolvedPreset,
        openclawAutoBootstrapEnabled: true
      };
    }
    return {
      ...options,
      openclawAutoBootstrapEnabled: autoBootstrapEnabled
    };
  }

  private resolveAttachBootstrapMemory(
    target: unknown,
    integration: string,
    options: AttachOptions
  ): AttachBootstrapMemoryOptions | undefined {
    const presetRaw = asOptionalString(options.openclawBootstrapPreset);
    if (!presetRaw) {
      return options.bootstrapMemory;
    }

    if (options.bootstrapMemory) {
      this.emitDebug("attach_openclaw_bootstrap_preset_ignored", {
        integration,
        preset: presetRaw,
        reason: "bootstrapMemory_provided"
      });
      return options.bootstrapMemory;
    }

    if (integration !== "openclaw" || !looksLikeOpenClawRuntime(target)) {
      this.emitDebug("attach_openclaw_bootstrap_preset_skipped", {
        integration,
        preset: presetRaw,
        reason: "target_is_not_openclaw_runtime"
      });
      return options.bootstrapMemory;
    }

    try {
      const built = buildOpenClawBootstrapOptions({
        preset: presetRaw as OpenClawBootstrapPreset,
        maxRecords: options.openclawBootstrapMaxRecords ?? 1000,
        sourceSystem: options.openclawBootstrapSourceSystem,
        createdBy: options.openclawBootstrapCreatedBy ?? "sdk_attach",
        cursor: options.openclawBootstrapCursor,
        chunkSize: options.openclawBootstrapChunkSize ?? 100
      });
      this.emitDebug("attach_openclaw_bootstrap_preset_enabled", {
        integration,
        preset: presetRaw,
        source_system: built.sourceSystem ?? "sdk_attach_bootstrap",
        max_records: built.maxRecords ?? options.openclawBootstrapMaxRecords ?? 1000,
        chunk_size: built.chunkSize ?? options.openclawBootstrapChunkSize ?? 100
      });
      return built;
    } catch (error) {
      const errorType = error instanceof Error ? error.name : "Error";
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.emitDebug("attach_openclaw_bootstrap_preset_failed", {
        integration,
        preset: presetRaw,
        error_type: errorType,
        error_message: errorMessage
      });
      return options.bootstrapMemory;
    }
  }

  private bootstrapMemoryOnAttach(
    target: unknown,
    integration: string,
    bootstrapMemory: AttachBootstrapMemoryOptions | undefined,
    trace: { agentId?: string; sessionId?: string }
  ): void {
    if (!bootstrapMemory) {
      return;
    }
    if (bootstrapMemory.chunkSize != null && bootstrapMemory.chunkSize <= 0) {
      throw new Error("bootstrapMemory.chunkSize must be greater than 0");
    }
    let rawRecords: BootstrapMemoryInput[] | null | undefined;
    if (typeof bootstrapMemory.provider === "function") {
      try {
        rawRecords = bootstrapMemory.provider(target);
      } catch (error) {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.emitDebug("attach_bootstrap_provider_failed", {
          integration,
          error_type: errorType,
          error_message: errorMessage
        });
        return;
      }
    } else if (Array.isArray(bootstrapMemory.records)) {
      rawRecords = bootstrapMemory.records;
    } else {
      this.emitDebug("attach_bootstrap_skipped", {
        integration,
        reason: "missing_records_and_provider"
      });
      return;
    }

    const normalized = this.normalizeAttachBootstrapRecords(rawRecords ?? [], bootstrapMemory.maxRecords ?? 1000);
    if (!normalized.length) {
      this.emitDebug("attach_bootstrap_empty", {
        integration,
        source_system: bootstrapMemory.sourceSystem ?? "sdk_attach_bootstrap"
      });
      return;
    }

    void this
      .backfillMemory(normalized, {
        sourceSystem: bootstrapMemory.sourceSystem ?? "sdk_attach_bootstrap",
        createdBy: bootstrapMemory.createdBy ?? "sdk_attach",
        cursor: bootstrapMemory.cursor,
        chunkSize: bootstrapMemory.chunkSize ?? 100,
        agentId: trace.agentId,
        sessionId: trace.sessionId
      })
      .then((batchId) => {
        this.emitDebug("attach_bootstrap_completed", {
          integration,
          records: normalized.length,
          batch_id: batchId,
          source_system: bootstrapMemory.sourceSystem ?? "sdk_attach_bootstrap"
        });
      })
      .catch((error) => {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.emitDebug("attach_bootstrap_failed", {
          integration,
          records: normalized.length,
          source_system: bootstrapMemory.sourceSystem ?? "sdk_attach_bootstrap",
          error_type: errorType,
          error_message: errorMessage
        });
      });
  }

  private normalizeAttachBootstrapRecords(records: BootstrapMemoryInput[], maxRecords: number): MemoryBackfillRecord[] {
    const limit = clamp(Number.isFinite(maxRecords) ? Math.trunc(maxRecords) : 1000, 1, 10_000);
    const out: MemoryBackfillRecord[] = [];
    const dedupe = new Set<string>();
    for (let index = 0; index < records.length; index += 1) {
      if (out.length >= limit) {
        break;
      }
      const normalized = this.coerceAttachBootstrapRecord(records[index], index);
      if (!normalized) {
        continue;
      }
      const key = `${normalized.source_id}::${normalized.content.trim()}`;
      if (dedupe.has(key)) {
        continue;
      }
      dedupe.add(key);
      out.push(normalized);
    }
    return out;
  }

  private coerceAttachBootstrapRecord(input: BootstrapMemoryInput, index: number): MemoryBackfillRecord | null {
    if (typeof input === "string") {
      const content = input.trim();
      if (!content) {
        return null;
      }
      return {
        source_id: `attach_bootstrap_${index + 1}`,
        content
      };
    }
    if (!isPlainObject(input)) {
      return null;
    }
    const sourceId =
      asOptionalString(input["source_id"]) ??
      asOptionalString(input["id"]) ??
      asOptionalString(input["key"]) ??
      asOptionalString(input["memory_id"]) ??
      `attach_bootstrap_${index + 1}`;
    const content =
      asOptionalString(input["content"]) ??
      asOptionalString(input["text"]) ??
      asOptionalString(input["fact"]) ??
      asOptionalString(input["message"]) ??
      asOptionalString(input["summary"]);
    if (!content) {
      return null;
    }
    const rawTags = Array.isArray(input["tags"]) ? input["tags"] : [];
    const tags = rawTags
      .map((item) => String(item).trim())
      .filter(Boolean);
    return {
      source_id: sourceId,
      content,
      observed_at: asOptionalString(input["observed_at"]) ?? asOptionalString(input["timestamp"]),
      entity_key: asOptionalString(input["entity_key"]) ?? asOptionalString(input["entity"]),
      category: asOptionalString(input["category"]),
      metadata: isPlainObject(input["metadata"]) ? input["metadata"] : {},
      tags
    };
  }

  private attachOpenClawHooks(
    runtime: OpenClawRuntime,
    hookEvents: readonly string[],
    defaults: { agentId?: string; sessionId?: string }
  ): void {
    const register = this.resolveOpenClawHookRegistrar(runtime);
    for (const eventName of hookEvents) {
      register(eventName, (event) => {
        const payload = isPlainObject(event) ? event : {};
        this.capture({
          event_type: "system_signal",
          payload: {
            integration: "openclaw",
            phase: "hook_event",
            event_name: eventName,
            event: preview(payload)
          },
          agent_id: defaults.agentId,
          session_id: defaults.sessionId ?? eventSessionId(payload),
          tags: ["integration:openclaw", `event:${eventName}`]
        });
      });
    }
  }

  private registerOpenClawTools(
    runtime: OpenClawRuntime,
    options: {
      registerTools: boolean;
      registerSearchTool: boolean;
      registerProposeTool: boolean;
      registerTaskTools: boolean;
      toolPrefix: string;
      searchKnowledge?: OpenClawSearchKnowledgeResolver;
      listTasks?: OpenClawListTasksResolver;
      updateTaskStatus?: OpenClawUpdateTaskStatusResolver;
      defaultAgentId?: string;
      defaultSessionId?: string;
    }
  ): { registeredTools: string[]; autoSearchEnabled: boolean } {
    if (!options.registerTools) {
      return { registeredTools: [], autoSearchEnabled: false };
    }
    const registerTool = this.resolveOpenClawToolRegistrar(runtime);
    const registeredTools: string[] = [];
    let autoSearchEnabled = false;

    const resolveSearch = (): OpenClawSearchKnowledgeResolver | undefined => {
      if (!options.registerSearchTool) {
        return undefined;
      }
      if (typeof options.searchKnowledge === "function") {
        return options.searchKnowledge;
      }
      autoSearchEnabled = true;
      this.emitDebug("attach_openclaw_search_auto_enabled", {
        mode: "sdk_search_knowledge_api"
      });
      return (query, limit, filters) =>
        this.searchKnowledge(query, {
          limit,
          relatedEntityKey: asOptionalString(filters?.entity_key)
        });
    };
    const searchResolver = resolveSearch();
    if (searchResolver) {
      const searchToolName = `${options.toolPrefix}_search_wiki`;
      registerTool(
        searchToolName,
        async (...args: unknown[]) => {
          const normalized = this.normalizeOpenClawSearchArgs(args);
          const rows = await Promise.resolve(
            searchResolver(normalized.query, normalized.limit, normalized.filters)
          );
          this.capture({
            event_type: "tool_result",
            payload: {
              integration: "openclaw",
              phase: "search_wiki",
              query: normalized.query,
              limit: normalized.limit,
              filters: normalized.filters,
              result_preview: preview(rows)
            },
            agent_id: options.defaultAgentId,
            session_id: options.defaultSessionId,
            tags: ["integration:openclaw", "tool:search_wiki"]
          });
          return rows;
        },
        "Search approved Synapse knowledge for the current task."
      );
      registeredTools.push(searchToolName);
    } else {
      this.emitDebug("attach_openclaw_search_disabled", {
        reason: options.registerSearchTool ? "missing_callback_and_auto_search" : "disabled_by_policy",
        tool: `${options.toolPrefix}_search_wiki`
      });
    }

    if (options.registerProposeTool) {
      const proposeToolName = `${options.toolPrefix}_propose_to_wiki`;
      registerTool(
        proposeToolName,
        async (...args: unknown[]) => {
          const normalized = this.normalizeOpenClawProposeArgs(args);
          if (!normalized.claim_text.trim()) {
            throw new Error("synapse_propose_to_wiki requires non-empty claim_text");
          }
          const claimId = makeId();
          const observedAt = new Date().toISOString();
          const provenance = await buildOpenClawProvenance({
            phase: "propose_to_wiki",
            observedAt,
            payload: {
              project_id: this.projectId,
              entity_key: normalized.entity_key,
              category: normalized.category,
              claim_text: normalized.claim_text,
              source_id: normalized.source_id,
              source_type: normalized.source_type,
              agent_id: options.defaultAgentId ?? null,
              session_id: options.defaultSessionId ?? null
            },
            defaultAgentId: options.defaultAgentId,
            defaultSessionId: options.defaultSessionId
          });
          const claim: Claim = {
            id: claimId,
            schema_version: "v1",
            project_id: this.projectId,
            entity_key: normalized.entity_key,
            category: normalized.category,
            claim_text: normalized.claim_text,
            status: "draft",
            confidence: normalized.confidence,
            metadata: {
              ...normalized.metadata,
              synapse_provenance: provenance
            },
            evidence: [
              {
                source_type: normalized.source_type,
                source_id: normalized.source_id,
                observed_at: observedAt,
                provenance
              }
            ]
          };
          await this.proposeFact(claim);
          this.capture({
            event_type: "fact_proposed",
            payload: {
              integration: "openclaw",
              phase: "propose_to_wiki",
              claim_id: claimId,
              entity_key: normalized.entity_key,
              category: normalized.category,
              provenance: {
                signature_alg: provenance.signature_alg,
                signature: provenance.signature,
                key_id: provenance.key_id ?? null,
                mode: provenance.mode,
                payload_sha256: provenance.payload_sha256
              }
            },
            agent_id: options.defaultAgentId,
            session_id: options.defaultSessionId,
            tags: ["integration:openclaw", "tool:propose_to_wiki"]
          });
          return { status: "queued", claim_id: claimId };
        },
        "Propose a new fact to Synapse for human review."
      );
      registeredTools.push(proposeToolName);
    }

    const canListTasks = options.registerTaskTools && (typeof options.listTasks === "function" || this.transportSupportsTaskApi());
    if (canListTasks) {
      const getTasksToolName = `${options.toolPrefix}_get_open_tasks`;
      registerTool(
        getTasksToolName,
        async (...args: unknown[]) => {
          const normalized = this.normalizeOpenClawGetTasksArgs(args);
          const resolver = options.listTasks;
          const tasks = resolver
            ? await Promise.resolve(
              resolver({
                limit: normalized.limit,
                assignee: normalized.assignee,
                entity_key: normalized.entity_key,
                include_closed: false
              })
            )
            : await this.listTasks({
              limit: normalized.limit,
              assignee: normalized.assignee,
              entityKey: normalized.entity_key,
              includeClosed: false
            });
          const rows = Array.isArray(tasks) ? tasks : [];
          this.capture({
            event_type: "tool_result",
            payload: {
              integration: "openclaw",
              phase: "get_open_tasks",
              limit: normalized.limit,
              assignee: normalized.assignee ?? null,
              entity_key: normalized.entity_key ?? null,
              result_count: rows.length
            },
            agent_id: options.defaultAgentId,
            session_id: options.defaultSessionId,
            tags: ["integration:openclaw", "tool:get_open_tasks"]
          });
          return { tasks: rows };
        },
        "List active Synapse tasks relevant for the current operation."
      );
      registeredTools.push(getTasksToolName);
    }

    const canUpdateTaskStatus = options.registerTaskTools && (typeof options.updateTaskStatus === "function" || this.transportSupportsTaskApi());
    if (canUpdateTaskStatus) {
      const updateStatusToolName = `${options.toolPrefix}_update_task_status`;
      registerTool(
        updateStatusToolName,
        async (...args: unknown[]) => {
          const normalized = this.normalizeOpenClawUpdateTaskArgs(args);
          const actor = normalized.updated_by ?? options.defaultAgentId ?? "openclaw_agent";
          const result = options.updateTaskStatus
            ? await Promise.resolve(
              options.updateTaskStatus(normalized.task_id, {
                status: normalized.status,
                updated_by: actor,
                note: normalized.note
              })
            )
            : await this.updateTaskStatus(normalized.task_id, {
              status: normalizeTaskStatus(normalized.status),
              updatedBy: actor,
              note: normalized.note
            });
          this.capture({
            event_type: "tool_result",
            payload: {
              integration: "openclaw",
              phase: "update_task_status",
              task_id: normalized.task_id,
              status: normalized.status,
              updated_by: actor
            },
            agent_id: options.defaultAgentId,
            session_id: options.defaultSessionId,
            tags: ["integration:openclaw", "tool:update_task_status"]
          });
          return isPlainObject(result) ? result : { status: "ok" };
        },
        "Update Synapse task status after execution progress."
      );
      registeredTools.push(updateStatusToolName);
    }

    return { registeredTools, autoSearchEnabled };
  }

  private resolveOpenClawHookRegistrar(runtime: OpenClawRuntime): (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown {
    if (typeof runtime.on === "function") {
      return runtime.on.bind(runtime);
    }
    if (typeof runtime.register_hook === "function") {
      return runtime.register_hook.bind(runtime);
    }
    throw new TypeError("OpenClaw runtime must provide `on(event, handler)` or `register_hook(event, handler)`.");
  }

  private resolveOpenClawToolRegistrar(
    runtime: OpenClawRuntime
  ): (name: string, handler: (...args: unknown[]) => unknown, description?: string) => unknown {
    if (typeof runtime.register_tool !== "function") {
      throw new TypeError("OpenClaw runtime must provide `register_tool(name, handler, description?)`.");
    }
    const registerTool = runtime.register_tool as (...args: unknown[]) => unknown;
    return (name, handler, description) => {
      try {
        return registerTool.call(runtime, name, handler, description);
      } catch (error) {
        if (!(error instanceof TypeError)) {
          throw error;
        }
        return registerTool.call(runtime, { name, handler, description });
      }
    };
  }

  private transportSupportsTaskApi(): boolean {
    const internal = this as unknown as { transport?: { requestJson?: unknown } };
    return typeof internal.transport?.requestJson === "function";
  }

  private normalizeOpenClawSearchArgs(args: unknown[]): { query: string; limit: number; filters: Record<string, unknown> } {
    if (args.length === 0) {
      throw new TypeError("search_wiki requires query.");
    }
    if (typeof args[0] === "string") {
      const options = isPlainObject(args[1]) ? args[1] : {};
      const query = args[0].trim();
      if (!query) {
        throw new TypeError("search_wiki requires non-empty query.");
      }
      return {
        query,
        limit: normalizeInt(Number(options.limit ?? args[1] ?? 5), 1, 100),
        filters: isPlainObject(options.filters) ? options.filters : {}
      };
    }
    if (args.length === 1 && isPlainObject(args[0])) {
      const payload = args[0];
      const query = asOptionalString(payload.query);
      if (!query) {
        throw new TypeError("search_wiki requires non-empty query.");
      }
      return {
        query,
        limit: normalizeInt(Number(payload.limit ?? 5), 1, 100),
        filters: isPlainObject(payload.filters) ? payload.filters : {}
      };
    }
    throw new TypeError("search_wiki requires string query or payload with query.");
  }

  private normalizeOpenClawProposeArgs(args: unknown[]): {
    entity_key: string;
    category: string;
    claim_text: string;
    source_id: string;
    source_type: EvidenceRef["source_type"];
    confidence?: number;
    metadata: Record<string, unknown>;
  } {
    if (args.length === 1 && isPlainObject(args[0])) {
      const payload = args[0];
      const sourceType = normalizeEvidenceSourceType(asOptionalString(payload.source_type) ?? "external_event");
      return {
        entity_key: requireString(payload.entity_key, "entity_key"),
        category: requireString(payload.category, "category"),
        claim_text: requireString(payload.claim_text, "claim_text"),
        source_id: requireString(payload.source_id, "source_id"),
        source_type: sourceType,
        confidence: normalizeConfidence(payload.confidence),
        metadata: isPlainObject(payload.metadata) ? payload.metadata : {}
      };
    }
    if (args.length >= 4) {
      const options = isPlainObject(args[4]) ? args[4] : {};
      return {
        entity_key: requireString(args[0], "entity_key"),
        category: requireString(args[1], "category"),
        claim_text: requireString(args[2], "claim_text"),
        source_id: requireString(args[3], "source_id"),
        source_type: normalizeEvidenceSourceType(options.source_type ?? "external_event"),
        confidence: normalizeConfidence(options.confidence),
        metadata: isPlainObject(options.metadata) ? options.metadata : {}
      };
    }
    throw new TypeError("propose_to_wiki requires {entity_key, category, claim_text, source_id} or positional arguments.");
  }

  private normalizeOpenClawGetTasksArgs(args: unknown[]): { limit: number; assignee?: string; entity_key?: string } {
    if (args.length === 0) {
      return { limit: 20 };
    }
    if (!(args.length === 1 && isPlainObject(args[0]))) {
      return {
        limit: normalizeInt(Number(args[0] ?? 20), 1, 200)
      };
    }
    const payload = args[0];
    return {
      limit: normalizeInt(Number(payload.limit ?? 20), 1, 200),
      assignee: asOptionalString(payload.assignee),
      entity_key: asOptionalString(payload.entity_key)
    };
  }

  private normalizeOpenClawUpdateTaskArgs(args: unknown[]): {
    task_id: string;
    status: string;
    updated_by?: string;
    note?: string;
  } {
    if (args.length === 1 && isPlainObject(args[0])) {
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
      if (isPlainObject(args[1])) {
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

type OpenClawRuntime = {
  on?: (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown;
  register_hook?: (eventName: string, handler: (event: Record<string, unknown>) => unknown) => unknown;
  register_tool?: ((name: string, handler: (...args: unknown[]) => unknown, description?: string) => unknown)
    | ((payload: Record<string, unknown>) => unknown);
};

type OpenClawProvenanceRecord = {
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
};

async function buildOpenClawProvenance(input: {
  phase: string;
  observedAt: string;
  payload: Record<string, unknown>;
  defaultAgentId?: string;
  defaultSessionId?: string;
}): Promise<OpenClawProvenanceRecord> {
  const canonicalPayload = canonicalJson(input.payload);
  const payloadSha256 = await sha256Hex(canonicalPayload);
  const secret = resolveOpenClawProvenanceSecret();
  const keyId = secret ? resolveOpenClawProvenanceKeyId() : undefined;
  if (secret) {
    return {
      schema: "synapse.openclaw.provenance.v1",
      phase: input.phase,
      integration: "openclaw",
      connector: "synapse-sdk-ts",
      agent_id: input.defaultAgentId,
      session_id: input.defaultSessionId,
      captured_at: input.observedAt,
      signature_alg: "hmac-sha256",
      signature: await hmacSha256Hex(secret, canonicalPayload),
      payload_sha256: payloadSha256,
      key_id: keyId,
      mode: "signed"
    };
  }
  return {
    schema: "synapse.openclaw.provenance.v1",
    phase: input.phase,
    integration: "openclaw",
    connector: "synapse-sdk-ts",
    agent_id: input.defaultAgentId,
    session_id: input.defaultSessionId,
    captured_at: input.observedAt,
    signature_alg: "sha256",
    signature: payloadSha256,
    payload_sha256: payloadSha256,
    mode: "digest_only"
  };
}

function resolveOpenClawProvenanceSecret(): string | undefined {
  return (
    readProcessEnv("SYNAPSE_OPENCLAW_PROVENANCE_SECRET")
    ?? readProcessEnv("SYNAPSE_PROVENANCE_SECRET")
  );
}

function resolveOpenClawProvenanceKeyId(): string {
  return (
    readProcessEnv("SYNAPSE_OPENCLAW_PROVENANCE_KEY_ID")
    ?? readProcessEnv("SYNAPSE_PROVENANCE_KEY_ID")
    ?? "openclaw-default"
  );
}

function canonicalJson(payload: Record<string, unknown>): string {
  return JSON.stringify(sortObject(payload));
}

function sortObject(value: unknown): unknown {
  if (value == null || typeof value !== "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => sortObject(item));
  }
  const out: Record<string, unknown> = {};
  const keys = Object.keys(value as Record<string, unknown>).sort();
  for (const key of keys) {
    out[key] = sortObject((value as Record<string, unknown>)[key]);
  }
  return out;
}

async function sha256Hex(input: string): Promise<string> {
  return digestHex("SHA-256", input);
}

async function hmacSha256Hex(secret: string, input: string): Promise<string> {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) {
    return `${hashString(`${secret}::${input}`)}${hashString(input)}`.slice(0, 64).padEnd(64, "0");
  }
  const encoder = new TextEncoder();
  const key = await cryptoApi.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await cryptoApi.subtle.sign("HMAC", key, encoder.encode(input));
  return toHex(signature);
}

async function digestHex(algorithm: string, input: string): Promise<string> {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) {
    return hashString(input).padEnd(64, "0").slice(0, 64);
  }
  const encoder = new TextEncoder();
  const digest = await cryptoApi.subtle.digest(algorithm, encoder.encode(input));
  return toHex(digest);
}

function toHex(bytesLike: ArrayBuffer): string {
  const bytes = new Uint8Array(bytesLike);
  let out = "";
  for (const byte of bytes) {
    out += byte.toString(16).padStart(2, "0");
  }
  return out;
}

function preview(value: unknown, maxLength = 2000): string {
  const text = typeof value === "string" ? value : JSON.stringify(safeSerialize(value));
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...(truncated)`;
}

function eventSessionId(event: Record<string, unknown>): string {
  return (
    asOptionalString(event.sessionKey)
    ?? asOptionalString(event.session_id)
    ?? asOptionalString(event.sessionId)
    ?? `openclaw_${makeUuid()}`
  );
}

function normalizeEvidenceSourceType(value: unknown): EvidenceRef["source_type"] {
  const candidate = asOptionalString(value);
  if (
    candidate === "dialog"
    || candidate === "tool_output"
    || candidate === "file"
    || candidate === "human_note"
    || candidate === "external_event"
  ) {
    return candidate;
  }
  return "external_event";
}

function normalizeConfidence(value: unknown): number | undefined {
  if (value == null) {
    return undefined;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return undefined;
  }
  return clamp(numeric, 0, 1);
}

function requireString(value: unknown, field: string): string {
  const normalized = asOptionalString(value);
  if (!normalized) {
    throw new TypeError(`${field} is required.`);
  }
  return normalized;
}

function normalizeTaskStatus(value: string): TaskStatus {
  const normalized = value.trim().toLowerCase();
  if (normalized === "todo" || normalized === "in_progress" || normalized === "blocked" || normalized === "done" || normalized === "canceled") {
    return normalized;
  }
  return "todo";
}

function normalizeCallbackMeta(kwargs: Record<string, unknown>): { runId?: string; parentRunId?: string } {
  return {
    runId: asOptionalString(kwargs.run_id) ?? asOptionalString(kwargs.runId),
    parentRunId: asOptionalString(kwargs.parent_run_id) ?? asOptionalString(kwargs.parentRunId)
  };
}

function mergeCallbackMeta(
  runId?: string,
  parentRunId?: string,
  kwargs: Record<string, unknown> = {}
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...kwargs };
  if (runId) {
    out.run_id = runId;
    out.runId = runId;
  }
  if (parentRunId) {
    out.parent_run_id = parentRunId;
    out.parentRunId = parentRunId;
  }
  return out;
}

function bindLangChainLikeTarget<T extends object>(
  target: T,
  handler: LangChainCallbackHandler
): { target: T; mode?: string } {
  const candidate = target as unknown as Record<string, unknown>;

  if (typeof candidate.withConfig === "function") {
    try {
      const withConfig = candidate.withConfig as (config: Record<string, unknown>) => unknown;
      const bound = withConfig({ callbacks: [handler] });
      if (bound && typeof bound === "object") {
        return { target: bound as T, mode: "withConfig" };
      }
    } catch {
      // continue
    }
  }

  const callbackManager = candidate.callbackManager;
  if (callbackManager && typeof callbackManager === "object") {
    const manager = callbackManager as Record<string, unknown>;
    if (typeof manager.addHandler === "function") {
      const addHandler = manager.addHandler as (...args: unknown[]) => unknown;
      for (const call of [
        () => addHandler(handler),
        () => addHandler(handler, true),
        () => addHandler(handler, { inherit: true })
      ]) {
        try {
          call();
          return { target, mode: "callbackManager.addHandler" };
        } catch {
          // continue
        }
      }
    }
    if (typeof manager.addHandlers === "function") {
      const addHandlers = manager.addHandlers as (...args: unknown[]) => unknown;
      for (const call of [
        () => addHandlers([handler]),
        () => addHandlers([handler], true),
        () => addHandlers([handler], { inherit: true })
      ]) {
        try {
          call();
          return { target, mode: "callbackManager.addHandlers" };
        } catch {
          // continue
        }
      }
    }
  }

  if (Array.isArray(candidate.callbacks)) {
    const callbacks = candidate.callbacks as unknown[];
    if (!callbacks.includes(handler)) {
      callbacks.push(handler);
    }
    return { target, mode: "callbacks_list" };
  }

  if (Array.isArray(candidate.config)) {
    // impossible shape for langchain config; ignore
  } else if (isPlainObject(candidate.config)) {
    const config = candidate.config as Record<string, unknown>;
    if (Array.isArray(config.callbacks)) {
      const callbacks = config.callbacks as unknown[];
      if (!callbacks.includes(handler)) {
        callbacks.push(handler);
      }
      return { target, mode: "config_callbacks_list" };
    }
    config.callbacks = [handler];
    return { target, mode: "config_callbacks_new" };
  }

  if (candidate.callbacks == null) {
    try {
      candidate.callbacks = [handler];
      return { target, mode: "callbacks_new" };
    } catch {
      // ignore immutable objects
    }
  }

  return { target };
}

function registerNativeEventListener(
  container: unknown,
  eventName: string,
  handler: (payload: unknown) => void
): boolean {
  if (!container || typeof container !== "object") {
    return false;
  }
  const target = container as Record<string, unknown>;
  const attempts: Array<{ method: string; args: unknown[] }> = [
    { method: "on", args: [eventName, handler] },
    { method: "addListener", args: [eventName, handler] },
    { method: "subscribe", args: [eventName, handler] },
    { method: "registerListener", args: [eventName, handler] }
  ];
  for (const attempt of attempts) {
    const fn = target[attempt.method];
    if (typeof fn !== "function") {
      continue;
    }
    try {
      (fn as (...args: unknown[]) => unknown)(...attempt.args);
      return true;
    } catch {
      // try next binding signature
    }
  }
  return false;
}

function makeClaimIdempotencyKey(claimId: string): string {
  return `claim:v1:${claimId}`;
}

function makeBatchIdempotencyKey(events: ObservationEvent[]): string {
  const material = events.map((event) => event.id).join("|");
  return `events:v1:${hashString(material)}:${events.length}`;
}

function makeBackfillIdempotencyKey(batchId: string, start: number, size: number, finalized: boolean): string {
  return `backfill:v1:${batchId}:${start}:${size}:${finalized ? "final" : "part"}`;
}

function makeUuid(): string {
  if (typeof globalThis.crypto !== "undefined" && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback RFC4122-ish v4 UUID for environments without crypto.randomUUID.
  const template = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx";
  return template.replace(/[xy]/g, (char) => {
    const r = Math.floor(Math.random() * 16);
    const v = char === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function hashString(value: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeInt(value: number, min: number, max: number): number {
  const safe = Number.isFinite(value) ? Math.trunc(value) : min;
  return Math.max(min, Math.min(max, safe));
}

function asOptionalString(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function normalizeStringList(values: unknown): string[] {
  if (!Array.isArray(values)) {
    return [];
  }
  const out: string[] = [];
  const seen = new Set<string>();
  for (const item of values) {
    const value = asOptionalString(item);
    if (!value) {
      continue;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(value);
    if (out.length >= 200) {
      break;
    }
  }
  return out;
}

function coerceResultText(value: unknown): string | undefined {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || undefined;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (isPlainObject(value)) {
    for (const key of ["claim_text", "fact", "message", "text", "result", "summary"]) {
      const candidate = value[key];
      if (typeof candidate === "string" && candidate.trim()) {
        return candidate.trim();
      }
    }
  }
  return undefined;
}

function inferEntityKey(args: unknown[], functionName: string): string {
  if (args.length > 0 && typeof args[0] === "string" && args[0].trim()) {
    return args[0].trim();
  }
  const normalized = functionName.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || "unknown_entity";
}

function defaultMethodsForIntegration(integration: string): string[] {
  return DEFAULT_METHODS[integration] ?? DEFAULT_METHODS.generic;
}

function normalizeDegradationMode(value?: string): DegradationMode {
  const normalized = (value ?? "buffer").trim().toLowerCase();
  if (normalized !== "buffer" && normalized !== "drop" && normalized !== "sync_flush") {
    throw new Error(`invalid degradation mode: ${String(value)}`);
  }
  return normalized;
}

function normalizeAdoptionMode(value?: string): AdoptionMode {
  const raw = (value ?? "full_loop").trim().toLowerCase();
  const aliases: Record<string, AdoptionMode> = {
    full: "full_loop",
    observe: "observe_only",
    draft: "draft_only",
    retrieve: "retrieve_only"
  };
  const normalized = aliases[raw] ?? (raw as AdoptionMode);
  if (
    normalized !== "full_loop" &&
    normalized !== "observe_only" &&
    normalized !== "draft_only" &&
    normalized !== "retrieve_only"
  ) {
    throw new Error(`invalid adoption mode: ${String(value)}`);
  }
  return normalized;
}

function normalizeWikiSpaceKey(spaceKey: string): string {
  const normalized = String(spaceKey ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (!normalized) {
    throw new Error("spaceKey cannot be empty");
  }
  return normalized;
}

function normalizeWikiSpacePolicyMode(mode: string): WikiSpacePolicyMode {
  const normalized = String(mode ?? "open").trim().toLowerCase();
  if (normalized === "open" || normalized === "owners_only") {
    return normalized;
  }
  throw new Error(`unsupported wiki space policy mode: ${String(mode)}`);
}

function normalizeWikiPublishChecklistPreset(
  value: unknown,
  fallback: WikiPublishChecklistPreset = "none"
): WikiPublishChecklistPreset {
  const normalizedFallback = String(fallback ?? "none").trim().toLowerCase();
  const allowed = new Set(["none", "ops_standard", "policy_strict"]);
  const resolvedFallback = (allowed.has(normalizedFallback) ? normalizedFallback : "none") as WikiPublishChecklistPreset;
  const normalized = String(value ?? resolvedFallback).trim().toLowerCase();
  if (allowed.has(normalized)) {
    return normalized as WikiPublishChecklistPreset;
  }
  return resolvedFallback;
}

function normalizeLifecycleActionKey(value: unknown): string {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!normalized) {
    return "";
  }
  return normalized.slice(0, 96);
}

function normalizeLifecycleActionCounts(raw: unknown): Record<string, number> {
  if (!isPlainObject(raw)) {
    return {};
  }
  const normalized: Record<string, number> = {};
  for (const [rawKey, rawValue] of Object.entries(raw)) {
    const actionKey = normalizeLifecycleActionKey(rawKey);
    if (!actionKey) {
      continue;
    }
    const numeric = Number(rawValue);
    if (!Number.isFinite(numeric)) {
      continue;
    }
    normalized[actionKey] = normalizeInt(numeric, 0, 1_000_000_000);
  }
  return normalized;
}

function detectIntegration(target: object): string {
  const maybeRuntime = target as { on?: unknown; register_hook?: unknown; register_tool?: unknown };
  if (looksLikeOpenClawRuntime(maybeRuntime)) {
    return "openclaw";
  }
  if (looksLikeCrewAiRuntime(target)) {
    return "crewai";
  }
  if (looksLikeLangGraphRunnable(target)) {
    return "langgraph";
  }
  if (looksLikeLangChainRunnable(target)) {
    return "langchain";
  }
  return "generic";
}

function looksLikeLangGraphRunnable(target: unknown): boolean {
  const candidate = target as Record<string, unknown>;
  return (
    typeof candidate?.ainvoke === "function" ||
    typeof candidate?.astream === "function" ||
    typeof candidate?.abatch === "function"
  );
}

function looksLikeLangChainRunnable(target: unknown): boolean {
  const candidate = target as Record<string, unknown>;
  if (typeof candidate?.invoke !== "function") {
    return false;
  }
  return (
    typeof candidate?.call === "function" ||
    typeof candidate?.stream === "function" ||
    typeof candidate?.batch === "function" ||
    typeof candidate?.ainvoke === "function"
  );
}

function looksLikeCrewAiRuntime(target: unknown): boolean {
  const candidate = target as Record<string, unknown>;
  return typeof candidate?.kickoff === "function" || typeof candidate?.kickoff_async === "function";
}

function looksLikeOpenClawRuntime(target: unknown): boolean {
  const maybeRuntime = target as { on?: unknown; register_hook?: unknown; register_tool?: unknown };
  const hasHookApi =
    typeof maybeRuntime?.on === "function" || typeof maybeRuntime?.register_hook === "function";
  const hasToolApi = typeof maybeRuntime?.register_tool === "function";
  return Boolean(hasHookApi && hasToolApi);
}

function getAttachTargetType(target: unknown): string {
  if (target == null) {
    return "null";
  }
  if (typeof target === "object" && (target as { constructor?: { name?: string } }).constructor?.name) {
    return String((target as { constructor: { name: string } }).constructor.name);
  }
  return typeof target;
}

function readProcessEnv(key: string): string | undefined {
  const globalProcess = globalThis as { process?: { env?: Record<string, string | undefined>; cwd?: () => string } };
  const value = globalProcess.process?.env?.[key];
  const trimmed = typeof value === "string" ? value.trim() : "";
  return trimmed ? trimmed : undefined;
}

function normalizeBooleanEnv(value: string | undefined): boolean | undefined {
  if (!value) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }
  return undefined;
}

function inferProjectIdFromCwd(): string {
  const globalProcess = globalThis as { process?: { cwd?: () => string } };
  const cwdFn = globalProcess.process?.cwd;
  if (typeof cwdFn !== "function") {
    return "synapse_project";
  }
  const cwd = String(cwdFn() || "");
  const segments = cwd.split(/[\\/]/).filter(Boolean);
  const base = segments.length ? segments[segments.length - 1] : "synapse_project";
  const normalized = base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized || "synapse_project";
}

function isPromiseLike(value: unknown): value is Promise<unknown> {
  return !!value && typeof (value as { then?: unknown }).then === "function";
}

function isIteratorLike(value: unknown): value is Iterator<unknown> {
  return (
    !!value &&
    typeof (value as { next?: unknown }).next === "function" &&
    typeof (value as { [Symbol.iterator]?: unknown })[Symbol.iterator] === "function"
  );
}

function isAsyncIteratorLike(value: unknown): value is AsyncIterator<unknown> {
  return (
    !!value &&
    typeof (value as { next?: unknown }).next === "function" &&
    typeof (value as { [Symbol.asyncIterator]?: unknown })[Symbol.asyncIterator] === "function"
  );
}

function safeSerialize(value: unknown, depth = 0, seen?: WeakSet<object>): unknown {
  const maxDepth = 4;
  const maxItems = 25;
  const maxStringLength = 5000;
  const refs = seen ?? new WeakSet<object>();

  if (value == null || typeof value === "boolean" || typeof value === "number") {
    return value;
  }
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (typeof value === "string") {
    return value.length <= maxStringLength ? value : `${value.slice(0, maxStringLength)}...(truncated)`;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (depth >= maxDepth) {
    return String(value);
  }
  if (typeof value === "object") {
    if (refs.has(value as object)) {
      return "[Circular]";
    }
    refs.add(value as object);
  }

  if (Array.isArray(value)) {
    const out = value.slice(0, maxItems).map((item) => safeSerialize(item, depth + 1, refs));
    if (value.length > maxItems) {
      out.push({ __truncated__: value.length - maxItems });
    }
    return out;
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    const out: Record<string, unknown> = {};
    for (let i = 0; i < Math.min(entries.length, maxItems); i += 1) {
      const [key, itemValue] = entries[i];
      out[key] = safeSerialize(itemValue, depth + 1, refs);
    }
    if (entries.length > maxItems) {
      out.__truncated__ = entries.length - maxItems;
    }
    return out;
  }

  return String(value);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value == null || typeof value !== "object") {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}
