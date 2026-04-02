import type { Claim, ObservationEvent, RequestOptions, RetryPolicyConfig, SynapseTransport } from "../types.js";

const DEFAULT_RETRYABLE_STATUS_CODES = [408, 409, 425, 429, 500, 502, 503, 504];

const DEFAULT_RETRY_POLICY: Required<RetryPolicyConfig> = {
  maxRetries: 3,
  baseDelayMs: 250,
  maxDelayMs: 5_000,
  jitterRatio: 0.2,
  timeoutMs: 10_000,
  retryableStatusCodes: DEFAULT_RETRYABLE_STATUS_CODES
};

export class SynapseTransportError extends Error {
  readonly statusCode?: number;
  readonly retryable: boolean;
  readonly responseBody?: string;

  constructor(
    message: string,
    options: {
      statusCode?: number;
      retryable: boolean;
      responseBody?: string;
      cause?: unknown;
    }
  ) {
    super(message, { cause: options.cause });
    this.name = "SynapseTransportError";
    this.statusCode = options.statusCode;
    this.retryable = options.retryable;
    this.responseBody = options.responseBody;
  }
}

export class HttpTransport implements SynapseTransport {
  private readonly apiUrl: string;
  private readonly apiKey?: string;
  private readonly retryPolicy: Required<RetryPolicyConfig>;

  constructor(apiUrl: string, apiKey?: string, retry?: RetryPolicyConfig) {
    this.apiUrl = apiUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.retryPolicy = {
      ...DEFAULT_RETRY_POLICY,
      ...retry,
      retryableStatusCodes: retry?.retryableStatusCodes ?? DEFAULT_RETRYABLE_STATUS_CODES
    };
  }

  async sendEvents(events: ObservationEvent[], options?: RequestOptions): Promise<void> {
    await this.requestJson("/v1/events", { method: "POST", payload: { events }, idempotencyKey: options?.idempotencyKey });
  }

  async proposeFact(claim: Claim, options?: RequestOptions): Promise<void> {
    await this.requestJson("/v1/facts/proposals", { method: "POST", payload: { claim }, idempotencyKey: options?.idempotencyKey });
  }

  async ingestMemoryBackfill(payload: Record<string, unknown>, options?: RequestOptions): Promise<void> {
    await this.requestJson("/v1/backfill/memory", { method: "POST", payload, idempotencyKey: options?.idempotencyKey });
  }

  async requestJson<T = Record<string, unknown>>(
    path: string,
    options: {
      method?: "GET" | "POST";
      payload?: unknown;
      params?: Record<string, string | number | boolean | null | undefined>;
      idempotencyKey?: string;
    } = {}
  ): Promise<T> {
    const response = await this.requestWithRetry(path, {
      method: options.method ?? "GET",
      payload: options.payload,
      params: options.params,
      idempotencyKey: options.idempotencyKey
    });
    const raw = await safeReadBody(response);
    if (!raw) {
      return {} as T;
    }
    try {
      return JSON.parse(raw) as T;
    } catch {
      return {} as T;
    }
  }

  private async requestWithRetry(
    path: string,
    options: {
      method: "GET" | "POST";
      payload?: unknown;
      params?: Record<string, string | number | boolean | null | undefined>;
      idempotencyKey?: string;
    }
  ): Promise<Response> {
    for (let attempt = 0; attempt <= this.retryPolicy.maxRetries; attempt += 1) {
      try {
        const response = await this.fetchWithTimeout(path, options);
        if (response.ok) {
          return response;
        }

        const retryable = this.retryPolicy.retryableStatusCodes.includes(response.status);
        const bodyText = await safeReadBody(response);
        const error = new SynapseTransportError(
          `Synapse API request failed with status ${response.status}`,
          {
            statusCode: response.status,
            retryable,
            responseBody: bodyText
          }
        );

        if (!retryable || attempt >= this.retryPolicy.maxRetries) {
          throw error;
        }

        const retryAfterMs = parseRetryAfterMs(response.headers.get("retry-after"));
        const backoffMs = computeBackoffDelayMs(this.retryPolicy, attempt);
        await sleep(Math.max(retryAfterMs ?? 0, backoffMs));
      } catch (error) {
        const transportError = normalizeNetworkError(error);
        if (!transportError.retryable || attempt >= this.retryPolicy.maxRetries) {
          throw transportError;
        }
        await sleep(computeBackoffDelayMs(this.retryPolicy, attempt));
      }
    }
    throw new SynapseTransportError("Synapse API request failed after retries", { retryable: false });
  }

  private async fetchWithTimeout(
    path: string,
    options: {
      method: "GET" | "POST";
      payload?: unknown;
      params?: Record<string, string | number | boolean | null | undefined>;
      idempotencyKey?: string;
    }
  ): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.retryPolicy.timeoutMs);
    try {
      const query = buildQueryString(options.params);
      const url = `${this.apiUrl}${path}${query}`;
      return await fetch(url, {
        method: options.method,
        headers: this.headers(options.idempotencyKey),
        body: options.method === "GET" ? undefined : JSON.stringify(options.payload ?? {}),
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeout);
    }
  }

  private headers(idempotencyKey?: string): Record<string, string> {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.apiKey) {
      headers.authorization = `Bearer ${this.apiKey}`;
    }
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return headers;
  }
}

function normalizeNetworkError(error: unknown): SynapseTransportError {
  if (error instanceof SynapseTransportError) {
    return error;
  }
  const isTimeout = typeof DOMException !== "undefined" && error instanceof DOMException && error.name === "AbortError";
  return new SynapseTransportError(
    isTimeout ? "Synapse API request timed out" : "Synapse API request failed due to network error",
    { retryable: true, cause: error }
  );
}

function computeBackoffDelayMs(policy: Required<RetryPolicyConfig>, attempt: number): number {
  const expDelay = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** attempt);
  if (policy.jitterRatio <= 0) {
    return expDelay;
  }
  const jitterAmplitude = expDelay * policy.jitterRatio;
  const jitter = (Math.random() * 2 - 1) * jitterAmplitude;
  return Math.max(0, Math.round(expDelay + jitter));
}

function parseRetryAfterMs(retryAfterHeader: string | null): number | null {
  if (!retryAfterHeader) {
    return null;
  }
  const seconds = Number.parseInt(retryAfterHeader, 10);
  if (Number.isFinite(seconds)) {
    return Math.max(0, seconds * 1_000);
  }
  const retryAtMs = Date.parse(retryAfterHeader);
  if (Number.isNaN(retryAtMs)) {
    return null;
  }
  return Math.max(0, retryAtMs - Date.now());
}

async function safeReadBody(response: Response): Promise<string | undefined> {
  try {
    const body = await response.text();
    return body.slice(0, 2_000);
  } catch {
    return undefined;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildQueryString(params?: Record<string, string | number | boolean | null | undefined>): string {
  if (!params) {
    return "";
  }
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) continue;
    query.set(key, String(value));
  }
  const raw = query.toString();
  return raw ? `?${raw}` : "";
}
