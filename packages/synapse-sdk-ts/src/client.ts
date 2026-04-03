import { AsyncLocalStorage } from "node:async_hooks";
import { HttpTransport } from "./transports/http.js";
import { buildOpenClawBootstrapOptions } from "./openclaw.js";
import type {
  AttachBootstrapMemoryOptions,
  AttachOptions,
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
  ExtractedInsight,
  InsightContext,
  InsightExtractor,
  InsightSynthesizer,
  MemoryBackfillOptions,
  MemoryBackfillRecord,
  MonitorOptions,
  ObservationEvent,
  LangChainCallbackHandler,
  LangChainCallbackHandlerOptions,
  SynthesisContext,
  SynapseConfig,
  SynapseTransport,
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
          }))
        }
      };
      const idempotencyKey = makeBackfillIdempotencyKey(batchId, start, chunk.length, isLast);
      try {
        await this.transport.ingestMemoryBackfill(payload, { idempotencyKey });
        this.emitDebug("backfill_chunk_sent", {
          batch_id: batchId,
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
      try {
        await this.transport.ingestMemoryBackfill(item.payload, { idempotencyKey: item.idempotencyKey });
      } catch (error) {
        const errorType = error instanceof Error ? error.name : "Error";
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (this.degradationMode === "drop") {
          this.emitDebug("flush_pending_backfill_dropped", {
            error_type: errorType,
            error_message: errorMessage
          });
          continue;
        }
        const rest = pending.slice(index);
        this.pendingBackfill.unshift(...rest);
        this.emitDebug("flush_pending_backfill_requeued", {
          error_type: errorType,
          error_message: errorMessage,
          pending_backfill: this.pendingBackfill.length
        });
        return;
      }
    }
    this.emitDebug("flush_pending_backfill_success", { count: pending.length });
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
      method?: "GET" | "POST";
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
    this.emitDebug("attach_started", {
      integration,
      target_type: getAttachTargetType(target),
      auto_bootstrap_enabled: optionsWithDefaults.openclawAutoBootstrapEnabled,
      openclaw_bootstrap_preset: optionsWithDefaults.openclawBootstrapPreset ?? null
    });
    const resolvedBootstrapMemory = this.resolveAttachBootstrapMemory(target, integration, optionsWithDefaults);
    this.bootstrapMemoryOnAttach(target, integration, resolvedBootstrapMemory, {
      agentId: optionsWithDefaults.agentId,
      sessionId: optionsWithDefaults.sessionId
    });
    if (integration === "openclaw" && looksLikeOpenClawRuntime(target)) {
      this.attachOpenClawRuntime(target, optionsWithDefaults, resolvedBootstrapMemory);
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
      openclaw_bootstrap_preset: optionsWithDefaults.openclawBootstrapPreset ?? null
    });
    return monitored;
  }

  private attachOpenClawRuntime(
    target: unknown,
    options: AttachOptions,
    bootstrapMemory: AttachBootstrapMemoryOptions | undefined
  ): void {
    if (!looksLikeOpenClawRuntime(target)) {
      return;
    }
    const runtime = target as OpenClawRuntime;
    const hookEvents = Array.isArray(options.openclawHookEvents) && options.openclawHookEvents.length > 0
      ? options.openclawHookEvents
      : Array.from(DEFAULT_OPENCLAW_EVENTS);
    const registerTools = options.openclawRegisterTools ?? true;
    const toolPrefix = asOptionalString(options.openclawToolPrefix) ?? "synapse";
    this.attachOpenClawHooks(runtime, hookEvents, {
      agentId: options.agentId,
      sessionId: options.sessionId
    });
    const connector = this.registerOpenClawTools(runtime, {
      registerTools,
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
      search_mode: searchMode
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
        reason: "missing_callback_and_auto_search",
        tool: `${options.toolPrefix}_search_wiki`
      });
    }

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

    const canListTasks = typeof options.listTasks === "function" || this.transportSupportsTaskApi();
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

    const canUpdateTaskStatus = typeof options.updateTaskStatus === "function" || this.transportSupportsTaskApi();
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
