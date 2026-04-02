export type MCPToolCaller = (toolName: string, args: Record<string, unknown>) => Promise<unknown> | unknown;

export type MCPContextPolicyMode = "off" | "advisory" | "enforced";
export type MCPContextPolicyProfileName = "off" | "advisory" | "enforced" | "strict_enforced";

export interface MCPContextPolicyProfile {
  contextPolicyMode: MCPContextPolicyMode;
  minRetrievalConfidence?: number;
  minTotalScore?: number;
  minLexicalScore?: number;
  minTokenOverlapRatio?: number;
  description: string;
}

export const MCP_CONTEXT_POLICY_PROFILES: Record<MCPContextPolicyProfileName, MCPContextPolicyProfile> = {
  off: {
    contextPolicyMode: "off",
    description: "Disable context policy filtering and rely on baseline ranking only."
  },
  advisory: {
    contextPolicyMode: "advisory",
    description: "Keep full retrieval set but attach policy/confidence diagnostics."
  },
  enforced: {
    contextPolicyMode: "enforced",
    minRetrievalConfidence: 0.45,
    minTotalScore: 0.2,
    minLexicalScore: 0.08,
    minTokenOverlapRatio: 0.15,
    description: "Filter low-confidence rows for production-safe prompt injection."
  },
  strict_enforced: {
    contextPolicyMode: "enforced",
    minRetrievalConfidence: 0.6,
    minTotalScore: 0.3,
    minLexicalScore: 0.1,
    minTokenOverlapRatio: 0.2,
    description: "Use stricter filtering for high-risk or high-precision workflows."
  }
};

type ResolvedContextPolicyProfile = {
  contextPolicyProfile?: MCPContextPolicyProfileName;
  contextPolicyMode?: MCPContextPolicyMode;
  minRetrievalConfidence?: number;
  minTotalScore?: number;
  minLexicalScore?: number;
  minTokenOverlapRatio?: number;
};

export function listContextPolicyProfiles(): Array<MCPContextPolicyProfile & { profile: MCPContextPolicyProfileName }> {
  return (Object.keys(MCP_CONTEXT_POLICY_PROFILES) as MCPContextPolicyProfileName[]).map((profile) => ({
    profile,
    ...MCP_CONTEXT_POLICY_PROFILES[profile]
  }));
}

export interface MCPContextHelperOptions {
  defaultSearchLimit?: number;
  defaultFactLimit?: number;
  defaultContextPolicyProfile?: MCPContextPolicyProfileName | string;
  defaultContextPolicyMode?: MCPContextPolicyMode;
  defaultMinRetrievalConfidence?: number;
  defaultMinTotalScore?: number;
  defaultMinLexicalScore?: number;
  defaultMinTokenOverlapRatio?: number;
}

export interface SearchKnowledgeOptions {
  limit?: number;
  filters?: Record<string, unknown>;
  contextPolicyProfile?: MCPContextPolicyProfileName | string;
  contextPolicyMode?: MCPContextPolicyMode;
  minRetrievalConfidence?: number;
  minTotalScore?: number;
  minLexicalScore?: number;
  minTokenOverlapRatio?: number;
}

export interface EntityFactOptions {
  limit?: number;
  category?: string;
  includeNonCurrent?: boolean;
}

export interface BuildContextOptions {
  query: string;
  entityKey?: string;
  includeRecentChanges?: boolean;
  recentSinceHours?: number;
  contextPolicyProfile?: MCPContextPolicyProfileName | string;
  contextPolicyMode?: MCPContextPolicyMode;
  minRetrievalConfidence?: number;
  minTotalScore?: number;
  minLexicalScore?: number;
  minTokenOverlapRatio?: number;
}

export interface BuildContextMarkdownOptions extends BuildContextOptions {
  maxSearchResults?: number;
  maxEntityFacts?: number;
  maxRecentChanges?: number;
}

export class MCPContextHelper {
  private readonly defaultSearchLimit: number;
  private readonly defaultFactLimit: number;
  private readonly defaultContextPolicyProfile?: MCPContextPolicyProfileName;
  private readonly defaultContextPolicyMode: MCPContextPolicyMode;
  private readonly defaultMinRetrievalConfidence?: number;
  private readonly defaultMinTotalScore?: number;
  private readonly defaultMinLexicalScore?: number;
  private readonly defaultMinTokenOverlapRatio?: number;

  constructor(
    private readonly projectId: string,
    private readonly callTool: MCPToolCaller,
    options: MCPContextHelperOptions = {}
  ) {
    this.defaultSearchLimit = normalizeLimit(options.defaultSearchLimit ?? 6, 1, 100, 6);
    this.defaultFactLimit = normalizeLimit(options.defaultFactLimit ?? 20, 1, 500, 20);
    this.defaultContextPolicyProfile = normalizePolicyProfile(options.defaultContextPolicyProfile);
    this.defaultContextPolicyMode = normalizePolicyMode(options.defaultContextPolicyMode);
    this.defaultMinRetrievalConfidence =
      options.defaultMinRetrievalConfidence == null
        ? undefined
        : clampFloat(options.defaultMinRetrievalConfidence, 0, 1, 0.45);
    this.defaultMinTotalScore =
      options.defaultMinTotalScore == null ? undefined : clampFloat(options.defaultMinTotalScore, 0, 2, 0.2);
    this.defaultMinLexicalScore =
      options.defaultMinLexicalScore == null ? undefined : clampFloat(options.defaultMinLexicalScore, 0, 2, 0.08);
    this.defaultMinTokenOverlapRatio =
      options.defaultMinTokenOverlapRatio == null
        ? undefined
        : clampFloat(options.defaultMinTokenOverlapRatio, 0, 1, 0.15);
  }

  async searchKnowledge(query: string, options: SearchKnowledgeOptions = {}): Promise<Record<string, unknown>> {
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      query,
      limit: normalizeLimit(options.limit ?? this.defaultSearchLimit, 1, 100, this.defaultSearchLimit)
    };
    const profile = resolveContextPolicyProfile(options.contextPolicyProfile ?? this.defaultContextPolicyProfile);
    const mode = normalizePolicyMode(options.contextPolicyMode ?? profile.contextPolicyMode ?? this.defaultContextPolicyMode);
    if (mode !== "advisory") {
      payload.context_policy_mode = mode;
    }
    const minRetrievalConfidence =
      options.minRetrievalConfidence == null
        ? (profile.minRetrievalConfidence ?? this.defaultMinRetrievalConfidence)
        : options.minRetrievalConfidence;
    if (minRetrievalConfidence != null) {
      payload.min_retrieval_confidence = clampFloat(minRetrievalConfidence, 0, 1, 0.45);
    }
    const minTotalScore =
      options.minTotalScore == null ? (profile.minTotalScore ?? this.defaultMinTotalScore) : options.minTotalScore;
    if (minTotalScore != null) {
      payload.min_total_score = clampFloat(minTotalScore, 0, 2, 0.2);
    }
    const minLexicalScore =
      options.minLexicalScore == null
        ? (profile.minLexicalScore ?? this.defaultMinLexicalScore)
        : options.minLexicalScore;
    if (minLexicalScore != null) {
      payload.min_lexical_score = clampFloat(minLexicalScore, 0, 2, 0.08);
    }
    const minTokenOverlapRatio =
      options.minTokenOverlapRatio == null
        ? (profile.minTokenOverlapRatio ?? this.defaultMinTokenOverlapRatio)
        : options.minTokenOverlapRatio;
    if (minTokenOverlapRatio != null) {
      payload.min_token_overlap_ratio = clampFloat(minTokenOverlapRatio, 0, 1, 0.15);
    }
    Object.assign(payload, options.filters ?? {});
    const response = await this.callTool("search_knowledge", payload);
    const normalized = coercePayload(response);
    if (isRecord(normalized)) {
      return normalized;
    }
    return { results: normalized };
  }

  async getEntityFacts(entityKey: string, options: EntityFactOptions = {}): Promise<Record<string, unknown>> {
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      entity_key: entityKey,
      limit: normalizeLimit(options.limit ?? this.defaultFactLimit, 1, 500, this.defaultFactLimit),
      include_non_current: Boolean(options.includeNonCurrent ?? false)
    };
    if (options.category) {
      payload.category = options.category;
    }
    const response = await this.callTool("get_entity_facts", payload);
    const normalized = coercePayload(response);
    if (isRecord(normalized)) {
      return normalized;
    }
    return { facts: normalized };
  }

  async getRecentChanges(limit = 20, sinceHours = 168): Promise<Record<string, unknown>> {
    const payload = {
      project_id: this.projectId,
      limit: normalizeLimit(limit, 1, 200, 20),
      since_hours: normalizeLimit(sinceHours, 1, 24 * 90, 168)
    };
    const response = await this.callTool("get_recent_changes", payload);
    const normalized = coercePayload(response);
    if (isRecord(normalized)) {
      return normalized;
    }
    return { changes: normalized };
  }

  async explainConflicts(limit = 20, resolutionStatus = "open", entityKey?: string): Promise<Record<string, unknown>> {
    const payload: Record<string, unknown> = {
      project_id: this.projectId,
      limit: normalizeLimit(limit, 1, 200, 20),
      resolution_status: resolutionStatus
    };
    if (entityKey) {
      payload.entity_key = entityKey;
    }
    const response = await this.callTool("explain_conflicts", payload);
    const normalized = coercePayload(response);
    if (isRecord(normalized)) {
      return normalized;
    }
    return { conflicts: normalized };
  }

  async buildContext(options: BuildContextOptions): Promise<Record<string, unknown>> {
    const policyMode = normalizePolicyMode(options.contextPolicyMode ?? "enforced");
    const searchPayload = await this.searchKnowledge(options.query, {
      contextPolicyProfile: options.contextPolicyProfile,
      contextPolicyMode: policyMode,
      minRetrievalConfidence: options.minRetrievalConfidence,
      minTotalScore: options.minTotalScore,
      minLexicalScore: options.minLexicalScore,
      minTokenOverlapRatio: options.minTokenOverlapRatio
    });
    const rawSearchResults = toArray(searchPayload.results);
    const filtered = filterContextResults(rawSearchResults, {
      mode: policyMode,
      minRetrievalConfidence: options.minRetrievalConfidence
    });
    const context: Record<string, unknown> = {
      query: options.query,
      search_results: filtered.results,
      revision: searchPayload.revision ?? null,
      policy_filtered_out:
        typeof searchPayload.policy_filtered_out === "number"
          ? Number(searchPayload.policy_filtered_out)
          : filtered.filteredOut,
      context_policy: coerceContextPolicyPayload(searchPayload, policyMode),
      entity_facts: [],
      recent_changes: []
    };

    if (options.entityKey) {
      const factsPayload = await this.getEntityFacts(options.entityKey);
      context.entity_key = options.entityKey;
      context.entity_facts = toArray(factsPayload.facts);
      context.facts_revision = factsPayload.revision ?? null;
    }

    if (options.includeRecentChanges) {
      const changesPayload = await this.getRecentChanges(20, options.recentSinceHours ?? 24);
      context.recent_changes = toArray(changesPayload.changes);
    }
    return context;
  }

  async buildContextMarkdown(options: BuildContextMarkdownOptions): Promise<string> {
    const maxSearchResults = normalizeLimit(options.maxSearchResults ?? 5, 1, 50, 5);
    const maxEntityFacts = normalizeLimit(options.maxEntityFacts ?? 8, 1, 50, 8);
    const maxRecentChanges = normalizeLimit(options.maxRecentChanges ?? 4, 1, 50, 4);
    const context = await this.buildContext(options);

    const lines: string[] = ["## Synapse Context Injection", `- query: ${options.query}`];
    if (options.entityKey) {
      lines.push(`- entity_key: ${options.entityKey}`);
    }

    const searchResults = toArray(context.search_results);
    if (searchResults.length > 0) {
      lines.push("### Relevant Knowledge");
      for (const item of searchResults.slice(0, maxSearchResults)) {
        if (!isRecord(item)) continue;
        const statement = typeof item.statement_text === "string" ? item.statement_text : "";
        if (!statement) continue;
        const page = isRecord(item.page) ? item.page : {};
        const pageSlug = typeof page.slug === "string" ? page.slug : "";
        lines.push(pageSlug ? `- ${statement} (\`${pageSlug}\`)` : `- ${statement}`);
      }
    }

    const facts = toArray(context.entity_facts);
    if (facts.length > 0) {
      lines.push("### Entity Facts");
      for (const item of facts.slice(0, maxEntityFacts)) {
        if (!isRecord(item)) continue;
        const statement = typeof item.statement_text === "string" ? item.statement_text : "";
        if (statement) {
          lines.push(`- ${statement}`);
        }
      }
    }

    const recentChanges = toArray(context.recent_changes);
    if (recentChanges.length > 0) {
      lines.push("### Recent Changes");
      for (const item of recentChanges.slice(0, maxRecentChanges)) {
        if (!isRecord(item)) continue;
        const action = typeof item.action === "string" ? item.action : "";
        const createdAt = typeof item.created_at === "string" ? item.created_at : "";
        const page = isRecord(item.page) ? item.page : {};
        const pageSlug = typeof page.slug === "string" ? page.slug : "";
        const label = [action, pageSlug].filter(Boolean).join(" ");
        if (label) {
          lines.push(createdAt ? `- ${label} (${createdAt})` : `- ${label}`);
        }
      }
    }
    return `${lines.join("\n").trim()}\n`;
  }

  makeOpenClawSearchCallback(
    defaultFilters: Record<string, unknown> = {},
    options: {
      contextPolicyProfile?: MCPContextPolicyProfileName | string;
      contextPolicyMode?: MCPContextPolicyMode;
      minRetrievalConfidence?: number;
      minTotalScore?: number;
      minLexicalScore?: number;
      minTokenOverlapRatio?: number;
    } = {}
  ) {
    return async (query: string, limit = 5, filters: Record<string, unknown> = {}): Promise<unknown> => {
      const payload = await this.searchKnowledge(query, {
        limit,
        filters: { ...defaultFilters, ...filters },
        contextPolicyProfile: options.contextPolicyProfile,
        contextPolicyMode: options.contextPolicyMode,
        minRetrievalConfidence: options.minRetrievalConfidence,
        minTotalScore: options.minTotalScore,
        minLexicalScore: options.minLexicalScore,
        minTokenOverlapRatio: options.minTokenOverlapRatio
      });
      return payload.results ?? payload;
    };
  }
}

function normalizeLimit(value: unknown, minValue: number, maxValue: number, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, Math.trunc(parsed)));
}

function clampFloat(value: unknown, minValue: number, maxValue: number, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, parsed));
}

function normalizePolicyMode(value: unknown): MCPContextPolicyMode {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "off" || normalized === "advisory" || normalized === "enforced") {
    return normalized;
  }
  return "advisory";
}

function normalizePolicyProfile(value: unknown): MCPContextPolicyProfileName | undefined {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  if (normalized in MCP_CONTEXT_POLICY_PROFILES) {
    return normalized as MCPContextPolicyProfileName;
  }
  throw new Error(
    `unsupported context policy profile \`${String(value)}\` (allowed: ${Object.keys(MCP_CONTEXT_POLICY_PROFILES).join(", ")})`
  );
}

function resolveContextPolicyProfile(value: unknown): ResolvedContextPolicyProfile {
  const profile = normalizePolicyProfile(value);
  if (!profile) {
    return {};
  }
  const config = MCP_CONTEXT_POLICY_PROFILES[profile];
  return {
    contextPolicyProfile: profile,
    contextPolicyMode: config.contextPolicyMode,
    minRetrievalConfidence: config.minRetrievalConfidence,
    minTotalScore: config.minTotalScore,
    minLexicalScore: config.minLexicalScore,
    minTokenOverlapRatio: config.minTokenOverlapRatio
  };
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function coercePayload(response: unknown): unknown {
  if (isRecord(response)) {
    if (isRecord(response.structuredContent)) {
      return response.structuredContent;
    }
    if (isRecord(response.result)) {
      return response.result;
    }
    return response;
  }
  if (Array.isArray(response)) {
    return response;
  }
  return { raw: response };
}

function coerceContextPolicyPayload(
  payload: Record<string, unknown>,
  mode: "off" | "advisory" | "enforced"
): Record<string, unknown> {
  const explainability = isRecord(payload.explainability) ? payload.explainability : null;
  if (explainability && isRecord(explainability.context_policy)) {
    return explainability.context_policy;
  }
  if (isRecord(payload.context_policy)) {
    return payload.context_policy;
  }
  return { mode };
}

function filterContextResults(
  results: unknown[],
  options: { mode: MCPContextPolicyMode; minRetrievalConfidence?: number }
): { results: unknown[]; filteredOut: number } {
  if (options.mode !== "enforced") {
    return { results, filteredOut: 0 };
  }
  const threshold =
    options.minRetrievalConfidence == null ? undefined : clampFloat(options.minRetrievalConfidence, 0, 1, 0.45);
  const kept: unknown[] = [];
  let filteredOut = 0;
  for (const item of results) {
    if (!isRecord(item)) {
      kept.push(item);
      continue;
    }
    if (isRecord(item.context_policy) && "eligible" in item.context_policy) {
      if (Boolean(item.context_policy.eligible)) {
        kept.push(item);
      } else {
        filteredOut += 1;
      }
      continue;
    }
    if (threshold != null && typeof item.retrieval_confidence === "number" && item.retrieval_confidence < threshold) {
      filteredOut += 1;
      continue;
    }
    kept.push(item);
  }
  return { results: kept, filteredOut };
}
