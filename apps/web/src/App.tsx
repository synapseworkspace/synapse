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
  Kbd,
  Loader,
  PasswordInput,
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
  IconBell,
  IconBookmark,
  IconBookmarkFilled,
  IconCheck,
  IconChevronDown,
  IconChevronUp,
  IconCloudCog,
  IconDeviceFloppy,
  IconEditCircle,
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

type WikiPageUpdateResponse = {
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
  latest_version?: {
    version: number;
    markdown: string;
    source: string | null;
    created_by: string | null;
    change_summary: string | null;
  };
  snapshot_id?: string;
  inserted_statements?: number;
  superseded_statements?: number;
};

type WikiPageMoveResponse = {
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
  include_descendants: boolean;
  moved_pages: Array<{
    id: string;
    old_slug: string;
    new_slug: string;
    old_title: string;
    new_title: string;
  }>;
  snapshot_id?: string;
};

type WikiPageStatusTransitionResponse = {
  status: string;
  page: {
    id: string;
    title: string;
    slug: string;
    status: string;
    current_version: number | null;
  };
  include_descendants: boolean;
  changed_pages: Array<{
    id: string;
    title: string;
    slug: string;
    previous_status: string;
    status: string;
  }>;
  snapshot_id?: string;
};

type WikiPageAliasItem = {
  alias_text: string;
  created_at: string | null;
};

type WikiPageCommentItem = {
  id: string;
  author: string;
  body: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

type WikiPageWatcherItem = {
  watcher: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

type WikiPageReviewAssignmentItem = {
  id: string;
  assignee: string;
  role: string;
  status: string;
  note: string | null;
  due_at: string | null;
  created_by: string;
  resolved_by: string | null;
  resolution_note: string | null;
  created_at: string | null;
  resolved_at: string | null;
};

type WikiSpacePolicyPayload = {
  project_id: string;
  space_key: string;
  policy: {
    write_mode: "open" | "owners_only" | string;
    comment_mode: "open" | "owners_only" | string;
    review_assignment_required: boolean;
    metadata: Record<string, unknown>;
    exists: boolean;
  };
};

type WikiSpaceOwnerItem = {
  owner: string;
  role: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

type WikiPageOwnerItem = {
  owner: string;
  role: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

type WikiNotificationItem = {
  id: string;
  recipient: string;
  actor: string | null;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  metadata: Record<string, unknown>;
  status: string;
  created_at: string | null;
  read_at: string | null;
};

type WikiUploadItem = {
  id: string;
  page_id: string | null;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  checksum_sha256: string;
  created_by: string;
  created_at: string | null;
  content_url: string;
  content_url_absolute?: string | null;
};

type WikiUploadCreatePayload = {
  status: string;
  upload: {
    id: string;
    project_id: string;
    page_id: string | null;
    page_slug: string | null;
    filename: string;
    content_type: string | null;
    size_bytes: number;
    checksum_sha256: string;
    created_by: string;
    created_at: string | null;
    content_url: string;
    content_url_absolute?: string | null;
    markdown_snippet: string;
  };
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

type AuthModePayload = {
  auth_mode: string;
  rbac_mode: string;
  tenancy_mode: string;
  oidc: {
    issuer_configured: boolean;
    audience_configured: boolean;
    roles_claim: string;
    tenant_claim: string;
    email_claim: string;
    session_ttl_minutes_default: number;
    session_ttl_minutes_max: number;
  };
};

type AuthSessionPayload = {
  status: string;
  session: {
    id: string;
    session_token?: string;
    subject: string;
    email: string | null;
    tenant_id: string | null;
    roles: string[];
    issued_at: string | null;
    expires_at: string | null;
    auth_source?: string;
    auth_provider?: string;
    active?: boolean;
    last_seen_at?: string | null;
    revoked_at?: string | null;
  };
};

type BootstrapApproveRunPayload = {
  status: string;
  dry_run: boolean;
  project_id: string;
  reviewed_by: string;
  source_system?: string;
  selection: {
    limit: number;
    min_confidence: number;
    require_conflict_free: boolean;
    trusted_source_systems: string[];
  };
  summary: {
    candidates: number;
    sample_size?: number;
    approved?: number;
    failed?: number;
    source_ownership_advisories?: number;
  };
  sample?: Array<{
    draft_id: string;
    confidence: number;
    decision: string;
  }>;
  items?: Array<{
    draft_id: string;
    confidence: number;
    outcome: string;
    reason?: string;
  }>;
  generated_at?: string;
};

type WikiPageNode = {
  id?: string;
  slug: string;
  title: string;
  status?: string | null;
  page_type?: string | null;
  current_version?: number | null;
  updated_at: string | null;
  created_at?: string | null;
  draft_count: number;
  open_count: number;
  latest_draft_at: string | null;
};

type WikiPageListItem = {
  id: string;
  title: string;
  slug: string;
  entity_key: string | null;
  page_type: string | null;
  status: string;
  current_version: number | null;
  created_at: string | null;
  updated_at: string | null;
  draft_count: number;
  open_draft_count: number;
  latest_draft_at: string | null;
};

type WikiSpaceNode = {
  key: string;
  title: string;
  page_count: number;
  open_count: number;
  latest_draft_at: string | null;
};

type WikiTreeNode = {
  key: string;
  label: string;
  slug: string | null;
  depth: number;
  page: WikiPageNode | null;
  page_count: number;
  open_count: number;
  latest_activity_at: string | null;
  children: WikiTreeNode[];
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
  status: "draft" | "reviewed" | "published";
};

type DetailTab = "page" | "history" | "semantic" | "conflicts" | "patch" | "evidence" | "timeline";

type SavedView = {
  id: string;
  name: string;
  selectedSpaceKey: string | null;
  selectedPageSlug: string | null;
  status: string | null;
  pageStatusFilter: string | null;
  pageUpdatedByFilter: string;
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

type UiMode = "core" | "advanced";
type CoreWorkspaceTab = "wiki" | "drafts" | "tasks";

const UI_PROFILE = String(import.meta.env.VITE_SYNAPSE_UI_PROFILE || "")
  .trim()
  .toLowerCase();
const DEFAULT_API_URL = String(import.meta.env.VITE_SYNAPSE_API_URL || "http://localhost:8080").trim() || "http://localhost:8080";
const ADVANCED_UI_PROFILES = new Set(["advanced", "admin", "ops-admin", "ops_admin", "control-center", "control_center"]);
const CAN_ACCESS_ADVANCED_MODE = ADVANCED_UI_PROFILES.has(UI_PROFILE);

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

function resolveWikiAssetUrl(apiUrl: string, url: string | null | undefined): string {
  const raw = String(url || "").trim();
  if (!raw) return "";
  const lowered = raw.toLowerCase();
  if (lowered.startsWith("http://") || lowered.startsWith("https://") || lowered.startsWith("data:") || lowered.startsWith("blob:")) {
    return raw;
  }
  const root = apiUrl.replace(/\/+$/, "");
  if (raw.startsWith("/")) return `${root}${raw}`;
  return raw;
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

function normalizeSourceSystemCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .sort();
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

function activityTimestampMs(value: string | null | undefined): number {
  if (!value) return 0;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function buildWikiTreeNodes(pages: WikiPageNode[]): WikiTreeNode[] {
  type MutableNode = WikiTreeNode & { childMap: Map<string, MutableNode> };
  const rootMap = new Map<string, MutableNode>();

  const upsertNode = (
    container: Map<string, MutableNode>,
    key: string,
    label: string,
    depth: number,
  ): MutableNode => {
    const existing = container.get(key);
    if (existing) return existing;
    const created: MutableNode = {
      key,
      label,
      slug: null,
      depth,
      page: null,
      page_count: 0,
      open_count: 0,
      latest_activity_at: null,
      children: [],
      childMap: new Map<string, MutableNode>(),
    };
    container.set(key, created);
    return created;
  };

  for (const page of pages) {
    const normalizedSlug = String(page.slug || "").trim();
    if (!normalizedSlug) continue;
    const segments = normalizedSlug.split("/").map((segment) => segment.trim()).filter(Boolean);
    if (segments.length === 0) continue;
    let container = rootMap;
    let currentPath = "";
    let parentNode: MutableNode | null = null;
    for (let index = 0; index < segments.length; index += 1) {
      const segment = segments[index];
      currentPath = currentPath ? `${currentPath}/${segment}` : segment;
      const node = upsertNode(container, currentPath, segment, index);
      node.page_count += 1;
      node.open_count += page.open_count;
      const pageActivity = page.latest_draft_at || page.updated_at || page.created_at || null;
      if (activityTimestampMs(pageActivity) > activityTimestampMs(node.latest_activity_at)) {
        node.latest_activity_at = pageActivity;
      }
      if (parentNode && !parentNode.children.some((child) => child.key === node.key)) {
        parentNode.children.push(node);
      }
      if (index === segments.length - 1) {
        node.slug = normalizedSlug;
        node.page = page;
        node.label = page.title || segment;
      }
      parentNode = node;
      container = node.childMap;
    }
  }

  const sortTree = (nodes: MutableNode[]): WikiTreeNode[] =>
    [...nodes]
      .sort((a, b) => {
        const aIsFolder = a.page == null;
        const bIsFolder = b.page == null;
        if (aIsFolder !== bIsFolder) return aIsFolder ? -1 : 1;
        if (a.open_count !== b.open_count) return b.open_count - a.open_count;
        const activityDiff = activityTimestampMs(b.latest_activity_at) - activityTimestampMs(a.latest_activity_at);
        if (activityDiff !== 0) return activityDiff;
        return a.label.localeCompare(b.label);
      })
      .map((node) => ({
        key: node.key,
        label: node.label,
        slug: node.slug,
        depth: node.depth,
        page: node.page,
        page_count: node.page_count,
        open_count: node.open_count,
        latest_activity_at: node.latest_activity_at,
        children: sortTree(node.children as MutableNode[]),
      }));

  return sortTree([...rootMap.values()]);
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
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: Record<string, unknown>;
    formData?: FormData;
    idempotencyKey?: string;
    extraHeaders?: Record<string, string>;
  },
): Promise<T> {
  const root = apiUrl.replace(/\/+$/, "");
  let sessionHeader: Record<string, string> = {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { sessionToken?: string };
      const token = String(parsed.sessionToken || "").trim();
      if (token) {
        sessionHeader = { "X-Synapse-Session": token };
      }
    }
  } catch {
    sessionHeader = {};
  }
  const usingFormData = Boolean(options?.formData);
  const response = await fetch(`${root}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      ...(usingFormData ? {} : { "Content-Type": "application/json" }),
      ...(options?.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}),
      ...sessionHeader,
      ...(options?.extraHeaders || {}),
    },
    body: usingFormData ? options?.formData : options?.body ? JSON.stringify(options.body) : undefined,
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
  tokens.forEach((token: { value: string; added?: boolean; removed?: boolean }) => {
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
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [projectId, setProjectId] = useState("");
  const [reviewer, setReviewer] = useState("ops_manager");
  const [authMode, setAuthMode] = useState<AuthModePayload | null>(null);
  const [oidcToken, setOidcToken] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [sessionSummary, setSessionSummary] = useState<AuthSessionPayload["session"] | null>(null);
  const [authActionLoading, setAuthActionLoading] = useState(false);
  const [uiMode, setUiMode] = useState<UiMode>(CAN_ACCESS_ADVANCED_MODE ? "advanced" : "core");
  const [coreExpertControls, setCoreExpertControls] = useState(false);
  const [coreWorkspaceTab, setCoreWorkspaceTab] = useState<CoreWorkspaceTab>("wiki");
  const [showOperationsNav, setShowOperationsNav] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [pageStatusFilter, setPageStatusFilter] = useState<string | null>(null);
  const [pageUpdatedByFilter, setPageUpdatedByFilter] = useState("");
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [wikiPages, setWikiPages] = useState<WikiPageListItem[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedPageSlug, setSelectedPageSlug] = useState<string | null>(null);
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string | null>(null);
  const [pageFilter, setPageFilter] = useState("");
  const [draftFilter, setDraftFilter] = useState("");
  const [openPagesOnly, setOpenPagesOnly] = useState(false);
  const [collapsedTreeNodes, setCollapsedTreeNodes] = useState<Record<string, boolean>>({});
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
  const [bootstrapTrustedSources, setBootstrapTrustedSources] = useState("legacy_import,postgres_sql");
  const [bootstrapMinConfidence, setBootstrapMinConfidence] = useState("0.85");
  const [bootstrapLimit, setBootstrapLimit] = useState("50");
  const [bootstrapSampleSize, setBootstrapSampleSize] = useState("15");
  const [bootstrapRequireConflictFree, setBootstrapRequireConflictFree] = useState(true);
  const [showBootstrapTools, setShowBootstrapTools] = useState(false);
  const [showMigrationMode, setShowMigrationMode] = useState(false);
  const [showDraftOperationsTools, setShowDraftOperationsTools] = useState(false);
  const [bootstrapLoading, setBootstrapLoading] = useState(false);
  const [bootstrapResult, setBootstrapResult] = useState<BootstrapApproveRunPayload | null>(null);
  const [draftDetail, setDraftDetail] = useState<DraftDetailPayload | null>(null);
  const [selectedPageDetail, setSelectedPageDetail] = useState<WikiPageDetailPayload | null>(null);
  const [pageHistory, setPageHistory] = useState<WikiPageHistoryPayload | null>(null);
  const [loadingPageHistory, setLoadingPageHistory] = useState(false);
  const [historyBaseVersion, setHistoryBaseVersion] = useState<string | null>(null);
  const [historyTargetVersion, setHistoryTargetVersion] = useState<string | null>(null);
  const [pageEditMode, setPageEditMode] = useState(false);
  const [pageEditTitle, setPageEditTitle] = useState("");
  const [pageEditStatus, setPageEditStatus] = useState<"draft" | "reviewed" | "published" | "archived">("published");
  const [pageEditSummary, setPageEditSummary] = useState("Manual wiki page edit");
  const [pageEditMarkdown, setPageEditMarkdown] = useState("");
  const [savingPageEdit, setSavingPageEdit] = useState(false);
  const [pageAssetFile, setPageAssetFile] = useState<File | null>(null);
  const [uploadingPageAsset, setUploadingPageAsset] = useState(false);
  const [pageMoveMode, setPageMoveMode] = useState(false);
  const [pageMoveParentPath, setPageMoveParentPath] = useState("");
  const [pageMoveSlugLeaf, setPageMoveSlugLeaf] = useState("");
  const [pageMoveTitle, setPageMoveTitle] = useState("");
  const [pageMoveSummary, setPageMoveSummary] = useState("Page move/rename");
  const [pageMoveIncludeDescendants, setPageMoveIncludeDescendants] = useState(true);
  const [movingPage, setMovingPage] = useState(false);
  const [pageAliases, setPageAliases] = useState<WikiPageAliasItem[]>([]);
  const [loadingPageAliases, setLoadingPageAliases] = useState(false);
  const [newPageAlias, setNewPageAlias] = useState("");
  const [savingPageAlias, setSavingPageAlias] = useState(false);
  const [pageComments, setPageComments] = useState<WikiPageCommentItem[]>([]);
  const [loadingPageComments, setLoadingPageComments] = useState(false);
  const [newPageComment, setNewPageComment] = useState("");
  const [savingPageComment, setSavingPageComment] = useState(false);
  const [pageWatchers, setPageWatchers] = useState<WikiPageWatcherItem[]>([]);
  const [loadingPageWatchers, setLoadingPageWatchers] = useState(false);
  const [watcherInput, setWatcherInput] = useState("");
  const [savingPageWatcher, setSavingPageWatcher] = useState(false);
  const [pageReviewAssignments, setPageReviewAssignments] = useState<WikiPageReviewAssignmentItem[]>([]);
  const [loadingPageReviewAssignments, setLoadingPageReviewAssignments] = useState(false);
  const [assignmentAssigneeInput, setAssignmentAssigneeInput] = useState("");
  const [assignmentNoteInput, setAssignmentNoteInput] = useState("");
  const [savingPageAssignment, setSavingPageAssignment] = useState(false);
  const [spacePolicy, setSpacePolicy] = useState<WikiSpacePolicyPayload["policy"] | null>(null);
  const [loadingSpacePolicy, setLoadingSpacePolicy] = useState(false);
  const [savingSpacePolicy, setSavingSpacePolicy] = useState(false);
  const [spaceWriteMode, setSpaceWriteMode] = useState<"open" | "owners_only">("open");
  const [spaceCommentMode, setSpaceCommentMode] = useState<"open" | "owners_only">("open");
  const [spaceReviewRequired, setSpaceReviewRequired] = useState(false);
  const [spaceOwners, setSpaceOwners] = useState<WikiSpaceOwnerItem[]>([]);
  const [loadingSpaceOwners, setLoadingSpaceOwners] = useState(false);
  const [savingSpaceOwner, setSavingSpaceOwner] = useState(false);
  const [spaceOwnerInput, setSpaceOwnerInput] = useState("");
  const [spaceOwnerRoleInput, setSpaceOwnerRoleInput] = useState("owner");
  const [pageOwners, setPageOwners] = useState<WikiPageOwnerItem[]>([]);
  const [loadingPageOwners, setLoadingPageOwners] = useState(false);
  const [savingPageOwner, setSavingPageOwner] = useState(false);
  const [pageOwnerInput, setPageOwnerInput] = useState("");
  const [pageOwnerRoleInput, setPageOwnerRoleInput] = useState("editor");
  const [pageUploads, setPageUploads] = useState<WikiUploadItem[]>([]);
  const [loadingPageUploads, setLoadingPageUploads] = useState(false);
  const [notificationsInbox, setNotificationsInbox] = useState<WikiNotificationItem[]>([]);
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);
  const [loadingNotificationsInbox, setLoadingNotificationsInbox] = useState(false);
  const [savingNotificationState, setSavingNotificationState] = useState(false);
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
  const [loadingPages, setLoadingPages] = useState(false);
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
  const [urlStateReady, setUrlStateReady] = useState(false);
  const effectiveUiMode: UiMode = CAN_ACCESS_ADVANCED_MODE ? uiMode : "core";
  const showExpertModerationControls = effectiveUiMode === "advanced" || (CAN_ACCESS_ADVANCED_MODE && coreExpertControls);
  const requiresAuthSession =
    authMode?.auth_mode === "oidc" || authMode?.rbac_mode === "enforce" || authMode?.tenancy_mode === "enforce";
  const hasSessionToken = sessionToken.trim().length > 0;

  const pageNodes = useMemo<WikiPageNode[]>(() => {
    const draftStats = new Map<
      string,
      {
        title: string;
        draft_count: number;
        open_count: number;
        latest_draft_at: string | null;
      }
    >();
    for (const draft of drafts) {
      const slug = String(draft.page.slug || "").trim();
      if (!slug) continue;
      const current = draftStats.get(slug) || {
        title: draft.page.title || slug,
        draft_count: 0,
        open_count: 0,
        latest_draft_at: null,
      };
      current.draft_count += 1;
      if (draft.status === "pending_review" || draft.status === "blocked_conflict") {
        current.open_count += 1;
      }
      if (activityTimestampMs(draft.created_at) > activityTimestampMs(current.latest_draft_at)) {
        current.latest_draft_at = draft.created_at;
      }
      if (!current.title && draft.page.title) {
        current.title = draft.page.title;
      }
      draftStats.set(slug, current);
    }

    const map = new Map<string, WikiPageNode>();
    for (const page of wikiPages) {
      const slug = String(page.slug || "").trim();
      if (!slug) continue;
      const draft = draftStats.get(slug);
      const latestDraftAtCandidates = [
        String(page.latest_draft_at || ""),
        String(draft?.latest_draft_at || ""),
      ]
        .filter(Boolean)
        .sort();
      const latestDraftAt =
        latestDraftAtCandidates.length > 0 ? latestDraftAtCandidates[latestDraftAtCandidates.length - 1] : null;
      map.set(slug, {
        id: page.id,
        slug,
        title: page.title || draft?.title || slug,
        status: page.status,
        page_type: page.page_type,
        current_version: page.current_version,
        created_at: page.created_at,
        updated_at: page.updated_at,
        draft_count: Math.max(Number(page.draft_count || 0), Number(draft?.draft_count || 0)),
        open_count: Math.max(Number(page.open_draft_count || 0), Number(draft?.open_count || 0)),
        latest_draft_at: latestDraftAt,
      });
    }
    for (const [slug, draft] of draftStats.entries()) {
      if (map.has(slug)) continue;
      map.set(slug, {
        slug,
        title: draft.title || slug,
        status: "draft",
        page_type: null,
        current_version: null,
        created_at: null,
        updated_at: draft.latest_draft_at,
        draft_count: draft.draft_count,
        open_count: draft.open_count,
        latest_draft_at: draft.latest_draft_at,
      });
    }
    return [...map.values()].sort((a, b) => {
      if (a.open_count !== b.open_count) return b.open_count - a.open_count;
      const aActivity = activityTimestampMs(a.latest_draft_at || a.updated_at || a.created_at);
      const bActivity = activityTimestampMs(b.latest_draft_at || b.updated_at || b.created_at);
      if (aActivity !== bActivity) return bActivity - aActivity;
      return String(a.title || a.slug).localeCompare(String(b.title || b.slug));
    });
  }, [drafts, wikiPages]);

  const filteredPageNodes = useMemo(() => {
    const selectedSpace = selectedSpaceKey;
    const filterNeedle = pageFilter.trim().toLowerCase();
    return pageNodes.filter((page) => {
      const groupKey = pageGroupKey(page.slug);
      if (selectedSpace && groupKey !== selectedSpace) return false;
      if (openPagesOnly && page.open_count <= 0) return false;
      if (!filterNeedle) return true;
      const haystack = `${page.title} ${page.slug}`.toLowerCase();
      return haystack.includes(filterNeedle);
    });
  }, [openPagesOnly, pageFilter, pageNodes, selectedSpaceKey]);

  const wikiTreeNodes = useMemo(() => buildWikiTreeNodes(filteredPageNodes), [filteredPageNodes]);

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
      const pageActivity = page.latest_draft_at || page.updated_at || page.created_at || null;
      if (activityTimestampMs(pageActivity) > activityTimestampMs(current.latest_draft_at)) {
        current.latest_draft_at = pageActivity;
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
      .sort((a, b) => {
        const aTs = activityTimestampMs(a.latest_draft_at || a.updated_at || a.created_at);
        const bTs = activityTimestampMs(b.latest_draft_at || b.updated_at || b.created_at);
        return bTs - aTs;
      })
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
      effectiveUiMode === "advanced" || (CAN_ACCESS_ADVANCED_MODE && coreExpertControls) ? reviewQueuePreset : "open_queue";
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
  }, [coreExpertControls, effectiveUiMode, reviewQueuePreset, reviewSlaHours, scopedDrafts]);

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
        sessionToken?: string;
        uiMode?: UiMode;
        coreExpertControls?: boolean;
        coreWorkspaceTab?: CoreWorkspaceTab;
        status?: string | null;
        pageStatusFilter?: string | null;
        pageUpdatedByFilter?: string;
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
      if (parsed.sessionToken) setSessionToken(parsed.sessionToken);
      if (CAN_ACCESS_ADVANCED_MODE && (parsed.uiMode === "core" || parsed.uiMode === "advanced")) {
        setUiMode(parsed.uiMode);
      }
      if (CAN_ACCESS_ADVANCED_MODE && typeof parsed.coreExpertControls === "boolean") {
        setCoreExpertControls(parsed.coreExpertControls);
      }
      if (
        parsed.coreWorkspaceTab === "wiki" ||
        parsed.coreWorkspaceTab === "drafts" ||
        parsed.coreWorkspaceTab === "tasks"
      ) {
        setCoreWorkspaceTab(parsed.coreWorkspaceTab);
      }
      if (typeof parsed.status === "string" || parsed.status === null) setStatus(parsed.status);
      if (typeof parsed.pageStatusFilter === "string" || parsed.pageStatusFilter === null) {
        setPageStatusFilter(parsed.pageStatusFilter);
      }
      if (typeof parsed.pageUpdatedByFilter === "string") {
        setPageUpdatedByFilter(parsed.pageUpdatedByFilter);
      }
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
    try {
      const params = new URLSearchParams(window.location.search);
      const projectParam = String(params.get("project") || "").trim();
      if (projectParam) {
        setProjectId(projectParam);
      }
      const spaceParam = String(params.get("wiki_space") || "").trim();
      if (spaceParam) {
        setSelectedSpaceKey(spaceParam);
      }
      const pageParam = String(params.get("wiki_page") || "").trim();
      if (pageParam) {
        setSelectedPageSlug(pageParam);
      }
      const pageStatusParam = String(params.get("wiki_status") || "").trim().toLowerCase();
      if (pageStatusParam && ["draft", "reviewed", "published", "archived"].includes(pageStatusParam)) {
        setPageStatusFilter(pageStatusParam);
      }
      const pageUpdatedByParam = String(params.get("wiki_updated_by") || "").trim();
      if (pageUpdatedByParam) {
        setPageUpdatedByFilter(pageUpdatedByParam);
      }
      const withOpenDraftsParam = String(params.get("wiki_with_open_drafts") || "")
        .trim()
        .toLowerCase();
      if (withOpenDraftsParam === "true") {
        setOpenPagesOnly(true);
      } else if (withOpenDraftsParam === "false") {
        setOpenPagesOnly(false);
      }
      const pageQueryParam = String(params.get("wiki_q") || "").trim();
      if (pageQueryParam) {
        setPageFilter(pageQueryParam);
      }
    } catch {
      // ignore invalid URL params
    } finally {
      setUrlStateReady(true);
    }
  }, []);

  useEffect(() => {
    if (!urlStateReady) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const setOrDelete = (key: string, value: string | null) => {
      if (value && value.trim()) {
        params.set(key, value.trim());
      } else {
        params.delete(key);
      }
    };
    setOrDelete("project", projectId.trim() || null);
    setOrDelete("wiki_space", selectedSpaceKey || null);
    setOrDelete("wiki_page", selectedPageSlug || null);
    setOrDelete("wiki_status", pageStatusFilter || null);
    setOrDelete("wiki_updated_by", pageUpdatedByFilter.trim() || null);
    setOrDelete("wiki_with_open_drafts", openPagesOnly ? "true" : null);
    setOrDelete("wiki_q", pageFilter.trim() || null);
    const nextSearch = params.toString();
    const currentSearch = window.location.search.replace(/^\?/, "");
    if (nextSearch === currentSearch) {
      return;
    }
    const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }, [openPagesOnly, pageFilter, pageStatusFilter, pageUpdatedByFilter, projectId, selectedPageSlug, selectedSpaceKey, urlStateReady]);

  useEffect(() => {
    if (!CAN_ACCESS_ADVANCED_MODE) {
      if (uiMode !== "core") {
        setUiMode("core");
      }
      if (coreExpertControls) {
        setCoreExpertControls(false);
      }
    }
  }, [coreExpertControls, uiMode]);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        apiUrl,
        projectId,
        reviewer,
        sessionToken,
        uiMode: effectiveUiMode,
        coreExpertControls: CAN_ACCESS_ADVANCED_MODE ? coreExpertControls : false,
        coreWorkspaceTab,
        status,
        pageStatusFilter,
        pageUpdatedByFilter,
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
    coreWorkspaceTab,
    pageStatusFilter,
    pageUpdatedByFilter,
    openPagesOnly,
    pinnedPageSlugs,
    projectId,
    reviewer,
    sessionToken,
    reviewQueuePreset,
    reviewSlaHours,
    savedViews,
    selectedSpaceKey,
    selectedViewId,
    status,
    effectiveUiMode,
  ]);

  const authHeaders: Record<string, string> = {};
  if (sessionToken.trim()) {
    authHeaders["X-Synapse-Session"] = sessionToken.trim();
  }

  const loadAuthMode = useCallback(async () => {
    try {
      const payload = await apiFetch<AuthModePayload>(apiUrl, "/v1/auth/mode", { extraHeaders: authHeaders });
      setAuthMode(payload);
    } catch {
      setAuthMode(null);
    }
  }, [apiUrl, authHeaders]);

  const createWebSessionFromOidc = useCallback(async () => {
    const token = oidcToken.trim();
    if (!token) {
      notifications.show({
        color: "red",
        title: "OIDC token required",
        message: "Paste an OIDC bearer token before creating a session.",
      });
      return;
    }
    setAuthActionLoading(true);
    try {
      const payload = await apiFetch<AuthSessionPayload>(apiUrl, "/v1/auth/session", {
        method: "POST",
        body: {},
        extraHeaders: { Authorization: `Bearer ${token}` },
      });
      const tokenValue = String(payload.session.session_token || "").trim();
      if (tokenValue) {
        setSessionToken(tokenValue);
      }
      setSessionSummary(payload.session);
      notifications.show({
        color: "teal",
        title: "Session created",
        message: `Authenticated as ${payload.session.subject}.`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Session create failed",
        message: String(error),
      });
    } finally {
      setAuthActionLoading(false);
    }
  }, [apiUrl, oidcToken]);

  const validateSession = useCallback(async () => {
    const token = sessionToken.trim();
    if (!token) {
      setSessionSummary(null);
      return;
    }
    setAuthActionLoading(true);
    try {
      const payload = await apiFetch<AuthSessionPayload>(apiUrl, "/v1/auth/session", {
        extraHeaders: { "X-Synapse-Session": token },
      });
      setSessionSummary(payload.session);
    } catch (error) {
      setSessionSummary(null);
      notifications.show({
        color: "orange",
        title: "Session invalid",
        message: String(error),
      });
    } finally {
      setAuthActionLoading(false);
    }
  }, [apiUrl, sessionToken]);

  const revokeSession = useCallback(async () => {
    const token = sessionToken.trim();
    if (!token) {
      setSessionSummary(null);
      return;
    }
    setAuthActionLoading(true);
    try {
      await apiFetch<{ status: string; revoked: boolean }>(apiUrl, "/v1/auth/session", {
        method: "DELETE",
        extraHeaders: { "X-Synapse-Session": token },
      });
      setSessionToken("");
      setSessionSummary(null);
      notifications.show({
        color: "teal",
        title: "Session revoked",
        message: "Web session token has been revoked.",
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Session revoke failed",
        message: String(error),
      });
    } finally {
      setAuthActionLoading(false);
    }
  }, [apiUrl, sessionToken]);

  useEffect(() => {
    void loadAuthMode();
  }, [loadAuthMode]);

  useEffect(() => {
    if (!sessionToken.trim()) {
      setSessionSummary(null);
      return;
    }
    void validateSession();
  }, [sessionToken, validateSession]);

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

  const loadWikiPages = useCallback(
    async (opts?: { silent?: boolean }) => {
      const project = projectId.trim();
      if (!project) {
        setWikiPages([]);
        return;
      }
      setLoadingPages(true);
      try {
        const params = new URLSearchParams();
        params.set("project_id", project);
        params.set("limit", "500");
        params.set("sort_by", "activity");
        params.set("sort_dir", "desc");
        const normalizedPageStatus = String(pageStatusFilter || "").trim().toLowerCase();
        if (normalizedPageStatus) {
          params.set("status", normalizedPageStatus);
        }
        const normalizedUpdatedBy = pageUpdatedByFilter.trim();
        if (normalizedUpdatedBy) {
          params.set("updated_by", normalizedUpdatedBy);
        }
        if (openPagesOnly) {
          params.set("with_open_drafts", "true");
        }
        const payload = await apiFetch<{ pages: WikiPageListItem[] }>(
          apiUrl,
          `/v1/wiki/pages?${params.toString()}`,
        );
        setWikiPages(payload.pages ?? []);
      } catch (error) {
        setWikiPages([]);
        if (!opts?.silent) {
          notifications.show({
            color: "red",
            title: "Failed to load wiki pages",
            message: String(error),
          });
        }
      } finally {
        setLoadingPages(false);
      }
    },
    [apiUrl, openPagesOnly, pageStatusFilter, pageUpdatedByFilter, projectId],
  );

  useEffect(() => {
    if (!projectId.trim()) {
      setWikiPages([]);
      return;
    }
    void loadWikiPages({ silent: true });
  }, [loadWikiPages, projectId]);

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
      await loadWikiPages({ silent: true });
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
  }, [
    apiUrl,
    loadModerationThroughput,
    loadWikiPages,
    projectId,
    selectedDraftId,
    showExpertModerationControls,
    status,
  ]);

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

  const loadPageAliases = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageAliases([]);
        return;
      }
      setLoadingPageAliases(true);
      try {
        const payload = await apiFetch<{ aliases: WikiPageAliasItem[] }>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/aliases?project_id=${encodeURIComponent(projectId)}`,
        );
        setPageAliases(payload.aliases ?? []);
      } catch {
        setPageAliases([]);
      } finally {
        setLoadingPageAliases(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageComments = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageComments([]);
        return;
      }
      setLoadingPageComments(true);
      try {
        const payload = await apiFetch<{ comments: WikiPageCommentItem[] }>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/comments?project_id=${encodeURIComponent(projectId)}&limit=100`,
        );
        setPageComments(payload.comments ?? []);
      } catch {
        setPageComments([]);
      } finally {
        setLoadingPageComments(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageWatchers = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageWatchers([]);
        return;
      }
      setLoadingPageWatchers(true);
      try {
        const payload = await apiFetch<{ watchers: WikiPageWatcherItem[] }>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/watchers?project_id=${encodeURIComponent(projectId)}`,
        );
        setPageWatchers(payload.watchers ?? []);
      } catch {
        setPageWatchers([]);
      } finally {
        setLoadingPageWatchers(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageReviewAssignments = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageReviewAssignments([]);
        return;
      }
      setLoadingPageReviewAssignments(true);
      try {
        const payload = await apiFetch<{ assignments: WikiPageReviewAssignmentItem[] }>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/review-assignments?project_id=${encodeURIComponent(projectId)}&limit=100`,
        );
        setPageReviewAssignments(payload.assignments ?? []);
      } catch {
        setPageReviewAssignments([]);
      } finally {
        setLoadingPageReviewAssignments(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadSpacePolicy = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setSpacePolicy(null);
        return;
      }
      setLoadingSpacePolicy(true);
      try {
        const spaceKey = pageGroupKey(slug).toLowerCase();
        const payload = await apiFetch<WikiSpacePolicyPayload>(
          apiUrl,
          `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/policy?project_id=${encodeURIComponent(projectId)}`,
        );
        setSpacePolicy(payload.policy);
        setSpaceWriteMode(payload.policy.write_mode === "owners_only" ? "owners_only" : "open");
        setSpaceCommentMode(payload.policy.comment_mode === "owners_only" ? "owners_only" : "open");
        setSpaceReviewRequired(Boolean(payload.policy.review_assignment_required));
      } catch {
        setSpacePolicy(null);
      } finally {
        setLoadingSpacePolicy(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadSpaceOwners = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setSpaceOwners([]);
        return;
      }
      setLoadingSpaceOwners(true);
      try {
        const spaceKey = pageGroupKey(slug).toLowerCase();
        const payload = await apiFetch<{ owners: WikiSpaceOwnerItem[] }>(
          apiUrl,
          `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/owners?project_id=${encodeURIComponent(projectId)}`,
        );
        setSpaceOwners(payload.owners ?? []);
      } catch {
        setSpaceOwners([]);
      } finally {
        setLoadingSpaceOwners(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageOwners = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageOwners([]);
        return;
      }
      setLoadingPageOwners(true);
      try {
        const payload = await apiFetch<{ owners: WikiPageOwnerItem[] }>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(slug)}/owners?project_id=${encodeURIComponent(projectId)}`,
        );
        setPageOwners(payload.owners ?? []);
      } catch {
        setPageOwners([]);
      } finally {
        setLoadingPageOwners(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadPageUploads = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setPageUploads([]);
        return;
      }
      setLoadingPageUploads(true);
      try {
        const payload = await apiFetch<{ uploads: WikiUploadItem[] }>(
          apiUrl,
          `/v1/wiki/uploads?project_id=${encodeURIComponent(projectId)}&page_slug=${encodeURIComponent(slug)}&limit=50`,
        );
        setPageUploads(payload.uploads ?? []);
      } catch {
        setPageUploads([]);
      } finally {
        setLoadingPageUploads(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadNotificationsInbox = useCallback(
    async (targetRecipient?: string) => {
      const recipient = (targetRecipient ?? reviewer).trim();
      if (!projectId.trim() || !recipient) {
        setNotificationsInbox([]);
        setUnreadNotificationCount(0);
        return;
      }
      setLoadingNotificationsInbox(true);
      try {
        const payload = await apiFetch<{
          notifications: WikiNotificationItem[];
          meta?: { unread_count?: number };
        }>(
          apiUrl,
          `/v1/wiki/notifications?project_id=${encodeURIComponent(projectId)}&recipient=${encodeURIComponent(recipient)}&status=all&limit=25`,
        );
        setNotificationsInbox(payload.notifications ?? []);
        setUnreadNotificationCount(Number(payload.meta?.unread_count ?? 0));
      } catch {
        setNotificationsInbox([]);
        setUnreadNotificationCount(0);
      } finally {
        setLoadingNotificationsInbox(false);
      }
    },
    [apiUrl, projectId, reviewer],
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
    if (Object.keys(collapsedTreeNodes).length === 0) return;
    const valid = new Set<string>();
    const stack = [...wikiTreeNodes];
    while (stack.length > 0) {
      const node = stack.pop();
      if (!node) continue;
      valid.add(node.key);
      if (node.children.length > 0) {
        stack.push(...node.children);
      }
    }
    const next: Record<string, boolean> = {};
    let changed = false;
    for (const [key, value] of Object.entries(collapsedTreeNodes)) {
      if (valid.has(key)) {
        next[key] = value;
      } else {
        changed = true;
      }
    }
    if (changed) {
      setCollapsedTreeNodes(next);
    }
  }, [collapsedTreeNodes, wikiTreeNodes]);

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
      setPageAliases([]);
      setPageComments([]);
      setPageWatchers([]);
      setPageReviewAssignments([]);
      setSpacePolicy(null);
      setSpaceOwners([]);
      setPageOwners([]);
      setPageUploads([]);
      setPageEditMode(false);
      setPageMoveMode(false);
      return;
    }
    void loadPageDetail(selectedPageSlug);
    void loadPageHistory(selectedPageSlug);
    void loadPageAliases(selectedPageSlug);
    void loadPageComments(selectedPageSlug);
    void loadPageWatchers(selectedPageSlug);
    void loadPageReviewAssignments(selectedPageSlug);
    void loadSpacePolicy(selectedPageSlug);
    void loadSpaceOwners(selectedPageSlug);
    void loadPageOwners(selectedPageSlug);
    void loadPageUploads(selectedPageSlug);
  }, [
    loadPageAliases,
    loadPageComments,
    loadPageDetail,
    loadPageHistory,
    loadPageOwners,
    loadPageUploads,
    loadPageReviewAssignments,
    loadSpaceOwners,
    loadSpacePolicy,
    loadPageWatchers,
    selectedPageSlug,
  ]);

  useEffect(() => {
    void loadNotificationsInbox();
  }, [loadNotificationsInbox]);

  useEffect(() => {
    if (pageEditMode) return;
    if (!selectedPageDetail) {
      setPageEditTitle("");
      setPageEditStatus("published");
      setPageEditSummary("Manual wiki page edit");
      setPageEditMarkdown("");
      return;
    }
    setPageEditTitle(selectedPageDetail.page.title || "");
    const normalizedStatus = String(selectedPageDetail.page.status || "published");
    if (
      normalizedStatus === "draft" ||
      normalizedStatus === "reviewed" ||
      normalizedStatus === "published" ||
      normalizedStatus === "archived"
    ) {
      setPageEditStatus(normalizedStatus);
    } else {
      setPageEditStatus("published");
    }
    setPageEditSummary("Manual wiki page edit");
    const nextMarkdown = String(selectedPageDetail.latest_version?.markdown || "");
    setPageEditMarkdown(nextMarkdown);
  }, [pageEditMode, selectedPageDetail]);

  useEffect(() => {
    if (pageMoveMode) return;
    if (!selectedPageDetail) {
      setPageMoveParentPath("");
      setPageMoveSlugLeaf("");
      setPageMoveTitle("");
      setPageMoveSummary("Page move/rename");
      setPageMoveIncludeDescendants(true);
      return;
    }
    const slug = String(selectedPageDetail.page.slug || "").trim();
    const segments = slug.split("/").filter(Boolean);
    const leaf = segments.length > 0 ? segments[segments.length - 1] : slugifySegment(selectedPageDetail.page.title || "page");
    const parent = segments.length > 1 ? segments.slice(0, -1).join("/") : "";
    setPageMoveParentPath(parent);
    setPageMoveSlugLeaf(leaf);
    setPageMoveTitle(selectedPageDetail.page.title || "");
    setPageMoveSummary("Page move/rename");
    setPageMoveIncludeDescendants(true);
  }, [pageMoveMode, selectedPageDetail]);

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
    if (effectiveUiMode === "core") {
      setCoreWorkspaceTab("drafts");
    }
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
  }, [effectiveUiMode]);

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
      if (effectiveUiMode === "core") {
        setCoreWorkspaceTab("drafts");
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
      effectiveUiMode,
    ],
  );

  const runBootstrapApprove = useCallback(
    async (dryRun: boolean) => {
      if (!projectId.trim() || !reviewer.trim()) {
        notifications.show({
          color: "red",
          title: "Missing reviewer or project",
          message: "Set Project ID and Reviewer before migration bootstrap.",
        });
        return;
      }
      const trustedSourceSystems = normalizeSourceSystemCsv(bootstrapTrustedSources);
      const limitRaw = Number.parseInt(bootstrapLimit, 10);
      const sampleRaw = Number.parseInt(bootstrapSampleSize, 10);
      const confidenceRaw = Number.parseFloat(bootstrapMinConfidence);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(2000, limitRaw)) : 50;
      const sampleSize = Number.isFinite(sampleRaw) ? Math.max(1, Math.min(200, sampleRaw)) : 15;
      const minConfidence = Number.isFinite(confidenceRaw) ? Math.max(0, Math.min(1, confidenceRaw)) : 0.85;
      const normalizedTrusted = trustedSourceSystems;
      if (!dryRun && normalizedTrusted.length === 0) {
        notifications.show({
          color: "orange",
          title: "Trusted sources required",
          message: "Set trusted sources before applying bootstrap migration.",
        });
        return;
      }
      if (!dryRun && limit > 200) {
        notifications.show({
          color: "orange",
          title: "Batch too large",
          message: "Apply flow is capped at 200 drafts per run in migration mode. Lower Batch limit.",
        });
        return;
      }
      const previewSelection = bootstrapResult?.selection;
      const previewTrusted = [...(previewSelection?.trusted_source_systems || [])]
        .map((item) => String(item || "").trim().toLowerCase())
        .filter(Boolean)
        .sort();
      const hasMatchingPreview =
        Boolean(bootstrapResult?.dry_run) &&
        String(bootstrapResult?.project_id || "") === projectId &&
        Number(previewSelection?.limit || -1) === limit &&
        Number(previewSelection?.min_confidence || -1) === minConfidence &&
        Boolean(previewSelection?.require_conflict_free) === bootstrapRequireConflictFree &&
        previewTrusted.join(",") === normalizedTrusted.join(",");
      if (!dryRun && !hasMatchingPreview) {
        notifications.show({
          color: "orange",
          title: "Preview required",
          message: "Run Preview Candidates first with the same migration settings before batch approval.",
        });
        return;
      }
      setBootstrapLoading(true);
      try {
        const payload = await apiFetch<BootstrapApproveRunPayload>(apiUrl, "/v1/wiki/drafts/bootstrap-approve/run", {
          method: "POST",
          body: {
            project_id: projectId,
            reviewed_by: reviewer.trim(),
            source_system: "web_bootstrap_ui",
            limit,
            sample_size: sampleSize,
            min_confidence: minConfidence,
            require_conflict_free: bootstrapRequireConflictFree,
            trusted_source_systems: trustedSourceSystems,
            require_trusted_sources_on_apply: true,
            allow_large_batch: false,
            dry_run: dryRun,
          },
          idempotencyKey: randomKey(),
        });
        setBootstrapResult(payload);
        if (dryRun) {
          notifications.show({
            color: "indigo",
            title: "Bootstrap preview ready",
            message: `Candidates: ${payload.summary.candidates}; sample: ${payload.summary.sample_size ?? 0}.`,
          });
          return;
        }
        notifications.show({
          color: payload.summary.failed ? "orange" : "green",
          title: "Bootstrap approval completed",
          message: `Approved ${payload.summary.approved ?? 0}; failed ${payload.summary.failed ?? 0}.`,
        });
        await loadDrafts();
        if (selectedDraftId) {
          await loadDraftDetail(selectedDraftId);
          await loadConflictExplain(selectedDraftId);
        }
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Bootstrap migration failed",
          message: String(error),
        });
      } finally {
        setBootstrapLoading(false);
      }
    },
    [
      apiUrl,
      bootstrapLimit,
      bootstrapMinConfidence,
      bootstrapRequireConflictFree,
      bootstrapSampleSize,
      bootstrapTrustedSources,
      bootstrapResult,
      loadConflictExplain,
      loadDraftDetail,
      loadDrafts,
      projectId,
      reviewer,
      selectedDraftId,
    ],
  );

  const saveWikiPageEdit = useCallback(async () => {
    if (!selectedPageSlug) {
      notifications.show({
        color: "red",
        title: "Page not selected",
        message: "Select wiki page before saving edits.",
      });
      return;
    }
    if (!projectId.trim() || !reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Missing reviewer or project",
        message: "Set Project ID and Reviewer before saving page edits.",
      });
      return;
    }
    const markdown = pageEditMarkdown.trim();
    if (!markdown) {
      notifications.show({
        color: "red",
        title: "Markdown required",
        message: "Page markdown cannot be empty.",
      });
      return;
    }
    setSavingPageEdit(true);
    try {
      const payload = await apiFetch<WikiPageUpdateResponse>(
        apiUrl,
        `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}`,
        {
          method: "PUT",
          body: {
            project_id: projectId,
            updated_by: reviewer.trim(),
            title: pageEditTitle.trim() || null,
            page_type: selectedPageDetail?.page.page_type || null,
            status: pageEditStatus,
            markdown,
            change_summary: pageEditSummary.trim() || null,
          },
          idempotencyKey: randomKey(),
        },
      );
      if (payload.status === "no_change") {
        notifications.show({
          color: "gray",
          title: "No page changes",
          message: "Wiki page content is unchanged.",
        });
      } else {
        notifications.show({
          color: "green",
          title: "Wiki page saved",
          message: `Version ${payload.page.current_version ?? "updated"} published.`,
        });
      }
      setPageEditMode(false);
      await loadPageDetail(selectedPageSlug);
      await loadPageHistory(selectedPageSlug);
      await loadWikiPages({ silent: true });
      await loadDrafts();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Save failed",
        message: String(error),
      });
    } finally {
      setSavingPageEdit(false);
    }
  }, [
    apiUrl,
    loadDrafts,
    loadPageDetail,
    loadPageHistory,
    loadWikiPages,
    pageEditMarkdown,
    pageEditStatus,
    pageEditSummary,
    pageEditTitle,
    projectId,
    reviewer,
    selectedPageDetail?.page.page_type,
    selectedPageSlug,
  ]);

  const moveWikiPage = useCallback(async () => {
    if (!selectedPageSlug) {
      notifications.show({
        color: "red",
        title: "Page not selected",
        message: "Select wiki page before move/rename.",
      });
      return;
    }
    if (!projectId.trim() || !reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Missing reviewer or project",
        message: "Set Project ID and Reviewer before moving pages.",
      });
      return;
    }
    const leaf = slugifySegment(pageMoveSlugLeaf.trim() || pageMoveTitle.trim() || selectedPageSlug);
    const parentRaw = pageMoveParentPath.trim();
    const normalizedParent = parentRaw ? normalizeWikiSlug(parentRaw, "root") : "";
    const rawTarget = normalizedParent ? `${normalizedParent}/${leaf}` : leaf;
    const normalizedNewSlug = normalizeWikiSlug(rawTarget, selectedPageSlug);
    if (!normalizedNewSlug) {
      notifications.show({
        color: "red",
        title: "Invalid target slug",
        message: "Provide valid parent path and slug leaf.",
      });
      return;
    }
    setMovingPage(true);
    try {
      const payload = await apiFetch<WikiPageMoveResponse>(
        apiUrl,
        `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/reparent`,
        {
          method: "PUT",
          body: {
            project_id: projectId,
            moved_by: reviewer.trim(),
            new_parent_slug: normalizedParent || null,
            new_slug_leaf: leaf,
            new_title: pageMoveTitle.trim() || null,
            include_descendants: pageMoveIncludeDescendants,
            change_summary: pageMoveSummary.trim() || null,
          },
          idempotencyKey: randomKey(),
        },
      );
      if (payload.status === "no_change") {
        notifications.show({
          color: "gray",
          title: "No move changes",
          message: "Page slug/title unchanged.",
        });
      } else {
        notifications.show({
          color: "green",
          title: "Page moved",
          message: `${payload.moved_pages.length || 1} page(s) updated.`,
        });
      }
      const nextSlug = String(payload.page.slug || normalizedNewSlug);
      setSelectedSpaceKey(pageGroupKey(nextSlug));
      setSelectedPageSlug(nextSlug);
      setPageMoveMode(false);
      await loadWikiPages({ silent: true });
      await loadPageDetail(nextSlug);
      await loadPageHistory(nextSlug);
      await loadDrafts();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Move failed",
        message: String(error),
      });
    } finally {
      setMovingPage(false);
    }
  }, [
    apiUrl,
    loadDrafts,
    loadPageDetail,
    loadPageHistory,
    loadWikiPages,
    pageMoveIncludeDescendants,
    pageMoveParentPath,
    pageMoveSlugLeaf,
    pageMoveSummary,
    pageMoveTitle,
    projectId,
    reviewer,
    selectedPageSlug,
  ]);

  const transitionWikiPageStatus = useCallback(
    async (mode: "archive" | "restore") => {
      if (!selectedPageSlug) {
        notifications.show({
          color: "red",
          title: "Page not selected",
          message: "Select wiki page before changing status.",
        });
        return;
      }
      if (!projectId.trim() || !reviewer.trim()) {
        notifications.show({
          color: "red",
          title: "Missing reviewer or project",
          message: "Set Project ID and Reviewer before status change.",
        });
        return;
      }
      setMovingPage(true);
      try {
        const endpoint = mode === "archive" ? "archive" : "restore";
        const payload = await apiFetch<WikiPageStatusTransitionResponse>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/${endpoint}`,
          {
            method: "PUT",
            body: {
              project_id: projectId,
              updated_by: reviewer.trim(),
              include_descendants: false,
              restore_status: "published",
              change_summary:
                mode === "archive"
                  ? `Archived by ${reviewer.trim()}`
                  : `Restored by ${reviewer.trim()} to published`,
            },
            idempotencyKey: randomKey(),
          },
        );
        const nextSlug = String(payload.page.slug || selectedPageSlug);
        notifications.show({
          color: "green",
          title: mode === "archive" ? "Page archived" : "Page restored",
          message: `${payload.changed_pages.length || 0} page(s) updated.`,
        });
        await loadWikiPages({ silent: true });
        await loadPageDetail(nextSlug);
        await loadPageHistory(nextSlug);
        await loadDrafts();
      } catch (error) {
        notifications.show({
          color: "red",
          title: mode === "archive" ? "Archive failed" : "Restore failed",
          message: String(error),
        });
      } finally {
        setMovingPage(false);
      }
    },
    [
      apiUrl,
      loadDrafts,
      loadPageDetail,
      loadPageHistory,
      loadWikiPages,
      projectId,
      reviewer,
      selectedPageSlug,
    ],
  );

  const uploadPageAsset = useCallback(async () => {
    if (!pageAssetFile || !projectId.trim() || !reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Asset upload unavailable",
        message: "Select a file and ensure Project ID + Reviewer are set.",
      });
      return;
    }
    setUploadingPageAsset(true);
    try {
      const formData = new FormData();
      formData.set("project_id", projectId.trim());
      formData.set("uploaded_by", reviewer.trim());
      if (selectedPageSlug) {
        formData.set("page_slug", selectedPageSlug);
      }
      formData.set("file", pageAssetFile);
      const payload = await apiFetch<WikiUploadCreatePayload>(apiUrl, "/v1/wiki/uploads", {
        method: "POST",
        formData,
        idempotencyKey: randomKey(),
      });
      const snippet = String(payload.upload.markdown_snippet || "").trim();
      if (snippet) {
        setPageEditMarkdown((prev) => {
          const normalizedPrev = prev.trimEnd();
          if (normalizedPrev.includes(snippet)) {
            return `${normalizedPrev}\n`;
          }
          return `${normalizedPrev}\n\n${snippet}\n`;
        });
      }
      setPageAssetFile(null);
      if (selectedPageSlug) {
        await loadPageUploads(selectedPageSlug);
      }
      notifications.show({
        color: "green",
        title: "Asset uploaded",
        message: `${payload.upload.filename} uploaded and snippet inserted into markdown.`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Asset upload failed",
        message: String(error),
      });
    } finally {
      setUploadingPageAsset(false);
    }
  }, [apiUrl, loadPageUploads, pageAssetFile, projectId, reviewer, selectedPageSlug]);

  const createPageAlias = useCallback(async () => {
    if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
    const raw = newPageAlias.trim();
    if (!raw) return;
    setSavingPageAlias(true);
    try {
      await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/aliases`, {
        method: "POST",
        body: {
          project_id: projectId,
          created_by: reviewer.trim(),
          alias_text: raw,
        },
        idempotencyKey: randomKey(),
      });
      setNewPageAlias("");
      await loadPageAliases(selectedPageSlug);
      notifications.show({
        color: "green",
        title: "Alias added",
        message: "Wiki alias saved.",
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Alias create failed",
        message: String(error),
      });
    } finally {
      setSavingPageAlias(false);
    }
  }, [apiUrl, loadPageAliases, newPageAlias, projectId, reviewer, selectedPageSlug]);

  const deletePageAlias = useCallback(
    async (aliasText: string) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      setSavingPageAlias(true);
      try {
        await apiFetch(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/aliases/${encodeURIComponent(aliasText)}?project_id=${encodeURIComponent(projectId)}&deleted_by=${encodeURIComponent(reviewer.trim())}`,
          {
            method: "DELETE",
            idempotencyKey: randomKey(),
          },
        );
        await loadPageAliases(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Alias delete failed",
          message: String(error),
        });
      } finally {
        setSavingPageAlias(false);
      }
    },
    [apiUrl, loadPageAliases, projectId, reviewer, selectedPageSlug],
  );

  const createPageComment = useCallback(async () => {
    if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
    const body = newPageComment.trim();
    if (!body) return;
    setSavingPageComment(true);
    try {
      await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/comments`, {
        method: "POST",
        body: {
          project_id: projectId,
          created_by: reviewer.trim(),
          body,
        },
        idempotencyKey: randomKey(),
      });
      setNewPageComment("");
      await loadPageComments(selectedPageSlug);
      notifications.show({
        color: "green",
        title: "Comment added",
        message: "Page comment saved.",
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Comment create failed",
        message: String(error),
      });
    } finally {
      setSavingPageComment(false);
    }
  }, [apiUrl, loadPageComments, newPageComment, projectId, reviewer, selectedPageSlug]);

  const deletePageComment = useCallback(
    async (commentId: string) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      setSavingPageComment(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/comments/${encodeURIComponent(commentId)}`, {
          method: "DELETE",
          body: {
            project_id: projectId,
            deleted_by: reviewer.trim(),
          },
          idempotencyKey: randomKey(),
        });
        await loadPageComments(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Comment delete failed",
          message: String(error),
        });
      } finally {
        setSavingPageComment(false);
      }
    },
    [apiUrl, loadPageComments, projectId, reviewer, selectedPageSlug],
  );

  const upsertPageWatcher = useCallback(
    async (watcher: string, active: boolean) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      const normalizedWatcher = watcher.trim();
      if (!normalizedWatcher) return;
      setSavingPageWatcher(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/watchers`, {
          method: "PUT",
          body: {
            project_id: projectId,
            actor: reviewer.trim(),
            watcher: normalizedWatcher,
            active,
          },
          idempotencyKey: randomKey(),
        });
        if (active) setWatcherInput("");
        await loadPageWatchers(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: active ? "Watcher add failed" : "Watcher remove failed",
          message: String(error),
        });
      } finally {
        setSavingPageWatcher(false);
      }
    },
    [apiUrl, loadPageWatchers, projectId, reviewer, selectedPageSlug],
  );

  const createPageReviewAssignment = useCallback(async () => {
    if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
    const assignee = assignmentAssigneeInput.trim();
    if (!assignee) return;
    setSavingPageAssignment(true);
    try {
      await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/review-assignments`, {
        method: "PUT",
        body: {
          project_id: projectId,
          created_by: reviewer.trim(),
          assignee,
          role: "reviewer",
          note: assignmentNoteInput.trim() || null,
        },
        idempotencyKey: randomKey(),
      });
      setAssignmentAssigneeInput("");
      setAssignmentNoteInput("");
      await loadPageReviewAssignments(selectedPageSlug);
      notifications.show({
        color: "green",
        title: "Reviewer assigned",
        message: `${assignee} assigned to page review.`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Assign reviewer failed",
        message: String(error),
      });
    } finally {
      setSavingPageAssignment(false);
    }
  }, [
    apiUrl,
    assignmentAssigneeInput,
    assignmentNoteInput,
    loadPageReviewAssignments,
    projectId,
    reviewer,
    selectedPageSlug,
  ]);

  const resolvePageReviewAssignment = useCallback(
    async (assignmentId: string) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      setSavingPageAssignment(true);
      try {
        await apiFetch(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/review-assignments/${encodeURIComponent(assignmentId)}/resolve`,
          {
            method: "POST",
            body: {
              project_id: projectId,
              resolved_by: reviewer.trim(),
              resolution_note: "Resolved from wiki context panel",
            },
            idempotencyKey: randomKey(),
          },
        );
        await loadPageReviewAssignments(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Resolve assignment failed",
          message: String(error),
        });
      } finally {
        setSavingPageAssignment(false);
      }
    },
    [apiUrl, loadPageReviewAssignments, projectId, reviewer, selectedPageSlug],
  );

  const saveSpacePolicy = useCallback(async () => {
    if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
    const spaceKey = pageGroupKey(selectedPageSlug).toLowerCase();
    setSavingSpacePolicy(true);
    try {
      await apiFetch(apiUrl, `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/policy`, {
        method: "PUT",
        body: {
          project_id: projectId,
          space_key: spaceKey,
          updated_by: reviewer.trim(),
          write_mode: spaceWriteMode,
          comment_mode: spaceCommentMode,
          review_assignment_required: spaceReviewRequired,
        },
        idempotencyKey: randomKey(),
      });
      await loadSpacePolicy(selectedPageSlug);
      notifications.show({
        color: "green",
        title: "Space policy updated",
        message: `${spaceKey} policy saved.`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Policy update failed",
        message: String(error),
      });
    } finally {
      setSavingSpacePolicy(false);
    }
  }, [
    apiUrl,
    loadSpacePolicy,
    projectId,
    reviewer,
    selectedPageSlug,
    spaceCommentMode,
    spaceReviewRequired,
    spaceWriteMode,
  ]);

  const upsertSpaceOwner = useCallback(
    async (owner: string, active: boolean) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      const ownerValue = owner.trim();
      if (!ownerValue) return;
      const spaceKey = pageGroupKey(selectedPageSlug).toLowerCase();
      setSavingSpaceOwner(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/owners`, {
          method: "PUT",
          body: {
            project_id: projectId,
            actor: reviewer.trim(),
            owner: ownerValue,
            role: spaceOwnerRoleInput.trim() || "owner",
            active,
          },
          idempotencyKey: randomKey(),
        });
        if (active) setSpaceOwnerInput("");
        await loadSpaceOwners(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: active ? "Owner add failed" : "Owner remove failed",
          message: String(error),
        });
      } finally {
        setSavingSpaceOwner(false);
      }
    },
    [
      apiUrl,
      loadSpaceOwners,
      projectId,
      reviewer,
      selectedPageSlug,
      spaceOwnerRoleInput,
    ],
  );

  const upsertPageOwner = useCallback(
    async (owner: string, active: boolean) => {
      if (!selectedPageSlug || !projectId.trim() || !reviewer.trim()) return;
      const ownerValue = owner.trim();
      if (!ownerValue) return;
      setSavingPageOwner(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/owners`, {
          method: "PUT",
          body: {
            project_id: projectId,
            actor: reviewer.trim(),
            owner: ownerValue,
            role: pageOwnerRoleInput.trim() || "editor",
            active,
          },
          idempotencyKey: randomKey(),
        });
        if (active) setPageOwnerInput("");
        await loadPageOwners(selectedPageSlug);
      } catch (error) {
        notifications.show({
          color: "red",
          title: active ? "Page owner add failed" : "Page owner remove failed",
          message: String(error),
        });
      } finally {
        setSavingPageOwner(false);
      }
    },
    [apiUrl, loadPageOwners, pageOwnerRoleInput, projectId, reviewer, selectedPageSlug],
  );

  const markNotificationRead = useCallback(
    async (notificationId: string) => {
      if (!projectId.trim() || !reviewer.trim()) return;
      setSavingNotificationState(true);
      try {
        await apiFetch(apiUrl, `/v1/wiki/notifications/${encodeURIComponent(notificationId)}/read`, {
          method: "POST",
          body: {
            project_id: projectId,
            recipient: reviewer.trim(),
          },
          idempotencyKey: randomKey(),
        });
        await loadNotificationsInbox(reviewer.trim());
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Notification update failed",
          message: String(error),
        });
      } finally {
        setSavingNotificationState(false);
      }
    },
    [apiUrl, loadNotificationsInbox, projectId, reviewer],
  );

  const markAllNotificationsRead = useCallback(async () => {
    if (!projectId.trim() || !reviewer.trim()) return;
    setSavingNotificationState(true);
    try {
      await apiFetch(apiUrl, "/v1/wiki/notifications/read-all", {
        method: "POST",
        body: {
          project_id: projectId,
          recipient: reviewer.trim(),
        },
        idempotencyKey: randomKey(),
      });
      await loadNotificationsInbox(reviewer.trim());
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Mark all failed",
        message: String(error),
      });
    } finally {
      setSavingNotificationState(false);
    }
  }, [apiUrl, loadNotificationsInbox, projectId, reviewer]);

  const selectPrevDraft = useCallback(() => {
    if (visibleDrafts.length === 0) return;
    if (effectiveUiMode === "core") {
      setCoreWorkspaceTab("drafts");
    }
    const current = selectedIndex >= 0 ? selectedIndex : 0;
    const prev = current <= 0 ? visibleDrafts.length - 1 : current - 1;
    setSelectedDraftId(visibleDrafts[prev].id);
  }, [effectiveUiMode, selectedIndex, visibleDrafts]);

  const selectNextDraft = useCallback(() => {
    if (visibleDrafts.length === 0) return;
    if (effectiveUiMode === "core") {
      setCoreWorkspaceTab("drafts");
    }
    const current = selectedIndex >= 0 ? selectedIndex : -1;
    const next = current >= visibleDrafts.length - 1 ? 0 : current + 1;
    setSelectedDraftId(visibleDrafts[next].id);
  }, [effectiveUiMode, selectedIndex, visibleDrafts]);

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
                pageStatusFilter,
                pageUpdatedByFilter,
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
      pageStatusFilter,
      pageUpdatedByFilter,
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
    pageStatusFilter,
    pageUpdatedByFilter,
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
      setPageStatusFilter(view.pageStatusFilter ?? null);
      setPageUpdatedByFilter(view.pageUpdatedByFilter ?? "");
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
      await loadWikiPages({ silent: true });
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
  }, [apiUrl, guidedPageForm, loadPageDetail, loadPageHistory, loadWikiPages, projectId, reviewer]);

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
  const wikiPreviewMarkdown = useMemo(() => {
    const latestMarkdown = String(selectedPageDetail?.latest_version?.markdown || "").trim();
    if (latestMarkdown) return latestMarkdown;
    const sections = selectedPageDetail?.sections ?? [];
    const statements = selectedPageDetail?.statements ?? [];
    if (sections.length === 0) return "";
    return sections
      .map((section) => {
        const lines = statements
          .filter((item) => item.section_key === section.section_key)
          .map((item) => `- ${item.statement_text}`);
        if (lines.length === 0) {
          return `## ${section.heading}\n\n_No statements yet._`;
        }
        return `## ${section.heading}\n\n${lines.join("\n")}`;
      })
      .join("\n\n");
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
  const wikiPageBreadcrumb = useMemo(() => {
    const slug = String(selectedPageDetail?.page.slug || selectedPageSlug || "").trim();
    const segments = slug.split("/").filter(Boolean);
    const crumbs: Array<{ label: string; slug: string | null }> = [
      { label: "Wiki", slug: null },
    ];
    let current = "";
    for (const segment of segments) {
      current = current ? `${current}/${segment}` : segment;
      const pageMatch = pageNodes.find((item) => item.slug === current);
      crumbs.push({
        label: pageMatch?.title || segment,
        slug: current,
      });
    }
    if (segments.length === 0 && selectedPageDetail?.page.title) {
      crumbs.push({ label: selectedPageDetail.page.title, slug: selectedPageSlug });
    }
    return crumbs;
  }, [pageNodes, selectedPageDetail?.page.slug, selectedPageDetail?.page.title, selectedPageSlug]);
  const effectiveQueuePreset: ReviewQueuePresetKey = showExpertModerationControls ? reviewQueuePreset : "open_queue";
  const isCoreSimplified = effectiveUiMode === "core" && (!CAN_ACCESS_ADVANCED_MODE || !coreExpertControls);
  const showCoreWikiPanel = effectiveUiMode === "advanced" || coreWorkspaceTab === "wiki";
  const showCoreDraftPanels = effectiveUiMode === "advanced" || coreWorkspaceTab === "drafts";
  const showCoreTaskPanel = effectiveUiMode === "advanced" || coreWorkspaceTab === "tasks";
  const showCoreWikiPreviewPanel = effectiveUiMode === "core" && coreWorkspaceTab === "wiki";
  const showCoreWikiContextPanel = effectiveUiMode === "core" && coreWorkspaceTab === "wiki";
  const bootstrapTrustedSourceSystems = useMemo(
    () => normalizeSourceSystemCsv(bootstrapTrustedSources),
    [bootstrapTrustedSources],
  );
  const bootstrapLimitValue = useMemo(() => {
    const parsed = Number.parseInt(bootstrapLimit, 10);
    return Number.isFinite(parsed) ? Math.max(1, Math.min(2000, parsed)) : 50;
  }, [bootstrapLimit]);
  const bootstrapMinConfidenceValue = useMemo(() => {
    const parsed = Number.parseFloat(bootstrapMinConfidence);
    return Number.isFinite(parsed) ? Math.max(0, Math.min(1, parsed)) : 0.85;
  }, [bootstrapMinConfidence]);
  const bootstrapCanApply = useMemo(() => {
    const selection = bootstrapResult?.selection;
    if (!bootstrapResult?.dry_run || !selection) return false;
    if (String(bootstrapResult.project_id || "") !== projectId) return false;
    const previewTrusted = [...(selection.trusted_source_systems || [])]
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean)
      .sort();
    if (previewTrusted.join(",") !== bootstrapTrustedSourceSystems.join(",")) return false;
    if (Number(selection.limit || -1) !== bootstrapLimitValue) return false;
    if (Number(selection.min_confidence || -1) !== bootstrapMinConfidenceValue) return false;
    if (Boolean(selection.require_conflict_free) !== bootstrapRequireConflictFree) return false;
    return Number(bootstrapResult.summary.candidates || 0) > 0;
  }, [
    bootstrapLimitValue,
    bootstrapMinConfidenceValue,
    bootstrapRequireConflictFree,
    bootstrapResult,
    bootstrapTrustedSourceSystems,
    projectId,
  ]);
  const coreGridCols =
    effectiveUiMode === "advanced"
      ? { base: 1, xl: 3 }
      : coreWorkspaceTab === "wiki"
        ? { base: 1, xl: 3 }
        : { base: 1, xl: 2 };
  const selectedQueuePreset = useMemo(
    () => REVIEW_QUEUE_PRESETS.find((item) => item.key === effectiveQueuePreset) || REVIEW_QUEUE_PRESETS[0],
    [effectiveQueuePreset],
  );
  const selectedDraftSummary = useMemo(
    () => (selectedDraftId ? drafts.find((item) => item.id === selectedDraftId) || null : null),
    [drafts, selectedDraftId],
  );
  const latestPageVersion = useMemo(() => (pageHistory?.versions ?? [])[0] || null, [pageHistory]);
  const pageRevisionDelta = useMemo(() => {
    const addedTokens = pageHistoryDiff.after.filter((token) => token.kind === "added").length;
    const removedTokens = pageHistoryDiff.before.filter((token) => token.kind === "removed").length;
    return {
      addedTokens,
      removedTokens,
      changed: addedTokens + removedTokens,
    };
  }, [pageHistoryDiff]);
  const selectedPageOpenDrafts = useMemo(() => {
    if (!selectedPageSlug) return [];
    return drafts
      .filter((item) => String(item.page.slug || "").trim() === selectedPageSlug && isOpenReviewDraft(item))
      .slice(0, 6);
  }, [drafts, selectedPageSlug]);
  const currentReviewerWatchingPage = useMemo(() => {
    const actor = reviewer.trim().toLowerCase();
    if (!actor) return false;
    return pageWatchers.some((item) => String(item.watcher || "").trim().toLowerCase() === actor);
  }, [pageWatchers, reviewer]);
  const pageMovePreviewSlug = useMemo(() => {
    const leaf = slugifySegment(pageMoveSlugLeaf.trim() || pageMoveTitle.trim() || selectedPageSlug || "page");
    const parentRaw = pageMoveParentPath.trim();
    if (!parentRaw) {
      return normalizeWikiSlug(leaf, leaf);
    }
    const normalizedParent = normalizeWikiSlug(parentRaw, "root");
    return normalizeWikiSlug(`${normalizedParent}/${leaf}`, leaf);
  }, [pageMoveParentPath, pageMoveSlugLeaf, pageMoveTitle, selectedPageSlug]);
  const wikiHomeRecentPages = useMemo(() => {
    return [...pageNodes]
      .sort((a, b) => {
        const tsA = a.latest_draft_at ? new Date(a.latest_draft_at).getTime() : 0;
        const tsB = b.latest_draft_at ? new Date(b.latest_draft_at).getTime() : 0;
        return tsB - tsA;
      })
      .slice(0, 8);
  }, [pageNodes]);
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

  const renderWikiTreeNode = (node: WikiTreeNode) => {
    const isSelected = Boolean(node.slug && selectedPageSlug === node.slug);
    const isCollapsed = Boolean(collapsedTreeNodes[node.key]);
    const hasChildren = node.children.length > 0;
    const hasPage = Boolean(node.page && node.slug);
    const page = node.page;
    return (
      <Stack key={node.key} gap={6} style={{ marginLeft: `${Math.max(0, node.depth) * 14}px` }}>
        <Paper
          withBorder
          p="xs"
          radius="md"
          className={isSelected ? "draft-card active wiki-tree-node-row" : "draft-card wiki-tree-node-row"}
          onClick={() => {
            if (!node.slug) return;
            setSelectedSpaceKey(pageGroupKey(node.slug));
            setSelectedPageSlug(node.slug);
          }}
        >
          <Group justify="space-between" align="center" wrap="nowrap">
            <Group gap={6} wrap="nowrap">
              {hasChildren ? (
                <ActionIcon
                  size="sm"
                  variant="subtle"
                  onClick={(event) => {
                    event.stopPropagation();
                    setCollapsedTreeNodes((prev) => ({ ...prev, [node.key]: !prev[node.key] }));
                  }}
                  aria-label={isCollapsed ? `Expand ${node.label}` : `Collapse ${node.label}`}
                >
                  {isCollapsed ? <IconChevronDown size={14} /> : <IconChevronUp size={14} />}
                </ActionIcon>
              ) : (
                <Box w={24} />
              )}
              <Stack gap={2}>
                <Text size="sm" fw={700}>
                  {node.label}
                </Text>
                {node.slug && (
                  <Text size="xs" c="dimmed">
                    {node.slug}
                  </Text>
                )}
              </Stack>
            </Group>
            <Group gap={6} wrap="nowrap">
              {hasPage && page ? (
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
                  {pinnedPageSlugs.includes(page.slug) ? <IconBookmarkFilled size={14} /> : <IconBookmark size={14} />}
                </ActionIcon>
              ) : null}
              <Badge size="xs" variant="light" color="blue">
                pages {node.page_count}
              </Badge>
              <Badge size="xs" variant="light" color="orange">
                open {node.open_count}
              </Badge>
            </Group>
          </Group>
          {isSelected && loadingPageDetail && (
            <Group mt={6}>
              <Loader size="xs" />
              <Text size="xs" c="dimmed">
                loading page sections
              </Text>
            </Group>
          )}
          {isSelected && selectedPageDetail && selectedPageDetail.sections.length > 0 && (
            <Stack gap={2} mt={6}>
              {selectedPageDetail.sections.slice(0, 4).map((section) => (
                <Text key={section.section_key} size="xs" c="dimmed">
                  {section.heading} ({section.statement_count})
                </Text>
              ))}
            </Stack>
          )}
        </Paper>
        {hasChildren && !isCollapsed && (
          <Stack gap={6}>
            {node.children.map((child) => renderWikiTreeNode(child))}
          </Stack>
        )}
      </Stack>
    );
  };

  if (requiresAuthSession && !hasSessionToken) {
    return (
      <Box className="synapse-shell">
        <Box className="bg-orb bg-orb-a" />
        <Box className="bg-orb bg-orb-b" />
        <Stack gap="lg">
          <Paper radius="xl" p="xl" className="hero-card">
            <Stack gap={6}>
              <Text className="eyebrow">Synapse Wiki</Text>
              <Title order={1}>Sign in to continue</Title>
              <Text c="dimmed">
                Authenticate once, then you will land directly in Wiki workspace with Drafts and Tasks.
              </Text>
            </Stack>
          </Paper>
          <Paper radius="xl" p="lg">
            <Stack gap="sm">
              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                <PasswordInput
                  label="OIDC Bearer Token"
                  value={oidcToken}
                  onChange={(event) => setOidcToken(event.currentTarget.value)}
                  placeholder="Paste token (without Bearer prefix)"
                />
                <TextInput
                  label="Session Token"
                  value={sessionToken}
                  onChange={(event) => setSessionToken(event.currentTarget.value)}
                  placeholder="syns_..."
                />
              </SimpleGrid>
              <Group gap="xs" wrap="wrap">
                <Button size="sm" variant="filled" loading={authActionLoading} onClick={() => void createWebSessionFromOidc()}>
                  Create Session
                </Button>
                <Button size="sm" variant="light" loading={authActionLoading} onClick={() => void validateSession()}>
                  Validate Session
                </Button>
              </Group>
              <Text size="xs" c="dimmed">
                Auth mode: {authMode?.auth_mode || "unknown"}; RBAC: {authMode?.rbac_mode || "unknown"}; tenancy:{" "}
                {authMode?.tenancy_mode || "unknown"}.
              </Text>
            </Stack>
          </Paper>
        </Stack>
      </Box>
    );
  }

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
                onClick={() => {
                  void loadDrafts();
                  void loadNotificationsInbox();
                  if (selectedPageSlug) {
                    void loadSpacePolicy(selectedPageSlug);
                    void loadSpaceOwners(selectedPageSlug);
                    void loadPageOwners(selectedPageSlug);
                    void loadPageUploads(selectedPageSlug);
                  }
                }}
                aria-label="Refresh drafts"
              >
                <IconRefresh size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>

        <Paper radius="xl" p="lg">
          <SimpleGrid cols={{ base: 1, md: 2, lg: effectiveUiMode === "advanced" ? 5 : 3 }} spacing="md">
            {effectiveUiMode === "advanced" && (
              <TextInput
                label="API URL"
                value={apiUrl}
                onChange={(event) => setApiUrl(event.currentTarget.value)}
                leftSection={<IconCloudCog size={16} />}
                placeholder="http://localhost:8080"
              />
            )}
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
            {effectiveUiMode === "advanced" && (
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
          {effectiveUiMode === "core" && (
            <Text size="xs" c="dimmed" mt={8}>
              API endpoint uses workspace default. Switch to advanced profile to override API URL.
            </Text>
          )}

          <Paper mt="md" withBorder radius="lg" p="md">
            <Stack gap="xs">
              <Group justify="space-between" align="center" wrap="wrap">
                <Group gap={8}>
                  <ThemeIcon size="sm" radius="xl" variant="light" color={unreadNotificationCount > 0 ? "orange" : "gray"}>
                    <IconBell size={14} />
                  </ThemeIcon>
                  <Text size="sm" fw={700}>
                    Notifications
                  </Text>
                  <Badge size="xs" variant="light" color={unreadNotificationCount > 0 ? "orange" : "gray"}>
                    unread {unreadNotificationCount}
                  </Badge>
                </Group>
                <Group gap={6}>
                  <Button size="compact-xs" variant="light" onClick={() => void loadNotificationsInbox()}>
                    Refresh
                  </Button>
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    color="teal"
                    loading={savingNotificationState}
                    onClick={() => void markAllNotificationsRead()}
                  >
                    Mark all read
                  </Button>
                </Group>
              </Group>
              {loadingNotificationsInbox ? (
                <Group gap={6}>
                  <Loader size="xs" />
                  <Text size="xs" c="dimmed">
                    loading notifications…
                  </Text>
                </Group>
              ) : notificationsInbox.length === 0 ? (
                <Text size="xs" c="dimmed">
                  No notifications for current reviewer.
                </Text>
              ) : (
                <Stack gap={6}>
                  {notificationsInbox.slice(0, 6).map((item) => (
                    <Paper key={`notif-${item.id}`} withBorder p="xs" radius="md">
                      <Group justify="space-between" align="flex-start" wrap="nowrap">
                        <Stack gap={2} style={{ flex: 1 }}>
                          <Text size="xs" fw={700}>
                            {item.title}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {item.actor ? `${item.actor} • ` : ""}
                            {fmtDate(item.created_at)}
                          </Text>
                          {item.body ? (
                            <Text size="xs" c="dimmed">
                              {item.body}
                            </Text>
                          ) : null}
                        </Stack>
                        {item.status === "unread" ? (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="teal"
                            loading={savingNotificationState}
                            onClick={() => void markNotificationRead(item.id)}
                          >
                            Read
                          </Button>
                        ) : (
                          <Badge size="xs" variant="light" color="gray">
                            read
                          </Badge>
                        )}
                      </Group>
                    </Paper>
                  ))}
                </Stack>
              )}
            </Stack>
          </Paper>

          {effectiveUiMode === "advanced" && (
            <Paper mt="md" withBorder radius="lg" p="md">
              <Stack gap="sm">
                <Group justify="space-between" align="center" wrap="wrap">
                  <Text fw={700}>Auth Session</Text>
                  <Group gap={8}>
                    <Badge variant="light" color={authMode?.auth_mode === "oidc" ? "teal" : "gray"}>
                      auth: {authMode?.auth_mode || "unknown"}
                    </Badge>
                    <Badge variant="light" color={authMode?.rbac_mode === "enforce" ? "orange" : "gray"}>
                      rbac: {authMode?.rbac_mode || "unknown"}
                    </Badge>
                    <Badge variant="light" color={authMode?.tenancy_mode === "enforce" ? "violet" : "gray"}>
                      tenancy: {authMode?.tenancy_mode || "unknown"}
                    </Badge>
                  </Group>
                </Group>
                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                  <PasswordInput
                    label="OIDC Bearer Token"
                    value={oidcToken}
                    onChange={(event) => setOidcToken(event.currentTarget.value)}
                    placeholder="Paste token only (without Bearer prefix)"
                  />
                  <TextInput
                    label="Session Token"
                    value={sessionToken}
                    onChange={(event) => setSessionToken(event.currentTarget.value)}
                    placeholder="syns_..."
                  />
                </SimpleGrid>
                <Group gap="xs" wrap="wrap">
                  <Button size="xs" variant="light" loading={authActionLoading} onClick={() => void createWebSessionFromOidc()}>
                    Create Session
                  </Button>
                  <Button size="xs" variant="light" loading={authActionLoading} onClick={() => void validateSession()}>
                    Validate Session
                  </Button>
                  <Button size="xs" color="red" variant="light" loading={authActionLoading} onClick={() => void revokeSession()}>
                    Revoke Session
                  </Button>
                </Group>
                <Text size="xs" c="dimmed">
                  {sessionSummary
                    ? `Session actor: ${sessionSummary.subject} (${(sessionSummary.roles || []).join(", ") || "no roles"})`
                    : "No active session loaded."}
                </Text>
              </Stack>
            </Paper>
          )}

          {effectiveUiMode === "advanced" && (
            <Paper mt="md" withBorder radius="lg" p="md" className="hotkey-panel">
              <Group justify="space-between" align="center" wrap="wrap">
                <Stack gap={2}>
                  <Text fw={700}>Workspace Mode</Text>
                  <Text size="xs" c="dimmed">
                    Advanced profile is enabled for this workspace.
                  </Text>
                </Stack>
                <Badge variant="light" color="orange">
                  advanced
                </Badge>
              </Group>
            </Paper>
          )}

          {effectiveUiMode === "advanced" && (
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
          )}
        </Paper>

        {effectiveUiMode === "advanced" ? (
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
              <Text className="eyebrow">Wiki Workspace</Text>
              <Title order={3}>Company Wiki, Written by Agents.</Title>
              <Text c="dimmed" size="sm">
                Review and publish trusted knowledge pages. Draft moderation and task tracking stay available as
                operational side flows when needed.
              </Text>
              <Group gap="xs" wrap="wrap">
                <Badge variant="light" color="teal">
                  Wiki
                </Badge>
                <Text size="xs" c="dimmed">
                  Draft moderation and tasks are available in Operations actions.
                </Text>
              </Group>
            </Stack>
          </Paper>
        )}

        {effectiveUiMode === "core" && (
          <Paper radius="xl" p="md" withBorder className="wiki-command-bar">
            <Group justify="space-between" align="flex-end" wrap="wrap">
              <Stack gap={2}>
                <Text className="eyebrow">Corporate Wiki Workspace</Text>
                <Text size="sm" c="dimmed">
                  Wiki is primary. Draft inbox and tasks are operational side flows.
                </Text>
              </Stack>
              <Group gap="xs" wrap="wrap">
                <Select
                  searchable
                  value={selectedPageSlug}
                  onChange={(value) => {
                    setCoreWorkspaceTab("wiki");
                    setSelectedPageSlug(value || null);
                    if (value) {
                      setSelectedSpaceKey(pageGroupKey(value));
                    }
                  }}
                  placeholder="Jump to wiki page"
                  w={320}
                  data={pageNodes.map((item) => ({
                    value: item.slug,
                    label: `${item.title || item.slug} (${item.open_count} open drafts)`,
                  }))}
                  clearable
                />
                <Button
                  variant={coreWorkspaceTab === "wiki" ? "filled" : "light"}
                  color="teal"
                  onClick={() => setCoreWorkspaceTab("wiki")}
                >
                  Open Wiki
                </Button>
                <Button
                  variant={coreWorkspaceTab === "drafts" || coreWorkspaceTab === "tasks" ? "filled" : "light"}
                  color={coreWorkspaceTab === "drafts" || coreWorkspaceTab === "tasks" ? "cyan" : "gray"}
                  onClick={() => setShowOperationsNav((value) => !value)}
                >
                  Operations ({openDraftCount})
                </Button>
              </Group>
            </Group>
          </Paper>
        )}

        {effectiveUiMode === "core" && showOperationsNav && (
          <Paper radius="xl" p="sm" withBorder className="operations-nav-card">
            <Group justify="space-between" align="center" wrap="wrap">
              <Text size="sm" c="dimmed">
                Operational flows for moderation and execution tracking.
              </Text>
              <Group gap="xs" wrap="wrap">
                <Button
                  size="compact-sm"
                  variant={coreWorkspaceTab === "drafts" ? "filled" : "light"}
                  color={coreWorkspaceTab === "drafts" ? "cyan" : "gray"}
                  onClick={() => setCoreWorkspaceTab("drafts")}
                >
                  Open Draft Inbox
                </Button>
                <Button
                  size="compact-sm"
                  variant={coreWorkspaceTab === "tasks" ? "filled" : "light"}
                  color={coreWorkspaceTab === "tasks" ? "orange" : "gray"}
                  onClick={() => setCoreWorkspaceTab("tasks")}
                >
                  Open Tasks
                </Button>
              </Group>
            </Group>
          </Paper>
        )}

        {showCoreTaskPanel && (
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
        )}

        {(effectiveUiMode === "advanced" || coreWorkspaceTab !== "tasks") && (
          <SimpleGrid cols={coreGridCols} spacing="lg" className="wiki-core-grid">
            {showCoreWikiPanel && (
              <Paper radius="xl" p="lg" className="wiki-tree-panel">
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
              <Select
                label="Page status"
                placeholder="All statuses"
                value={pageStatusFilter}
                onChange={(value) => setPageStatusFilter(value || null)}
                clearable
                data={[
                  { label: "Draft", value: "draft" },
                  { label: "Reviewed", value: "reviewed" },
                  { label: "Published", value: "published" },
                  { label: "Archived", value: "archived" },
                ]}
              />
              <TextInput
                label="Updated by"
                value={pageUpdatedByFilter}
                onChange={(event) => setPageUpdatedByFilter(event.currentTarget.value)}
                placeholder="ops_manager"
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
                <Button
                  size="xs"
                  variant={pageStatusFilter || pageUpdatedByFilter.trim() || openPagesOnly ? "light" : "filled"}
                  onClick={() => {
                    setPageStatusFilter(null);
                    setPageUpdatedByFilter("");
                    setOpenPagesOnly(false);
                  }}
                >
                  Reset index filters
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
                {pageStatusFilter && (
                  <Badge variant="light" color="grape">
                    status: {pageStatusFilter}
                  </Badge>
                )}
                {pageUpdatedByFilter.trim() && (
                  <Badge variant="light" color="cyan">
                    updated by: {pageUpdatedByFilter.trim()}
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
                          status: (value as "draft" | "reviewed" | "published" | null) ?? "published",
                        }))
                      }
                      data={[
                        { label: "published", value: "published" },
                        { label: "reviewed", value: "reviewed" },
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
                  {effectiveUiMode === "advanced" && (
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
                {(loadingPages || loadingDrafts) && (
                  <Paper withBorder p="md" radius="lg">
                    <Group gap="xs">
                      <Loader size="xs" />
                      <Text c="dimmed" size="sm">
                        syncing wiki tree…
                      </Text>
                    </Group>
                  </Paper>
                )}
                {wikiTreeNodes.length === 0 && !loadingPages && !loadingDrafts && (
                  <Paper withBorder p="md" radius="lg">
                    <Text c="dimmed">No pages in current scope.</Text>
                  </Paper>
                )}
                {wikiTreeNodes.map((node) => renderWikiTreeNode(node))}
              </Stack>
            </ScrollArea>
          </Paper>
            )}

          {showCoreWikiPreviewPanel && (
            <Paper radius="xl" p="lg" className="wiki-page-preview-panel">
              <Group justify="space-between" mb="sm">
                <Title order={3}>Wiki Page</Title>
                {selectedPageSlug ? (
                  <Badge size="lg" variant="light" color="teal">
                    {selectedPageTitle}
                  </Badge>
                ) : (
                  <Badge size="lg" variant="light" color="gray">
                    not selected
                  </Badge>
                )}
              </Group>
              {!selectedPageSlug && (
                <Stack gap="sm">
                  <Paper withBorder p="md" radius="md">
                    <Stack gap={6}>
                      <Text size="sm" fw={700}>
                        Wiki Home
                      </Text>
                      <Text size="sm" c="dimmed">
                        Select a page in Wiki Tree or jump from recent pages.
                      </Text>
                    </Stack>
                  </Paper>
                  <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" fw={700} mb={6}>
                        Spaces
                      </Text>
                      <Stack gap={4}>
                        {spaceNodes.slice(0, 6).map((space) => (
                          <Button
                            key={`wiki-home-space-${space.key}`}
                            size="compact-sm"
                            variant="subtle"
                            onClick={() => setSelectedSpaceKey(space.key)}
                          >
                            {space.title} ({space.page_count})
                          </Button>
                        ))}
                        {spaceNodes.length === 0 && (
                          <Text size="xs" c="dimmed">
                            No spaces available yet.
                          </Text>
                        )}
                      </Stack>
                    </Paper>
                    <Paper withBorder p="xs" radius="md">
                      <Text size="xs" fw={700} mb={6}>
                        Recent pages
                      </Text>
                      <Stack gap={4}>
                        {wikiHomeRecentPages.map((page) => (
                          <Button
                            key={`wiki-home-page-${page.slug}`}
                            size="compact-sm"
                            variant="light"
                            onClick={() => {
                              setSelectedPageSlug(page.slug);
                              setSelectedSpaceKey(pageGroupKey(page.slug));
                            }}
                          >
                            {page.title || page.slug}
                          </Button>
                        ))}
                        {wikiHomeRecentPages.length === 0 && (
                          <Text size="xs" c="dimmed">
                            No recent pages yet.
                          </Text>
                        )}
                      </Stack>
                    </Paper>
                  </SimpleGrid>
                </Stack>
              )}
              {selectedPageSlug && loadingPageDetail && (
                <Group py="md">
                  <Loader size="sm" />
                  <Text size="sm" c="dimmed">
                    Loading wiki page…
                  </Text>
                </Group>
              )}
              {selectedPageSlug && !loadingPageDetail && !selectedPageDetail && (
                <Paper withBorder p="md" radius="md">
                  <Text size="sm" c="dimmed">
                    Page content is not available yet for this selection.
                  </Text>
                </Paper>
              )}
              {selectedPageSlug && selectedPageDetail && (
                <Stack gap="sm">
                  <Paper withBorder p="xs" radius="md" className="wiki-page-header-card">
                    <Stack gap={6}>
                      <Group justify="space-between" align="flex-start" wrap="wrap">
                        <Stack gap={2}>
                          <Breadcrumbs separator="›">
                            {wikiPageBreadcrumb.map((crumb, index) => (
                              <Text
                                key={`wiki-page-breadcrumb-${index}-${crumb.slug || "root"}`}
                                size="xs"
                                c={crumb.slug ? "dimmed" : "gray"}
                                style={crumb.slug ? { cursor: "pointer" } : undefined}
                                onClick={() => {
                                  if (!crumb.slug) {
                                    setSelectedPageSlug(null);
                                    return;
                                  }
                                  setSelectedSpaceKey(pageGroupKey(crumb.slug));
                                  setSelectedPageSlug(crumb.slug);
                                }}
                              >
                                {crumb.label}
                              </Text>
                            ))}
                          </Breadcrumbs>
                          <Text size="xs" fw={700}>
                            {selectedPageDetail.page.title || selectedPageDetail.page.slug}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {selectedSpaceTitle} / {selectedPageDetail.page.slug}
                          </Text>
                        </Stack>
                        <Group gap={6} wrap="wrap">
                          <Badge size="xs" variant="light" color="indigo">
                            status {selectedPageDetail.page.status}
                          </Badge>
                          {selectedPageDetail.page.page_type ? (
                            <Badge size="xs" variant="light" color="grape">
                              type {selectedPageDetail.page.page_type}
                            </Badge>
                          ) : null}
                          <Badge size="xs" variant="light" color="blue">
                            v{latestPageVersion?.version ?? selectedPageDetail.page.current_version ?? "—"}
                          </Badge>
                        </Group>
                      </Group>
                      <Group gap={6} wrap="wrap">
                        <Badge size="xs" variant="light" color="teal">
                          updated {fmtDate(latestPageVersion?.created_at)}
                        </Badge>
                        {latestPageVersion?.created_by ? (
                          <Badge size="xs" variant="light" color="gray">
                            by {latestPageVersion.created_by}
                          </Badge>
                        ) : null}
                        <Badge size="xs" variant="light" color={pageRevisionDelta.changed > 0 ? "orange" : "gray"}>
                          delta +{pageRevisionDelta.addedTokens} / -{pageRevisionDelta.removedTokens}
                        </Badge>
                      </Group>
                      <Group gap="xs" wrap="wrap">
                        <Button
                          size="compact-xs"
                          variant="light"
                          onClick={() => {
                            if (!selectedPageSlug) return;
                            void loadPageDetail(selectedPageSlug);
                            void loadPageHistory(selectedPageSlug);
                            void loadPageAliases(selectedPageSlug);
                            void loadPageComments(selectedPageSlug);
                            void loadPageWatchers(selectedPageSlug);
                            void loadPageReviewAssignments(selectedPageSlug);
                          }}
                        >
                          Refresh Page
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="cyan"
                          onClick={() => setCoreWorkspaceTab("drafts")}
                        >
                          Open Page Drafts ({selectedPageOpenDrafts.length})
                        </Button>
                        {!pageEditMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="indigo"
                            onClick={() => {
                              setPageMoveMode(false);
                              setPageEditMode(true);
                            }}
                          >
                            Edit Page
                          </Button>
                        )}
                        {!pageMoveMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="violet"
                            onClick={() => {
                              setPageEditMode(false);
                              setPageMoveMode(true);
                            }}
                          >
                            Move/Rename
                          </Button>
                        )}
                        {selectedPageDetail.page.status !== "archived" && !pageEditMode && !pageMoveMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="red"
                            loading={movingPage}
                            onClick={() => void transitionWikiPageStatus("archive")}
                          >
                            Archive
                          </Button>
                        )}
                        {selectedPageDetail.page.status === "archived" && !pageEditMode && !pageMoveMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="teal"
                            loading={movingPage}
                            onClick={() => void transitionWikiPageStatus("restore")}
                          >
                            Restore
                          </Button>
                        )}
                        {pageEditMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="gray"
                            onClick={() => setPageEditMode(false)}
                          >
                            Cancel Edit
                          </Button>
                        )}
                        {pageEditMode && (
                          <Button
                            size="compact-xs"
                            color="teal"
                            loading={savingPageEdit}
                            onClick={() => void saveWikiPageEdit()}
                          >
                            Save Page
                          </Button>
                        )}
                        {pageMoveMode && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="gray"
                            onClick={() => setPageMoveMode(false)}
                          >
                            Cancel Move
                          </Button>
                        )}
                        {pageMoveMode && (
                          <Button
                            size="compact-xs"
                            color="violet"
                            loading={movingPage}
                            onClick={() => void moveWikiPage()}
                          >
                            Apply Move
                          </Button>
                        )}
                      </Group>
                    </Stack>
                  </Paper>
                  {pageMoveMode ? (
                    <Paper withBorder p="sm" radius="md" className="wiki-page-edit-card">
                      <Stack gap="sm">
                        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                          <TextInput
                            label="Parent path"
                            value={pageMoveParentPath}
                            onChange={(event) => setPageMoveParentPath(event.currentTarget.value)}
                            placeholder="operations/locations"
                            description="Leave empty to move page to space root."
                          />
                          <TextInput
                            label="Slug leaf"
                            value={pageMoveSlugLeaf}
                            onChange={(event) => setPageMoveSlugLeaf(event.currentTarget.value)}
                            placeholder="bc-omega-access-policy"
                            description="Final segment for target page slug."
                          />
                        </SimpleGrid>
                        <TextInput
                          label="Page title"
                          value={pageMoveTitle}
                          onChange={(event) => setPageMoveTitle(event.currentTarget.value)}
                          placeholder="BC Omega Access Policy"
                        />
                        <TextInput
                          label="Change summary"
                          value={pageMoveSummary}
                          onChange={(event) => setPageMoveSummary(event.currentTarget.value)}
                          placeholder="Moved under operations/locations and renamed page."
                        />
                        <Checkbox
                          label="Move descendants (pages under current slug prefix)"
                          checked={pageMoveIncludeDescendants}
                          onChange={(event) => setPageMoveIncludeDescendants(event.currentTarget.checked)}
                        />
                        <Group gap="xs">
                          <Badge size="xs" variant="light" color="gray">
                            current {selectedPageDetail.page.slug}
                          </Badge>
                          <Badge size="xs" variant="light" color="violet">
                            target {pageMovePreviewSlug}
                          </Badge>
                        </Group>
                      </Stack>
                    </Paper>
                  ) : pageEditMode ? (
                    <Paper withBorder p="sm" radius="md" className="wiki-page-edit-card">
                      <Stack gap="sm">
                        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                          <TextInput
                            label="Page title"
                            value={pageEditTitle}
                            onChange={(event) => setPageEditTitle(event.currentTarget.value)}
                            placeholder="Operations / BC Omega Access"
                          />
                          <Select
                            label="Page status"
                            value={pageEditStatus}
                            onChange={(value) => {
                              if (value === "draft" || value === "reviewed" || value === "published" || value === "archived") {
                                setPageEditStatus(value);
                              }
                            }}
                            data={[
                              { value: "published", label: "published" },
                              { value: "reviewed", label: "reviewed" },
                              { value: "draft", label: "draft" },
                              { value: "archived", label: "archived" },
                            ]}
                            allowDeselect={false}
                          />
                        </SimpleGrid>
                        <TextInput
                          label="Change summary"
                          value={pageEditSummary}
                          onChange={(event) => setPageEditSummary(event.currentTarget.value)}
                          placeholder="Updated access policy and pickup constraints."
                        />
                        <Paper withBorder p="xs" radius="md">
                          <Stack gap={6}>
                            <Text size="xs" fw={700}>
                              Attach file / media
                            </Text>
                            <Group gap={8} align="center" wrap="wrap">
                              <input
                                type="file"
                                onChange={(event) => {
                                  const file = event.currentTarget.files?.[0] ?? null;
                                  setPageAssetFile(file);
                                }}
                              />
                              <Button
                                size="compact-xs"
                                variant="light"
                                color="indigo"
                                loading={uploadingPageAsset}
                                disabled={!pageAssetFile}
                                onClick={() => void uploadPageAsset()}
                              >
                                Upload + insert snippet
                              </Button>
                            </Group>
                            <Text size="xs" c="dimmed">
                              Allowed common extensions. Uploaded file link will be inserted into markdown automatically.
                            </Text>
                          </Stack>
                        </Paper>
                        <Textarea
                          label="Page markdown"
                          value={pageEditMarkdown}
                          onChange={(event) => setPageEditMarkdown(event.currentTarget.value)}
                          minRows={18}
                          autosize
                        />
                      </Stack>
                    </Paper>
                  ) : (
                    <>
                      <Group gap="xs" wrap="wrap">
                        <Badge size="xs" variant="light" color="indigo">
                          slug {selectedPageDetail.page.slug}
                        </Badge>
                        <Badge size="xs" variant="light" color="grape">
                          sections {selectedPageDetail.sections.length}
                        </Badge>
                        <Badge size="xs" variant="light" color="blue">
                          statements {selectedPageDetail.statements.length}
                        </Badge>
                      </Group>
                      <Suspense
                        fallback={
                          <Paper withBorder p="md" radius="md">
                            <Group py="sm">
                              <Loader size="sm" />
                              <Text size="sm" c="dimmed">
                                Rendering page preview…
                              </Text>
                            </Group>
                          </Paper>
                        }
                      >
                        <LazyWikiPageCanvas
                          title={selectedPageDetail.page.title || selectedPageDetail.page.slug || "Untitled page"}
                          slug={selectedPageDetail.page.slug}
                          markdown={wikiPreviewMarkdown}
                          apiBaseUrl={apiUrl}
                          readonly
                          onApplyEditedStatement={() => {}}
                        />
                      </Suspense>
                    </>
                  )}
                </Stack>
              )}
            </Paper>
          )}

          {showCoreWikiContextPanel && (
            <Paper radius="xl" p="lg" className="wiki-context-panel">
              <Group justify="space-between" mb="sm">
                <Title order={3}>Page Context</Title>
                {selectedPageSlug ? (
                  <Badge variant="light" color="indigo">
                    {selectedPageSlug}
                  </Badge>
                ) : null}
              </Group>
              {!selectedPageSlug && (
                <Text size="sm" c="dimmed">
                  Select a page to view sections, revision timeline, and open draft context.
                </Text>
              )}
              {selectedPageSlug && (
                <Stack gap="sm">
                  <Paper withBorder p="xs" radius="md">
                    <Text size="xs" fw={700} mb={6}>
                      Sections
                    </Text>
                    {(selectedPageDetail?.sections ?? []).length === 0 ? (
                      <Text size="xs" c="dimmed">
                        No sections available.
                      </Text>
                    ) : (
                      <Stack gap={4}>
                        {(selectedPageDetail?.sections ?? []).slice(0, 8).map((section) => (
                          <Text key={`ctx-section-${section.section_key}`} size="xs" c="dimmed">
                            {section.heading} ({section.statement_count})
                          </Text>
                        ))}
                      </Stack>
                    )}
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Text size="xs" fw={700} mb={6}>
                      Latest revisions
                    </Text>
                    {(pageHistory?.versions ?? []).length === 0 ? (
                      <Text size="xs" c="dimmed">
                        Revision history is not available.
                      </Text>
                    ) : (
                      <Stack gap={4}>
                        {(pageHistory?.versions ?? []).slice(0, 5).map((version) => (
                          <Text key={`ctx-version-${version.version}`} size="xs" c="dimmed">
                            v{version.version} • {fmtDate(version.created_at)}
                          </Text>
                        ))}
                      </Stack>
                    )}
                    {(pageHistory?.versions ?? []).length > 1 && (
                      <Group gap={6} mt={8} wrap="wrap">
                        <Badge size="xs" variant="light" color={pageRevisionDelta.changed > 0 ? "orange" : "gray"}>
                          changes {pageRevisionDelta.changed}
                        </Badge>
                        <Badge size="xs" variant="light" color="teal">
                          +{pageRevisionDelta.addedTokens}
                        </Badge>
                        <Badge size="xs" variant="light" color="red">
                          -{pageRevisionDelta.removedTokens}
                        </Badge>
                      </Group>
                    )}
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Open drafts on this page
                      </Text>
                      <Badge size="xs" variant="light" color="cyan">
                        {selectedPageOpenDrafts.length}
                      </Badge>
                    </Group>
                    {selectedPageOpenDrafts.length === 0 ? (
                      <Text size="xs" c="dimmed">
                        No open drafts for this page.
                      </Text>
                    ) : (
                      <Stack gap={6}>
                        {selectedPageOpenDrafts.map((draft) => (
                          <Button
                            key={`ctx-draft-${draft.id}`}
                            size="compact-sm"
                            variant="light"
                            color="cyan"
                            onClick={() => {
                              setCoreWorkspaceTab("drafts");
                              setSelectedDraftId(draft.id);
                            }}
                          >
                            {draft.page.title || draft.section_key || draft.id.slice(0, 8)} • conf {draft.confidence.toFixed(2)}
                          </Button>
                        ))}
                      </Stack>
                    )}
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Aliases
                      </Text>
                      <Badge size="xs" variant="light" color="indigo">
                        {pageAliases.length}
                      </Badge>
                    </Group>
                    <Stack gap={6}>
                      <Group gap={6} wrap="wrap">
                        <TextInput
                          size="xs"
                          placeholder="operations/old-slug"
                          value={newPageAlias}
                          onChange={(event) => setNewPageAlias(event.currentTarget.value)}
                          style={{ flex: 1, minWidth: 180 }}
                        />
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="indigo"
                          loading={savingPageAlias}
                          onClick={() => void createPageAlias()}
                        >
                          Add alias
                        </Button>
                      </Group>
                      {loadingPageAliases ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading aliases…
                          </Text>
                        </Group>
                      ) : pageAliases.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No aliases configured.
                        </Text>
                      ) : (
                        <Stack gap={4}>
                          {pageAliases.map((alias) => (
                            <Group key={`page-alias-${alias.alias_text}`} justify="space-between" align="center" wrap="nowrap">
                              <Text size="xs" c="dimmed">
                                {alias.alias_text}
                              </Text>
                              <ActionIcon
                                size="sm"
                                variant="subtle"
                                color="red"
                                loading={savingPageAlias}
                                onClick={() => void deletePageAlias(alias.alias_text)}
                                aria-label="Delete alias"
                              >
                                <IconTrash size={12} />
                              </ActionIcon>
                            </Group>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Governance
                      </Text>
                      <Badge size="xs" variant="light" color="violet">
                        {pageGroupKey(selectedPageSlug)}
                      </Badge>
                    </Group>
                    <Stack gap={8}>
                      <SimpleGrid cols={{ base: 1, md: 2 }} spacing={6}>
                        <Select
                          size="xs"
                          label="Write mode"
                          value={spaceWriteMode}
                          onChange={(value) => {
                            if (value === "open" || value === "owners_only") {
                              setSpaceWriteMode(value);
                            }
                          }}
                          data={[
                            { value: "open", label: "open" },
                            { value: "owners_only", label: "owners_only" },
                          ]}
                          allowDeselect={false}
                          disabled={loadingSpacePolicy}
                        />
                        <Select
                          size="xs"
                          label="Comment mode"
                          value={spaceCommentMode}
                          onChange={(value) => {
                            if (value === "open" || value === "owners_only") {
                              setSpaceCommentMode(value);
                            }
                          }}
                          data={[
                            { value: "open", label: "open" },
                            { value: "owners_only", label: "owners_only" },
                          ]}
                          allowDeselect={false}
                          disabled={loadingSpacePolicy}
                        />
                      </SimpleGrid>
                      <Checkbox
                        size="xs"
                        checked={spaceReviewRequired}
                        onChange={(event) => setSpaceReviewRequired(event.currentTarget.checked)}
                        label="Require review assignment before publish"
                        disabled={loadingSpacePolicy}
                      />
                      <Group justify="flex-end">
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="violet"
                          loading={savingSpacePolicy}
                          onClick={() => void saveSpacePolicy()}
                        >
                          Save policy
                        </Button>
                      </Group>
                      {spacePolicy && (
                        <Text size="xs" c="dimmed">
                          policy source: {spacePolicy.exists ? "configured" : "default open"}
                        </Text>
                      )}

                      <Divider />

                      <Text size="xs" fw={700}>
                        Space owners
                      </Text>
                      <Group gap={6} wrap="wrap">
                        <TextInput
                          size="xs"
                          placeholder="owner_id"
                          value={spaceOwnerInput}
                          onChange={(event) => setSpaceOwnerInput(event.currentTarget.value)}
                          style={{ flex: 1, minWidth: 120 }}
                        />
                        <TextInput
                          size="xs"
                          placeholder="role"
                          value={spaceOwnerRoleInput}
                          onChange={(event) => setSpaceOwnerRoleInput(event.currentTarget.value)}
                          style={{ width: 100 }}
                        />
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="violet"
                          loading={savingSpaceOwner}
                          onClick={() => void upsertSpaceOwner(spaceOwnerInput, true)}
                        >
                          Add
                        </Button>
                      </Group>
                      {loadingSpaceOwners ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading space owners…
                          </Text>
                        </Group>
                      ) : spaceOwners.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No space owners configured.
                        </Text>
                      ) : (
                        <Stack gap={4}>
                          {spaceOwners.map((owner) => (
                            <Group key={`space-owner-${owner.owner}`} justify="space-between" align="center" wrap="nowrap">
                              <Text size="xs" c="dimmed">
                                {owner.owner} ({owner.role})
                              </Text>
                              <ActionIcon
                                size="sm"
                                variant="subtle"
                                color="red"
                                loading={savingSpaceOwner}
                                onClick={() => void upsertSpaceOwner(owner.owner, false)}
                                aria-label="Remove space owner"
                              >
                                <IconTrash size={12} />
                              </ActionIcon>
                            </Group>
                          ))}
                        </Stack>
                      )}

                      <Divider />

                      <Text size="xs" fw={700}>
                        Page owners
                      </Text>
                      <Group gap={6} wrap="wrap">
                        <TextInput
                          size="xs"
                          placeholder="owner_id"
                          value={pageOwnerInput}
                          onChange={(event) => setPageOwnerInput(event.currentTarget.value)}
                          style={{ flex: 1, minWidth: 120 }}
                        />
                        <TextInput
                          size="xs"
                          placeholder="role"
                          value={pageOwnerRoleInput}
                          onChange={(event) => setPageOwnerRoleInput(event.currentTarget.value)}
                          style={{ width: 100 }}
                        />
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="violet"
                          loading={savingPageOwner}
                          onClick={() => void upsertPageOwner(pageOwnerInput, true)}
                        >
                          Add
                        </Button>
                      </Group>
                      {loadingPageOwners ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading page owners…
                          </Text>
                        </Group>
                      ) : pageOwners.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No page owners configured.
                        </Text>
                      ) : (
                        <Stack gap={4}>
                          {pageOwners.map((owner) => (
                            <Group key={`page-owner-${owner.owner}`} justify="space-between" align="center" wrap="nowrap">
                              <Text size="xs" c="dimmed">
                                {owner.owner} ({owner.role})
                              </Text>
                              <ActionIcon
                                size="sm"
                                variant="subtle"
                                color="red"
                                loading={savingPageOwner}
                                onClick={() => void upsertPageOwner(owner.owner, false)}
                                aria-label="Remove page owner"
                              >
                                <IconTrash size={12} />
                              </ActionIcon>
                            </Group>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Watchers
                      </Text>
                      <Badge size="xs" variant="light" color="teal">
                        {pageWatchers.length}
                      </Badge>
                    </Group>
                    <Stack gap={6}>
                      <Group gap={6} wrap="wrap">
                        <Button
                          size="compact-xs"
                          variant={currentReviewerWatchingPage ? "light" : "filled"}
                          color={currentReviewerWatchingPage ? "gray" : "teal"}
                          loading={savingPageWatcher}
                          onClick={() => void upsertPageWatcher(reviewer.trim(), !currentReviewerWatchingPage)}
                        >
                          {currentReviewerWatchingPage ? "Unwatch me" : "Watch me"}
                        </Button>
                        <TextInput
                          size="xs"
                          placeholder="teammate_id"
                          value={watcherInput}
                          onChange={(event) => setWatcherInput(event.currentTarget.value)}
                          style={{ flex: 1, minWidth: 140 }}
                        />
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="teal"
                          loading={savingPageWatcher}
                          onClick={() => void upsertPageWatcher(watcherInput, true)}
                        >
                          Add
                        </Button>
                      </Group>
                      {loadingPageWatchers ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading watchers…
                          </Text>
                        </Group>
                      ) : pageWatchers.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No watchers.
                        </Text>
                      ) : (
                        <Stack gap={4}>
                          {pageWatchers.map((item) => (
                            <Group key={`page-watcher-${item.watcher}`} justify="space-between" align="center" wrap="nowrap">
                              <Text size="xs" c="dimmed">
                                {item.watcher}
                              </Text>
                              <ActionIcon
                                size="sm"
                                variant="subtle"
                                color="red"
                                loading={savingPageWatcher}
                                onClick={() => void upsertPageWatcher(item.watcher, false)}
                                aria-label="Remove watcher"
                              >
                                <IconTrash size={12} />
                              </ActionIcon>
                            </Group>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Comments
                      </Text>
                      <Badge size="xs" variant="light" color="grape">
                        {pageComments.length}
                      </Badge>
                    </Group>
                    <Stack gap={6}>
                      <Textarea
                        size="xs"
                        minRows={2}
                        autosize
                        placeholder="Add comment for reviewers and operators... Use @username for mention."
                        value={newPageComment}
                        onChange={(event) => setNewPageComment(event.currentTarget.value)}
                      />
                      <Text size="xs" c="dimmed">
                        Mentions (`@username`) notify teammates and page watchers.
                      </Text>
                      <Group justify="flex-end">
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="grape"
                          loading={savingPageComment}
                          onClick={() => void createPageComment()}
                        >
                          Add comment
                        </Button>
                      </Group>
                      {loadingPageComments ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading comments…
                          </Text>
                        </Group>
                      ) : pageComments.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No comments yet.
                        </Text>
                      ) : (
                        <Stack gap={6}>
                          {pageComments.map((comment) => (
                            <Paper key={`page-comment-${comment.id}`} withBorder p="xs" radius="md">
                              <Stack gap={4}>
                                <Group justify="space-between" align="center" wrap="nowrap">
                                  <Text size="xs" fw={700}>
                                    {comment.author}
                                  </Text>
                                  <Group gap={6} wrap="nowrap">
                                    <Text size="xs" c="dimmed">
                                      {fmtDate(comment.created_at)}
                                    </Text>
                                    <ActionIcon
                                      size="sm"
                                      variant="subtle"
                                      color="red"
                                      loading={savingPageComment}
                                      onClick={() => void deletePageComment(comment.id)}
                                      aria-label="Delete comment"
                                    >
                                      <IconTrash size={12} />
                                    </ActionIcon>
                                  </Group>
                                </Group>
                                <Text size="xs" c="dimmed">
                                  {comment.body}
                                </Text>
                              </Stack>
                            </Paper>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Attachments
                      </Text>
                      <Badge size="xs" variant="light" color="indigo">
                        {pageUploads.length}
                      </Badge>
                    </Group>
                    {loadingPageUploads ? (
                      <Group gap={6}>
                        <Loader size="xs" />
                        <Text size="xs" c="dimmed">
                          loading uploads…
                        </Text>
                      </Group>
                    ) : pageUploads.length === 0 ? (
                      <Text size="xs" c="dimmed">
                        No uploads for this page yet.
                      </Text>
                    ) : (
                      <Stack gap={6}>
                        {pageUploads.slice(0, 12).map((upload) => {
                          const resolvedUrl = resolveWikiAssetUrl(
                            apiUrl,
                            upload.content_url_absolute || upload.content_url,
                          );
                          return (
                            <Paper key={`page-upload-${upload.id}`} withBorder p="xs" radius="md">
                              <Group justify="space-between" align="center" wrap="nowrap">
                                <Stack gap={2} style={{ flex: 1 }}>
                                  <Text size="xs" fw={700} lineClamp={1}>
                                    {upload.filename}
                                  </Text>
                                  <Text size="xs" c="dimmed">
                                    {upload.content_type || "application/octet-stream"} •{" "}
                                    {(upload.size_bytes / 1024).toFixed(1)} KB • {fmtDate(upload.created_at)}
                                  </Text>
                                </Stack>
                                <Button
                                  component="a"
                                  href={resolvedUrl || undefined}
                                  target="_blank"
                                  rel="noreferrer"
                                  size="compact-xs"
                                  variant="light"
                                  color="indigo"
                                >
                                  Open
                                </Button>
                              </Group>
                            </Paper>
                          );
                        })}
                      </Stack>
                    )}
                  </Paper>
                  <Paper withBorder p="xs" radius="md">
                    <Group justify="space-between" align="center" mb={6}>
                      <Text size="xs" fw={700}>
                        Review assignments
                      </Text>
                      <Badge size="xs" variant="light" color="orange">
                        {pageReviewAssignments.filter((item) => item.status === "open").length}
                      </Badge>
                    </Group>
                    <Stack gap={6}>
                      <SimpleGrid cols={{ base: 1, md: 2 }} spacing={6}>
                        <TextInput
                          size="xs"
                          placeholder="assignee_id"
                          value={assignmentAssigneeInput}
                          onChange={(event) => setAssignmentAssigneeInput(event.currentTarget.value)}
                        />
                        <TextInput
                          size="xs"
                          placeholder="Note (optional)"
                          value={assignmentNoteInput}
                          onChange={(event) => setAssignmentNoteInput(event.currentTarget.value)}
                        />
                      </SimpleGrid>
                      <Group justify="flex-end">
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="orange"
                          loading={savingPageAssignment}
                          onClick={() => void createPageReviewAssignment()}
                        >
                          Assign reviewer
                        </Button>
                      </Group>
                      {loadingPageReviewAssignments ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading assignments…
                          </Text>
                        </Group>
                      ) : pageReviewAssignments.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No review assignments yet.
                        </Text>
                      ) : (
                        <Stack gap={6}>
                          {pageReviewAssignments.slice(0, 12).map((assignment) => (
                            <Paper key={`assignment-${assignment.id}`} withBorder p="xs" radius="md">
                              <Group justify="space-between" align="center" wrap="nowrap">
                                <Stack gap={2}>
                                  <Text size="xs" fw={700}>
                                    {assignment.assignee}
                                  </Text>
                                  <Text size="xs" c="dimmed">
                                    {assignment.status} • {assignment.role} • {fmtDate(assignment.created_at)}
                                  </Text>
                                  {assignment.note ? (
                                    <Text size="xs" c="dimmed">
                                      {assignment.note}
                                    </Text>
                                  ) : null}
                                </Stack>
                                {assignment.status === "open" ? (
                                  <Button
                                    size="compact-xs"
                                    variant="subtle"
                                    color="teal"
                                    loading={savingPageAssignment}
                                    onClick={() => void resolvePageReviewAssignment(assignment.id)}
                                  >
                                    Resolve
                                  </Button>
                                ) : (
                                  <Badge size="xs" variant="light" color="gray">
                                    resolved
                                  </Badge>
                                )}
                              </Group>
                            </Paper>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                </Stack>
              )}
            </Paper>
          )}

          {showCoreDraftPanels && (
            <Paper radius="xl" p="lg" className="draft-inbox-panel">
            <Group justify="space-between" mb="sm">
              <Title order={3}>Draft Inbox</Title>
              <Group gap="xs" wrap="wrap">
                <Badge size="lg" color="teal" variant="light">
                  {visibleDrafts.length}/{scopedDrafts.length}
                </Badge>
                {!showExpertModerationControls && (
                  <Button
                    size="compact-xs"
                    variant="light"
                    onClick={() => setShowDraftOperationsTools((value) => !value)}
                  >
                    {showDraftOperationsTools ? "Hide operations" : "Open operations"}
                  </Button>
                )}
              </Group>
            </Group>
            {(showExpertModerationControls || showDraftOperationsTools) && (
              <>
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
            {!showExpertModerationControls && (
              <Paper withBorder p="xs" radius="md" mb="sm" className="bootstrap-migration-card">
                <Group justify="space-between" align="center" wrap="wrap">
                  <Stack gap={2}>
                    <Text size="sm" fw={700}>
                      Migration Mode
                    </Text>
                    <Text size="xs" c="dimmed">
                      Enable only for initial trusted-source adoption batches.
                    </Text>
                  </Stack>
                  <Button
                    size="compact-xs"
                    variant={showMigrationMode ? "filled" : "light"}
                    color={showMigrationMode ? "orange" : "gray"}
                    onClick={() => setShowMigrationMode((value) => !value)}
                  >
                    {showMigrationMode ? "Hide migration tools" : "Open migration tools"}
                  </Button>
                </Group>
              </Paper>
            )}
            {(showExpertModerationControls || showMigrationMode) && (
            <Paper withBorder p="xs" radius="md" mb="sm" className="bootstrap-migration-card">
              <Stack gap={8}>
                <Group justify="space-between" align="center" wrap="wrap">
                  <Group gap="xs" wrap="wrap">
                    <Text size="sm" fw={700}>
                      Bootstrap Migration
                    </Text>
                    <Badge variant="light" color="indigo">
                      trusted source flow
                    </Badge>
                  </Group>
                  <Button
                    size="compact-xs"
                    variant="light"
                    onClick={() => setShowBootstrapTools((value) => !value)}
                  >
                    {showBootstrapTools ? "Hide tools" : "Open tools"}
                  </Button>
                </Group>
                <Text size="xs" c="dimmed">
                  Use this after legacy import to approve high-confidence drafts in phased batches.
                </Text>
                {showBootstrapTools && (
                  <>
                    <TextInput
                      label="Trusted sources (csv)"
                      value={bootstrapTrustedSources}
                      onChange={(event) => setBootstrapTrustedSources(event.currentTarget.value)}
                      placeholder="legacy_import,postgres_sql"
                    />
                    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xs">
                      <TextInput
                        label="Min confidence"
                        value={bootstrapMinConfidence}
                        onChange={(event) => setBootstrapMinConfidence(event.currentTarget.value)}
                        placeholder="0.85"
                      />
                      <TextInput
                        label="Batch limit"
                        value={bootstrapLimit}
                        onChange={(event) => setBootstrapLimit(event.currentTarget.value)}
                        placeholder="50"
                      />
                      <TextInput
                        label="Preview sample"
                        value={bootstrapSampleSize}
                        onChange={(event) => setBootstrapSampleSize(event.currentTarget.value)}
                        placeholder="15"
                      />
                    </SimpleGrid>
                    <Group gap={6} wrap="wrap">
                      <Text size="xs" c="dimmed">
                        Phased rollout:
                      </Text>
                      {["25", "50", "200"].map((preset) => (
                        <Button
                          key={`bootstrap-limit-${preset}`}
                          size="compact-xs"
                          variant={bootstrapLimit === preset ? "filled" : "light"}
                          onClick={() => setBootstrapLimit(preset)}
                        >
                          {preset}
                        </Button>
                      ))}
                    </Group>
                    <Checkbox
                      label="Require conflict-free drafts"
                      checked={bootstrapRequireConflictFree}
                      onChange={(event) => setBootstrapRequireConflictFree(event.currentTarget.checked)}
                    />
                    <Group gap="xs" wrap="wrap">
                      <Button
                        size="xs"
                        variant="light"
                        color="indigo"
                        loading={bootstrapLoading}
                        onClick={() => void runBootstrapApprove(true)}
                      >
                        Preview Candidates
                      </Button>
                      <Button
                        size="xs"
                        color="teal"
                        disabled={!bootstrapCanApply && !bootstrapLoading}
                        loading={bootstrapLoading}
                        onClick={() => void runBootstrapApprove(false)}
                      >
                        Approve Trusted Batch
                      </Button>
                    </Group>
                    {!bootstrapCanApply && (
                      <Text size="xs" c="dimmed">
                        Preview with current settings first. Apply is capped to 200 drafts/run and requires trusted sources.
                      </Text>
                    )}
                  </>
                )}
                {bootstrapResult && (
                  <Paper withBorder p="xs" radius="md">
                    <Stack gap={6}>
                      <Group gap={6} wrap="wrap">
                        <Badge size="xs" variant="light" color={bootstrapResult.dry_run ? "indigo" : "teal"}>
                          {bootstrapResult.dry_run ? "dry-run" : "applied"}
                        </Badge>
                        <Badge size="xs" variant="light" color="blue">
                          candidates {bootstrapResult.summary.candidates}
                        </Badge>
                        {typeof bootstrapResult.summary.approved === "number" && (
                          <Badge size="xs" variant="light" color="teal">
                            approved {bootstrapResult.summary.approved}
                          </Badge>
                        )}
                        {typeof bootstrapResult.summary.failed === "number" && (
                          <Badge size="xs" variant="light" color={bootstrapResult.summary.failed > 0 ? "orange" : "gray"}>
                            failed {bootstrapResult.summary.failed}
                          </Badge>
                        )}
                      </Group>
                      {bootstrapResult.dry_run && (bootstrapResult.sample ?? []).length > 0 && (
                        <Stack gap={4}>
                          {(bootstrapResult.sample ?? []).slice(0, 5).map((item) => (
                            <Text key={`bootstrap-sample-${item.draft_id}`} size="xs" c="dimmed">
                              {item.draft_id.slice(0, 8)} • {item.decision} • conf {Number(item.confidence).toFixed(2)}
                            </Text>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                )}
              </Stack>
            </Paper>
            )}
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
                {showExpertModerationControls && (
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
                )}
                {showExpertModerationControls && (
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
                )}
              </Stack>
            </Paper>
              </>
            )}
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
          )}

          {showCoreDraftPanels && (
            <Paper radius="xl" p="lg" className="draft-detail-panel">
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
                        apiBaseUrl={apiUrl}
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
          )}
          </SimpleGrid>
        )}

        {(effectiveUiMode === "advanced" || coreWorkspaceTab === "drafts") && (
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
        )}
      </Stack>
    </Box>
  );
}
