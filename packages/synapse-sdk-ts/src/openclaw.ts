import type { AttachBootstrapMemoryOptions, BootstrapMemoryInput, OpenClawBootstrapPreset } from "./types.js";

export const OPENCLAW_BOOTSTRAP_PRESETS = ["runtime_memory", "event_log", "hybrid"] as const;

export interface OpenClawBootstrapPresetDescriptor {
  preset: OpenClawBootstrapPreset;
  description: string;
  defaultSourceSystem: string;
}

export interface BuildOpenClawBootstrapOptionsInput {
  preset?: OpenClawBootstrapPreset | string;
  maxRecords?: number;
  sourceSystem?: string;
  createdBy?: string;
  cursor?: string;
  chunkSize?: number;
}

export interface CollectOpenClawBootstrapRecordsInput {
  preset?: OpenClawBootstrapPreset | string;
  maxRecords?: number;
}

type OpenClawBootstrapRecord = {
  source_id?: string;
  content?: string;
  observed_at?: string;
  entity_key?: string;
  category?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
  [key: string]: unknown;
};

export function listOpenClawBootstrapPresets(): OpenClawBootstrapPresetDescriptor[] {
  return [
    {
      preset: "runtime_memory",
      description: "Read historical records from runtime memory exporter methods.",
      defaultSourceSystem: "openclaw_runtime_memory"
    },
    {
      preset: "event_log",
      description: "Build bootstrap records from runtime event log replay payloads.",
      defaultSourceSystem: "openclaw_event_log"
    },
    {
      preset: "hybrid",
      description: "Combine runtime memory export + event log replay (deduplicated).",
      defaultSourceSystem: "openclaw_hybrid_bootstrap"
    }
  ];
}

export function buildOpenClawBootstrapOptions(
  options: BuildOpenClawBootstrapOptionsInput = {}
): AttachBootstrapMemoryOptions {
  const preset = normalizeOpenClawBootstrapPreset(options.preset ?? "runtime_memory");
  const maxRecords = clampInt(options.maxRecords ?? 1000, 1, 10_000, 1000);
  const chunkSize = clampInt(options.chunkSize ?? 100, 1, 10_000, 100);
  const sourceSystem = options.sourceSystem?.trim() || defaultSourceSystemForPreset(preset);
  const createdBy = options.createdBy ?? "sdk_attach";
  const cursor = options.cursor ?? undefined;
  return {
    provider: (runtime) =>
      collectOpenClawBootstrapRecords(runtime, {
        preset,
        maxRecords
      }),
    sourceSystem,
    createdBy,
    cursor,
    chunkSize,
    maxRecords
  };
}

export function collectOpenClawBootstrapRecords(
  runtime: unknown,
  options: CollectOpenClawBootstrapRecordsInput = {}
): BootstrapMemoryInput[] {
  const preset = normalizeOpenClawBootstrapPreset(options.preset ?? "runtime_memory");
  const maxRecords = clampInt(options.maxRecords ?? 1000, 1, 10_000, 1000);
  return collectOpenClawBootstrapRecordsInternal({
    runtime,
    preset,
    maxRecords
  });
}

export function normalizeOpenClawBootstrapPreset(value: string): OpenClawBootstrapPreset {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase();
  if (
    normalized !== "runtime_memory" &&
    normalized !== "event_log" &&
    normalized !== "hybrid"
  ) {
    const allowed = OPENCLAW_BOOTSTRAP_PRESETS.join(", ");
    throw new Error(`unsupported openclaw bootstrap preset \`${value}\` (allowed: ${allowed})`);
  }
  return normalized;
}

function defaultSourceSystemForPreset(preset: OpenClawBootstrapPreset): string {
  if (preset === "runtime_memory") {
    return "openclaw_runtime_memory";
  }
  if (preset === "event_log") {
    return "openclaw_event_log";
  }
  return "openclaw_hybrid_bootstrap";
}

function collectOpenClawBootstrapRecordsInternal(options: {
  runtime: unknown;
  preset: OpenClawBootstrapPreset;
  maxRecords: number;
}): BootstrapMemoryInput[] {
  const records: BootstrapMemoryInput[] = [];
  if (options.preset === "runtime_memory" || options.preset === "hybrid") {
    records.push(...recordsFromRuntimeMemory(options.runtime));
  }
  if (options.preset === "event_log" || options.preset === "hybrid") {
    records.push(...recordsFromRuntimeEventLog(options.runtime));
  }

  const dedupe = new Set<string>();
  const out: BootstrapMemoryInput[] = [];
  for (const item of records) {
    const normalized = coerceBootstrapItem(item);
    if (!normalized) {
      continue;
    }
    const sourceId = asOptionalString(normalized.source_id);
    const content = asOptionalString(normalized.content);
    if (!sourceId || !content) {
      continue;
    }
    const key = `${sourceId}::${content}`;
    if (dedupe.has(key)) {
      continue;
    }
    dedupe.add(key);
    out.push(normalized);
    if (out.length >= options.maxRecords) {
      break;
    }
  }
  return out;
}

function recordsFromRuntimeMemory(runtime: unknown): BootstrapMemoryInput[] {
  const resolver = resolveRuntimeMemoryExporter(runtime);
  if (!resolver) {
    return [];
  }
  const raw = resolver();
  return coerceIterablePayload(raw);
}

function resolveRuntimeMemoryExporter(runtime: unknown): (() => unknown) | null {
  if (!isRecord(runtime)) {
    return null;
  }
  const memory = isRecord(runtime.memory) ? runtime.memory : null;
  const holders: Record<string, unknown>[] = [];
  if (memory) {
    holders.push(memory);
  }
  holders.push(runtime);
  const candidates = [
    "export_all",
    "exportAll",
    "export_memory",
    "exportMemory",
    "dump",
    "list",
    "list_all",
    "to_records",
    "records"
  ];
  for (const holder of holders) {
    for (const name of candidates) {
      const maybeFn = holder[name];
      if (typeof maybeFn === "function") {
        return () => (maybeFn as (...args: unknown[]) => unknown).call(holder);
      }
    }
  }
  return null;
}

function recordsFromRuntimeEventLog(runtime: unknown): BootstrapMemoryInput[] {
  if (!isRecord(runtime)) {
    return [];
  }
  const eventLogCandidate =
    runtime.event_log ??
    runtime.eventLog ??
    (typeof runtime.get_event_log === "function"
      ? (runtime.get_event_log as () => unknown).call(runtime)
      : undefined) ??
    (typeof runtime.getEventLog === "function"
      ? (runtime.getEventLog as () => unknown).call(runtime)
      : undefined);
  const rows = coerceIterablePayload(
    typeof eventLogCandidate === "function"
      ? (eventLogCandidate as () => unknown).call(runtime)
      : eventLogCandidate
  );
  const out: BootstrapMemoryInput[] = [];
  rows.forEach((row, index) => {
    if (!isRecord(row)) {
      const text = asOptionalString(row);
      if (!text) {
        return;
      }
      out.push({
        source_id: `openclaw_event_${index + 1}`,
        content: text,
        metadata: { openclaw_bootstrap_origin: "event_log" },
        tags: ["origin:event_log"]
      });
      return;
    }
    const rowRecord = row as Record<string, unknown>;
    const eventName = asOptionalString(rowRecord["event_name"]) ?? asOptionalString(rowRecord["event"]) ?? "event";
    const payload = isRecord(rowRecord["payload"]) ? (rowRecord["payload"] as Record<string, unknown>) : {};
    let content =
      asOptionalString(payload.result) ??
      asOptionalString(payload.message) ??
      asOptionalString(payload.summary) ??
      asOptionalString(payload.text) ??
      asOptionalString(rowRecord["message"]) ??
      asOptionalString(rowRecord["summary"]) ??
      asOptionalString(rowRecord["content"]);
    if (!content) {
      content = preview(payload && Object.keys(payload).length ? payload : rowRecord, 800);
    }
    if (!content) {
      return;
    }
    const sourceId =
      asOptionalString(rowRecord["source_id"]) ??
      asOptionalString(payload.source_id) ??
      asOptionalString(payload.sessionKey) ??
      `openclaw_event_${index + 1}`;
    out.push({
      source_id: sourceId,
      content,
      entity_key: asOptionalString(payload.entity_key) ?? asOptionalString(row.entity_key),
      category: asOptionalString(payload.category) ?? asOptionalString(row.category),
      observed_at: asOptionalString(rowRecord["observed_at"]) ?? asOptionalString(payload.observed_at),
      metadata: {
        openclaw_bootstrap_origin: "event_log",
        event_name: eventName
      },
      tags: [`event:${eventName}`, "origin:event_log"]
    });
  });
  return out;
}

function coerceBootstrapItem(item: BootstrapMemoryInput): OpenClawBootstrapRecord | null {
  if (typeof item === "string") {
    const content = item.trim();
    if (!content) {
      return null;
    }
    return {
      source_id: `openclaw_memory_${hashString(content).slice(0, 12)}`,
      content,
      metadata: { openclaw_bootstrap_origin: "runtime_memory" },
      tags: ["origin:runtime_memory"]
    };
  }
  if (!isRecord(item)) {
    return null;
  }
  const sourceId =
    asOptionalString(item.source_id) ??
    asOptionalString(item.id) ??
    asOptionalString(item.key) ??
    asOptionalString(item.memory_id);
  const content =
    asOptionalString(item.content) ??
    asOptionalString(item.text) ??
    asOptionalString(item.fact) ??
    asOptionalString(item.message) ??
    asOptionalString(item.summary) ??
    asOptionalString((item as Record<string, unknown>)["result"]);
  if (!content) {
    return null;
  }
  const metadata = isRecord(item.metadata) ? { ...item.metadata } : {};
  if (!("openclaw_bootstrap_origin" in metadata)) {
    metadata.openclaw_bootstrap_origin = "runtime_memory";
  }
  const tags = toStringArray(item.tags);
  if (!tags.includes("origin:runtime_memory")) {
    tags.push("origin:runtime_memory");
  }
  return {
    source_id: sourceId ?? `openclaw_memory_${hashString(content).slice(0, 12)}`,
    content,
    observed_at:
      asOptionalString(item.observed_at) ??
      asOptionalString(item.timestamp) ??
      asOptionalString((item as Record<string, unknown>)["created_at"]),
    entity_key: asOptionalString(item.entity_key) ?? asOptionalString(item.entity),
    category: asOptionalString(item.category),
    metadata,
    tags
  };
}

function coerceIterablePayload(payload: unknown): BootstrapMemoryInput[] {
  if (payload == null) {
    return [];
  }
  if (Array.isArray(payload)) {
    return payload as BootstrapMemoryInput[];
  }
  if (isRecord(payload)) {
    for (const key of ["items", "records", "data", "events", "rows"]) {
      const value = payload[key];
      if (Array.isArray(value)) {
        return value as BootstrapMemoryInput[];
      }
    }
    return [payload as BootstrapMemoryInput];
  }
  return [payload as BootstrapMemoryInput];
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item).trim())
    .filter(Boolean);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function asOptionalString(value: unknown): string | undefined {
  if (value == null) {
    return undefined;
  }
  const text = String(value).trim();
  return text || undefined;
}

function clampInt(value: number, minValue: number, maxValue: number, fallback: number): number {
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, Math.trunc(value)));
}

function preview(value: unknown, maxLength = 2000): string | undefined {
  const text = asOptionalString(
    (() => {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    })()
  );
  if (!text) {
    return undefined;
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...(truncated)`;
}

function hashString(input: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < input.length; i += 1) {
    const ch = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(16, "0");
}
