import type {
  DebugRecord,
  OTelCounterLike,
  OTelHistogramLike,
  OTelMeterLike,
  OTelSpanLike,
  OTelTracerLike,
  TelemetrySink
} from "./types.js";

type BridgeOptions = {
  projectId: string;
  serviceName?: string;
  tracer?: OTelTracerLike;
  meter?: OTelMeterLike;
};

export class OpenTelemetryBridge {
  private readonly tracer?: OTelTracerLike;
  private readonly meter?: OTelMeterLike;
  private readonly projectId: string;
  private readonly serviceName: string;
  private readonly activeSpans = new Map<string, OTelSpanLike>();

  private readonly eventsTotal?: OTelCounterLike;
  private readonly proposalsTotal?: OTelCounterLike;
  private readonly transportFailuresTotal?: OTelCounterLike;
  private readonly flushBatchSize?: OTelHistogramLike;
  private readonly queueSize?: OTelHistogramLike;

  constructor(options: BridgeOptions) {
    this.projectId = options.projectId;
    this.serviceName = options.serviceName ?? "synapse-sdk";
    this.tracer = options.tracer;
    this.meter = options.meter;

    this.eventsTotal = this.meter?.createCounter("synapse.debug.events_total", {
      description: "Total Synapse debug events"
    });
    this.proposalsTotal = this.meter?.createCounter("synapse.knowledge.proposals_total", {
      description: "Total knowledge proposals emitted by SDK"
    });
    this.transportFailuresTotal = this.meter?.createCounter("synapse.transport.failures_total", {
      description: "Total transport failures observed by SDK"
    });
    this.flushBatchSize = this.meter?.createHistogram("synapse.flush.batch_size", {
      description: "Observed flush batch size",
      unit: "events"
    });
    this.queueSize = this.meter?.createHistogram("synapse.queue.size", {
      description: "Observed in-memory queue sizes",
      unit: "events"
    });
  }

  sink(): TelemetrySink {
    return (record: DebugRecord) => this.handle(record);
  }

  handle(record: DebugRecord): void {
    try {
      this.process(record);
    } catch {
      return;
    }
  }

  private process(record: DebugRecord): void {
    const event = record.event;
    const details = record.details ?? {};
    const attrs = this.buildAttributes(record, event, details);

    this.eventsTotal?.add(1, attrs);

    if (event === "propose_fact_sent" || event === "collect_insight_proposed") {
      this.proposalsTotal?.add(1, attrs);
    }
    if (event.includes("failed") || event.endsWith("_dropped") || event.endsWith("_requeued")) {
      this.transportFailuresTotal?.add(1, attrs);
    }

    const batchSize = asNumber(details.batch_size);
    if (batchSize != null) {
      this.flushBatchSize?.record(batchSize, attrs);
    }
    const queueSize = asNumber(details.queue_size);
    if (queueSize != null) {
      this.queueSize?.record(queueSize, attrs);
    }

    this.mapSpan(record, event, attrs, details);
  }

  private buildAttributes(
    record: DebugRecord,
    event: string,
    details: Record<string, unknown>
  ): Record<string, string | number | boolean> {
    const attrs: Record<string, string | number | boolean> = {
      "synapse.project_id": this.projectId,
      "synapse.service_name": this.serviceName,
      "synapse.event": event
    };
    if (record.traceId) {
      attrs["synapse.trace_id"] = record.traceId;
    }
    if (record.spanId) {
      attrs["synapse.span_id"] = record.spanId;
    }
    if (record.parentSpanId) {
      attrs["synapse.parent_span_id"] = record.parentSpanId;
    }
    const integration = details.integration;
    if (typeof integration === "string" && integration.trim()) {
      attrs["synapse.integration"] = integration;
    }
    for (const key of ["agent_id", "session_id", "function", "extractor", "synthesizer"]) {
      const value = details[key];
      if (typeof value === "string" && value.trim()) {
        attrs[`synapse.${key}`] = value;
      }
    }
    return attrs;
  }

  private mapSpan(
    record: DebugRecord,
    event: string,
    attrs: Record<string, string | number | boolean>,
    details: Record<string, unknown>
  ): void {
    if (!this.tracer) {
      return;
    }
    const operation = operationFromEvent(event);
    if (!operation) {
      return;
    }
    const key = spanKey(record, operation);
    const isStart = event.endsWith("_started") || event.endsWith("_start");
    const isEnd =
      event.endsWith("_completed") ||
      event.endsWith("_success") ||
      event.endsWith("_failed") ||
      event.endsWith("_dropped") ||
      event.endsWith("_requeued");

    if (isStart) {
      const span = this.tracer.startSpan(`synapse.${operation}`, {
        attributes: attrs
      });
      this.activeSpans.set(key, span);
      return;
    }
    if (!isEnd) {
      return;
    }
    const span = this.activeSpans.get(key) ?? this.tracer.startSpan(`synapse.${operation}`, {
      attributes: attrs
    });
    this.activeSpans.delete(key);
    if (span.addEvent) {
      span.addEvent(event, attrs);
    }
    if (span.setAttribute) {
      span.setAttribute("synapse.status", event.includes("failed") || event.includes("dropped") ? "error" : "ok");
      if (typeof details.error_message === "string" && details.error_message) {
        span.setAttribute("synapse.error_message", details.error_message);
      }
    }
    span.end();
  }
}

export function createOpenTelemetryBridge(options: BridgeOptions): OpenTelemetryBridge {
  return new OpenTelemetryBridge(options);
}

function operationFromEvent(event: string): string | null {
  for (const suffix of ["_started", "_completed", "_success", "_failed", "_dropped", "_requeued"]) {
    if (event.endsWith(suffix) && event.length > suffix.length) {
      return event.slice(0, -suffix.length);
    }
  }
  if (event.endsWith("_start") && event.length > "_start".length) {
    return event.slice(0, -"_start".length);
  }
  return null;
}

function spanKey(record: DebugRecord, operation: string): string {
  return `${record.traceId ?? "no-trace"}:${record.spanId ?? "no-span"}:${operation}`;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}
