import {
  Alert,
  ActionIcon,
  Badge,
  Box,
  Button,
  Checkbox,
  Divider,
  Drawer,
  Group,
  Kbd,
  Loader,
  Menu,
  Modal,
  PasswordInput,
  Paper,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
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
  IconAlertTriangle,
  IconBell,
  IconBookmark,
  IconBookmarkFilled,
  IconChevronDown,
  IconChevronUp,
  IconCloudCog,
  IconDots,
  IconEditCircle,
  IconKeyboard,
  IconRefresh,
  IconSearch,
} from "@tabler/icons-react";
import { diffLines } from "diff";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import CoreDraftTab from "./components/core/CoreDraftTab";
import CoreWorkspaceLeftRail from "./components/core/CoreWorkspaceLeftRail";
import CoreWikiMain from "./components/core/CoreWikiMain";
import CoreWikiRightRail from "./components/core/CoreWikiRightRail";
import CoreWorkspaceTopBar from "./components/core/CoreWorkspaceTopBar";

type DraftStatus = "pending_review" | "blocked_conflict" | "approved" | "rejected";
type PublishMode = "human_required" | "conditional" | "auto_publish";
type DraftRecommendationFilter = "all" | "approve_first" | "review_with_context" | "needs_human_caution" | "needs_more_bundle_evidence";

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
    page_type?: string | null;
  };
  claim?: {
    category: string | null;
    entity_key: string | null;
    text?: string | null;
  };
  gatekeeper?: {
    tier: string | null;
    assertion_class?: string | null;
    compiler_v2?: {
      knowledge_dimensions?: string[];
      knowledge_like_score?: number | null;
      suggested_page_type?: string | null;
      bundle_key?: string | null;
      bundle_support?: number;
      promotion_ready_from_bundle?: boolean;
    };
  };
  bundle?: {
    bundle_key: string;
    bundle_type: string;
    suggested_page_type: string | null;
    entity_key: string | null;
    bundle_status: string;
    support_count: number;
    source_diversity: number;
    evidence_count: number;
    quality_score: number;
    knowledge_taxonomy_class?: string | null;
    normalized_target_type?: string | null;
    sample_claims?: Array<{ claim_text?: string; category?: string }>;
  } | null;
  bundle_priority?: {
    score: number;
    recommendation: string;
    reason: string;
  };
  evidence?: {
    source_systems?: string[];
    connectors?: string[];
    source_types?: string[];
  };
  has_open_conflict?: boolean;
  risk?: {
    level?: string;
  };
};

type DraftQueueSummary = {
  drafts_total: number;
  recommendations: Record<string, number>;
  bundle_statuses: Record<string, number>;
  suggested_page_types: Record<string, number>;
  ready_bundle_support_total: number;
  top_recommended: Array<{
    draft_id: string;
    page_slug: string;
    page_type: string;
    claim_category: string;
    recommendation: string;
    score: number;
    reason: string;
  }>;
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
  bundle?: DraftSummary["bundle"];
  bundle_priority?: DraftSummary["bundle_priority"];
  recommended_action?: string;
  gatekeeper?: {
    tier: string | null;
    score: number | null;
    rationale: string | null;
    llm: {
      status: string | null;
      applied: boolean;
      suggested_tier: string | null;
      confidence: number | null;
      reason_code: string | null;
      provider: string | null;
      model: string | null;
    };
    routing: {
      hard_block: boolean;
      blocked_by_category: boolean;
      blocked_by_source_system: boolean;
      blocked_by_source_type: boolean;
      blocked_by_entity: boolean;
      blocked_by_source_id: boolean;
    };
  } | null;
  conflicts: ConflictItem[];
  moderation_actions: ModerationActionItem[];
};

type ModerationActionItem = {
  id: string;
  action_type: string;
  reviewed_by: string | null;
  decision_before: string | null;
  decision_after: string | null;
  draft_status_before: string | null;
  draft_status_after: string | null;
  note: string | null;
  reason: string | null;
  payload: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  created_at: string | null;
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

type WikiSpacePolicyAuditItem = {
  id: string;
  changed_by: string;
  before_policy: {
    write_mode?: string;
    comment_mode?: string;
    review_assignment_required?: boolean;
    metadata?: Record<string, unknown>;
  };
  after_policy: {
    write_mode?: string;
    comment_mode?: string;
    review_assignment_required?: boolean;
    metadata?: Record<string, unknown>;
  };
  changed_fields: string[];
  reason: string | null;
  created_at: string | null;
};

type WikiSpacePolicyAuditPayload = {
  project_id: string;
  space_key: string;
  entries: WikiSpacePolicyAuditItem[];
  available: boolean;
};

type WikiSpacePolicyAdoptionSummaryPayload = {
  project_id: string;
  space_key: string;
  summary: {
    total_updates: number;
    unique_actors: number;
    top_actor: string | null;
    top_actor_updates: number;
    avg_update_interval_days: number | null;
    checklist_usage: {
      none: number;
      ops_standard: number;
      policy_strict: number;
    };
    checklist_transitions: number;
    first_updated_at: string | null;
    last_updated_at: string | null;
  };
  available: boolean;
  meta: {
    sampled_entries: number;
    limit: number;
  };
};

type GatekeeperConfig = {
  project_id: string;
  min_sources_for_golden: number;
  conflict_free_days: number;
  min_score_for_golden: number;
  operational_short_text_len: number;
  operational_short_token_len: number;
  llm_assist_enabled: boolean;
  llm_provider: string;
  llm_model: string;
  llm_score_weight: number;
  llm_min_confidence: number;
  llm_timeout_ms: number;
  publish_mode_default: PublishMode;
  publish_mode_by_category: Record<string, PublishMode>;
  routing_policy?: {
    backfill_llm_classifier_mode?: "off" | "assist" | "enforce";
    backfill_llm_classifier_min_confidence?: number;
    backfill_llm_classifier_ambiguous_only?: boolean;
    backfill_llm_classifier_model?: string;
    [key: string]: unknown;
  };
  auto_publish_min_score: number;
  auto_publish_min_sources: number;
  auto_publish_require_golden: boolean;
  auto_publish_allow_conflicts: boolean;
  updated_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  source: string;
};

type GatekeeperConfigPayload = {
  config: GatekeeperConfig;
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

type WikiProcessSimulationPayload = {
  status: string;
  project_id: string;
  page: {
    id: string;
    title: string;
    slug: string;
    entity_key: string | null;
    page_type: string | null;
    status: string | null;
  } | null;
  diff: {
    changed_terms_total: number;
    added_terms: string[];
    removed_terms: string[];
  };
  impact: {
    candidate_pages_total: number;
    top_impacted_pages: Array<{
      slug: string;
      title: string;
      page_type: string;
      updated_at: string | null;
      matched_terms: string[];
    }>;
    pending_process_drafts: number;
    open_process_conflicts: number;
  };
  risk: {
    level: string;
    score: number;
    high_risk_hits: string[];
    medium_risk_hits: string[];
    should_block_publish: boolean;
    suggested_publish_mode: string;
  };
  recommendation: {
    action: string;
    suggested_publish_mode: string;
    rollback_hint?: {
      wiki_page_rollback_endpoint?: string;
      gatekeeper_rollback_endpoint?: string;
    };
  };
  generated_at: string;
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

type WikiLifecycleStatsPayload = {
  project_id: string;
  thresholds: {
    stale_days: number;
    critical_days: number;
  };
  counts: {
    total_pages: number;
    draft_pages: number;
    reviewed_pages: number;
    published_pages: number;
    archived_pages: number;
    pages_with_open_drafts: number;
    stale_warning_pages: number;
    stale_critical_pages: number;
  };
  stale_pages: Array<{
    slug: string;
    title: string | null;
    status: string;
    open_draft_count: number;
    activity_at: string | null;
    updated_at: string | null;
    age_days: number | null;
    severity: "warning" | "critical" | string;
  }>;
  stale_critical_pages: Array<{
    slug: string;
    title: string | null;
    status: string;
    open_draft_count: number;
    activity_at: string | null;
    updated_at: string | null;
    age_days: number | null;
    severity: "warning" | "critical" | string;
  }>;
  meta: {
    generated_at: string | null;
    limit: number;
    space_key?: string | null;
    searched_scope?: {
      project_id?: string;
      space_key?: string | null;
      status_scope?: string;
    };
    filters_applied?: {
      stale_days?: number;
      critical_days?: number;
      stale_limit?: number;
      space_key?: string | null;
    };
    empty_scope?: {
      code: "no_published" | "all_open_drafts" | "below_threshold" | string;
      message: string;
      details?: {
        published_pages?: number;
        published_pages_with_open_drafts?: number;
        published_pages_without_open_drafts?: number;
        published_pages_below_stale_threshold?: number;
        stale_days?: number;
      };
      suggested_actions?: Array<{
        action: "create_page" | "review_open_drafts" | "lower_threshold" | string;
        label: string;
        deep_link?: {
          core_tab?: "wiki" | "drafts" | "tasks" | string;
          wiki_focus?: string | null;
        };
      }>;
    };
  };
};

type WikiLifecycleTelemetryPayload = {
  project_id: string;
  action_key?: string | null;
  days: number;
  since: string;
  until: string;
  summary: {
    shown_total: number;
    applied_total: number;
    apply_rate: number;
    actions: Array<{
      action_key: string;
      shown_total: number;
      applied_total: number;
      apply_rate: number;
    }>;
  };
  daily: Array<{
    metric_date: string;
    shown_total: number;
    applied_total: number;
  }>;
  generated_at: string;
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

type AgentOrgchartNode = {
  agent_id: string;
  display_name: string;
  team: string;
  role: string;
  status: string;
  profile_slug: string;
  last_seen_at: string | null;
};

type AgentOrgchartEdge = {
  from_agent: string;
  to_agent: string;
  input_contract: string | null;
  output_contract: string | null;
  sla: string | null;
};

type AgentOrgchartPayload = {
  nodes: AgentOrgchartNode[];
  edges: AgentOrgchartEdge[];
  teams: Array<{
    team: string;
    agents_total: number;
  }>;
  summary: {
    nodes_total: number;
    edges_total: number;
    teams_total: number;
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

type BootstrapApproveRecommendationPayload = {
  status: string;
  project_id: string;
  recommended: {
    limit: number;
    sample_size: number;
    min_confidence: number;
    require_conflict_free: boolean;
    trusted_source_systems: string[];
    require_trusted_sources_on_apply: boolean;
    allow_large_batch: boolean;
    dry_run: boolean;
  };
  diagnostics?: {
    queue?: {
      open_pending_review?: number;
      blocked_conflict?: number;
      open_conflicts?: number;
    };
    backfill_quality?: {
      batches_recent?: number;
      processed_events?: number;
      generated_claims?: number;
      dropped_event_like?: number;
      kept_durable?: number;
      trusted_bypass?: number;
      event_drop_ratio?: number;
      durable_keep_ratio?: number;
    };
    sources?: {
      ownership_sources?: string[];
      legacy_source_types?: string[];
      legacy_declared_source_systems?: string[];
      fallback_used?: boolean;
    };
    notes?: string[];
  };
  safety?: {
    apply_limit_soft_cap?: number;
    rollback_hint?: {
      moderation_actions_endpoint?: string;
      note?: string;
    };
  };
  generated_at?: string;
};

type AdoptionBootstrapProfileApplyPayload = {
  status: string;
  dry_run: boolean;
  project_id: string;
  profile: string;
  updated_by: string;
  gatekeeper?: {
    diff?: {
      changed_keys?: {
        top_level?: string[];
        routing_policy?: string[];
      };
    };
  };
  bootstrap_recommendation?: BootstrapApproveRecommendationPayload["recommended"];
  diagnostics?: BootstrapApproveRecommendationPayload["diagnostics"];
  warning?: string;
  snapshot_id?: string | null;
  generated_at?: string;
};

type AdoptionPipelineVisibilityPayload = {
  project_id: string;
  window_days: number;
  since: string;
  generated_at?: string;
  filters_applied?: {
    source_systems?: string[];
    namespaces?: string[];
  };
  pipeline: {
    accepted: number;
    events: number;
    claims: number;
    drafts: number;
    pages: number;
  };
  accepted_source?: string;
  rejected_event_like?: number;
  conversions?: {
    accepted_to_events?: number | null;
    events_to_claims?: number | null;
    claims_to_drafts?: number | null;
    drafts_to_pages?: number | null;
  };
  draft_queue?: {
    pending_review?: number;
    blocked_conflict?: number;
    open_total?: number;
  };
  bottleneck?: {
    from_stage: string;
    to_stage: string;
    drop_count: number;
    drop_ratio: number;
    status: string;
    hint?: string;
  } | null;
  stages?: Array<{
    key: string;
    label: string;
    count: number;
  }>;
};

type AdoptionEvidenceBundleItem = {
  id: string;
  bundle_key: string;
  bundle_type: string;
  suggested_page_type: string;
  entity_key: string;
  bundle_status: string;
  support_count: number;
  repeated_claims: number;
  source_diversity: number;
  evidence_count: number;
  quality_score: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  latest_claim_at?: string | null;
  linked_claims?: number;
  metadata?: Record<string, unknown>;
  sample_claims?: Array<{
    claim_text?: string;
    category?: string;
    metadata?: Record<string, unknown>;
  }>;
};

type AdoptionEvidenceBundlesPayload = {
  bundles: AdoptionEvidenceBundleItem[];
  filters?: {
    project_id?: string;
    bundle_status?: string | null;
    bundle_type?: string | null;
    limit?: number;
  };
};

type AdoptionRejectionDiagnosticsPayload = {
  project_id: string;
  window_days: number;
  summary?: {
    rejected_total?: number;
    sampled_examples?: number;
  };
  top_reject_reasons?: Array<{
    key: string;
    count: number;
  }>;
  top_blocked_patterns?: {
    source_types?: Array<{ key: string; count: number }>;
    source_systems?: Array<{ key: string; count: number }>;
    tool_names?: Array<{ key: string; count: number }>;
  };
  suggested_policy_knobs?: Array<{
    knob: string;
    hint: string;
  }>;
  examples?: Array<{
    claim_id?: string;
    category?: string;
    reason_tags?: string[];
    updated_at?: string;
    claim_text_snippet?: string;
  }>;
};

type LegacyImportProfile = {
  profile: string;
  label: string;
  description: string;
  default_table?: string | null;
  table_candidates?: string[];
  default_source_id_prefix?: string | null;
};

type LegacyImportProfilesPayload = {
  profiles: LegacyImportProfile[];
};

type AdoptionImportConnectorItem = {
  id: string;
  source_type: string;
  profile: string;
  sync_mode: string;
  label: string;
  description: string;
  config_patch: Record<string, unknown>;
  validation_hints?: {
    required_fields?: string[];
    errors?: string[];
    warnings?: string[];
    is_valid?: boolean;
  };
};

type AdoptionImportConnectorsPayload = {
  source_type: string;
  profile: string | null;
  connectors: AdoptionImportConnectorItem[];
};

type AdoptionImportConnectorResolvePayload = {
  status: string;
  connector?: AdoptionImportConnectorItem;
  field_overrides?: Record<string, unknown>;
};

type AdoptionImportConnectorBootstrapPayload = {
  status: string;
  dry_run: boolean;
  source_ref?: string;
  connector?: AdoptionImportConnectorItem;
  source?: {
    id?: string;
    source_ref?: string;
    enabled?: boolean;
  };
  validation?: {
    is_valid?: boolean;
    errors?: string[];
    warnings?: string[];
  };
  sync_queue?: {
    status?: string;
    next_action?: string;
    run?: {
      id?: string;
    };
  };
  sync_queue_processor?: {
    status?: string;
  };
};

type AdoptionKpiPayload = {
  project_id: string;
  window_days: number;
  generated_at?: string;
  kpi?: {
    time_to_first_draft_sec?: number | null;
    time_to_first_publish_sec?: number | null;
    draft_noise_ratio?: number;
    publish_revert_rate?: number;
  };
  alerts?: Array<{
    metric: string;
    status: string;
    hint?: string;
  }>;
  wiki_quality?: {
    quality?: {
      pass?: boolean;
      checks?: Record<string, boolean>;
      thresholds?: {
        placeholder_ratio_core_max?: number;
        daily_summary_open_draft_ratio_max?: number;
        min_core_published?: number;
      };
    };
    core_pages?: {
      required_leaves?: string[];
      published_total?: number;
      published_slugs?: string[];
      missing_required_leaves?: string[];
    };
    content_quality?: {
      placeholder_ratio_core?: number;
      placeholder_hits_core?: number;
      core_word_count_total?: number;
    };
    draft_noise?: {
      open_drafts_total?: number;
      daily_summary_open_drafts?: number;
      daily_summary_open_draft_ratio?: number;
    };
    warnings?: Array<{
      code?: string;
      severity?: string;
      ratio?: number;
      threshold?: number;
      message?: string;
    }>;
  };
};

type AdoptionPolicyQuickLoopPayload = {
  project_id: string;
  window_days: number;
  recommended?: {
    preset_key?: string;
    title?: string;
    reason?: string;
    changed_routing_keys?: string[];
  };
  apply_endpoint?: string;
  rollback_preview_endpoint?: string;
};

type SelfhostConsistencyPayload = {
  status: "ok" | "warning";
  checks?: Array<{
    key: string;
    status: string;
    message?: string;
  }>;
  warnings_total?: number;
};

type EnterpriseReadinessPayload = {
  status: "healthy" | "warning" | "critical" | string;
  summary?: {
    critical?: number;
    warnings?: number;
    auth_mode?: string;
    rbac_mode?: string;
    tenancy_mode?: string;
  };
  counts?: {
    tenants?: number;
    tenant_projects?: number;
    active_auth_sessions?: number;
    active_idp_connections?: number;
    active_scim_tokens?: number;
  };
  warnings?: Array<{
    code?: string;
    severity?: string;
    message?: string;
  }>;
};

type AdoptionSyncPresetPayload = {
  status: string;
  project_id: string;
  dry_run: boolean;
  explainability?: {
    summary?: {
      total_rejections?: number;
      critical_warnings?: number;
      primary_bucket?: string;
    };
    reason_buckets?: Record<
      string,
      {
        count?: number;
        share?: number;
        top_tags?: string[];
      }
    >;
  };
  pipeline_visibility?: AdoptionPipelineVisibilityPayload;
  rejection_diagnostics?: AdoptionRejectionDiagnosticsPayload;
  bootstrap_profile?: Record<string, unknown>;
  sync_queue?: {
    queued?: number;
    already_queued?: number;
    sources_scanned?: number;
  };
  bootstrap_approve?: {
    dry_run?: boolean;
    summary?: {
      candidates?: number;
      approved?: number;
      failed?: number;
    };
  };
};

type AdoptionAgentWikiBootstrapPayload = {
  status: string;
  project_id: string;
  dry_run: boolean;
  requested_status?: string;
  plan?: {
    pages_total?: number;
    pages?: Array<{
      title?: string;
      slug?: string;
      page_type?: string;
      words?: number;
    }>;
  };
  summary?: {
    created?: number;
    existing?: number;
    skipped?: number;
  };
  definition_of_done?: {
    agent_page?: boolean;
    data_sources_page?: boolean;
    operational_process_page?: boolean;
    published_minimum_ready?: boolean;
    pages_total?: number;
  };
};

type AdoptionFirstRunBootstrapPayload = {
  status: string;
  project_id: string;
  profile: string;
  requested_status: string;
  summary?: {
    created?: number;
    existing?: number;
    skipped?: number;
    published_downgraded_to_reviewed?: number;
  };
  snapshot_id?: string | null;
};

type LegacyImportSource = {
  id: string;
  project_id: string;
  source_type: string;
  source_ref: string;
  enabled: boolean;
  sync_interval_minutes: number;
  next_run_at: string | null;
  last_run_at: string | null;
  last_success_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
  config: Record<string, unknown>;
};

type LegacyImportSourcesPayload = {
  sources: LegacyImportSource[];
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

type SpaceRecoveryNotice = {
  from: string | null;
  to: string;
  reason: "missing_space" | "empty_published_space";
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
  pageType: string;
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

type PageLifecycleActionKind = "open_drafts" | "promote_reviewed" | "publish" | "archive" | "restore";

type PageLifecycleSuggestion = {
  key: string;
  severity: "info" | "watch" | "critical";
  title: string;
  detail: string;
  action: {
    kind: PageLifecycleActionKind;
    label: string;
  } | null;
};

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

type LifecycleQueryPresetKey = "stale_21" | "critical_45" | "custom";

type WikiUxMetricsState = {
  sessionStartedMs: number;
  firstPageViewMs: number | null;
  firstPublishMs: number | null;
  pageOpenCount: number;
  pageOpenCountAtFirstPublish: number | null;
  publishCount: number;
};

type LifecycleAdvisorMetricsState = {
  sessionId: string;
  sessionStartedMs: number;
  suggestionShown: number;
  suggestionApplied: number;
  staleShownAtBySlug: Record<string, number>;
  staleResolvedDurationsMs: number[];
  emptyScopeActionShownByType: Record<string, number>;
  emptyScopeActionAppliedByType: Record<string, number>;
};

type FriendlyRoleDescriptor = {
  key: "viewer" | "editor" | "approver" | "admin";
  label: string;
  canDo: string;
  typicalUse: string;
  mapsTo: string[];
};

type PublishChecklistPresetKey = "none" | "ops_standard" | "policy_strict";

type PublishChecklistItem = {
  id: string;
  label: string;
  help: string;
};

type PublishChecklistPreset = {
  key: PublishChecklistPresetKey;
  label: string;
  description: string;
  items: PublishChecklistItem[];
};

type SpacePolicyAdoptionSummary = {
  totalUpdates: number;
  uniqueActors: number;
  topActor: string | null;
  topActorUpdates: number;
  avgCadenceDays: number | null;
  checklistUsage: Record<PublishChecklistPresetKey, number>;
  checklistTransitions: number;
  firstUpdatedAt: string | null;
  lastUpdatedAt: string | null;
};

// v5 drops legacy/stale profile state from pre-wiki-first builds.
const STORAGE_KEY = "synapse_web_console_v5";
const LEGACY_STORAGE_KEYS = ["synapse_web_console_v4", "synapse_web_console_v3"];

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
    pageType: "access",
    sectionKey: "access_rules",
    sectionHeading: "Access Rules",
    sectionMode: "append",
    statements: ["Access requirements changed. Confirm credentials before dispatch."],
  },
  {
    key: "operations_incident",
    title: "Operations Incident",
    description: "Use for temporary outages, repairs, or operational constraints.",
    pageType: "incident",
    sectionKey: "ops_notes",
    sectionHeading: "Ops Notes",
    sectionMode: "append",
    statements: ["Operational incident active. Route planning must account for this constraint."],
  },
  {
    key: "customer_preference",
    title: "Customer Preference",
    description: "Use for stable customer communication/delivery preferences.",
    pageType: "customer",
    sectionKey: "customer_preferences",
    sectionHeading: "Customer Preferences",
    sectionMode: "append",
    statements: ["Preference confirmed. Apply consistently to future interactions."],
  },
  {
    key: "issue_playbook",
    title: "Issue Playbook",
    description: "Use for trigger -> action -> outcome support/ops workflows.",
    pageType: "process",
    sectionKey: "steps",
    sectionHeading: "Steps",
    sectionMode: "append",
    statements: ["When issue is detected, follow documented steps and verify outcome."],
  },
  {
    key: "escalation_rule",
    title: "Escalation Rule",
    description: "Use for escalation conditions, handoff path, and SLA.",
    pageType: "process",
    sectionKey: "escalation",
    sectionHeading: "Escalation",
    sectionMode: "append",
    statements: ["Escalate to Tier-2 when risk/severity threshold is met."],
  },
  {
    key: "customer_exception",
    title: "Customer Exception",
    description: "Use for approved deviations from default process.",
    pageType: "process",
    sectionKey: "exceptions",
    sectionHeading: "Exceptions",
    sectionMode: "append",
    statements: ["Exception approved for customer segment with explicit expiry and owner."],
  },
  {
    key: "known_incident_playbook",
    title: "Known Incident",
    description: "Use for recurring incident trigger, workaround, and verification.",
    pageType: "incident",
    sectionKey: "workarounds",
    sectionHeading: "Workarounds",
    sectionMode: "append",
    statements: ["Known incident detected. Apply workaround and confirm service restoration."],
  },
];

const PUBLISH_CHECKLIST_PRESETS: PublishChecklistPreset[] = [
  {
    key: "none",
    label: "No checklist",
    description: "Publish modal has no extra confirmation checklist.",
    items: [],
  },
  {
    key: "ops_standard",
    label: "Ops standard",
    description: "Lightweight process check before publish.",
    items: [
      {
        id: "evidence-linked",
        label: "Evidence or source context is linked",
        help: "Every critical change is traceable to drafts, tickets, or operator notes.",
      },
      {
        id: "scope-reviewed",
        label: "Change scope is clear for agents",
        help: "The page explicitly states where the rule applies and where it does not.",
      },
      {
        id: "rollback-ready",
        label: "Rollback path is known",
        help: "Reviewer can revert this publish safely if downstream behavior regresses.",
      },
    ],
  },
  {
    key: "policy_strict",
    label: "Policy strict",
    description: "Use for legal/financial/security-sensitive spaces.",
    items: [
      {
        id: "policy-owner",
        label: "Policy owner acknowledged the change",
        help: "Named owner or approver has validated final wording.",
      },
      {
        id: "risk-reviewed",
        label: "Risk and customer impact reviewed",
        help: "Potential failure modes and blast radius are documented.",
      },
      {
        id: "compliance-check",
        label: "Compliance constraints are satisfied",
        help: "No conflicts with legal/security/finance constraints for this space.",
      },
      {
        id: "rollback-drill",
        label: "Rollback plan tested or confirmed",
        help: "Rollback owner and trigger conditions are explicit.",
      },
    ],
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

const LIFECYCLE_QUERY_PRESETS: Array<{
  key: LifecycleQueryPresetKey;
  label: string;
  staleDays: number;
  criticalDays: number;
}> = [
  { key: "stale_21", label: "Stale >=21d", staleDays: 21, criticalDays: 45 },
  { key: "critical_45", label: "Critical >=45d", staleDays: 45, criticalDays: 45 },
  { key: "custom", label: "Custom", staleDays: 21, criticalDays: 45 },
];

const ONBOARDING_STORAGE_PREFIX = "synapse:onboarding_done:";
const LAST_PAGE_STORAGE_PREFIX = "synapse:last_page:";
const PAGE_EDIT_DRAFT_STORAGE_PREFIX = "synapse:page_edit_draft:";
const UX_METRICS_STORAGE_PREFIX = "synapse:wiki_ux_metrics:";
const LIFECYCLE_METRICS_STORAGE_PREFIX = "synapse:lifecycle_metrics:";
const LIFECYCLE_SPACE_FILTER_ALL = "__all__";
const LIFECYCLE_TELEMETRY_WINDOW_DAYS = 7;
const LIFECYCLE_TELEMETRY_SYNC_DEBOUNCE_MS = 1200;

const FRIENDLY_ROLE_MODEL: FriendlyRoleDescriptor[] = [
  {
    key: "viewer",
    label: "Viewer",
    canDo: "Read wiki pages and open draft context.",
    typicalUse: "Business users who consume knowledge but do not edit policy.",
    mapsTo: ["viewer", "read_only", "reader"],
  },
  {
    key: "editor",
    label: "Editor",
    canDo: "Create and edit pages, propose updates, attach evidence.",
    typicalUse: "Ops leads and subject-matter experts writing runbooks.",
    mapsTo: ["editor", "writer", "contributor"],
  },
  {
    key: "approver",
    label: "Approver",
    canDo: "Review/approve/reject drafts and publish trusted updates.",
    typicalUse: "Team leads responsible for quality gates.",
    mapsTo: ["approver", "reviewer", "moderator"],
  },
  {
    key: "admin",
    label: "Admin",
    canDo: "Manage workspace settings, policies, and role assignments.",
    typicalUse: "Platform owners and security administrators.",
    mapsTo: ["admin", "owner", "workspace_admin"],
  },
];

type UiMode = "core" | "advanced";
type CoreWorkspaceTab = "wiki" | "drafts" | "tasks";
type CoreWorkspaceRoute = "wiki" | "operations";

const DEFAULT_API_URL = String(import.meta.env.VITE_SYNAPSE_API_URL || "http://localhost:8080").trim() || "http://localhost:8080";
const WEB_BUILD = String(import.meta.env.VITE_SYNAPSE_WEB_BUILD || "0.1.0").trim() || "0.1.0";
const REQUESTED_UI_PROFILE = String(import.meta.env.VITE_SYNAPSE_UI_PROFILE || "")
  .trim()
  .toLowerCase();
// Legacy control-center workspace is removed from OSS UI.
const CAN_ACCESS_ADVANCED_MODE = false;
if (
  REQUESTED_UI_PROFILE &&
  !["core", "core-only", "wiki", "wiki-first"].includes(REQUESTED_UI_PROFILE) &&
  typeof window !== "undefined"
) {
  // eslint-disable-next-line no-console
  console.warn("[Synapse] VITE_SYNAPSE_UI_PROFILE is deprecated and ignored. UI is wiki-first only.");
}

type ParsedWikiPath = {
  basePath: string;
  pageSlug: string | null;
  route: CoreWorkspaceRoute;
};

function parseWikiPath(pathname: string): ParsedWikiPath {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  const lower = normalized.toLowerCase();
  const marker = "/wiki";
  const markerWithSlash = "/wiki/";
  const operationsMarker = "/operations";
  const operationsMarkerWithSlash = "/operations/";

  if (lower.endsWith(operationsMarker)) {
    const basePath = normalized.slice(0, normalized.length - operationsMarker.length) || "/";
    return { basePath, pageSlug: null, route: "operations" };
  }

  const operationsMarkerIndex = lower.indexOf(operationsMarkerWithSlash);
  if (operationsMarkerIndex >= 0) {
    const basePath = normalized.slice(0, operationsMarkerIndex) || "/";
    return { basePath, pageSlug: null, route: "operations" };
  }

  if (lower.endsWith(marker)) {
    const basePath = normalized.slice(0, normalized.length - marker.length) || "/";
    return { basePath, pageSlug: null, route: "wiki" };
  }

  const markerIndex = lower.indexOf(markerWithSlash);
  if (markerIndex >= 0) {
    const basePath = normalized.slice(0, markerIndex) || "/";
    const rawSlug = normalized.slice(markerIndex + markerWithSlash.length);
    const decodedSlug = rawSlug
      .split("/")
      .map((segment) => {
        try {
          return decodeURIComponent(segment);
        } catch {
          return segment;
        }
      })
      .filter((segment) => segment.trim().length > 0)
      .join("/");
    return { basePath, pageSlug: decodedSlug || null, route: "wiki" };
  }

  return { basePath: normalized, pageSlug: null, route: "wiki" };
}

function encodeWikiSlugForPath(slug: string | null): string {
  if (!slug) return "";
  return slug
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function buildWikiPath(basePath: string, pageSlug: string | null): string {
  const normalizedBase = (basePath || "/").replace(/\/+$/, "") || "/";
  const wikiRoot = normalizedBase === "/" ? "/wiki" : `${normalizedBase}/wiki`;
  const encodedSlug = encodeWikiSlugForPath(pageSlug);
  if (!encodedSlug) {
    return wikiRoot;
  }
  return `${wikiRoot}/${encodedSlug}`;
}

function buildOperationsPath(basePath: string): string {
  const normalizedBase = (basePath || "/").replace(/\/+$/, "") || "/";
  return normalizedBase === "/" ? "/operations" : `${normalizedBase}/operations`;
}

function buildWorkspacePath(basePath: string, route: CoreWorkspaceRoute, pageSlug: string | null): string {
  if (route === "operations") {
    return buildOperationsPath(basePath);
  }
  return buildWikiPath(basePath, pageSlug);
}

function scrollElementIntoViewWithRetry(elementId: string, attempts = 6, delayMs = 140): void {
  if (typeof window === "undefined") return;
  const maxAttempts = Math.max(1, attempts);
  const normalizedDelay = Math.max(40, delayMs);
  let tries = 0;
  const tick = () => {
    tries += 1;
    const element = window.document.getElementById(elementId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (tries >= maxAttempts) return;
    window.setTimeout(tick, normalizedDelay);
  };
  tick();
}

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

function randomKey(): string {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

type InlineMarkdownDiffLine = {
  kind: "added" | "removed" | "context";
  text: string;
};

function buildInlineMarkdownDiff(
  baseMarkdown: string,
  targetMarkdown: string,
  maxLines = 520,
): { added: number; removed: number; changed: boolean; lines: InlineMarkdownDiffLine[]; truncated: boolean } {
  const parts = diffLines(String(baseMarkdown || ""), String(targetMarkdown || ""));
  let added = 0;
  let removed = 0;
  const output: InlineMarkdownDiffLine[] = [];
  for (const part of parts) {
    const lines = String(part.value || "").split("\n");
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      const isTailEmpty = index === lines.length - 1 && line === "";
      if (isTailEmpty) continue;
      if (part.added) {
        added += 1;
        output.push({ kind: "added", text: line });
      } else if (part.removed) {
        removed += 1;
        output.push({ kind: "removed", text: line });
      } else {
        output.push({ kind: "context", text: line });
      }
    }
  }
  const changed = added > 0 || removed > 0;
  if (!changed) {
    return {
      added,
      removed,
      changed: false,
      lines: [{ kind: "context", text: "No changes between selected versions." }],
      truncated: false,
    };
  }
  const clipped = output.slice(0, Math.max(40, maxLines));
  const truncated = output.length > clipped.length;
  if (truncated) {
    clipped.push({
      kind: "context",
      text: `… diff truncated: showing ${clipped.length}/${output.length} lines`,
    });
  }
  return {
    added,
    removed,
    changed: true,
    lines: clipped,
    truncated,
  };
}

function normalizeTelemetryActionKey(value: string): string {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized.slice(0, 96);
}

function statusColor(status: string): string {
  if (status === "pending_review") return "blue";
  if (status === "blocked_conflict") return "orange";
  if (status === "approved") return "green";
  if (status === "rejected") return "red";
  return "gray";
}

function recommendationColor(recommendation: string | null | undefined): string {
  const normalized = String(recommendation || "").trim().toLowerCase();
  if (normalized === "approve_first") return "teal";
  if (normalized === "review_with_context") return "blue";
  if (normalized === "needs_human_caution") return "orange";
  if (normalized === "needs_more_bundle_evidence") return "gray";
  return "grape";
}

function humanizeRecommendation(recommendation: string | null | undefined): string {
  const normalized = String(recommendation || "").trim();
  if (!normalized) return "review";
  return normalized.replace(/_/g, " ");
}

function draftPassesDefaultBundleGuard(draft: DraftSummary): boolean {
  const compiler = draft.gatekeeper?.compiler_v2;
  const bundleStatus = String(draft.bundle?.bundle_status || "").trim().toLowerCase();
  const support = Number(draft.bundle?.support_count ?? compiler?.bundle_support ?? 0);
  if (bundleStatus === "ready" && support >= 1) return true;
  if (compiler?.promotion_ready_from_bundle && support >= 2) return true;
  return false;
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

function formatCadenceDays(value: number | null): string {
  if (value == null || !Number.isFinite(value) || value < 0) return "—";
  if (value < 1) return "<1 day";
  if (value < 7) return `${value.toFixed(1)} days`;
  return `${(value / 7).toFixed(1)} weeks`;
}

function normalizedChecklistPresetFromMetadata(metadataRaw: unknown): PublishChecklistPresetKey {
  if (!metadataRaw || typeof metadataRaw !== "object") return "none";
  const metadata = metadataRaw as Record<string, unknown>;
  const preset = String(metadata.publish_checklist_preset || "").trim().toLowerCase();
  if (preset === "ops_standard" || preset === "policy_strict") return preset;
  return "none";
}

function summarizeSpacePolicyAudit(entries: WikiSpacePolicyAuditItem[]): SpacePolicyAdoptionSummary {
  const actorCounts = new Map<string, number>();
  const checklistUsage: Record<PublishChecklistPresetKey, number> = {
    none: 0,
    ops_standard: 0,
    policy_strict: 0,
  };
  let checklistTransitions = 0;
  const timestamps: number[] = [];

  for (const entry of entries) {
    const actor = String(entry.changed_by || "").trim() || "unknown";
    actorCounts.set(actor, (actorCounts.get(actor) || 0) + 1);

    const afterPreset = normalizedChecklistPresetFromMetadata(entry.after_policy?.metadata);
    checklistUsage[afterPreset] += 1;

    const beforePreset = normalizedChecklistPresetFromMetadata(entry.before_policy?.metadata);
    if (beforePreset !== afterPreset) {
      checklistTransitions += 1;
    }

    const ts = entry.created_at ? new Date(entry.created_at).getTime() : Number.NaN;
    if (!Number.isNaN(ts) && ts > 0) {
      timestamps.push(ts);
    }
  }

  const sortedActors = [...actorCounts.entries()].sort((left, right) => right[1] - left[1]);
  const topActor = sortedActors.length > 0 ? sortedActors[0][0] : null;
  const topActorUpdates = sortedActors.length > 0 ? sortedActors[0][1] : 0;

  timestamps.sort((left, right) => left - right);
  let avgCadenceDays: number | null = null;
  if (timestamps.length >= 2) {
    let diffSumMs = 0;
    for (let index = 1; index < timestamps.length; index += 1) {
      diffSumMs += timestamps[index] - timestamps[index - 1];
    }
    const avgDiffMs = diffSumMs / Math.max(1, timestamps.length - 1);
    avgCadenceDays = avgDiffMs / (1000 * 60 * 60 * 24);
  }

  return {
    totalUpdates: entries.length,
    uniqueActors: actorCounts.size,
    topActor,
    topActorUpdates,
    avgCadenceDays,
    checklistUsage,
    checklistTransitions,
    firstUpdatedAt: timestamps.length > 0 ? new Date(Math.min(...timestamps)).toISOString() : null,
    lastUpdatedAt: timestamps.length > 0 ? new Date(Math.max(...timestamps)).toISOString() : null,
  };
}

const PAGE_STALE_WARNING_DAYS = 21;
const PAGE_STALE_CRITICAL_DAYS = 45;
const PAGE_RECENT_ACTIVITY_DAYS = 7;

function pageAgeDays(value: string | null | undefined, referenceMs = Date.now()): number | null {
  const ts = activityTimestampMs(value);
  if (!ts) return null;
  const diff = Math.max(0, referenceMs - ts);
  return diff / (1000 * 60 * 60 * 24);
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

function matchesBootstrapPreview(
  preview: BootstrapApproveRunPayload | null | undefined,
  expected: {
    projectId: string;
    trustedSourceSystems: string[];
    limit: number;
    minConfidence: number;
    requireConflictFree: boolean;
  },
): boolean {
  const selection = preview?.selection;
  if (!preview?.dry_run || !selection) return false;
  if (String(preview.project_id || "") !== expected.projectId) return false;
  const previewTrusted = [...(selection.trusted_source_systems || [])]
    .map((item) => String(item || "").trim().toLowerCase())
    .filter(Boolean)
    .sort();
  const expectedTrusted = [...expected.trustedSourceSystems]
    .map((item) => String(item || "").trim().toLowerCase())
    .filter(Boolean)
    .sort();
  if (previewTrusted.join(",") !== expectedTrusted.join(",")) return false;
  if (Number(selection.limit || -1) !== Number(expected.limit)) return false;
  if (Number(selection.min_confidence || -1) !== Number(expected.minConfidence)) return false;
  if (Boolean(selection.require_conflict_free) !== Boolean(expected.requireConflictFree)) return false;
  return Number(preview.summary.candidates || 0) > 0;
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

const LazyIntelligencePanel = lazy(() => import("./components/IntelligencePanel"));
const LazyTaskTrackerPanel = lazy(() => import("./components/TaskTrackerPanel"));
const LazyWikiPageCanvas = lazy(() => import("./components/WikiPageCanvas"));

export default function App() {
  const initialPathState = useMemo(() => parseWikiPath(window.location.pathname), []);
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [projectId, setProjectId] = useState("");
  const [reviewer, setReviewer] = useState("ops_manager");
  const [authMode, setAuthMode] = useState<AuthModePayload | null>(null);
  const [oidcToken, setOidcToken] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [sessionSummary, setSessionSummary] = useState<AuthSessionPayload["session"] | null>(null);
  const [authActionLoading, setAuthActionLoading] = useState(false);
  const [uiMode, setUiMode] = useState<UiMode>("core");
  const [coreExpertControls, setCoreExpertControls] = useState(false);
  const [coreWorkspaceTab, setCoreWorkspaceTab] = useState<CoreWorkspaceTab>("wiki");
  const [coreWorkspaceRoute, setCoreWorkspaceRoute] = useState<CoreWorkspaceRoute>(initialPathState.route);
  const [wikiBasePath, setWikiBasePath] = useState(initialPathState.basePath);
  const [status, setStatus] = useState<string | null>(null);
  const [pageStatusFilter, setPageStatusFilter] = useState<string | null>(null);
  const [pageUpdatedByFilter, setPageUpdatedByFilter] = useState("");
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [draftQueueSummary, setDraftQueueSummary] = useState<DraftQueueSummary | null>(null);
  const [wikiPages, setWikiPages] = useState<WikiPageListItem[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedPageSlug, setSelectedPageSlug] = useState<string | null>(null);
  const pageEditDraftStorageKey =
    projectId.trim() && selectedPageSlug
      ? `${PAGE_EDIT_DRAFT_STORAGE_PREFIX}${projectId.trim()}:${selectedPageSlug}`
      : null;
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string | null>(null);
  const [spaceRecoveryNotice, setSpaceRecoveryNotice] = useState<SpaceRecoveryNotice | null>(null);
  const [pageFilter, setPageFilter] = useState("");
  const [draftFilter] = useState("");
  const [openPagesOnly, setOpenPagesOnly] = useState(false);
  const [collapsedTreeNodes, setCollapsedTreeNodes] = useState<Record<string, boolean>>({});
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<string | null>(null);
  const [pinnedPageSlugs, setPinnedPageSlugs] = useState<string[]>([]);
  const [reviewQueuePreset, setReviewQueuePreset] = useState<ReviewQueuePresetKey>("open_queue");
  const [draftRecommendationFilter, setDraftRecommendationFilter] = useState<DraftRecommendationFilter>("all");
  const [reviewSlaHours, setReviewSlaHours] = useState(24);
  const [bulkSelectedDraftIds, setBulkSelectedDraftIds] = useState<string[]>([]);
  const [bulkForceApprove, setBulkForceApprove] = useState(false);
  const bulkApproveNote = "";
  const bulkRejectReason = "";
  const [bootstrapTrustedSources, setBootstrapTrustedSources] = useState("legacy_import,postgres_sql");
  const [bootstrapTrustedSourcesTouched, setBootstrapTrustedSourcesTouched] = useState(false);
  const [bootstrapMinConfidence, setBootstrapMinConfidence] = useState("0.85");
  const [bootstrapLimit, setBootstrapLimit] = useState("50");
  const [bootstrapSampleSize, setBootstrapSampleSize] = useState("15");
  const [bootstrapRequireConflictFree, setBootstrapRequireConflictFree] = useState(true);
  const [showBootstrapTools, setShowBootstrapTools] = useState(false);
  const [showMigrationMode, setShowMigrationMode] = useState(false);
  const [showDraftOperationsTools, setShowDraftOperationsTools] = useState(false);
  const [showAdvancedDraftOps, setShowAdvancedDraftOps] = useState(false);
  const [showWikiFilters, setShowWikiFilters] = useState(false);
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
  const [showCoreLifecycleDetails, setShowCoreLifecycleDetails] = useState(false);
  const [bootstrapLoading, setBootstrapLoading] = useState(false);
  const [bootstrapProfileLoading, setBootstrapProfileLoading] = useState(false);
  const [bootstrapResult, setBootstrapResult] = useState<BootstrapApproveRunPayload | null>(null);
  const [bootstrapRecommendation, setBootstrapRecommendation] = useState<BootstrapApproveRecommendationPayload | null>(null);
  const [bootstrapProfileResult, setBootstrapProfileResult] = useState<AdoptionBootstrapProfileApplyPayload | null>(null);
  const [adoptionPipeline, setAdoptionPipeline] = useState<AdoptionPipelineVisibilityPayload | null>(null);
  const [adoptionPipelineLoading, setAdoptionPipelineLoading] = useState(false);
  const [adoptionEvidenceBundles, setAdoptionEvidenceBundles] = useState<AdoptionEvidenceBundlesPayload | null>(null);
  const [adoptionEvidenceBundlesLoading, setAdoptionEvidenceBundlesLoading] = useState(false);
  const [adoptionRejections, setAdoptionRejections] = useState<AdoptionRejectionDiagnosticsPayload | null>(null);
  const [adoptionRejectionsLoading, setAdoptionRejectionsLoading] = useState(false);
  const [, setLoadingBootstrapRecommendation] = useState(false);
  const [legacyProfiles, setLegacyProfiles] = useState<LegacyImportProfile[]>([]);
  const [adoptionImportConnectors, setAdoptionImportConnectors] = useState<AdoptionImportConnectorItem[]>([]);
  const [selectedConnectorId, setSelectedConnectorId] = useState<string | null>(null);
  const [resolvedConnector, setResolvedConnector] = useState<AdoptionImportConnectorItem | null>(null);
  const [loadingConnectorResolve, setLoadingConnectorResolve] = useState(false);
  const [legacySources, setLegacySources] = useState<LegacyImportSource[]>([]);
  const [, setLoadingLegacyProfiles] = useState(false);
  const [, setLoadingLegacySources] = useState(false);
  const [adoptionKpi, setAdoptionKpi] = useState<AdoptionKpiPayload | null>(null);
  const [loadingAdoptionKpi, setLoadingAdoptionKpi] = useState(false);
  const [policyQuickLoop, setPolicyQuickLoop] = useState<AdoptionPolicyQuickLoopPayload | null>(null);
  const [loadingPolicyQuickLoop, setLoadingPolicyQuickLoop] = useState(false);
  const [applyingPolicyQuickLoop, setApplyingPolicyQuickLoop] = useState(false);
  const [enterpriseReadiness, setEnterpriseReadiness] = useState<EnterpriseReadinessPayload | null>(null);
  const [loadingEnterpriseReadiness, setLoadingEnterpriseReadiness] = useState(false);
  const [runningSyncPreset, setRunningSyncPreset] = useState(false);
  const [runningAgentWikiBootstrap, setRunningAgentWikiBootstrap] = useState(false);
  const [agentWikiBootstrapResult, setAgentWikiBootstrapResult] = useState<AdoptionAgentWikiBootstrapPayload | null>(null);
  const [selfhostConsistency, setSelfhostConsistency] = useState<SelfhostConsistencyPayload | null>(null);
  const [loadingSelfhostConsistency, setLoadingSelfhostConsistency] = useState(false);
  const [connectingLegacySource, setConnectingLegacySource] = useState(false);
  const [, setRunningLegacySyncSourceId] = useState<string | null>(null);
  const [legacySourceRef, setLegacySourceRef] = useState("existing_memory");
  const [legacySqlProfile, setLegacySqlProfile] = useState("ops_kb_items");
  const [legacySqlDsnEnv, setLegacySqlDsnEnv] = useState("LEGACY_SQL_DSN");
  const [legacyMemoryApiUrl, setLegacyMemoryApiUrl] = useState("");
  const [legacySyncIntervalMinutes, setLegacySyncIntervalMinutes] = useState("5");
  const [legacyMaxRecords] = useState("5000");
  const [legacyChunkSize] = useState("100");
  const [legacyAutoOpenMigrationMode, setLegacyAutoOpenMigrationMode] = useState(true);
  const [showLegacySetupModal, setShowLegacySetupModal] = useState(false);
  const [legacySetupStep, setLegacySetupStep] = useState(1);
  const [legacyWizardStep1Done, setLegacyWizardStep1Done] = useState(false);
  const [legacyWizardStep2Done, setLegacyWizardStep2Done] = useState(false);
  const [legacyWizardStep3Done, setLegacyWizardStep3Done] = useState(false);
  const [legacyWizardStep4Done, setLegacyWizardStep4Done] = useState(false);
  const [legacySeedStarterPages, setLegacySeedStarterPages] = useState(true);
  const [legacyStarterProfile, setLegacyStarterProfile] = useState<"standard" | "support_ops">("standard");
  const [runningStarterBootstrap, setRunningStarterBootstrap] = useState(false);
  const [draftDetail, setDraftDetail] = useState<DraftDetailPayload | null>(null);
  const [selectedPageDetail, setSelectedPageDetail] = useState<WikiPageDetailPayload | null>(null);
  const [pageHistory, setPageHistory] = useState<WikiPageHistoryPayload | null>(null);
  const [, setLoadingPageHistory] = useState(false);
  const [historyBaseVersion, setHistoryBaseVersion] = useState<string | null>(null);
  const [historyTargetVersion, setHistoryTargetVersion] = useState<string | null>(null);
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [rollbackSummaryInput, setRollbackSummaryInput] = useState("Rollback to selected version");
  const [rollingBackPageVersion, setRollingBackPageVersion] = useState(false);
  const [pageEditMode, setPageEditMode] = useState(false);
  const [pageEditTitle, setPageEditTitle] = useState("");
  const [pageEditStatus, setPageEditStatus] = useState<"draft" | "reviewed" | "published" | "archived">("published");
  const [pageEditSummary, setPageEditSummary] = useState("Manual wiki page edit");
  const [pageEditMarkdown, setPageEditMarkdown] = useState("");
  const [pageEditDraftState, setPageEditDraftState] = useState<"idle" | "saving" | "saved" | "restored">("idle");
  const [pageEditDraftSavedAt, setPageEditDraftSavedAt] = useState<string | null>(null);
  const [restoredDraftKey, setRestoredDraftKey] = useState<string | null>(null);
  const [savingPageEdit, setSavingPageEdit] = useState(false);
  const [pageMoveMode, setPageMoveMode] = useState(false);
  const [, setPageMoveParentPath] = useState("");
  const [, setPageMoveSlugLeaf] = useState("");
  const [, setPageMoveTitle] = useState("");
  const [, setPageMoveSummary] = useState("Page move/rename");
  const [, setPageMoveIncludeDescendants] = useState(true);
  const [, setMovingPage] = useState(false);
  const [draggingPageSlug, setDraggingPageSlug] = useState<string | null>(null);
  const [treeDropTargetSlug, setTreeDropTargetSlug] = useState<string | null>(null);
  const [pageReviewAssignments, setPageReviewAssignments] = useState<WikiPageReviewAssignmentItem[]>([]);
  const [loadingPageReviewAssignments, setLoadingPageReviewAssignments] = useState(false);
  const [assignmentAssigneeInput, setAssignmentAssigneeInput] = useState("");
  const [assignmentNoteInput, setAssignmentNoteInput] = useState("");
  const [savingPageAssignment, setSavingPageAssignment] = useState(false);
  const [runningLifecycleQuickAction, setRunningLifecycleQuickAction] = useState(false);
  const [spacePolicy, setSpacePolicy] = useState<WikiSpacePolicyPayload["policy"] | null>(null);
  const [loadingSpacePolicy, setLoadingSpacePolicy] = useState(false);
  const [savingSpacePolicy, setSavingSpacePolicy] = useState(false);
  const [spaceWriteMode, setSpaceWriteMode] = useState<"open" | "owners_only">("open");
  const [spaceCommentMode, setSpaceCommentMode] = useState<"open" | "owners_only">("open");
  const [spaceReviewRequired, setSpaceReviewRequired] = useState(false);
  const [spacePublishChecklistPreset, setSpacePublishChecklistPreset] = useState<PublishChecklistPresetKey>("none");
  const [spacePolicyAudit, setSpacePolicyAudit] = useState<WikiSpacePolicyAuditItem[]>([]);
  const [loadingSpacePolicyAudit, setLoadingSpacePolicyAudit] = useState(false);
  const [spacePolicyAdoptionSummaryApi, setSpacePolicyAdoptionSummaryApi] = useState<SpacePolicyAdoptionSummary | null>(null);
  const [loadingSpacePolicyAdoptionSummary, setLoadingSpacePolicyAdoptionSummary] = useState(false);
  const [gatekeeperConfig, setGatekeeperConfig] = useState<GatekeeperConfig | null>(null);
  const [, setLoadingGatekeeperConfig] = useState(false);
  const [, setPublishModeDefault] = useState<PublishMode>("auto_publish");
  const [, setBackfillLlmClassifierMode] = useState<"off" | "assist" | "enforce">("off");
  const [, setBackfillLlmClassifierMinConfidence] = useState("0.78");
  const [, setBackfillLlmClassifierAmbiguousOnly] = useState(true);
  const [, setBackfillLlmClassifierModel] = useState("");
  const [agentWorklogTimezone, setAgentWorklogTimezone] = useState("UTC");
  const [agentWorklogScheduleHour, setAgentWorklogScheduleHour] = useState("2");
  const [agentWorklogScheduleMinute, setAgentWorklogScheduleMinute] = useState("0");
  const [agentWorklogMinActivityScore, setAgentWorklogMinActivityScore] = useState("2");
  const [agentWorklogIncludeIdleDays, setAgentWorklogIncludeIdleDays] = useState(false);
  const [agentWorklogRealtimeEnabled, setAgentWorklogRealtimeEnabled] = useState(false);
  const [agentWorklogRealtimeLookbackMinutes, setAgentWorklogRealtimeLookbackMinutes] = useState("30");
  const [savingAgentWorklogPolicy, setSavingAgentWorklogPolicy] = useState(false);
  const [runningAgentWorklogSync, setRunningAgentWorklogSync] = useState(false);
  const [agentOrgchart, setAgentOrgchart] = useState<AgentOrgchartPayload | null>(null);
  const [loadingAgentOrgchart, setLoadingAgentOrgchart] = useState(false);
  const [agentOrgchartIncludeHandoffs, setAgentOrgchartIncludeHandoffs] = useState(true);
  const [notificationsInbox, setNotificationsInbox] = useState<WikiNotificationItem[]>([]);
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);
  const [loadingNotificationsInbox, setLoadingNotificationsInbox] = useState(false);
  const [savingNotificationState, setSavingNotificationState] = useState(false);
  const [guidedPageForm, setGuidedPageForm] = useState<GuidedPageFormState>(DEFAULT_GUIDED_PAGE_FORM);
  const [, setModerationThroughput] = useState<ModerationThroughputPayload | null>(null);
  const [, setLoadingModerationThroughput] = useState(false);
  const [wikiLifecycleStats, setWikiLifecycleStats] = useState<WikiLifecycleStatsPayload | null>(null);
  const [loadingWikiLifecycleStats, setLoadingWikiLifecycleStats] = useState(false);
  const [wikiLifecycleTelemetry, setWikiLifecycleTelemetry] = useState<WikiLifecycleTelemetryPayload | null>(null);
  const [loadingWikiLifecycleTelemetry, setLoadingWikiLifecycleTelemetry] = useState(false);
  const [lifecycleTelemetryActionKey, setLifecycleTelemetryActionKey] = useState<string | null>(null);
  const [wikiLifecycleTelemetryAction, setWikiLifecycleTelemetryAction] = useState<WikiLifecycleTelemetryPayload | null>(null);
  const [loadingWikiLifecycleTelemetryAction, setLoadingWikiLifecycleTelemetryAction] = useState(false);
  const [lifecycleQueryPreset, setLifecycleQueryPreset] = useState<LifecycleQueryPresetKey>("stale_21");
  const [lifecycleStaleDays, setLifecycleStaleDays] = useState(21);
  const [lifecycleCriticalDays, setLifecycleCriticalDays] = useState(45);
  const [lifecycleSpaceFilter, setLifecycleSpaceFilter] = useState<string>(LIFECYCLE_SPACE_FILTER_ALL);
  const [creatingPage, setCreatingPage] = useState(false);
  const [showCoreCreatePanel, setShowCoreCreatePanel] = useState(false);
  const [showRolesGuideModal, setShowRolesGuideModal] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishSummary, setPublishSummary] = useState("Publish page update");
  const [publishConfirmHighRisk, setPublishConfirmHighRisk] = useState(false);
  const [publishChecklistAcks, setPublishChecklistAcks] = useState<Record<string, boolean>>({});
  const [loadingProcessSimulation, setLoadingProcessSimulation] = useState(false);
  const [processSimulation, setProcessSimulation] = useState<WikiProcessSimulationPayload | null>(null);
  const [showQuickNavModal, setShowQuickNavModal] = useState(false);
  const [quickNavSlug, setQuickNavSlug] = useState<string | null>(null);
  const [quickNavQuery, setQuickNavQuery] = useState("");
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(1);
  const [selectedCreateTemplateKey, setSelectedCreateTemplateKey] = useState<string | null>(null);
  const [, setConflictExplain] = useState<ConflictExplainPayload | null>(null);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [, setLoadingPages] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingPageDetail, setLoadingPageDetail] = useState(false);
  const [, setLoadingConflictExplain] = useState(false);
  const [runningAction, setRunningAction] = useState(false);
  const [armedRiskActionKey, setArmedRiskActionKey] = useState<string | null>(null);
  const [approveForm, setApproveForm] = useState<ApproveFormState>(DEFAULT_APPROVE_FORM);
  const [rejectForm, setRejectForm] = useState<RejectFormState>(DEFAULT_REJECT_FORM);
  const [detailTab, setDetailTab] = useState<DetailTab>("semantic");
  const [selectedTocSectionKey, setSelectedTocSectionKey] = useState<string | null>(null);
  const [urlStateReady, setUrlStateReady] = useState(false);
  const [wikiUxMetrics, setWikiUxMetrics] = useState<WikiUxMetricsState>(() => ({
    sessionStartedMs: Date.now(),
    firstPageViewMs: null,
    firstPublishMs: null,
    pageOpenCount: 0,
    pageOpenCountAtFirstPublish: null,
    publishCount: 0,
  }));
  const [lifecycleAdvisorMetrics, setLifecycleAdvisorMetrics] = useState<LifecycleAdvisorMetricsState>(() => ({
    sessionId: randomKey(),
    sessionStartedMs: Date.now(),
    suggestionShown: 0,
    suggestionApplied: 0,
    staleShownAtBySlug: {},
    staleResolvedDurationsMs: [],
    emptyScopeActionShownByType: {},
    emptyScopeActionAppliedByType: {},
  }));
  const previousSelectedPageSlugRef = useRef<string | null>(null);
  const lifecycleSuggestionSeenRef = useRef<Record<string, string>>({});
  const lifecycleEmptyScopeSeenRef = useRef<Record<string, string>>({});
  const autoSpaceRecoverySeenRef = useRef<Record<string, string>>({});
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

  const spaceContentStats = useMemo(() => {
    const map = new Map<
      string,
      {
        key: string;
        pageCount: number;
        openCount: number;
        publishedCount: number;
        reviewedCount: number;
        draftLikeCount: number;
        latestActivityAt: string | null;
      }
    >();
    for (const page of pageNodes) {
      const key = pageGroupKey(page.slug);
      const current =
        map.get(key) || {
          key,
          pageCount: 0,
          openCount: 0,
          publishedCount: 0,
          reviewedCount: 0,
          draftLikeCount: 0,
          latestActivityAt: null,
        };
      current.pageCount += 1;
      current.openCount += page.open_count;
      if (page.status === "published") current.publishedCount += 1;
      if (page.status === "reviewed") current.reviewedCount += 1;
      if (page.status === "draft") current.draftLikeCount += 1;
      const activityAt = page.latest_draft_at || page.updated_at || page.created_at || null;
      if (activityTimestampMs(activityAt) > activityTimestampMs(current.latestActivityAt)) {
        current.latestActivityAt = activityAt;
      }
      map.set(key, current);
    }
    const ranked = [...map.values()].sort((a, b) => {
      if (a.publishedCount !== b.publishedCount) return b.publishedCount - a.publishedCount;
      if (a.openCount !== b.openCount) return b.openCount - a.openCount;
      if (a.pageCount !== b.pageCount) return b.pageCount - a.pageCount;
      const activityDelta = activityTimestampMs(b.latestActivityAt) - activityTimestampMs(a.latestActivityAt);
      if (activityDelta !== 0) return activityDelta;
      return a.key.localeCompare(b.key);
    });
    return {
      byKey: map,
      preferred: ranked[0] ?? null,
      ranked,
    };
  }, [pageNodes]);

  const lifecycleSpaceChips = useMemo(() => {
    if (!wikiLifecycleStats) return [] as Array<{ key: string; title: string; staleCount: number; criticalCount: number }>;
    const counts = new Map<string, { key: string; title: string; staleCount: number; criticalCount: number }>();
    const titleByKey = new Map(spaceNodes.map((item) => [item.key, item.title]));
    for (const item of wikiLifecycleStats.stale_pages) {
      const key = pageGroupKey(item.slug);
      const current = counts.get(key) || {
        key,
        title: titleByKey.get(key) || key,
        staleCount: 0,
        criticalCount: 0,
      };
      current.staleCount += 1;
      if (String(item.severity || "").trim().toLowerCase() === "critical") {
        current.criticalCount += 1;
      }
      counts.set(key, current);
    }
    return [...counts.values()].sort((a, b) => {
      if (a.criticalCount !== b.criticalCount) return b.criticalCount - a.criticalCount;
      if (a.staleCount !== b.staleCount) return b.staleCount - a.staleCount;
      return a.title.localeCompare(b.title);
    });
  }, [spaceNodes, wikiLifecycleStats]);

  const adoptionBundleSummary = useMemo(() => {
    const bundles = adoptionEvidenceBundles?.bundles || [];
    const counts = {
      total: bundles.length,
      ready: 0,
      candidate: 0,
      observed: 0,
      suppressed: 0,
    };
    const pageTypes = new Map<string, number>();
    for (const bundle of bundles) {
      const status = String(bundle.bundle_status || "").trim().toLowerCase();
      if (status === "ready") counts.ready += 1;
      else if (status === "candidate") counts.candidate += 1;
      else if (status === "observed") counts.observed += 1;
      else if (status === "suppressed") counts.suppressed += 1;
      const pageType = String(bundle.suggested_page_type || "operations").trim().toLowerCase() || "operations";
      pageTypes.set(pageType, Number(pageTypes.get(pageType) || 0) + 1);
    }
    const topPageTypes = [...pageTypes.entries()]
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => {
        if (a.count !== b.count) return b.count - a.count;
        return a.key.localeCompare(b.key);
      })
      .slice(0, 4);
    return {
      ...counts,
      topPageTypes,
    };
  }, [adoptionEvidenceBundles]);

  const lifecycleVisibleStalePages = useMemo(() => {
    if (!wikiLifecycleStats) return [] as WikiLifecycleStatsPayload["stale_pages"];
    if (!lifecycleSpaceFilter || lifecycleSpaceFilter === LIFECYCLE_SPACE_FILTER_ALL) {
      return wikiLifecycleStats.stale_pages;
    }
    return wikiLifecycleStats.stale_pages.filter((item) => pageGroupKey(item.slug) === lifecycleSpaceFilter);
  }, [lifecycleSpaceFilter, wikiLifecycleStats]);

  const lifecycleEmptyScope = useMemo(() => {
    if (!wikiLifecycleStats || wikiLifecycleStats.stale_pages.length > 0) return null;
    const candidate = wikiLifecycleStats.meta?.empty_scope;
    if (!candidate || typeof candidate !== "object") return null;
    return candidate;
  }, [wikiLifecycleStats]);
  const lifecycleEmptyScopeActions = useMemo(() => {
    if (!lifecycleEmptyScope || !Array.isArray(lifecycleEmptyScope.suggested_actions)) {
      return [] as Array<{ action: string; label: string; deep_link?: { core_tab?: string; wiki_focus?: string | null } }>;
    }
    const rawActions = lifecycleEmptyScope.suggested_actions as Array<{
      action?: string;
      label?: string;
      deep_link?: { core_tab?: string; wiki_focus?: string | null };
    }>;
    return rawActions
      .filter((item) => Boolean(item && typeof item === "object" && String(item.action || "").trim()))
      .map((item) => ({
        action: String(item.action || "").trim().toLowerCase(),
        label: String(item.label || item.action || "").trim() || "Action",
        deep_link: item.deep_link,
      }));
  }, [lifecycleEmptyScope]);

  const scopeSpaceKey = useMemo(() => {
    if (selectedSpaceKey) return selectedSpaceKey;
    return null;
  }, [selectedSpaceKey]);

  const scopeSpaceLabel = useMemo(() => {
    if (!scopeSpaceKey) return null;
    return spaceNodes.find((item) => item.key === scopeSpaceKey)?.title || scopeSpaceKey;
  }, [scopeSpaceKey, spaceNodes]);

  const scopePageLabel = useMemo(() => {
    if (!selectedPageSlug) return null;
    const fromDetail = selectedPageDetail?.page?.title;
    if (fromDetail) return fromDetail;
    return pageNodes.find((item) => item.slug === selectedPageSlug)?.title || selectedPageSlug;
  }, [pageNodes, selectedPageDetail, selectedPageSlug]);

  const applyLifecycleQueryPreset = useCallback((preset: LifecycleQueryPresetKey) => {
    const nextPreset = LIFECYCLE_QUERY_PRESETS.find((item) => item.key === preset);
    if (!nextPreset) return;
    setLifecycleQueryPreset(nextPreset.key);
    if (nextPreset.key !== "custom") {
      setLifecycleStaleDays(nextPreset.staleDays);
      setLifecycleCriticalDays(nextPreset.criticalDays);
    }
  }, []);
  const toggleLifecycleTelemetryActionDrilldown = useCallback((actionKey: string) => {
    const normalized = normalizeTelemetryActionKey(actionKey);
    if (!normalized) return;
    setLifecycleTelemetryActionKey((prev) => (prev === normalized ? null : normalized));
    window.requestAnimationFrame(() => {
      scrollElementIntoViewWithRetry("wiki-lifecycle-action-detail", 8, 120);
    });
  }, []);

  const runLifecycleEmptyScopeAction = useCallback(
    (
      action: string,
      deepLink?: {
        core_tab?: "wiki" | "drafts" | "tasks" | string;
        wiki_focus?: string | null;
      },
    ) => {
      const deepLinkTab = String(deepLink?.core_tab || "")
        .trim()
        .toLowerCase();
      if (deepLinkTab === "wiki" || deepLinkTab === "drafts" || deepLinkTab === "tasks") {
        setCoreWorkspaceTab(deepLinkTab as CoreWorkspaceTab);
      }
      const focus = String(deepLink?.wiki_focus || "")
        .trim()
        .toLowerCase();
      if (focus === "draft_inbox") {
        scrollElementIntoViewWithRetry("wiki-draft-inbox", 10, 120);
      } else if (focus === "policy_timeline") {
        scrollElementIntoViewWithRetry("wiki-policy-timeline", 10, 120);
      } else if (focus === "policy_edit") {
        scrollElementIntoViewWithRetry("wiki-governance-panel", 10, 120);
      }
      const normalized = String(action || "").trim().toLowerCase();
      if (normalized) {
        setLifecycleAdvisorMetrics((prev) => ({
          ...prev,
          emptyScopeActionAppliedByType: {
            ...prev.emptyScopeActionAppliedByType,
            [normalized]: (prev.emptyScopeActionAppliedByType[normalized] || 0) + 1,
          },
        }));
      }
      if (normalized === "create_page") {
        setCoreWorkspaceTab("wiki");
        setShowCoreCreatePanel(true);
        return;
      }
      if (normalized === "review_open_drafts") {
        setCoreWorkspaceTab("drafts");
        return;
      }
      if (normalized === "lower_threshold") {
        applyLifecycleQueryPreset("stale_21");
      }
    },
    [applyLifecycleQueryPreset],
  );

  useEffect(() => {
    if (!selectedSpaceKey) {
      setLifecycleSpaceFilter(LIFECYCLE_SPACE_FILTER_ALL);
      return;
    }
    setLifecycleSpaceFilter(selectedSpaceKey);
  }, [selectedSpaceKey]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project || !lifecycleEmptyScope || lifecycleEmptyScopeActions.length === 0) return;
    const scopeSignature = `${project}::${selectedSpaceKey || "all"}::${lifecycleEmptyScope.code}::${lifecycleEmptyScopeActions
      .map((item) => item.action)
      .join("|")}`;
    if (lifecycleEmptyScopeSeenRef.current[scopeSignature]) return;
    lifecycleEmptyScopeSeenRef.current[scopeSignature] = "seen";
    setLifecycleAdvisorMetrics((prev) => {
      const nextShown = { ...prev.emptyScopeActionShownByType };
      for (const item of lifecycleEmptyScopeActions) {
        const action = String(item.action || "").trim().toLowerCase();
        if (!action) continue;
        nextShown[action] = (nextShown[action] || 0) + 1;
      }
      return {
        ...prev,
        emptyScopeActionShownByType: nextShown,
      };
    });
  }, [lifecycleEmptyScope, lifecycleEmptyScopeActions, projectId, selectedSpaceKey]);

  useEffect(() => {
    if (!wikiLifecycleStats) {
      setLifecycleSpaceFilter(LIFECYCLE_SPACE_FILTER_ALL);
      return;
    }
    if (!lifecycleSpaceFilter || lifecycleSpaceFilter === LIFECYCLE_SPACE_FILTER_ALL) {
      return;
    }
    const exists = wikiLifecycleStats.stale_pages.some((item) => pageGroupKey(item.slug) === lifecycleSpaceFilter);
    if (!exists) {
      setLifecycleSpaceFilter(LIFECYCLE_SPACE_FILTER_ALL);
    }
  }, [lifecycleSpaceFilter, wikiLifecycleStats]);

  const legacySelectedProfile = useMemo(
    () => legacyProfiles.find((item) => item.profile === legacySqlProfile) || null,
    [legacyProfiles, legacySqlProfile],
  );
  const selectedAdoptionConnector = useMemo(
    () => adoptionImportConnectors.find((item) => item.id === selectedConnectorId) || resolvedConnector || null,
    [adoptionImportConnectors, resolvedConnector, selectedConnectorId],
  );

  const scopedDrafts = useMemo(
    () =>
      drafts.filter((item) => {
        if (selectedPageSlug && item.page.slug !== selectedPageSlug) return false;
        if (selectedSpaceKey && pageGroupKey(item.page.slug) !== selectedSpaceKey) return false;
        if (
          draftRecommendationFilter !== "all" &&
          String(item.bundle_priority?.recommendation || "").trim().toLowerCase() !== draftRecommendationFilter
        ) {
          return false;
        }
        const draftNeedle = draftFilter.trim().toLowerCase();
        if (!draftNeedle) return true;
        const haystack = `${item.page.title || ""} ${item.page.slug || ""} ${item.decision} ${item.section_key || ""}`.toLowerCase();
        return haystack.includes(draftNeedle);
      }),
    [draftFilter, draftRecommendationFilter, drafts, selectedPageSlug, selectedSpaceKey],
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

  const safeBulkApproveSkippedCount = useMemo(
    () =>
      visibleDrafts.filter(
        (item) => isOpenReviewDraft(item) && !item.has_open_conflict && !draftPassesDefaultBundleGuard(item),
      ).length,
    [visibleDrafts],
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
      for (const key of LEGACY_STORAGE_KEYS) {
        window.localStorage.removeItem(key);
      }
    } catch {
      // ignore storage access failures
    }
  }, []);

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
        lifecycleTelemetryActionKey?: string | null;
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
      if (typeof parsed.lifecycleTelemetryActionKey === "string" || parsed.lifecycleTelemetryActionKey === null) {
        const normalizedActionKey = normalizeTelemetryActionKey(String(parsed.lifecycleTelemetryActionKey || ""));
        setLifecycleTelemetryActionKey(normalizedActionKey || null);
      }
    } catch {
      // ignore corrupt local storage
    }
  }, []);

  useEffect(() => {
    try {
      const pathState = parseWikiPath(window.location.pathname);
      setWikiBasePath(pathState.basePath);
      setCoreWorkspaceRoute(pathState.route);
      if (pathState.pageSlug) {
        setSelectedPageSlug(pathState.pageSlug);
        setSelectedSpaceKey(pageGroupKey(pathState.pageSlug));
        setCoreWorkspaceTab("wiki");
      }

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
      if (pathState.route === "wiki" && !pathState.pageSlug && pageParam) {
        setSelectedPageSlug(pageParam);
        setSelectedSpaceKey(pageGroupKey(pageParam));
        setCoreWorkspaceTab("wiki");
      }
      const coreTabParam = String(params.get("core_tab") || "").trim().toLowerCase();
      if (coreTabParam === "wiki" || coreTabParam === "drafts" || coreTabParam === "tasks") {
        setCoreWorkspaceTab(coreTabParam as CoreWorkspaceTab);
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
      const lifecyclePresetParam = String(params.get("wiki_lifecycle_preset") || "")
        .trim()
        .toLowerCase() as LifecycleQueryPresetKey;
      if (lifecyclePresetParam === "stale_21" || lifecyclePresetParam === "critical_45" || lifecyclePresetParam === "custom") {
        setLifecycleQueryPreset(lifecyclePresetParam);
      }
      const lifecycleStaleParamRaw = Number(params.get("wiki_lifecycle_stale_days"));
      if (Number.isFinite(lifecycleStaleParamRaw)) {
        setLifecycleStaleDays(Math.max(1, Math.min(365, Math.round(lifecycleStaleParamRaw))));
      }
      const lifecycleCriticalParamRaw = Number(params.get("wiki_lifecycle_critical_days"));
      if (Number.isFinite(lifecycleCriticalParamRaw)) {
        setLifecycleCriticalDays(Math.max(1, Math.min(365, Math.round(lifecycleCriticalParamRaw))));
      }
      const lifecycleActionParam = normalizeTelemetryActionKey(String(params.get("wiki_lifecycle_action") || ""));
      if (lifecycleActionParam) {
        setLifecycleTelemetryActionKey(lifecycleActionParam);
      }
      const focusParam = String(params.get("wiki_focus") || "").trim().toLowerCase();
      if (focusParam === "draft_inbox") {
        setCoreWorkspaceRoute("wiki");
        setCoreWorkspaceTab("drafts");
        scrollElementIntoViewWithRetry("wiki-draft-inbox", 12, 140);
      } else if (focusParam === "policy_timeline") {
        setCoreWorkspaceRoute("wiki");
        setCoreWorkspaceTab("wiki");
        scrollElementIntoViewWithRetry("wiki-policy-timeline", 12, 140);
      } else if (focusParam === "policy_edit") {
        setCoreWorkspaceRoute("wiki");
        setCoreWorkspaceTab("wiki");
        scrollElementIntoViewWithRetry("wiki-governance-panel", 12, 140);
      } else if (focusParam === "review_assignments") {
        setCoreWorkspaceRoute("wiki");
        setCoreWorkspaceTab("wiki");
        scrollElementIntoViewWithRetry("wiki-review-assignments", 12, 140);
      }
      if (projectParam) {
        if (!params.has("wiki_space")) setSelectedSpaceKey(null);
        if (!params.has("wiki_status")) setPageStatusFilter(null);
        if (!params.has("wiki_updated_by")) setPageUpdatedByFilter("");
        if (!params.has("wiki_with_open_drafts")) setOpenPagesOnly(false);
        if (!params.has("wiki_q")) setPageFilter("");
        if (!params.has("wiki_lifecycle_preset")) {
          setLifecycleQueryPreset("stale_21");
        }
        if (!params.has("wiki_lifecycle_stale_days")) {
          setLifecycleStaleDays(21);
        }
        if (!params.has("wiki_lifecycle_critical_days")) {
          setLifecycleCriticalDays(45);
        }
        if (!params.has("wiki_lifecycle_action")) {
          setLifecycleTelemetryActionKey(null);
        }
      }
    } catch {
      // ignore invalid URL params
    } finally {
      setUrlStateReady(true);
    }
  }, []);

  useEffect(() => {
    if (coreWorkspaceRoute !== "operations") return;
    if (coreWorkspaceTab !== "drafts") {
      setCoreWorkspaceTab("drafts");
    }
  }, [coreWorkspaceRoute, coreWorkspaceTab]);

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
    setOrDelete("core_tab", coreWorkspaceTab !== "wiki" ? coreWorkspaceTab : null);
    setOrDelete("wiki_status", pageStatusFilter || null);
    setOrDelete("wiki_updated_by", pageUpdatedByFilter.trim() || null);
    setOrDelete("wiki_with_open_drafts", openPagesOnly ? "true" : null);
    setOrDelete("wiki_q", pageFilter.trim() || null);
    setOrDelete("wiki_lifecycle_preset", lifecycleQueryPreset || null);
    setOrDelete("wiki_lifecycle_stale_days", String(Math.max(1, Math.min(365, Math.round(lifecycleStaleDays)))));
    setOrDelete("wiki_lifecycle_critical_days", String(Math.max(1, Math.min(365, Math.round(lifecycleCriticalDays)))));
    setOrDelete("wiki_lifecycle_action", lifecycleTelemetryActionKey || null);
    setOrDelete("wiki_focus", null);
    const nextSearch = params.toString();
    const currentSearch = window.location.search.replace(/^\?/, "");
    const nextPathname = buildWorkspacePath(wikiBasePath, coreWorkspaceRoute, selectedPageSlug);
    if (nextSearch === currentSearch && window.location.pathname === nextPathname) {
      return;
    }
    const nextUrl = `${nextPathname}${nextSearch ? `?${nextSearch}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }, [
    openPagesOnly,
    pageFilter,
    pageStatusFilter,
    pageUpdatedByFilter,
    lifecycleCriticalDays,
    lifecycleTelemetryActionKey,
    lifecycleQueryPreset,
    lifecycleStaleDays,
    projectId,
    coreWorkspaceRoute,
    coreWorkspaceTab,
    selectedPageSlug,
    selectedSpaceKey,
    urlStateReady,
    wikiBasePath,
  ]);

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
        lifecycleTelemetryActionKey,
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
    lifecycleTelemetryActionKey,
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

  const loadWikiLifecycleStats = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setWikiLifecycleStats(null);
      return;
    }
    const scopedSpaceKey = String(selectedSpaceKey || "").trim();
    const staleDays = Math.max(1, Math.min(365, Math.trunc(Number(lifecycleStaleDays || 21))));
    const criticalDays = Math.max(staleDays, Math.min(365, Math.trunc(Number(lifecycleCriticalDays || 45))));
    setLoadingWikiLifecycleStats(true);
    try {
      const params = new URLSearchParams();
      params.set("project_id", project);
      params.set("stale_days", String(staleDays));
      params.set("critical_days", String(criticalDays));
      params.set("stale_limit", "20");
      if (scopedSpaceKey) {
        params.set("space_key", scopedSpaceKey);
      }
      const payload = await apiFetch<WikiLifecycleStatsPayload>(
        apiUrl,
        `/v1/wiki/lifecycle/stats?${params.toString()}`,
      );
      setWikiLifecycleStats(payload);
    } catch {
      setWikiLifecycleStats(null);
    } finally {
      setLoadingWikiLifecycleStats(false);
    }
  }, [apiUrl, lifecycleCriticalDays, lifecycleStaleDays, projectId, selectedSpaceKey]);

  useEffect(() => {
    if (!projectId.trim()) {
      setWikiLifecycleStats(null);
      return;
    }
    void loadWikiLifecycleStats();
  }, [loadWikiLifecycleStats, projectId]);

  const loadWikiLifecycleTelemetry = useCallback(
    async (opts?: { silent?: boolean }) => {
      const project = projectId.trim();
      if (!project) {
        setWikiLifecycleTelemetry(null);
        return;
      }
      if (!opts?.silent) {
        setLoadingWikiLifecycleTelemetry(true);
      }
      try {
        const payload = await apiFetch<WikiLifecycleTelemetryPayload>(
          apiUrl,
          `/v1/wiki/lifecycle/telemetry?project_id=${encodeURIComponent(project)}&days=${LIFECYCLE_TELEMETRY_WINDOW_DAYS}`,
        );
        setWikiLifecycleTelemetry(payload);
      } catch {
        if (!opts?.silent) {
          setWikiLifecycleTelemetry(null);
        }
      } finally {
        if (!opts?.silent) {
          setLoadingWikiLifecycleTelemetry(false);
        }
      }
    },
    [apiUrl, projectId],
  );

  const loadWikiLifecycleTelemetryByAction = useCallback(
    async (actionKey: string, opts?: { silent?: boolean }) => {
      const project = projectId.trim();
      const normalizedActionKey = normalizeTelemetryActionKey(actionKey);
      if (!project || !normalizedActionKey) {
        setWikiLifecycleTelemetryAction(null);
        return;
      }
      if (!opts?.silent) {
        setLoadingWikiLifecycleTelemetryAction(true);
      }
      try {
        const payload = await apiFetch<WikiLifecycleTelemetryPayload>(
          apiUrl,
          `/v1/wiki/lifecycle/telemetry?project_id=${encodeURIComponent(project)}&days=${LIFECYCLE_TELEMETRY_WINDOW_DAYS}&action_key=${encodeURIComponent(normalizedActionKey)}`,
        );
        setWikiLifecycleTelemetryAction(payload);
      } catch {
        if (!opts?.silent) {
          setWikiLifecycleTelemetryAction(null);
        }
      } finally {
        if (!opts?.silent) {
          setLoadingWikiLifecycleTelemetryAction(false);
        }
      }
    },
    [apiUrl, projectId],
  );

  useEffect(() => {
    if (!projectId.trim()) {
      setWikiLifecycleTelemetry(null);
      setWikiLifecycleTelemetryAction(null);
      return;
    }
    void loadWikiLifecycleTelemetry();
    if (lifecycleTelemetryActionKey) {
      void loadWikiLifecycleTelemetryByAction(lifecycleTelemetryActionKey);
    } else {
      setWikiLifecycleTelemetryAction(null);
    }
    const timer = window.setInterval(() => {
      void loadWikiLifecycleTelemetry({ silent: true });
      if (lifecycleTelemetryActionKey) {
        void loadWikiLifecycleTelemetryByAction(lifecycleTelemetryActionKey, { silent: true });
      }
    }, 30000);
    return () => {
      window.clearInterval(timer);
    };
  }, [loadWikiLifecycleTelemetry, loadWikiLifecycleTelemetryByAction, lifecycleTelemetryActionKey, projectId]);

  const loadWikiPages = useCallback(
    async (opts?: { silent?: boolean }) => {
      const project = projectId.trim();
      if (!project) {
        setWikiPages([]);
        setWikiLifecycleStats(null);
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
    [apiUrl, loadWikiLifecycleStats, openPagesOnly, pageStatusFilter, pageUpdatedByFilter, projectId],
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
    setDraftQueueSummary(null);
    const throughputPromise = showExpertModerationControls ? loadModerationThroughput() : Promise.resolve();
    if (!showExpertModerationControls) {
      setModerationThroughput(null);
    }
    try {
      const statusQuery = status ? `&status=${encodeURIComponent(status)}` : "";
      const data = await apiFetch<{ drafts: DraftSummary[]; queue_summary?: DraftQueueSummary }>(
        apiUrl,
        `/v1/wiki/drafts?project_id=${encodeURIComponent(projectId)}${statusQuery}&limit=120`,
      );
      setDrafts(data.drafts ?? []);
      setDraftQueueSummary(data.queue_summary ?? null);
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
        const metadata = payload.policy.metadata && typeof payload.policy.metadata === "object" ? payload.policy.metadata : {};
        const presetRaw = String((metadata as Record<string, unknown>).publish_checklist_preset || "").trim().toLowerCase();
        if (presetRaw === "ops_standard" || presetRaw === "policy_strict") {
          setSpacePublishChecklistPreset(presetRaw);
        } else {
          setSpacePublishChecklistPreset("none");
        }
      } catch {
        setSpacePolicy(null);
        setSpacePublishChecklistPreset("none");
      } finally {
        setLoadingSpacePolicy(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadSpacePolicyAudit = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setSpacePolicyAudit([]);
        return;
      }
      setLoadingSpacePolicyAudit(true);
      try {
        const spaceKey = pageGroupKey(slug).toLowerCase();
        const payload = await apiFetch<WikiSpacePolicyAuditPayload>(
          apiUrl,
          `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/policy/audit?project_id=${encodeURIComponent(projectId)}&limit=30`,
        );
        setSpacePolicyAudit(payload.entries ?? []);
      } catch {
        setSpacePolicyAudit([]);
      } finally {
        setLoadingSpacePolicyAudit(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadSpacePolicyAdoptionSummary = useCallback(
    async (slug: string) => {
      if (!projectId.trim() || !slug.trim()) {
        setLoadingSpacePolicyAdoptionSummary(false);
        setSpacePolicyAdoptionSummaryApi(null);
        return;
      }
      setLoadingSpacePolicyAdoptionSummary(true);
      try {
        const spaceKey = pageGroupKey(slug).toLowerCase();
        const payload = await apiFetch<WikiSpacePolicyAdoptionSummaryPayload>(
          apiUrl,
          `/v1/wiki/spaces/${encodeURIComponent(spaceKey)}/policy/adoption-summary?project_id=${encodeURIComponent(projectId)}&limit=200`,
        );
        const summaryRaw = payload.summary && typeof payload.summary === "object" ? payload.summary : null;
        if (!summaryRaw) {
          setSpacePolicyAdoptionSummaryApi(null);
          return;
        }
        const checklistUsageRaw =
          summaryRaw.checklist_usage && typeof summaryRaw.checklist_usage === "object" ? summaryRaw.checklist_usage : {};
        setSpacePolicyAdoptionSummaryApi({
          totalUpdates: Math.max(0, Number(summaryRaw.total_updates || 0)),
          uniqueActors: Math.max(0, Number(summaryRaw.unique_actors || 0)),
          topActor: summaryRaw.top_actor ? String(summaryRaw.top_actor) : null,
          topActorUpdates: Math.max(0, Number(summaryRaw.top_actor_updates || 0)),
          avgCadenceDays:
            summaryRaw.avg_update_interval_days == null || !Number.isFinite(Number(summaryRaw.avg_update_interval_days))
              ? null
              : Number(summaryRaw.avg_update_interval_days),
          checklistUsage: {
            none: Math.max(0, Number((checklistUsageRaw as Record<string, unknown>).none || 0)),
            ops_standard: Math.max(0, Number((checklistUsageRaw as Record<string, unknown>).ops_standard || 0)),
            policy_strict: Math.max(0, Number((checklistUsageRaw as Record<string, unknown>).policy_strict || 0)),
          },
          checklistTransitions: Math.max(0, Number(summaryRaw.checklist_transitions || 0)),
          firstUpdatedAt: summaryRaw.first_updated_at ? String(summaryRaw.first_updated_at) : null,
          lastUpdatedAt: summaryRaw.last_updated_at ? String(summaryRaw.last_updated_at) : null,
        });
      } catch {
        setSpacePolicyAdoptionSummaryApi(null);
      } finally {
        setLoadingSpacePolicyAdoptionSummary(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadGatekeeperConfig = useCallback(async () => {
    if (!projectId.trim()) {
      setGatekeeperConfig(null);
      setPublishModeDefault("auto_publish");
      setBackfillLlmClassifierMode("off");
      setBackfillLlmClassifierMinConfidence("0.78");
      setBackfillLlmClassifierAmbiguousOnly(true);
      setBackfillLlmClassifierModel("");
      setAgentWorklogTimezone("UTC");
      setAgentWorklogScheduleHour("2");
      setAgentWorklogScheduleMinute("0");
      setAgentWorklogMinActivityScore("2");
      setAgentWorklogIncludeIdleDays(false);
      setAgentWorklogRealtimeEnabled(false);
      setAgentWorklogRealtimeLookbackMinutes("30");
      return;
    }
    setLoadingGatekeeperConfig(true);
    try {
      const payload = await apiFetch<GatekeeperConfigPayload>(
        apiUrl,
        `/v1/gatekeeper/config?project_id=${encodeURIComponent(projectId)}`,
      );
      const nextConfig = payload.config;
      const routingPolicy =
        nextConfig.routing_policy && typeof nextConfig.routing_policy === "object" ? nextConfig.routing_policy : {};
      const llmModeRaw = String(routingPolicy.backfill_llm_classifier_mode || "off").trim().toLowerCase();
      const llmMode = llmModeRaw === "assist" || llmModeRaw === "enforce" ? llmModeRaw : "off";
      const llmMinConfidenceRaw = Number(routingPolicy.backfill_llm_classifier_min_confidence);
      const llmMinConfidence = Number.isFinite(llmMinConfidenceRaw)
        ? Math.max(0, Math.min(1, llmMinConfidenceRaw))
        : 0.78;
      const llmModel = String(routingPolicy.backfill_llm_classifier_model || "").trim();
      const worklogTimezone = String(routingPolicy.agent_worklog_timezone || "UTC").trim() || "UTC";
      const worklogScheduleHourRaw = Number(routingPolicy.agent_worklog_schedule_hour_local);
      const worklogScheduleMinuteRaw = Number(routingPolicy.agent_worklog_schedule_minute_local);
      const worklogMinActivityScoreRaw = Number(routingPolicy.agent_worklog_min_activity_score);
      const worklogRealtimeLookbackRaw = Number(routingPolicy.agent_worklog_realtime_lookback_minutes);
      const worklogScheduleHour = Number.isFinite(worklogScheduleHourRaw)
        ? Math.max(0, Math.min(23, Math.round(worklogScheduleHourRaw)))
        : 2;
      const worklogScheduleMinute = Number.isFinite(worklogScheduleMinuteRaw)
        ? Math.max(0, Math.min(59, Math.round(worklogScheduleMinuteRaw)))
        : 0;
      const worklogMinActivityScore = Number.isFinite(worklogMinActivityScoreRaw)
        ? Math.max(0, Math.min(100, Math.round(worklogMinActivityScoreRaw)))
        : 2;
      const worklogRealtimeLookback = Number.isFinite(worklogRealtimeLookbackRaw)
        ? Math.max(5, Math.min(720, Math.round(worklogRealtimeLookbackRaw)))
        : 30;
      setGatekeeperConfig(nextConfig);
      setBackfillLlmClassifierMode(llmMode);
      setBackfillLlmClassifierMinConfidence(llmMinConfidence.toFixed(2));
      setBackfillLlmClassifierAmbiguousOnly(routingPolicy.backfill_llm_classifier_ambiguous_only !== false);
      setBackfillLlmClassifierModel(llmModel);
      setAgentWorklogTimezone(worklogTimezone);
      setAgentWorklogScheduleHour(String(worklogScheduleHour));
      setAgentWorklogScheduleMinute(String(worklogScheduleMinute));
      setAgentWorklogMinActivityScore(String(worklogMinActivityScore));
      setAgentWorklogIncludeIdleDays(routingPolicy.agent_worklog_include_idle_days === true);
      setAgentWorklogRealtimeEnabled(routingPolicy.agent_worklog_realtime_enabled === true);
      setAgentWorklogRealtimeLookbackMinutes(String(worklogRealtimeLookback));
      if (
        nextConfig.publish_mode_default === "human_required" ||
        nextConfig.publish_mode_default === "conditional" ||
        nextConfig.publish_mode_default === "auto_publish"
      ) {
        setPublishModeDefault(nextConfig.publish_mode_default);
      } else {
        setPublishModeDefault("auto_publish");
      }
    } catch {
      setGatekeeperConfig(null);
      setPublishModeDefault("auto_publish");
      setBackfillLlmClassifierMode("off");
      setBackfillLlmClassifierMinConfidence("0.78");
      setBackfillLlmClassifierAmbiguousOnly(true);
      setBackfillLlmClassifierModel("");
      setAgentWorklogTimezone("UTC");
      setAgentWorklogScheduleHour("2");
      setAgentWorklogScheduleMinute("0");
      setAgentWorklogMinActivityScore("2");
      setAgentWorklogIncludeIdleDays(false);
      setAgentWorklogRealtimeEnabled(false);
      setAgentWorklogRealtimeLookbackMinutes("30");
    } finally {
      setLoadingGatekeeperConfig(false);
    }
  }, [apiUrl, projectId]);

  const loadAgentOrgchart = useCallback(
    async (opts?: { silent?: boolean }) => {
      const project = projectId.trim();
      if (!project) {
        setAgentOrgchart(null);
        return;
      }
      setLoadingAgentOrgchart(true);
      try {
        const payload = await apiFetch<AgentOrgchartPayload>(
          apiUrl,
          `/v1/agents/orgchart?project_id=${encodeURIComponent(project)}&include_handoffs=${
            agentOrgchartIncludeHandoffs ? "true" : "false"
          }&include_retired=false&max_agents=1000&max_edges=2000`,
        );
        setAgentOrgchart(payload);
      } catch (error) {
        setAgentOrgchart(null);
        if (!opts?.silent) {
          notifications.show({
            color: "red",
            title: "Failed to load orgchart",
            message: String(error),
          });
        }
      } finally {
        setLoadingAgentOrgchart(false);
      }
    },
    [agentOrgchartIncludeHandoffs, apiUrl, projectId],
  );

  const saveAgentWorklogPolicy = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before saving worklog policy.",
      });
      return;
    }
    if (!gatekeeperConfig) {
      notifications.show({
        color: "orange",
        title: "Policy not loaded",
        message: "Loading latest gatekeeper config first.",
      });
      await loadGatekeeperConfig();
      return;
    }

    const scheduleHourRaw = Number.parseInt(agentWorklogScheduleHour, 10);
    const scheduleMinuteRaw = Number.parseInt(agentWorklogScheduleMinute, 10);
    const minActivityRaw = Number.parseInt(agentWorklogMinActivityScore, 10);
    const lookbackRaw = Number.parseInt(agentWorklogRealtimeLookbackMinutes, 10);
    const scheduleHour = Number.isFinite(scheduleHourRaw) ? Math.max(0, Math.min(23, scheduleHourRaw)) : 2;
    const scheduleMinute = Number.isFinite(scheduleMinuteRaw) ? Math.max(0, Math.min(59, scheduleMinuteRaw)) : 0;
    const minActivityScore = Number.isFinite(minActivityRaw) ? Math.max(0, Math.min(100, minActivityRaw)) : 2;
    const realtimeLookbackMinutes = Number.isFinite(lookbackRaw) ? Math.max(5, Math.min(720, lookbackRaw)) : 30;
    const timezone = agentWorklogTimezone.trim() || "UTC";
    const existingRoutingPolicy =
      gatekeeperConfig.routing_policy && typeof gatekeeperConfig.routing_policy === "object"
        ? gatekeeperConfig.routing_policy
        : {};
    const nextRoutingPolicy = {
      ...existingRoutingPolicy,
      agent_worklog_timezone: timezone,
      agent_worklog_schedule_hour_local: scheduleHour,
      agent_worklog_schedule_minute_local: scheduleMinute,
      agent_worklog_min_activity_score: minActivityScore,
      agent_worklog_include_idle_days: agentWorklogIncludeIdleDays,
      agent_worklog_realtime_enabled: agentWorklogRealtimeEnabled,
      agent_worklog_realtime_lookback_minutes: realtimeLookbackMinutes,
    };

    setSavingAgentWorklogPolicy(true);
    try {
      const payload = await apiFetch<GatekeeperConfigPayload>(apiUrl, "/v1/gatekeeper/config", {
        method: "PUT",
        body: {
          project_id: project,
          min_sources_for_golden: gatekeeperConfig.min_sources_for_golden,
          conflict_free_days: gatekeeperConfig.conflict_free_days,
          min_score_for_golden: gatekeeperConfig.min_score_for_golden,
          operational_short_text_len: gatekeeperConfig.operational_short_text_len,
          operational_short_token_len: gatekeeperConfig.operational_short_token_len,
          llm_assist_enabled: gatekeeperConfig.llm_assist_enabled,
          llm_provider: gatekeeperConfig.llm_provider,
          llm_model: gatekeeperConfig.llm_model,
          llm_score_weight: gatekeeperConfig.llm_score_weight,
          llm_min_confidence: gatekeeperConfig.llm_min_confidence,
          llm_timeout_ms: gatekeeperConfig.llm_timeout_ms,
          publish_mode_default: gatekeeperConfig.publish_mode_default,
          publish_mode_by_category: gatekeeperConfig.publish_mode_by_category,
          auto_publish_min_score: gatekeeperConfig.auto_publish_min_score,
          auto_publish_min_sources: gatekeeperConfig.auto_publish_min_sources,
          auto_publish_require_golden: gatekeeperConfig.auto_publish_require_golden,
          auto_publish_allow_conflicts: gatekeeperConfig.auto_publish_allow_conflicts,
          routing_policy: nextRoutingPolicy,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      setGatekeeperConfig(payload.config);
      notifications.show({
        color: "teal",
        title: "Worklog policy saved",
        message: `Timezone ${timezone}, schedule ${String(scheduleHour).padStart(2, "0")}:${String(scheduleMinute).padStart(2, "0")}.`,
      });
      await loadGatekeeperConfig();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Could not save worklog policy",
        message: String(error),
      });
    } finally {
      setSavingAgentWorklogPolicy(false);
    }
  }, [
    agentWorklogIncludeIdleDays,
    agentWorklogMinActivityScore,
    agentWorklogRealtimeEnabled,
    agentWorklogRealtimeLookbackMinutes,
    agentWorklogScheduleHour,
    agentWorklogScheduleMinute,
    agentWorklogTimezone,
    apiUrl,
    gatekeeperConfig,
    loadGatekeeperConfig,
    projectId,
    reviewer,
  ]);

  const runAgentWorklogSyncNow = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before syncing worklogs.",
      });
      return;
    }
    const minActivityRaw = Number.parseInt(agentWorklogMinActivityScore, 10);
    const minActivityScore = Number.isFinite(minActivityRaw) ? Math.max(0, Math.min(100, minActivityRaw)) : 2;
    setRunningAgentWorklogSync(true);
    try {
      const payload = await apiFetch<{
        profiles_with_updates?: number;
        worklogs_generated?: number;
        timezone?: string;
        skipped_idle?: number;
      }>(apiUrl, "/v1/agents/worklogs/sync", {
        method: "POST",
        body: {
          project_id: project,
          generated_by: reviewer.trim() || "web_ui",
          days_back: 1,
          max_agents: 200,
          timezone: agentWorklogTimezone.trim() || "UTC",
          include_idle_days: agentWorklogIncludeIdleDays,
          min_activity_score: minActivityScore,
          trigger_mode: "manual",
          trigger_reason: "operations_ui_sync_now",
        },
      });
      notifications.show({
        color: "teal",
        title: "Worklogs synced",
        message: `Updated profiles: ${Number(payload.profiles_with_updates || 0)} • entries: ${Number(payload.worklogs_generated || 0)} • tz: ${String(payload.timezone || "UTC")}`,
      });
      void loadAgentOrgchart({ silent: true });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Sync failed",
        message: String(error),
      });
    } finally {
      setRunningAgentWorklogSync(false);
    }
  }, [
    agentWorklogIncludeIdleDays,
    agentWorklogMinActivityScore,
    agentWorklogTimezone,
    apiUrl,
    loadAgentOrgchart,
    projectId,
    reviewer,
  ]);

  const loadLegacyImportProfiles = useCallback(async () => {
    setLoadingLegacyProfiles(true);
    try {
      const payload = await apiFetch<LegacyImportProfilesPayload>(
        apiUrl,
        "/v1/legacy-import/profiles?source_type=postgres_sql",
      );
      const nextProfiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      setLegacyProfiles(nextProfiles);
      if (nextProfiles.length > 0) {
        const hasCurrent = nextProfiles.some((item) => item.profile === legacySqlProfile);
        if (!hasCurrent) {
          setLegacySqlProfile(nextProfiles[0].profile);
        }
      }
    } catch {
      setLegacyProfiles([]);
    } finally {
      setLoadingLegacyProfiles(false);
    }
  }, [apiUrl, legacySqlProfile]);

  const loadAdoptionImportConnectors = useCallback(async () => {
    try {
      const [postgresPayload, memoryApiPayload] = await Promise.all([
        apiFetch<AdoptionImportConnectorsPayload>(apiUrl, "/v1/adoption/import-connectors?source_type=postgres_sql"),
        apiFetch<AdoptionImportConnectorsPayload>(apiUrl, "/v1/adoption/import-connectors?source_type=memory_api"),
      ]);
      const connectors = [
        ...(Array.isArray(postgresPayload.connectors) ? postgresPayload.connectors : []),
        ...(Array.isArray(memoryApiPayload.connectors) ? memoryApiPayload.connectors : []),
      ];
      setAdoptionImportConnectors(connectors);
      if (connectors.length > 0 && !selectedConnectorId) {
        const preferred = connectors.find((item) => item.profile === legacySqlProfile && item.sync_mode === "polling");
        setSelectedConnectorId((preferred || connectors[0]).id);
      }
    } catch {
      setAdoptionImportConnectors([]);
      setSelectedConnectorId(null);
      setResolvedConnector(null);
    }
  }, [apiUrl, legacySqlProfile, selectedConnectorId]);

  const resolveConnectorConfig = useCallback(
    async (connectorId: string, fieldOverrides?: Record<string, unknown>) => {
      if (!connectorId.trim()) {
        setResolvedConnector(null);
        return;
      }
      const sourceTypeFromId = (() => {
        const parts = connectorId.split(":");
        return String(parts[0] || "").trim().toLowerCase() || "postgres_sql";
      })();
      setLoadingConnectorResolve(true);
      try {
        const payload = await apiFetch<AdoptionImportConnectorResolvePayload>(
          apiUrl,
          "/v1/adoption/import-connectors/resolve",
          {
            method: "POST",
            body: {
              source_type: sourceTypeFromId,
              connector_id: connectorId,
              project_id: projectId.trim() || undefined,
              field_overrides: fieldOverrides || {},
            },
          },
        );
        setResolvedConnector(payload.connector || null);
      } catch {
        setResolvedConnector(null);
      } finally {
        setLoadingConnectorResolve(false);
      }
    },
    [apiUrl, projectId],
  );

  const loadLegacyImportSources = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setLegacySources([]);
      return;
    }
    setLoadingLegacySources(true);
    try {
      const payload = await apiFetch<LegacyImportSourcesPayload>(
        apiUrl,
        `/v1/legacy-import/sources?project_id=${encodeURIComponent(project)}&enabled=true&limit=200`,
      );
      setLegacySources(Array.isArray(payload.sources) ? payload.sources : []);
    } catch {
      setLegacySources([]);
    } finally {
      setLoadingLegacySources(false);
    }
  }, [apiUrl, projectId]);

  const loadBootstrapRecommendation = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setBootstrapRecommendation(null);
      return;
    }
    setLoadingBootstrapRecommendation(true);
    try {
      const payload = await apiFetch<BootstrapApproveRecommendationPayload>(
        apiUrl,
        `/v1/wiki/drafts/bootstrap-approve/recommendation?project_id=${encodeURIComponent(project)}`,
      );
      setBootstrapRecommendation(payload);
    } catch {
      setBootstrapRecommendation(null);
    } finally {
      setLoadingBootstrapRecommendation(false);
    }
  }, [apiUrl, projectId]);

  const loadAdoptionPipelineVisibility = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setAdoptionPipeline(null);
      return;
    }
    setAdoptionPipelineLoading(true);
    try {
      const query = new URLSearchParams({
        project_id: project,
        days: "14",
      });
      const payload = await apiFetch<AdoptionPipelineVisibilityPayload>(
        apiUrl,
        `/v1/adoption/pipeline/visibility?${query.toString()}`,
      );
      setAdoptionPipeline(payload);
    } catch {
      setAdoptionPipeline(null);
    } finally {
      setAdoptionPipelineLoading(false);
    }
  }, [apiUrl, projectId]);

  const loadAdoptionEvidenceBundles = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setAdoptionEvidenceBundles(null);
      return;
    }
    setAdoptionEvidenceBundlesLoading(true);
    try {
      const payload = await apiFetch<AdoptionEvidenceBundlesPayload>(
        apiUrl,
        `/v1/adoption/evidence-bundles?project_id=${encodeURIComponent(project)}&limit=40`,
      );
      setAdoptionEvidenceBundles(payload);
    } catch {
      setAdoptionEvidenceBundles(null);
    } finally {
      setAdoptionEvidenceBundlesLoading(false);
    }
  }, [apiUrl, projectId]);

  const loadAdoptionRejections = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setAdoptionRejections(null);
      return;
    }
    setAdoptionRejectionsLoading(true);
    try {
      const query = new URLSearchParams({
        project_id: project,
        days: "14",
        sample_limit: "5",
      });
      const payload = await apiFetch<AdoptionRejectionDiagnosticsPayload>(
        apiUrl,
        `/v1/adoption/rejections/diagnostics?${query.toString()}`,
      );
      setAdoptionRejections(payload);
    } catch {
      setAdoptionRejections(null);
    } finally {
      setAdoptionRejectionsLoading(false);
    }
  }, [apiUrl, projectId]);

  const loadAdoptionKpi = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setAdoptionKpi(null);
      return;
    }
    setLoadingAdoptionKpi(true);
    try {
      const payload = await apiFetch<AdoptionKpiPayload>(
        apiUrl,
        `/v1/adoption/kpi?project_id=${encodeURIComponent(project)}&days=30`,
      );
      setAdoptionKpi(payload);
    } catch {
      setAdoptionKpi(null);
    } finally {
      setLoadingAdoptionKpi(false);
    }
  }, [apiUrl, projectId]);

  const loadPolicyQuickLoop = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setPolicyQuickLoop(null);
      return;
    }
    setLoadingPolicyQuickLoop(true);
    try {
      const payload = await apiFetch<AdoptionPolicyQuickLoopPayload>(
        apiUrl,
        `/v1/adoption/policy-calibration/quick-loop?project_id=${encodeURIComponent(project)}&days=14`,
      );
      setPolicyQuickLoop(payload);
    } catch {
      setPolicyQuickLoop(null);
    } finally {
      setLoadingPolicyQuickLoop(false);
    }
  }, [apiUrl, projectId]);

  const loadEnterpriseReadiness = useCallback(async () => {
    const project = projectId.trim();
    if (!project) {
      setEnterpriseReadiness(null);
      return;
    }
    setLoadingEnterpriseReadiness(true);
    try {
      const payload = await apiFetch<EnterpriseReadinessPayload>(
        apiUrl,
        `/v1/enterprise/readiness?project_id=${encodeURIComponent(project)}`,
      );
      setEnterpriseReadiness(payload);
    } catch {
      setEnterpriseReadiness(null);
    } finally {
      setLoadingEnterpriseReadiness(false);
    }
  }, [apiUrl, projectId]);

  const applyPolicyQuickLoopPreset = useCallback(
    async (dryRun: boolean) => {
      const project = projectId.trim();
      const actor = reviewer.trim();
      if (!project || !actor) {
        notifications.show({
          color: "red",
          title: "Project and reviewer required",
          message: "Set Project ID and reviewer before applying quick policy calibration.",
        });
        return;
      }
      setApplyingPolicyQuickLoop(true);
      try {
        const payload = await apiFetch<{ status: string; changed_routing_keys?: string[] }>(
          apiUrl,
          "/v1/adoption/policy-calibration/quick-loop/apply",
          {
            method: "POST",
            body: {
              project_id: project,
              updated_by: actor,
              preset_key: policyQuickLoop?.recommended?.preset_key || undefined,
              dry_run: dryRun,
              confirm_project_id: dryRun ? undefined : project,
            },
          },
        );
        notifications.show({
          color: dryRun ? "violet" : "teal",
          title: dryRun ? "Policy quick loop preview ready" : "Policy quick loop applied",
          message:
            payload.changed_routing_keys && payload.changed_routing_keys.length > 0
              ? `Changed routing keys: ${payload.changed_routing_keys.slice(0, 6).join(", ")}`
              : "No routing changes were required.",
        });
        await loadGatekeeperConfig();
        await loadPolicyQuickLoop();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Policy quick loop failed",
          message: String(error),
        });
      } finally {
        setApplyingPolicyQuickLoop(false);
      }
    },
    [apiUrl, loadGatekeeperConfig, loadPolicyQuickLoop, policyQuickLoop?.recommended?.preset_key, projectId, reviewer],
  );

  const loadSelfhostConsistency = useCallback(async () => {
    setLoadingSelfhostConsistency(true);
    try {
      const payload = await apiFetch<SelfhostConsistencyPayload>(
        apiUrl,
        `/v1/adoption/selfhost/consistency?web_build=${encodeURIComponent(WEB_BUILD)}&ui_profile=${encodeURIComponent(
          "core",
        )}&route_path=${encodeURIComponent("/wiki")}`,
      );
      setSelfhostConsistency(payload);
    } catch {
      setSelfhostConsistency(null);
    } finally {
      setLoadingSelfhostConsistency(false);
    }
  }, [apiUrl]);

  const runLegacySourceSync = useCallback(
    async (sourceId: string) => {
      const project = projectId.trim();
      if (!project || !sourceId.trim()) {
        return;
      }
      setRunningLegacySyncSourceId(sourceId);
      try {
        const payload = await apiFetch<{ status: string; run?: { id?: string } }>(
          apiUrl,
          `/v1/legacy-import/sources/${encodeURIComponent(sourceId)}/sync`,
          {
            method: "POST",
            body: {
              project_id: project,
              requested_by: reviewer.trim() || "web_ui",
            },
          },
        );
        notifications.show({
          color: "teal",
          title: payload.status === "already_queued" ? "Sync already queued" : "Sync queued",
          message:
            payload.run?.id && String(payload.run.id).trim()
              ? `Run ${String(payload.run.id).slice(0, 8)} queued.`
              : "Legacy memory sync run queued.",
        });
        await loadLegacyImportSources();
        await loadBootstrapRecommendation();
        await loadAdoptionPipelineVisibility();
        await loadAdoptionEvidenceBundles();
        await loadAdoptionKpi();
        await loadPolicyQuickLoop();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Sync queue failed",
          message: String(error),
        });
      } finally {
        setRunningLegacySyncSourceId(null);
      }
    },
    [
      apiUrl,
      loadAdoptionEvidenceBundles,
      loadAdoptionKpi,
      loadAdoptionPipelineVisibility,
      loadBootstrapRecommendation,
      loadLegacyImportSources,
      loadPolicyQuickLoop,
      projectId,
      reviewer,
    ],
  );

  const connectLegacyMemoryQuickstart = useCallback(async (): Promise<boolean> => {
    const project = projectId.trim();
    const sourceRef = legacySourceRef.trim();
    const selectedConnector =
      adoptionImportConnectors.find((item) => item.id === selectedConnectorId) || resolvedConnector || null;
    const connectorSourceType = String(selectedConnector?.source_type || "postgres_sql")
      .trim()
      .toLowerCase();
    const profile = String(
      selectedConnector?.profile || resolvedConnector?.profile || legacySqlProfile || "",
    )
      .trim()
      .toLowerCase();
    const dsnEnv = legacySqlDsnEnv.trim();
    const memoryApiUrl = legacyMemoryApiUrl.trim();
    if (!project) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before connecting existing memory.",
      });
      return false;
    }
    if (!sourceRef) {
      notifications.show({
        color: "red",
        title: "Source ref required",
        message: "Set a source name for this memory connector.",
      });
      return false;
    }
    if (!profile) {
      notifications.show({
        color: "red",
        title: "Profile required",
        message: "Select a memory profile first.",
      });
      return false;
    }
    if (connectorSourceType === "postgres_sql" && !dsnEnv) {
      notifications.show({
        color: "red",
        title: "DSN env var required",
        message: "Set environment variable name for PostgreSQL DSN.",
      });
      return false;
    }
    if (connectorSourceType === "memory_api") {
      const effectiveMemoryApiUrl =
        memoryApiUrl || (sourceRef.startsWith("http://") || sourceRef.startsWith("https://") ? sourceRef : "");
      if (!effectiveMemoryApiUrl) {
        notifications.show({
          color: "red",
          title: "Memory API URL required",
          message: "Set Memory API URL (or use URL directly as source ref).",
        });
        return false;
      }
    }
    const intervalDefault =
      String(selectedConnector?.sync_mode || "").trim().toLowerCase() === "wal_cdc" ? 1 : Number(legacySyncIntervalMinutes || "5") || 5;
    const interval = Math.max(1, Math.min(10080, intervalDefault));
    const maxRecords = Math.max(1, Math.min(50000, Number(legacyMaxRecords || "5000") || 5000));
    const chunkSize = Math.max(1, Math.min(500, Number(legacyChunkSize || "100") || 100));
    const baseConfig = resolvedConnector?.config_patch ? { ...resolvedConnector.config_patch } : {};
    const connectorSyncMode = String(selectedConnector?.sync_mode || "").trim().toLowerCase();
    if (connectorSyncMode) {
      baseConfig["sql_sync_mode"] = connectorSyncMode;
    }
    if (connectorSourceType === "postgres_sql") {
      baseConfig["sql_profile"] = profile;
      baseConfig["sql_dsn_env"] = dsnEnv;
    } else if (connectorSourceType === "memory_api") {
      baseConfig["api_url"] =
        memoryApiUrl || (sourceRef.startsWith("http://") || sourceRef.startsWith("https://") ? sourceRef : "");
      baseConfig["api_method"] = String(baseConfig["api_method"] || "GET").toUpperCase();
    }
    baseConfig["max_records"] = maxRecords;
    baseConfig["chunk_size"] = chunkSize;

    setConnectingLegacySource(true);
    let connected = false;
    try {
      const bootstrap = await apiFetch<AdoptionImportConnectorBootstrapPayload>(
        apiUrl,
        "/v1/adoption/import-connectors/bootstrap",
        {
          method: "POST",
          body: {
            project_id: project,
            updated_by: reviewer.trim() || "web_ui",
            source_type: connectorSourceType || "postgres_sql",
            connector_id: selectedConnector?.id || selectedConnectorId,
            source_ref: sourceRef,
            field_overrides: {
              ...baseConfig,
            },
            enabled: true,
            sync_interval_minutes: interval,
            queue_sync: true,
            dry_run: false,
            confirm_project_id: project,
            sync_processor_lookback_minutes: 30,
            fail_on_sync_processor_unavailable: false,
          },
          idempotencyKey: randomKey(),
        },
      );
      const sourceId = String(bootstrap.source?.id || "").trim();
      if (!sourceId) {
        throw new Error("connector bootstrap did not return source id");
      }
      if (String(bootstrap.status || "").trim().toLowerCase() === "blocked") {
        throw new Error(
          `connector validation failed: ${(bootstrap.validation?.errors || []).slice(0, 3).join("; ") || "unknown error"}`,
        );
      }
      if (String(bootstrap.sync_queue?.status || "").trim().toLowerCase() === "unavailable") {
        notifications.show({
          color: "orange",
          title: "Source connected, queue unavailable",
          message: "Legacy sync scheduler is unavailable. Start worker scheduler and retry queue run.",
        });
      }
      if (String(bootstrap.sync_queue?.status || "").trim().toLowerCase() === "skipped") {
        await runLegacySourceSync(sourceId);
      }
      if (legacyAutoOpenMigrationMode) {
        setCoreWorkspaceTab("drafts");
        setShowMigrationMode(true);
        setShowDraftOperationsTools(true);
      }
      notifications.show({
        color: "teal",
        title: "Existing memory connected",
        message: `${selectedConnector?.label || profile || connectorSourceType} connected via connector bootstrap.`,
      });
      connected = true;
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Could not connect memory",
        message: String(error),
      });
    } finally {
      setConnectingLegacySource(false);
      await loadLegacyImportSources();
      await loadBootstrapRecommendation();
      await loadAdoptionPipelineVisibility();
      await loadAdoptionRejections();
      await loadAdoptionKpi();
      await loadPolicyQuickLoop();
      await loadEnterpriseReadiness();
    }
    return connected;
  }, [
    adoptionImportConnectors,
    apiUrl,
    legacyAutoOpenMigrationMode,
    legacyChunkSize,
    legacyMemoryApiUrl,
    legacyMaxRecords,
    legacySourceRef,
    legacySqlDsnEnv,
    legacySqlProfile,
    legacySyncIntervalMinutes,
    loadAdoptionPipelineVisibility,
    loadAdoptionRejections,
    loadBootstrapRecommendation,
    loadEnterpriseReadiness,
    loadAdoptionKpi,
    loadLegacyImportSources,
    loadPolicyQuickLoop,
    projectId,
    resolvedConnector,
    reviewer,
    runLegacySourceSync,
    selectedConnectorId,
  ]);

  const completeLegacySetupWizard = useCallback(async () => {
    const ok = await connectLegacyMemoryQuickstart();
    if (ok) {
      setLegacyWizardStep1Done(true);
      setLegacyWizardStep2Done(true);
      setLegacyWizardStep3Done(true);
      setLegacySetupStep(4);
    }
  }, [connectLegacyMemoryQuickstart]);

  const openLegacySetupWizard = useCallback(() => {
    setLegacySetupStep(1);
    setLegacyWizardStep1Done(false);
    setLegacyWizardStep2Done(false);
    setLegacyWizardStep3Done(false);
    setLegacyWizardStep4Done(false);
    setLegacySeedStarterPages(true);
    setLegacyStarterProfile("standard");
    setShowLegacySetupModal(true);
  }, []);

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
    const project = projectId.trim();
    previousSelectedPageSlugRef.current = null;
    lifecycleSuggestionSeenRef.current = {};
    lifecycleEmptyScopeSeenRef.current = {};
    if (!project) {
      setWikiUxMetrics({
        sessionStartedMs: Date.now(),
        firstPageViewMs: null,
        firstPublishMs: null,
        pageOpenCount: 0,
        pageOpenCountAtFirstPublish: null,
        publishCount: 0,
      });
      setLifecycleAdvisorMetrics({
        sessionId: randomKey(),
        sessionStartedMs: Date.now(),
        suggestionShown: 0,
        suggestionApplied: 0,
        staleShownAtBySlug: {},
        staleResolvedDurationsMs: [],
        emptyScopeActionShownByType: {},
        emptyScopeActionAppliedByType: {},
      });
      return;
    }
    try {
      const raw = window.localStorage.getItem(`${UX_METRICS_STORAGE_PREFIX}${project}`);
      if (!raw) throw new Error("missing metrics");
      const parsed = JSON.parse(raw) as Partial<WikiUxMetricsState>;
      const sessionStartedMs = Number(parsed.sessionStartedMs);
      const firstPageViewMs = parsed.firstPageViewMs == null ? null : Number(parsed.firstPageViewMs);
      const firstPublishMs = parsed.firstPublishMs == null ? null : Number(parsed.firstPublishMs);
      const pageOpenCount = Number(parsed.pageOpenCount ?? 0);
      const pageOpenCountAtFirstPublish =
        parsed.pageOpenCountAtFirstPublish == null ? null : Number(parsed.pageOpenCountAtFirstPublish);
      const publishCount = Number(parsed.publishCount ?? 0);
      if (!Number.isFinite(sessionStartedMs)) throw new Error("invalid metrics");
      setWikiUxMetrics({
        sessionStartedMs,
        firstPageViewMs: Number.isFinite(firstPageViewMs ?? NaN) ? firstPageViewMs : null,
        firstPublishMs: Number.isFinite(firstPublishMs ?? NaN) ? firstPublishMs : null,
        pageOpenCount: Number.isFinite(pageOpenCount) ? Math.max(0, Math.round(pageOpenCount)) : 0,
        pageOpenCountAtFirstPublish:
          pageOpenCountAtFirstPublish != null && Number.isFinite(pageOpenCountAtFirstPublish)
            ? Math.max(0, Math.round(pageOpenCountAtFirstPublish))
            : null,
        publishCount: Number.isFinite(publishCount) ? Math.max(0, Math.round(publishCount)) : 0,
      });
    } catch {
      setWikiUxMetrics({
        sessionStartedMs: Date.now(),
        firstPageViewMs: null,
        firstPublishMs: null,
        pageOpenCount: 0,
        pageOpenCountAtFirstPublish: null,
        publishCount: 0,
      });
    }
    try {
      const raw = window.localStorage.getItem(`${LIFECYCLE_METRICS_STORAGE_PREFIX}${project}`);
      if (!raw) throw new Error("missing lifecycle metrics");
      const parsed = JSON.parse(raw) as Partial<LifecycleAdvisorMetricsState>;
      const sessionId = String(parsed.sessionId || "").trim() || randomKey();
      const sessionStartedMs = Number(parsed.sessionStartedMs);
      const suggestionShown = Number(parsed.suggestionShown ?? 0);
      const suggestionApplied = Number(parsed.suggestionApplied ?? 0);
      const staleShownAtBySlug =
        parsed.staleShownAtBySlug && typeof parsed.staleShownAtBySlug === "object" ? parsed.staleShownAtBySlug : {};
      const staleResolvedDurationsMs = Array.isArray(parsed.staleResolvedDurationsMs)
        ? parsed.staleResolvedDurationsMs.map((item) => Number(item)).filter((item) => Number.isFinite(item) && item >= 0)
        : [];
      const emptyScopeActionShownByType =
        parsed.emptyScopeActionShownByType && typeof parsed.emptyScopeActionShownByType === "object"
          ? parsed.emptyScopeActionShownByType
          : {};
      const emptyScopeActionAppliedByType =
        parsed.emptyScopeActionAppliedByType && typeof parsed.emptyScopeActionAppliedByType === "object"
          ? parsed.emptyScopeActionAppliedByType
          : {};
      if (!Number.isFinite(sessionStartedMs)) throw new Error("invalid lifecycle metrics");
      setLifecycleAdvisorMetrics({
        sessionId,
        sessionStartedMs,
        suggestionShown: Number.isFinite(suggestionShown) ? Math.max(0, Math.round(suggestionShown)) : 0,
        suggestionApplied: Number.isFinite(suggestionApplied) ? Math.max(0, Math.round(suggestionApplied)) : 0,
        staleShownAtBySlug: Object.fromEntries(
          Object.entries(staleShownAtBySlug)
            .map(([key, value]) => [key, Number(value)] as const)
            .filter(([, value]) => Number.isFinite(value) && value > 0),
        ) as Record<string, number>,
        staleResolvedDurationsMs: staleResolvedDurationsMs.slice(-200),
        emptyScopeActionShownByType: Object.fromEntries(
          Object.entries(emptyScopeActionShownByType)
            .map(([key, value]) => [key, Number(value)] as const)
            .filter(([key, value]) => Boolean(String(key).trim()) && Number.isFinite(value) && value > 0),
        ) as Record<string, number>,
        emptyScopeActionAppliedByType: Object.fromEntries(
          Object.entries(emptyScopeActionAppliedByType)
            .map(([key, value]) => [key, Number(value)] as const)
            .filter(([key, value]) => Boolean(String(key).trim()) && Number.isFinite(value) && value > 0),
        ) as Record<string, number>,
      });
    } catch {
      setLifecycleAdvisorMetrics({
        sessionId: randomKey(),
        sessionStartedMs: Date.now(),
        suggestionShown: 0,
        suggestionApplied: 0,
        staleShownAtBySlug: {},
        staleResolvedDurationsMs: [],
        emptyScopeActionShownByType: {},
        emptyScopeActionAppliedByType: {},
      });
    }
  }, [projectId]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project) return;
    try {
      window.localStorage.setItem(`${UX_METRICS_STORAGE_PREFIX}${project}`, JSON.stringify(wikiUxMetrics));
    } catch {
      // ignore storage errors
    }
  }, [projectId, wikiUxMetrics]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project) return;
    try {
      window.localStorage.setItem(`${LIFECYCLE_METRICS_STORAGE_PREFIX}${project}`, JSON.stringify(lifecycleAdvisorMetrics));
    } catch {
      // ignore storage errors
    }
  }, [lifecycleAdvisorMetrics, projectId]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project) return;
    const normalizeCounts = (raw: Record<string, number>) => {
      const out: Record<string, number> = {};
      for (const [action, value] of Object.entries(raw || {})) {
        const key = normalizeTelemetryActionKey(action);
        if (!key) continue;
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) continue;
        const bounded = Math.max(0, Math.min(1_000_000_000, Math.round(numeric)));
        out[key] = bounded;
      }
      return out;
    };
    const shownCounts = normalizeCounts(lifecycleAdvisorMetrics.emptyScopeActionShownByType || {});
    const appliedCounts = normalizeCounts(lifecycleAdvisorMetrics.emptyScopeActionAppliedByType || {});
    if (Object.keys(shownCounts).length === 0 && Object.keys(appliedCounts).length === 0) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        await apiFetch(apiUrl, "/v1/wiki/lifecycle/telemetry/snapshot", {
          method: "POST",
          body: {
            project_id: project,
            session_id: lifecycleAdvisorMetrics.sessionId,
            observed_at: new Date().toISOString(),
            empty_scope_action_shown: shownCounts,
            empty_scope_action_applied: appliedCounts,
            source: "web_ui",
          },
          idempotencyKey: randomKey(),
        });
        if (!cancelled) {
          void loadWikiLifecycleTelemetry({ silent: true });
        }
      } catch {
        // best effort telemetry sync
      }
    }, LIFECYCLE_TELEMETRY_SYNC_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    apiUrl,
    lifecycleAdvisorMetrics.emptyScopeActionAppliedByType,
    lifecycleAdvisorMetrics.emptyScopeActionShownByType,
    lifecycleAdvisorMetrics.sessionId,
    loadWikiLifecycleTelemetry,
    projectId,
  ]);

  useEffect(() => {
    if (!selectedPageSlug) {
      previousSelectedPageSlugRef.current = null;
      return;
    }
    const previous = previousSelectedPageSlugRef.current;
    previousSelectedPageSlugRef.current = selectedPageSlug;
    if (previous === selectedPageSlug) return;
    const now = Date.now();
    setWikiUxMetrics((prev) => ({
      ...prev,
      firstPageViewMs: prev.firstPageViewMs ?? now,
      pageOpenCount: prev.pageOpenCount + 1,
    }));
  }, [selectedPageSlug]);

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
    const project = projectId.trim();
    const preferred = spaceContentStats.preferred;
    if (!project || !preferred || pageNodes.length === 0) return;
    if (!selectedSpaceKey) return;

    const current = spaceContentStats.byKey.get(selectedSpaceKey) || null;
    let reason: SpaceRecoveryNotice["reason"] | null = null;
    if (!current) {
      reason = "missing_space";
    } else if (
      current.publishedCount <= 0
      && preferred.publishedCount > 0
      && preferred.key !== selectedSpaceKey
    ) {
      reason = "empty_published_space";
    }
    if (!reason) return;

    const signature = `${project}:${selectedSpaceKey || "none"}:${preferred.key}:${reason}`;
    if (autoSpaceRecoverySeenRef.current[project] === signature) return;
    autoSpaceRecoverySeenRef.current[project] = signature;

    setSelectedSpaceKey(preferred.key);
    if (!selectedPageSlug || pageGroupKey(selectedPageSlug) !== preferred.key) {
      const nextPage = pageNodes.find((item) => pageGroupKey(item.slug) === preferred.key)?.slug || null;
      if (nextPage) {
        setSelectedPageSlug(nextPage);
      }
    }
    setSpaceRecoveryNotice({
      from: selectedSpaceKey,
      to: preferred.key,
      reason,
    });
  }, [pageNodes, projectId, selectedPageSlug, selectedSpaceKey, spaceContentStats]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project || !selectedPageSlug) return;
    try {
      window.localStorage.setItem(`${LAST_PAGE_STORAGE_PREFIX}${project}`, selectedPageSlug);
    } catch {
      // ignore storage errors
    }
  }, [projectId, selectedPageSlug]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project || selectedPageSlug || pageNodes.length === 0) return;
    let remembered: string | null = null;
    try {
      remembered = window.localStorage.getItem(`${LAST_PAGE_STORAGE_PREFIX}${project}`);
    } catch {
      remembered = null;
    }
    const rememberedExists = remembered && pageNodes.some((item) => item.slug === remembered);
    const scopedPages = selectedSpaceKey
      ? pageNodes.filter((item) => pageGroupKey(item.slug) === selectedSpaceKey)
      : pageNodes;
    const fallback = scopedPages[0]?.slug || pageNodes[0]?.slug || null;
    const next = rememberedExists ? remembered : fallback;
    if (next) {
      setSelectedSpaceKey(pageGroupKey(next));
      setSelectedPageSlug(next);
    }
  }, [pageNodes, projectId, selectedPageSlug, selectedSpaceKey]);

  useEffect(() => {
    const project = projectId.trim();
    if (!project) {
      setShowOnboardingModal(false);
      return;
    }
    let onboardingDone = false;
    try {
      onboardingDone = window.localStorage.getItem(`${ONBOARDING_STORAGE_PREFIX}${project}`) === "1";
    } catch {
      onboardingDone = false;
    }
    if (pageNodes.length === 0 && !onboardingDone) {
      setShowOnboardingModal(true);
      setOnboardingStep(1);
      return;
    }
    if (showOnboardingModal && (pageNodes.length > 0 || onboardingDone)) {
      setShowOnboardingModal(false);
    }
  }, [pageNodes.length, projectId, showOnboardingModal]);

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
      setPageReviewAssignments([]);
      setSpacePolicy(null);
      setSpacePolicyAudit([]);
      setSpacePolicyAdoptionSummaryApi(null);
      setPageEditMode(false);
      setPageMoveMode(false);
      return;
    }
    void loadPageDetail(selectedPageSlug);
    void loadPageHistory(selectedPageSlug);
    void loadPageReviewAssignments(selectedPageSlug);
    void loadSpacePolicy(selectedPageSlug);
    void loadSpacePolicyAudit(selectedPageSlug);
    void loadSpacePolicyAdoptionSummary(selectedPageSlug);
  }, [
    loadPageDetail,
    loadPageHistory,
    loadPageReviewAssignments,
    loadSpacePolicyAdoptionSummary,
    loadSpacePolicyAudit,
    loadSpacePolicy,
    selectedPageSlug,
  ]);

  useEffect(() => {
    if (selectedPageSlug) return;
    if (historyDrawerOpen) {
      setHistoryDrawerOpen(false);
    }
  }, [historyDrawerOpen, selectedPageSlug]);

  useEffect(() => {
    void loadGatekeeperConfig();
  }, [loadGatekeeperConfig]);

  useEffect(() => {
    if (!projectId.trim()) {
      setAgentOrgchart(null);
      return;
    }
    if (coreWorkspaceRoute !== "operations") {
      return;
    }
    void loadAgentOrgchart({ silent: true });
  }, [coreWorkspaceRoute, loadAgentOrgchart, projectId]);

  useEffect(() => {
    if (!projectId.trim()) {
      setLegacyProfiles([]);
      setAdoptionImportConnectors([]);
      setSelectedConnectorId(null);
      setResolvedConnector(null);
      setLegacySources([]);
      setBootstrapRecommendation(null);
      setAdoptionPipeline(null);
      setAdoptionEvidenceBundles(null);
      setAdoptionRejections(null);
      setAdoptionKpi(null);
      setPolicyQuickLoop(null);
      setEnterpriseReadiness(null);
      return;
    }
    void loadLegacyImportProfiles();
    void loadAdoptionImportConnectors();
    void loadLegacyImportSources();
    void loadBootstrapRecommendation();
    void loadAdoptionPipelineVisibility();
    void loadAdoptionEvidenceBundles();
    void loadAdoptionRejections();
    void loadAdoptionKpi();
    void loadPolicyQuickLoop();
    void loadEnterpriseReadiness();
  }, [
    loadAdoptionImportConnectors,
    loadAdoptionEvidenceBundles,
    loadAdoptionKpi,
    loadAdoptionPipelineVisibility,
    loadAdoptionRejections,
    loadBootstrapRecommendation,
    loadEnterpriseReadiness,
    loadLegacyImportProfiles,
    loadLegacyImportSources,
    loadPolicyQuickLoop,
    projectId,
  ]);

  useEffect(() => {
    void loadSelfhostConsistency();
  }, [coreWorkspaceRoute, loadSelfhostConsistency, selectedPageSlug]);

  useEffect(() => {
    if (!projectId.trim()) return;
    if (legacySourceRef.trim()) return;
    const suffix = legacySqlProfile.trim() || "memory";
    const projectToken = projectId
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 40);
    const nextSourceRef = projectToken ? `${projectToken}_${suffix}` : `existing_${suffix}`;
    setLegacySourceRef(nextSourceRef);
  }, [legacySourceRef, legacySqlProfile, projectId]);

  useEffect(() => {
    const connectorId = String(selectedConnectorId || "").trim();
    if (!connectorId) {
      setResolvedConnector(null);
      return;
    }
    const connectorSourceType = String(connectorId.split(":")[0] || "").trim().toLowerCase() || "postgres_sql";
    const overrides: Record<string, unknown> = {
      max_records: Number(legacyMaxRecords || "5000") || 5000,
      chunk_size: Number(legacyChunkSize || "100") || 100,
      "curated_import.noise_preset": "knowledge_v2",
      "curated_import.drop_event_like": true,
      "curated_import.enabled": true,
    };
    if (connectorSourceType === "memory_api") {
      overrides.api_url = legacyMemoryApiUrl.trim() || undefined;
    } else {
      overrides.sql_dsn_env = legacySqlDsnEnv.trim() || undefined;
    }
    void resolveConnectorConfig(connectorId, {
      ...overrides,
    });
  }, [legacyChunkSize, legacyMaxRecords, legacyMemoryApiUrl, legacySqlDsnEnv, resolveConnectorConfig, selectedConnectorId]);

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
    if (!pageEditDraftStorageKey) {
      setRestoredDraftKey(null);
      return;
    }
    if (restoredDraftKey && restoredDraftKey !== pageEditDraftStorageKey) {
      setRestoredDraftKey(null);
    }
  }, [pageEditDraftStorageKey, restoredDraftKey]);

  useEffect(() => {
    if (!pageEditMode || !pageEditDraftStorageKey || restoredDraftKey === pageEditDraftStorageKey) return;
    try {
      const raw = window.localStorage.getItem(pageEditDraftStorageKey);
      if (!raw) {
        setRestoredDraftKey(pageEditDraftStorageKey);
        return;
      }
      const payload = JSON.parse(raw) as {
        title?: string;
        summary?: string;
        markdown?: string;
        updated_at?: string;
      };
      const markdown = String(payload.markdown || "");
      const title = String(payload.title || "");
      const summary = String(payload.summary || "");
      if (!markdown.trim() && !title.trim() && !summary.trim()) {
        setRestoredDraftKey(pageEditDraftStorageKey);
        return;
      }
      setPageEditTitle((prev) => title || prev);
      setPageEditSummary((prev) => summary || prev);
      setPageEditMarkdown((prev) => (markdown.trim() ? markdown : prev));
      setPageEditDraftSavedAt(payload.updated_at || null);
      setPageEditDraftState("restored");
      notifications.show({
        color: "blue",
        title: "Draft restored",
        message: "Recovered unsaved page edits from local draft.",
      });
    } catch {
      // ignore corrupted local draft
    } finally {
      setRestoredDraftKey(pageEditDraftStorageKey);
    }
  }, [pageEditDraftStorageKey, pageEditMode, restoredDraftKey]);

  useEffect(() => {
    if (!pageEditMode || !pageEditDraftStorageKey) return;
    const markdown = pageEditMarkdown.trim();
    const title = pageEditTitle.trim();
    const summary = pageEditSummary.trim();
    if (!markdown && !title && !summary) return;
    setPageEditDraftState("saving");
    const timer = window.setTimeout(() => {
      const updatedAt = new Date().toISOString();
      try {
        window.localStorage.setItem(
          pageEditDraftStorageKey,
          JSON.stringify({
            title,
            summary,
            markdown: pageEditMarkdown,
            updated_at: updatedAt,
          }),
        );
        setPageEditDraftSavedAt(updatedAt);
        setPageEditDraftState("saved");
      } catch {
        setPageEditDraftState("idle");
      }
    }, 700);
    return () => window.clearTimeout(timer);
  }, [pageEditDraftStorageKey, pageEditMarkdown, pageEditMode, pageEditSummary, pageEditTitle]);

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

  const runBootstrapApprove = useCallback(
    async (
      dryRun: boolean,
      overrides?: {
        trustedSourceSystems?: string[];
        limit?: number;
        sampleSize?: number;
        minConfidence?: number;
        requireConflictFree?: boolean;
      },
    ) => {
      if (!projectId.trim() || !reviewer.trim()) {
        notifications.show({
          color: "red",
          title: "Missing reviewer or project",
          message: "Set Project ID and Reviewer before migration bootstrap.",
        });
        return;
      }
      const trustedSourceSystems = Array.isArray(overrides?.trustedSourceSystems)
        ? [...new Set(overrides.trustedSourceSystems.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean))].sort()
        : normalizeSourceSystemCsv(bootstrapTrustedSources);
      const limitRaw =
        typeof overrides?.limit === "number" && Number.isFinite(overrides.limit)
          ? overrides.limit
          : Number.parseInt(bootstrapLimit, 10);
      const sampleRaw =
        typeof overrides?.sampleSize === "number" && Number.isFinite(overrides.sampleSize)
          ? overrides.sampleSize
          : Number.parseInt(bootstrapSampleSize, 10);
      const confidenceRaw =
        typeof overrides?.minConfidence === "number" && Number.isFinite(overrides.minConfidence)
          ? overrides.minConfidence
          : Number.parseFloat(bootstrapMinConfidence);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(2000, limitRaw)) : 50;
      const sampleSize = Number.isFinite(sampleRaw) ? Math.max(1, Math.min(200, sampleRaw)) : 15;
      const minConfidence = Number.isFinite(confidenceRaw) ? Math.max(0, Math.min(1, confidenceRaw)) : 0.85;
      const requireConflictFree =
        typeof overrides?.requireConflictFree === "boolean" ? overrides.requireConflictFree : bootstrapRequireConflictFree;
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
      const hasMatchingPreview = matchesBootstrapPreview(bootstrapResult, {
        projectId,
        trustedSourceSystems: normalizedTrusted,
        limit,
        minConfidence,
        requireConflictFree,
      });
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
            require_conflict_free: requireConflictFree,
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
          await loadBootstrapRecommendation();
          await loadAdoptionPipelineVisibility();
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
        await loadBootstrapRecommendation();
        await loadAdoptionPipelineVisibility();
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
      loadAdoptionPipelineVisibility,
      loadBootstrapRecommendation,
      projectId,
      reviewer,
      selectedDraftId,
    ],
  );

  const resolveRecommendedBootstrapPreset = useCallback(() => {
    const fromApi = bootstrapRecommendation?.recommended;
    if (fromApi) {
      const trustedSourceSystems = [...new Set(
        (Array.isArray(fromApi.trusted_source_systems) ? fromApi.trusted_source_systems : [])
          .map((item) => String(item || "").trim().toLowerCase())
          .filter(Boolean),
      )].sort();
      return {
        trustedSourceSystems: trustedSourceSystems.length > 0 ? trustedSourceSystems : ["legacy_import", "postgres_sql"],
        minConfidence: Math.max(0, Math.min(1, Number(fromApi.min_confidence || 0.9))),
        limit: Math.max(1, Math.min(2000, Number(fromApi.limit || 50))),
        sampleSize: Math.max(1, Math.min(200, Number(fromApi.sample_size || 15))),
        requireConflictFree: Boolean(fromApi.require_conflict_free),
      };
    }
    const mappedTrusted = [...new Set(
      legacySources
        .map((item) => String(item.source_type || "").trim().toLowerCase())
        .filter((item) => item === "postgres_sql" || item === "legacy_import"),
    )].sort();
    const trustedSourceSystems = mappedTrusted.length > 0 ? mappedTrusted : ["legacy_import", "postgres_sql"];
    const currentOpenDrafts = drafts.filter((item) => item.status === "pending_review" || item.status === "blocked_conflict").length;
    const limit = currentOpenDrafts >= 300 ? 25 : currentOpenDrafts >= 100 ? 40 : 50;
    const sampleSize = Math.min(20, Math.max(10, Math.floor(limit / 2)));
    return {
      trustedSourceSystems,
      minConfidence: 0.9,
      limit,
      sampleSize,
      requireConflictFree: true,
    };
  }, [bootstrapRecommendation, drafts, legacySources]);

  const applyRecommendedBootstrapPreset = useCallback(
    (preset?: {
      trustedSourceSystems: string[];
      minConfidence: number;
      limit: number;
      sampleSize: number;
      requireConflictFree: boolean;
    }) => {
      const nextPreset = preset ?? resolveRecommendedBootstrapPreset();
      setBootstrapTrustedSources(nextPreset.trustedSourceSystems.join(","));
      setBootstrapTrustedSourcesTouched(false);
      setBootstrapMinConfidence(nextPreset.minConfidence.toFixed(2));
      setBootstrapLimit(String(nextPreset.limit));
      setBootstrapSampleSize(String(nextPreset.sampleSize));
      setBootstrapRequireConflictFree(nextPreset.requireConflictFree);
      setShowMigrationMode(true);
      setShowBootstrapTools(true);
      setShowDraftOperationsTools(true);
      if (effectiveUiMode === "core") {
        setCoreWorkspaceTab("drafts");
      }
      return nextPreset;
    },
    [effectiveUiMode, resolveRecommendedBootstrapPreset],
  );

  const applyAdoptionBootstrapProfile = useCallback(
    async (dryRun: boolean) => {
      const project = projectId.trim();
      const reviewedBy = reviewer.trim();
      if (!project || !reviewedBy) {
        notifications.show({
          color: "red",
          title: "Missing reviewer or project",
          message: "Set Project ID and Reviewer before applying bootstrap profile.",
        });
        return;
      }
      setBootstrapProfileLoading(true);
      try {
        const payload = await apiFetch<AdoptionBootstrapProfileApplyPayload>(
          apiUrl,
          "/v1/adoption/bootstrap-profile/apply",
          {
            method: "POST",
            body: {
              project_id: project,
              updated_by: reviewedBy,
              profile: "initial_import",
              dry_run: dryRun,
              confirm_project_id: dryRun ? null : project,
              note: dryRun ? "Bootstrap profile dry-run from web ui." : "Bootstrap profile applied from web ui.",
            },
            idempotencyKey: randomKey(),
          },
        );
        setBootstrapProfileResult(payload);
        if (payload.bootstrap_recommendation) {
          setBootstrapRecommendation({
            status: "ok",
            project_id: project,
            recommended: payload.bootstrap_recommendation,
            diagnostics: payload.diagnostics,
            generated_at: payload.generated_at,
          });
          if (!dryRun) {
            applyRecommendedBootstrapPreset({
              trustedSourceSystems: [...new Set(
                (payload.bootstrap_recommendation.trusted_source_systems ?? [])
                  .map((item) => String(item || "").trim().toLowerCase())
                  .filter(Boolean),
              )].sort(),
              minConfidence: Math.max(0, Math.min(1, Number(payload.bootstrap_recommendation.min_confidence || 0.9))),
              limit: Math.max(1, Math.min(2000, Number(payload.bootstrap_recommendation.limit || 50))),
              sampleSize: Math.max(1, Math.min(200, Number(payload.bootstrap_recommendation.sample_size || 15))),
              requireConflictFree: Boolean(payload.bootstrap_recommendation.require_conflict_free),
            });
          }
        }
        if (dryRun) {
          notifications.show({
            color: "indigo",
            title: "Bootstrap profile preview ready",
            message: "Profile diff is ready. Apply profile to switch project into initial-import mode.",
          });
          return;
        }
        notifications.show({
          color: "teal",
          title: "Bootstrap profile applied",
          message: payload.snapshot_id
            ? `Gatekeeper snapshot ${String(payload.snapshot_id).slice(0, 8)} created.`
            : "Gatekeeper profile switched to initial-import mode.",
        });
        await loadBootstrapRecommendation();
        await loadAdoptionPipelineVisibility();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Bootstrap profile failed",
          message: String(error),
        });
      } finally {
        setBootstrapProfileLoading(false);
      }
    },
    [
      apiUrl,
      applyRecommendedBootstrapPreset,
      loadAdoptionEvidenceBundles,
      loadAdoptionPipelineVisibility,
      loadBootstrapRecommendation,
      projectId,
      reviewer,
    ],
  );

  const runRecommendedBootstrapPreview = useCallback(async () => {
    const preset = applyRecommendedBootstrapPreset();
    await runBootstrapApprove(true, preset);
  }, [applyRecommendedBootstrapPreset, runBootstrapApprove]);

  const runRecommendedBootstrapApply = useCallback(async () => {
    const preset = applyRecommendedBootstrapPreset();
    const project = projectId.trim();
    const hasMatchingPreview = matchesBootstrapPreview(bootstrapResult, {
      projectId: project,
      trustedSourceSystems: preset.trustedSourceSystems,
      limit: preset.limit,
      minConfidence: preset.minConfidence,
      requireConflictFree: preset.requireConflictFree,
    });
    if (!hasMatchingPreview) {
      await runBootstrapApprove(true, preset);
      notifications.show({
        color: "indigo",
        title: "Preview generated",
        message: "Recommended preview is ready. Re-run apply to approve the trusted batch.",
      });
      return;
    }
    await runBootstrapApprove(false, preset);
  }, [applyRecommendedBootstrapPreset, bootstrapResult, projectId, runBootstrapApprove]);

  const executeAdoptionSyncPreset = useCallback(
    async (dryRun: boolean) => {
      const project = projectId.trim();
      if (!project) return;
      setRunningSyncPreset(true);
      try {
        const payload = await apiFetch<AdoptionSyncPresetPayload>(apiUrl, "/v1/adoption/sync-presets/execute", {
          method: "POST",
          body: {
            project_id: project,
            updated_by: reviewer.trim() || "web_ui",
            reviewed_by: reviewer.trim() || "web_ui",
            preset_key: "enterprise_curated_safe",
            dry_run: Boolean(dryRun),
            confirm_project_id: dryRun ? undefined : project,
            apply_bootstrap_profile: true,
            queue_enabled_sources: true,
            run_bootstrap_approve: true,
            include_starter_pages: !dryRun,
            starter_profile: "support_ops",
            include_role_template: false,
          },
          idempotencyKey: randomKey(),
        });
        if (payload.pipeline_visibility) {
          setAdoptionPipeline(payload.pipeline_visibility);
        }
        if (payload.rejection_diagnostics) {
          setAdoptionRejections(payload.rejection_diagnostics);
        }
        const explainabilityPrimaryBucket = String(payload.explainability?.summary?.primary_bucket || "").trim();
        const explainabilityRejectedTotal = Number(payload.explainability?.summary?.total_rejections || 0);
        if (dryRun) {
          notifications.show({
            color: "indigo",
            title: "Sync preset preview ready",
            message:
              `Candidates: ${Number(payload.bootstrap_approve?.summary?.candidates || 0)}.` +
              (explainabilityPrimaryBucket
                ? ` Primary blocker: ${explainabilityPrimaryBucket.replace(/_/g, " ")} (${explainabilityRejectedTotal} rejected).`
                : ""),
          });
        } else {
          notifications.show({
            color: "teal",
            title: "Sync preset applied",
            message:
              `Queued ${Number(payload.sync_queue?.queued || 0)} source(s), approved ${Number(payload.bootstrap_approve?.summary?.approved || 0)} draft(s).` +
              (explainabilityPrimaryBucket
                ? ` Primary blocker: ${explainabilityPrimaryBucket.replace(/_/g, " ")}.`
                : ""),
          });
          setCoreWorkspaceTab("drafts");
        }
        await loadLegacyImportSources();
        await loadAdoptionPipelineVisibility();
        await loadAdoptionEvidenceBundles();
        await loadAdoptionRejections();
        await loadAdoptionKpi();
        await loadPolicyQuickLoop();
        await loadEnterpriseReadiness();
        await loadWikiPages();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Sync preset failed",
          message: String(error),
        });
      } finally {
        setRunningSyncPreset(false);
      }
    },
    [
      apiUrl,
      loadAdoptionEvidenceBundles,
      loadAdoptionKpi,
      loadAdoptionPipelineVisibility,
      loadAdoptionRejections,
      loadEnterpriseReadiness,
      loadLegacyImportSources,
      loadPolicyQuickLoop,
      loadWikiPages,
      projectId,
      reviewer,
    ],
  );

  const runAgentWikiBootstrap = useCallback(
    async (dryRun: boolean) => {
      const project = projectId.trim();
      if (!project) return;
      setRunningAgentWikiBootstrap(true);
      try {
        const payload = await apiFetch<AdoptionAgentWikiBootstrapPayload>(apiUrl, "/v1/adoption/agent-wiki-bootstrap", {
          method: "POST",
          body: {
            project_id: project,
            updated_by: reviewer.trim() || "web_ui",
            dry_run: Boolean(dryRun),
            confirm_project_id: dryRun ? undefined : project,
            publish: true,
            space_key: "operations",
            include_data_sources_catalog: true,
            include_agent_capability_profile: true,
            include_operational_logic: true,
            include_first_run_starter: true,
            max_sources: 25,
            max_agents: 120,
            max_signals: 40,
          },
          idempotencyKey: randomKey(),
        });
        setAgentWikiBootstrapResult(payload);
        if (dryRun) {
          notifications.show({
            color: "indigo",
            title: "Bootstrap Wiki preview ready",
            message: `Planned pages: ${Number(payload.plan?.pages_total || 0)}.`,
          });
        } else {
          notifications.show({
            color: "teal",
            title: "Bootstrap Wiki completed",
            message: `Created ${Number(payload.summary?.created || 0)} page(s), existing ${Number(payload.summary?.existing || 0)}.`,
          });
        }
        await loadWikiPages();
        await loadAdoptionPipelineVisibility();
        await loadAdoptionEvidenceBundles();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Bootstrap Wiki failed",
          message: String(error),
        });
      } finally {
        setRunningAgentWikiBootstrap(false);
      }
    },
    [apiUrl, loadAdoptionEvidenceBundles, loadAdoptionPipelineVisibility, loadWikiPages, projectId, reviewer],
  );

  const runFirstRunStarterBootstrap = useCallback(async () => {
    const project = projectId.trim();
    if (!project) return null;
    setRunningStarterBootstrap(true);
    try {
      const payload = await apiFetch<AdoptionFirstRunBootstrapPayload>(apiUrl, "/v1/adoption/first-run/bootstrap", {
        method: "POST",
        body: {
          project_id: project,
          created_by: reviewer.trim() || "web_ui",
          profile: legacyStarterProfile,
          publish: true,
        },
        idempotencyKey: randomKey(),
      });
      const createdCount = Number(payload.summary?.created || 0);
      const existingCount = Number(payload.summary?.existing || 0);
      notifications.show({
        color: "teal",
        title: "Starter wiki pages ready",
        message: `Created ${createdCount}, existing ${existingCount}.`,
      });
      await loadWikiPages();
      return payload;
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Starter pages failed",
        message: String(error),
      });
      return null;
    } finally {
      setRunningStarterBootstrap(false);
    }
  }, [apiUrl, legacyStarterProfile, loadWikiPages, projectId, reviewer]);

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
      if (pageEditDraftStorageKey) {
        try {
          window.localStorage.removeItem(pageEditDraftStorageKey);
        } catch {
          // ignore storage errors
        }
      }
      setPageEditDraftState("idle");
      setPageEditDraftSavedAt(null);
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
    pageEditDraftStorageKey,
    selectedPageDetail?.page.page_type,
    selectedPageSlug,
  ]);

  const runProcessSafetySimulation = useCallback(async () => {
    if (!selectedPageSlug || !projectId.trim()) {
      notifications.show({
        color: "red",
        title: "Project or page missing",
        message: "Set project and select page before running simulation.",
      });
      return;
    }
    const proposedMarkdown = pageEditMarkdown.trim() || String(selectedPageDetail?.latest_version?.markdown || "").trim();
    if (!proposedMarkdown) {
      notifications.show({
        color: "red",
        title: "No content to simulate",
        message: "Page markdown is empty.",
      });
      return;
    }
    setLoadingProcessSimulation(true);
    try {
      const payload = await apiFetch<WikiProcessSimulationPayload>(apiUrl, "/v1/wiki/process/simulate", {
        method: "POST",
        body: {
          project_id: projectId,
          page_slug: selectedPageSlug,
          proposed_markdown: proposedMarkdown,
          baseline_markdown: String(selectedPageDetail?.latest_version?.markdown || ""),
          sample_limit: 10,
        },
      });
      setProcessSimulation(payload);
      notifications.show({
        color: payload.risk?.should_block_publish ? "orange" : "green",
        title: "Process simulation ready",
        message: `Risk ${payload.risk?.level || "unknown"} (score ${Number(payload.risk?.score || 0).toFixed(0)}).`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Simulation failed",
        message: String(error),
      });
    } finally {
      setLoadingProcessSimulation(false);
    }
  }, [apiUrl, pageEditMarkdown, projectId, selectedPageDetail?.latest_version?.markdown, selectedPageSlug]);

  const publishCurrentPage = useCallback(async () => {
    if (!selectedPageSlug) {
      notifications.show({
        color: "red",
        title: "Page not selected",
        message: "Select wiki page before publishing.",
      });
      return;
    }
    if (!projectId.trim() || !reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Missing reviewer or project",
        message: "Set Project ID and Reviewer before publishing.",
      });
      return;
    }
    const markdownSeed = pageEditMarkdown.trim() || String(selectedPageDetail?.latest_version?.markdown || "").trim();
    if (!markdownSeed) {
      notifications.show({
        color: "red",
        title: "No content to publish",
        message: "Page markdown is empty.",
      });
      return;
    }
    const checklistPreset =
      PUBLISH_CHECKLIST_PRESETS.find((item) => item.key === spacePublishChecklistPreset) || PUBLISH_CHECKLIST_PRESETS[0];
    const checklistComplete = checklistPreset.items.every((item) => Boolean(publishChecklistAcks[item.id]));
    if (!checklistComplete) {
      notifications.show({
        color: "orange",
        title: "Checklist not complete",
        message: "Complete publish checklist items for this space before publishing.",
      });
      return;
    }
    if (processSimulation?.risk?.should_block_publish && !publishConfirmHighRisk) {
      notifications.show({
        color: "orange",
        title: "High-risk publish requires confirmation",
        message: "Run safety simulation review and acknowledge high-risk publish before continuing.",
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
            title: pageEditTitle.trim() || selectedPageDetail?.page.title || null,
            page_type: selectedPageDetail?.page.page_type || null,
            status: "published",
            markdown: markdownSeed,
            change_summary: publishSummary.trim() || "Published from wiki UI",
            confirm_high_risk_publish: publishConfirmHighRisk,
          },
          idempotencyKey: randomKey(),
        },
      );
      notifications.show({
        color: "green",
        title: "Page published",
        message: `${payload.page.title || selectedPageSlug} is published.`,
      });
      const publishedAtMs = Date.now();
      setWikiUxMetrics((prev) => ({
        ...prev,
        firstPublishMs: prev.firstPublishMs ?? publishedAtMs,
        pageOpenCountAtFirstPublish: prev.firstPublishMs == null ? prev.pageOpenCount : prev.pageOpenCountAtFirstPublish,
        publishCount: prev.publishCount + 1,
      }));
      setShowPublishModal(false);
      setPageEditMode(false);
      setProcessSimulation(null);
      setPublishConfirmHighRisk(false);
      setPublishChecklistAcks({});
      if (pageEditDraftStorageKey) {
        try {
          window.localStorage.removeItem(pageEditDraftStorageKey);
        } catch {
          // ignore storage errors
        }
      }
      setPageEditDraftState("idle");
      setPageEditDraftSavedAt(null);
      await loadPageDetail(selectedPageSlug);
      await loadPageHistory(selectedPageSlug);
      await loadWikiPages({ silent: true });
      await loadDrafts();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Publish failed",
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
    pageEditTitle,
    processSimulation?.risk?.should_block_publish,
    pageEditDraftStorageKey,
    publishChecklistAcks,
    publishConfirmHighRisk,
    projectId,
    publishSummary,
    reviewer,
    spacePublishChecklistPreset,
    selectedPageDetail?.latest_version?.markdown,
    selectedPageDetail?.page.page_type,
    selectedPageDetail?.page.title,
    selectedPageSlug,
  ]);

  const rollbackSelectedPageVersion = useCallback(async () => {
    if (!selectedPageSlug) {
      notifications.show({
        color: "red",
        title: "Page not selected",
        message: "Select page before rollback.",
      });
      return;
    }
    if (!projectId.trim() || !reviewer.trim()) {
      notifications.show({
        color: "red",
        title: "Missing reviewer or project",
        message: "Set Project ID and Reviewer before rollback.",
      });
      return;
    }
    const target =
      (pageHistory?.versions ?? []).find((item) => String(item.version) === String(historyTargetVersion || "")) || null;
    if (!target) {
      notifications.show({
        color: "red",
        title: "Version not selected",
        message: "Choose target version in history drawer.",
      });
      return;
    }
    const latestVersion = (pageHistory?.versions ?? [])[0]?.version ?? null;
    if (latestVersion != null && Number(target.version) === Number(latestVersion)) {
      notifications.show({
        color: "gray",
        title: "Already latest",
        message: `v${target.version} is already current version.`,
      });
      return;
    }
    setRollingBackPageVersion(true);
    try {
      const payload = await apiFetch<WikiPageUpdateResponse>(
        apiUrl,
        `/v1/wiki/pages/${encodeURIComponent(selectedPageSlug)}/rollback`,
        {
          method: "PUT",
          body: {
            project_id: projectId,
            rolled_back_by: reviewer.trim(),
            target_version: Number(target.version),
            status: selectedPageDetail?.page.status || "published",
            change_summary: rollbackSummaryInput.trim() || null,
          },
          idempotencyKey: randomKey(),
        },
      );
      notifications.show({
        color: "green",
        title: "Rollback completed",
        message: `${payload.page.title || selectedPageSlug}: now v${payload.page.current_version ?? target.version}.`,
      });
      await loadPageDetail(selectedPageSlug);
      await loadPageHistory(selectedPageSlug);
      await loadWikiPages({ silent: true });
      await loadDrafts();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Rollback failed",
        message: String(error),
      });
    } finally {
      setRollingBackPageVersion(false);
    }
  }, [
    apiUrl,
    historyTargetVersion,
    loadDrafts,
    loadPageDetail,
    loadPageHistory,
    loadWikiPages,
    pageHistory?.versions,
    projectId,
    reviewer,
    rollbackSummaryInput,
    selectedPageDetail?.page.status,
    selectedPageSlug,
  ]);

  const openHistoryDrawerForVersion = useCallback(
    (targetVersion?: number | null) => {
      if (selectedPageSlug) {
        void loadPageHistory(selectedPageSlug);
      }
      const target = targetVersion != null ? String(targetVersion) : null;
      if (target) {
        setHistoryTargetVersion(target);
        const versions = pageHistory?.versions ?? [];
        const idx = versions.findIndex((item) => String(item.version) === target);
        if (idx >= 0) {
          const baseCandidate = versions[Math.min(idx + 1, versions.length - 1)] || versions[idx];
          if (baseCandidate) {
            setHistoryBaseVersion(String(baseCandidate.version));
          }
        }
      }
      setHistoryDrawerOpen(true);
    },
    [loadPageHistory, pageHistory?.versions, selectedPageSlug],
  );

  const shareCurrentPage = useCallback(async () => {
    const project = projectId.trim();
    const currentPath = buildWikiPath(wikiBasePath, selectedPageSlug);
    const currentUrl = `${window.location.origin}${currentPath}${
      project ? `?project=${encodeURIComponent(project)}&wiki_status=published` : ""
    }`;
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(currentUrl);
      }
      notifications.show({
        color: "green",
        title: "Link copied",
        message: currentUrl,
      });
    } catch {
      notifications.show({
        color: "blue",
        title: "Share link",
        message: currentUrl,
      });
    }
  }, [projectId, selectedPageSlug, wikiBasePath]);

  const copyScopeDeepLink = useCallback(async () => {
    const params = new URLSearchParams();
    if (projectId.trim()) params.set("project", projectId.trim());
    if (selectedSpaceKey) params.set("wiki_space", selectedSpaceKey);
    if (selectedPageSlug) params.set("wiki_page", selectedPageSlug);
    if (coreWorkspaceTab !== "wiki") params.set("core_tab", coreWorkspaceTab);
    params.set("wiki_status", "published");
    const currentPath = buildWorkspacePath(wikiBasePath, coreWorkspaceRoute, selectedPageSlug);
    const scopeUrl = `${window.location.origin}${currentPath}${params.toString() ? `?${params.toString()}` : ""}`;
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(scopeUrl);
      }
      notifications.show({
        color: "green",
        title: "Scope link copied",
        message: scopeUrl,
      });
    } catch {
      notifications.show({
        color: "blue",
        title: "Scope link",
        message: scopeUrl,
      });
    }
  }, [coreWorkspaceRoute, coreWorkspaceTab, projectId, selectedPageSlug, selectedSpaceKey, wikiBasePath]);

  const moveWikiPageFromTree = useCallback(
    async (sourceSlug: string, targetParentSlug: string) => {
      const source = String(sourceSlug || "").trim();
      const targetParent = String(targetParentSlug || "").trim();
      if (!source || !targetParent || source === targetParent) return;
      if (!projectId.trim() || !reviewer.trim()) return;
      if (targetParent.startsWith(`${source}/`)) {
        notifications.show({
          color: "red",
          title: "Invalid move",
          message: "Cannot move a page inside its own subtree.",
        });
        return;
      }
      const sourceNode = pageNodes.find((item) => item.slug === source) || null;
      const leaf = source.split("/").filter(Boolean).pop() || "page";
      setMovingPage(true);
      try {
        const payload = await apiFetch<WikiPageMoveResponse>(
          apiUrl,
          `/v1/wiki/pages/${encodeURIComponent(source)}/reparent`,
          {
            method: "PUT",
            body: {
              project_id: projectId,
              updated_by: reviewer.trim(),
              parent_path: targetParent,
              slug_leaf: leaf,
              title: sourceNode?.title || null,
              include_descendants: true,
              change_summary: `Moved from ${source} to ${targetParent}/${leaf}`,
            },
            idempotencyKey: randomKey(),
          },
        );
        const nextSlug = String(payload.page.slug || "");
        notifications.show({
          color: "green",
          title: "Page moved",
          message: `${sourceNode?.title || source} -> ${nextSlug || "updated"}`,
        });
        if (nextSlug) {
          setSelectedSpaceKey(pageGroupKey(nextSlug));
          setSelectedPageSlug(nextSlug);
        }
        await loadWikiPages({ silent: true });
        if (nextSlug) {
          await loadPageDetail(nextSlug);
          await loadPageHistory(nextSlug);
        }
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Tree move failed",
          message: String(error),
        });
      } finally {
        setMovingPage(false);
        setDraggingPageSlug(null);
        setTreeDropTargetSlug(null);
      }
    },
    [apiUrl, loadPageDetail, loadPageHistory, loadWikiPages, pageNodes, projectId, reviewer],
  );

  const transitionWikiPageStatusForSlug = useCallback(
    async (slug: string, mode: "archive" | "restore") => {
      const normalizedSlug = String(slug || "").trim();
      if (!normalizedSlug) {
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
          `/v1/wiki/pages/${encodeURIComponent(normalizedSlug)}/${endpoint}`,
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
        const nextSlug = String(payload.page.slug || normalizedSlug);
        setSelectedSpaceKey(pageGroupKey(nextSlug));
        setSelectedPageSlug(nextSlug);
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
    [apiUrl, loadDrafts, loadPageDetail, loadPageHistory, loadWikiPages, projectId, reviewer],
  );

  const openLifecycleDrilldown = useCallback(
    (slug: string, target: "page" | "policy" | "policy_edit" | "review_assignments" | "drafts") => {
      const normalizedSlug = String(slug || "").trim();
      if (!normalizedSlug) return;
      setSelectedSpaceKey(pageGroupKey(normalizedSlug));
      setSelectedPageSlug(normalizedSlug);
      if (target === "drafts") {
        setCoreWorkspaceTab("drafts");
        scrollElementIntoViewWithRetry("wiki-draft-inbox", 8, 120);
        return;
      }
      setCoreWorkspaceTab("wiki");
      if (target === "policy") {
        void loadSpacePolicy(normalizedSlug);
        void loadSpacePolicyAudit(normalizedSlug);
        void loadSpacePolicyAdoptionSummary(normalizedSlug);
        scrollElementIntoViewWithRetry("wiki-policy-timeline", 10, 140);
        return;
      }
      if (target === "policy_edit") {
        void loadSpacePolicy(normalizedSlug);
        void loadSpacePolicyAudit(normalizedSlug);
        void loadSpacePolicyAdoptionSummary(normalizedSlug);
        scrollElementIntoViewWithRetry("wiki-governance-panel", 10, 140);
        return;
      }
      if (target === "review_assignments") {
        void loadPageReviewAssignments(normalizedSlug);
        scrollElementIntoViewWithRetry("wiki-review-assignments", 10, 140);
      }
    },
    [loadPageReviewAssignments, loadSpacePolicy, loadSpacePolicyAdoptionSummary, loadSpacePolicyAudit],
  );

  const createSelectedPageReviewTask = useCallback(async () => {
    if (!projectId.trim() || !reviewer.trim() || !selectedPageSlug) {
      notifications.show({
        color: "red",
        title: "Task context required",
        message: "Set Project ID + Reviewer and select a page before creating a review task.",
      });
      return;
    }
    setRunningLifecycleQuickAction(true);
    try {
      const titleBase = String(selectedPageDetail?.page.title || selectedPageSlug || "wiki_page").trim();
      const payload = await apiFetch<{ task: { id: string; title: string } }>(apiUrl, "/v1/tasks", {
        method: "POST",
        idempotencyKey: randomKey(),
        body: {
          project_id: projectId,
          title: `Lifecycle review: ${titleBase}`,
          description: `Governance review requested from wiki page context for \`${selectedPageSlug}\`.`,
          status: "todo",
          priority: "high",
          source: "human",
          assignee: reviewer.trim(),
          entity_key: selectedPageSlug,
          category: "wiki_governance",
          due_at: null,
          metadata: {
            source: "wiki_review_assignments_panel",
            page_slug: selectedPageSlug,
            page_title: titleBase,
          },
          created_by: reviewer.trim(),
        },
      });
      setCoreWorkspaceTab("tasks");
      notifications.show({
        color: "teal",
        title: "Task created",
        message: payload.task.title || `Created lifecycle task for ${selectedPageSlug}.`,
      });
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Create task failed",
        message: String(error),
      });
    } finally {
      setRunningLifecycleQuickAction(false);
    }
  }, [apiUrl, projectId, reviewer, selectedPageDetail?.page.title, selectedPageSlug]);

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
    const baseMetadata =
      spacePolicy?.metadata && typeof spacePolicy.metadata === "object" ? { ...spacePolicy.metadata } : {};
    if (spacePublishChecklistPreset === "none") {
      delete (baseMetadata as Record<string, unknown>).publish_checklist_preset;
    } else {
      (baseMetadata as Record<string, unknown>).publish_checklist_preset = spacePublishChecklistPreset;
    }
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
          metadata: baseMetadata,
        },
        idempotencyKey: randomKey(),
      });
      await loadSpacePolicy(selectedPageSlug);
      await loadSpacePolicyAudit(selectedPageSlug);
      await loadSpacePolicyAdoptionSummary(selectedPageSlug);
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
    loadSpacePolicyAdoptionSummary,
    loadSpacePolicyAudit,
    projectId,
    reviewer,
    selectedPageSlug,
    spaceCommentMode,
    spacePolicy?.metadata,
    spacePublishChecklistPreset,
    spaceReviewRequired,
    spaceWriteMode,
  ]);

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

  const applyCreateTemplate = useCallback(
    (templateKey: string) => {
      const template = PAGE_TEMPLATES.find((item) => item.key === templateKey);
      if (!template) return;
      const title = template.title;
      const space = guidedPageForm.spaceKey.trim() || "operations";
      const slug = normalizeWikiSlug(`${space}/${title}`, title);
      setGuidedPageForm((prev) => ({
        ...prev,
        title,
        slug,
        pageType: template.pageType,
        sectionHeading: template.sectionHeading,
        sectionStatement: template.statements[0] || "",
        changeSummary: `Created from template: ${template.title}`,
      }));
      setSelectedCreateTemplateKey(template.key);
      notifications.show({
        color: "teal",
        title: "Template selected",
        message: `${template.title} prefilled.`,
      });
    },
    [guidedPageForm.spaceKey],
  );

  const completeOnboarding = useCallback(() => {
    const project = projectId.trim();
    if (project) {
      try {
        window.localStorage.setItem(`${ONBOARDING_STORAGE_PREFIX}${project}`, "1");
      } catch {
        // ignore storage errors
      }
    }
    setShowOnboardingModal(false);
  }, [projectId]);

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

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      const key = event.key.toLowerCase();
      const mod = event.metaKey || event.ctrlKey;

      if (mod && key === "k") {
        event.preventDefault();
        setShowQuickNavModal(true);
        return;
      }
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

  useEffect(() => {
    if (!showQuickNavModal) return;
    setQuickNavSlug(selectedPageSlug || null);
    setQuickNavQuery("");
  }, [selectedPageSlug, showQuickNavModal]);

  const selectedPageNode = useMemo(
    () => pageNodes.find((item) => item.slug === selectedPageSlug) || null,
    [pageNodes, selectedPageSlug],
  );
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
  const isOperationsRoute = coreWorkspaceRoute === "operations";
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
    return matchesBootstrapPreview(bootstrapResult, {
      projectId,
      trustedSourceSystems: bootstrapTrustedSourceSystems,
      limit: bootstrapLimitValue,
      minConfidence: bootstrapMinConfidenceValue,
      requireConflictFree: bootstrapRequireConflictFree,
    });
  }, [
    bootstrapLimitValue,
    bootstrapMinConfidenceValue,
    bootstrapRequireConflictFree,
    bootstrapResult,
    bootstrapTrustedSourceSystems,
    projectId,
  ]);
  const recommendedBootstrapPreset = useMemo(() => resolveRecommendedBootstrapPreset(), [resolveRecommendedBootstrapPreset]);
  const agentOrgchartTeams = useMemo(() => {
    const nodes = agentOrgchart?.nodes ?? [];
    const byTeam = new Map<string, AgentOrgchartNode[]>();
    for (const node of nodes) {
      const team = String(node.team || "").trim() || "Unassigned";
      if (!byTeam.has(team)) {
        byTeam.set(team, []);
      }
      byTeam.get(team)!.push(node);
    }
    return Array.from(byTeam.entries())
      .map(([team, teamNodes]) => ({
        team,
        nodes: [...teamNodes].sort((a, b) =>
          String(a.display_name || a.agent_id).localeCompare(String(b.display_name || b.agent_id)),
        ),
      }))
      .sort((a, b) => b.nodes.length - a.nodes.length || a.team.localeCompare(b.team));
  }, [agentOrgchart]);
  const agentOrgchartNodeById = useMemo(() => {
    const map = new Map<string, AgentOrgchartNode>();
    for (const node of agentOrgchart?.nodes ?? []) {
      map.set(node.agent_id, node);
    }
    return map;
  }, [agentOrgchart]);
  const agentOrgchartEdgePreview = useMemo(() => {
    return (agentOrgchart?.edges ?? []).slice(0, 12);
  }, [agentOrgchart]);
  useEffect(() => {
    if (effectiveUiMode === "advanced" && !showWikiFilters) {
      setShowWikiFilters(true);
    }
  }, [effectiveUiMode, showWikiFilters]);

  useEffect(() => {
    if (isOperationsRoute) {
      setShowDraftOperationsTools(true);
      return;
    }
    if (showDraftOperationsTools) {
      setShowDraftOperationsTools(false);
    }
    if (showAdvancedDraftOps) {
      setShowAdvancedDraftOps(false);
    }
    if (showMigrationMode) {
      setShowMigrationMode(false);
    }
  }, [isOperationsRoute, showAdvancedDraftOps, showDraftOperationsTools, showMigrationMode]);

  useEffect(() => {
    if (bootstrapTrustedSourcesTouched) return;
    if (!projectId.trim()) return;
    const recommendedCsv = recommendedBootstrapPreset.trustedSourceSystems.join(",");
    if (!recommendedCsv) return;
    const currentCsv = normalizeSourceSystemCsv(bootstrapTrustedSources).join(",");
    if (currentCsv === recommendedCsv) return;
    setBootstrapTrustedSources(recommendedCsv);
  }, [
    bootstrapTrustedSources,
    bootstrapTrustedSourcesTouched,
    projectId,
    recommendedBootstrapPreset,
  ]);
  const latestPageVersion = useMemo(() => (pageHistory?.versions ?? [])[0] || null, [pageHistory]);
  const selectedPageRelatedPages = useMemo(() => {
    if (!selectedPageSlug) return [];
    const scopeKey = pageGroupKey(selectedPageSlug);
    return pageNodes
      .filter((item) => String(item.slug || "").trim() !== selectedPageSlug)
      .filter((item) => pageGroupKey(item.slug) === scopeKey)
      .sort((a, b) => {
        const tsA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const tsB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        if (tsA !== tsB) return tsB - tsA;
        return String(a.title || a.slug || "").localeCompare(String(b.title || b.slug || ""));
      })
      .slice(0, 10)
      .map((item) => ({
        slug: item.slug,
        title: item.title || item.slug,
        updated_at: item.updated_at,
      }));
  }, [pageNodes, selectedPageSlug]);
  const selectedPageRecentVersions = useMemo(() => {
    return (pageHistory?.versions ?? []).slice(0, 8).map((item) => ({
      version: Number(item.version || 0),
      created_by: String(item.created_by || ""),
      change_summary: item.change_summary || null,
      created_at: item.created_at || null,
    }));
  }, [pageHistory]);
  const historyVersionOptions = useMemo(() => {
    return (pageHistory?.versions ?? []).map((item) => ({
      value: String(item.version),
      label: `v${item.version} · ${fmtDate(item.created_at)}${item.created_by ? ` · ${item.created_by}` : ""}`,
    }));
  }, [pageHistory]);
  const historyTargetVersionItem = useMemo(() => {
    const versions = pageHistory?.versions ?? [];
    if (versions.length === 0) return null;
    const selected = versions.find((item) => String(item.version) === String(historyTargetVersion || ""));
    return selected || versions[0];
  }, [historyTargetVersion, pageHistory]);
  const historyBaseVersionItem = useMemo(() => {
    const versions = pageHistory?.versions ?? [];
    if (versions.length === 0) return null;
    const selected = versions.find((item) => String(item.version) === String(historyBaseVersion || ""));
    return selected || versions[Math.min(1, versions.length - 1)] || versions[0];
  }, [historyBaseVersion, pageHistory]);
  const historyDiffPreview = useMemo(() => {
    return buildInlineMarkdownDiff(
      String(historyBaseVersionItem?.markdown || ""),
      String(historyTargetVersionItem?.markdown || ""),
    );
  }, [historyBaseVersionItem?.markdown, historyTargetVersionItem?.markdown]);
  const latestHistoryVersionNumber = useMemo(() => {
    const latest = (pageHistory?.versions ?? [])[0];
    return latest ? Number(latest.version || 0) : null;
  }, [pageHistory]);
  const canRollbackTargetInOperations = useMemo(() => {
    if (!isOperationsRoute) return false;
    if (!selectedPageSlug) return false;
    if (!historyTargetVersionItem) return false;
    if (!projectId.trim() || !reviewer.trim()) return false;
    if (rollingBackPageVersion) return false;
    if (latestHistoryVersionNumber == null) return false;
    return Number(historyTargetVersionItem.version || 0) !== Number(latestHistoryVersionNumber);
  }, [
    historyTargetVersionItem,
    isOperationsRoute,
    latestHistoryVersionNumber,
    projectId,
    reviewer,
    rollingBackPageVersion,
    selectedPageSlug,
  ]);
  const selectedPageOpenDrafts = useMemo(() => {
    if (!selectedPageSlug) return [];
    return drafts
      .filter((item) => String(item.page.slug || "").trim() === selectedPageSlug && isOpenReviewDraft(item))
      .slice(0, 6);
  }, [drafts, selectedPageSlug]);
  const selectedPageConflictDraftCount = useMemo(
    () =>
      selectedPageOpenDrafts.filter((item) => item.status === "blocked_conflict" || item.decision === "conflict").length,
    [selectedPageOpenDrafts],
  );
  const selectedPageOpenReviewAssignmentsCount = useMemo(
    () => pageReviewAssignments.filter((item) => String(item.status || "").trim().toLowerCase() === "open").length,
    [pageReviewAssignments],
  );
  const selectedPageActivityAt = useMemo(() => {
    return (
      selectedPageNode?.latest_draft_at ||
      selectedPageDetail?.latest_version?.created_at ||
      selectedPageNode?.updated_at ||
      selectedPageNode?.created_at ||
      null
    );
  }, [
    selectedPageDetail?.latest_version?.created_at,
    selectedPageNode?.created_at,
    selectedPageNode?.latest_draft_at,
    selectedPageNode?.updated_at,
  ]);
  const selectedPageAgeDays = useMemo(() => pageAgeDays(selectedPageActivityAt), [selectedPageActivityAt]);
  const selectedPageLifecycleSuggestions = useMemo<PageLifecycleSuggestion[]>(() => {
    if (!selectedPageDetail || !selectedPageNode) return [];
    const status = String(selectedPageDetail.page.status || "").trim().toLowerCase();
    const ageDays = selectedPageAgeDays;
    const openDrafts = selectedPageOpenDrafts.length;
    const conflictDrafts = selectedPageConflictDraftCount;
    const openAssignments = selectedPageOpenReviewAssignmentsCount;
    const suggestions: PageLifecycleSuggestion[] = [];
    const latestDraftAgeDays = pageAgeDays(selectedPageNode.latest_draft_at);
    const hasRecentDraftActivity = latestDraftAgeDays != null && latestDraftAgeDays <= PAGE_RECENT_ACTIVITY_DAYS;

    if (conflictDrafts > 0) {
      suggestions.push({
        key: "resolve-conflicts",
        severity: "critical",
        title: "Conflicts are blocking trusted updates",
        detail: `${conflictDrafts} draft${conflictDrafts === 1 ? "" : "s"} require conflict resolution before this page can stabilize.`,
        action: {
          kind: "open_drafts",
          label: "Open drafts",
        },
      });
    }

    if (status === "published" && ageDays != null && ageDays >= PAGE_STALE_CRITICAL_DAYS && openDrafts === 0) {
      suggestions.push({
        key: "published-stale-critical",
        severity: "critical",
        title: "Page looks stale for active wiki",
        detail: `No updates for ${Math.floor(ageDays)} days. Archive if obsolete, or edit to refresh current process reality.`,
        action: {
          kind: "archive",
          label: "Archive page",
        },
      });
    } else if (status === "published" && ageDays != null && ageDays >= PAGE_STALE_WARNING_DAYS && openDrafts === 0) {
      suggestions.push({
        key: "published-stale-watch",
        severity: "watch",
        title: "Published page may need freshness check",
        detail: `No edits for ${Math.floor(ageDays)} days. Mark obsolete sections, or archive when no longer operational.`,
        action: {
          kind: "archive",
          label: "Archive if obsolete",
        },
      });
    }

    if (
      status === "draft" &&
      conflictDrafts === 0 &&
      openDrafts === 0 &&
      (ageDays == null || ageDays <= PAGE_STALE_WARNING_DAYS)
    ) {
      suggestions.push({
        key: "promote-reviewed",
        severity: "info",
        title: "Draft is stable enough for review stage",
        detail: "No open draft conflicts on this page. Promote to reviewed to put it in the publish lane.",
        action: {
          kind: "promote_reviewed",
          label: "Promote to reviewed",
        },
      });
    }

    if (status === "reviewed" && conflictDrafts === 0 && openAssignments === 0) {
      suggestions.push({
        key: "publish-reviewed",
        severity: "info",
        title: "Reviewed page is ready to publish",
        detail: "No open reviewer assignments or conflicts are detected. Publish to make it active for all agents.",
        action: {
          kind: "publish",
          label: "Open publish",
        },
      });
    }

    if (status === "archived" && (openDrafts > 0 || hasRecentDraftActivity)) {
      suggestions.push({
        key: "restore-archived",
        severity: "watch",
        title: "Archived page has new activity",
        detail: "Recent incoming drafts suggest this topic is active again. Restore page to include new knowledge safely.",
        action: {
          kind: "restore",
          label: "Restore page",
        },
      });
    }

    return suggestions.slice(0, 3);
  }, [
    selectedPageAgeDays,
    selectedPageConflictDraftCount,
    selectedPageDetail,
    selectedPageNode,
    selectedPageOpenDrafts,
    selectedPageOpenReviewAssignmentsCount,
  ]);
  const selectedPageHasStaleSuggestion = useMemo(
    () => selectedPageLifecycleSuggestions.some((item) => item.key.startsWith("published-stale")),
    [selectedPageLifecycleSuggestions],
  );
  useEffect(() => {
    if (!selectedPageSlug || selectedPageLifecycleSuggestions.length === 0) return;
    const signature = selectedPageLifecycleSuggestions.map((item) => item.key).join("|");
    if (!signature) return;
    if (lifecycleSuggestionSeenRef.current[selectedPageSlug] === signature) return;
    lifecycleSuggestionSeenRef.current[selectedPageSlug] = signature;
    setLifecycleAdvisorMetrics((prev) => ({
      ...prev,
      suggestionShown: prev.suggestionShown + 1,
    }));
  }, [selectedPageLifecycleSuggestions, selectedPageSlug]);
  useEffect(() => {
    if (!selectedPageSlug) return;
    const nowMs = Date.now();
    setLifecycleAdvisorMetrics((prev) => {
      const currentStartedAt = prev.staleShownAtBySlug[selectedPageSlug];
      if (selectedPageHasStaleSuggestion) {
        if (currentStartedAt) return prev;
        return {
          ...prev,
          staleShownAtBySlug: {
            ...prev.staleShownAtBySlug,
            [selectedPageSlug]: nowMs,
          },
        };
      }
      if (!currentStartedAt) return prev;
      const nextStaleMap = { ...prev.staleShownAtBySlug };
      delete nextStaleMap[selectedPageSlug];
      return {
        ...prev,
        staleShownAtBySlug: nextStaleMap,
        staleResolvedDurationsMs: [...prev.staleResolvedDurationsMs.slice(-199), Math.max(0, nowMs - currentStartedAt)],
      };
    });
  }, [selectedPageHasStaleSuggestion, selectedPageSlug]);
  const activePublishChecklistPreset = useMemo(
    () => PUBLISH_CHECKLIST_PRESETS.find((item) => item.key === spacePublishChecklistPreset) || PUBLISH_CHECKLIST_PRESETS[0],
    [spacePublishChecklistPreset],
  );
  const localSpacePolicyAdoptionSummary = useMemo(
    () => summarizeSpacePolicyAudit(spacePolicyAudit),
    [spacePolicyAudit],
  );
  const spacePolicyAdoptionSummary = useMemo(
    () => spacePolicyAdoptionSummaryApi || localSpacePolicyAdoptionSummary,
    [localSpacePolicyAdoptionSummary, spacePolicyAdoptionSummaryApi],
  );
  const activePublishChecklistItems = activePublishChecklistPreset.items;
  const isPublishChecklistComplete = useMemo(() => {
    if (activePublishChecklistItems.length === 0) return true;
    return activePublishChecklistItems.every((item) => Boolean(publishChecklistAcks[item.id]));
  }, [activePublishChecklistItems, publishChecklistAcks]);
  useEffect(() => {
    if (!showPublishModal) {
      setPublishChecklistAcks({});
      return;
    }
    if (activePublishChecklistItems.length === 0) {
      setPublishChecklistAcks({});
      return;
    }
    setPublishChecklistAcks((prev) => {
      const next: Record<string, boolean> = {};
      for (const item of activePublishChecklistItems) {
        next[item.id] = Boolean(prev[item.id]);
      }
      return next;
    });
  }, [activePublishChecklistItems, showPublishModal]);
  const wikiHomeRecentPages = useMemo(() => {
    return [...pageNodes]
      .sort((a, b) => {
        const tsA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
        const tsB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
        return tsB - tsA;
      })
      .slice(0, 8);
  }, [pageNodes]);
  const quickNavMatches = useMemo(() => {
    const query = quickNavQuery.trim().toLowerCase();
    if (!query) return wikiHomeRecentPages.slice(0, 8);
    return pageNodes
      .filter((page) => {
        const title = String(page.title || "").toLowerCase();
        const slug = String(page.slug || "").toLowerCase();
        return title.includes(query) || slug.includes(query);
      })
      .slice(0, 10);
  }, [pageNodes, quickNavQuery, wikiHomeRecentPages]);
  const lifecycleTelemetrySummary = useMemo(() => {
    if (!wikiLifecycleTelemetry) return null;
    const actions = Array.isArray(wikiLifecycleTelemetry.summary?.actions) ? wikiLifecycleTelemetry.summary.actions : [];
    const topActions = actions
      .slice()
      .sort((a, b) => Number(b.applied_total || 0) - Number(a.applied_total || 0))
      .slice(0, 3);
    const recentDaily = Array.isArray(wikiLifecycleTelemetry.daily) ? wikiLifecycleTelemetry.daily.slice(-7) : [];
    return {
      days: Number(wikiLifecycleTelemetry.days || LIFECYCLE_TELEMETRY_WINDOW_DAYS),
      shownTotal: Number(wikiLifecycleTelemetry.summary?.shown_total || 0),
      appliedTotal: Number(wikiLifecycleTelemetry.summary?.applied_total || 0),
      applyRate: Number(wikiLifecycleTelemetry.summary?.apply_rate || 0),
      topActions,
      recentDaily,
      generatedAt: wikiLifecycleTelemetry.generated_at,
    };
  }, [wikiLifecycleTelemetry]);
  const lifecycleTelemetryActionSummary = useMemo(() => {
    const requestedActionKey = normalizeTelemetryActionKey(lifecycleTelemetryActionKey || "");
    if (!requestedActionKey) return null;
    if (!wikiLifecycleTelemetryAction) return null;
    const actions = Array.isArray(wikiLifecycleTelemetryAction.summary?.actions) ? wikiLifecycleTelemetryAction.summary.actions : [];
    const selectedAction =
      actions.find((item) => normalizeTelemetryActionKey(String(item.action_key || "")) === requestedActionKey) || null;
    const shownTotal = Number(
      selectedAction?.shown_total ?? wikiLifecycleTelemetryAction.summary?.shown_total ?? 0,
    );
    const appliedTotal = Number(
      selectedAction?.applied_total ?? wikiLifecycleTelemetryAction.summary?.applied_total ?? 0,
    );
    const applyRate = selectedAction
      ? Number(selectedAction.apply_rate || 0)
      : shownTotal > 0
        ? appliedTotal / shownTotal
        : 0;
    const recentDaily = Array.isArray(wikiLifecycleTelemetryAction.daily) ? wikiLifecycleTelemetryAction.daily.slice(-7) : [];
    return {
      actionKey: requestedActionKey,
      days: Number(wikiLifecycleTelemetryAction.days || LIFECYCLE_TELEMETRY_WINDOW_DAYS),
      shownTotal,
      appliedTotal,
      applyRate,
      recentDaily,
      generatedAt: wikiLifecycleTelemetryAction.generated_at,
    };
  }, [lifecycleTelemetryActionKey, wikiLifecycleTelemetryAction]);

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

  const renderConfluenceTreeNode = (node: WikiTreeNode) => {
    const isSelected = Boolean(node.slug && selectedPageSlug === node.slug);
    const isDropTarget = Boolean(
      node.slug && treeDropTargetSlug === node.slug && draggingPageSlug && draggingPageSlug !== node.slug,
    );
    const isCollapsed = Boolean(collapsedTreeNodes[node.key]);
    const hasChildren = node.children.length > 0;
    const rowPad = 10 + Math.max(0, node.depth) * 14;
    const pageStatus = String(node.page?.status || "").trim().toLowerCase();
    const nodeActivityAt = node.page?.latest_draft_at || node.page?.updated_at || node.page?.created_at || null;
    const nodeAgeDays = pageAgeDays(nodeActivityAt);
    const isNodeStaleWarning =
      pageStatus === "published" &&
      nodeAgeDays != null &&
      nodeAgeDays >= PAGE_STALE_WARNING_DAYS &&
      node.page != null &&
      Number(node.page.open_count || 0) === 0;
    const isNodeStaleCritical = isNodeStaleWarning && nodeAgeDays != null && nodeAgeDays >= PAGE_STALE_CRITICAL_DAYS;
    return (
      <Stack key={node.key} gap={2}>
        <Group
          className={`${isSelected ? "confluence-tree-row active" : "confluence-tree-row"}${isDropTarget ? " drop-target" : ""}`}
          style={{ paddingLeft: rowPad }}
          gap={6}
          wrap="nowrap"
          draggable={Boolean(node.slug)}
          onDragStart={(event) => {
            if (!node.slug) return;
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", node.slug);
            setDraggingPageSlug(node.slug);
          }}
          onDragEnd={() => {
            setDraggingPageSlug(null);
            setTreeDropTargetSlug(null);
          }}
          onDragOver={(event) => {
            if (!node.slug || !draggingPageSlug || draggingPageSlug === node.slug) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            setTreeDropTargetSlug(node.slug);
          }}
          onDragLeave={() => {
            if (treeDropTargetSlug === node.slug) {
              setTreeDropTargetSlug(null);
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            if (!node.slug) return;
            const source = draggingPageSlug || event.dataTransfer.getData("text/plain");
            if (!source || source === node.slug) return;
            void moveWikiPageFromTree(source, node.slug);
          }}
          onClick={() => {
            if (!node.slug) return;
            setSelectedSpaceKey(pageGroupKey(node.slug));
            setSelectedPageSlug(node.slug);
          }}
        >
          {hasChildren ? (
            <ActionIcon
              size="sm"
              variant="subtle"
              color="gray"
              onClick={(event) => {
                event.stopPropagation();
                setCollapsedTreeNodes((prev) => ({ ...prev, [node.key]: !prev[node.key] }));
              }}
              aria-label={isCollapsed ? `Expand ${node.label}` : `Collapse ${node.label}`}
            >
              {isCollapsed ? <IconChevronDown size={12} /> : <IconChevronUp size={12} />}
            </ActionIcon>
          ) : (
            <Box w={22} />
          )}
          <Text size="sm" fw={isSelected ? 700 : 500} lineClamp={1} style={{ flex: 1 }}>
            {node.label}
          </Text>
          <Group gap={4} wrap="nowrap">
            {isNodeStaleWarning ? (
              <Tooltip
                label={
                  isNodeStaleCritical
                    ? `No updates for ${Math.floor(nodeAgeDays || 0)} days. Consider archive or refresh.`
                    : `No updates for ${Math.floor(nodeAgeDays || 0)} days. Check freshness.`
                }
              >
                <Badge size="xs" variant="light" color={isNodeStaleCritical ? "red" : "orange"}>
                  stale
                </Badge>
              </Tooltip>
            ) : null}
            {node.open_count > 0 ? (
              <Badge size="xs" variant="light" color="orange">
                {node.open_count}
              </Badge>
            ) : null}
            {node.slug ? (
              <Menu shadow="md" width={168} withinPortal position="bottom-end">
                <Menu.Target>
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="gray"
                    aria-label={`Open actions for ${node.label}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <IconDots size={12} />
                  </ActionIcon>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedSpaceKey(pageGroupKey(node.slug!));
                      setSelectedPageSlug(node.slug!);
                      setCoreWorkspaceTab("wiki");
                    }}
                  >
                    Open
                  </Menu.Item>
                  <Menu.Item
                    onClick={(event) => {
                      event.stopPropagation();
                      const segments = node.slug!.split("/").filter(Boolean);
                      const leaf = segments[segments.length - 1] || "page";
                      const parent = segments.slice(0, -1).join("/");
                      setSelectedSpaceKey(pageGroupKey(node.slug!));
                      setSelectedPageSlug(node.slug!);
                      setPageMoveParentPath(parent);
                      setPageMoveSlugLeaf(leaf);
                      setPageMoveTitle(node.page?.title || leaf);
                      setPageMoveSummary("Page move/rename");
                      setPageMoveIncludeDescendants(true);
                      setPageEditMode(false);
                      setPageMoveMode(true);
                    }}
                  >
                    Move / Rename
                  </Menu.Item>
                  {pageStatus === "archived" ? (
                    <Menu.Item
                      onClick={(event) => {
                        event.stopPropagation();
                        void transitionWikiPageStatusForSlug(node.slug!, "restore");
                      }}
                    >
                      Restore
                    </Menu.Item>
                  ) : (
                    <Menu.Item
                      color="red"
                      onClick={(event) => {
                        event.stopPropagation();
                        void transitionWikiPageStatusForSlug(node.slug!, "archive");
                      }}
                    >
                      Archive
                    </Menu.Item>
                  )}
                </Menu.Dropdown>
              </Menu>
            ) : null}
          </Group>
        </Group>
        {hasChildren && !isCollapsed ? node.children.map((child) => renderConfluenceTreeNode(child)) : null}
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
                Authenticate once, then you will land directly in your company wiki.
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

  if (uiMode === "core" || !CAN_ACCESS_ADVANCED_MODE) {
    return (
      <Box className="confluence-shell">
        <CoreWorkspaceTopBar
          isOperationsRoute={isOperationsRoute}
          coreWorkspaceTab={coreWorkspaceTab}
          pageFilter={pageFilter}
          selectedPageSlug={selectedPageSlug}
          pageEditMode={pageEditMode}
          projectId={projectId}
          scopeSpaceLabel={scopeSpaceLabel}
          scopePageLabel={scopePageLabel}
          selectedSpaceKey={selectedSpaceKey}
          onOpenWiki={() => {
            setCoreWorkspaceRoute("wiki");
            setCoreWorkspaceTab("wiki");
          }}
          onOpenDrafts={() => {
            setCoreWorkspaceRoute("wiki");
            setCoreWorkspaceTab("drafts");
          }}
          onOpenTasks={() => {
            setCoreWorkspaceRoute("wiki");
            setCoreWorkspaceTab("tasks");
          }}
          onOpenOperations={() => {
            setCoreWorkspaceRoute("operations");
            setCoreWorkspaceTab("drafts");
          }}
          onPageFilterChange={setPageFilter}
          onToggleCreate={() => {
            setShowCoreCreatePanel((prev) => !prev);
            setCoreWorkspaceRoute("wiki");
            setCoreWorkspaceTab("wiki");
          }}
          onShareCurrentPage={() => {
            void shareCurrentPage();
          }}
          onEditPage={() => {
            setPageMoveMode(false);
            setPageEditMode(true);
          }}
          onOpenPublish={() => {
            setProcessSimulation(null);
            setPublishConfirmHighRisk(false);
            setShowPublishModal(true);
          }}
          onSync={() => {
            void loadWikiPages();
            void loadDrafts();
          }}
          onCopyScopeLink={() => {
            void copyScopeDeepLink();
          }}
          onClearSpaceScope={() => {
            setSelectedSpaceKey(null);
            setLifecycleSpaceFilter(LIFECYCLE_SPACE_FILTER_ALL);
          }}
          onOpenRolesGuide={() => setShowRolesGuideModal(true)}
        />
        {selfhostConsistency?.status === "warning" ? (
          <Alert
            variant="light"
            color="yellow"
            icon={<IconAlertTriangle size={16} />}
            title="Self-host consistency warning"
            mx="md"
            mt="sm"
          >
            {(selfhostConsistency.checks || [])
              .filter((item) => item.status !== "ok")
              .map((item) => item.message || item.key)
              .slice(0, 2)
              .join(" ")}
          </Alert>
        ) : null}
        {loadingSelfhostConsistency ? (
          <Text size="xs" c="dimmed" px="md" mt={6}>
            Checking UI/API consistency…
          </Text>
        ) : null}
        {spaceRecoveryNotice ? (
          <Alert
            variant="light"
            color="blue"
            icon={<IconArrowsShuffle size={16} />}
            title="Wiki scope adjusted"
            mx="md"
            mt="sm"
            withCloseButton
            onClose={() => setSpaceRecoveryNotice(null)}
          >
            {spaceRecoveryNotice.reason === "missing_space"
              ? `Saved space "${spaceRecoveryNotice.from || "unknown"}" had no pages here, so Synapse opened "${spaceRecoveryNotice.to}" instead.`
              : `Current space "${spaceRecoveryNotice.from || "unknown"}" had no published wiki pages, so Synapse opened richer space "${spaceRecoveryNotice.to}".`}
          </Alert>
        ) : null}

        <Box className="confluence-layout">
          <CoreWorkspaceLeftRail
            projectId={projectId}
            reviewer={reviewer}
            selectedSpaceKey={selectedSpaceKey}
            pageStatusFilter={pageStatusFilter}
            spaceOptions={spaceNodes.map((space) => ({
              value: space.key,
              label: `${space.title} (${space.page_count})`,
            }))}
            pageCount={pageNodes.length}
            onProjectIdChange={setProjectId}
            onReviewerChange={setReviewer}
            onSpaceChange={setSelectedSpaceKey}
            onPageStatusChange={setPageStatusFilter}
            lifecyclePanel={
              <Paper withBorder p="xs" radius="md" id="core-left-lifecycle">
                <Stack gap={6}>
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Text size="xs" fw={700}>
                      Lifecycle
                    </Text>
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      loading={loadingWikiLifecycleStats}
                      disabled={!projectId.trim()}
                      onClick={() => void loadWikiLifecycleStats()}
                    >
                      Refresh
                    </Button>
                  </Group>
                  {!projectId.trim() ? (
                    <Text size="xs" c="dimmed">
                      Set workspace to load lifecycle diagnostics.
                    </Text>
                  ) : loadingWikiLifecycleStats && !wikiLifecycleStats ? (
                    <Group gap={6}>
                      <Loader size="xs" />
                      <Text size="xs" c="dimmed">
                        loading…
                      </Text>
                    </Group>
                  ) : !wikiLifecycleStats ? (
                    <Text size="xs" c="dimmed">
                      Lifecycle stats unavailable.
                    </Text>
                  ) : (
                    <>
                      <Group gap={6} wrap="wrap">
                        <Badge size="xs" variant="light" color="teal">
                          pub {wikiLifecycleStats.counts.published_pages}
                        </Badge>
                        <Badge size="xs" variant="light" color="orange">
                          stale {wikiLifecycleStats.counts.stale_warning_pages}
                        </Badge>
                        <Badge size="xs" variant="light" color="red">
                          critical {wikiLifecycleStats.counts.stale_critical_pages}
                        </Badge>
                      </Group>
                      {isOperationsRoute ? (
                        <>
                          <Group justify="space-between" align="center" wrap="wrap">
                            <Text size="xs" c="dimmed">
                              Lifecycle diagnostics are available on demand.
                            </Text>
                            <Button
                              size="compact-xs"
                              variant={showCoreLifecycleDetails ? "filled" : "light"}
                              color={showCoreLifecycleDetails ? "blue" : "gray"}
                              onClick={() => setShowCoreLifecycleDetails((value) => !value)}
                            >
                              {showCoreLifecycleDetails ? "Hide details" : "Show details"}
                            </Button>
                          </Group>
                          {showCoreLifecycleDetails ? (
                            <>
                              {loadingWikiLifecycleTelemetry ? (
                                <Group gap={6}>
                                  <Loader size="xs" />
                                  <Text size="xs" c="dimmed">
                                    loading action mix…
                                  </Text>
                                </Group>
                              ) : lifecycleTelemetrySummary ? (
                                <Paper withBorder p={6} radius="sm" data-testid="core-lifecycle-action-mix">
                                  <Stack gap={4}>
                                    <Text size="xs" fw={700}>
                                      Action mix ({lifecycleTelemetrySummary.days}d)
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                      shown {lifecycleTelemetrySummary.shownTotal} • applied {lifecycleTelemetrySummary.appliedTotal} • apply rate{" "}
                                      {(lifecycleTelemetrySummary.applyRate * 100).toFixed(1)}%
                                    </Text>
                                    {lifecycleTelemetrySummary.topActions.length > 0 ? (
                                      <Group gap={4} wrap="wrap">
                                        {lifecycleTelemetrySummary.topActions.map((item) => (
                                          <Button
                                            key={`core-lifecycle-action-top-${item.action_key}`}
                                            data-testid={`core-lifecycle-action-open-${normalizeTelemetryActionKey(item.action_key)}`}
                                            size="xs"
                                            variant={
                                              lifecycleTelemetryActionKey === normalizeTelemetryActionKey(item.action_key)
                                                ? "filled"
                                                : "light"
                                            }
                                            color={
                                              lifecycleTelemetryActionKey === normalizeTelemetryActionKey(item.action_key)
                                                ? "blue"
                                                : item.applied_total > 0
                                                  ? "blue"
                                                  : "gray"
                                            }
                                            onClick={() => toggleLifecycleTelemetryActionDrilldown(item.action_key)}
                                          >
                                            {item.action_key} {item.applied_total}/{item.shown_total}
                                          </Button>
                                        ))}
                                      </Group>
                                    ) : null}
                                    {lifecycleTelemetrySummary.recentDaily.length > 0 ? (
                                      <Group gap={4} wrap="wrap">
                                        {lifecycleTelemetrySummary.recentDaily.map((item) => (
                                          <Badge
                                            key={`core-lifecycle-action-day-${item.metric_date}`}
                                            size="xs"
                                            variant="outline"
                                            color={item.applied_total > 0 ? "indigo" : "gray"}
                                          >
                                            {item.metric_date.slice(5)} {item.applied_total}/{item.shown_total}
                                          </Badge>
                                        ))}
                                      </Group>
                                    ) : null}
                                    {loadingWikiLifecycleTelemetryAction && lifecycleTelemetryActionKey ? (
                                      <Group gap={6}>
                                        <Loader size="xs" />
                                        <Text size="xs" c="dimmed">
                                          loading action drill-down…
                                        </Text>
                                      </Group>
                                    ) : lifecycleTelemetryActionSummary ? (
                                      <Paper withBorder p={6} radius="sm" data-testid="wiki-lifecycle-action-detail" id="core-lifecycle-action-detail">
                                        <Stack gap={4}>
                                          <Group justify="space-between" align="center" wrap="wrap">
                                            <Text size="xs" fw={700}>
                                              Drill-down: {lifecycleTelemetryActionSummary.actionKey} ({lifecycleTelemetryActionSummary.days}d)
                                            </Text>
                                            <Button
                                              size="compact-xs"
                                              variant="subtle"
                                              color="gray"
                                              onClick={() => setLifecycleTelemetryActionKey(null)}
                                            >
                                              Clear
                                            </Button>
                                          </Group>
                                          <Text size="xs" c="dimmed">
                                            shown {lifecycleTelemetryActionSummary.shownTotal} • applied {lifecycleTelemetryActionSummary.appliedTotal} •
                                            apply rate {(lifecycleTelemetryActionSummary.applyRate * 100).toFixed(1)}%
                                          </Text>
                                          {lifecycleTelemetryActionSummary.recentDaily.length > 0 ? (
                                            <Group gap={4} wrap="wrap">
                                              {lifecycleTelemetryActionSummary.recentDaily.map((item) => (
                                                <Badge
                                                  key={`core-lifecycle-action-drill-day-${item.metric_date}`}
                                                  size="xs"
                                                  variant="outline"
                                                  color={item.applied_total > 0 ? "blue" : "gray"}
                                                >
                                                  {item.metric_date.slice(5)} {item.applied_total}/{item.shown_total}
                                                </Badge>
                                              ))}
                                            </Group>
                                          ) : null}
                                        </Stack>
                                      </Paper>
                                    ) : null}
                                  </Stack>
                                </Paper>
                              ) : null}
                              <Group gap={4} wrap="wrap">
                                {LIFECYCLE_QUERY_PRESETS.map((preset) => (
                                  <Button
                                    key={`core-lifecycle-preset-${preset.key}`}
                                    data-testid={`core-lifecycle-preset-${preset.key}`}
                                    size="compact-xs"
                                    variant={lifecycleQueryPreset === preset.key ? "filled" : "light"}
                                    color={lifecycleQueryPreset === preset.key ? "blue" : "gray"}
                                    onClick={() => applyLifecycleQueryPreset(preset.key)}
                                  >
                                    {preset.label}
                                  </Button>
                                ))}
                              </Group>
                              {lifecycleQueryPreset === "custom" ? (
                                <Group gap={6} wrap="nowrap">
                                  <TextInput
                                    size="xs"
                                    type="number"
                                    label="Stale days"
                                    value={String(lifecycleStaleDays)}
                                    onChange={(event) => {
                                      const value = Number(event.currentTarget.value);
                                      if (!Number.isFinite(value)) return;
                                      setLifecycleStaleDays(Math.max(1, Math.min(365, Math.round(value))));
                                    }}
                                    styles={{ root: { width: 120 } }}
                                  />
                                  <TextInput
                                    size="xs"
                                    type="number"
                                    label="Critical days"
                                    value={String(lifecycleCriticalDays)}
                                    onChange={(event) => {
                                      const value = Number(event.currentTarget.value);
                                      if (!Number.isFinite(value)) return;
                                      setLifecycleCriticalDays(Math.max(1, Math.min(365, Math.round(value))));
                                    }}
                                    styles={{ root: { width: 120 } }}
                                  />
                                </Group>
                              ) : null}
                              {lifecycleSpaceChips.length > 0 ? (
                                <Group gap={4} wrap="wrap">
                                  <Button
                                    data-testid="core-lifecycle-space-chip-all"
                                    size="compact-xs"
                                    variant={lifecycleSpaceFilter === LIFECYCLE_SPACE_FILTER_ALL ? "filled" : "light"}
                                    color={lifecycleSpaceFilter === LIFECYCLE_SPACE_FILTER_ALL ? "blue" : "gray"}
                                    onClick={() => {
                                      setLifecycleSpaceFilter(LIFECYCLE_SPACE_FILTER_ALL);
                                      setSelectedSpaceKey(null);
                                    }}
                                  >
                                    All {wikiLifecycleStats.stale_pages.length}
                                  </Button>
                                  {lifecycleSpaceChips.map((space) => (
                                    <Button
                                      key={`core-lifecycle-space-chip-${space.key}`}
                                      data-testid={`core-lifecycle-space-chip-${space.key}`}
                                      size="compact-xs"
                                      variant={lifecycleSpaceFilter === space.key ? "filled" : "light"}
                                      color={lifecycleSpaceFilter === space.key ? "blue" : "gray"}
                                      onClick={() => {
                                        setLifecycleSpaceFilter(space.key);
                                        setSelectedSpaceKey(space.key);
                                      }}
                                    >
                                      {space.title} {space.staleCount}
                                    </Button>
                                  ))}
                                </Group>
                              ) : null}
                              {wikiLifecycleStats.stale_pages.length === 0 ? (
                                <Stack gap={4}>
                                  <Text size="xs" c="dimmed">
                                    No stale pages.
                                  </Text>
                                  {lifecycleEmptyScope ? (
                                    <Paper withBorder p={6} radius="sm" data-testid="core-lifecycle-empty-scope">
                                      <Stack gap={2}>
                                        <Text size="xs" fw={700}>
                                          Reason: {lifecycleEmptyScope.code}
                                        </Text>
                                        <Text size="xs" c="dimmed">
                                          {lifecycleEmptyScope.message}
                                        </Text>
                                        {lifecycleEmptyScope.details ? (
                                          <Text size="xs" c="dimmed">
                                            published {lifecycleEmptyScope.details.published_pages ?? 0} • with open drafts{" "}
                                            {lifecycleEmptyScope.details.published_pages_with_open_drafts ?? 0} • below threshold{" "}
                                            {lifecycleEmptyScope.details.published_pages_below_stale_threshold ?? 0}
                                          </Text>
                                        ) : null}
                                        {Array.isArray(lifecycleEmptyScope.suggested_actions) &&
                                        lifecycleEmptyScope.suggested_actions.length > 0 ? (
                                          <Group gap={4} wrap="wrap">
                                            {lifecycleEmptyScope.suggested_actions.map((item) => (
                                              <Button
                                                key={`core-lifecycle-empty-action-${item.action}-${item.label}`}
                                                size="compact-xs"
                                                variant="light"
                                                color="gray"
                                                data-testid={`core-lifecycle-empty-action-${item.action}`}
                                                onClick={() => runLifecycleEmptyScopeAction(item.action, item.deep_link)}
                                              >
                                                {item.label}
                                              </Button>
                                            ))}
                                          </Group>
                                        ) : null}
                                      </Stack>
                                    </Paper>
                                  ) : null}
                                </Stack>
                              ) : lifecycleVisibleStalePages.length === 0 ? (
                                <Text size="xs" c="dimmed">
                                  No stale pages in selected space.
                                </Text>
                              ) : (
                                <Stack gap={4}>
                                  {lifecycleVisibleStalePages.slice(0, 3).map((item) => (
                                    <Group key={`core-left-stale-${item.slug}`} justify="space-between" align="center" wrap="nowrap">
                                      <Button
                                        size="compact-xs"
                                        variant="subtle"
                                        color="gray"
                                        onClick={() => openLifecycleDrilldown(item.slug, "page")}
                                      >
                                        {item.title || item.slug}
                                      </Button>
                                      <Group gap={4} wrap="nowrap">
                                        <Button
                                          size="compact-xs"
                                          variant="subtle"
                                          color="violet"
                                          onClick={() => openLifecycleDrilldown(item.slug, "policy")}
                                        >
                                          Policy
                                        </Button>
                                        <Badge size="xs" variant="light" color={item.severity === "critical" ? "red" : "orange"}>
                                          {Math.round(Number(item.age_days || 0))}d
                                        </Badge>
                                      </Group>
                                    </Group>
                                  ))}
                                </Stack>
                              )}
                            </>
                          ) : (
                            <Text size="xs" c="dimmed">
                              Open details only when you need drill-down actions.
                            </Text>
                          )}
                        </>
                      ) : (
                        <Paper withBorder p={6} radius="sm">
                          <Stack gap={4}>
                            <Text size="xs" c="dimmed">
                              Detailed lifecycle diagnostics are available only in Operations.
                            </Text>
                            <Group gap={6} wrap="wrap">
                              <Button
                                size="compact-xs"
                                variant="light"
                                color="indigo"
                                onClick={() => {
                                  setCoreWorkspaceRoute("operations");
                                  setCoreWorkspaceTab("drafts");
                                }}
                              >
                                Open ops diagnostics
                              </Button>
                              <Button
                                size="compact-xs"
                                variant="subtle"
                                color="gray"
                                loading={loadingWikiLifecycleStats}
                                onClick={() => void loadWikiLifecycleStats()}
                              >
                                Refresh stats
                              </Button>
                            </Group>
                          </Stack>
                        </Paper>
                      )}
                    </>
                  )}
                </Stack>
              </Paper>
            }
            treeContent={
              wikiTreeNodes.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No pages yet.
                </Text>
              ) : (
                wikiTreeNodes.map((node) => renderConfluenceTreeNode(node))
              )
            }
          />

          <Paper className="confluence-main" withBorder>
            {coreWorkspaceTab === "tasks" ? (
              <Suspense
                fallback={
                  <Group gap={8}>
                    <Loader size="sm" />
                    <Text size="sm" c="dimmed">
                      Loading tasks…
                    </Text>
                  </Group>
                }
              >
                <LazyTaskTrackerPanel apiUrl={apiUrl} projectId={projectId} reviewer={reviewer} />
              </Suspense>
            ) : coreWorkspaceTab === "drafts" ? (
              <CoreDraftTab
                isOperationsRoute={isOperationsRoute}
                visibleDraftCount={visibleDrafts.length}
                onToggleOperationsRoute={() => {
                  if (isOperationsRoute) {
                    setCoreWorkspaceRoute("wiki");
                    setCoreWorkspaceTab("drafts");
                    return;
                  }
                  setCoreWorkspaceRoute("operations");
                  setCoreWorkspaceTab("drafts");
                }}
                migrationPanel={
                  isOperationsRoute ? (
                    <Stack gap="sm">
                      <Paper withBorder p="sm" radius="md" data-testid="operations-worklog-policy">
                        <Stack gap="xs">
                          <Group justify="space-between" align="center" wrap="wrap">
                            <Text size="sm" fw={700}>
                              Agent Worklog Policy
                            </Text>
                            <Badge size="xs" variant="light" color="blue">
                              project policy
                            </Badge>
                          </Group>
                          <Text size="xs" c="dimmed">
                            Configure daily agent report generation and realtime trigger behavior.
                          </Text>
                          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="xs">
                            <TextInput
                              size="xs"
                              label="Timezone"
                              value={agentWorklogTimezone}
                              onChange={(event) => setAgentWorklogTimezone(event.currentTarget.value)}
                              placeholder="Europe/Moscow"
                            />
                            <TextInput
                              size="xs"
                              type="number"
                              label="Daily hour (local)"
                              value={agentWorklogScheduleHour}
                              onChange={(event) => setAgentWorklogScheduleHour(event.currentTarget.value)}
                              placeholder="2"
                            />
                            <TextInput
                              size="xs"
                              type="number"
                              label="Daily minute (local)"
                              value={agentWorklogScheduleMinute}
                              onChange={(event) => setAgentWorklogScheduleMinute(event.currentTarget.value)}
                              placeholder="0"
                            />
                            <TextInput
                              size="xs"
                              type="number"
                              label="Min activity score"
                              value={agentWorklogMinActivityScore}
                              onChange={(event) => setAgentWorklogMinActivityScore(event.currentTarget.value)}
                              placeholder="2"
                            />
                          </SimpleGrid>
                          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
                            <Checkbox
                              label="Include idle days"
                              checked={agentWorklogIncludeIdleDays}
                              onChange={(event) => setAgentWorklogIncludeIdleDays(event.currentTarget.checked)}
                            />
                            <Checkbox
                              label="Enable realtime worklog sync"
                              checked={agentWorklogRealtimeEnabled}
                              onChange={(event) => setAgentWorklogRealtimeEnabled(event.currentTarget.checked)}
                            />
                          </SimpleGrid>
                          <TextInput
                            size="xs"
                            type="number"
                            label="Realtime lookback (minutes)"
                            value={agentWorklogRealtimeLookbackMinutes}
                            onChange={(event) => setAgentWorklogRealtimeLookbackMinutes(event.currentTarget.value)}
                            placeholder="30"
                            disabled={!agentWorklogRealtimeEnabled}
                          />
                          <Group gap="xs" wrap="wrap">
                            <Button
                              size="xs"
                              variant="light"
                              color="blue"
                              loading={savingAgentWorklogPolicy}
                              disabled={!projectId.trim()}
                              onClick={() => void saveAgentWorklogPolicy()}
                            >
                              Save policy
                            </Button>
                            <Button
                              size="xs"
                              color="teal"
                              loading={runningAgentWorklogSync}
                              disabled={!projectId.trim()}
                              onClick={() => void runAgentWorklogSyncNow()}
                            >
                              Sync worklogs now
                            </Button>
                          </Group>
                        </Stack>
                      </Paper>

                      <Paper withBorder p="sm" radius="md" data-testid="operations-orgchart-panel">
                        <Stack gap="xs">
                          <Group justify="space-between" align="center" wrap="wrap">
                            <Group gap={6} wrap="wrap">
                              <Text size="sm" fw={700}>
                                AI Agent Orgchart
                              </Text>
                              <Badge size="xs" variant="light" color="gray">
                                nodes {agentOrgchart?.summary?.nodes_total ?? 0}
                              </Badge>
                              <Badge size="xs" variant="light" color="gray">
                                teams {agentOrgchart?.summary?.teams_total ?? 0}
                              </Badge>
                              <Badge size="xs" variant="light" color="gray">
                                handoffs {agentOrgchart?.summary?.edges_total ?? 0}
                              </Badge>
                            </Group>
                            <Group gap={6} wrap="wrap">
                              <Checkbox
                                size="xs"
                                label="Include handoffs"
                                checked={agentOrgchartIncludeHandoffs}
                                onChange={(event) => setAgentOrgchartIncludeHandoffs(event.currentTarget.checked)}
                              />
                              <Button
                                size="compact-xs"
                                variant="light"
                                loading={loadingAgentOrgchart}
                                disabled={!projectId.trim()}
                                onClick={() => void loadAgentOrgchart()}
                              >
                                Refresh
                              </Button>
                            </Group>
                          </Group>
                          {!projectId.trim() ? (
                            <Text size="xs" c="dimmed">
                              Set workspace to load agent orgchart.
                            </Text>
                          ) : loadingAgentOrgchart && !agentOrgchart ? (
                            <Group gap={6}>
                              <Loader size="xs" />
                              <Text size="xs" c="dimmed">
                                loading orgchart…
                              </Text>
                            </Group>
                          ) : !agentOrgchart || (agentOrgchart.nodes ?? []).length === 0 ? (
                            <Text size="xs" c="dimmed">
                              No registered agents yet. SDK registration creates orgchart profiles automatically.
                            </Text>
                          ) : (
                            <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="sm">
                              <Paper withBorder p="xs" radius="md">
                                <Stack gap={6}>
                                  <Text size="xs" fw={700}>
                                    Teams
                                  </Text>
                                  <ScrollArea h={220} type="auto">
                                    <Stack gap={6}>
                                      {agentOrgchartTeams.map((team) => (
                                        <Paper key={`orgchart-team-${team.team}`} withBorder p="xs" radius="md">
                                          <Stack gap={4}>
                                            <Group justify="space-between" align="center" wrap="wrap">
                                              <Text size="xs" fw={700}>
                                                {team.team}
                                              </Text>
                                              <Badge size="xs" variant="light" color="indigo">
                                                {team.nodes.length}
                                              </Badge>
                                            </Group>
                                            <Group gap={4} wrap="wrap">
                                              {team.nodes.slice(0, 8).map((node) => (
                                                <Button
                                                  key={`orgchart-node-open-${node.agent_id}`}
                                                  size="compact-xs"
                                                  variant="light"
                                                  color="gray"
                                                  onClick={() => {
                                                    const slug = String(node.profile_slug || "").trim();
                                                    if (!slug) return;
                                                    setSelectedSpaceKey(pageGroupKey(slug));
                                                    setSelectedPageSlug(slug);
                                                    setCoreWorkspaceRoute("wiki");
                                                    setCoreWorkspaceTab("wiki");
                                                  }}
                                                >
                                                  {node.display_name} · {node.role}
                                                </Button>
                                              ))}
                                              {team.nodes.length > 8 ? (
                                                <Badge size="xs" variant="light" color="gray">
                                                  +{team.nodes.length - 8} more
                                                </Badge>
                                              ) : null}
                                            </Group>
                                          </Stack>
                                        </Paper>
                                      ))}
                                    </Stack>
                                  </ScrollArea>
                                </Stack>
                              </Paper>
                              <Paper withBorder p="xs" radius="md">
                                <Stack gap={6}>
                                  <Text size="xs" fw={700}>
                                    Recent handoffs
                                  </Text>
                                  {agentOrgchartEdgePreview.length === 0 ? (
                                    <Text size="xs" c="dimmed">
                                      No handoff edges captured yet.
                                    </Text>
                                  ) : (
                                    <ScrollArea h={220} type="auto">
                                      <Stack gap={4}>
                                        {agentOrgchartEdgePreview.map((edge, index) => {
                                          const from = agentOrgchartNodeById.get(edge.from_agent);
                                          const to = agentOrgchartNodeById.get(edge.to_agent);
                                          return (
                                            <Paper key={`orgchart-edge-${edge.from_agent}-${edge.to_agent}-${index}`} withBorder p={6} radius="sm">
                                              <Stack gap={2}>
                                                <Text size="xs" fw={700}>
                                                  {from?.display_name || edge.from_agent} → {to?.display_name || edge.to_agent}
                                                </Text>
                                                <Text size="xs" c="dimmed">
                                                  input: {edge.input_contract || "n/a"} • output: {edge.output_contract || "n/a"}
                                                </Text>
                                                {edge.sla ? (
                                                  <Badge size="xs" variant="light" color="orange">
                                                    SLA {edge.sla}
                                                  </Badge>
                                                ) : null}
                                              </Stack>
                                            </Paper>
                                          );
                                        })}
                                      </Stack>
                                    </ScrollArea>
                                  )}
                                </Stack>
                              </Paper>
                            </SimpleGrid>
                          )}
                        </Stack>
                      </Paper>

                      <Paper withBorder p="sm" radius="md">
                        <Stack gap="xs">
                          <Text size="sm" fw={700}>
                            Migration Mode
                          </Text>
                          <Text size="xs" c="dimmed">
                            Use this route for trusted-source onboarding and batch approvals.
                          </Text>
                          <Group gap="xs" wrap="wrap">
                            <Button
                              size="xs"
                              variant="light"
                              color="teal"
                              onClick={openLegacySetupWizard}
                            >
                              Setup wizard
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="gray"
                              loading={adoptionPipelineLoading}
                              onClick={() => void loadAdoptionPipelineVisibility()}
                            >
                              Refresh pipeline
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                document.getElementById("operations-pipeline-panel")?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                              }}
                            >
                              View pipeline
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="indigo"
                              loading={adoptionEvidenceBundlesLoading}
                              onClick={() => void loadAdoptionEvidenceBundles()}
                            >
                              Refresh bundles
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                document.getElementById("operations-bundles-panel")?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                              }}
                            >
                              View bundles
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="blue"
                              loading={loadingAdoptionKpi}
                              onClick={() => void loadAdoptionKpi()}
                            >
                              Refresh quality
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                document.getElementById("operations-wiki-quality-panel")?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                              }}
                            >
                              View quality
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="orange"
                              loading={adoptionRejectionsLoading}
                              onClick={() => void loadAdoptionRejections()}
                            >
                              Refresh rejections
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                document.getElementById("operations-rejections-panel")?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                              }}
                            >
                              View rejections
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="grape"
                              loading={loadingEnterpriseReadiness}
                              onClick={() => void loadEnterpriseReadiness()}
                            >
                              Refresh enterprise
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                document.getElementById("operations-enterprise-panel")?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                              }}
                            >
                              View enterprise
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="violet"
                              loading={bootstrapProfileLoading}
                              onClick={() => void applyAdoptionBootstrapProfile(true)}
                            >
                              Preview import profile
                            </Button>
                            <Button
                              size="xs"
                              color="violet"
                              loading={bootstrapProfileLoading}
                              onClick={() => void applyAdoptionBootstrapProfile(false)}
                            >
                              Apply import profile
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="cyan"
                              loading={runningSyncPreset}
                              onClick={() => void executeAdoptionSyncPreset(true)}
                            >
                              Preview sync preset
                            </Button>
                            <Button
                              size="xs"
                              color="cyan"
                              loading={runningSyncPreset}
                              onClick={() => void executeAdoptionSyncPreset(false)}
                            >
                              Run sync preset
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="blue"
                              loading={runningAgentWikiBootstrap}
                              onClick={() => void runAgentWikiBootstrap(true)}
                            >
                              Preview Bootstrap Wiki
                            </Button>
                            <Button
                              size="xs"
                              color="blue"
                              loading={runningAgentWikiBootstrap}
                              onClick={() => void runAgentWikiBootstrap(false)}
                            >
                              Bootstrap Wiki
                            </Button>
                            <Button
                              size="xs"
                              variant="light"
                              color="indigo"
                              loading={bootstrapLoading || bootstrapProfileLoading}
                              onClick={() => void runRecommendedBootstrapPreview()}
                            >
                              Preview recommended
                            </Button>
                            <Button
                              size="xs"
                              color="teal"
                              loading={bootstrapLoading || bootstrapProfileLoading}
                              onClick={() => void runRecommendedBootstrapApply()}
                            >
                              Apply recommended
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => {
                                applyRecommendedBootstrapPreset(recommendedBootstrapPreset);
                                setShowBootstrapTools((value) => !value);
                              }}
                            >
                              {showBootstrapTools ? "Hide bootstrap settings" : "Open bootstrap settings"}
                            </Button>
                          </Group>
                          {agentWikiBootstrapResult ? (
                            <Text size="xs" c="dimmed">
                              Bootstrap Wiki {agentWikiBootstrapResult.dry_run ? "preview" : "run"}:{" "}
                              {Number(agentWikiBootstrapResult.plan?.pages_total || 0)} planned page(s), created{" "}
                              {Number(agentWikiBootstrapResult.summary?.created || 0)}. DoD: agent{" "}
                              {agentWikiBootstrapResult.definition_of_done?.agent_page ? "yes" : "no"}, sources{" "}
                              {agentWikiBootstrapResult.definition_of_done?.data_sources_page ? "yes" : "no"}, process{" "}
                              {agentWikiBootstrapResult.definition_of_done?.operational_process_page ? "yes" : "no"}.
                            </Text>
                          ) : null}
                          {adoptionPipeline ? (
                            <Paper withBorder p="xs" radius="md" id="operations-pipeline-panel">
                              <Stack gap={6}>
                                <Group justify="space-between" align="center" wrap="wrap">
                                  <Text size="xs" fw={700}>
                                    Pipeline visibility ({adoptionPipeline.window_days}d)
                                  </Text>
                                  {adoptionPipeline.bottleneck ? (
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={
                                        adoptionPipeline.bottleneck.status === "critical"
                                          ? "red"
                                          : adoptionPipeline.bottleneck.status === "watch"
                                            ? "orange"
                                            : "teal"
                                      }
                                    >
                                      Bottleneck: {adoptionPipeline.bottleneck.from_stage} → {adoptionPipeline.bottleneck.to_stage}
                                    </Badge>
                                  ) : (
                                    <Badge size="xs" variant="light" color="teal">
                                      No major bottleneck
                                    </Badge>
                                  )}
                                </Group>
                                <SimpleGrid cols={{ base: 2, sm: 5 }} spacing={6}>
                                  <Badge size="xs" variant="light" color="gray">
                                    accepted {adoptionPipeline.pipeline.accepted}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    events {adoptionPipeline.pipeline.events}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    claims {adoptionPipeline.pipeline.claims}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    drafts {adoptionPipeline.pipeline.drafts}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    pages {adoptionPipeline.pipeline.pages}
                                  </Badge>
                                </SimpleGrid>
                                <Text size="xs" c="dimmed">
                                  Queue: {adoptionPipeline.draft_queue?.open_total ?? 0} open ({adoptionPipeline.draft_queue?.pending_review ?? 0} pending,{" "}
                                  {adoptionPipeline.draft_queue?.blocked_conflict ?? 0} conflicts). Rejected event-like:{" "}
                                  {adoptionPipeline.rejected_event_like ?? 0}.
                                </Text>
                                {adoptionPipeline.bottleneck?.hint ? (
                                  <Text size="xs" c="dimmed">
                                    {adoptionPipeline.bottleneck.hint}
                                  </Text>
                                ) : null}
                              </Stack>
                            </Paper>
                          ) : (
                            <Text size="xs" c="dimmed">
                              Pipeline visibility is unavailable for current project yet.
                            </Text>
                          )}
                          <Paper withBorder p="xs" radius="md" id="operations-bundles-panel">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Knowledge bundles
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="indigo"
                                  loading={adoptionEvidenceBundlesLoading}
                                  onClick={() => void loadAdoptionEvidenceBundles()}
                                >
                                  Refresh
                                </Button>
                              </Group>
                              {adoptionEvidenceBundles && (adoptionEvidenceBundles.bundles || []).length > 0 ? (
                                <>
                                  <Group gap={6} wrap="wrap">
                                    <Badge size="xs" variant="light" color="teal">
                                      ready {adoptionBundleSummary.ready}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="blue">
                                      candidate {adoptionBundleSummary.candidate}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      observed {adoptionBundleSummary.observed}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="red">
                                      suppressed {adoptionBundleSummary.suppressed}
                                    </Badge>
                                  </Group>
                                  <Text size="xs" c="dimmed">
                                    Durable knowledge clusters that can ground wiki pages before raw events become drafts.
                                    Top suggested pages:{" "}
                                    {adoptionBundleSummary.topPageTypes.length > 0
                                      ? adoptionBundleSummary.topPageTypes.map((item) => `${item.key} (${item.count})`).join(", ")
                                      : "n/a"}
                                    .
                                  </Text>
                                  <Stack gap={6}>
                                    {(adoptionEvidenceBundles.bundles || []).slice(0, 8).map((bundle) => {
                                      const preview = Array.isArray(bundle.sample_claims)
                                        ? bundle.sample_claims
                                            .map((item) => String(item?.claim_text || "").trim())
                                            .find((item) => item.length > 0) || ""
                                        : "";
                                      return (
                                        <Paper key={`bundle-preview-${bundle.id}`} withBorder p="xs" radius="md">
                                          <Stack gap={4}>
                                            <Group justify="space-between" align="center" wrap="wrap">
                                              <Group gap={6} wrap="wrap">
                                                <Text size="xs" fw={700}>
                                                  {bundle.bundle_key}
                                                </Text>
                                                <Badge
                                                  size="xs"
                                                  variant="light"
                                                  color={
                                                    bundle.bundle_status === "ready"
                                                      ? "teal"
                                                      : bundle.bundle_status === "candidate"
                                                        ? "blue"
                                                        : bundle.bundle_status === "suppressed"
                                                          ? "red"
                                                          : "gray"
                                                  }
                                                >
                                                  {bundle.bundle_status}
                                                </Badge>
                                                <Badge size="xs" variant="light" color="gray">
                                                  {bundle.bundle_type}
                                                </Badge>
                                              </Group>
                                              <Group gap={6} wrap="wrap">
                                                <Badge size="xs" variant="light" color="gray">
                                                  support {bundle.support_count}
                                                </Badge>
                                                <Badge size="xs" variant="light" color="gray">
                                                  page {bundle.suggested_page_type}
                                                </Badge>
                                              </Group>
                                            </Group>
                                            <Text size="xs" c="dimmed">
                                              entity {bundle.entity_key || "n/a"} • evidence {bundle.evidence_count} • linked claims{" "}
                                              {bundle.linked_claims ?? 0} • quality {Math.round(Number(bundle.quality_score || 0) * 100)}%
                                            </Text>
                                            {preview ? (
                                              <Text size="xs">
                                                {preview.length > 220 ? `${preview.slice(0, 220)}…` : preview}
                                              </Text>
                                            ) : (
                                              <Text size="xs" c="dimmed">
                                                No preview claim linked yet; bundle metadata exists but sample evidence is still thin.
                                              </Text>
                                            )}
                                          </Stack>
                                        </Paper>
                                      );
                                    })}
                                  </Stack>
                                </>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  No durable bundles surfaced yet. If events exist but bundles stay empty, the system is still seeing mostly
                                  operational flow instead of reusable knowledge.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                          <Paper withBorder p="xs" radius="md" id="operations-wiki-quality-panel">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Wiki quality report
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="blue"
                                  loading={loadingAdoptionKpi}
                                  onClick={() => void loadAdoptionKpi()}
                                >
                                  Refresh quality
                                </Button>
                              </Group>
                              {adoptionKpi?.wiki_quality ? (
                                <>
                                  <Group gap={6} wrap="wrap">
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={adoptionKpi.wiki_quality.quality?.pass ? "teal" : "orange"}
                                    >
                                      {adoptionKpi.wiki_quality.quality?.pass ? "quality pass" : "needs attention"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      core published {Number(adoptionKpi.wiki_quality.core_pages?.published_total || 0)}
                                      /
                                      {Array.isArray(adoptionKpi.wiki_quality.core_pages?.required_leaves)
                                        ? adoptionKpi.wiki_quality.core_pages?.required_leaves?.length
                                        : "—"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      placeholders{" "}
                                      {Number.isFinite(Number(adoptionKpi.wiki_quality.content_quality?.placeholder_ratio_core))
                                        ? `${Math.round(Number(adoptionKpi.wiki_quality.content_quality?.placeholder_ratio_core) * 100)}%`
                                        : "—"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      daily-summary drafts{" "}
                                      {Number.isFinite(Number(adoptionKpi.wiki_quality.draft_noise?.daily_summary_open_draft_ratio))
                                        ? `${Math.round(Number(adoptionKpi.wiki_quality.draft_noise?.daily_summary_open_draft_ratio) * 100)}%`
                                        : "—"}
                                    </Badge>
                                  </Group>
                                  <Text size="xs" c="dimmed">
                                    Missing core pages:{" "}
                                    {Array.isArray(adoptionKpi.wiki_quality.core_pages?.missing_required_leaves) &&
                                    adoptionKpi.wiki_quality.core_pages?.missing_required_leaves?.length > 0
                                      ? adoptionKpi.wiki_quality.core_pages?.missing_required_leaves?.join(", ")
                                      : "none"}
                                    .
                                  </Text>
                                  {Array.isArray(adoptionKpi.wiki_quality.warnings) && adoptionKpi.wiki_quality.warnings.length > 0 ? (
                                    <Text size="xs" c="dimmed">
                                      Top warning: {adoptionKpi.wiki_quality.warnings[0]?.code || "unknown"}.
                                    </Text>
                                  ) : (
                                    <Text size="xs" c="dimmed">
                                      Quality warnings are clear in the current window.
                                    </Text>
                                  )}
                                </>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  Quality report is unavailable yet. Run bootstrap/apply and refresh KPI.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                          <Paper withBorder p="xs" radius="md" id="operations-rejections-panel">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Rejection diagnostics (14d)
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="orange"
                                  loading={adoptionRejectionsLoading}
                                  onClick={() => void loadAdoptionRejections()}
                                >
                                  Refresh
                                </Button>
                              </Group>
                              {adoptionRejections ? (
                                <>
                                  <Text size="xs" c="dimmed">
                                    Rejected total: {Number(adoptionRejections.summary?.rejected_total || 0)}. Sampled examples:{" "}
                                    {Number(adoptionRejections.summary?.sampled_examples || 0)}.
                                  </Text>
                                  {Array.isArray(adoptionRejections.top_reject_reasons) &&
                                  adoptionRejections.top_reject_reasons.length > 0 ? (
                                    <Group gap={6} wrap="wrap">
                                      {adoptionRejections.top_reject_reasons.slice(0, 6).map((item) => (
                                        <Badge key={`rej-reason-${item.key}`} size="xs" variant="light" color="orange">
                                          {item.key} · {item.count}
                                        </Badge>
                                      ))}
                                    </Group>
                                  ) : (
                                    <Text size="xs" c="dimmed">
                                      No dominant rejection tags in current window.
                                    </Text>
                                  )}
                                  {Array.isArray(adoptionRejections.suggested_policy_knobs) &&
                                  adoptionRejections.suggested_policy_knobs.length > 0 ? (
                                    <Text size="xs" c="dimmed">
                                      Suggested next step: {adoptionRejections.suggested_policy_knobs[0]?.knob} —{" "}
                                      {adoptionRejections.suggested_policy_knobs[0]?.hint}
                                    </Text>
                                  ) : null}
                                </>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  Rejection diagnostics are unavailable for current project yet.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                          <Paper withBorder p="xs" radius="md" id="operations-enterprise-panel">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Enterprise readiness
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="grape"
                                  loading={loadingEnterpriseReadiness}
                                  onClick={() => void loadEnterpriseReadiness()}
                                >
                                  Refresh
                                </Button>
                              </Group>
                              {enterpriseReadiness ? (
                                <>
                                  <Group gap={6} wrap="wrap">
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={
                                        enterpriseReadiness.status === "critical"
                                          ? "red"
                                          : enterpriseReadiness.status === "warning"
                                            ? "orange"
                                            : "teal"
                                      }
                                    >
                                      {enterpriseReadiness.status}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      auth {enterpriseReadiness.summary?.auth_mode || "open"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      rbac {enterpriseReadiness.summary?.rbac_mode || "open"}
                                    </Badge>
                                    <Badge size="xs" variant="light" color="gray">
                                      tenancy {enterpriseReadiness.summary?.tenancy_mode || "open"}
                                    </Badge>
                                  </Group>
                                  <Text size="xs" c="dimmed">
                                    Tenants: {Number(enterpriseReadiness.counts?.tenants || 0)} • Mapped projects:{" "}
                                    {Number(enterpriseReadiness.counts?.tenant_projects || 0)} • Active sessions:{" "}
                                    {Number(enterpriseReadiness.counts?.active_auth_sessions || 0)}.
                                  </Text>
                                  {Array.isArray(enterpriseReadiness.warnings) && enterpriseReadiness.warnings.length > 0 ? (
                                    <Text size="xs" c="dimmed">
                                      Top warning: {enterpriseReadiness.warnings[0]?.code || "unknown"} —{" "}
                                      {enterpriseReadiness.warnings[0]?.message || "check readiness details"}.
                                    </Text>
                                  ) : (
                                    <Text size="xs" c="dimmed">
                                      Enterprise baseline checks look healthy.
                                    </Text>
                                  )}
                                </>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  Enterprise readiness snapshot is unavailable for current project yet.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                          <Paper withBorder p="xs" radius="md">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Adoption KPI
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  loading={loadingAdoptionKpi}
                                  onClick={() => void loadAdoptionKpi()}
                                >
                                  Refresh KPI
                                </Button>
                              </Group>
                              {adoptionKpi?.kpi ? (
                                <SimpleGrid cols={{ base: 2, sm: 4 }} spacing={6}>
                                  <Badge size="xs" variant="light" color="gray">
                                    first draft{" "}
                                    {adoptionKpi.kpi.time_to_first_draft_sec == null
                                      ? "—"
                                      : `${Math.round(Number(adoptionKpi.kpi.time_to_first_draft_sec) / 60)}m`}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    first publish{" "}
                                    {adoptionKpi.kpi.time_to_first_publish_sec == null
                                      ? "—"
                                      : `${Math.round(Number(adoptionKpi.kpi.time_to_first_publish_sec) / 60)}m`}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    draft noise{" "}
                                    {Number.isFinite(Number(adoptionKpi.kpi.draft_noise_ratio))
                                      ? `${Math.round(Number(adoptionKpi.kpi.draft_noise_ratio) * 100)}%`
                                      : "—"}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    revert rate{" "}
                                    {Number.isFinite(Number(adoptionKpi.kpi.publish_revert_rate))
                                      ? `${Math.round(Number(adoptionKpi.kpi.publish_revert_rate) * 100)}%`
                                      : "—"}
                                  </Badge>
                                </SimpleGrid>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  KPI are not available yet for this project.
                                </Text>
                              )}
                              {Array.isArray(adoptionKpi?.alerts) && adoptionKpi?.alerts.length > 0 ? (
                                <Text size="xs" c="dimmed">
                                  {adoptionKpi.alerts.slice(0, 2).map((item) => item.hint || item.metric).join(" ")}
                                </Text>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  KPI health is stable for the last {adoptionKpi?.window_days || 30} days.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                          <Paper withBorder p="xs" radius="md">
                            <Stack gap={6}>
                              <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm" fw={700}>
                                  Policy quick loop
                                </Text>
                                <Button
                                  size="xs"
                                  variant="light"
                                  loading={loadingPolicyQuickLoop}
                                  onClick={() => void loadPolicyQuickLoop()}
                                >
                                  Refresh recommendation
                                </Button>
                              </Group>
                              <Text size="xs" c="dimmed">
                                {policyQuickLoop?.recommended?.title || "No recommendation yet"}.
                              </Text>
                              {policyQuickLoop?.recommended?.changed_routing_keys?.length ? (
                                <Text size="xs" c="dimmed">
                                  Will tune: {policyQuickLoop.recommended.changed_routing_keys.slice(0, 6).join(", ")}.
                                </Text>
                              ) : null}
                              <Group gap="xs" wrap="wrap">
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="violet"
                                  loading={applyingPolicyQuickLoop}
                                  onClick={() => void applyPolicyQuickLoopPreset(true)}
                                >
                                  Preview quick preset
                                </Button>
                                <Button
                                  size="xs"
                                  color="violet"
                                  loading={applyingPolicyQuickLoop}
                                  onClick={() => void applyPolicyQuickLoopPreset(false)}
                                >
                                  Apply quick preset
                                </Button>
                              </Group>
                            </Stack>
                          </Paper>
                          {bootstrapProfileResult ? (
                            <Text size="xs" c="dimmed">
                              Profile `{bootstrapProfileResult.profile}` {bootstrapProfileResult.status}. Changed gatekeeper keys:{" "}
                              {[
                                ...(bootstrapProfileResult.gatekeeper?.diff?.changed_keys?.top_level ?? []),
                                ...(bootstrapProfileResult.gatekeeper?.diff?.changed_keys?.routing_policy ?? []),
                              ]
                                .slice(0, 6)
                                .join(", ") || "none"}
                              .
                            </Text>
                          ) : null}
                          <Paper withBorder p="xs" radius="md">
                            <Stack gap={6}>
                              <Text size="sm" fw={700}>
                                Bootstrap Migration
                              </Text>
                              <Text size="xs" c="dimmed">
                                Preview candidates first, then approve trusted batches.
                              </Text>
                              {showBootstrapTools ? (
                                <>
                                  <TextInput
                                    label="Trusted sources (csv)"
                                    value={bootstrapTrustedSources}
                                    onChange={(event) => {
                                      setBootstrapTrustedSources(event.currentTarget.value);
                                      setBootstrapTrustedSourcesTouched(true);
                                    }}
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
                                </>
                              ) : (
                                <Text size="xs" c="dimmed">
                                  Open bootstrap settings to tune confidence and batch size.
                                </Text>
                              )}
                            </Stack>
                          </Paper>
                        </Stack>
                      </Paper>
                    </Stack>
                  ) : null
                }
                draftListContent={
                  visibleDrafts.length === 0 ? (
                    <Paper withBorder p="md" radius="md">
                      <Text size="sm" c="dimmed">
                        No drafts in current scope.
                      </Text>
                    </Paper>
                  ) : (
                    <Stack gap="sm">
                      {draftQueueSummary ? (
                        <Paper withBorder p="sm" radius="md">
                          <Stack gap={8}>
                            <Group justify="space-between" align="center" wrap="wrap">
                              <Text size="sm" fw={700}>
                                Queue summary
                              </Text>
                              <Badge size="xs" variant="light" color="cyan">
                                {draftQueueSummary.drafts_total} drafts
                              </Badge>
                            </Group>
                            <Group gap={6} wrap="wrap">
                              {Object.entries(draftQueueSummary.recommendations || {}).map(([key, count]) => (
                                <Badge key={`rec-${key}`} size="xs" variant="light" color={recommendationColor(key)}>
                                  {humanizeRecommendation(key)} {count}
                                </Badge>
                              ))}
                            </Group>
                            <Group gap={6} wrap="wrap">
                              {(
                                [
                                  { key: "all", label: "all" },
                                  { key: "approve_first", label: "approve first" },
                                  { key: "review_with_context", label: "review with context" },
                                  { key: "needs_human_caution", label: "human caution" },
                                ] as Array<{ key: DraftRecommendationFilter; label: string }>
                              ).map((item) => (
                                <Button
                                  key={`draft-rec-filter-${item.key}`}
                                  size="compact-xs"
                                  variant={draftRecommendationFilter === item.key ? "filled" : "light"}
                                  color={draftRecommendationFilter === item.key ? recommendationColor(item.key) : "gray"}
                                  onClick={() => setDraftRecommendationFilter(item.key)}
                                >
                                  {item.label}
                                </Button>
                              ))}
                            </Group>
                            <Group gap={6} wrap="wrap">
                              {Object.entries(draftQueueSummary.bundle_statuses || {}).map(([key, count]) => (
                                <Badge key={`bundle-status-${key}`} size="xs" variant="light" color={key === "ready" ? "teal" : key === "candidate" ? "blue" : "gray"}>
                                  {key.replace(/_/g, " ")} {count}
                                </Badge>
                              ))}
                            </Group>
                            <Text size="xs" c="dimmed">
                              Ready bundle support total: {draftQueueSummary.ready_bundle_support_total}. Queue is ranked by durable bundle maturity before raw draft recency.
                            </Text>
                            {safeBulkApproveSkippedCount > 0 ? (
                              <Text size="xs" c="dimmed">
                                Safe bulk approve would skip {safeBulkApproveSkippedCount} weaker draft{safeBulkApproveSkippedCount === 1 ? "" : "s"} in the current scope.
                              </Text>
                            ) : null}
                          </Stack>
                        </Paper>
                      ) : null}
                      <ScrollArea h={680} type="auto">
                        <Stack gap="xs">
                        {visibleDrafts.map((draft) => (
                          <Paper
                            key={draft.id}
                            withBorder
                            p="sm"
                            radius="md"
                            data-testid={`core-draft-list-item-${draft.id}`}
                            style={{ cursor: "pointer" }}
                            onClick={() => setSelectedDraftId(draft.id)}
                          >
                            <Group justify="space-between" align="flex-start" wrap="nowrap">
                              <Stack gap={4} style={{ flex: 1 }}>
                                <Text fw={700} size="sm">
                                  {draft.page.title || draft.page.slug || draft.section_key || "Untitled draft"}
                                </Text>
                                <Group gap={6} wrap="wrap">
                                  <Badge size="xs" color={statusColor(draft.status)} variant="light">
                                    {draft.status}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="blue">
                                    conf {draft.confidence.toFixed(2)}
                                  </Badge>
                                  <Badge size="xs" variant="light" color="gray">
                                    {fmtDate(draft.created_at)}
                                  </Badge>
                                  {draft.bundle_priority?.recommendation ? (
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={recommendationColor(draft.bundle_priority.recommendation)}
                                    >
                                      {humanizeRecommendation(draft.bundle_priority.recommendation)}
                                    </Badge>
                                  ) : null}
                                  {draft.bundle?.bundle_status ? (
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={draft.bundle.bundle_status === "ready" ? "teal" : draft.bundle.bundle_status === "candidate" ? "blue" : "gray"}
                                    >
                                      bundle {draft.bundle.bundle_status}
                                    </Badge>
                                  ) : null}
                                </Group>
                                <Text size="xs" c="dimmed" lineClamp={2}>
                                  {draft.rationale}
                                </Text>
                                <Text size="xs" c="dimmed" lineClamp={1}>
                                  {draft.bundle_priority?.reason
                                    ? `why now: ${draft.bundle_priority.reason}`
                                    : draft.claim?.category || draft.page.page_type || "knowledge draft"}
                                </Text>
                              </Stack>
                              <Button
                                size="compact-sm"
                                variant="light"
                                onClick={() => {
                                  if (!draft.page.slug) return;
                                  setSelectedSpaceKey(pageGroupKey(draft.page.slug));
                                  setSelectedPageSlug(draft.page.slug);
                                  setCoreWorkspaceTab("wiki");
                                }}
                              >
                                Open page
                              </Button>
                            </Group>
                          </Paper>
                        ))}
                        </Stack>
                      </ScrollArea>
                    </Stack>
                  )
                }
                detailContent={
                  <Paper withBorder p="md" radius="md" data-testid="core-draft-detail-panel">
                    <Stack gap="sm">
                      <Group justify="space-between" align="center" wrap="wrap">
                        <Title order={4}>Draft Detail</Title>
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
                      {!selectedDraftId ? (
                        <Text size="sm" c="dimmed">
                          Select draft in inbox to inspect semantic diff and moderate it.
                        </Text>
                      ) : loadingDetail ? (
                        <Group gap={8}>
                          <Loader size="sm" />
                          <Text size="sm" c="dimmed">
                            Loading draft detail…
                          </Text>
                        </Group>
                      ) : draftDetail ? (
                        <Stack gap="xs">
                          <Group gap={6} wrap="wrap">
                            <Badge size="xs" variant="light" color="blue">
                              conf {draftDetail.draft.confidence.toFixed(2)}
                            </Badge>
                            <Badge size="xs" variant="light" color="gray">
                              {fmtDate(draftDetail.draft.created_at)}
                            </Badge>
                            {draftDetail.recommended_action ? (
                              <Badge
                                size="xs"
                                variant="light"
                                color={recommendationColor(draftDetail.recommended_action)}
                              >
                                {humanizeRecommendation(draftDetail.recommended_action)}
                              </Badge>
                            ) : null}
                          </Group>
                          <Text size="sm" fw={700}>
                            {draftDetail.draft.page.title || draftDetail.draft.page.slug || "Untitled draft"}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {draftDetail.draft.rationale}
                          </Text>
                          {draftDetail.bundle_priority || draftDetail.bundle ? (
                            <Paper withBorder p="sm" radius="md">
                              <Stack gap={6}>
                                <Group justify="space-between" align="center" wrap="wrap">
                                  <Text size="sm" fw={700}>
                                    Bundle Recommendation
                                  </Text>
                                  {draftDetail.bundle?.bundle_status ? (
                                    <Badge
                                      size="xs"
                                      variant="light"
                                      color={
                                        draftDetail.bundle.bundle_status === "ready"
                                          ? "teal"
                                          : draftDetail.bundle.bundle_status === "candidate"
                                            ? "blue"
                                            : "gray"
                                      }
                                    >
                                      bundle {draftDetail.bundle.bundle_status}
                                    </Badge>
                                  ) : null}
                                </Group>
                                <Group gap={6} wrap="wrap">
                                  {draftDetail.bundle_priority ? (
                                    <>
                                      <Badge
                                        size="xs"
                                        variant="light"
                                        color={recommendationColor(draftDetail.bundle_priority.recommendation)}
                                      >
                                        {humanizeRecommendation(draftDetail.bundle_priority.recommendation)}
                                      </Badge>
                                      <Badge size="xs" variant="light" color="grape">
                                        score {draftDetail.bundle_priority.score.toFixed(2)}
                                      </Badge>
                                    </>
                                  ) : null}
                                  {draftDetail.bundle?.support_count != null ? (
                                    <Badge size="xs" variant="light" color="cyan">
                                      support {draftDetail.bundle.support_count}
                                    </Badge>
                                  ) : null}
                                  {draftDetail.bundle?.quality_score != null ? (
                                    <Badge size="xs" variant="light" color="indigo">
                                      quality {draftDetail.bundle.quality_score.toFixed(2)}
                                    </Badge>
                                  ) : null}
                                </Group>
                                {draftDetail.bundle_priority?.reason ? (
                                  <Text size="xs" c="dimmed">
                                    {draftDetail.bundle_priority.reason}
                                  </Text>
                                ) : null}
                                {draftDetail.bundle?.sample_claims?.length ? (
                                  <Text size="xs" c="dimmed" lineClamp={2}>
                                    {draftDetail.bundle.sample_claims
                                      .map((item) => item.claim_text)
                                      .filter(Boolean)
                                      .slice(0, 2)
                                      .join(" • ")}
                                  </Text>
                                ) : null}
                              </Stack>
                            </Paper>
                          ) : null}
                          {draftDetail.gatekeeper ? (
                            <Paper withBorder p="sm" radius="md">
                              <Stack gap={6}>
                                <Group justify="space-between" align="center" wrap="wrap">
                                  <Text size="sm" fw={700}>
                                    Gatekeeper Signal
                                  </Text>
                                  <Badge size="xs" variant="light" color="indigo">
                                    {draftDetail.gatekeeper.tier || "unknown_tier"}
                                  </Badge>
                                </Group>
                                <Group gap={6} wrap="wrap">
                                  <Badge size="xs" variant="light" color="blue">
                                    score{" "}
                                    {draftDetail.gatekeeper.score == null ? "—" : Number(draftDetail.gatekeeper.score).toFixed(2)}
                                  </Badge>
                                  <Badge
                                    size="xs"
                                    variant="light"
                                    color={draftDetail.gatekeeper.llm.applied ? "teal" : "gray"}
                                  >
                                    llm {draftDetail.gatekeeper.llm.applied ? "applied" : "not_applied"}
                                  </Badge>
                                  {draftDetail.gatekeeper.llm.reason_code ? (
                                    <Badge size="xs" variant="light" color="violet">
                                      reason {draftDetail.gatekeeper.llm.reason_code}
                                    </Badge>
                                  ) : null}
                                </Group>
                                <Text size="xs" c="dimmed">
                                  {draftDetail.gatekeeper.rationale || "No gatekeeper rationale recorded."}
                                </Text>
                              </Stack>
                            </Paper>
                          ) : null}
                        </Stack>
                      ) : (
                        <Text size="sm" c="dimmed">
                          Draft detail is unavailable.
                        </Text>
                      )}
                    </Stack>
                  </Paper>
                }
              />
            ) : (
              <CoreWikiMain
                isOperationsRoute={isOperationsRoute}
                wikiPageBreadcrumb={wikiPageBreadcrumb}
                selectedPageSlug={selectedPageSlug}
                pageEditMode={pageEditMode}
                showCreatePanel={showCoreCreatePanel}
                onSelectBreadcrumb={(slug) => {
                  if (!slug) {
                    setSelectedPageSlug(null);
                    return;
                  }
                  setSelectedSpaceKey(pageGroupKey(slug));
                  setSelectedPageSlug(slug);
                }}
                onToggleCreatePanel={() => setShowCoreCreatePanel((prev) => !prev)}
                onRefreshPage={() => {
                  if (!selectedPageSlug) return;
                  void loadPageDetail(selectedPageSlug);
                  void loadPageHistory(selectedPageSlug);
                  void loadPageReviewAssignments(selectedPageSlug);
                  void loadSpacePolicy(selectedPageSlug);
                  void loadSpacePolicyAudit(selectedPageSlug);
                  void loadSpacePolicyAdoptionSummary(selectedPageSlug);
                }}
                onEnterEdit={() => {
                  setPageMoveMode(false);
                  setPageEditMode(true);
                }}
                onOpenHistory={() => {
                  openHistoryDrawerForVersion(null);
                }}
                createPanel={
                  <Paper withBorder p="sm" radius="md" className="confluence-create-panel">
                    <Group gap={6} mb="sm" wrap="wrap">
                      {PAGE_TEMPLATES.map((template) => (
                        <Button
                          key={`core-create-template-${template.key}`}
                          size="compact-xs"
                          variant={selectedCreateTemplateKey === template.key ? "filled" : "light"}
                          color={selectedCreateTemplateKey === template.key ? "blue" : "gray"}
                          onClick={() => applyCreateTemplate(template.key)}
                        >
                          {template.title}
                        </Button>
                      ))}
                    </Group>
                    <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm">
                      <TextInput
                        size="xs"
                        label="Space"
                        value={guidedPageForm.spaceKey}
                        onChange={(event) => setGuidedPageForm((prev) => ({ ...prev, spaceKey: event.currentTarget.value }))}
                        placeholder="operations"
                      />
                      <TextInput
                        size="xs"
                        label="Title"
                        value={guidedPageForm.title}
                        onChange={(event) => setGuidedPageForm((prev) => ({ ...prev, title: event.currentTarget.value }))}
                        placeholder="BC Omega Access"
                      />
                      <TextInput
                        size="xs"
                        label="Slug"
                        value={guidedPageForm.slug}
                        onChange={(event) => setGuidedPageForm((prev) => ({ ...prev, slug: event.currentTarget.value }))}
                        placeholder="operations/bc-omega-access"
                      />
                      <Select
                        size="xs"
                        label="Status"
                        value={guidedPageForm.status}
                        onChange={(value) => {
                          if (value === "draft" || value === "reviewed" || value === "published") {
                            setGuidedPageForm((prev) => ({ ...prev, status: value }));
                          }
                        }}
                        allowDeselect={false}
                        data={[
                          { value: "published", label: "published" },
                          { value: "reviewed", label: "reviewed" },
                          { value: "draft", label: "draft" },
                        ]}
                      />
                    </SimpleGrid>
                    <Group mt="sm" justify="flex-end">
                      <Button size="compact-sm" variant="subtle" onClick={() => void suggestGuidedSlug()}>
                        Suggest slug
                      </Button>
                      <Button size="compact-sm" loading={creatingPage} onClick={() => void createGuidedWikiPage()}>
                        Create page
                      </Button>
                    </Group>
                  </Paper>
                }
              >
                {!selectedPageSlug ? (
                  <Paper withBorder p="lg" radius="md">
                    <Stack gap="sm">
                      <Title order={2}>Welcome to your wiki</Title>
                      <Text c="dimmed">
                        Choose a page from the left tree or create the first page for this workspace.
                      </Text>
                      <Divider />
                      <Text fw={700} size="sm">
                        Recent pages
                      </Text>
                      <Group gap="xs" wrap="wrap">
                        {wikiHomeRecentPages.map((page) => (
                          <Button
                            key={`core-home-${page.slug}`}
                            size="compact-sm"
                            variant="light"
                            onClick={() => {
                              setSelectedSpaceKey(pageGroupKey(page.slug));
                              setSelectedPageSlug(page.slug);
                            }}
                          >
                            {page.title || page.slug}
                          </Button>
                        ))}
                      </Group>
                    </Stack>
                  </Paper>
                ) : loadingPageDetail ? (
                  <Group gap={8}>
                    <Loader size="sm" />
                    <Text size="sm" c="dimmed">
                      Loading page…
                    </Text>
                  </Group>
                ) : selectedPageDetail ? (
                  <>
                    <Stack gap={2}>
                      <Title order={1}>{selectedPageDetail.page.title || selectedPageDetail.page.slug}</Title>
                      <Text size="sm" c="dimmed">
                        Updated {fmtDate(latestPageVersion?.created_at)} {latestPageVersion?.created_by ? `by ${latestPageVersion.created_by}` : ""}
                      </Text>
                    </Stack>
                    {pageEditMode ? (
                      <Paper withBorder p="sm" radius="md">
                        <Stack gap="sm">
                          <Group justify="space-between" align="center" wrap="wrap">
                            <Text size="xs" c="dimmed">
                              {pageEditDraftState === "saving"
                                ? "Autosave: saving..."
                                : pageEditDraftState === "saved"
                                  ? `Autosave: saved ${fmtDate(pageEditDraftSavedAt)}`
                                  : pageEditDraftState === "restored"
                                    ? "Autosave: restored local draft"
                                    : "Autosave: idle"}
                            </Text>
                            <Badge size="xs" variant="light" color={pageEditDraftState === "saving" ? "orange" : "teal"}>
                              {pageEditDraftState}
                            </Badge>
                          </Group>
                          <TextInput
                            label="Page title"
                            value={pageEditTitle}
                            onChange={(event) => setPageEditTitle(event.currentTarget.value)}
                          />
                          <TextInput
                            label="Change summary"
                            value={pageEditSummary}
                            onChange={(event) => setPageEditSummary(event.currentTarget.value)}
                          />
                          <Textarea
                            label="Page markdown"
                            value={pageEditMarkdown}
                            onChange={(event) => setPageEditMarkdown(event.currentTarget.value)}
                            autosize
                            minRows={20}
                          />
                          <Group justify="flex-end">
                            <Button
                              variant="subtle"
                              onClick={() => setPageEditMode(false)}
                            >
                              Cancel
                            </Button>
                            <Button
                              loading={savingPageEdit}
                              onClick={() => void saveWikiPageEdit()}
                            >
                              Update
                            </Button>
                          </Group>
                        </Stack>
                      </Paper>
                    ) : (
                      <Suspense
                        fallback={
                          <Paper withBorder p="md" radius="md">
                            <Group gap={8}>
                              <Loader size="sm" />
                              <Text size="sm" c="dimmed">
                                Rendering page…
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
                    )}
                  </>
                ) : (
                  <Text size="sm" c="dimmed">
                    Page content is unavailable.
                  </Text>
                )}
              </CoreWikiMain>
            )}
          </Paper>

          {coreWorkspaceTab === "wiki" ? (
            <CoreWikiRightRail
              isOperationsRoute={isOperationsRoute}
              selectedPageSlug={selectedPageSlug}
              selectedPageStatus={selectedPageDetail?.page.status || null}
              selectedPageVersion={latestPageVersion?.version ?? selectedPageDetail?.page.current_version ?? null}
              sections={selectedPageDetail?.sections ?? []}
              openDraftCount={selectedPageOpenDrafts.length}
              onOpenDrafts={() => setCoreWorkspaceTab("drafts")}
              reviewAssignments={pageReviewAssignments}
              assignmentAssigneeInput={assignmentAssigneeInput}
              assignmentNoteInput={assignmentNoteInput}
              onAssignmentAssigneeChange={setAssignmentAssigneeInput}
              onAssignmentNoteChange={setAssignmentNoteInput}
              onCreateReviewTask={() => void createSelectedPageReviewTask()}
              onAssignReviewer={() => void createPageReviewAssignment()}
              onResolveAssignment={(assignmentId) => void resolvePageReviewAssignment(assignmentId)}
              runningLifecycleQuickAction={runningLifecycleQuickAction}
              loadingPageReviewAssignments={loadingPageReviewAssignments}
              savingPageAssignment={savingPageAssignment}
              canCreateReviewTask={Boolean(projectId.trim() && reviewer.trim() && selectedPageSlug)}
              spaceKey={selectedPageSlug ? pageGroupKey(selectedPageSlug) : ""}
              spaceWriteMode={spaceWriteMode}
              onSpaceWriteModeChange={setSpaceWriteMode}
              spacePublishChecklistPreset={spacePublishChecklistPreset}
              onSpacePublishChecklistPresetChange={setSpacePublishChecklistPreset}
              publishChecklistOptions={PUBLISH_CHECKLIST_PRESETS.map((item) => ({
                value: item.key,
                label: item.label,
              }))}
              spaceReviewRequired={spaceReviewRequired}
              onSpaceReviewRequiredChange={setSpaceReviewRequired}
              loadingSpacePolicy={loadingSpacePolicy}
              savingSpacePolicy={savingSpacePolicy}
              onSaveSpacePolicy={() => void saveSpacePolicy()}
              policyTimelineCount={spacePolicyAudit.length}
              policyTopActorText={
                spacePolicyAdoptionSummary.topActor
                  ? `${spacePolicyAdoptionSummary.topActor} (${spacePolicyAdoptionSummary.topActorUpdates})`
                  : "n/a"
              }
              policyCadenceText={`cadence: ${formatCadenceDays(spacePolicyAdoptionSummary.avgCadenceDays)} • updates: ${spacePolicyAdoptionSummary.totalUpdates}`}
              policySourceText={spacePolicyAdoptionSummaryApi ? "api summary" : "local audit fallback"}
              loadingSpacePolicyAudit={loadingSpacePolicyAudit}
              loadingSpacePolicyAdoptionSummary={loadingSpacePolicyAdoptionSummary}
              policyAuditItems={spacePolicyAudit}
              relatedPages={selectedPageRelatedPages}
              onOpenRelatedPage={(slug) => {
                setSelectedSpaceKey(pageGroupKey(slug));
                setSelectedPageSlug(slug);
              }}
              recentVersions={selectedPageRecentVersions}
              wikiQualitySummary={
                adoptionKpi?.wiki_quality
                  ? {
                      pass:
                        typeof adoptionKpi.wiki_quality.quality?.pass === "boolean"
                          ? Boolean(adoptionKpi.wiki_quality.quality?.pass)
                          : null,
                      corePublished: Number.isFinite(Number(adoptionKpi.wiki_quality.core_pages?.published_total))
                        ? Number(adoptionKpi.wiki_quality.core_pages?.published_total)
                        : null,
                      coreRequired: Array.isArray(adoptionKpi.wiki_quality.core_pages?.required_leaves)
                        ? adoptionKpi.wiki_quality.core_pages?.required_leaves?.length || 0
                        : null,
                      placeholderRatioCore: Number.isFinite(Number(adoptionKpi.wiki_quality.content_quality?.placeholder_ratio_core))
                        ? Number(adoptionKpi.wiki_quality.content_quality?.placeholder_ratio_core)
                        : null,
                      dailySummaryDraftRatio: Number.isFinite(
                        Number(adoptionKpi.wiki_quality.draft_noise?.daily_summary_open_draft_ratio),
                      )
                        ? Number(adoptionKpi.wiki_quality.draft_noise?.daily_summary_open_draft_ratio)
                        : null,
                    }
                  : null
              }
              onOpenHistory={() => openHistoryDrawerForVersion(null)}
              onOpenVersionHistory={(version) => openHistoryDrawerForVersion(version)}
              formatDate={fmtDate}
              onOpenOperations={() => {
                setCoreWorkspaceRoute("operations");
                setCoreWorkspaceTab("wiki");
              }}
            />
          ) : null}
        </Box>

        <Modal
          opened={showQuickNavModal}
          onClose={() => setShowQuickNavModal(false)}
          title="Jump to page"
          centered
        >
          <Stack gap="sm">
            <TextInput
              autoFocus
              value={quickNavQuery}
              onChange={(event) => setQuickNavQuery(event.currentTarget.value)}
              placeholder="Type page title or slug"
            />
            <Paper withBorder p="xs" radius="md">
              <Stack gap={6}>
                {(quickNavMatches.length === 0 && quickNavQuery.trim().length > 0) ? (
                  <Text size="xs" c="dimmed">
                    No matching pages.
                  </Text>
                ) : (
                  quickNavMatches.map((item) => (
                    <Button
                      key={`quick-nav-item-${item.slug}`}
                      size="compact-sm"
                      variant={quickNavSlug === item.slug ? "filled" : "subtle"}
                      justify="flex-start"
                      onClick={() => setQuickNavSlug(item.slug)}
                    >
                      {item.title || item.slug}
                    </Button>
                  ))
                )}
              </Stack>
            </Paper>
            <Group justify="flex-end">
              <Button
                size="compact-sm"
                variant="subtle"
                disabled={quickNavQuery.trim().length < 2}
                onClick={() => {
                  const title = quickNavQuery.trim();
                  if (!title) return;
                  const space = selectedSpaceKey || guidedPageForm.spaceKey || "operations";
                  const slug = normalizeWikiSlug(`${space}/${title}`, title);
                  setGuidedPageForm((prev) => ({
                    ...prev,
                    spaceKey: space,
                    title,
                    slug,
                    changeSummary: `Created from quick search: ${title}`,
                  }));
                  setSelectedCreateTemplateKey(null);
                  setShowCoreCreatePanel(true);
                  setCoreWorkspaceTab("wiki");
                  setShowQuickNavModal(false);
                }}
              >
                Create from query
              </Button>
              <Button
                size="compact-sm"
                variant="light"
                onClick={() => setShowQuickNavModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="compact-sm"
                disabled={!(quickNavSlug || quickNavMatches[0]?.slug)}
                onClick={() => {
                  const target = quickNavSlug || quickNavMatches[0]?.slug || null;
                  if (!target) return;
                  setSelectedSpaceKey(pageGroupKey(target));
                  setSelectedPageSlug(target);
                  setCoreWorkspaceTab("wiki");
                  setShowQuickNavModal(false);
                }}
              >
                Open page
              </Button>
            </Group>
          </Stack>
        </Modal>

        <Modal
          opened={showRolesGuideModal}
          onClose={() => setShowRolesGuideModal(false)}
          title="Roles & access"
          centered
        >
          <Stack gap="sm">
            <Text size="sm" c="dimmed">
              Synapse uses four human-friendly roles. Internal RBAC claims can map to these labels.
            </Text>
            {FRIENDLY_ROLE_MODEL.map((role) => (
              <Paper key={`friendly-role-${role.key}`} withBorder p="sm" radius="md">
                <Stack gap={4}>
                  <Group justify="space-between" align="center">
                    <Text fw={700} size="sm">
                      {role.label}
                    </Text>
                    <Badge variant="light" color="indigo">
                      {role.mapsTo.join(", ")}
                    </Badge>
                  </Group>
                  <Text size="xs">{role.canDo}</Text>
                  <Text size="xs" c="dimmed">
                    Typical use: {role.typicalUse}
                  </Text>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Modal>

        <Modal
          opened={showPublishModal}
          onClose={() => {
            setShowPublishModal(false);
            setProcessSimulation(null);
            setPublishConfirmHighRisk(false);
            setPublishChecklistAcks({});
          }}
          title="Publish page"
          centered
        >
          <Stack gap="sm">
            <Text size="sm" c="dimmed">
              Publishing this page will make the latest content visible to all connected agents.
            </Text>
            <TextInput
              label="Location"
              value={selectedPageSlug || ""}
              readOnly
            />
            <TextInput
              label="Change summary"
              value={publishSummary}
              onChange={(event) => setPublishSummary(event.currentTarget.value)}
              placeholder="What changed in this version?"
            />
            {activePublishChecklistItems.length > 0 ? (
              <Paper withBorder p="xs" radius="md">
                <Stack gap={6}>
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Text size="xs" fw={700}>
                      Publish checklist · {activePublishChecklistPreset.label}
                    </Text>
                    <Badge size="xs" variant="light" color={isPublishChecklistComplete ? "teal" : "orange"}>
                      {isPublishChecklistComplete
                        ? "ready"
                        : `${activePublishChecklistItems.filter((item) => Boolean(publishChecklistAcks[item.id])).length}/${activePublishChecklistItems.length}`}
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed">
                    {activePublishChecklistPreset.description}
                  </Text>
                  <Stack gap={4}>
                    {activePublishChecklistItems.map((item) => (
                      <Checkbox
                        key={`publish-check-${item.id}`}
                        size="xs"
                        checked={Boolean(publishChecklistAcks[item.id])}
                        onChange={(event) =>
                          setPublishChecklistAcks((prev) => ({
                            ...prev,
                            [item.id]: event.currentTarget.checked,
                          }))
                        }
                        label={item.label}
                        description={item.help}
                      />
                    ))}
                  </Stack>
                </Stack>
              </Paper>
            ) : null}
            <Group justify="space-between" align="center" wrap="wrap">
              <Button
                size="compact-sm"
                variant="light"
                loading={loadingProcessSimulation}
                disabled={!selectedPageSlug || !projectId.trim()}
                onClick={() => void runProcessSafetySimulation()}
              >
                Run safety simulation
              </Button>
              {processSimulation?.risk ? (
                <Group gap={6}>
                  <Badge
                    size="sm"
                    variant="light"
                    color={processSimulation.risk.should_block_publish ? "red" : processSimulation.risk.level === "medium" ? "orange" : "teal"}
                  >
                    risk {processSimulation.risk.level}
                  </Badge>
                  <Badge size="sm" variant="light" color="blue">
                    score {processSimulation.risk.score}
                  </Badge>
                  <Badge size="sm" variant="light" color="indigo">
                    suggested {processSimulation.risk.suggested_publish_mode}
                  </Badge>
                </Group>
              ) : null}
            </Group>
            {processSimulation ? (
              <Paper withBorder p="xs" radius="md">
                <Stack gap={4}>
                  <Text size="xs" fw={700}>
                    Pre-publish impact preview
                  </Text>
                  <Text size="xs" c="dimmed">
                    {processSimulation.recommendation?.action}
                  </Text>
                  <Group gap={6} wrap="wrap">
                    <Badge size="xs" variant="light" color="gray">
                      changed terms {processSimulation.diff.changed_terms_total}
                    </Badge>
                    <Badge size="xs" variant="light" color="gray">
                      impacted pages {processSimulation.impact.candidate_pages_total}
                    </Badge>
                    <Badge size="xs" variant="light" color="gray">
                      pending drafts {processSimulation.impact.pending_process_drafts}
                    </Badge>
                    <Badge size="xs" variant="light" color="gray">
                      open conflicts {processSimulation.impact.open_process_conflicts}
                    </Badge>
                  </Group>
                  {processSimulation.risk.high_risk_hits?.length ? (
                    <Text size="xs" c="red">
                      high-risk matches: {processSimulation.risk.high_risk_hits.join(", ")}
                    </Text>
                  ) : null}
                  {processSimulation.impact.top_impacted_pages?.length ? (
                    <Stack gap={2}>
                      {processSimulation.impact.top_impacted_pages.slice(0, 4).map((item) => (
                        <Text key={`sim-impact-${item.slug}`} size="xs" c="dimmed">
                          {item.slug} ({item.page_type}) {item.matched_terms?.length ? `- ${item.matched_terms.join(", ")}` : ""}
                        </Text>
                      ))}
                    </Stack>
                  ) : null}
                </Stack>
              </Paper>
            ) : null}
            {processSimulation?.risk?.should_block_publish ? (
              <Checkbox
                checked={publishConfirmHighRisk}
                onChange={(event) => setPublishConfirmHighRisk(event.currentTarget.checked)}
                label="I understand this is a high-risk process/policy change and want to publish anyway."
              />
            ) : null}
            <Group justify="flex-end">
              <Button
                size="compact-sm"
                variant="light"
                onClick={() => setShowPublishModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="compact-sm"
                loading={savingPageEdit}
                disabled={
                  !selectedPageSlug ||
                  !isPublishChecklistComplete ||
                  Boolean(processSimulation?.risk?.should_block_publish && !publishConfirmHighRisk)
                }
                onClick={() => void publishCurrentPage()}
              >
                Publish
              </Button>
            </Group>
          </Stack>
        </Modal>

        {effectiveUiMode === "core" ? (
          <Drawer
            opened={historyDrawerOpen}
            onClose={() => setHistoryDrawerOpen(false)}
            position="right"
            size={680}
            title={selectedPageDetail?.page.title ? `Page history · ${selectedPageDetail.page.title}` : "Page history"}
          >
            <Stack gap="sm" data-testid="core-history-drawer">
              {!selectedPageSlug ? (
                <Text size="sm" c="dimmed">
                  Select page first.
                </Text>
              ) : !pageHistory || historyVersionOptions.length === 0 ? (
                <Group gap={8}>
                  <Loader size="sm" />
                  <Text size="sm" c="dimmed">
                    Loading history…
                  </Text>
                </Group>
              ) : (
                <>
                  <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                    <Select
                      label="Target version"
                      value={historyTargetVersion}
                      onChange={(value) => setHistoryTargetVersion(value)}
                      data={historyVersionOptions}
                      allowDeselect={false}
                    />
                    <Select
                      label="Base version"
                      value={historyBaseVersion}
                      onChange={(value) => setHistoryBaseVersion(value)}
                      data={historyVersionOptions}
                      allowDeselect={false}
                    />
                  </SimpleGrid>
                  <Group gap={6} wrap="wrap">
                    <Badge size="sm" variant="light" color="teal">
                      +{historyDiffPreview.added}
                    </Badge>
                    <Badge size="sm" variant="light" color="red">
                      -{historyDiffPreview.removed}
                    </Badge>
                    <Badge size="sm" variant="light" color={historyDiffPreview.changed ? "orange" : "gray"}>
                      {historyDiffPreview.changed ? "changed" : "no changes"}
                    </Badge>
                  </Group>
                  <Paper withBorder p="xs" radius="md">
                    <ScrollArea h={380} type="auto">
                      <Stack gap={2} data-testid="core-history-inline-diff">
                        {historyDiffPreview.lines.map((line, index) => {
                          const bg =
                            line.kind === "added"
                              ? "rgba(12, 166, 120, 0.14)"
                              : line.kind === "removed"
                                ? "rgba(250, 82, 82, 0.14)"
                                : "rgba(148, 163, 184, 0.08)";
                          const symbol = line.kind === "added" ? "+" : line.kind === "removed" ? "-" : " ";
                          return (
                            <Box
                              key={`core-history-diff-line-${index}-${line.kind}`}
                              style={{
                                borderRadius: "6px",
                                background: bg,
                                padding: "4px 6px",
                                fontFamily:
                                  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                                fontSize: "12px",
                                lineHeight: 1.4,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}
                            >
                              {symbol} {line.text}
                            </Box>
                          );
                        })}
                      </Stack>
                    </ScrollArea>
                  </Paper>
                  <Text size="xs" c="dimmed">
                    Comparing v{historyBaseVersionItem?.version ?? "—"} → v{historyTargetVersionItem?.version ?? "—"}.
                  </Text>
                  {isOperationsRoute ? (
                    <Paper withBorder p="xs" radius="md">
                      <Stack gap={6}>
                        <Text size="xs" fw={700}>
                          Rollback
                        </Text>
                        <TextInput
                          size="xs"
                          label="Rollback summary"
                          value={rollbackSummaryInput}
                          onChange={(event) => setRollbackSummaryInput(event.currentTarget.value)}
                          placeholder="Why this rollback is needed"
                        />
                        <Group justify="flex-end" align="center" wrap="wrap">
                          <Button
                            size="compact-sm"
                            variant="light"
                            color="orange"
                            loading={rollingBackPageVersion}
                            disabled={!canRollbackTargetInOperations}
                            onClick={() => void rollbackSelectedPageVersion()}
                          >
                            Rollback to v{historyTargetVersionItem?.version ?? "?"}
                          </Button>
                        </Group>
                        {!canRollbackTargetInOperations ? (
                          <Text size="xs" c="dimmed">
                            Rollback is available for non-current versions in operations mode.
                          </Text>
                        ) : null}
                      </Stack>
                    </Paper>
                  ) : (
                    <Paper withBorder p="xs" radius="md">
                      <Stack gap={6}>
                        <Text size="xs" c="dimmed">
                          Rollback actions are restricted to Operations route.
                        </Text>
                        <Group justify="flex-end">
                          <Button
                            size="compact-sm"
                            variant="light"
                            color="orange"
                            onClick={() => {
                              setCoreWorkspaceRoute("operations");
                              setCoreWorkspaceTab("wiki");
                            }}
                          >
                            Open operations
                          </Button>
                        </Group>
                      </Stack>
                    </Paper>
                  )}
                </>
              )}
            </Stack>
          </Drawer>
        ) : null}

        <Modal
          opened={showOnboardingModal}
          onClose={() => setShowOnboardingModal(false)}
          title="Welcome to Synapse Wiki"
          centered
        >
          <Stack gap="sm">
            <Badge variant="light" color="blue">
              Step {onboardingStep} of 3
            </Badge>
            {onboardingStep === 1 && (
              <>
                <Text size="sm" fw={700}>
                  1. Connect your workspace
                </Text>
                <Text size="sm" c="dimmed">
                  Project and reviewer are already set. Next we create your first wiki page.
                </Text>
              </>
            )}
            {onboardingStep === 2 && (
              <>
                <Text size="sm" fw={700}>
                  2. Create your first page
                </Text>
                <Group gap={6} wrap="wrap">
                  {PAGE_TEMPLATES.map((template) => (
                    <Button
                      key={`onboarding-template-${template.key}`}
                      size="compact-xs"
                      variant="light"
                      onClick={() => {
                        applyCreateTemplate(template.key);
                        setShowCoreCreatePanel(true);
                        setCoreWorkspaceTab("wiki");
                        setShowOnboardingModal(false);
                      }}
                    >
                      {template.title}
                    </Button>
                  ))}
                </Group>
                <Text size="xs" c="dimmed">
                  Selecting a template opens the create panel prefilled.
                </Text>
              </>
            )}
            {onboardingStep === 3 && (
              <>
                <Text size="sm" fw={700}>
                  3. Review incoming drafts
                </Text>
                <Text size="sm" c="dimmed">
                  Drafts are a separate inbox. Use it only when updates need moderation.
                </Text>
              </>
            )}
            <Group justify="space-between">
              <Button
                size="compact-sm"
                variant="subtle"
                disabled={onboardingStep <= 1}
                onClick={() => setOnboardingStep((prev) => Math.max(1, prev - 1))}
              >
                Back
              </Button>
              <Group gap="xs">
                <Button
                  size="compact-sm"
                  variant="light"
                  onClick={() => {
                    completeOnboarding();
                    setCoreWorkspaceTab("wiki");
                  }}
                >
                  Skip
                </Button>
                {onboardingStep < 3 ? (
                  <Button
                    size="compact-sm"
                    onClick={() => setOnboardingStep((prev) => Math.min(3, prev + 1))}
                  >
                    Next
                  </Button>
                ) : (
                  <Button
                    size="compact-sm"
                    onClick={() => {
                      completeOnboarding();
                      setCoreWorkspaceTab("drafts");
                    }}
                  >
                    Finish
                  </Button>
                )}
              </Group>
            </Group>
          </Stack>
        </Modal>
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
                  void loadWikiLifecycleStats();
                  void loadNotificationsInbox();
                  if (selectedPageSlug) {
                    void loadSpacePolicy(selectedPageSlug);
                    void loadSpacePolicyAudit(selectedPageSlug);
                    void loadSpacePolicyAdoptionSummary(selectedPageSlug);
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
          {effectiveUiMode === "core" && (
            <Paper withBorder radius="lg" p="sm" mb="md">
              <Group justify="space-between" align="center" wrap="wrap">
                <Group gap={6} wrap="wrap">
                  <Badge variant="light" color={projectId.trim() ? "teal" : "orange"}>
                    project: {projectId.trim() || "not set"}
                  </Badge>
                  <Badge variant="light" color="gray">
                    reviewer: {reviewer.trim() || "ops_manager"}
                  </Badge>
                </Group>
                <Group gap={6} wrap="wrap">
                  <Button
                    size="compact-xs"
                    variant="light"
                    onClick={() => setSettingsDrawerOpen(true)}
                  >
                    Settings
                  </Button>
                  <Button
                    size="compact-xs"
                    variant="filled"
                    color="teal"
                    onClick={() => void loadDrafts()}
                    loading={loadingDrafts}
                    leftSection={<IconArrowsShuffle size={14} />}
                  >
                    Refresh inbox
                  </Button>
                </Group>
              </Group>
            </Paper>
          )}

          {effectiveUiMode === "advanced" && (
            <>
          <SimpleGrid cols={{ base: 1, md: 2, lg: 5 }} spacing="md">
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
            </>
          )}
        </Paper>

        {effectiveUiMode === "core" && (
          <Drawer
            opened={settingsDrawerOpen}
            onClose={() => setSettingsDrawerOpen(false)}
            position="right"
            size={460}
            title="Workspace settings"
          >
            <Stack gap="md">
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
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
              </SimpleGrid>
              <Text size="xs" c="dimmed">
                API endpoint uses workspace default. Set VITE_SYNAPSE_API_URL to override.
              </Text>
              <Group gap="xs" wrap="wrap">
                <Button
                  size="xs"
                  variant="light"
                  onClick={() => void loadDrafts()}
                  loading={loadingDrafts}
                  leftSection={<IconArrowsShuffle size={14} />}
                >
                  Refresh inbox
                </Button>
                <Button size="xs" variant="light" onClick={() => void loadNotificationsInbox()}>
                  Refresh notifications
                </Button>
                <Button
                  size="xs"
                  variant="subtle"
                  color="teal"
                  loading={savingNotificationState}
                  onClick={() => void markAllNotificationsRead()}
                >
                  Mark all read
                </Button>
              </Group>
              <Paper withBorder radius="lg" p="md">
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
                      {notificationsInbox.slice(0, 10).map((item) => (
                        <Paper key={`notif-drawer-${item.id}`} withBorder p="xs" radius="md">
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
            </Stack>
          </Drawer>
        )}

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
                Review and publish trusted knowledge pages with a page-first workspace.
              </Text>
              <Group gap="xs" wrap="wrap">
                <Badge variant="light" color="teal">
                  Wiki
                </Badge>
                <Text size="xs" c="dimmed">
                  Drafts and Tasks are secondary tabs.
                </Text>
              </Group>
            </Stack>
          </Paper>
        )}
        {effectiveUiMode === "advanced" && (
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

        <Modal
          opened={showLegacySetupModal}
          onClose={() => {
            if (connectingLegacySource) return;
            setShowLegacySetupModal(false);
          }}
          title="Connect Existing Agent Memory"
          centered
        >
          <Stack gap="sm">
            <Badge variant="light" color="teal">
              Step {legacySetupStep} of 5
            </Badge>
            {legacySetupStep === 1 && (
              <Stack gap={8}>
                <Text size="sm" fw={700}>
                  1. Choose connector template
                </Text>
                <Text size="sm" c="dimmed">
                  Select a prebuilt connector for your existing memory schema.
                </Text>
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs">
                  {(adoptionImportConnectors.length > 0
                    ? adoptionImportConnectors
                    : [
                        {
                          id: "postgres_sql:ops_kb_items:polling",
                          source_type: "postgres_sql",
                          profile: "ops_kb_items",
                          sync_mode: "polling",
                          label: "Ops KB Items (Polling)",
                          description: "Operational KB table via incremental polling.",
                          validation_hints: { warnings: [] },
                        },
                        {
                          id: "postgres_sql:memory_items:polling",
                          source_type: "postgres_sql",
                          profile: "memory_items",
                          sync_mode: "polling",
                          label: "Memory Items (Polling)",
                          description: "Runtime memory table via incremental polling.",
                          validation_hints: { warnings: [] },
                        },
                        {
                          id: "memory_api:generic:polling",
                          source_type: "memory_api",
                          profile: "generic",
                          sync_mode: "polling",
                          label: "Memory API (Polling)",
                          description: "REST memory endpoint with path mapping and cursor polling.",
                          validation_hints: { warnings: [] },
                        },
                      ]
                  ).map((connector) => (
                    <Paper
                      key={`legacy-connector-${connector.id}`}
                      withBorder
                      p="xs"
                      radius="md"
                      style={{ cursor: "pointer" }}
                      onClick={() => {
                        setSelectedConnectorId(connector.id);
                        setLegacySqlProfile(connector.profile);
                      }}
                    >
                      <Stack gap={4}>
                        <Group justify="space-between" align="center">
                          <Text size="sm" fw={700}>
                            {connector.label}
                          </Text>
                          <Badge
                            size="xs"
                            variant={selectedConnectorId === connector.id ? "filled" : "light"}
                            color={selectedConnectorId === connector.id ? "teal" : "gray"}
                          >
                            {selectedConnectorId === connector.id ? "selected" : "choose"}
                          </Badge>
                        </Group>
                        <Text size="xs" c="dimmed">
                          profile: {connector.profile} • mode: {connector.sync_mode}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {connector.description}
                        </Text>
                        {connector.validation_hints?.warnings && connector.validation_hints.warnings.length > 0 ? (
                          <Text size="xs" c="dimmed">
                            {connector.validation_hints.warnings[0]}
                          </Text>
                        ) : null}
                      </Stack>
                    </Paper>
                  ))}
                </SimpleGrid>
              </Stack>
            )}
            {legacySetupStep === 2 && (
              <Stack gap={8}>
                <Text size="sm" fw={700}>
                  2. Configure connector
                </Text>
                <Text size="sm" c="dimmed">
                  These are the only required fields for day-0 adoption.
                </Text>
                <TextInput
                  label="Source ref"
                  value={legacySourceRef}
                  onChange={(event) => setLegacySourceRef(event.currentTarget.value)}
                  placeholder="existing_memory"
                />
                {String(selectedAdoptionConnector?.source_type || "postgres_sql") === "memory_api" ? (
                  <TextInput
                    label="Memory API URL"
                    value={legacyMemoryApiUrl}
                    onChange={(event) => setLegacyMemoryApiUrl(event.currentTarget.value)}
                    placeholder="https://memory.company/v1/items"
                  />
                ) : (
                  <TextInput
                    label="Postgres DSN env var"
                    value={legacySqlDsnEnv}
                    onChange={(event) => setLegacySqlDsnEnv(event.currentTarget.value)}
                    placeholder="HW_MEMORY_DSN"
                  />
                )}
                <Select
                  label="Noise preset"
                  value="knowledge_v2"
                  data={[
                    { value: "knowledge_v2", label: "knowledge_v2 (recommended)" },
                    { value: "strict", label: "strict" },
                    { value: "order_snapshots", label: "order_snapshots" },
                    { value: "telemetry", label: "telemetry" },
                  ]}
                  disabled
                />
                <Select
                  label="Sync interval"
                  value={legacySyncIntervalMinutes}
                  onChange={(value) => {
                    if (!value) return;
                    setLegacySyncIntervalMinutes(value);
                  }}
                  data={[
                    { value: "1", label: "every 1 minute" },
                    { value: "5", label: "every 5 minutes" },
                    { value: "15", label: "every 15 minutes" },
                    { value: "30", label: "every 30 minutes" },
                    { value: "60", label: "every 60 minutes" },
                  ]}
                  allowDeselect={false}
                />
                {loadingConnectorResolve ? (
                  <Text size="xs" c="dimmed">
                    Resolving connector overrides…
                  </Text>
                ) : null}
                {resolvedConnector?.validation_hints ? (
                  <Paper withBorder p="xs" radius="md">
                    <Stack gap={4}>
                      <Text size="xs" fw={700}>
                        Validation
                      </Text>
                      {resolvedConnector.validation_hints.errors && resolvedConnector.validation_hints.errors.length > 0 ? (
                        <Text size="xs" c="red">
                          {resolvedConnector.validation_hints.errors.join(" ")}
                        </Text>
                      ) : (
                        <Text size="xs" c="teal">
                          Connector config is valid for first sync.
                        </Text>
                      )}
                      {resolvedConnector.validation_hints.warnings && resolvedConnector.validation_hints.warnings.length > 0 ? (
                        <Text size="xs" c="dimmed">
                          {resolvedConnector.validation_hints.warnings[0]}
                        </Text>
                      ) : null}
                    </Stack>
                  </Paper>
                ) : null}
              </Stack>
            )}
            {legacySetupStep === 3 && (
              <Stack gap={8}>
                <Text size="sm" fw={700}>
                  3. Connect source and queue sync
                </Text>
                <Text size="sm" c="dimmed">
                  Synapse will create/update connector and enqueue first import run.
                </Text>
                <Paper withBorder p="xs" radius="md">
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">
                      Profile
                    </Text>
                    <Text size="sm" fw={700}>
                      {selectedAdoptionConnector?.label || legacySelectedProfile?.label || legacySqlProfile}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Connector
                    </Text>
                    <Text size="sm" fw={700}>
                      {selectedAdoptionConnector?.id || "manual"}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Source
                    </Text>
                    <Text size="sm" fw={700}>
                      {legacySourceRef || "—"}
                    </Text>
                    {String(selectedAdoptionConnector?.source_type || "postgres_sql") === "memory_api" ? (
                      <>
                        <Text size="xs" c="dimmed">
                          Memory API URL
                        </Text>
                        <Text size="sm" fw={700}>
                          {legacyMemoryApiUrl || legacySourceRef || "—"}
                        </Text>
                      </>
                    ) : (
                      <>
                        <Text size="xs" c="dimmed">
                          DSN env
                        </Text>
                        <Text size="sm" fw={700}>
                          {legacySqlDsnEnv || "—"}
                        </Text>
                      </>
                    )}
                    <Text size="xs" c="dimmed">
                      Interval
                    </Text>
                    <Text size="sm" fw={700}>
                      every {legacySyncIntervalMinutes || "5"} minute(s)
                    </Text>
                  </Stack>
                </Paper>
                <Checkbox
                  label="After connect, open Drafts migration tools"
                  checked={legacyAutoOpenMigrationMode}
                  onChange={(event) => setLegacyAutoOpenMigrationMode(event.currentTarget.checked)}
                />
              </Stack>
            )}
            {legacySetupStep === 4 && (
              <Stack gap={8}>
                <Text size="sm" fw={700}>
                  4. Preview curated import
                </Text>
                <Text size="sm" c="dimmed">
                  Run trusted-source preview to confirm draft quality before publish.
                </Text>
                <Paper withBorder p="xs" radius="md">
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">
                      Trusted sources
                    </Text>
                    <Text size="sm" fw={700}>
                      {bootstrapTrustedSources || "legacy_import,postgres_sql"}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Recommendation
                    </Text>
                    <Text size="sm" fw={700}>
                      min_confidence {Number(bootstrapRecommendation?.recommended?.min_confidence || 0.85).toFixed(2)} • limit{" "}
                      {Number(bootstrapRecommendation?.recommended?.limit || 50)}
                    </Text>
                    {bootstrapResult?.dry_run ? (
                      <Text size="xs" c="teal">
                        Preview ready: {Number(bootstrapResult.summary?.candidates || 0)} candidates, sample{" "}
                        {Number(bootstrapResult.summary?.sample_size || 0)}.
                      </Text>
                    ) : (
                      <Text size="xs" c="dimmed">
                        Run preview now to inspect migration candidates.
                      </Text>
                    )}
                  </Stack>
                </Paper>
              </Stack>
            )}
            {legacySetupStep === 5 && (
              <Stack gap={8}>
                <Text size="sm" fw={700}>
                  5. First publish batch
                </Text>
                <Text size="sm" c="dimmed">
                  Apply the trusted batch and jump to Wiki/Drafts for final review.
                </Text>
                <Paper withBorder p="xs" radius="md">
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">
                      Preview status
                    </Text>
                    <Text size="sm" fw={700}>
                      {bootstrapResult?.dry_run
                        ? `${Number(bootstrapResult.summary?.candidates || 0)} candidates`
                        : "Preview missing (run step 4 first)."}
                    </Text>
                    <Text size="xs" c="dimmed">
                      After apply, Synapse opens Drafts tab so you can verify quality instantly.
                    </Text>
                  </Stack>
                </Paper>
                <Checkbox
                  label="Create starter wiki pages automatically (Agent Profile, Data Map, Runbook)"
                  checked={legacySeedStarterPages}
                  onChange={(event) => setLegacySeedStarterPages(event.currentTarget.checked)}
                />
                {legacySeedStarterPages ? (
                  <Select
                    label="Starter profile"
                    value={legacyStarterProfile}
                    onChange={(value) => setLegacyStarterProfile(value === "support_ops" ? "support_ops" : "standard")}
                    data={[
                      { value: "standard", label: "standard" },
                      { value: "support_ops", label: "support_ops" },
                    ]}
                    allowDeselect={false}
                  />
                ) : null}
              </Stack>
            )}
            <Group justify="space-between">
              <Button
                size="compact-sm"
                variant="subtle"
                disabled={legacySetupStep <= 1 || connectingLegacySource}
                onClick={() => setLegacySetupStep((prev) => Math.max(1, prev - 1))}
              >
                Back
              </Button>
              <Group gap="xs">
                <Button
                  size="compact-sm"
                  variant="light"
                  disabled={connectingLegacySource}
                  onClick={() => setShowLegacySetupModal(false)}
                >
                  Cancel
                </Button>
                {legacySetupStep < 3 ? (
                  <Button
                    size="compact-sm"
                    onClick={() => {
                      if (legacySetupStep === 1) setLegacyWizardStep1Done(true);
                      if (legacySetupStep === 2) setLegacyWizardStep2Done(true);
                      setLegacySetupStep((prev) => Math.min(5, prev + 1));
                    }}
                  >
                    Next
                  </Button>
                ) : legacySetupStep === 3 ? (
                  <Button
                    size="compact-sm"
                    color="teal"
                    loading={connectingLegacySource}
                    onClick={() => void completeLegacySetupWizard()}
                  >
                    Connect & queue sync
                  </Button>
                ) : legacySetupStep === 4 ? (
                  <Button
                    size="compact-sm"
                    color="indigo"
                    loading={bootstrapLoading}
                    onClick={async () => {
                      await runRecommendedBootstrapPreview();
                      setLegacyWizardStep4Done(true);
                      setLegacySetupStep(5);
                    }}
                  >
                    Preview curated import
                  </Button>
                ) : (
                  <Button
                    size="compact-sm"
                    color="teal"
                    loading={bootstrapLoading || runningStarterBootstrap}
                    onClick={async () => {
                      await runRecommendedBootstrapApply();
                      if (legacySeedStarterPages) {
                        await runFirstRunStarterBootstrap();
                      }
                      setCoreWorkspaceRoute("wiki");
                      setCoreWorkspaceTab("drafts");
                      setShowLegacySetupModal(false);
                      setLegacySetupStep(1);
                    }}
                  >
                    Apply first batch
                  </Button>
                )}
              </Group>
            </Group>
            <Group gap={6} wrap="wrap">
              <Badge size="xs" color={legacyWizardStep1Done ? "teal" : "gray"} variant="light">
                template {legacyWizardStep1Done ? "done" : "todo"}
              </Badge>
              <Badge size="xs" color={legacyWizardStep2Done ? "teal" : "gray"} variant="light">
                config {legacyWizardStep2Done ? "done" : "todo"}
              </Badge>
              <Badge size="xs" color={legacyWizardStep3Done ? "teal" : "gray"} variant="light">
                connect {legacyWizardStep3Done ? "done" : "todo"}
              </Badge>
              <Badge size="xs" color={legacyWizardStep4Done ? "teal" : "gray"} variant="light">
                preview {legacyWizardStep4Done ? "done" : "todo"}
              </Badge>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Box>
  );
}
