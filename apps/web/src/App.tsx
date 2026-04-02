import {
  ActionIcon,
  Badge,
  Breadcrumbs,
  Box,
  Button,
  Card,
  Checkbox,
  Code,
  Divider,
  Group,
  HoverCard,
  Kbd,
  Loader,
  Paper,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconArrowsShuffle,
  IconBookmark,
  IconBookmarkFilled,
  IconCheck,
  IconChevronDown,
  IconChevronUp,
  IconCloudCog,
  IconDeviceFloppy,
  IconEditCircle,
  IconExternalLink,
  IconExclamationCircle,
  IconFilePlus,
  IconHistory,
  IconKeyboard,
  IconRefresh,
  IconSearch,
  IconSwords,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import { diffWords } from "diff";
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";

type DraftStatus = "pending_review" | "blocked_conflict" | "approved" | "rejected";

type DraftSummary = {
  id: string;
  claim_id: string;
  page_id: string | null;
  section_key: string | null;
  decision: string;
  confidence: number;
  rationale: string;
  status: DraftStatus;
  created_at: string;
  page: {
    title: string | null;
    slug: string | null;
  };
};

type ConflictItem = {
  id: string;
  conflict_type: string;
  resolution_status: string;
  details: Record<string, unknown>;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
};

type ConflictExplainItem = {
  conflict_id: string;
  conflict_type: string;
  resolution_status: string;
  created_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  details: Record<string, unknown>;
  root_cause: string;
  recommendation: string;
  page: {
    id: string | null;
    title: string | null;
    slug: string | null;
    entity_key: string | null;
  };
  incoming_claim: {
    id: string | null;
    entity_key: string | null;
    category: string | null;
    claim_text: string | null;
    valid_from: string | null;
    valid_to: string | null;
  };
  conflicting_statement: {
    id: string | null;
    section_key: string | null;
    statement_text: string | null;
    valid_from: string | null;
    valid_to: string | null;
  };
  rank_score: number;
};

type ConflictExplainPayload = {
  project_id: string;
  draft_id: string;
  source: string;
  scope: {
    claim_id: string;
    entity_key: string | null;
  };
  resolution_status: string | null;
  conflicts: ConflictExplainItem[];
};

type DraftDetailPayload = {
  draft: {
    id: string;
    claim_id: string;
    page_id: string | null;
    section_key: string | null;
    decision: string;
    confidence: number;
    rationale: string;
    status: DraftStatus;
    created_at: string;
    updated_at: string;
    markdown_patch: string;
    semantic_diff: Record<string, unknown>;
    evidence: unknown[];
    page: {
      title: string | null;
      slug: string | null;
      page_type: string | null;
      entity_key: string | null;
    };
    claim: {
      claim_text: string | null;
      category: string | null;
      entity_key: string | null;
      status: string | null;
      valid_from: string | null;
      valid_to: string | null;
      created_at: string | null;
    };
  };
  conflicts: ConflictItem[];
  moderation_actions: Array<Record<string, unknown>>;
};

type WikiPageDetailPayload = {
  page: {
    id: string;
    title: string;
    slug: string;
    entity_key: string | null;
    page_type: string | null;
    status: string;
    current_version: number | null;
  };
  latest_version: {
    version: number;
    markdown: string;
    source: string | null;
    created_by: string | null;
    created_at: string;
  } | null;
  sections: Array<{
    section_key: string;
    heading: string;
    order_index: number;
    statement_count: number;
  }>;
  statements: Array<{
    id: string;
    section_key: string | null;
    statement_text: string;
    claim_fingerprint: string;
    valid_from: string | null;
    valid_to: string | null;
    created_at: string;
  }>;
};

type WikiPageHistoryVersion = {
  version: number;
  source: string | null;
  created_by: string | null;
  change_summary: string | null;
  created_at: string;
  markdown_length: number;
  markdown?: string;
};

type WikiPageHistoryPayload = {
  page: {
    id: string;
    title: string;
    slug: string;
    entity_key: string | null;
    page_type: string | null;
    status: string;
    current_version: number | null;
  };
  versions: WikiPageHistoryVersion[];
};

type WikiPageSearchResult = {
  id: string;
  title: string;
  slug: string;
  entity_key: string | null;
  page_type: string | null;
  status: string;
  score: number;
};

type RetrievalExplainResult = {
  statement_id: string;
  statement_text: string;
  section_key: string | null;
  category: string | null;
  score: number;
  graph_hops: number | null;
  graph_boost: number;
  retrieval_reason: string;
  score_breakdown: {
    total: number;
    lexical: number;
    graph: number;
    lexical_components: {
      query_tokens_total: number;
      token_overlap_hits: number;
      token_overlap_ratio: number;
      statement_token_hits: number;
      statement_token_ratio: number;
      title_token_hits: number;
      title_token_ratio: number;
      slug_token_hits: number;
      slug_token_ratio: number;
      entity_exact_match: boolean;
      slug_exact_match: boolean;
      title_phrase_match: boolean;
      phrase_match: boolean;
    };
  };
  retrieval_confidence: number;
  confidence_breakdown: {
    overall: number;
    lexical_overlap: number;
    lexical_score_norm: number;
    exact_match_signal: number;
    phrase_signal: number;
    graph_support: number;
  };
  context_policy: {
    mode: string;
    eligible: boolean;
    blocked_by: string[];
    thresholds: {
      mode: string;
      min_confidence: number;
      min_total_score: number;
      min_lexical_score: number;
      min_token_overlap_ratio: number;
    };
  };
  page: {
    id: string;
    title: string;
    slug: string;
    entity_key: string | null;
    page_type: string | null;
  };
};

type RetrievalExplainPayload = {
  project_id: string;
  query: string;
  source: string;
  filters: {
    entity_key: string | null;
    category: string | null;
    page_type: string | null;
    related_entity_key: string | null;
  };
  results: RetrievalExplainResult[];
  graph_config: {
    max_graph_hops: number;
    boost_hop1: number;
    boost_hop2: number;
    boost_hop3: number;
    boost_other: number;
  };
  context_policy: {
    mode: string;
    min_confidence: number;
    min_total_score: number;
    min_lexical_score: number;
    min_token_overlap_ratio: number;
  };
  policy_filtered_out: number;
  explainability: {
    version: string;
    query_tokens: string[];
    related_entity_key: string | null;
    context_policy?: {
      mode: string;
      min_confidence: number;
      min_total_score: number;
      min_lexical_score: number;
      min_token_overlap_ratio: number;
    };
  };
};

type ModerationThroughputPayload = {
  project_id: string;
  window_hours: number;
  since: string;
  generated_at: string;
  health: "healthy" | "watch" | "critical" | string;
  alerts: string[];
  metrics: {
    actions_total: number;
    approvals: number;
    rejections: number;
    approval_rate: number | null;
    reviewers_active: number;
    processed_per_hour: number;
    drafts_created: number;
    net_backlog_delta: number;
    conflict_unblocks: number;
    latency_minutes: {
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
  };
  backlog: {
    open_total: number;
    pending_review: number;
    blocked_conflict: number;
  };
  top_reviewers: Array<{
    reviewed_by: string;
    actions_total: number;
    approvals: number;
    rejections: number;
  }>;
};

type WikiPageNode = {
  slug: string;
  title: string;
  draft_count: number;
  open_count: number;
  latest_draft_at: string | null;
};

type WikiSpaceNode = {
  key: string;
  title: string;
  page_count: number;
  open_count: number;
  latest_draft_at: string | null;
};

type ApproveFormState = {
  note: string;
  editedStatement: string;
  sectionKey: string;
  sectionHeading: string;
  sectionMode: "append" | "replace";
  sectionStatements: string;
  force: boolean;
};

type RejectFormState = {
  reason: string;
  dismissConflicts: boolean;
};

type PageTemplate = {
  key: string;
  title: string;
  description: string;
  sectionKey: string;
  sectionHeading: string;
  sectionMode: "append" | "replace";
  statements: string[];
};

type GuidedPageFormState = {
  spaceKey: string;
  title: string;
  slug: string;
  pageType: string;
  entityKey: string;
  sectionHeading: string;
  sectionStatement: string;
  changeSummary: string;
  status: "draft" | "published";
};

type DetailTab = "page" | "history" | "semantic" | "conflicts" | "patch" | "evidence" | "timeline";

type SavedView = {
  id: string;
  name: string;
  selectedSpaceKey: string | null;
  selectedPageSlug: string | null;
  status: string | null;
  openPagesOnly: boolean;
  pageFilter: string;
  draftFilter: string;
  created_at: string;
  updated_at: string;
};

type ReviewQueuePresetKey = "open_queue" | "sla_breaches" | "conflicts" | "high_confidence" | "full_timeline";

type ReviewQueuePreset = {
  key: ReviewQueuePresetKey;
  label: string;
  description: string;
};

type QuickModerationSource = "triage_lane" | "inbox_card" | "detail_header";

type TriagePriorityReason = {
  key: string;
  label: string;
  color: string;
  weight: number;
};

const STORAGE_KEY = "synapse_web_console_v4";

const DEFAULT_APPROVE_FORM: ApproveFormState = {
  note: "",
  editedStatement: "",
  sectionKey: "",
  sectionHeading: "",
  sectionMode: "append",
  sectionStatements: "",
  force: false,
};

const DEFAULT_REJECT_FORM: RejectFormState = {
  reason: "",
  dismissConflicts: true,
};

const DEFAULT_GUIDED_PAGE_FORM: GuidedPageFormState = {
  spaceKey: "operations",
  title: "",
  slug: "",
  pageType: "operations",
  entityKey: "",
  sectionHeading: "Overview",
  sectionStatement: "",
  changeSummary: "",
  status: "published",
};

const PAGE_TEMPLATES: PageTemplate[] = [
  {
    key: "access_policy_update",
    title: "Access Policy Update",
    description: "Use for new entry/permit/checkpoint rules.",
    sectionKey: "access_rules",
    sectionHeading: "Access Rules",
    sectionMode: "append",
    statements: ["Access requirements changed. Confirm credentials before dispatch."],
  },
  {
    key: "operations_incident",
    title: "Operations Incident",
    description: "Use for temporary outages, repairs, or operational constraints.",
    sectionKey: "ops_notes",
    sectionHeading: "Ops Notes",
    sectionMode: "append",
    statements: ["Operational incident active. Route planning must account for this constraint."],
  },
  {
    key: "customer_preference",
    title: "Customer Preference",
    description: "Use for stable customer communication/delivery preferences.",
    sectionKey: "customer_preferences",
    sectionHeading: "Customer Preferences",
    sectionMode: "append",
    statements: ["Preference confirmed. Apply consistently to future interactions."],
  },
];

const REVIEW_QUEUE_PRESETS: ReviewQueuePreset[] = [
  {
    key: "open_queue",
    label: "Open queue",
    description: "All pending and blocked drafts sorted by oldest first.",
  },
  {
    key: "sla_breaches",
    label: "SLA breaches",
    description: "Open drafts older than selected SLA threshold.",
  },
  {
    key: "conflicts",
    label: "Conflicts",
    description: "Drafts blocked by conflicts or conflict decisions.",
  },
  {
    key: "high_confidence",
    label: "High confidence",
    description: "Open drafts with confidence >= 0.85 for fast approvals.",
  },
  {
    key: "full_timeline",
    label: "Full timeline",
    description: "All drafts in scope sorted by newest updates.",
  },
];

const DOCS_BASE_URL = "https://github.com/maksbdev/synapse/blob/main";

const CORE_WALKTHROUGH_DOC_LINKS = [
  {
    label: "Getting Started",
    href: `${DOCS_BASE_URL}/docs/getting-started.md`,
    preview: "Bootstrap Synapse API, SDK ingest, and local wiki moderation in a single first-run flow.",
    highlights: ["Install + run local stack", "Ingest first insights", "Approve first wiki draft"],
  },
  {
    label: "Core Scope",
    href: `${DOCS_BASE_URL}/docs/core-product-scope.md`,
    preview: "Defines what stays in OSS core: SDK observer, synthesizer loop, wiki moderation, MCP retrieval.",
    highlights: ["Core loop boundaries", "Out-of-scope enterprise features", "Roadmap priorities"],
  },
  {
    label: "Web Console Guide",
    href: `${DOCS_BASE_URL}/apps/web/README.md`,
    preview: "Operator-focused UI guide for inbox triage, conflict resolution, and quick moderation actions.",
    highlights: ["Core vs advanced mode", "Draft inbox workflows", "Troubleshooting and e2e checks"],
  },
] as const;

type UiMode = "core" | "advanced";

function fmtDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function safeJson(value: unknown): string {
  return JSON.stringify(value ?? null, null, 2);
}

function randomKey(): string {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function statusColor(status: string): string {
  if (status === "pending_review") return "blue";
  if (status === "blocked_conflict") return "orange";
  if (status === "approved") return "green";
  if (status === "rejected") return "red";
  return "gray";
}

function isOpenReviewDraft(draft: DraftSummary): boolean {
  return draft.status === "pending_review" || draft.status === "blocked_conflict";
}

function draftAgeHours(draft: DraftSummary, referenceMs: number): number | null {
  const ts = new Date(draft.created_at).getTime();
  if (Number.isNaN(ts)) return null;
  const ageMs = Math.max(0, referenceMs - ts);
  return ageMs / (1000 * 60 * 60);
}

function formatHours(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value < 1) return "<1h";
  if (value < 24) return `${value.toFixed(1)}h`;
  return `${(value / 24).toFixed(1)}d`;
}

function formatMinutes(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value < 1) return "<1m";
  if (value < 60) return `${Math.round(value)}m`;
  if (value < 24 * 60) return `${(value / 60).toFixed(1)}h`;
  return `${(value / (24 * 60)).toFixed(1)}d`;
}

function formatPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatSeconds(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value < 1) return "<1s";
  if (value < 60) return `${Math.round(value)}s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes}m ${seconds}s`;
}

function moderationHealthColor(health: string | null | undefined): string {
  if (health === "critical") return "red";
  if (health === "watch") return "orange";
  return "teal";
}

function ageBadgeColor(ageHours: number | null, slaHours: number): string {
  if (ageHours == null || !Number.isFinite(ageHours)) return "gray";
  if (ageHours >= slaHours * 2) return "red";
  if (ageHours >= slaHours) return "orange";
  if (ageHours >= slaHours * 0.5) return "yellow";
  return "teal";
}

function triagePriorityScore(draft: DraftSummary, nowMs: number, slaHours: number): number {
  const age = draftAgeHours(draft, nowMs) ?? 0;
  let score = age;
  if (draft.status === "blocked_conflict") score += 200;
  if (draft.decision === "conflict") score += 120;
  if (age >= slaHours) score += 100;
  if (Number(draft.confidence) >= 0.9 && isOpenReviewDraft(draft)) score += 30;
  return score;
}

function triagePriorityReasons(draft: DraftSummary, nowMs: number, slaHours: number): TriagePriorityReason[] {
  const age = draftAgeHours(draft, nowMs);
  const reasons: TriagePriorityReason[] = [];
  if (draft.status === "blocked_conflict") {
    reasons.push({
      key: "blocked_conflict",
      label: "blocked conflict",
      color: "orange",
      weight: 200,
    });
  }
  if (draft.decision === "conflict") {
    reasons.push({
      key: "decision_conflict",
      label: "decision conflict",
      color: "grape",
      weight: 120,
    });
  }
  if (age != null && age >= slaHours) {
    reasons.push({
      key: "sla_breach",
      label: `sla breach >= ${slaHours}h`,
      color: "red",
      weight: 100,
    });
  } else if (age != null && age >= slaHours * 0.5) {
    reasons.push({
      key: "aging_queue",
      label: "aging queue",
      color: "yellow",
      weight: 40,
    });
  }
  if (Number(draft.confidence) >= 0.9 && isOpenReviewDraft(draft)) {
    reasons.push({
      key: "high_confidence",
      label: "high confidence",
      color: "teal",
      weight: 30,
    });
  }
  if (reasons.length === 0) {
    reasons.push({
      key: "open_queue",
      label: "open queue",
      color: "gray",
      weight: 0,
    });
  }
  return reasons.sort((a, b) => b.weight - a.weight);
}

function quickModerationSourceLabel(source: QuickModerationSource): string {
  if (source === "triage_lane") return "triage lane";
  if (source === "detail_header") return "draft detail";
  return "draft inbox";
}

function slugifySegment(value: string): string {
  const normalized = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized || "page";
}

function normalizeWikiSlug(rawSlug: string, fallbackTitle: string): string {
  const source = (rawSlug || "").trim().replace(/\\/g, "/");
  if (!source) return slugifySegment(fallbackTitle);
  const parts = source
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => slugifySegment(part));
  if (parts.length === 0) return slugifySegment(fallbackTitle);
  return parts.join("/");
}

function _sectionHeadingFromKeyForUi(sectionKey: string): string {
  return sectionKey
    .split("_")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

function pageGroupKey(slug: string | null | undefined): string {
  const value = String(slug || "").trim();
  if (!value) return "Ungrouped";
  if (!value.includes("/")) return "General";
  return value.split("/")[0];
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") {
    return true;
  }
  return target.isContentEditable;
}

async function apiFetch<T>(
  apiUrl: string,
  path: string,
  options?: {
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
    idempotencyKey?: string;
  },
): Promise<T> {
  const root = apiUrl.replace(/\/+$/, "");
  const response = await fetch(`${root}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options?.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}),
    },
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });
  const raw = await response.text();
  const payload = raw ? (JSON.parse(raw) as T) : ({} as T);
  if (!response.ok) {
    throw new Error(`${response.status} ${raw}`);
  }
  return payload;
}

type DiffToken = {
  value: string;
  kind: "same" | "added" | "removed";
};

function buildStatementDiff(beforeRaw: string, afterRaw: string): { before: DiffToken[]; after: DiffToken[] } {
  const before = beforeRaw || "";
  const after = afterRaw || "";
  const tokens = diffWords(before, after);
  const beforeLine: DiffToken[] = [];
  const afterLine: DiffToken[] = [];
  tokens.forEach((token) => {
    if (token.removed) {
      beforeLine.push({ value: token.value, kind: "removed" });
      return;
    }
    if (token.added) {
      afterLine.push({ value: token.value, kind: "added" });
      return;
    }
    beforeLine.push({ value: token.value, kind: "same" });
    afterLine.push({ value: token.value, kind: "same" });
  });
  return { before: beforeLine, after: afterLine };
}

function DiffLine({ label, tokens }: { label: string; tokens: DiffToken[] }) {
  return (
    <Box className="diff-line">
      <Text fw={700} size="sm" c="dimmed" mb={4}>
        {label}
      </Text>
      <Text className="diff-text">
        {tokens.length === 0 ? (
          <span className="diff-empty">—</span>
        ) : (
          tokens.map((token, index) => (
            <span key={`${label}-${index}`} className={`diff-token diff-${token.kind}`}>
              {token.value}
            </span>
          ))
        )}
      </Text>
    </Box>
  );
}

const LazyIntelligencePanel = lazy(() => import("./components/IntelligencePanel"));
const LazyTaskTrackerPanel = lazy(() => import("./components/TaskTrackerPanel"));
const LazyWikiPageCanvas = lazy(() => import("./components/WikiPageCanvas"));

export default function App() {
  const [apiUrl, setApiUrl] = useState("http://localhost:8080");
  const [projectId, setProjectId] = useState("");
  const [reviewer, setReviewer] = useState("ops_manager");
  const [uiMode, setUiMode] = useState<UiMode>("core");
  const [coreExpertControls, setCoreExpertControls] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedPageSlug, setSelectedPageSlug] = useState<string | null>(null);
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string | null>(null);
  const [pageFilter, setPageFilter] = useState("");
  const [draftFilter, setDraftFilter] = useState("");
  const [openPagesOnly, setOpenPagesOnly] = useState(false);
  const [collapsedSpaces, setCollapsedSpaces] = useState<Record<string, boolean>>({});
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<string | null>(null);
  const [savedViewName, setSavedViewName] = useState("");
  const [pinnedPageSlugs, setPinnedPageSlugs] = useState<string[]>([]);
  const [reviewQueuePreset, setReviewQueuePreset] = useState<ReviewQueuePresetKey>("open_queue");
  const [reviewSlaHours, setReviewSlaHours] = useState(24);
  const [bulkSelectedDraftIds, setBulkSelectedDraftIds] = useState<string[]>([]);
  const [bulkForceApprove, setBulkForceApprove] = useState(false);
  const [bulkApproveNote, setBulkApproveNote] = useState("");
  const [bulkRejectReason, setBulkRejectReason] = useState("");
  const [draftDetail, setDraftDetail] = useState<DraftDetailPayload | null>(null);
  const [selectedPageDetail, setSelectedPageDetail] = useState<WikiPageDetailPayload | null>(null);
  const [pageHistory, setPageHistory] = useState<WikiPageHistoryPayload | null>(null);
  const [loadingPageHistory, setLoadingPageHistory] = useState(false);
  const [historyBaseVersion, setHistoryBaseVersion] = useState<string | null>(null);
  const [historyTargetVersion, setHistoryTargetVersion] = useState<string | null>(null);
  const [guidedPageForm, setGuidedPageForm] = useState<GuidedPageFormState>(DEFAULT_GUIDED_PAGE_FORM);
  const [guidedPageMatches, setGuidedPageMatches] = useState<WikiPageSearchResult[]>([]);
  const [searchingGuidedMatches, setSearchingGuidedMatches] = useState(false);
  const [retrievalExplainQuery, setRetrievalExplainQuery] = useState("");
  const [retrievalExplainRelatedEntity, setRetrievalExplainRelatedEntity] = useState("");
  const [retrievalExplainPolicyMode, setRetrievalExplainPolicyMode] = useState<"off" | "advisory" | "enforced">(
    "advisory",
  );
  const [retrievalExplainMinConfidence, setRetrievalExplainMinConfidence] = useState("0.45");
  const [retrievalExplainMinTotalScore, setRetrievalExplainMinTotalScore] = useState("0.20");
  const [retrievalExplainMinLexicalScore, setRetrievalExplainMinLexicalScore] = useState("0.08");
  const [retrievalExplainMinTokenOverlap, setRetrievalExplainMinTokenOverlap] = useState("0.15");
  const [retrievalExplainResults, setRetrievalExplainResults] = useState<RetrievalExplainResult[]>([]);
  const [retrievalExplainGraphConfig, setRetrievalExplainGraphConfig] = useState<RetrievalExplainPayload["graph_config"] | null>(
    null,
  );
  const [retrievalExplainContextPolicy, setRetrievalExplainContextPolicy] = useState<
    RetrievalExplainPayload["context_policy"] | null
  >(null);
  const [retrievalExplainPolicyFilteredOut, setRetrievalExplainPolicyFilteredOut] = useState(0);
  const [walkthroughTelemetry, setWalkthroughTelemetry] = useState(() => ({
    startedAtMs: Date.now(),
    stepCompletedAtMs: {
      workspace: null as number | null,
      inbox: null as number | null,
      firstReview: null as number | null,
    },
    actionCounts: {
      useDemoValues: 0,
      loadDraftQueue: 0,
      selectDraft: 0,
    },
  }));
  const [coreIntentSignals, setCoreIntentSignals] = useState(() => ({
    startedAtMs: Date.now(),
    triageOpenCount: 0,
    triageOpenedDraftIds: [] as string[],
    quickModeration: {
      approve: 0,
      reject: 0,
      bySource: {
        triage_lane: 0,
        inbox_card: 0,
        detail_header: 0,
      } as Record<QuickModerationSource, number>,
    },
    lastAction: null as { label: string; timestampMs: number } | null,
  }));
  const [loadingRetrievalExplain, setLoadingRetrievalExplain] = useState(false);
  const [moderationThroughput, setModerationThroughput] = useState<ModerationThroughputPayload | null>(null);
  const [loadingModerationThroughput, setLoadingModerationThroughput] = useState(false);
  const [creatingPage, setCreatingPage] = useState(false);
  const [conflictExplain, setConflictExplain] = useState<ConflictExplainPayload | null>(null);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingPageDetail, setLoadingPageDetail] = useState(false);
  const [loadingConflictExplain, setLoadingConflictExplain] = useState(false);
  const [runningAction, setRunningAction] = useState(false);
  const [armedRiskActionKey, setArmedRiskActionKey] = useState<string | null>(null);
  const [approveForm, setApproveForm] = useState<ApproveFormState>(DEFAULT_APPROVE_FORM);
  const [rejectForm, setRejectForm] = useState<RejectFormState>(DEFAULT_REJECT_FORM);
  const [detailTab, setDetailTab] = useState<DetailTab>("semantic");
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string | null>(null);
  const [selectedTocSectionKey, setSelectedTocSectionKey] = useState<string | null>(null);
  const showExpertModerationControls = uiMode === "advanced" || coreExpertControls;

  const pageNodes = useMemo<WikiPageNode[]>(() => {
    const map = new Map<string, WikiPageNode>();
    for (const draft of drafts) {
      const slug = String(draft.page.slug || "").trim();
      if (!slug) continue;
      const current =
        map.get(slug) ||
        ({
          slug,
          title: draft.page.title || slug,
          draft_count: 0,
          open_count: 0,
          latest_draft_at: null,
        } satisfies WikiPageNode);
      current.draft_count += 1;
      if (draft.status === "pending_review" || draft.status === "blocked_conflict") {
        current.open_count += 1;
      }
      if (current.latest_draft_at == null || String(draft.created_at) > String(current.latest_draft_at)) {
        current.latest_draft_at = draft.created_at;
      }
      if (!current.title && draft.page.title) {
        current.title = draft.page.title;
      }
      map.set(slug, current);
    }
    return [...map.values()].sort((a, b) => {
      if (a.open_count !== b.open_count) return b.open_count - a.open_count;
      if (String(a.latest_draft_at || "") !== String(b.latest_draft_at || "")) {
        return String(b.latest_draft_at || "").localeCompare(String(a.latest_draft_at || ""));
      }
      return String(a.title || a.slug).localeCompare(String(b.title || b.slug));
    });
  }, [drafts]);

  const pageGroups = useMemo(() => {
    const selectedSpace = selectedSpaceKey;
    const filter = pageFilter.trim().toLowerCase();
    const grouped = new Map<string, WikiPageNode[]>();
    for (const page of pageNodes) {
      const groupKey = pageGroupKey(page.slug);
      if (selectedSpace && groupKey !== selectedSpace) continue;
      if (openPagesOnly && page.open_count <= 0) continue;
      if (filter) {
        const haystack = `${page.title} ${page.slug}`.toLowerCase();
        if (!haystack.includes(filter)) continue;
      }
      const key = groupKey;
      const rows = grouped.get(key) || [];
      rows.push(page);
      grouped.set(key, rows);
    }
    return [...grouped.entries()]
      .map(([group, rows]) => [
        group,
        [...rows].sort((a, b) => {
          if (a.open_count !== b.open_count) return b.open_count - a.open_count;
          if (String(a.latest_draft_at || "") !== String(b.latest_draft_at || "")) {
            return String(b.latest_draft_at || "").localeCompare(String(a.latest_draft_at || ""));
          }
          return String(a.title || a.slug).localeCompare(String(b.title || b.slug));
        }),
      ] as const)
      .sort((a, b) => {
        if (a[0] === b[0]) return 0;
        if (selectedSpace && a[0] === selectedSpace) return -1;
        if (selectedSpace && b[0] === selectedSpace) return 1;
        return a[0].localeCompare(b[0]);
      });
  }, [openPagesOnly, pageFilter, pageNodes, selectedSpaceKey]);

  const spaceNodes = useMemo<WikiSpaceNode[]>(() => {
    const map = new Map<string, WikiSpaceNode>();
    for (const page of pageNodes) {
      const key = pageGroupKey(page.slug);
      const current =
        map.get(key) ||
        ({
          key,
          title: key,
          page_count: 0,
          open_count: 0,
          latest_draft_at: null,
        } satisfies WikiSpaceNode);
      current.page_count += 1;
      current.open_count += page.open_count;
      if (current.latest_draft_at == null || String(page.latest_draft_at || "") > String(current.latest_draft_at || "")) {
        current.latest_draft_at = page.latest_draft_at;
      }
      map.set(key, current);
    }
    return [...map.values()].sort((a, b) => {
      if (a.open_count !== b.open_count) return b.open_count - a.open_count;
      if (String(a.latest_draft_at || "") !== String(b.latest_draft_at || "")) {
        return String(b.latest_draft_at || "").localeCompare(String(a.latest_draft_at || ""));
      }
      return a.title.localeCompare(b.title);
    });
  }, [pageNodes]);

  const recentPages = useMemo(() => {
    return [...pageNodes]
      .filter((item) => !selectedSpaceKey || pageGroupKey(item.slug) === selectedSpaceKey)
      .sort((a, b) => String(b.latest_draft_at || "").localeCompare(String(a.latest_draft_at || "")))
      .slice(0, 5);
  }, [pageNodes, selectedSpaceKey]);

  const pinnedPages = useMemo(() => {
    return pinnedPageSlugs
      .map((slug) => pageNodes.find((item) => item.slug === slug))
      .filter((item): item is WikiPageNode => Boolean(item));
  }, [pageNodes, pinnedPageSlugs]);

  const scopedDrafts = useMemo(
    () =>
      drafts.filter((item) => {
        if (selectedPageSlug && item.page.slug !== selectedPageSlug) return false;
        if (selectedSpaceKey && pageGroupKey(item.page.slug) !== selectedSpaceKey) return false;
        const draftNeedle = draftFilter.trim().toLowerCase();
        if (!draftNeedle) return true;
        const haystack = `${item.page.title || ""} ${item.page.slug || ""} ${item.decision} ${item.section_key || ""}`.toLowerCase();
        return haystack.includes(draftNeedle);
      }),
    [draftFilter, drafts, selectedPageSlug, selectedSpaceKey],
  );

  const visibleDrafts = useMemo(() => {
    const activeQueuePreset: ReviewQueuePresetKey =
      uiMode === "advanced" || coreExpertControls ? reviewQueuePreset : "open_queue";
    const nowMs = Date.now();
    let next = [...scopedDrafts];
    switch (activeQueuePreset) {
      case "open_queue":
        next = next
          .filter((item) => isOpenReviewDraft(item))
          .sort((a, b) => (draftAgeHours(b, nowMs) ?? -1) - (draftAgeHours(a, nowMs) ?? -1));
        break;
      case "sla_breaches":
        next = next
          .filter((item) => isOpenReviewDraft(item) && (draftAgeHours(item, nowMs) ?? -1) >= reviewSlaHours)
          .sort((a, b) => (draftAgeHours(b, nowMs) ?? -1) - (draftAgeHours(a, nowMs) ?? -1));
        break;
      case "conflicts":
        next = next
          .filter((item) => item.status === "blocked_conflict" || item.decision === "conflict")
          .sort((a, b) => (draftAgeHours(b, nowMs) ?? -1) - (draftAgeHours(a, nowMs) ?? -1));
        break;
      case "high_confidence":
        next = next
          .filter((item) => isOpenReviewDraft(item) && Number(item.confidence) >= 0.85)
          .sort((a, b) => {
            if (Number(a.confidence) !== Number(b.confidence)) {
              return Number(b.confidence) - Number(a.confidence);
            }
            return (draftAgeHours(b, nowMs) ?? -1) - (draftAgeHours(a, nowMs) ?? -1);
          });
        break;
      case "full_timeline":
        next = next.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
        break;
      default:
        next = next.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
        break;
    }
    return next;
  }, [coreExpertControls, reviewQueuePreset, reviewSlaHours, scopedDrafts, uiMode]);

  const selectedIndex = useMemo(
    () => (selectedDraftId ? visibleDrafts.findIndex((item) => item.id === selectedDraftId) : -1),
    [visibleDrafts, selectedDraftId],
  );

  const openPageOrder = useMemo(() => {
    const scope = pageNodes.filter((item) => (!selectedSpaceKey ? true : pageGroupKey(item.slug) === selectedSpaceKey));
    const openScoped = scope.filter((item) => item.open_count > 0);
    return openScoped.length > 0 ? openScoped : scope;
  }, [pageNodes, selectedSpaceKey]);

  const conflictPageOrder = useMemo(() => {
    const conflictSlugs = new Set(
      drafts
        .filter((item) => item.status === "blocked_conflict" || item.decision === "conflict")
        .map((item) => String(item.page.slug || "").trim())
        .filter(Boolean),
    );
    return pageNodes.filter((item) => conflictSlugs.has(item.slug));
  }, [drafts, pageNodes]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        apiUrl?: string;
        projectId?: string;
        reviewer?: string;
        uiMode?: UiMode;
        coreExpertControls?: boolean;
        status?: string | null;
        selectedSpaceKey?: string | null;
        openPagesOnly?: boolean;
        savedViews?: SavedView[];
        selectedViewId?: string | null;
        pinnedPageSlugs?: string[];
        bulkForceApprove?: boolean;
        reviewQueuePreset?: ReviewQueuePresetKey;
        reviewSlaHours?: number;
      };
      if (parsed.apiUrl) setApiUrl(parsed.apiUrl);
      if (parsed.projectId) setProjectId(parsed.projectId);
      if (parsed.reviewer) setReviewer(parsed.reviewer);
      if (parsed.uiMode === "core" || parsed.uiMode === "advanced") {
        setUiMode(parsed.uiMode);
      }
      if (typeof parsed.coreExpertControls === "boolean") {
        setCoreExpertControls(parsed.coreExpertControls);
      }
      if (typeof parsed.status === "string" || parsed.status === null) setStatus(parsed.status);
      if (typeof parsed.selectedSpaceKey === "string" || parsed.selectedSpaceKey === null) {
        setSelectedSpaceKey(parsed.selectedSpaceKey);
      }
      if (typeof parsed.openPagesOnly === "boolean") {
        setOpenPagesOnly(parsed.openPagesOnly);
      }
      if (Array.isArray(parsed.savedViews)) {
        setSavedViews(
          parsed.savedViews.filter((item): item is SavedView => {
            return Boolean(item && typeof item.id === "string" && typeof item.name === "string");
          }),
        );
      }
      if (typeof parsed.selectedViewId === "string" || parsed.selectedViewId === null) {
        setSelectedViewId(parsed.selectedViewId);
      }
      if (Array.isArray(parsed.pinnedPageSlugs)) {
        setPinnedPageSlugs(parsed.pinnedPageSlugs.filter((item): item is string => typeof item === "string"));
      }
      if (typeof parsed.bulkForceApprove === "boolean") {
        setBulkForceApprove(parsed.bulkForceApprove);
      }
      if (typeof parsed.reviewQueuePreset === "string") {
        const knownPreset = REVIEW_QUEUE_PRESETS.some((item) => item.key === parsed.reviewQueuePreset);
        if (knownPreset) {
          setReviewQueuePreset(parsed.reviewQueuePreset);
        }
      }
      if (typeof parsed.reviewSlaHours === "number" && Number.isFinite(parsed.reviewSlaHours)) {
        setReviewSlaHours(Math.max(1, Math.min(168, Math.round(parsed.reviewSlaHours))));
      }
    } catch {
      // ignore corrupt local storage
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        apiUrl,
        projectId,
        reviewer,
        uiMode,
        coreExpertControls,
        status,
        selectedSpaceKey,
        openPagesOnly,
        savedViews,
        selectedViewId,
        pinnedPageSlugs,
        bulkForceApprove,
        reviewQueuePreset,
        reviewSlaHours,
      }),
    );
  }, [
    apiUrl,
    bulkForceApprove,
    coreExpertControls,
    openPagesOnly,
    pinnedPageSlugs,
    projectId,
    reviewer,
    reviewQueuePreset,
    reviewSlaHours,
    savedViews,
    selectedSpaceKey,
    selectedViewId,
    status,
    uiMode,
  ]);

  const loadModerationThroughput = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setModerationThroughput(null);
      return;
    }
    setLoadingModerationThroughput(true);
    try {
      const payload = await apiFetch<ModerationThroughputPayload>(
        apiUrl,
        `/v1/wiki/moderation/throughput?project_id=${encodeURIComponent(project)}&window_hours=24&top_reviewers=4`,
      );
      setModerationThroughput(payload);
    } catch {
      setModerationThroughput(null);
    } finally {
      setLoadingModerationThroughput(false);
    }
  }, [apiUrl, projectId]);

  const loadDrafts = useCallback(async () => {
    if (!projectId.trim()) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before loading drafts.",
      });
      return;
    }
    setLoadingDrafts(true);
    const throughputPromise = showExpertModerationControls ? loadModerationThroughput() : Promise.resolve();
    if (!showExpertModerationControls) {
      setModerationThroughput(null);
    }
    try {
      const statusQuery = status ? `&status=${encodeURIComponent(status)}` : "";
      const data = await apiFetch<{ drafts: DraftSummary[] }>(
        apiUrl,
        `/v1/wiki/drafts?project_id=${encodeURIComponent(projectId)}${statusQuery}&limit=120`,
      );
      setDrafts(data.drafts ?? []);
      if (selectedDraftId && !data.drafts.some((item) => item.id === selectedDraftId)) {
        setSelectedDraftId(null);
        setDraftDetail(null);
        setConflictExplain(null);
      }
      if (!selectedDraftId && data.drafts.length > 0) {
        setSelectedDraftId(data.drafts[0].id);
      }
      await throughputPromise;
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Failed to load drafts",
        message: String(error),
      });
    } finally {
      setLoadingDrafts(false);
    }
  }, [apiUrl, loadModerationThroughput, projectId, selectedDraftId, showExpertModerationControls, status]);

  const loadDraftDetail = useCallback(
    async (draftId: string) => {
      setLoadingDetail(true);
      try {
        const payload = await apiFetch<DraftDetailPayload>(
          apiUrl,
          `/v1/wiki/drafts/${encodeURIComponent(draftId)}?project_id=${encodeURIComponent(projectId)}`,
        );
        setDraftDetail(payload);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Failed to load draft detail",
          message: String(error),
        });
      } finally {
        setLoadingDetail(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadConflictExplain = useCallback(
    async (draftId: string) => {
      setLoadingConflictExplain(true);
      try {
        const payload = await apiFetch<ConflictExplainPayload>(
          apiUrl,
          `/v1/wiki/drafts/${encodeURIComponent(draftId)}/conflicts/explain?project_id=${encodeURIComponent(projectId)}&limit=25`,
        );
        setConflictExplain(payload);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Failed to load conflict explain",
          message: String(error),
        });
        setConflictExplain(null);
      } finally {
        setLoadingConflictExplain(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageDetail = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setSelectedPageDetail(null);
        return;
      }
      setLoadingPageDetail(true);
      try {
        const payload = await apiFetch<WikiPageDetailPayload>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}?project_id=${encodeURIComponent(projectId)}`,
        );
        setSelectedPageDetail(payload);
      } catch {
        // keep core flow resilient even when page endpoint is unavailable in local/mocked env
        setSelectedPageDetail(null);
      } finally {
        setLoadingPageDetail(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageHistory = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageHistory(null);
        return;
      }
      setLoadingPageHistory(true);
      try {
        const payload = await apiFetch<WikiPageHistoryPayload>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/history?project_id=${encodeURIComponent(projectId)}&limit=20&include_markdown=true`,
        );
        setPageHistory(payload);
      } catch {
        setPageHistory(null);
      } finally {
        setLoadingPageHistory(false);
      }
    },
    [apiUrl, projectId],
  );

  useEffect(() => {
    if (visibleDrafts.length === 0) {
      setSelectedDraftId(null);
      setDraftDetail(null);
      setConflictExplain(null);
      return;
    }
    if (!selectedDraftId || !visibleDrafts.some((item) => item.id === selectedDraftId)) {
      setSelectedDraftId(visibleDrafts[0].id);
    }
  }, [selectedDraftId, visibleDrafts]);

  useEffect(() => {
    if (!selectedPageSlug) return;
    if (!pageNodes.some((item) => item.slug === selectedPageSlug)) {
      setSelectedPageSlug(null);
    }
  }, [pageNodes, selectedPageSlug]);

  useEffect(() => {
    if (!selectedPageSlug || !selectedSpaceKey) return;
    if (pageGroupKey(selectedPageSlug) !== selectedSpaceKey) {
      setSelectedPageSlug(null);
    }
  }, [selectedPageSlug, selectedSpaceKey]);

  useEffect(() => {
    if (Object.keys(collapsedSpaces).length === 0) return;
    const valid = new Set(spaceNodes.map((item) => item.key));
    const next: Record<string, boolean> = {};
    let changed = false;
    for (const [key, value] of Object.entries(collapsedSpaces)) {
      if (valid.has(key)) {
        next[key] = value;
      } else {
        changed = true;
      }
    }
    if (changed) {
      setCollapsedSpaces(next);
    }
  }, [collapsedSpaces, spaceNodes]);

  useEffect(() => {
    if (!selectedViewId) return;
    if (!savedViews.some((item) => item.id === selectedViewId)) {
      setSelectedViewId(null);
    }
  }, [savedViews, selectedViewId]);

  useEffect(() => {
    if (pinnedPageSlugs.length === 0) return;
    const valid = new Set(pageNodes.map((item) => item.slug));
    const next = pinnedPageSlugs.filter((slug) => valid.has(slug));
    if (next.length !== pinnedPageSlugs.length) {
      setPinnedPageSlugs(next);
    }
  }, [pageNodes, pinnedPageSlugs]);

  useEffect(() => {
    if (bulkSelectedDraftIds.length === 0) return;
    const valid = new Set(drafts.map((item) => item.id));
    const next = bulkSelectedDraftIds.filter((id) => valid.has(id));
    if (next.length !== bulkSelectedDraftIds.length) {
      setBulkSelectedDraftIds(next);
    }
  }, [bulkSelectedDraftIds, drafts]);

  useEffect(() => {
    if (!selectedDraftId) {
      setDraftDetail(null);
      setConflictExplain(null);
      return;
    }
    setDetailTab("semantic");
    void loadDraftDetail(selectedDraftId);
    void loadConflictExplain(selectedDraftId);
  }, [selectedDraftId, loadDraftDetail, loadConflictExplain]);

  useEffect(() => {
    if (showExpertModerationControls) {
      return;
    }
    if (detailTab === "page" || detailTab === "history" || detailTab === "patch" || detailTab === "timeline") {
      setDetailTab("semantic");
    }
  }, [detailTab, showExpertModerationControls]);

  useEffect(() => {
    if (!selectedPageSlug) {
      setSelectedPageDetail(null);
      setPageHistory(null);
      return;
    }
    void loadPageDetail(selectedPageSlug);
    void loadPageHistory(selectedPageSlug);
  }, [loadPageDetail, loadPageHistory, selectedPageSlug]);

  useEffect(() => {
    const sections = selectedPageDetail?.sections ?? [];
    if (sections.length === 0) {
      setSelectedTocSectionKey(null);
      return;
    }
    if (!selectedTocSectionKey || !sections.some((section) => section.section_key === selectedTocSectionKey)) {
      setSelectedTocSectionKey(sections[0].section_key);
    }
  }, [selectedPageDetail, selectedTocSectionKey]);

  useEffect(() => {
    const versions = pageHistory?.versions ?? [];
    if (versions.length === 0) {
      setHistoryBaseVersion(null);
      setHistoryTargetVersion(null);
      return;
    }
    const current = String(versions[0].version);
    const previous = String(versions[Math.min(1, versions.length - 1)].version);
    setHistoryTargetVersion((prev) => (prev && versions.some((item) => String(item.version) === prev) ? prev : current));
    setHistoryBaseVersion((prev) => (prev && versions.some((item) => String(item.version) === prev) ? prev : previous));
  }, [pageHistory]);

  const canModerate = useMemo(() => {
    return Boolean(selectedDraftId && reviewer.trim() && projectId.trim()) && !runningAction;
  }, [selectedDraftId, reviewer, projectId, runningAction]);

  useEffect(() => {
    if (!armedRiskActionKey) return;
    const timer = window.setTimeout(() => {
      setArmedRiskActionKey((prev) => (prev === armedRiskActionKey ? null : prev));
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [armedRiskActionKey]);

  useEffect(() => {
    setArmedRiskActionKey(null);
  }, [selectedDraftId]);

  const requireRiskConfirmation = useCallback(
    (actionKey: string, actionLabel: string): boolean => {
      if (armedRiskActionKey === actionKey) {
        setArmedRiskActionKey(null);
        return true;
      }
      setArmedRiskActionKey(actionKey);
      notifications.show({
        color: "orange",
        title: "Confirm high-impact moderation action",
        message: `Click "${actionLabel}" again within 6s to proceed.`,
      });
      return false;
    },
    [armedRiskActionKey],
  );

  const approveDraft = useCallback(
    async (mode: "form" | "quick_force" = "form") => {
      if (!selectedDraftId) return;
      const quickForce = mode === "quick_force";
      const forceApprove = quickForce ? true : approveForm.force;
      if (
        forceApprove &&
        !requireRiskConfirmation(
          quickForce ? `force-approve:${selectedDraftId}` : `force-approve-form:${selectedDraftId}`,
          quickForce ? "Force Approve" : "Approve Draft",
        )
      ) {
        return;
      }
      setRunningAction(true);
      try {
        const statements = approveForm.sectionStatements
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean);

        const payload: Record<string, unknown> = {
          project_id: projectId,
          reviewed_by: reviewer.trim(),
          note:
            quickForce
              ? `Conflict resolved with force-approve by ${reviewer.trim()}.`
              : approveForm.note.trim() || null,
          force: forceApprove,
        };

        if (!quickForce && approveForm.editedStatement.trim()) {
          payload.edited_statement_text = approveForm.editedStatement.trim();
        }
        if (!quickForce && approveForm.sectionKey.trim() && statements.length > 0) {
          payload.section_edits = [
            {
              section_key: approveForm.sectionKey.trim(),
              heading: approveForm.sectionHeading.trim() || null,
              mode: approveForm.sectionMode,
              statements,
            },
          ];
        }

        const response = await apiFetch<{ snapshot_id?: string }>(
          apiUrl,
          `/v1/wiki/drafts/${encodeURIComponent(selectedDraftId)}/approve`,
          {
            method: "POST",
            body: payload,
            idempotencyKey: randomKey(),
          },
        );
        notifications.show({
          color: "green",
          title: quickForce ? "Conflict force-approved" : "Draft approved",
          message: `Snapshot: ${response.snapshot_id ?? "created"}`,
        });
        if (!quickForce) {
          setApproveForm(DEFAULT_APPROVE_FORM);
        }
        await loadDrafts();
        await loadDraftDetail(selectedDraftId);
        await loadConflictExplain(selectedDraftId);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Approve failed",
          message: String(error),
        });
      } finally {
        setRunningAction(false);
      }
    },
    [
      apiUrl,
      approveForm,
      loadConflictExplain,
      loadDraftDetail,
      loadDrafts,
      projectId,
      requireRiskConfirmation,
      reviewer,
      selectedDraftId,
    ],
  );

  const rejectDraft = useCallback(
    async (mode: "form" | "quick_dismiss" = "form") => {
      if (!selectedDraftId) return;
      const quickDismiss = mode === "quick_dismiss";
      const dismissConflicts = quickDismiss ? true : rejectForm.dismissConflicts;
      if (
        dismissConflicts &&
        !requireRiskConfirmation(
          quickDismiss ? `reject-dismiss:${selectedDraftId}` : `reject-dismiss-form:${selectedDraftId}`,
          quickDismiss ? "Reject + Dismiss" : "Reject Draft",
        )
      ) {
        return;
      }
      setRunningAction(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/drafts/${encodeURIComponent(selectedDraftId)}/reject`, {
          method: "POST",
          body: {
            project_id: projectId,
            reviewed_by: reviewer.trim(),
            reason: quickDismiss ? "Conflict rejected via quick resolver." : rejectForm.reason.trim() || null,
            dismiss_conflicts: dismissConflicts,
          },
          idempotencyKey: randomKey(),
        });
        notifications.show({
          color: "orange",
          title: quickDismiss ? "Conflict rejected" : "Draft rejected",
          message: `Draft ${selectedDraftId} rejected.`,
        });
        if (!quickDismiss) {
          setRejectForm(DEFAULT_REJECT_FORM);
        }
        await loadDrafts();
        await loadDraftDetail(selectedDraftId);
        await loadConflictExplain(selectedDraftId);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Reject failed",
          message: String(error),
        });
      } finally {
        setRunningAction(false);
      }
    },
    [
      apiUrl,
      loadConflictExplain,
      loadDraftDetail,
      loadDrafts,
      projectId,
      requireRiskConfirmation,
      rejectForm.dismissConflicts,
      rejectForm.reason,
      reviewer,
      selectedDraftId,
    ],
  );

  const openDraftFromTriage = useCallback((draft: DraftSummary) => {
    setSelectedDraftId(draft.id);
    const slug = String(draft.page.slug || "").trim();
    if (slug) {
      setSelectedPageSlug(slug);
      setSelectedSpaceKey(pageGroupKey(slug));
    }
    setDetailTab("semantic");
    setCoreIntentSignals((prev) => {
      const nextUniqueDraftIds = prev.triageOpenedDraftIds.includes(draft.id)
        ? prev.triageOpenedDraftIds
        : [...prev.triageOpenedDraftIds, draft.id].slice(-24);
      return {
        ...prev,
        triageOpenCount: prev.triageOpenCount + 1,
        triageOpenedDraftIds: nextUniqueDraftIds,
        lastAction: {
          label: "triage open draft",
          timestampMs: Date.now(),
        },
      };
    });
  }, []);

  const quickModerateDraft = useCallback(
    async (draft: DraftSummary, action: "approve" | "reject", source: QuickModerationSource = "inbox_card") => {
      if (!projectId.trim() || !reviewer.trim()) {
        notifications.show({
          color: "red",
          title: "Missing reviewer or project",
          message: "Set Project ID and Reviewer before quick moderation.",
        });
        return;
      }
      if (!isOpenReviewDraft(draft)) {
        notifications.show({
          color: "gray",
          title: "Draft already resolved",
          message: "Quick moderation is only available for open drafts.",
        });
        return;
      }
      setSelectedDraftId(draft.id);
      setRunningAction(true);
      try {
        if (action === "approve") {
          const quickForce = draft.status === "blocked_conflict" || draft.decision === "conflict";
          const response = await apiFetch<{ snapshot_id?: string }>(
            apiUrl,
            `/v1/wiki/drafts/${encodeURIComponent(draft.id)}/approve`,
            {
              method: "POST",
              body: {
                project_id: projectId,
                reviewed_by: reviewer.trim(),
                note: quickForce
                  ? `Conflict resolved with force-approve by ${reviewer.trim()}.`
                  : `Quick approved from ${quickModerationSourceLabel(source)} by ${reviewer.trim()}.`,
                force: quickForce,
              },
              idempotencyKey: randomKey(),
            },
          );
          notifications.show({
            color: "green",
            title: quickForce ? "Conflict force-approved" : "Draft quick-approved",
            message: `Snapshot: ${response.snapshot_id ?? "created"}`,
          });
        } else {
          const quickDismiss = draft.status === "blocked_conflict" || draft.decision === "conflict";
          await apiFetch(apiUrl, `/v1/wiki/drafts/${encodeURIComponent(draft.id)}/reject`, {
            method: "POST",
            body: {
              project_id: projectId,
              reviewed_by: reviewer.trim(),
              reason: quickDismiss
                ? "Conflict rejected via quick resolver."
                : `Quick rejected from ${quickModerationSourceLabel(source)} by ${reviewer.trim()}.`,
              dismiss_conflicts: quickDismiss,
            },
            idempotencyKey: randomKey(),
          });
          notifications.show({
            color: "orange",
            title: "Draft quick-rejected",
            message: `Draft ${draft.id} rejected.`,
          });
        }
        setCoreIntentSignals((prev) => ({
          ...prev,
          quickModeration: {
            approve: action === "approve" ? prev.quickModeration.approve + 1 : prev.quickModeration.approve,
            reject: action === "reject" ? prev.quickModeration.reject + 1 : prev.quickModeration.reject,
            bySource: {
              ...prev.quickModeration.bySource,
              [source]: prev.quickModeration.bySource[source] + 1,
            },
          },
          lastAction: {
            label: `${quickModerationSourceLabel(source)} ${action}`,
            timestampMs: Date.now(),
          },
        }));

        await loadDrafts();
        if (selectedDraftId === draft.id) {
          await loadDraftDetail(draft.id);
          await loadConflictExplain(draft.id);
        }
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Quick moderation failed",
          message: String(error),
        });
      } finally {
        setRunningAction(false);
      }
    },
    [
      apiUrl,
      loadConflictExplain,
      loadDraftDetail,
      loadDrafts,
      projectId,
      reviewer,
      selectedDraftId,
    ],
  );

  const selectPrevDraft = useCallback(() => {
    if (visibleDrafts.length === 0) return;
    const current = selectedIndex >= 0 ? selectedIndex : 0;
    const prev = current <= 0 ? visibleDrafts.length - 1 : current - 1;
    setSelectedDraftId(visibleDrafts[prev].id);
  }, [selectedIndex, visibleDrafts]);

  const selectNextDraft = useCallback(() => {
    if (visibleDrafts.length === 0) return;
    const current = selectedIndex >= 0 ? selectedIndex : -1;
    const next = current >= visibleDrafts.length - 1 ? 0 : current + 1;
    setSelectedDraftId(visibleDrafts[next].id);
  }, [selectedIndex, visibleDrafts]);

  const applyPageTemplate = useCallback(
    (templateKey: string) => {
      const template = PAGE_TEMPLATES.find((item) => item.key === templateKey);
      if (!template) return;
      setApproveForm((prev) => ({
        ...prev,
        sectionKey: template.sectionKey,
        sectionHeading: template.sectionHeading,
        sectionMode: template.sectionMode,
        sectionStatements: template.statements.join("\n"),
      }));
      setSelectedTemplateKey(template.key);
      notifications.show({
        color: "teal",
        title: "Template applied",
        message: `${template.title} loaded into Approve form.`,
      });
    },
    [setApproveForm],
  );

  const jumpToPageFromList = useCallback(
    (pages: WikiPageNode[], direction: "next" | "prev") => {
      if (pages.length === 0) return;
      const currentIndex = selectedPageSlug ? pages.findIndex((item) => item.slug === selectedPageSlug) : -1;
      const nextIndex =
        direction === "next"
          ? currentIndex < 0 || currentIndex >= pages.length - 1
            ? 0
            : currentIndex + 1
          : currentIndex <= 0
            ? pages.length - 1
            : currentIndex - 1;
      const nextPage = pages[nextIndex];
      setSelectedSpaceKey(pageGroupKey(nextPage.slug));
      setSelectedPageSlug(nextPage.slug);
      const firstDraft = drafts.find((item) => item.page.slug === nextPage.slug);
      if (firstDraft) {
        setSelectedDraftId(firstDraft.id);
      }
    },
    [drafts, selectedPageSlug],
  );

  const jumpToNextPage = useCallback(() => {
    jumpToPageFromList(openPageOrder, "next");
  }, [jumpToPageFromList, openPageOrder]);

  const jumpToPrevPage = useCallback(() => {
    jumpToPageFromList(openPageOrder, "prev");
  }, [jumpToPageFromList, openPageOrder]);

  const jumpToNextConflictPage = useCallback(() => {
    jumpToPageFromList(conflictPageOrder, "next");
  }, [conflictPageOrder, jumpToPageFromList]);

  const togglePinPage = useCallback((slug: string) => {
    setPinnedPageSlugs((prev) => {
      if (prev.includes(slug)) {
        return prev.filter((item) => item !== slug);
      }
      return [slug, ...prev].slice(0, 20);
    });
  }, []);

  const saveCurrentView = useCallback(() => {
    const name = savedViewName.trim();
    if (!name) {
      notifications.show({
        color: "red",
        title: "View name required",
        message: "Provide a name before saving the view.",
      });
      return;
    }
    const now = new Date().toISOString();
    const existing = savedViews.find((item) => item.name.trim().toLowerCase() === name.toLowerCase());
    if (existing) {
      setSavedViews((prev) =>
        prev.map((item) =>
          item.id === existing.id
            ? {
                ...item,
                name,
                selectedSpaceKey,
                selectedPageSlug,
                status,
                openPagesOnly,
                pageFilter,
                draftFilter,
                updated_at: now,
              }
            : item,
        ),
      );
      setSelectedViewId(existing.id);
      setSavedViewName(name);
      notifications.show({
        color: "teal",
        title: "View updated",
        message: `Saved view "${name}" updated.`,
      });
      return;
    }
    const next: SavedView = {
      id: `view_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 7)}`,
      name,
      selectedSpaceKey,
      selectedPageSlug,
      status,
      openPagesOnly,
      pageFilter,
      draftFilter,
      created_at: now,
      updated_at: now,
    };
    setSavedViews((prev) => [next, ...prev].slice(0, 25));
    setSelectedViewId(next.id);
    setSavedViewName(name);
    notifications.show({
      color: "teal",
      title: "View saved",
      message: `Saved view "${name}" created.`,
    });
  }, [
    draftFilter,
    openPagesOnly,
    pageFilter,
    savedViewName,
    savedViews,
    selectedPageSlug,
    selectedSpaceKey,
    status,
  ]);

  const applySavedView = useCallback(
    (viewId: string | null) => {
      if (!viewId) {
        setSelectedViewId(null);
        return;
      }
      const view = savedViews.find((item) => item.id === viewId);
      if (!view) return;
      setSelectedViewId(view.id);
      setSelectedSpaceKey(view.selectedSpaceKey);
      setSelectedPageSlug(view.selectedPageSlug);
      setStatus(view.status);
      setOpenPagesOnly(view.openPagesOnly);
      setPageFilter(view.pageFilter);
      setDraftFilter(view.draftFilter);
      setSavedViewName(view.name);
      notifications.show({
        color: "teal",
        title: "View applied",
        message: `Applied saved view "${view.name}".`,
      });
    },
    [savedViews],
  );

  const deleteSavedView = useCallback(() => {
    if (!selectedViewId) return;
    const view = savedViews.find((item) => item.id === selectedViewId);
    setSavedViews((prev) => prev.filter((item) => item.id !== selectedViewId));
    setSelectedViewId(null);
    setSavedViewName("");
    notifications.show({
      color: "orange",
      title: "View deleted",
      message: view ? `Removed "${view.name}".` : "Removed saved view.",
    });
  }, [savedViews, selectedViewId]);

  const toggleBulkDraftSelection = useCallback((draftId: string) => {
    setBulkSelectedDraftIds((prev) => {
      if (prev.includes(draftId)) {
        return prev.filter((item) => item !== draftId);
      }
      return [...prev, draftId];
    });
  }, []);

  const bulkSelectedVisibleCount = useMemo(
    () => visibleDrafts.filter((item) => bulkSelectedDraftIds.includes(item.id)).length,
    [bulkSelectedDraftIds, visibleDrafts],
  );

  const allVisibleSelected = useMemo(
    () => visibleDrafts.length > 0 && bulkSelectedVisibleCount === visibleDrafts.length,
    [bulkSelectedVisibleCount, visibleDrafts.length],
  );

  const selectAllVisibleDrafts = useCallback(
    (checked: boolean) => {
      if (!checked) {
        setBulkSelectedDraftIds((prev) => prev.filter((id) => !visibleDrafts.some((item) => item.id === id)));
        return;
      }
      setBulkSelectedDraftIds((prev) => {
        const merged = new Set(prev);
        for (const draft of visibleDrafts) {
          merged.add(draft.id);
        }
        return [...merged];
      });
    },
    [visibleDrafts],
  );

  const runBulkModeration = useCallback(
    async (action: "approve" | "reject") => {
      const targetIds = visibleDrafts
        .map((item) => item.id)
        .filter((id) => bulkSelectedDraftIds.includes(id));
      if (targetIds.length === 0) {
        notifications.show({
          color: "orange",
          title: "No drafts selected",
          message: "Select one or more drafts to run bulk moderation.",
        });
        return;
      }
      const requiresRiskConfirmation = action === "reject" || (action === "approve" && bulkForceApprove);
      if (
        requiresRiskConfirmation &&
        !requireRiskConfirmation(
          action === "approve" ? "bulk-approve" : "bulk-reject",
          action === "approve" ? "Approve Selected" : "Reject Selected",
        )
      ) {
        return;
      }
      setRunningAction(true);
      try {
        let success = 0;
        let failed = 0;
        let firstError = "";
        for (const draftId of targetIds) {
          try {
            if (action === "approve") {
              await apiFetch(apiUrl, `/v1/wiki/drafts/${encodeURIComponent(draftId)}/approve`, {
                method: "POST",
                body: {
                  project_id: projectId,
                  reviewed_by: reviewer.trim(),
                  note: bulkApproveNote.trim() || `Bulk approved by ${reviewer.trim()}.`,
                  force: bulkForceApprove,
                },
                idempotencyKey: randomKey(),
              });
            } else {
              await apiFetch(apiUrl, `/v1/wiki/drafts/${encodeURIComponent(draftId)}/reject`, {
                method: "POST",
                body: {
                  project_id: projectId,
                  reviewed_by: reviewer.trim(),
                  reason: bulkRejectReason.trim() || `Bulk rejected by ${reviewer.trim()}.`,
                  dismiss_conflicts: true,
                },
                idempotencyKey: randomKey(),
              });
            }
            success += 1;
          } catch (error) {
            failed += 1;
            if (!firstError) {
              firstError = String(error);
            }
          }
        }
        notifications.show({
          color: failed > 0 ? "orange" : "green",
          title: action === "approve" ? "Bulk approve finished" : "Bulk reject finished",
          message:
            failed > 0
              ? `Success: ${success}, failed: ${failed}. First error: ${firstError}`
              : `Success: ${success}, failed: 0.`,
        });
        setBulkSelectedDraftIds((prev) => prev.filter((id) => !targetIds.includes(id)));
        await loadDrafts();
        if (selectedDraftId) {
          await loadDraftDetail(selectedDraftId);
          await loadConflictExplain(selectedDraftId);
        }
      } finally {
        setRunningAction(false);
      }
    },
    [
      apiUrl,
      bulkApproveNote,
      bulkForceApprove,
      bulkRejectReason,
      bulkSelectedDraftIds,
      loadConflictExplain,
      loadDraftDetail,
      loadDrafts,
      projectId,
      requireRiskConfirmation,
      reviewer,
      selectedDraftId,
      visibleDrafts,
    ],
  );

  const suggestGuidedSlug = useCallback(() => {
    setGuidedPageForm((prev) => {
      const base = prev.slug.trim() || `${prev.spaceKey.trim()}/${prev.title.trim()}`;
      const normalized = normalizeWikiSlug(base, prev.title.trim() || "page");
      return { ...prev, slug: normalized };
    });
  }, []);

  const autofillGuidedFromDraft = useCallback(() => {
    const draft = draftDetail?.draft;
    const claimText = draft?.claim?.claim_text?.trim() || "";
    const fallbackSlug = draft?.page.slug?.trim() || "";
    const fallbackTitle =
      draft?.page.title?.trim() ||
      (fallbackSlug ? fallbackSlug.split("/").slice(-1)[0].replace(/[-_]/g, " ") : "") ||
      "New knowledge page";
    const spaceKey = selectedSpaceKey || pageGroupKey(fallbackSlug) || "operations";
    const statement = claimText || "Document the validated operational fact.";
    const sectionHeading = draft?.section_key ? _sectionHeadingFromKeyForUi(draft.section_key) : "Overview";
    const seedSlug = fallbackSlug || `${spaceKey}/${fallbackTitle}`;
    const normalizedSeedSlug = normalizeWikiSlug(seedSlug, fallbackTitle);
    setGuidedPageForm((prev) => ({
      ...prev,
      spaceKey,
      title: fallbackTitle,
      slug: normalizedSeedSlug,
      pageType: draft?.claim?.category?.trim() || prev.pageType || "operations",
      entityKey: draft?.claim?.entity_key?.trim() || draft?.page.entity_key?.trim() || prev.entityKey,
      sectionHeading,
      sectionStatement: statement,
      changeSummary: prev.changeSummary || `Bootstrapped from draft ${draft?.id || selectedDraftId || ""}`.trim(),
    }));
    if (!retrievalExplainQuery.trim()) {
      setRetrievalExplainQuery(claimText || fallbackTitle);
    }
    if (!retrievalExplainRelatedEntity.trim()) {
      const hintedEntity = draft?.claim?.entity_key?.trim() || draft?.page.entity_key?.trim() || "";
      if (hintedEntity) {
        setRetrievalExplainRelatedEntity(hintedEntity);
      }
    }
    notifications.show({
      color: "teal",
      title: "Guided form autofilled",
      message: "Seeded page builder fields from selected draft context.",
    });
  }, [draftDetail, retrievalExplainQuery, retrievalExplainRelatedEntity, selectedDraftId, selectedSpaceKey]);

  const createGuidedWikiPage = useCallback(async () => {
    if (!projectId.trim()) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before creating pages.",
      });
      return;
    }
    if (!reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Reviewer required",
        message: "Set reviewer before creating pages.",
      });
      return;
    }
    const title = guidedPageForm.title.trim();
    if (!title) {
      notifications.show({
        color: "red",
        title: "Title required",
        message: "Provide a page title in Guided Builder.",
      });
      return;
    }
    const spacePrefix = slugifySegment(guidedPageForm.spaceKey.trim() || "operations");
    const slugSeed = guidedPageForm.slug.trim() || `${spacePrefix}/${title}`;
    const normalizedSlug = normalizeWikiSlug(slugSeed, title);
    const normalizedPageType = (guidedPageForm.pageType.trim() || "operations").toLowerCase().replace(/\s+/g, "_");
    const sectionHeading = guidedPageForm.sectionHeading.trim() || "Overview";
    const sectionStatement = guidedPageForm.sectionStatement.trim();
    const initialMarkdown = [
      `# ${title}`,
      "",
      `## ${sectionHeading}`,
      sectionStatement ? `- ${sectionStatement}` : "",
      "",
    ]
      .filter(Boolean)
      .join("\n");
    setCreatingPage(true);
    try {
      const payload = await apiFetch<{
        status: string;
        page: {
          id: string;
          title: string;
          slug: string;
          entity_key: string | null;
          page_type: string | null;
          status: string;
          current_version: number | null;
        };
      }>(apiUrl, "/v1/wiki/pages", {
        method: "POST",
        idempotencyKey: randomKey(),
        body: {
          project_id: projectId,
          created_by: reviewer.trim(),
          title,
          slug: normalizedSlug,
          entity_key: guidedPageForm.entityKey.trim() || null,
          page_type: normalizedPageType,
          status: guidedPageForm.status,
          initial_markdown: initialMarkdown,
          change_summary: guidedPageForm.changeSummary.trim() || null,
          allow_existing: true,
        },
      });
      const pageSlug = payload.page.slug;
      setSelectedSpaceKey(pageGroupKey(pageSlug));
      setSelectedPageSlug(pageSlug);
      setGuidedPageForm((prev) => ({
        ...prev,
        slug: pageSlug,
      }));
      notifications.show({
        color: payload.status === "existing" ? "orange" : "green",
        title: payload.status === "existing" ? "Existing page opened" : "Page created",
        message: `${payload.page.title} (${payload.page.slug})`,
      });
      await loadPageDetail(pageSlug);
      await loadPageHistory(pageSlug);
      setDetailTab("history");
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Page creation failed",
        message: String(error),
      });
    } finally {
      setCreatingPage(false);
    }
  }, [apiUrl, guidedPageForm, loadPageDetail, loadPageHistory, projectId, reviewer]);

  const runRetrievalExplain = useCallback(async () => {
    if (!projectId.trim()) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before running retrieval diagnostics.",
      });
      return;
    }
    const query = retrievalExplainQuery.trim();
    if (!query) {
      notifications.show({
        color: "red",
        title: "Query required",
        message: "Enter a retrieval query to inspect MCP ranking reasons.",
      });
      return;
    }
    setLoadingRetrievalExplain(true);
    setRetrievalExplainGraphConfig(null);
    setRetrievalExplainContextPolicy(null);
    setRetrievalExplainPolicyFilteredOut(0);
    setRetrievalExplainResults([]);
    try {
      const related = retrievalExplainRelatedEntity.trim();
      const mode = retrievalExplainPolicyMode;
      const minConfidence = Number.parseFloat(retrievalExplainMinConfidence);
      const minTotalScore = Number.parseFloat(retrievalExplainMinTotalScore);
      const minLexicalScore = Number.parseFloat(retrievalExplainMinLexicalScore);
      const minOverlap = Number.parseFloat(retrievalExplainMinTokenOverlap);
      const params = new URLSearchParams();
      params.set("project_id", projectId);
      params.set("q", query);
      params.set("limit", "6");
      if (related) params.set("related_entity_key", related);
      if (mode) params.set("context_policy_mode", mode);
      if (Number.isFinite(minConfidence)) params.set("min_retrieval_confidence", String(minConfidence));
      if (Number.isFinite(minTotalScore)) params.set("min_total_score", String(minTotalScore));
      if (Number.isFinite(minLexicalScore)) params.set("min_lexical_score", String(minLexicalScore));
      if (Number.isFinite(minOverlap)) params.set("min_token_overlap_ratio", String(minOverlap));
      const payload = await apiFetch<RetrievalExplainPayload>(
        apiUrl,
        `/v1/mcp/retrieval/explain?${params.toString()}`,
      );
      setRetrievalExplainResults(payload.results ?? []);
      setRetrievalExplainGraphConfig(payload.graph_config ?? null);
      setRetrievalExplainContextPolicy(payload.context_policy ?? null);
      setRetrievalExplainPolicyFilteredOut(Number(payload.policy_filtered_out ?? 0));
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Retrieval diagnostics failed",
        message: String(error),
      });
    } finally {
      setLoadingRetrievalExplain(false);
    }
  }, [
    apiUrl,
    projectId,
    retrievalExplainMinConfidence,
    retrievalExplainMinLexicalScore,
    retrievalExplainMinTokenOverlap,
    retrievalExplainMinTotalScore,
    retrievalExplainPolicyMode,
    retrievalExplainQuery,
    retrievalExplainRelatedEntity,
  ]);

  useEffect(() => {
    const project = projectId.trim();
    const query = guidedPageForm.title.trim();
    if (!project || query.length < 2) {
      setGuidedPageMatches([]);
      setSearchingGuidedMatches(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSearchingGuidedMatches(true);
      try {
        const payload = await apiFetch<{ results: WikiPageSearchResult[] }>(
          apiUrl,
          `/v1/wiki/pages/search?project_id=${encodeURIComponent(project)}&q=${encodeURIComponent(query)}&limit=6`,
        );
        if (cancelled) return;
        setGuidedPageMatches(payload.results ?? []);
      } catch {
        if (!cancelled) {
          setGuidedPageMatches([]);
        }
      } finally {
        if (!cancelled) {
          setSearchingGuidedMatches(false);
        }
      }
    }, 280);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [apiUrl, guidedPageForm.title, projectId]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      const key = event.key.toLowerCase();
      const mod = event.metaKey || event.ctrlKey;

      if (mod && key === "r") {
        event.preventDefault();
        void loadDrafts();
        return;
      }
      if (event.shiftKey && key === "j" && !mod && !event.altKey) {
        event.preventDefault();
        jumpToNextPage();
        return;
      }
      if (event.shiftKey && key === "k" && !mod && !event.altKey) {
        event.preventDefault();
        jumpToPrevPage();
        return;
      }
      if (event.shiftKey && key === "c" && !mod && !event.altKey) {
        event.preventDefault();
        jumpToNextConflictPage();
        return;
      }
      if (showExpertModerationControls && mod && event.shiftKey && key === "enter") {
        event.preventDefault();
        void runBulkModeration("approve");
        return;
      }
      if (showExpertModerationControls && mod && event.shiftKey && key === "backspace") {
        event.preventDefault();
        void runBulkModeration("reject");
        return;
      }
      if (key === "j" && !mod && !event.altKey) {
        event.preventDefault();
        selectNextDraft();
        return;
      }
      if (key === "k" && !mod && !event.altKey) {
        event.preventDefault();
        selectPrevDraft();
        return;
      }
      if (mod && key === "enter" && canModerate) {
        event.preventDefault();
        void approveDraft();
        return;
      }
      if (mod && key === "backspace" && canModerate) {
        event.preventDefault();
        void rejectDraft();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    approveDraft,
    canModerate,
    jumpToNextConflictPage,
    jumpToNextPage,
    jumpToPrevPage,
    loadDrafts,
    rejectDraft,
    runBulkModeration,
    showExpertModerationControls,
    selectNextDraft,
    selectPrevDraft,
  ]);

  const semanticDiff = draftDetail?.draft.semantic_diff ?? {};
  const enrichedConflicts = conflictExplain?.conflicts ?? [];
  const beforeText = String((semanticDiff as Record<string, unknown>).before ?? "");
  const afterText = String((semanticDiff as Record<string, unknown>).after ?? "");
  const statementDiff = useMemo(() => buildStatementDiff(beforeText, afterText), [beforeText, afterText]);
  const hasOpenConflicts =
    enrichedConflicts.some((item) => item.resolution_status === "open") ||
    (draftDetail?.conflicts ?? []).some((item) => item.resolution_status === "open");
  const selectedPageNode = useMemo(
    () => pageNodes.find((item) => item.slug === selectedPageSlug) || null,
    [pageNodes, selectedPageSlug],
  );
  const selectedSpaceNode = useMemo(
    () => spaceNodes.find((item) => item.key === selectedSpaceKey) || null,
    [selectedSpaceKey, spaceNodes],
  );
  const openPageCount = useMemo(() => pageNodes.filter((item) => item.open_count > 0).length, [pageNodes]);
  const openDraftCount = useMemo(
    () => drafts.filter((item) => item.status === "pending_review" || item.status === "blocked_conflict").length,
    [drafts],
  );
  const selectedTemplate = useMemo(
    () => PAGE_TEMPLATES.find((item) => item.key === selectedTemplateKey) || null,
    [selectedTemplateKey],
  );
  const pageTocSections = useMemo(() => {
    const sections = selectedPageDetail?.sections ?? [];
    const statements = selectedPageDetail?.statements ?? [];
    return sections.map((section) => {
      const sectionStatements = statements.filter((item) => item.section_key === section.section_key);
      return {
        ...section,
        statements: sectionStatements,
      };
    });
  }, [selectedPageDetail]);
  const selectedTocSection = useMemo(
    () => pageTocSections.find((item) => item.section_key === selectedTocSectionKey) || null,
    [pageTocSections, selectedTocSectionKey],
  );
  const pageHistoryOptions = useMemo(
    () =>
      (pageHistory?.versions ?? []).map((item) => ({
        value: String(item.version),
        label: `v${item.version} • ${fmtDate(item.created_at)}${item.created_by ? ` • ${item.created_by}` : ""}`,
      })),
    [pageHistory],
  );
  const selectedHistoryBase = useMemo(
    () => (pageHistory?.versions ?? []).find((item) => String(item.version) === String(historyBaseVersion || "")) || null,
    [historyBaseVersion, pageHistory],
  );
  const selectedHistoryTarget = useMemo(
    () => (pageHistory?.versions ?? []).find((item) => String(item.version) === String(historyTargetVersion || "")) || null,
    [historyTargetVersion, pageHistory],
  );
  const pageHistoryDiff = useMemo(
    () =>
      buildStatementDiff(
        String(selectedHistoryBase?.markdown || ""),
        String(selectedHistoryTarget?.markdown || ""),
      ),
    [selectedHistoryBase?.markdown, selectedHistoryTarget?.markdown],
  );
  const selectedSpaceTitle = selectedSpaceNode?.title || "All spaces";
  const selectedPageTitle = selectedPageNode?.title || selectedPageSlug || "All pages";
  const effectiveQueuePreset: ReviewQueuePresetKey = showExpertModerationControls ? reviewQueuePreset : "open_queue";
  const isCoreSimplified = uiMode === "core" && !coreExpertControls;
  const selectedQueuePreset = useMemo(
    () => REVIEW_QUEUE_PRESETS.find((item) => item.key === effectiveQueuePreset) || REVIEW_QUEUE_PRESETS[0],
    [effectiveQueuePreset],
  );
  const selectedDraftSummary = useMemo(
    () => (selectedDraftId ? drafts.find((item) => item.id === selectedDraftId) || null : null),
    [drafts, selectedDraftId],
  );
  const queueMetrics = useMemo(() => {
    const nowMs = Date.now();
    const openScoped = scopedDrafts.filter((item) => isOpenReviewDraft(item));
    const openAges = openScoped
      .map((item) => draftAgeHours(item, nowMs))
      .filter((value): value is number => value != null)
      .sort((a, b) => a - b);
    const medianAge =
      openAges.length === 0
        ? null
        : openAges.length % 2 === 1
          ? openAges[(openAges.length - 1) / 2]
          : (openAges[openAges.length / 2 - 1] + openAges[openAges.length / 2]) / 2;
    return {
      openCount: openScoped.length,
      breachCount: openScoped.filter((item) => (draftAgeHours(item, nowMs) ?? -1) >= reviewSlaHours).length,
      conflictCount: openScoped.filter((item) => item.status === "blocked_conflict" || item.decision === "conflict").length,
      highConfidenceCount: openScoped.filter((item) => Number(item.confidence) >= 0.85).length,
      oldestAge: openAges.length > 0 ? openAges[openAges.length - 1] : null,
      medianAge,
    };
  }, [reviewSlaHours, scopedDrafts]);
  const triageLaneEntries = useMemo(() => {
    const nowMs = Date.now();
    return [...visibleDrafts]
      .filter((item) => isOpenReviewDraft(item))
      .map((draft) => {
        const score = triagePriorityScore(draft, nowMs, reviewSlaHours);
        return {
          draft,
          score,
          reasons: triagePriorityReasons(draft, nowMs, reviewSlaHours),
        };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 4);
  }, [reviewSlaHours, visibleDrafts]);
  const canQuickModerateFromInbox = useMemo(
    () => Boolean(projectId.trim() && reviewer.trim()) && !runningAction,
    [projectId, reviewer, runningAction],
  );
  const quickForceArmed = armedRiskActionKey === `force-approve:${selectedDraftId ?? "none"}`;
  const quickDismissArmed = armedRiskActionKey === `reject-dismiss:${selectedDraftId ?? "none"}`;
  const formForceArmed = armedRiskActionKey === `force-approve-form:${selectedDraftId ?? "none"}`;
  const formDismissArmed = armedRiskActionKey === `reject-dismiss-form:${selectedDraftId ?? "none"}`;
  const bulkApproveArmed = armedRiskActionKey === "bulk-approve";
  const bulkRejectArmed = armedRiskActionKey === "bulk-reject";
  const walkthroughHasWorkspace = Boolean(apiUrl.trim() && projectId.trim() && reviewer.trim());
  const walkthroughHasDrafts = visibleDrafts.length > 0;
  const walkthroughTargetDraft = useMemo(
    () => visibleDrafts.find((item) => isOpenReviewDraft(item)) || visibleDrafts[0] || null,
    [visibleDrafts],
  );
  const walkthroughHasSelectedDraft = Boolean(
    selectedDraftId && drafts.some((item) => item.id === selectedDraftId),
  );
  const walkthroughCompletedSteps = [walkthroughHasWorkspace, walkthroughHasDrafts, walkthroughHasSelectedDraft].filter(
    Boolean,
  ).length;
  useEffect(() => {
    if (!walkthroughHasWorkspace) return;
    setWalkthroughTelemetry((prev) => {
      if (prev.stepCompletedAtMs.workspace != null) return prev;
      return {
        ...prev,
        stepCompletedAtMs: {
          ...prev.stepCompletedAtMs,
          workspace: Date.now(),
        },
      };
    });
  }, [walkthroughHasWorkspace]);
  useEffect(() => {
    if (!walkthroughHasDrafts) return;
    setWalkthroughTelemetry((prev) => {
      if (prev.stepCompletedAtMs.inbox != null) return prev;
      return {
        ...prev,
        stepCompletedAtMs: {
          ...prev.stepCompletedAtMs,
          inbox: Date.now(),
        },
      };
    });
  }, [walkthroughHasDrafts]);
  useEffect(() => {
    if (!walkthroughHasSelectedDraft) return;
    setWalkthroughTelemetry((prev) => {
      if (prev.stepCompletedAtMs.firstReview != null) return prev;
      return {
        ...prev,
        stepCompletedAtMs: {
          ...prev.stepCompletedAtMs,
          firstReview: Date.now(),
        },
      };
    });
  }, [walkthroughHasSelectedDraft]);
  const walkthroughLatencySeconds = useMemo(() => {
    const startedAtMs = walkthroughTelemetry.startedAtMs;
    const completed = walkthroughTelemetry.stepCompletedAtMs;
    const toSeconds = (timestampMs: number | null) =>
      timestampMs == null ? null : Math.max(0, (timestampMs - startedAtMs) / 1000);
    return {
      workspace: toSeconds(completed.workspace),
      inbox: toSeconds(completed.inbox),
      firstReview: toSeconds(completed.firstReview),
    };
  }, [walkthroughTelemetry.startedAtMs, walkthroughTelemetry.stepCompletedAtMs]);
  const coreIntentSummary = useMemo(() => {
    const quick = coreIntentSignals.quickModeration;
    const sessionMinutes = Math.max(0, (Date.now() - coreIntentSignals.startedAtMs) / (1000 * 60));
    return {
      triageOpenCount: coreIntentSignals.triageOpenCount,
      triageUniqueDrafts: coreIntentSignals.triageOpenedDraftIds.length,
      quickApproveCount: quick.approve,
      quickRejectCount: quick.reject,
      quickFromTriage: quick.bySource.triage_lane,
      quickFromInbox: quick.bySource.inbox_card,
      quickFromDetail: quick.bySource.detail_header,
      quickActionsPerHour:
        sessionMinutes > 0 ? Number((((quick.approve + quick.reject) / sessionMinutes) * 60).toFixed(1)) : 0,
      lastAction: coreIntentSignals.lastAction,
    };
  }, [coreIntentSignals]);
  return (
    <Box className="synapse-shell">
      <Box className="bg-orb bg-orb-a" />
      <Box className="bg-orb bg-orb-b" />

      <Stack gap="lg">
        <Paper radius="xl" p="xl" className="hero-card">
          <Group justify="space-between" align="flex-start">
            <Stack gap={2}>
              <Text className="eyebrow">Synapse Wiki</Text>
              <Title order={1}>Knowledge Workspace</Title>
              <Text c="dimmed">
                Review incoming knowledge drafts, resolve conflicts, and publish trusted updates for all connected
                agents.
              </Text>
            </Stack>
            <Tooltip label="Refresh drafts">
              <ActionIcon
                size="lg"
                variant="light"
                color="teal"
                onClick={() => void loadDrafts()}
                aria-label="Refresh drafts"
              >
                <IconRefresh size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>

        <Paper radius="xl" p="lg">
          <SimpleGrid cols={{ base: 1, md: 2, lg: uiMode === "advanced" ? 5 : 4 }} spacing="md">
            <TextInput
              label="API URL"
              value={apiUrl}
              onChange={(event) => setApiUrl(event.currentTarget.value)}
              leftSection={<IconCloudCog size={16} />}
              placeholder="http://localhost:8080"
            />
            <TextInput
              label="Project ID"
              value={projectId}
              onChange={(event) => setProjectId(event.currentTarget.value)}
              leftSection={<IconSearch size={16} />}
              placeholder="omega_demo"
            />
            <TextInput
              label="Reviewer"
              value={reviewer}
              onChange={(event) => setReviewer(event.currentTarget.value)}
              leftSection={<IconEditCircle size={16} />}
              placeholder="ops_manager"
            />
            {uiMode === "advanced" && (
              <Select
                label="Status Filter"
                value={status}
                onChange={setStatus}
                clearable
                data={[
                  { label: "pending_review", value: "pending_review" },
                  { label: "blocked_conflict", value: "blocked_conflict" },
                  { label: "approved", value: "approved" },
                  { label: "rejected", value: "rejected" },
                ]}
              />
            )}
            <Button
              onClick={() => void loadDrafts()}
              loading={loadingDrafts}
              leftSection={<IconArrowsShuffle size={16} />}
              variant="gradient"
              gradient={{ from: "teal.7", to: "cyan.6", deg: 140 }}
              mt={24}
            >
              Refresh Inbox
            </Button>
          </SimpleGrid>

          <Paper mt="md" withBorder radius="lg" p="md" className="hotkey-panel">
            <Group justify="space-between" align="center" wrap="wrap">
              <Stack gap={2}>
                <Text fw={700}>Workspace Mode</Text>
                <Text size="xs" c="dimmed">
                  Core mode keeps only the day-to-day workflow. Advanced mode unlocks analytics and operations controls.
                </Text>
              </Stack>
              <Group>
                <Button
                  size="xs"
                  variant={uiMode === "core" ? "filled" : "light"}
                  color="teal"
                  onClick={() => setUiMode("core")}
                >
                  Core Mode
                </Button>
                <Button
                  size="xs"
                  variant={uiMode === "advanced" ? "filled" : "light"}
                  color="orange"
                  onClick={() => setUiMode("advanced")}
                >
                  Advanced Mode
                </Button>
              </Group>
            </Group>
            {uiMode === "core" && (
              <Group mt="sm" justify="space-between" align="center" wrap="wrap">
                <Text size="xs" c="dimmed">
                  {coreExpertControls
                    ? "Expert controls are visible in core mode."
                    : "Simplified core mode hides advanced controls for faster moderation."}
                </Text>
                <Button
                  size="xs"
                  variant={coreExpertControls ? "light" : "filled"}
                  color={coreExpertControls ? "gray" : "teal"}
                  onClick={() => setCoreExpertControls((prev) => !prev)}
                >
                  {coreExpertControls ? "Back to Simplified Core" : "Enable Expert Controls"}
                </Button>
              </Group>
            )}
          </Paper>

          <Paper mt="md" withBorder radius="lg" p="sm" className="hotkey-panel">
            <Group gap="md" wrap="wrap">
              <Group gap={6}>
                <ThemeIcon variant="light" color="teal" size="sm">
                  <IconKeyboard size={14} />
                </ThemeIcon>
                <Text size="sm" fw={600}>
                  Quick keys
                </Text>
              </Group>
              <Group gap={4}>
                <Kbd>j</Kbd>
                <Text size="xs" c="dimmed">
                  next draft
                </Text>
              </Group>
              <Group gap={4}>
                <Kbd>k</Kbd>
                <Text size="xs" c="dimmed">
                  previous draft
                </Text>
              </Group>
              {showExpertModerationControls && (
                <Group gap={4}>
                  <Kbd>Shift + j</Kbd>
                  <Text size="xs" c="dimmed">
                    next page
                  </Text>
                </Group>
              )}
              {showExpertModerationControls && (
                <Group gap={4}>
                  <Kbd>Shift + k</Kbd>
                  <Text size="xs" c="dimmed">
                    previous page
                  </Text>
                </Group>
              )}
              {showExpertModerationControls && (
                <Group gap={4}>
                  <Kbd>Shift + c</Kbd>
                  <Text size="xs" c="dimmed">
                    next conflict page
                  </Text>
                </Group>
              )}
              <Group gap={4}>
                <Kbd>Ctrl/Cmd + Enter</Kbd>
                <Text size="xs" c="dimmed">
                  approve
                </Text>
              </Group>
              <Group gap={4}>
                <Kbd>Ctrl/Cmd + Backspace</Kbd>
                <Text size="xs" c="dimmed">
                  reject
                </Text>
              </Group>
              {showExpertModerationControls && (
                <Group gap={4}>
                  <Kbd>Ctrl/Cmd + Shift + Enter</Kbd>
                  <Text size="xs" c="dimmed">
                    approve selected
                  </Text>
                </Group>
              )}
              {showExpertModerationControls && (
                <Group gap={4}>
                  <Kbd>Ctrl/Cmd + Shift + Backspace</Kbd>
                  <Text size="xs" c="dimmed">
                    reject selected
                  </Text>
                </Group>
              )}
              <Group gap={4}>
                <Kbd>Ctrl/Cmd + R</Kbd>
                <Text size="xs" c="dimmed">
                  refresh
                </Text>
              </Group>
            </Group>
          </Paper>
        </Paper>

        {uiMode === "advanced" ? (
          <Suspense
            fallback={
              <Paper radius="xl" p="lg" className="intelligence-panel">
                <Group justify="space-between" align="center">
                  <Stack gap={2}>
                    <Text className="eyebrow">Intelligence Pulse</Text>
                    <Title order={3}>Loading analytics…</Title>
                  </Stack>
                  <Loader size="sm" />
                </Group>
              </Paper>
            }
          >
            <LazyIntelligencePanel apiUrl={apiUrl} projectId={projectId} reviewer={reviewer} />
          </Suspense>
        ) : (
          <Paper radius="xl" p="lg" className="intelligence-panel">
            <Stack gap="sm">
              <Text className="eyebrow">Core Mode</Text>
              <Title order={3}>Focused Workflow</Title>
              <Text c="dimmed" size="sm">
                Advanced analytics and queue operations are hidden to keep this workspace simple: capture facts, review drafts,
                approve knowledge, and manage tasks.
              </Text>
              <Group gap="xs">
                <Badge variant="light" color="teal">
                  SDK ingest
                </Badge>
                <Badge variant="light" color="cyan">
                  Draft moderation
                </Badge>
                <Badge variant="light" color="orange">
                  Task lifecycle
                </Badge>
              </Group>
              <Divider />
              <Stack gap="xs" className="core-walkthrough-card">
                <Group justify="space-between" align="center" wrap="wrap">
                  <Text size="sm" fw={700}>
                    Operator Walkthrough
                  </Text>
                  <Badge size="sm" variant="light" color={walkthroughCompletedSteps === 3 ? "teal" : "indigo"}>
                    {walkthroughCompletedSteps}/3 complete
                  </Badge>
                </Group>
                <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xs">
                  <Paper withBorder p="xs" radius="md" className="core-walkthrough-step-card">
                    <Stack gap={6}>
                      <Group gap={6} align="center" wrap="nowrap">
                        <ThemeIcon size="sm" variant="light" color={walkthroughHasWorkspace ? "teal" : "gray"}>
                          {walkthroughHasWorkspace ? <IconCheck size={12} /> : <Text size="xs">1</Text>}
                        </ThemeIcon>
                        <Text size="sm" fw={600}>
                          Connect workspace
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        Configure API URL, project ID, and reviewer.
                      </Text>
                      {walkthroughHasWorkspace ? (
                        <Badge size="xs" variant="light" color="teal">
                          ready
                        </Badge>
                      ) : (
                        <Button
                          size="compact-xs"
                          variant="light"
                          onClick={() => {
                            setWalkthroughTelemetry((prev) => ({
                              ...prev,
                              actionCounts: {
                                ...prev.actionCounts,
                                useDemoValues: prev.actionCounts.useDemoValues + 1,
                              },
                            }));
                            if (!apiUrl.trim()) {
                              setApiUrl("http://localhost:8080");
                            }
                            if (!projectId.trim()) {
                              setProjectId("omega_demo");
                            }
                            if (!reviewer.trim()) {
                              setReviewer("ops_manager");
                            }
                          }}
                        >
                          Use demo values
                        </Button>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md" className="core-walkthrough-step-card">
                    <Stack gap={6}>
                      <Group gap={6} align="center" wrap="nowrap">
                        <ThemeIcon size="sm" variant="light" color={walkthroughHasDrafts ? "teal" : "gray"}>
                          {walkthroughHasDrafts ? <IconCheck size={12} /> : <Text size="xs">2</Text>}
                        </ThemeIcon>
                        <Text size="sm" fw={600}>
                          Load inbox
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        Pull current draft queue for triage and moderation.
                      </Text>
                      {walkthroughHasDrafts ? (
                        <Badge size="xs" variant="light" color="teal">
                          {visibleDrafts.length} drafts
                        </Badge>
                      ) : (
                        <Button
                          size="compact-xs"
                          variant="light"
                          onClick={() => {
                            setWalkthroughTelemetry((prev) => ({
                              ...prev,
                              actionCounts: {
                                ...prev.actionCounts,
                                loadDraftQueue: prev.actionCounts.loadDraftQueue + 1,
                              },
                            }));
                            void loadDrafts();
                          }}
                          loading={loadingDrafts}
                        >
                          Load Draft Queue
                        </Button>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md" className="core-walkthrough-step-card">
                    <Stack gap={6}>
                      <Group gap={6} align="center" wrap="nowrap">
                        <ThemeIcon size="sm" variant="light" color={walkthroughHasSelectedDraft ? "teal" : "gray"}>
                          {walkthroughHasSelectedDraft ? <IconCheck size={12} /> : <Text size="xs">3</Text>}
                        </ThemeIcon>
                        <Text size="sm" fw={600}>
                          Review first draft
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        Open any draft to inspect semantic diff and approve or reject.
                      </Text>
                      {walkthroughHasSelectedDraft ? (
                        <Badge size="xs" variant="light" color="teal">
                          draft selected
                        </Badge>
                      ) : (
                        <Button
                          size="compact-xs"
                          variant="light"
                          disabled={!walkthroughTargetDraft}
                          onClick={() => {
                            if (!walkthroughTargetDraft) return;
                            setWalkthroughTelemetry((prev) => ({
                              ...prev,
                              actionCounts: {
                                ...prev.actionCounts,
                                selectDraft: prev.actionCounts.selectDraft + 1,
                              },
                            }));
                            setSelectedDraftId(walkthroughTargetDraft.id);
                            const slug = String(walkthroughTargetDraft.page.slug || "").trim();
                            if (slug) {
                              setSelectedSpaceKey(pageGroupKey(slug));
                              setSelectedPageSlug(slug);
                            }
                            setDetailTab("semantic");
                          }}
                        >
                          Select draft
                        </Button>
                      )}
                    </Stack>
                  </Paper>
                </SimpleGrid>
                <Group gap="xs" wrap="wrap">
                  {CORE_WALKTHROUGH_DOC_LINKS.map((item) => (
                    <HoverCard key={item.href} width={300} shadow="md" openDelay={120} closeDelay={80} withArrow>
                      <HoverCard.Target>
                        <Button
                          component="a"
                          href={item.href}
                          target="_blank"
                          rel="noreferrer"
                          size="compact-xs"
                          variant="subtle"
                          rightSection={<IconExternalLink size={12} />}
                        >
                          {item.label}
                        </Button>
                      </HoverCard.Target>
                      <HoverCard.Dropdown>
                        <Stack gap={4} className="core-doc-preview-card">
                          <Text size="xs" fw={700}>
                            {item.label}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {item.preview}
                          </Text>
                          <Stack gap={2}>
                            {item.highlights.map((highlight) => (
                              <Text key={`${item.label}-${highlight}`} size="xs">
                                - {highlight}
                              </Text>
                            ))}
                          </Stack>
                        </Stack>
                      </HoverCard.Dropdown>
                    </HoverCard>
                  ))}
                </Group>
                <Paper withBorder p="xs" radius="md" className="core-walkthrough-telemetry-card">
                  <Stack gap={6}>
                    <Group justify="space-between" align="center" wrap="wrap">
                      <Text size="xs" fw={700}>
                        Onboarding Telemetry (Session)
                      </Text>
                      <Badge size="xs" variant="light" color="gray">
                        step timers
                      </Badge>
                    </Group>
                    <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xs">
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Workspace ready
                        </Text>
                        <Text size="sm" fw={700}>
                          {formatSeconds(walkthroughLatencySeconds.workspace)}
                        </Text>
                      </Paper>
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Inbox loaded
                        </Text>
                        <Text size="sm" fw={700}>
                          {formatSeconds(walkthroughLatencySeconds.inbox)}
                        </Text>
                      </Paper>
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          First draft opened
                        </Text>
                        <Text size="sm" fw={700}>
                          {formatSeconds(walkthroughLatencySeconds.firstReview)}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                    <Group gap={6} wrap="wrap">
                      <Badge size="xs" variant="light" color="indigo">
                        demo clicks {walkthroughTelemetry.actionCounts.useDemoValues}
                      </Badge>
                      <Badge size="xs" variant="light" color="cyan">
                        queue clicks {walkthroughTelemetry.actionCounts.loadDraftQueue}
                      </Badge>
                      <Badge size="xs" variant="light" color="teal">
                        select clicks {walkthroughTelemetry.actionCounts.selectDraft}
                      </Badge>
                    </Group>
                  </Stack>
                </Paper>
              </Stack>
            </Stack>
          </Paper>
        )}

        <Suspense
          fallback={
            <Paper radius="xl" p="lg" className="intelligence-panel">
              <Group justify="space-between" align="center">
                <Stack gap={2}>
                  <Text className="eyebrow">Agentic Todo Core</Text>
                  <Title order={3}>Loading tasks…</Title>
                </Stack>
                <Loader size="sm" />
              </Group>
            </Paper>
          }
        >
          <LazyTaskTrackerPanel apiUrl={apiUrl} projectId={projectId} reviewer={reviewer} />
        </Suspense>

        <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="lg">
          <Paper radius="xl" p="lg">
            <Group justify="space-between" mb="sm">
              <Title order={3}>Wiki Tree</Title>
              <Badge size="lg" color="indigo" variant="light">
                {pageNodes.length}
              </Badge>
            </Group>
            <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xs" mb="sm">
              <Paper withBorder p="xs" radius="md">
                <Text size="xs" c="dimmed">
                  Spaces
                </Text>
                <Text fw={700}>{spaceNodes.length}</Text>
              </Paper>
              <Paper withBorder p="xs" radius="md">
                <Text size="xs" c="dimmed">
                  Pages with open drafts
                </Text>
                <Text fw={700}>{openPageCount}</Text>
              </Paper>
              <Paper withBorder p="xs" radius="md">
                <Text size="xs" c="dimmed">
                  Open drafts
                </Text>
                <Text fw={700}>{openDraftCount}</Text>
              </Paper>
            </SimpleGrid>
            <Stack gap="sm" mb="sm">
              <Select
                label="Space"
                placeholder="All spaces"
                value={selectedSpaceKey}
                onChange={(value) => {
                  setSelectedSpaceKey(value || null);
                  if (!value) {
                    return;
                  }
                  if (selectedPageSlug && pageGroupKey(selectedPageSlug) !== value) {
                    setSelectedPageSlug(null);
                  }
                }}
                clearable
                data={spaceNodes.map((space) => ({
                  label: `${space.title} (${space.page_count})`,
                  value: space.key,
                }))}
              />
              <TextInput
                label="Page filter"
                value={pageFilter}
                onChange={(event) => setPageFilter(event.currentTarget.value)}
                placeholder="Find page by title or slug"
              />
              <Checkbox
                label="Show only pages with open drafts"
                checked={openPagesOnly}
                onChange={(event) => setOpenPagesOnly(event.currentTarget.checked)}
              />
              <Group gap="xs" wrap="wrap">
                <Button
                  size="xs"
                  variant={selectedSpaceKey ? "light" : "filled"}
                  onClick={() => {
                    setSelectedSpaceKey(null);
                    setSelectedPageSlug(null);
                  }}
                >
                  All spaces
                </Button>
                <Button size="xs" variant={selectedPageSlug ? "light" : "filled"} onClick={() => setSelectedPageSlug(null)}>
                  All pages
                </Button>
                {selectedSpaceKey && (
                  <Badge variant="light" color="violet">
                    {selectedSpaceTitle}
                  </Badge>
                )}
                {selectedPageSlug && (
                  <Badge variant="light" color="teal">
                    {selectedPageTitle}
                  </Badge>
                )}
              </Group>
              {showExpertModerationControls && (
                <Paper withBorder p="xs" radius="md" className="saved-view-card">
                  <Text size="xs" c="dimmed" fw={700} mb={6}>
                    Saved Views
                  </Text>
                  <Stack gap={6}>
                    <Select
                      label="View"
                      placeholder="Select saved view"
                      value={selectedViewId}
                      onChange={applySavedView}
                      clearable
                      data={savedViews.map((view) => ({
                        label: `${view.name}${view.selectedSpaceKey ? ` (${view.selectedSpaceKey})` : ""}`,
                        value: view.id,
                      }))}
                    />
                    <TextInput
                      label="View name"
                      value={savedViewName}
                      onChange={(event) => setSavedViewName(event.currentTarget.value)}
                      placeholder="ops triage"
                    />
                    <Group gap="xs" justify="space-between" align="center">
                      <Button
                        size="xs"
                        variant="light"
                        leftSection={<IconDeviceFloppy size={14} />}
                        onClick={saveCurrentView}
                      >
                        Save current
                      </Button>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconTrash size={14} />}
                        disabled={!selectedViewId}
                        onClick={deleteSavedView}
                      >
                        Delete
                      </Button>
                    </Group>
                  </Stack>
                </Paper>
              )}
              {showExpertModerationControls && pinnedPages.length > 0 && (
                <Paper withBorder p="xs" radius="md" className="pinned-pages-card">
                  <Text size="xs" c="dimmed" fw={700} mb={6}>
                    Pinned Pages
                  </Text>
                  <Group gap={6} wrap="wrap">
                    {pinnedPages.map((page) => (
                      <Button
                        key={`pinned-${page.slug}`}
                        size="compact-xs"
                        variant={selectedPageSlug === page.slug ? "filled" : "light"}
                        onClick={() => {
                          setSelectedSpaceKey(pageGroupKey(page.slug));
                          setSelectedPageSlug(page.slug);
                        }}
                        leftSection={
                          selectedPageSlug === page.slug ? <IconBookmarkFilled size={12} /> : <IconBookmark size={12} />
                        }
                      >
                        {page.title || page.slug}
                      </Button>
                    ))}
                  </Group>
                </Paper>
              )}
              {recentPages.length > 0 && (
                <Paper withBorder p="xs" radius="md">
                  <Text size="xs" c="dimmed" fw={700} mb={6}>
                    Recent Pages
                  </Text>
                  <Group gap={6} wrap="wrap">
                    {recentPages.map((page) => (
                      <Button
                        key={`recent-${page.slug}`}
                        size="compact-xs"
                        variant={selectedPageSlug === page.slug ? "filled" : "light"}
                        onClick={() => {
                          setSelectedSpaceKey(pageGroupKey(page.slug));
                          setSelectedPageSlug(page.slug);
                        }}
                      >
                        {page.title || page.slug}
                      </Button>
                    ))}
                  </Group>
                </Paper>
              )}
              {showExpertModerationControls && (
                <Paper withBorder p="xs" radius="md" className="guided-page-card">
                  <Group justify="space-between" align="center" mb={4}>
                    <Text size="xs" c="dimmed" fw={700}>
                      Guided Page Builder
                    </Text>
                    <ThemeIcon size="sm" variant="light" color="teal">
                      <IconFilePlus size={12} />
                    </ThemeIcon>
                  </Group>
                  <Stack gap={6}>
                  <TextInput
                    label="Space key"
                    value={guidedPageForm.spaceKey}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, spaceKey: event.currentTarget.value }))
                    }
                    placeholder="operations"
                  />
                  <TextInput
                    label="Page title"
                    value={guidedPageForm.title}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, title: event.currentTarget.value }))
                    }
                    placeholder="BC Omega access policy"
                  />
                  <TextInput
                    label="Slug"
                    value={guidedPageForm.slug}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, slug: event.currentTarget.value }))
                    }
                    placeholder="operations/bc-omega-access-policy"
                  />
                  <Group gap="xs" justify="space-between" align="center">
                    <Select
                      label="Status"
                      value={guidedPageForm.status}
                      onChange={(value) =>
                        setGuidedPageForm((prev) => ({
                          ...prev,
                          status: (value as "draft" | "published" | null) ?? "published",
                        }))
                      }
                      data={[
                        { label: "published", value: "published" },
                        { label: "draft", value: "draft" },
                      ]}
                    />
                    <TextInput
                      label="Type"
                      value={guidedPageForm.pageType}
                      onChange={(event) =>
                        setGuidedPageForm((prev) => ({ ...prev, pageType: event.currentTarget.value }))
                      }
                      placeholder="operations"
                    />
                  </Group>
                  <TextInput
                    label="Entity key (optional)"
                    value={guidedPageForm.entityKey}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, entityKey: event.currentTarget.value }))
                    }
                    placeholder="bc_omega"
                  />
                  <TextInput
                    label="Section heading"
                    value={guidedPageForm.sectionHeading}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, sectionHeading: event.currentTarget.value }))
                    }
                    placeholder="Access Rules"
                  />
                  <Textarea
                    label="First statement"
                    value={guidedPageForm.sectionStatement}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, sectionStatement: event.currentTarget.value }))
                    }
                    minRows={2}
                    placeholder="Gate entry requires access card after 10:00."
                  />
                  <TextInput
                    label="Change summary (optional)"
                    value={guidedPageForm.changeSummary}
                    onChange={(event) =>
                      setGuidedPageForm((prev) => ({ ...prev, changeSummary: event.currentTarget.value }))
                    }
                    placeholder="Created from moderation flow"
                  />
                  <Group gap="xs" justify="space-between" align="center">
                    <Button size="xs" variant="light" onClick={autofillGuidedFromDraft}>
                      Autofill from draft
                    </Button>
                    <Button size="xs" variant="subtle" onClick={suggestGuidedSlug}>
                      Normalize slug
                    </Button>
                  </Group>
                  <Button
                    size="xs"
                    color="teal"
                    leftSection={<IconFilePlus size={14} />}
                    loading={creatingPage}
                    onClick={() => void createGuidedWikiPage()}
                  >
                    Create Page
                  </Button>
                  {searchingGuidedMatches && (
                    <Text size="xs" c="dimmed">
                      checking similar pages…
                    </Text>
                  )}
                  {guidedPageMatches.length > 0 && (
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        Similar pages
                      </Text>
                      <Group gap={6} wrap="wrap">
                        {guidedPageMatches.map((item) => (
                          <Button
                            key={`guided-match-${item.id}`}
                            size="compact-xs"
                            variant="light"
                            onClick={() => {
                              setSelectedSpaceKey(pageGroupKey(item.slug));
                              setSelectedPageSlug(item.slug);
                            }}
                          >
                            {item.title || item.slug}
                          </Button>
                        ))}
                      </Group>
                    </Paper>
                  )}
                  {uiMode === "advanced" && (
                    <Paper withBorder p="xs" radius="md" className="retrieval-diagnostics-card">
                      <Stack gap={6}>
                        <Group justify="space-between" align="center">
                          <Text size="xs" fw={700}>
                            MCP Retrieval Diagnostics
                          </Text>
                          <Badge size="xs" color="teal" variant="light">
                            explain v1
                          </Badge>
                        </Group>
                        <TextInput
                          label="Query"
                          value={retrievalExplainQuery}
                          onChange={(event) => setRetrievalExplainQuery(event.currentTarget.value)}
                          placeholder="omega gate access card"
                        />
                        <TextInput
                          label="Related entity (optional graph hint)"
                          value={retrievalExplainRelatedEntity}
                          onChange={(event) => setRetrievalExplainRelatedEntity(event.currentTarget.value)}
                          placeholder="bc_omega"
                        />
                        <Select
                          label="Context policy mode"
                          value={retrievalExplainPolicyMode}
                          onChange={(value) =>
                            setRetrievalExplainPolicyMode(
                              value === "off" || value === "enforced" ? value : "advisory",
                            )
                          }
                          data={[
                            { value: "advisory", label: "advisory" },
                            { value: "enforced", label: "enforced" },
                            { value: "off", label: "off" },
                          ]}
                        />
                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={6}>
                          <TextInput
                            label="Min confidence"
                            value={retrievalExplainMinConfidence}
                            onChange={(event) => setRetrievalExplainMinConfidence(event.currentTarget.value)}
                            placeholder="0.45"
                          />
                          <TextInput
                            label="Min total score"
                            value={retrievalExplainMinTotalScore}
                            onChange={(event) => setRetrievalExplainMinTotalScore(event.currentTarget.value)}
                            placeholder="0.20"
                          />
                          <TextInput
                            label="Min lexical score"
                            value={retrievalExplainMinLexicalScore}
                            onChange={(event) => setRetrievalExplainMinLexicalScore(event.currentTarget.value)}
                            placeholder="0.08"
                          />
                          <TextInput
                            label="Min token overlap ratio"
                            value={retrievalExplainMinTokenOverlap}
                            onChange={(event) => setRetrievalExplainMinTokenOverlap(event.currentTarget.value)}
                            placeholder="0.15"
                          />
                        </SimpleGrid>
                        <Button
                          size="xs"
                          variant="light"
                          color="teal"
                          leftSection={<IconSearch size={14} />}
                          loading={loadingRetrievalExplain}
                          onClick={() => void runRetrievalExplain()}
                        >
                          Explain retrieval
                        </Button>
                        {retrievalExplainGraphConfig && (
                          <Paper withBorder p="xs" radius="md" className="retrieval-graph-config-card">
                            <Stack gap={4}>
                              <Group justify="space-between" align="center" wrap="nowrap">
                                <Text size="xs" fw={700}>
                                  Runtime graph config
                                </Text>
                                <Badge size="xs" variant="light" color="indigo">
                                  shared contract
                                </Badge>
                              </Group>
                              <Group gap={6} wrap="wrap">
                                <Badge size="xs" variant="light" color="teal">
                                  max hops {retrievalExplainGraphConfig.max_graph_hops}
                                </Badge>
                                <Badge size="xs" variant="light" color="grape">
                                  hop1 +{retrievalExplainGraphConfig.boost_hop1.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="grape">
                                  hop2 +{retrievalExplainGraphConfig.boost_hop2.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="grape">
                                  hop3 +{retrievalExplainGraphConfig.boost_hop3.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="gray">
                                  other +{retrievalExplainGraphConfig.boost_other.toFixed(2)}
                                </Badge>
                              </Group>
                              <Text size="xs" c="dimmed">
                                Source env: SYNAPSE_MCP_GRAPH_MAX_HOPS / SYNAPSE_MCP_GRAPH_BOOST_HOP1 / HOP2 / HOP3 /
                                OTHER
                              </Text>
                            </Stack>
                          </Paper>
                        )}
                        {retrievalExplainContextPolicy && (
                          <Paper withBorder p="xs" radius="md">
                            <Stack gap={4}>
                              <Group justify="space-between" align="center">
                                <Text size="xs" fw={700}>
                                  Context injection policy
                                </Text>
                                <Badge
                                  size="xs"
                                  variant="light"
                                  color={retrievalExplainContextPolicy.mode === "enforced" ? "orange" : "indigo"}
                                >
                                  {retrievalExplainContextPolicy.mode}
                                </Badge>
                              </Group>
                              <Group gap={6} wrap="wrap">
                                <Badge size="xs" variant="light" color="teal">
                                  min conf {retrievalExplainContextPolicy.min_confidence.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="blue">
                                  min total {retrievalExplainContextPolicy.min_total_score.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="blue">
                                  min lexical {retrievalExplainContextPolicy.min_lexical_score.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color="gray">
                                  min overlap {retrievalExplainContextPolicy.min_token_overlap_ratio.toFixed(2)}
                                </Badge>
                                <Badge size="xs" variant="light" color={retrievalExplainPolicyFilteredOut > 0 ? "orange" : "gray"}>
                                  filtered {retrievalExplainPolicyFilteredOut}
                                </Badge>
                              </Group>
                            </Stack>
                          </Paper>
                        )}
                        {retrievalExplainResults.length === 0 ? (
                          <Text size="xs" c="dimmed">
                            Run diagnostics to inspect MCP retrieval ranking reasons.
                          </Text>
                        ) : (
                          <Stack gap={6}>
                            {retrievalExplainResults.map((item) => (
                              <Paper key={`retrieval-explain-${item.statement_id}`} withBorder p="xs" radius="md">
                                <Stack gap={4}>
                                  <Group justify="space-between" align="center" wrap="nowrap">
                                    <Text size="xs" fw={700}>
                                      {item.page.title || item.page.slug}
                                    </Text>
                                    <Badge size="xs" variant="light" color="blue">
                                      score {item.score.toFixed(3)}
                                    </Badge>
                                  </Group>
                                  <Text size="xs" c="dimmed">
                                    {item.page.slug}
                                  </Text>
                                  <Text size="xs" className="retrieval-statement-snippet">
                                    {item.statement_text}
                                  </Text>
                                  <Text size="xs" c="dimmed">
                                    {item.retrieval_reason}
                                  </Text>
                                  <Group gap={6} wrap="wrap">
                                    <Badge size="xs" variant="light" color="gray">
                                      lexical {item.score_breakdown.lexical.toFixed(3)}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="grape">
                                      graph {item.score_breakdown.graph.toFixed(3)}
                                    </Badge>
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={item.context_policy?.eligible ? "teal" : "orange"}
                                    >
                                      conf {Number(item.retrieval_confidence || 0).toFixed(2)}
                                    </Badge>
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={item.context_policy?.eligible ? "teal" : "orange"}
                                    >
                                      {item.context_policy?.eligible ? "eligible" : "blocked"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="orange">
                                      tokens {item.score_breakdown.lexical_components.token_overlap_hits}/
                                      {item.score_breakdown.lexical_components.query_tokens_total}
                                    </Badge>
                                    {!item.context_policy?.eligible && item.context_policy?.blocked_by?.length ? (
                                      <Badge size="xs" variant="light" color="red">
                                        {item.context_policy.blocked_by.join(", ")}
                                      </Badge>
                                    ) : null}
                                  </Group>
                                </Stack>
                              </Paper>
                            ))}
                          </Stack>
                        )}
                      </Stack>
                    </Paper>
                  )}
                  </Stack>
                </Paper>
              )}
            </Stack>
            <ScrollArea h={640} type="auto">
              <Stack gap="sm">
                {pageGroups.length === 0 && (
                  <Paper withBorder p="md" radius="lg">
                    <Text c="dimmed">No pages in current draft scope.</Text>
                  </Paper>
                )}
                {pageGroups.map(([group, items]) => (
                  <Paper key={group} withBorder p="sm" radius="md">
                    <Group justify="space-between" align="center" wrap="nowrap">
                      <Group gap={8} wrap="nowrap">
                        <Text size="xs" c="dimmed" fw={700}>
                          {group}
                        </Text>
                        <Badge size="xs" variant="light" color="indigo">
                          {items.length}
                        </Badge>
                        <Badge size="xs" variant="light" color="orange">
                          {items.reduce((acc, page) => acc + page.open_count, 0)} open
                        </Badge>
                      </Group>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => setCollapsedSpaces((prev) => ({ ...prev, [group]: !prev[group] }))}
                        aria-label={`Toggle ${group}`}
                      >
                        {collapsedSpaces[group] ? <IconChevronDown size={14} /> : <IconChevronUp size={14} />}
                      </ActionIcon>
                    </Group>
                    {!collapsedSpaces[group] && (
                      <Stack gap={6} mt={6}>
                        {items.map((page) => (
                          <Card
                            key={page.slug}
                            withBorder
                            radius="md"
                            p="xs"
                            className={selectedPageSlug === page.slug ? "draft-card active" : "draft-card"}
                            onClick={() => {
                              setSelectedSpaceKey(pageGroupKey(page.slug));
                              setSelectedPageSlug(page.slug);
                            }}
                          >
                            <Group justify="space-between" align="flex-start" wrap="nowrap">
                              <Stack gap={2}>
                                <Text size="sm" fw={700}>
                                  {page.title || page.slug}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  {page.slug}
                                </Text>
                              </Stack>
                              <Stack gap={2} align="flex-end">
                                <ActionIcon
                                  size="sm"
                                  variant="subtle"
                                  color={pinnedPageSlugs.includes(page.slug) ? "yellow" : "gray"}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    togglePinPage(page.slug);
                                  }}
                                  aria-label={pinnedPageSlugs.includes(page.slug) ? "Unpin page" : "Pin page"}
                                >
                                  {pinnedPageSlugs.includes(page.slug) ? (
                                    <IconBookmarkFilled size={14} />
                                  ) : (
                                    <IconBookmark size={14} />
                                  )}
                                </ActionIcon>
                                <Badge size="xs" variant="light" color="blue">
                                  drafts {page.draft_count}
                                </Badge>
                                <Badge size="xs" variant="light" color="orange">
                                  open {page.open_count}
                                </Badge>
                              </Stack>
                            </Group>
                            {selectedPageSlug === page.slug && loadingPageDetail && (
                              <Group mt={6}>
                                <Loader size="xs" />
                                <Text size="xs" c="dimmed">
                                  loading page sections
                                </Text>
                              </Group>
                            )}
                            {selectedPageSlug === page.slug &&
                              selectedPageDetail &&
                              selectedPageDetail.sections.length > 0 && (
                                <Stack gap={2} mt={6}>
                                  {selectedPageDetail.sections.slice(0, 6).map((section) => (
                                    <Text key={section.section_key} size="xs" c="dimmed">
                                      {section.heading} ({section.statement_count})
                                    </Text>
                                  ))}
                                </Stack>
                              )}
                          </Card>
                        ))}
                      </Stack>
                    )}
                  </Paper>
                ))}
              </Stack>
            </ScrollArea>
          </Paper>

          <Paper radius="xl" p="lg">
            <Group justify="space-between" mb="sm">
              <Title order={3}>Draft Inbox</Title>
              <Badge size="lg" color="teal" variant="light">
                {visibleDrafts.length}/{scopedDrafts.length}
              </Badge>
            </Group>
            <Stack gap={6} mb="sm">
              <TextInput
                label="Draft filter"
                value={draftFilter}
                onChange={(event) => setDraftFilter(event.currentTarget.value)}
                placeholder="Filter by page, section, or decision"
              />
              {selectedSpaceKey && (
                <Text size="xs" c="dimmed">
                  Space scope: <Code>{selectedSpaceTitle}</Code>
                </Text>
              )}
            </Stack>
            <Paper withBorder p="xs" radius="md" mb="sm" className="queue-presets-card">
              <Stack gap={8}>
                <Group justify="space-between" align="center" wrap="wrap">
                  <Text size="sm" fw={700}>
                    {showExpertModerationControls ? "Review Queue Presets" : "Core Review Queue"}
                  </Text>
                  {showExpertModerationControls ? (
                    <Group gap="xs" wrap="wrap">
                      <Select
                        label="Queue preset"
                        value={reviewQueuePreset}
                        onChange={(value) => setReviewQueuePreset((value as ReviewQueuePresetKey | null) ?? "open_queue")}
                        data={REVIEW_QUEUE_PRESETS.map((item) => ({ value: item.key, label: item.label }))}
                        allowDeselect={false}
                        w={190}
                      />
                      <Select
                        label="SLA threshold (hours)"
                        value={String(reviewSlaHours)}
                        onChange={(value) => {
                          if (!value) return;
                          const parsed = Number(value);
                          if (!Number.isFinite(parsed)) return;
                          setReviewSlaHours(Math.max(1, Math.min(168, Math.round(parsed))));
                        }}
                        data={[
                          { value: "6", label: "6h" },
                          { value: "12", label: "12h" },
                          { value: "24", label: "24h" },
                          { value: "48", label: "48h" },
                          { value: "72", label: "72h" },
                          { value: "168", label: "168h" },
                        ]}
                        allowDeselect={false}
                        w={170}
                      />
                    </Group>
                  ) : (
                    <Badge variant="light" color="teal">
                      open queue only
                    </Badge>
                  )}
                </Group>
                {showExpertModerationControls && (
                  <Group gap={6} wrap="wrap">
                    {REVIEW_QUEUE_PRESETS.map((preset) => (
                      <Button
                        key={preset.key}
                        size="compact-xs"
                        variant={reviewQueuePreset === preset.key ? "filled" : "light"}
                        color={reviewQueuePreset === preset.key ? "teal" : "gray"}
                        onClick={() => setReviewQueuePreset(preset.key)}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </Group>
                )}
                <Text size="xs" c="dimmed">
                  {showExpertModerationControls
                    ? selectedQueuePreset.description
                    : "Core queue prioritizes pending and blocked drafts by oldest first. Enable expert controls for custom presets."}
                </Text>
                <Paper withBorder p="xs" radius="md" className="queue-sla-card">
                  <Text size="xs" fw={700} mb={6}>
                    {showExpertModerationControls ? "Queue health metrics" : "Core queue snapshot"}
                  </Text>
                  <SimpleGrid cols={{ base: 2, md: showExpertModerationControls ? 3 : 2 }} spacing="xs">
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" c="dimmed">
                        Open
                      </Text>
                      <Text fw={700}>{queueMetrics.openCount}</Text>
                    </Paper>
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" c="dimmed">
                        SLA breaches
                      </Text>
                      <Text fw={700}>{queueMetrics.breachCount}</Text>
                    </Paper>
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" c="dimmed">
                        Conflicts
                      </Text>
                      <Text fw={700}>{queueMetrics.conflictCount}</Text>
                    </Paper>
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" c="dimmed">
                        Oldest wait
                      </Text>
                      <Text fw={700}>{formatHours(queueMetrics.oldestAge)}</Text>
                    </Paper>
                    {showExpertModerationControls && (
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          High confidence
                        </Text>
                        <Text fw={700}>{queueMetrics.highConfidenceCount}</Text>
                      </Paper>
                    )}
                    {showExpertModerationControls && (
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Median wait
                        </Text>
                        <Text fw={700}>{formatHours(queueMetrics.medianAge)}</Text>
                      </Paper>
                    )}
                  </SimpleGrid>
                </Paper>
                {showExpertModerationControls && (
                  <Paper withBorder p="xs" radius="md" className="moderation-throughput-card">
                  <Group justify="space-between" align="center" mb={6}>
                    <Text size="xs" fw={700}>
                      Moderation throughput (24h)
                    </Text>
                    <Badge
                      size="xs"
                      variant="light"
                      color={moderationHealthColor(moderationThroughput?.health)}
                    >
                      {moderationThroughput?.health || "n/a"}
                    </Badge>
                  </Group>
                  {loadingModerationThroughput ? (
                    <Group gap={6}>
                      <Loader size="xs" />
                      <Text size="xs" c="dimmed">
                        refreshing throughput
                      </Text>
                    </Group>
                  ) : moderationThroughput ? (
                    <Stack gap={6}>
                      <SimpleGrid cols={{ base: 2, md: 3 }} spacing="xs">
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Actions
                          </Text>
                          <Text fw={700}>{moderationThroughput.metrics.actions_total}</Text>
                        </Paper>
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Approve rate
                          </Text>
                          <Text fw={700}>{formatPercent(moderationThroughput.metrics.approval_rate)}</Text>
                        </Paper>
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            p50 decision
                          </Text>
                          <Text fw={700}>{formatMinutes(moderationThroughput.metrics.latency_minutes.p50)}</Text>
                        </Paper>
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Active reviewers
                          </Text>
                          <Text fw={700}>{moderationThroughput.metrics.reviewers_active}</Text>
                        </Paper>
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Backlog delta
                          </Text>
                          <Text fw={700}>{moderationThroughput.metrics.net_backlog_delta}</Text>
                        </Paper>
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Conflict unblocks
                          </Text>
                          <Text fw={700}>{moderationThroughput.metrics.conflict_unblocks}</Text>
                        </Paper>
                      </SimpleGrid>
                      {moderationThroughput.alerts.length > 0 && (
                        <Stack gap={2}>
                          {moderationThroughput.alerts.slice(0, 2).map((item, index) => (
                            <Text key={`throughput-alert-${index}`} size="xs" c="dimmed">
                              - {item}
                            </Text>
                          ))}
                        </Stack>
                      )}
                      {moderationThroughput.top_reviewers.length > 0 && (
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" fw={700} mb={4}>
                            Top reviewers
                          </Text>
                          <Stack gap={3}>
                            {moderationThroughput.top_reviewers.map((item) => (
                              <Group key={`reviewer-${item.reviewed_by}`} justify="space-between" align="center">
                                <Text size="xs">{item.reviewed_by}</Text>
                                <Badge size="xs" variant="light" color="indigo">
                                  {item.actions_total}
                                </Badge>
                              </Group>
                            ))}
                          </Stack>
                        </Paper>
                      )}
                    </Stack>
                  ) : (
                    <Text size="xs" c="dimmed">
                      Throughput metrics appear after refresh with a valid project id.
                    </Text>
                  )}
                  </Paper>
                )}
                <Paper withBorder p="xs" radius="md" className="triage-lane-card">
                  <Group justify="space-between" align="center" mb={6}>
                    <Text size="xs" fw={700}>
                      Triage lane
                    </Text>
                    <Badge variant="light" color="grape">
                      top {triageLaneEntries.length}
                    </Badge>
                  </Group>
                  {triageLaneEntries.length === 0 ? (
                    <Text size="xs" c="dimmed">
                      No open drafts in current scope.
                    </Text>
                  ) : (
                    <Stack gap={6}>
                      {triageLaneEntries.map((entry) => {
                        const draft = entry.draft;
                        const ageHours = draftAgeHours(draft, Date.now());
                        const reasonLimit = showExpertModerationControls ? 4 : 2;
                        return (
                          <Paper key={`triage-${draft.id}`} withBorder radius="md" p="xs">
                            <Group justify="space-between" align="center" wrap="nowrap">
                              <Stack gap={2}>
                                <Button
                                  variant="subtle"
                                  size="compact-sm"
                                  onClick={() => openDraftFromTriage(draft)}
                                  styles={{ root: { paddingInline: 0, height: "auto" } }}
                                  aria-label={`Open draft ${draft.id} from triage`}
                                >
                                  {draft.page.title || draft.page.slug || draft.section_key || "Untitled page"}
                                </Button>
                                <Group gap={6}>
                                  <Badge size="xs" color={statusColor(draft.status)} variant="light">
                                    {draft.status}
                                  </Badge>
                                  <Badge size="xs" color={ageBadgeColor(ageHours, reviewSlaHours)} variant="light">
                                    {formatHours(ageHours)}
                                  </Badge>
                                  <Badge size="xs" variant="light" color={Number(draft.confidence) >= 0.85 ? "teal" : "gray"}>
                                    conf {draft.confidence.toFixed(2)}
                                  </Badge>
                                </Group>
                                <Group gap={4} wrap="wrap">
                                  {entry.reasons.slice(0, reasonLimit).map((reason) => (
                                    <Badge
                                      key={`triage-reason-${draft.id}-${reason.key}`}
                                      size="xs"
                                      variant="outline"
                                      color={reason.color}
                                    >
                                      {reason.label}
                                    </Badge>
                                  ))}
                                  <Badge size="xs" variant="light" color="indigo">
                                    score {entry.score.toFixed(0)}
                                  </Badge>
                                </Group>
                              </Stack>
                              <Group gap={6}>
                                <Tooltip label="Quick approve">
                                  <ActionIcon
                                    size="sm"
                                    variant="light"
                                    color="teal"
                                    disabled={!canQuickModerateFromInbox}
                                    loading={runningAction}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void quickModerateDraft(draft, "approve", "triage_lane");
                                    }}
                                    aria-label="Quick approve draft"
                                  >
                                    <IconCheck size={14} />
                                  </ActionIcon>
                                </Tooltip>
                                <Tooltip label="Quick reject">
                                  <ActionIcon
                                    size="sm"
                                    variant="light"
                                    color="red"
                                    disabled={!canQuickModerateFromInbox}
                                    loading={runningAction}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void quickModerateDraft(draft, "reject", "triage_lane");
                                    }}
                                    aria-label="Quick reject draft"
                                  >
                                    <IconX size={14} />
                                  </ActionIcon>
                                </Tooltip>
                              </Group>
                            </Group>
                          </Paper>
                        );
                      })}
                      <Text size="xs" c="dimmed">
                        Queue priority signals combine conflict state, SLA age, and confidence.
                      </Text>
                    </Stack>
                  )}
                </Paper>
                <Paper withBorder p="xs" radius="md" className="core-intent-signals-card">
                  <Stack gap={6}>
                    <Group justify="space-between" align="center" wrap="wrap">
                      <Text size="xs" fw={700}>
                        Intent Signals (Session)
                      </Text>
                      <Badge size="xs" variant="light" color="indigo">
                        quick actions/hour {coreIntentSummary.quickActionsPerHour.toFixed(1)}
                      </Badge>
                    </Group>
                    <SimpleGrid cols={{ base: 2, md: showExpertModerationControls ? 4 : 3 }} spacing="xs">
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Triage opens
                        </Text>
                        <Text fw={700}>{coreIntentSummary.triageOpenCount}</Text>
                      </Paper>
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Unique triage drafts
                        </Text>
                        <Text fw={700}>{coreIntentSummary.triageUniqueDrafts}</Text>
                      </Paper>
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Quick approve
                        </Text>
                        <Text fw={700}>{coreIntentSummary.quickApproveCount}</Text>
                      </Paper>
                      <Paper withBorder p="xs" radius="md">
                        <Text size="xs" c="dimmed">
                          Quick reject
                        </Text>
                        <Text fw={700}>{coreIntentSummary.quickRejectCount}</Text>
                      </Paper>
                    </SimpleGrid>
                    <Group gap={6} wrap="wrap">
                      <Badge size="xs" variant="light" color="grape">
                        triage quick {coreIntentSummary.quickFromTriage}
                      </Badge>
                      <Badge size="xs" variant="light" color="blue">
                        inbox quick {coreIntentSummary.quickFromInbox}
                      </Badge>
                      <Badge size="xs" variant="light" color="teal">
                        detail quick {coreIntentSummary.quickFromDetail}
                      </Badge>
                    </Group>
                    <Text size="xs" c="dimmed">
                      {coreIntentSummary.lastAction
                        ? `Last action: ${coreIntentSummary.lastAction.label} at ${new Date(coreIntentSummary.lastAction.timestampMs).toLocaleTimeString()}.`
                        : "No triage or quick moderation actions recorded in this session yet."}
                    </Text>
                  </Stack>
                </Paper>
              </Stack>
            </Paper>
            {showExpertModerationControls && (
              <Paper withBorder p="xs" radius="md" mb="sm" className="bulk-actions-card">
                <Stack gap={6}>
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Checkbox
                      label={`Select all visible (${visibleDrafts.length})`}
                      checked={allVisibleSelected}
                      indeterminate={bulkSelectedVisibleCount > 0 && !allVisibleSelected}
                      onChange={(event) => selectAllVisibleDrafts(event.currentTarget.checked)}
                    />
                    <Badge variant="light" color={bulkSelectedVisibleCount > 0 ? "teal" : "gray"}>
                      selected {bulkSelectedVisibleCount}
                    </Badge>
                  </Group>
                  <TextInput
                    label="Bulk approve note (optional)"
                    value={bulkApproveNote}
                    onChange={(event) => setBulkApproveNote(event.currentTarget.value)}
                    placeholder="Approved after cross-check."
                  />
                  <TextInput
                    label="Bulk reject reason (optional)"
                    value={bulkRejectReason}
                    onChange={(event) => setBulkRejectReason(event.currentTarget.value)}
                    placeholder="Conflicting with current policy."
                  />
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Checkbox
                      label="Force approve conflicts in bulk"
                      checked={bulkForceApprove}
                      onChange={(event) => setBulkForceApprove(event.currentTarget.checked)}
                    />
                    <Group gap="xs">
                    <Button
                      size="xs"
                      variant="light"
                      color="teal"
                      disabled={bulkSelectedVisibleCount === 0 || runningAction}
                      loading={runningAction}
                      onClick={() => void runBulkModeration("approve")}
                    >
                      {bulkApproveArmed ? "Confirm Approve Selected" : "Approve Selected"}
                    </Button>
                    <Button
                      size="xs"
                      variant="light"
                      color="red"
                      disabled={bulkSelectedVisibleCount === 0 || runningAction}
                      loading={runningAction}
                      onClick={() => void runBulkModeration("reject")}
                    >
                      {bulkRejectArmed ? "Confirm Reject Selected" : "Reject Selected"}
                    </Button>
                      <Button
                        size="xs"
                        variant="subtle"
                        disabled={bulkSelectedVisibleCount === 0}
                        onClick={() =>
                          setBulkSelectedDraftIds((prev) =>
                            prev.filter((id) => !visibleDrafts.some((item) => item.id === id)),
                          )
                        }
                      >
                        Clear
                      </Button>
                    </Group>
                  </Group>
                </Stack>
              </Paper>
            )}
            {selectedPageSlug && (
              <Paper withBorder p="xs" radius="md" mb="sm">
                <Text size="xs" c="dimmed">
                  Filtered by page: <Code>{selectedPageTitle}</Code>
                </Text>
              </Paper>
            )}
            <ScrollArea h={680} type="auto">
              <Stack gap="sm">
                {visibleDrafts.length === 0 && (
                  <Paper withBorder p="md" radius="lg">
                    <Text c="dimmed">No drafts found for current page scope.</Text>
                  </Paper>
                )}
                {visibleDrafts.map((draft) => {
                  const ageHours = draftAgeHours(draft, Date.now());
                  return (
                    <Card
                      key={draft.id}
                      radius="lg"
                      withBorder
                      className={`${draft.id === selectedDraftId ? "draft-card active" : "draft-card"} draft-card-status-${draft.status}`}
                      onClick={() => setSelectedDraftId(draft.id)}
                    >
                      <Group justify="space-between" align="center">
                        <Group gap="xs" align="flex-start" wrap="nowrap">
                          {showExpertModerationControls && (
                            <Checkbox
                              checked={bulkSelectedDraftIds.includes(draft.id)}
                              onClick={(event) => event.stopPropagation()}
                              onChange={() => toggleBulkDraftSelection(draft.id)}
                              aria-label={`Select draft ${draft.id}`}
                            />
                          )}
                          <Stack gap={2}>
                            <Text fw={700}>{draft.page.title || draft.page.slug || draft.section_key || "Untitled page"}</Text>
                            <Group gap={6}>
                              <Badge size="xs" variant="light" color="gray">
                                {draft.decision}
                              </Badge>
                              <Badge size="xs" variant="light" color={Number(draft.confidence) >= 0.85 ? "teal" : "gray"}>
                                conf {draft.confidence.toFixed(2)}
                              </Badge>
                              <Badge size="xs" variant="light" color={ageBadgeColor(ageHours, reviewSlaHours)}>
                                wait {formatHours(ageHours)}
                              </Badge>
                            </Group>
                          </Stack>
                        </Group>
                        <Stack gap={4} align="flex-end">
                          <Badge color={statusColor(draft.status)} variant="light">
                            {draft.status}
                          </Badge>
                          {isOpenReviewDraft(draft) && (
                            <Group gap={6}>
                              <Tooltip label="Quick approve">
                                <ActionIcon
                                  size="sm"
                                  variant="light"
                                  color="teal"
                                  disabled={!canQuickModerateFromInbox}
                                  loading={runningAction}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void quickModerateDraft(draft, "approve", "inbox_card");
                                  }}
                                  aria-label="Quick approve draft"
                                >
                                  <IconCheck size={14} />
                                </ActionIcon>
                              </Tooltip>
                              <Tooltip label="Quick reject">
                                <ActionIcon
                                  size="sm"
                                  variant="light"
                                  color="red"
                                  disabled={!canQuickModerateFromInbox}
                                  loading={runningAction}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void quickModerateDraft(draft, "reject", "inbox_card");
                                  }}
                                  aria-label="Quick reject draft"
                                >
                                  <IconX size={14} />
                                </ActionIcon>
                              </Tooltip>
                            </Group>
                          )}
                        </Stack>
                      </Group>
                      <Text size="xs" c="dimmed" mt={8}>
                        {fmtDate(draft.created_at)}
                      </Text>
                    </Card>
                  );
                })}
              </Stack>
            </ScrollArea>
          </Paper>

          <Paper radius="xl" p="lg">
            <Group justify="space-between" mb="sm">
              <Group gap="xs">
                <Title order={3}>Draft Detail</Title>
                {selectedDraftId ? (
                  <Badge color={statusColor(draftDetail?.draft.status ?? "pending_review")} variant="light">
                    {draftDetail?.draft.status ?? "loading"}
                  </Badge>
                ) : (
                  <Badge color="gray" variant="light">
                    not selected
                  </Badge>
                )}
              </Group>
              {selectedDraftSummary && (
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="light"
                    color="teal"
                    disabled={!canQuickModerateFromInbox}
                    loading={runningAction}
                    onClick={() => void quickModerateDraft(selectedDraftSummary, "approve", "detail_header")}
                  >
                    Quick Approve
                  </Button>
                  <Button
                    size="xs"
                    variant="light"
                    color="red"
                    disabled={!canQuickModerateFromInbox}
                    loading={runningAction}
                    onClick={() => void quickModerateDraft(selectedDraftSummary, "reject", "detail_header")}
                  >
                    Quick Reject
                  </Button>
                </Group>
              )}
            </Group>
            <Breadcrumbs mb="sm" separator="›">
              <Text size="xs" c="dimmed">
                Wiki
              </Text>
              <Text size="xs" c="dimmed">
                {selectedSpaceTitle}
              </Text>
              <Text size="xs" c="dimmed">
                {selectedPageTitle}
              </Text>
              <Text size="xs" c="dimmed">
                {selectedDraftId ? `Draft ${selectedDraftId.slice(0, 8)}` : "No draft"}
              </Text>
            </Breadcrumbs>
            {!selectedDraftId && (
              <Paper withBorder p="xl" radius="lg">
                <Group>
                  <IconExclamationCircle size={20} />
                  <Text c="dimmed">Select draft in inbox to inspect semantic diff and moderate it.</Text>
                </Group>
              </Paper>
            )}
            {selectedDraftId && loadingDetail && (
              <Group justify="center" py="xl">
                <Loader />
              </Group>
            )}
            {selectedDraftId && draftDetail && !loadingDetail && (
              <Stack gap="md">
                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                  <Paper withBorder p="sm" radius="md">
                    <Text size="xs" c="dimmed">
                      Draft ID
                    </Text>
                    <Code>{draftDetail.draft.id}</Code>
                  </Paper>
                  <Paper withBorder p="sm" radius="md">
                    <Text size="xs" c="dimmed">
                      Page
                    </Text>
                    <Code>{draftDetail.draft.page.slug || "—"}</Code>
                  </Paper>
                  <Paper withBorder p="sm" radius="md">
                    <Text size="xs" c="dimmed">
                      Decision
                    </Text>
                    <Code>{draftDetail.draft.decision}</Code>
                  </Paper>
                  <Paper withBorder p="sm" radius="md">
                    <Text size="xs" c="dimmed">
                      Confidence
                    </Text>
                    <Code>{draftDetail.draft.confidence.toFixed(3)}</Code>
                  </Paper>
                </SimpleGrid>

                {showExpertModerationControls && pageTocSections.length > 0 && (
                  <Paper withBorder p="sm" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text fw={700}>Section TOC</Text>
                      <Text size="xs" c="dimmed">
                        {pageTocSections.length} sections
                      </Text>
                    </Group>
                    <Group gap={6} wrap="wrap">
                      {pageTocSections.map((section) => (
                        <Button
                          key={`toc-${section.section_key}`}
                          size="compact-xs"
                          variant={selectedTocSectionKey === section.section_key ? "filled" : "light"}
                          color={selectedTocSectionKey === section.section_key ? "teal" : "gray"}
                          onClick={() => {
                            setSelectedTocSectionKey(section.section_key);
                            setDetailTab("page");
                          }}
                        >
                          {section.heading} ({section.statement_count})
                        </Button>
                      ))}
                    </Group>
                    {selectedTocSection && (
                      <Paper withBorder p="xs" radius="md" mt="sm" className="toc-preview-card">
                        <Group justify="space-between" align="center" mb={4}>
                          <Text size="xs" fw={700}>
                            {selectedTocSection.heading}
                          </Text>
                          <Group gap={6}>
                            <Button
                              size="compact-xs"
                              variant="light"
                              onClick={() =>
                                setApproveForm((prev) => ({
                                  ...prev,
                                  sectionKey: selectedTocSection.section_key,
                                  sectionHeading: selectedTocSection.heading,
                                }))
                              }
                            >
                              Use section in form
                            </Button>
                            <Button size="compact-xs" variant="subtle" onClick={() => setDetailTab("page")}>
                              Open page tab
                            </Button>
                          </Group>
                        </Group>
                        <Stack gap={4}>
                          {selectedTocSection.statements.slice(0, 3).map((statement) => (
                            <Text key={statement.id} size="xs" c="dimmed">
                              • {statement.statement_text}
                            </Text>
                          ))}
                          {selectedTocSection.statements.length === 0 && (
                            <Text size="xs" c="dimmed">
                              No active statements in this section yet.
                            </Text>
                          )}
                        </Stack>
                      </Paper>
                    )}
                  </Paper>
                )}

                <Tabs value={detailTab} onChange={(value) => setDetailTab((value as DetailTab | null) ?? "semantic")}>
                  <Tabs.List>
                    {showExpertModerationControls && <Tabs.Tab value="page">Wiki Page</Tabs.Tab>}
                    {showExpertModerationControls && <Tabs.Tab value="history">Page History</Tabs.Tab>}
                    <Tabs.Tab value="semantic">Semantic Diff</Tabs.Tab>
                    <Tabs.Tab value="conflicts">Conflict Resolver</Tabs.Tab>
                    {showExpertModerationControls && <Tabs.Tab value="patch">Markdown Patch</Tabs.Tab>}
                    <Tabs.Tab value="evidence">Evidence</Tabs.Tab>
                    {showExpertModerationControls && <Tabs.Tab value="timeline">Timeline</Tabs.Tab>}
                  </Tabs.List>

                  {showExpertModerationControls && (
                    <Tabs.Panel value="page" pt="sm">
                      <Suspense
                      fallback={
                        <Paper withBorder p="md" radius="md">
                          <Group justify="center" py="sm">
                            <Loader size="sm" />
                            <Text size="sm" c="dimmed">
                              Loading wiki editor…
                            </Text>
                          </Group>
                        </Paper>
                      }
                    >
                      <LazyWikiPageCanvas
                        title={draftDetail.draft.page.title || draftDetail.draft.page.slug || "Untitled page"}
                        slug={draftDetail.draft.page.slug}
                        markdown={selectedPageDetail?.latest_version?.markdown || ""}
                        onApplyEditedStatement={(value) => {
                          setApproveForm((prev) => ({ ...prev, editedStatement: value }));
                          notifications.show({
                            color: "teal",
                            title: "Editor applied",
                            message: "Copied page text into Approve form edited statement.",
                          });
                        }}
                      />
                      </Suspense>
                    </Tabs.Panel>
                  )}

                  {showExpertModerationControls && (
                    <Tabs.Panel value="history" pt="sm">
                      <Paper withBorder p="sm" radius="md" className="page-history-card">
                      <Group justify="space-between" align="center" mb="sm">
                        <Group gap={6}>
                          <ThemeIcon variant="light" color="indigo">
                            <IconHistory size={14} />
                          </ThemeIcon>
                          <Text fw={700}>Version history</Text>
                        </Group>
                        <Badge variant="light" color="indigo">
                          {(pageHistory?.versions ?? []).length} versions
                        </Badge>
                      </Group>
                      {loadingPageHistory && (
                        <Group py="sm">
                          <Loader size="sm" />
                          <Text size="sm" c="dimmed">
                            loading history…
                          </Text>
                        </Group>
                      )}
                      {!loadingPageHistory && (!pageHistory || (pageHistory.versions ?? []).length === 0) && (
                        <Text size="sm" c="dimmed">
                          Page history is not available for this page yet.
                        </Text>
                      )}
                      {!loadingPageHistory && pageHistory && pageHistory.versions.length > 0 && (
                        <Stack gap="sm">
                          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                            <Select
                              label="Base version"
                              value={historyBaseVersion}
                              onChange={setHistoryBaseVersion}
                              data={pageHistoryOptions}
                            />
                            <Select
                              label="Target version"
                              value={historyTargetVersion}
                              onChange={setHistoryTargetVersion}
                              data={pageHistoryOptions}
                            />
                          </SimpleGrid>
                          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed">
                                Base metadata
                              </Text>
                              <Text size="sm">
                                v{selectedHistoryBase?.version ?? "—"} • {fmtDate(selectedHistoryBase?.created_at)}
                              </Text>
                              <Text size="xs" c="dimmed">
                                {selectedHistoryBase?.change_summary || "No summary"}
                              </Text>
                            </Paper>
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed">
                                Target metadata
                              </Text>
                              <Text size="sm">
                                v{selectedHistoryTarget?.version ?? "—"} • {fmtDate(selectedHistoryTarget?.created_at)}
                              </Text>
                              <Text size="xs" c="dimmed">
                                {selectedHistoryTarget?.change_summary || "No summary"}
                              </Text>
                            </Paper>
                          </SimpleGrid>
                          <Divider />
                          <Text fw={600} size="sm">
                            Markdown compare
                          </Text>
                          <Box className="diff-block">
                            <DiffLine label={`v${selectedHistoryBase?.version ?? "?"}`} tokens={pageHistoryDiff.before} />
                            <Divider my="sm" />
                            <DiffLine label={`v${selectedHistoryTarget?.version ?? "?"}`} tokens={pageHistoryDiff.after} />
                          </Box>
                          <Group justify="flex-end">
                            <Button
                              size="xs"
                              variant="light"
                              onClick={() => {
                                const targetMarkdown = String(selectedHistoryTarget?.markdown || "").trim();
                                if (!targetMarkdown) return;
                                setApproveForm((prev) => ({ ...prev, editedStatement: targetMarkdown }));
                                notifications.show({
                                  color: "teal",
                                  title: "History snapshot applied",
                                  message: `Copied v${selectedHistoryTarget?.version ?? "?"} markdown into Approve form.`,
                                });
                              }}
                            >
                              Use target markdown in Approve form
                            </Button>
                          </Group>
                        </Stack>
                      )}
                      </Paper>
                    </Tabs.Panel>
                  )}

                  <Tabs.Panel value="semantic" pt="sm">
                    <Paper withBorder p="sm" radius="md">
                      <Text fw={600} mb={6}>
                        Summary
                      </Text>
                      <Text size="sm" mb="sm">
                        {String((semanticDiff as Record<string, unknown>).summary ?? "No semantic summary")}
                      </Text>
                      <Divider mb="sm" />
                      <Text fw={600} mb={6}>
                        Statement-level Diff
                      </Text>
                      <Box className="diff-block">
                        <DiffLine label="Before" tokens={statementDiff.before} />
                        <Divider my="sm" />
                        <DiffLine label="After" tokens={statementDiff.after} />
                      </Box>
                      <Divider my="sm" />
                      <Text fw={600} mb={6}>
                        Raw semantic payload
                      </Text>
                      <Code block>{safeJson(draftDetail.draft.semantic_diff)}</Code>
                    </Paper>
                  </Tabs.Panel>

                  <Tabs.Panel value="conflicts" pt="sm">
                    <Stack>
                      {loadingConflictExplain && (
                        <Group justify="center" py="sm">
                          <Loader size="sm" />
                        </Group>
                      )}
                      {enrichedConflicts.length > 0 && (
                        <Paper withBorder p="xs" radius="md" className="hotkey-panel">
                          <Text size="xs" c="dimmed">
                            Enriched by {conflictExplain?.source} for entity{" "}
                            <Code>{conflictExplain?.scope.entity_key || "unknown"}</Code>
                          </Text>
                        </Paper>
                      )}
                      {enrichedConflicts.map((conflict) => (
                        <Paper key={`explain-${conflict.conflict_id}`} withBorder p="sm" radius="md" className="conflict-explain-card">
                          <Group justify="space-between" align="flex-start">
                            <Stack gap={3}>
                              <Group gap={6}>
                                <ThemeIcon color={conflict.resolution_status === "open" ? "orange" : "gray"} variant="light">
                                  <IconSwords size={14} />
                                </ThemeIcon>
                                <Text fw={700}>{conflict.conflict_type}</Text>
                                <Badge color={statusColor(conflict.resolution_status)} variant="light">
                                  {conflict.resolution_status}
                                </Badge>
                              </Group>
                              <Text size="xs" c="dimmed">
                                created: {fmtDate(conflict.created_at)} | page: {conflict.page.slug || "n/a"}
                              </Text>
                            </Stack>
                            {conflict.resolution_status === "open" && (
                              <Group>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="teal"
                                  leftSection={<IconCheck size={14} />}
                                  disabled={!canModerate}
                                  loading={runningAction}
                                  onClick={() => void approveDraft("quick_force")}
                                >
                                  {quickForceArmed ? "Confirm Force Approve" : "Force Approve"}
                                </Button>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="red"
                                  leftSection={<IconX size={14} />}
                                  disabled={!canModerate}
                                  loading={runningAction}
                                  onClick={() => void rejectDraft("quick_dismiss")}
                                >
                                  {quickDismissArmed ? "Confirm Reject + Dismiss" : "Reject + Dismiss"}
                                </Button>
                              </Group>
                            )}
                          </Group>
                          <Divider my="sm" />
                          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed" fw={700}>
                                Root Cause
                              </Text>
                              <Text size="sm">{conflict.root_cause}</Text>
                            </Paper>
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed" fw={700}>
                                Recommendation
                              </Text>
                              <Text size="sm">{conflict.recommendation}</Text>
                            </Paper>
                          </SimpleGrid>
                          <Divider my="sm" />
                          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed" fw={700}>
                                Incoming Claim
                              </Text>
                              <Text size="sm">{conflict.incoming_claim.claim_text || "—"}</Text>
                            </Paper>
                            <Paper withBorder p="xs" radius="md">
                              <Text size="xs" c="dimmed" fw={700}>
                                Conflicting Statement
                              </Text>
                              <Text size="sm">{conflict.conflicting_statement.statement_text || "—"}</Text>
                            </Paper>
                          </SimpleGrid>
                        </Paper>
                      ))}
                      {enrichedConflicts.length === 0 &&
                        (draftDetail.conflicts ?? []).map((conflict) => (
                          <Paper key={conflict.id} withBorder p="sm" radius="md">
                            <Group justify="space-between" align="flex-start">
                              <Stack gap={3}>
                                <Group gap={6}>
                                  <ThemeIcon color={conflict.resolution_status === "open" ? "orange" : "gray"} variant="light">
                                    <IconSwords size={14} />
                                  </ThemeIcon>
                                  <Text fw={700}>{conflict.conflict_type}</Text>
                                  <Badge color={statusColor(conflict.resolution_status)} variant="light">
                                    {conflict.resolution_status}
                                  </Badge>
                                </Group>
                                <Text size="xs" c="dimmed">
                                  created: {fmtDate(conflict.created_at)}
                                </Text>
                              </Stack>
                              {conflict.resolution_status === "open" && (
                                <Group>
                                  <Button
                                    size="xs"
                                    variant="light"
                                    color="teal"
                                    leftSection={<IconCheck size={14} />}
                                    disabled={!canModerate}
                                    loading={runningAction}
                                    onClick={() => void approveDraft("quick_force")}
                                  >
                                    {quickForceArmed ? "Confirm Force Approve" : "Force Approve"}
                                  </Button>
                                  <Button
                                    size="xs"
                                    variant="light"
                                    color="red"
                                    leftSection={<IconX size={14} />}
                                    disabled={!canModerate}
                                    loading={runningAction}
                                    onClick={() => void rejectDraft("quick_dismiss")}
                                  >
                                    {quickDismissArmed ? "Confirm Reject + Dismiss" : "Reject + Dismiss"}
                                  </Button>
                                </Group>
                              )}
                            </Group>
                            <Divider my="sm" />
                            <Code block>{safeJson(conflict.details)}</Code>
                          </Paper>
                        ))}
                      {!hasOpenConflicts && (
                        <Paper withBorder p="md" radius="md">
                          <Group>
                            <ThemeIcon color="green" variant="light">
                              <IconCheck size={16} />
                            </ThemeIcon>
                            <Text>No open conflicts for this draft.</Text>
                          </Group>
                        </Paper>
                      )}
                    </Stack>
                  </Tabs.Panel>

                  {showExpertModerationControls && (
                    <Tabs.Panel value="patch" pt="sm">
                      <Paper withBorder p="sm" radius="md">
                        <Code block>{draftDetail.draft.markdown_patch || "—"}</Code>
                      </Paper>
                    </Tabs.Panel>
                  )}

                  <Tabs.Panel value="evidence" pt="sm">
                    <Paper withBorder p="sm" radius="md">
                      <Text fw={600} mb={6}>
                        Evidence
                      </Text>
                      <Code block>{safeJson(draftDetail.draft.evidence)}</Code>
                    </Paper>
                  </Tabs.Panel>

                  {showExpertModerationControls && (
                    <Tabs.Panel value="timeline" pt="sm">
                      <Paper withBorder p="sm" radius="md">
                        <Code block>{safeJson(draftDetail.moderation_actions)}</Code>
                      </Paper>
                    </Tabs.Panel>
                  )}
                </Tabs>

                <Divider />

                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <Paper withBorder p="md" radius="lg">
                    <Group justify="space-between" mb="sm">
                      <Title order={4}>Approve / Edit</Title>
                      <IconCheck size={18} />
                    </Group>
                    <Stack>
                      {isCoreSimplified && (
                        <Paper withBorder p="xs" radius="md">
                          <Text size="xs" c="dimmed">
                            Simplified moderation mode: only essential fields are shown. Enable expert controls to edit sections/templates.
                          </Text>
                        </Paper>
                      )}
                      {showExpertModerationControls && (
                        <Paper withBorder p="xs" radius="md" className="template-card">
                          <Stack gap={6}>
                            <Group justify="space-between" align="center">
                              <Text size="xs" fw={700}>
                                Page Template
                              </Text>
                              {selectedTemplate && (
                                <Badge size="xs" variant="light" color="teal">
                                  {selectedTemplate.title}
                                </Badge>
                              )}
                            </Group>
                            <Select
                              label="Template"
                              placeholder="Choose template"
                              value={selectedTemplateKey}
                              onChange={setSelectedTemplateKey}
                              data={PAGE_TEMPLATES.map((template) => ({
                                label: template.title,
                                value: template.key,
                              }))}
                              clearable
                            />
                            {selectedTemplate && (
                              <Text size="xs" c="dimmed">
                                {selectedTemplate.description}
                              </Text>
                            )}
                            <Group gap="xs" justify="space-between" align="center">
                              <Button
                                size="xs"
                                variant="light"
                                disabled={!selectedTemplateKey}
                                onClick={() => {
                                  if (!selectedTemplateKey) return;
                                  applyPageTemplate(selectedTemplateKey);
                                }}
                              >
                                Apply Template
                              </Button>
                              <Button
                                size="xs"
                                variant="subtle"
                                disabled={!selectedTemplate}
                                onClick={() => {
                                  if (!selectedTemplate) return;
                                  setDetailTab("page");
                                  setSelectedTocSectionKey(selectedTemplate.sectionKey);
                                }}
                              >
                                Open Related Section
                              </Button>
                            </Group>
                          </Stack>
                        </Paper>
                      )}

                      <Textarea
                        label="Note"
                        value={approveForm.note}
                        onChange={(event) =>
                          setApproveForm((prev) => ({ ...prev, note: event.currentTarget.value }))
                        }
                        minRows={2}
                      />
                      {showExpertModerationControls && (
                        <Textarea
                          label="Edited statement (optional)"
                          value={approveForm.editedStatement}
                          onChange={(event) =>
                            setApproveForm((prev) => ({ ...prev, editedStatement: event.currentTarget.value }))
                          }
                          minRows={3}
                        />
                      )}
                      {showExpertModerationControls && (
                        <TextInput
                          label="Section key"
                          value={approveForm.sectionKey}
                          onChange={(event) =>
                            setApproveForm((prev) => ({ ...prev, sectionKey: event.currentTarget.value }))
                          }
                          placeholder="ops_notes"
                        />
                      )}
                      {showExpertModerationControls && (
                        <TextInput
                          label="Section heading"
                          value={approveForm.sectionHeading}
                          onChange={(event) =>
                            setApproveForm((prev) => ({ ...prev, sectionHeading: event.currentTarget.value }))
                          }
                          placeholder="Ops Notes"
                        />
                      )}
                      {showExpertModerationControls && (
                        <Select
                          label="Section mode"
                          data={[
                            { label: "append", value: "append" },
                            { label: "replace", value: "replace" },
                          ]}
                          value={approveForm.sectionMode}
                          onChange={(value) =>
                            setApproveForm((prev) => ({
                              ...prev,
                              sectionMode: (value as "append" | "replace" | null) ?? "append",
                            }))
                          }
                        />
                      )}
                      {showExpertModerationControls && (
                        <Textarea
                          label="Section statements (new line = new statement)"
                          value={approveForm.sectionStatements}
                          onChange={(event) =>
                            setApproveForm((prev) => ({ ...prev, sectionStatements: event.currentTarget.value }))
                          }
                          minRows={4}
                        />
                      )}
                      <Checkbox
                        checked={approveForm.force}
                        onChange={(event) => setApproveForm((prev) => ({ ...prev, force: event.currentTarget.checked }))}
                        label="Force approval when draft decision is conflict"
                      />
                      <Button
                        leftSection={<IconCheck size={16} />}
                        disabled={!canModerate}
                        loading={runningAction}
                        onClick={() => void approveDraft("form")}
                        variant="gradient"
                        gradient={{ from: "teal.7", to: "cyan.6", deg: 140 }}
                      >
                        {approveForm.force && formForceArmed ? "Confirm Approve Draft" : "Approve Draft"}
                      </Button>
                    </Stack>
                  </Paper>

                  <Paper withBorder p="md" radius="lg">
                    <Group justify="space-between" mb="sm">
                      <Title order={4}>Reject</Title>
                      <IconX size={18} />
                    </Group>
                    <Stack>
                      <Textarea
                        label="Reason"
                        value={rejectForm.reason}
                        onChange={(event) => setRejectForm((prev) => ({ ...prev, reason: event.currentTarget.value }))}
                        minRows={isCoreSimplified ? 4 : 8}
                      />
                      <Checkbox
                        checked={rejectForm.dismissConflicts}
                        onChange={(event) =>
                          setRejectForm((prev) => ({ ...prev, dismissConflicts: event.currentTarget.checked }))
                        }
                        label="Dismiss linked conflicts"
                      />
                      <Button
                        color="red"
                        leftSection={<IconX size={16} />}
                        disabled={!canModerate}
                        loading={runningAction}
                        onClick={() => void rejectDraft("form")}
                      >
                        {rejectForm.dismissConflicts && formDismissArmed ? "Confirm Reject Draft" : "Reject Draft"}
                      </Button>
                    </Stack>
                  </Paper>
                </SimpleGrid>
              </Stack>
            )}
          </Paper>
        </SimpleGrid>

        <Paper radius="xl" p="sm" withBorder>
          <Group justify="space-between">
            <Group>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconChevronUp size={14} />}
                onClick={selectPrevDraft}
                disabled={visibleDrafts.length <= 1}
              >
                Prev Draft (K)
              </Button>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconChevronDown size={14} />}
                onClick={selectNextDraft}
                disabled={visibleDrafts.length <= 1}
              >
                Next Draft (J)
              </Button>
              {showExpertModerationControls && (
                <Button
                  size="xs"
                  variant="light"
                  color="indigo"
                  onClick={jumpToPrevPage}
                  disabled={openPageOrder.length <= 1}
                >
                  Prev Page (Shift+K)
                </Button>
              )}
              {showExpertModerationControls && (
                <Button
                  size="xs"
                  variant="light"
                  color="indigo"
                  onClick={jumpToNextPage}
                  disabled={openPageOrder.length <= 1}
                >
                  Next Page (Shift+J)
                </Button>
              )}
              {showExpertModerationControls && (
                <Button
                  size="xs"
                  variant="light"
                  color="orange"
                  onClick={jumpToNextConflictPage}
                  disabled={conflictPageOrder.length === 0}
                >
                  Next Conflict Page (Shift+C)
                </Button>
              )}
            </Group>
            <Text size="xs" c="dimmed">
              {selectedIndex >= 0
                ? `selected draft ${selectedIndex + 1}/${visibleDrafts.length} • pages ${openPageOrder.length} • conflicts ${conflictPageOrder.length}`
                : "no draft selected"}
            </Text>
          </Group>
        </Paper>
      </Stack>
    </Box>
  );
}
