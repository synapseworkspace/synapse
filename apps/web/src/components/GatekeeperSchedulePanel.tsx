import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { BarChart, LineChart } from "@mantine/charts";
import { notifications } from "@mantine/notifications";
import { IconDeviceFloppy, IconPlayerPause, IconPlayerPlay, IconRefresh, IconTrash } from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type GatekeeperCalibrationSchedule = {
  id: string;
  project_id: string;
  name: string;
  enabled: boolean;
  preset: "nightly" | "weekly" | string;
  interval_hours: number | null;
  lookback_days: number;
  limit_rows: number;
  holdout_ratio: number;
  split_seed: string;
  weights: number[];
  confidences: number[];
  score_thresholds: number[];
  top_k: number;
  allow_guardrail_fail: boolean;
  snapshot_note: string | null;
  updated_by: string | null;
  last_run_at: string | null;
  last_status: string | null;
  last_run_summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type GatekeeperSchedulePanelProps = {
  apiUrl: string;
  projectId: string;
  reviewer: string;
  onRefresh?: () => Promise<void> | void;
};

type CalibrationOperationScheduleResult = {
  schedule_id: string | null;
  schedule_name: string;
  project_id: string;
  status: string;
  due: boolean;
  due_at: string | null;
  last_snapshot_at: string | null;
  interval_hours: number;
  force_run: boolean;
  skip_due_check: boolean;
};

type CalibrationOperationSummary = {
  status: string;
  run_id: string;
  started_at: string;
  finished_at: string;
  total_schedules: number;
  executed_count: number;
  alerts_count: number;
  results: CalibrationOperationScheduleResult[];
  artifacts_dir: string | null;
};

type CalibrationOperationPayload = {
  project_id: string;
  dry_run: boolean;
  force_run: boolean;
  skip_due_check: boolean;
  command_preview: string;
  process: {
    returncode: number;
    duration_ms: number;
    stderr_tail: string | null;
  };
  summary: CalibrationOperationSummary | Record<string, unknown>;
  generated_at: string;
};

type CalibrationOperationRun = {
  id: string;
  project_id: string;
  operation_token: string;
  requested_by: string | null;
  dry_run: boolean;
  status: "queued" | "running" | "cancel_requested" | "succeeded" | "failed" | "canceled" | string;
  mode: "sync" | "async" | string;
  progress_percent: number;
  progress_phase: string | null;
  attempt_no: number;
  max_attempts: number;
  retry_of: string | null;
  cancel_requested: boolean;
  cancel_requested_by: string | null;
  cancel_requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  worker_id: string | null;
  error_message: string | null;
  request_payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  events_count: number;
  last_event_id: number | null;
};

type CalibrationOperationEvent = {
  id: number;
  operation_run_id: string;
  project_id: string;
  event_type: string;
  phase: string | null;
  message: string;
  progress_percent: number | null;
  payload: Record<string, unknown>;
  created_at: string;
};

type CalibrationQueueControl = {
  project_id: string;
  paused_until: string | null;
  pause_reason: string | null;
  pause_active: boolean;
  worker_lag_sla_minutes: number;
  queue_depth_warn: number;
  incident_preflight_enforcement_mode?: "off" | "block" | "pause" | string;
  incident_preflight_pause_hours?: number;
  incident_preflight_critical_fail_threshold?: number;
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueOwnership = {
  project_id: string;
  owner_name: string | null;
  owner_contact: string | null;
  oncall_channel: string | null;
  escalation_channel: string | null;
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueIncident = {
  id: string;
  project_id: string;
  status: "open" | "resolved" | string;
  trigger_health: string;
  trigger_alert_codes: string[];
  open_reason: string | null;
  resolve_reason: string | null;
  external_provider: string;
  external_ticket_id: string | null;
  external_ticket_url: string | null;
  open_payload: Record<string, unknown>;
  resolve_payload: Record<string, unknown>;
  opened_at: string | null;
  resolved_at: string | null;
  last_sync_at: string | null;
  created_by: string;
  updated_by: string;
};

type CalibrationQueueIncidentHook = {
  project_id: string;
  enabled: boolean;
  provider: "webhook" | "pagerduty" | "jira" | string;
  open_webhook_url: string | null;
  resolve_webhook_url: string | null;
  provider_config: Record<string, unknown>;
  open_on_health: string[];
  auto_resolve: boolean;
  cooldown_minutes: number;
  timeout_sec: number;
  secret_edit_roles?: string[];
  secret_access?: {
    required_roles: string[];
    can_edit: boolean;
  };
  provider_config_secret_keys?: string[];
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueIncidentPolicy = {
  id: string;
  project_id: string;
  alert_code: string;
  enabled: boolean;
  priority: number;
  provider_override: "webhook" | "pagerduty" | "jira" | null | string;
  open_webhook_url: string | null;
  resolve_webhook_url: string | null;
  provider_config_override: Record<string, unknown>;
  severity_by_health: Record<string, string>;
  open_on_health: string[];
  secret_edit_roles?: string[];
  secret_access?: {
    required_roles: string[];
    can_edit: boolean;
  };
  provider_config_override_secret_keys?: string[];
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueThroughput = {
  project_id: string;
  window_hours: number;
  generated_at: string;
  control: CalibrationQueueControl;
  queue: {
    depth_total: number;
    queued: number;
    running: number;
    cancel_requested: number;
    succeeded: number;
    failed: number;
    canceled: number;
    oldest_queued_at: string | null;
    newest_queued_at: string | null;
    oldest_queued_age_minutes: number | null;
    queued_age_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
  };
  worker_lag: {
    sla_minutes: number;
    stale_workers: number;
    lag_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
  };
  throughput_window: {
    since: string;
    terminal_total: number;
    succeeded: number;
    failed: number;
    canceled: number;
    duration_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
  };
  health: "healthy" | "watch" | "critical" | string;
  alerts: Array<{
    code: string;
    severity: "info" | "warning" | "critical" | string;
    message: string;
  }>;
  ownership?: CalibrationQueueOwnership;
  incident?: CalibrationQueueIncident | null;
};

type CalibrationQueueThroughputCompare = {
  window_hours: number;
  requested_projects: string[];
  projects: CalibrationQueueThroughput[];
  generated_at: string;
};

type CalibrationQueueAuditPayload = {
  project_id: string | null;
  days: number;
  since: string;
  events: Array<{
    id: number;
    project_id: string;
    action: string;
    actor: string;
    reason: string | null;
    paused_until: string | null;
    payload: Record<string, unknown>;
    created_at: string;
    annotation: {
      id: string;
      status: "acknowledged" | "resolved" | string;
      note: string | null;
      follow_up_owner: string | null;
      created_by: string | null;
      created_at: string | null;
    } | null;
  }>;
  generated_at: string;
};

type CalibrationQueueAutoscalingRecommendation = {
  project_id: string;
  window_hours: number;
  history_hours: number;
  generated_at: string;
  health: "healthy" | "watch" | "critical" | string;
  current: {
    worker_concurrency_estimate: number;
    worker_lag_sla_minutes: number;
    queue_depth_warn: number;
  };
  observed: {
    history_since: string;
    created_total: number;
    started_total: number;
    terminal_total: number;
    duration_count: number;
    duration_minutes: {
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
    arrival_rate_per_hour: number;
    completion_rate_per_hour: number;
    arrival_peak_per_hour: number;
    completion_peak_per_hour: number;
    arrivals_per_active_hour: number;
    completions_per_active_hour: number;
    queue_depth: number;
    queue_wait_p90_minutes: number | null;
    worker_lag_p90_minutes: number | null;
    single_worker_capacity_per_hour: number;
  };
  recommendation: {
    worker_concurrency_target: number;
    worker_concurrency_delta: number;
    worker_lag_sla_minutes: number;
    queue_depth_warn: number;
    confidence: number;
    rationale: string[];
  };
  actions: Array<{
    id: string;
    priority: "high" | "medium" | "low" | string;
    title: string;
    detail: string;
  }>;
};

type CalibrationQueueAutoscalingPayload = {
  window_hours: number;
  history_hours: number;
  requested_projects: string[];
  recommendations: CalibrationQueueAutoscalingRecommendation[];
  generated_at: string;
};

type CalibrationQueueGovernanceDigest = {
  window_hours: number;
  audit_days: number;
  requested_projects: string[];
  generated_at: string;
  summary: {
    projects_total: number;
    critical_projects: number;
    watch_projects: number;
    paused_projects: number;
    unreviewed_pauses: number;
    congested_projects: number;
    open_incidents: number;
  };
  top_congestion: Array<{
    project_id: string;
    health: "healthy" | "watch" | "critical" | string;
    queue_depth: number;
    queued: number;
    running: number;
    queued_wait_p90_minutes: number | null;
    worker_lag_p90_minutes: number | null;
    stale_workers: number;
    pause_active: boolean;
    ownership?: CalibrationQueueOwnership;
    incident?: CalibrationQueueIncident | null;
  }>;
  unreviewed_pauses: Array<{
    project_id: string;
    paused_until: string | null;
    pause_reason: string | null;
    pause_updated_by: string | null;
    latest_action: string | null;
    latest_actor: string | null;
    latest_reason: string | null;
    latest_event_at: string | null;
    pause_age_minutes: number | null;
    queue_depth: number;
    health: "healthy" | "watch" | "critical" | string;
    ownership?: CalibrationQueueOwnership;
  }>;
};

type CalibrationQueueIncidentEscalationDigest = {
  window_hours: number;
  incident_sla_hours: number;
  requested_projects: string[];
  generated_at: string;
  summary: {
    projects_total: number;
    open_incidents: number;
    open_incidents_over_sla: number;
    critical_open_incidents: number;
    incidents_missing_owner: number;
    incidents_missing_oncall_channel: number;
    incidents_missing_escalation_channel: number;
    incidents_without_ticket: number;
    routing_ready_open_incidents: number;
    routing_ready_rate: number;
    ownership_gap_projects: number;
    ownership_gap_with_open_incident: number;
  };
  age_buckets: {
    under_1h: number;
    between_1h_4h: number;
    between_4h_12h: number;
    between_12h_24h: number;
    between_24h_72h: number;
    over_72h: number;
    unknown: number;
  };
  escalation_candidates: Array<{
    project_id: string;
    health: "healthy" | "watch" | "critical" | string;
    queue_depth: number;
    pause_active: boolean;
    over_sla: boolean;
    risk_score: number;
    recommended_action: string;
    incident: {
      id: string;
      status: string;
      external_provider: string;
      trigger_health: string;
      ticket_id: string | null;
      ticket_url: string | null;
      opened_at: string | null;
      age_minutes: number | null;
      last_sync_at: string | null;
    };
    ownership: {
      owner_name: string | null;
      owner_contact: string | null;
      oncall_channel: string | null;
      escalation_channel: string | null;
    };
    missing_fields: string[];
  }>;
  ownership_gaps: Array<{
    project_id: string;
    health: "healthy" | "watch" | "critical" | string;
    queue_depth: number;
    incident_open: boolean;
    incident_age_minutes: number | null;
    missing_fields: string[];
    ownership: {
      owner_name: string | null;
      owner_contact: string | null;
      oncall_channel: string | null;
      escalation_channel: string | null;
    };
    gap_score: number;
  }>;
};

type CalibrationQueueIncidentHooksPayload = {
  requested_projects: string[];
  hooks: CalibrationQueueIncidentHook[];
  generated_at: string;
};

type CalibrationQueueIncidentPoliciesPayload = {
  requested_projects: string[];
  policies: CalibrationQueueIncidentPolicy[];
  generated_at: string;
};

type CalibrationQueueIncidentPolicySimulationPayload = {
  status: "ok" | "invalid" | string;
  project_id: string;
  health: "healthy" | "watch" | "critical" | string;
  alert_codes: string[];
  dry_run: boolean;
  generated_at: string;
  matched_policy: CalibrationQueueIncidentPolicy | null;
  secrets: {
    requested: boolean;
    included: boolean;
    hook_access_granted: boolean;
    policy_access_granted: boolean;
  };
  effective_hook: {
    enabled: boolean;
    provider: "webhook" | "pagerduty" | "jira" | string;
    open_webhook_url: string | null;
    resolve_webhook_url: string | null;
    provider_config: Record<string, unknown>;
    provider_config_keys: string[];
    open_on_health: string[];
    auto_resolve: boolean;
    cooldown_minutes: number;
    timeout_sec: number;
  };
  route_trace: {
    matched_policy_id: string | null;
    matched_policy_alert_code: string | null;
    provider_before_policy: "webhook" | "pagerduty" | "jira" | string;
    provider_after_policy: "webhook" | "pagerduty" | "jira" | string;
    candidate_policies: Array<{
      id: string | null;
      alert_code: string;
      enabled: boolean;
      priority: number;
      provider_override: "webhook" | "pagerduty" | "jira" | null | string;
      matched: boolean;
    }>;
  };
  decision: {
    should_open_incident: boolean;
    skip_reason: string | null;
    ticket_side_effects: boolean;
  };
};

type CalibrationQueueIncidentPreflightPreset = {
  id: string | null;
  project_id: string;
  preset_key: string;
  name: string;
  enabled: boolean;
  alert_code: string;
  health: "healthy" | "watch" | "critical" | string;
  additional_alert_codes: string[];
  expected_decision: "open" | "skip" | "invalid_ok" | string;
  required_provider: "webhook" | "pagerduty" | "jira" | null | string;
  run_before_live_sync: boolean;
  severity: "info" | "warning" | "critical" | string;
  strict_mode: boolean;
  metadata: Record<string, unknown>;
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueIncidentPreflightPresetsPayload = {
  requested_projects: string[];
  include_disabled: boolean;
  run_before_live_sync_only: boolean;
  presets: CalibrationQueueIncidentPreflightPreset[];
  generated_at: string;
};

type CalibrationQueueIncidentPreflightRunPayload = {
  requested_projects: string[];
  preset_ids: string[];
  include_disabled: boolean;
  include_run_before_live_sync_only: boolean;
  record_audit: boolean;
  generated_at: string;
  summary: {
    projects_total: number;
    presets_total: number;
    checks_total: number;
    passed: number;
    failed: number;
    alerts_total: number;
    alerts_by_severity: {
      info: number;
      warning: number;
      critical: number;
    };
  };
  project_rollups: Array<{
    project_id: string;
    checks_total: number;
    passed: number;
    failed: number;
    critical_alerts: number;
    warning_alerts: number;
    info_alerts: number;
  }>;
  alerts: Array<{
    preset_id: string;
    project_id: string;
    preset_key: string;
    preset_name: string;
    status: "passed" | "failed" | string;
    fail_reasons: string[];
    recommendation: string | null;
    severity: "info" | "warning" | "critical" | string;
    simulation: {
      status: "ok" | "invalid" | string;
      decision: {
        should_open_incident: boolean;
        skip_reason: string | null;
      };
      provider_after_policy: string | null;
      provider_before_policy: string | null;
      matched_policy_id: string | null;
      matched_policy_alert_code: string | null;
      generated_at: string | null;
    };
  }>;
  results: Array<Record<string, unknown>>;
};

type CalibrationQueueIncidentSyncSchedule = {
  id: string;
  project_id: string;
  name: string;
  enabled: boolean;
  preset: "hourly" | "every_4h" | "daily" | "weekly" | "custom" | string;
  interval_minutes: number;
  window_hours: number;
  batch_size: number;
  sync_limit: number;
  dry_run: boolean;
  force_resolve: boolean;
  preflight_enforcement_mode: "inherit" | "off" | "block" | "pause" | string;
  preflight_pause_hours: number | null;
  preflight_critical_fail_threshold: number | null;
  preflight_include_run_before_live_sync_only: boolean;
  preflight_record_audit: boolean;
  requested_by: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: "ok" | "partial_failure" | "failed" | "skipped" | string | null;
  last_run_summary: Record<string, unknown>;
  updated_by: string;
  created_at: string | null;
  updated_at: string | null;
};

type CalibrationQueueIncidentSyncSchedulesPayload = {
  requested_projects: string[];
  requested_schedule_ids: string[];
  enabled_filter: boolean | null;
  status_filter?: string | null;
  project_contains_filter?: string | null;
  name_contains_filter?: string | null;
  due_only: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc" | string;
  paging?: {
    limit: number;
    offset: number;
    cursor?: string | null;
    next_cursor?: string | null;
    has_more: boolean;
    total: number;
  };
  schedules: CalibrationQueueIncidentSyncSchedule[];
  generated_at: string;
};

type CalibrationQueueIncidentSyncScheduleRunPayload = {
  status: "ok" | "partial_failure" | string;
  requested_projects: string[];
  requested_schedule_ids: string[];
  force_run: boolean;
  skip_due_check: boolean;
  summary: {
    schedules_total: number;
    executed: number;
    ok: number;
    partial_failure: number;
    failed: number;
    skipped: number;
    opened: number;
    resolved: number;
    sync_failed: number;
    noop: number;
    blocked: number;
    paused: number;
  };
  results: Array<{
    schedule_id: string;
    project_id: string;
    name: string;
    status: "ok" | "partial_failure" | "failed" | "skipped" | string;
    error?: string;
    failure_classes?: string[];
    run_actor: string;
    audit_event_id?: number | null;
    sync_generated_at?: string | null;
    sync_summary?: {
      opened: number;
      resolved: number;
      failed: number;
      noop: number;
      blocked: number;
      paused: number;
      projects_total: number;
    };
    sync_trace?: {
      requested_projects?: string[];
      window_hours?: number;
      dry_run?: boolean;
      force_resolve?: boolean;
      preflight_enforcement_mode?: string;
      summary?: Record<string, unknown>;
      results?: Array<Record<string, unknown>>;
      generated_at?: string | null;
    } | null;
    updated_schedule?: CalibrationQueueIncidentSyncSchedule | null;
  }>;
  generated_at: string;
};

type CalibrationQueueIncidentSyncScheduleTimelinePayload = {
  schedule_id: string;
  project_id: string;
  days: number;
  since: string;
  schedule: CalibrationQueueIncidentSyncSchedule;
  summary: {
    runs_total: number;
    ok: number;
    partial_failure: number;
    failed: number;
    skipped: number;
    unknown: number;
    latest_status: string | null;
    latest_run_at: string | null;
  };
  trend: Array<{
    day: string;
    runs: number;
    ok: number;
    partial_failure: number;
    failed: number;
    skipped: number;
    unknown: number;
  }>;
  failure_classes: Array<{
    code: string;
    count: number;
  }>;
  runs: Array<{
    audit_event_id: number;
    project_id: string;
    action: string;
    status: "ok" | "partial_failure" | "failed" | "skipped" | string;
    actor: string;
    reason: string | null;
    created_at: string;
    next_run_at: string | null;
    force_run: boolean;
    skip_due_check: boolean;
    sync_summary: {
      opened: number;
      resolved: number;
      failed: number;
      noop: number;
      blocked: number;
      paused: number;
      projects_total: number;
    };
    error: string | null;
    failure_classes: string[];
  }>;
  generated_at: string;
};

type CalibrationQueueIncidentsPayload = {
  requested_projects: string[];
  status_filter: string | null;
  incidents: CalibrationQueueIncident[];
  generated_at: string;
};

type CalibrationQueueOwnerRollupsPayload = {
  window_hours: number;
  sla_hours: number;
  requested_projects: string[];
  generated_at: string;
  summary: {
    owners_total: number;
    projects_total: number;
    critical_projects: number;
    watch_projects: number;
    open_incidents: number;
    pending_events: number;
    sla_breaches: number;
  };
  owners: Array<{
    owner_key: string;
    owner_name: string;
    oncall_channel: string;
    owner_contact: string | null;
    escalation_channel: string | null;
    projects_total: number;
    health: {
      critical: number;
      watch: number;
      healthy: number;
    };
    queue_depth_total: number;
    queue_depth_avg: number;
    queue_wait_p90_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
    open_incidents: number;
    paused_projects: number;
    governance: {
      events_total: number;
      resolved_events: number;
      pending_events: number;
      sla_breaches: number;
      mttr_minutes: {
        count: number;
        avg: number | null;
        p50: number | null;
        p90: number | null;
      };
      pending_age_minutes: {
        count: number;
        avg: number | null;
        p50: number | null;
        p90: number | null;
        max: number | null;
      };
    };
    projects: Array<{
      project_id: string;
      health: string;
      queue_depth: number;
      queued_wait_p90_minutes: number | null;
      pause_active: boolean;
      incident_open: boolean;
    }>;
  }>;
};

type CalibrationQueueGovernanceDriftPayload = {
  window_hours: number;
  audit_days: number;
  requested_projects: string[];
  generated_at: string;
  summary: {
    projects_total: number;
    ownership_coverage: {
      owner_name_rate: number;
      oncall_channel_rate: number;
      escalation_channel_rate: number;
      missing_owner_name: number;
      missing_oncall_channel: number;
      missing_escalation_channel: number;
    };
    unresolved_pauses: number;
    critical_without_owner: number;
    open_incidents_without_owner: number;
  };
  pause_age_buckets: {
    under_1h: number;
    between_1h_4h: number;
    between_4h_12h: number;
    between_12h_24h: number;
    over_24h: number;
  };
  drift_projects: Array<{
    project_id: string;
    health: string;
    queue_depth: number;
    pause_active: boolean;
    pause_age_minutes: number | null;
    incident_open: boolean;
    ownership: {
      owner_name: string | null;
      oncall_channel: string | null;
      escalation_channel: string | null;
    };
    missing_fields: string[];
    risk_score: number;
  }>;
};

type CalibrationQueueIncidentSloBoardPayload = {
  window_hours: number;
  incident_window_days: number;
  mttr_sla_hours: number;
  mtta_proxy_sla_minutes: number;
  rotation_lag_sla_hours: number;
  secret_max_age_days: number;
  requested_projects: string[];
  generated_at: string;
  summary: {
    projects_total: number;
    open_incidents: number;
    open_incidents_over_mttr_sla: number;
    resolved_incidents_window: number;
    mtta_proxy_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
    mttr_minutes: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
    projects_mtta_over_sla: number;
    projects_mttr_over_sla: number;
    rotation_lag_projects_over_sla: number;
    secret_required_total: number;
    secret_missing_required: number;
    secret_stale_required: number;
    secret_posture: {
      healthy: number;
      watch: number;
      critical: number;
    };
    slo_status: {
      healthy: number;
      watch: number;
      critical: number;
    };
  };
  trends: Array<{
    day: string;
    opened_incidents: number;
    resolved_incidents: number;
    mtta_proxy_minutes_avg: number | null;
    mtta_proxy_minutes_p90: number | null;
    mttr_minutes_avg: number | null;
    mttr_minutes_p90: number | null;
  }>;
  leaderboard: Array<{
    project_id: string;
    health: string;
    queue_depth: number;
    slo_status: string;
    risk_score: number;
    incident: {
      open: boolean;
      external_provider: string;
      open_age_minutes: number | null;
      mtta_proxy_minutes: number | null;
      mtta_proxy_p90_minutes: number | null;
      mttr_last_minutes: number | null;
      mttr_p90_minutes: number | null;
      resolved_incidents_window: number;
    };
    ownership: {
      owner_name: string | null;
      owner_contact: string | null;
      oncall_channel: string | null;
      escalation_channel: string | null;
      updated_at: string | null;
      rotation_lag_hours: number | null;
      rotation_lag_over_sla: boolean;
    };
    secrets: {
      required: number;
      configured: number;
      missing_required: number;
      stale_required: number;
      oldest_age_hours: number | null;
      posture: "healthy" | "watch" | "critical" | string;
      stale_keys: Array<{
        scope: string;
        scope_ref: string;
        provider: string;
        secret_key: string;
        age_hours: number;
      }>;
    };
    slo: {
      mtta_proxy_sla_minutes: number;
      mtta_proxy_value_minutes: number | null;
      mtta_proxy_over_sla: boolean;
      mttr_sla_minutes: number;
      mttr_value_minutes: number | null;
      mttr_over_sla: boolean;
      rotation_lag_sla_hours: number;
      rotation_lag_over_sla: boolean;
      secret_max_age_hours: number;
      secret_missing_required: number;
      secret_stale_required: number;
    };
  }>;
  projects: Array<Record<string, unknown>>;
};

type ScheduleObservabilityItem = {
  schedule_id: string;
  schedule_name: string;
  enabled: boolean;
  preset: string;
  last_run_at: string | null;
  last_status: string | null;
  slo: {
    health: "healthy" | "watch" | "critical" | "unknown" | string;
    success_rate: number;
    alert_rate: number;
    failure_rate: number;
  };
  window: {
    total: number;
    executed: number;
    ok: number;
    alert: number;
    failed: number;
    skipped: number;
    preview: number;
    unknown: number;
  };
  trend: Array<{
    day: string;
    ok: number;
    alert: number;
    failed: number;
    skipped: number;
  }>;
  top_failure_classes: Array<{
    code: string;
    count: number;
  }>;
};

type ScheduleObservabilityPayload = {
  project_id: string;
  days: number;
  since: string;
  schedules: ScheduleObservabilityItem[];
  generated_at: string;
};

type ObservabilityCompareProject = {
  project_id: string;
  schedules_total: number;
  enabled_schedules: number;
  window: {
    executed: number;
    ok: number;
    alert: number;
    failed: number;
    skipped: number;
    preview: number;
    unknown: number;
  };
  slo: {
    health: "healthy" | "watch" | "critical" | "unknown" | string;
    success_rate: number;
    alert_rate: number;
    failure_rate: number;
    drift_index: number;
  };
  last_run_at: string | null;
  top_failure_classes: Array<{ code: string; count: number }>;
};

type ObservabilityComparePayload = {
  days: number;
  since: string;
  requested_projects: string[];
  projects: ObservabilityCompareProject[];
  generated_at: string;
};

type ObservabilityCompareDrilldownPayload = {
  project_id: string;
  days: number;
  since: string | null;
  rank_position: number | null;
  total_projects: number;
  selected_project: ObservabilityCompareProject | null;
  neighbors: ObservabilityCompareProject[];
  schedule_observability: ScheduleObservabilityPayload;
  generated_at: string;
};

type SchedulePreset = {
  preset: "nightly" | "weekly";
  interval_hours: number;
  lookback_days: number;
  limit_rows: number;
  holdout_ratio: number;
  top_k: number;
  weights: string;
  confidences: string;
  score_thresholds: string;
  label: string;
  description: string;
};

type ScheduleFormState = {
  name: string;
  enabled: boolean;
  preset: "nightly" | "weekly";
  interval_hours: number | null;
  lookback_days: number;
  limit_rows: number;
  holdout_ratio: number;
  split_seed: string;
  weights: string;
  confidences: string;
  score_thresholds: string;
  top_k: number;
  allow_guardrail_fail: boolean;
  snapshot_note: string;
};

const PRESET_CONFIGS: Record<"nightly" | "weekly", SchedulePreset> = {
  nightly: {
    preset: "nightly",
    interval_hours: 24,
    lookback_days: 60,
    limit_rows: 20000,
    holdout_ratio: 0.3,
    top_k: 5,
    weights: "0.2,0.3,0.35,0.4,0.5",
    confidences: "0.6,0.65,0.7,0.75",
    score_thresholds: "0.55,0.62,0.7,0.78",
    label: "Nightly",
    description: "Daily calibration for fast drift detection.",
  },
  weekly: {
    preset: "weekly",
    interval_hours: 168,
    lookback_days: 90,
    limit_rows: 50000,
    holdout_ratio: 0.35,
    top_k: 7,
    weights: "0.2,0.3,0.4,0.5,0.6",
    confidences: "0.6,0.7,0.75,0.8",
    score_thresholds: "0.58,0.66,0.74,0.82",
    label: "Weekly",
    description: "Heavier sweep for slower projects or stable environments.",
  },
};

const DEFAULT_FORM: ScheduleFormState = {
  name: "",
  enabled: true,
  preset: "nightly",
  interval_hours: null,
  lookback_days: PRESET_CONFIGS.nightly.lookback_days,
  limit_rows: PRESET_CONFIGS.nightly.limit_rows,
  holdout_ratio: PRESET_CONFIGS.nightly.holdout_ratio,
  split_seed: "synapse-gatekeeper-prod-holdout-v1",
  weights: PRESET_CONFIGS.nightly.weights,
  confidences: PRESET_CONFIGS.nightly.confidences,
  score_thresholds: PRESET_CONFIGS.nightly.score_thresholds,
  top_k: PRESET_CONFIGS.nightly.top_k,
  allow_guardrail_fail: false,
  snapshot_note: "",
};

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

function asNumber(value: number | string, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function runStatusColor(status: string | null | undefined): string {
  if (status === "ok") return "teal";
  if (status === "alert") return "orange";
  if (status === "partial_failure") return "yellow";
  if (status === "preview") return "blue";
  if (status === "failed") return "red";
  return "gray";
}

function operationResultColor(status: string | null | undefined): string {
  if (status === "queued") return "blue";
  if (status === "running") return "cyan";
  if (status === "cancel_requested") return "orange";
  if (status === "canceled") return "gray";
  if (status === "succeeded") return "teal";
  if (status === "would_run") return "blue";
  if (status === "executed") return "teal";
  if (status === "skipped_not_due") return "gray";
  if (status === "skipped_disabled") return "gray";
  if (status === "partial_failure") return "yellow";
  if (status === "alert") return "orange";
  if (status === "failed") return "red";
  return "gray";
}

function healthColor(health: string | null | undefined): string {
  if (health === "healthy") return "teal";
  if (health === "watch") return "yellow";
  if (health === "critical") return "red";
  return "gray";
}

function normalizeIncidentPreflightEnforcementMode(value: string | null | undefined): "off" | "block" | "pause" {
  const normalized = String(value || "off").trim().toLowerCase();
  if (normalized === "block" || normalized === "pause") {
    return normalized;
  }
  return "off";
}

function incidentPreflightEnforcementColor(mode: "off" | "block" | "pause"): string {
  if (mode === "block") return "red";
  if (mode === "pause") return "orange";
  return "gray";
}

const INCIDENT_SYNC_SCHEDULE_PRESET_INTERVALS: Record<string, number> = {
  hourly: 60,
  every_4h: 240,
  daily: 1440,
  weekly: 10080,
};
const INCIDENT_SYNC_FLEET_VIEW_STORAGE_KEY = "synapse.queueIncidentSyncFleetView.v1";

function incidentSyncScheduleStatusColor(status: string | null | undefined): string {
  if (status === "ok") return "teal";
  if (status === "partial_failure") return "yellow";
  if (status === "skipped") return "gray";
  if (status === "failed") return "red";
  return "gray";
}

function incidentRiskColor(score: number | null | undefined): string {
  const value = Number(score || 0);
  if (value >= 10) return "red";
  if (value >= 7) return "orange";
  if (value >= 4) return "yellow";
  return "teal";
}

function asPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function makeOperationToken(): string {
  const maybeCrypto = globalThis.crypto as Crypto | undefined;
  if (maybeCrypto && typeof maybeCrypto.randomUUID === "function") {
    return maybeCrypto.randomUUID();
  }
  return `op-${Date.now()}`;
}

function parseThresholdCsv(raw: string): { values: number[]; errors: string[] } {
  const text = raw.trim();
  if (!text) {
    return { values: [], errors: [] };
  }
  const tokens = text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const values: number[] = [];
  const errors: string[] = [];
  if (tokens.length > 40) {
    errors.push("Maximum 40 values allowed.");
  }
  for (const token of tokens) {
    const parsed = Number(token);
    if (!Number.isFinite(parsed)) {
      errors.push(`Invalid number: ${token}`);
      continue;
    }
    if (parsed < 0 || parsed > 1) {
      errors.push(`Value out of [0,1]: ${token}`);
      continue;
    }
    values.push(Number(parsed.toFixed(4)));
  }
  for (let idx = 1; idx < values.length; idx += 1) {
    if (values[idx] < values[idx - 1]) {
      errors.push("Values should be ascending to keep grid search predictable.");
      break;
    }
  }
  return { values, errors };
}

function validateForm(form: ScheduleFormState): string[] {
  const errors: string[] = [];
  if (!form.name.trim()) {
    errors.push("Schedule name is required.");
  }
  if (form.interval_hours != null && form.interval_hours < 1) {
    errors.push("interval_hours must be >= 1.");
  }
  if (form.lookback_days < 1 || form.lookback_days > 365) {
    errors.push("lookback_days must be in [1, 365].");
  }
  if (form.limit_rows < 100 || form.limit_rows > 200000) {
    errors.push("limit_rows must be in [100, 200000].");
  }
  if (!(form.holdout_ratio > 0 && form.holdout_ratio < 1)) {
    errors.push("holdout_ratio must be between 0 and 1.");
  }
  if (form.top_k < 1 || form.top_k > 20) {
    errors.push("top_k must be in [1, 20].");
  }
  if (!form.split_seed.trim()) {
    errors.push("split_seed is required.");
  }
  const weights = parseThresholdCsv(form.weights);
  const confidences = parseThresholdCsv(form.confidences);
  const scoreThresholds = parseThresholdCsv(form.score_thresholds);
  errors.push(...weights.errors.map((item) => `weights: ${item}`));
  errors.push(...confidences.errors.map((item) => `confidences: ${item}`));
  errors.push(...scoreThresholds.errors.map((item) => `score_thresholds: ${item}`));
  return errors;
}

async function apiFetch<T>(
  apiUrl: string,
  path: string,
  options?: {
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: Record<string, unknown>;
  },
): Promise<T> {
  const root = apiUrl.replace(/\/+$/, "");
  const response = await fetch(`${root}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
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

export default function GatekeeperSchedulePanel({ apiUrl, projectId, reviewer, onRefresh }: GatekeeperSchedulePanelProps) {
  const [schedules, setSchedules] = useState<GatekeeperCalibrationSchedule[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [deletingScheduleId, setDeletingScheduleId] = useState<string | null>(null);
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null);
  const [operationLoading, setOperationLoading] = useState(false);
  const [operationExecuting, setOperationExecuting] = useState(false);
  const [skipDueCheckForOps, setSkipDueCheckForOps] = useState(false);
  const [operationResult, setOperationResult] = useState<CalibrationOperationPayload | null>(null);
  const [operationRuns, setOperationRuns] = useState<CalibrationOperationRun[]>([]);
  const [loadingOperationRuns, setLoadingOperationRuns] = useState(false);
  const [queueThroughput, setQueueThroughput] = useState<CalibrationQueueThroughput | null>(null);
  const [loadingQueueThroughput, setLoadingQueueThroughput] = useState(false);
  const [queueControlsBusy, setQueueControlsBusy] = useState(false);
  const [queueCompareProjectIds, setQueueCompareProjectIds] = useState("");
  const [loadingQueueCompare, setLoadingQueueCompare] = useState(false);
  const [queueThroughputCompare, setQueueThroughputCompare] = useState<CalibrationQueueThroughputCompare | null>(null);
  const [loadingQueueAutoscaling, setLoadingQueueAutoscaling] = useState(false);
  const [queueAutoscaling, setQueueAutoscaling] = useState<CalibrationQueueAutoscalingPayload | null>(null);
  const [loadingQueueGovernanceDigest, setLoadingQueueGovernanceDigest] = useState(false);
  const [queueGovernanceDigest, setQueueGovernanceDigest] = useState<CalibrationQueueGovernanceDigest | null>(null);
  const [loadingQueueIncidentEscalationDigest, setLoadingQueueIncidentEscalationDigest] = useState(false);
  const [queueIncidentEscalationDigest, setQueueIncidentEscalationDigest] =
    useState<CalibrationQueueIncidentEscalationDigest | null>(null);
  const [loadingQueueAudit, setLoadingQueueAudit] = useState(false);
  const [queueAudit, setQueueAudit] = useState<CalibrationQueueAuditPayload | null>(null);
  const [queueAuditActionBusyId, setQueueAuditActionBusyId] = useState<string | null>(null);
  const [queueAuditFocusEventId, setQueueAuditFocusEventId] = useState<number | null>(null);
  const [loadingQueueOwnerRollups, setLoadingQueueOwnerRollups] = useState(false);
  const [queueOwnerRollups, setQueueOwnerRollups] = useState<CalibrationQueueOwnerRollupsPayload | null>(null);
  const [loadingQueueGovernanceDrift, setLoadingQueueGovernanceDrift] = useState(false);
  const [queueGovernanceDrift, setQueueGovernanceDrift] = useState<CalibrationQueueGovernanceDriftPayload | null>(null);
  const [loadingQueueIncidentSloBoard, setLoadingQueueIncidentSloBoard] = useState(false);
  const [queueIncidentSloBoard, setQueueIncidentSloBoard] = useState<CalibrationQueueIncidentSloBoardPayload | null>(null);
  const [queueBulkBusy, setQueueBulkBusy] = useState(false);
  const [queueExportBusy, setQueueExportBusy] = useState(false);
  const [queueIncidentHookBusy, setQueueIncidentHookBusy] = useState(false);
  const [queueIncidentPolicyBusy, setQueueIncidentPolicyBusy] = useState(false);
  const [queueIncidentSyncBusy, setQueueIncidentSyncBusy] = useState(false);
  const [loadingQueueIncidentSyncSchedules, setLoadingQueueIncidentSyncSchedules] = useState(false);
  const [queueIncidentSyncSchedules, setQueueIncidentSyncSchedules] =
    useState<CalibrationQueueIncidentSyncSchedulesPayload | null>(null);
  const [queueIncidentSyncScheduleBusy, setQueueIncidentSyncScheduleBusy] = useState(false);
  const [queueIncidentSyncScheduleDeleteBusyId, setQueueIncidentSyncScheduleDeleteBusyId] = useState<string | null>(null);
  const [queueIncidentSyncScheduleRunBusy, setQueueIncidentSyncScheduleRunBusy] = useState(false);
  const [queueIncidentSyncScheduleRunResult, setQueueIncidentSyncScheduleRunResult] =
    useState<CalibrationQueueIncidentSyncScheduleRunPayload | null>(null);
  const [queueIncidentSyncScheduleRunSelectedScheduleId, setQueueIncidentSyncScheduleRunSelectedScheduleId] = useState<string | null>(null);
  const [loadingQueueIncidentSyncScheduleTimeline, setLoadingQueueIncidentSyncScheduleTimeline] = useState(false);
  const [queueIncidentSyncScheduleTimeline, setQueueIncidentSyncScheduleTimeline] =
    useState<CalibrationQueueIncidentSyncScheduleTimelinePayload | null>(null);
  const [queueIncidentSyncScheduleTimelineScheduleId, setQueueIncidentSyncScheduleTimelineScheduleId] = useState<string | null>(
    null,
  );
  const [queueIncidentSyncScheduleName, setQueueIncidentSyncScheduleName] = useState("");
  const [queueIncidentSyncScheduleEnabled, setQueueIncidentSyncScheduleEnabled] = useState(true);
  const [queueIncidentSyncSchedulePreset, setQueueIncidentSyncSchedulePreset] = useState<
    "hourly" | "every_4h" | "daily" | "weekly" | "custom"
  >("every_4h");
  const [queueIncidentSyncScheduleIntervalMinutes, setQueueIncidentSyncScheduleIntervalMinutes] = useState(240);
  const [queueIncidentSyncScheduleWindowHours, setQueueIncidentSyncScheduleWindowHours] = useState(24);
  const [queueIncidentSyncScheduleBatchSize, setQueueIncidentSyncScheduleBatchSize] = useState(50);
  const [queueIncidentSyncScheduleLimit, setQueueIncidentSyncScheduleLimit] = useState(50);
  const [queueIncidentSyncScheduleDryRun, setQueueIncidentSyncScheduleDryRun] = useState(false);
  const [queueIncidentSyncScheduleForceResolve, setQueueIncidentSyncScheduleForceResolve] = useState(false);
  const [queueIncidentSyncSchedulePreflightMode, setQueueIncidentSyncSchedulePreflightMode] = useState<
    "inherit" | "off" | "block" | "pause"
  >("inherit");
  const [queueIncidentSyncSchedulePreflightPauseHours, setQueueIncidentSyncSchedulePreflightPauseHours] = useState(4);
  const [queueIncidentSyncSchedulePreflightCriticalThreshold, setQueueIncidentSyncSchedulePreflightCriticalThreshold] = useState(1);
  const [queueIncidentSyncSchedulePreflightRunBeforeOnly, setQueueIncidentSyncSchedulePreflightRunBeforeOnly] = useState(true);
  const [queueIncidentSyncSchedulePreflightRecordAudit, setQueueIncidentSyncSchedulePreflightRecordAudit] = useState(true);
  const [queueIncidentSyncScheduleNextRunAt, setQueueIncidentSyncScheduleNextRunAt] = useState("");
  const [queueIncidentSyncScheduleRunForce, setQueueIncidentSyncScheduleRunForce] = useState(false);
  const [queueIncidentSyncScheduleRunSkipDue, setQueueIncidentSyncScheduleRunSkipDue] = useState(false);
  const [queueIncidentSyncScheduleRunSelectedOnly, setQueueIncidentSyncScheduleRunSelectedOnly] = useState(true);
  const [queueIncidentSyncScheduleFleetProjectFilter, setQueueIncidentSyncScheduleFleetProjectFilter] = useState("");
  const [queueIncidentSyncScheduleFleetNameFilter, setQueueIncidentSyncScheduleFleetNameFilter] = useState("");
  const [queueIncidentSyncScheduleFleetStatusFilter, setQueueIncidentSyncScheduleFleetStatusFilter] = useState<
    "all" | "ok" | "partial_failure" | "failed" | "skipped" | "never"
  >("all");
  const [queueIncidentSyncScheduleFleetEnabledFilter, setQueueIncidentSyncScheduleFleetEnabledFilter] = useState<
    "all" | "enabled" | "disabled"
  >("all");
  const [queueIncidentSyncScheduleFleetDueOnly, setQueueIncidentSyncScheduleFleetDueOnly] = useState(false);
  const [queueIncidentSyncScheduleFleetCompactMode, setQueueIncidentSyncScheduleFleetCompactMode] = useState(false);
  const [queueIncidentSyncScheduleFleetPageSize, setQueueIncidentSyncScheduleFleetPageSize] = useState(25);
  const [queueIncidentSyncScheduleFleetPage, setQueueIncidentSyncScheduleFleetPage] = useState(1);
  const [queueIncidentSyncScheduleFleetSortBy, setQueueIncidentSyncScheduleFleetSortBy] = useState<
    "next_run_at" | "updated_at" | "last_run_at" | "name" | "project_id" | "status"
  >("next_run_at");
  const [queueIncidentSyncScheduleFleetSortDir, setQueueIncidentSyncScheduleFleetSortDir] = useState<"asc" | "desc">("asc");
  const [loadingQueueIncidentSyncScheduleFleet, setLoadingQueueIncidentSyncScheduleFleet] = useState(false);
  const [queueIncidentSyncScheduleFleetPayload, setQueueIncidentSyncScheduleFleetPayload] =
    useState<CalibrationQueueIncidentSyncSchedulesPayload | null>(null);
  const [loadingQueueIncidentHooks, setLoadingQueueIncidentHooks] = useState(false);
  const [queueIncidentHooks, setQueueIncidentHooks] = useState<CalibrationQueueIncidentHooksPayload | null>(null);
  const [loadingQueueIncidentPolicies, setLoadingQueueIncidentPolicies] = useState(false);
  const [queueIncidentPolicies, setQueueIncidentPolicies] = useState<CalibrationQueueIncidentPoliciesPayload | null>(null);
  const [loadingQueueIncidentPreflightPresets, setLoadingQueueIncidentPreflightPresets] = useState(false);
  const [queueIncidentPreflightPresets, setQueueIncidentPreflightPresets] =
    useState<CalibrationQueueIncidentPreflightPresetsPayload | null>(null);
  const [queueIncidentPreflightPresetBusy, setQueueIncidentPreflightPresetBusy] = useState(false);
  const [queueIncidentPreflightRunBusy, setQueueIncidentPreflightRunBusy] = useState(false);
  const [queueIncidentPreflightRunResult, setQueueIncidentPreflightRunResult] =
    useState<CalibrationQueueIncidentPreflightRunPayload | null>(null);
  const [loadingQueueIncidents, setLoadingQueueIncidents] = useState(false);
  const [queueIncidents, setQueueIncidents] = useState<CalibrationQueueIncidentsPayload | null>(null);
  const [queueRecommendationBusyProjectId, setQueueRecommendationBusyProjectId] = useState<string | null>(null);
  const [queueWebhookUrl, setQueueWebhookUrl] = useState("");
  const [queueOwnershipBusy, setQueueOwnershipBusy] = useState(false);
  const [queueOwnerProjectId, setQueueOwnerProjectId] = useState("");
  const [queueOwnerName, setQueueOwnerName] = useState("");
  const [queueOwnerContact, setQueueOwnerContact] = useState("");
  const [queueOncallChannel, setQueueOncallChannel] = useState("");
  const [queueEscalationChannel, setQueueEscalationChannel] = useState("");
  const [queueIncidentProjectId, setQueueIncidentProjectId] = useState("");
  const [queueIncidentHookEnabled, setQueueIncidentHookEnabled] = useState(false);
  const [queueIncidentProvider, setQueueIncidentProvider] = useState<"webhook" | "pagerduty" | "jira" | string>("webhook");
  const [queueIncidentOpenWebhookUrl, setQueueIncidentOpenWebhookUrl] = useState("");
  const [queueIncidentResolveWebhookUrl, setQueueIncidentResolveWebhookUrl] = useState("");
  const [queueIncidentWebhookHeadersJson, setQueueIncidentWebhookHeadersJson] = useState("{}");
  const [queueIncidentPagerdutyRoutingKey, setQueueIncidentPagerdutyRoutingKey] = useState("");
  const [queueIncidentPagerdutyDedupPrefix, setQueueIncidentPagerdutyDedupPrefix] = useState("synapse-queue");
  const [queueIncidentJiraBaseUrl, setQueueIncidentJiraBaseUrl] = useState("");
  const [queueIncidentJiraProjectKey, setQueueIncidentJiraProjectKey] = useState("");
  const [queueIncidentJiraAuthMode, setQueueIncidentJiraAuthMode] = useState<"basic" | "bearer">("basic");
  const [queueIncidentJiraEmail, setQueueIncidentJiraEmail] = useState("");
  const [queueIncidentJiraApiToken, setQueueIncidentJiraApiToken] = useState("");
  const [queueIncidentJiraIssueType, setQueueIncidentJiraIssueType] = useState("Incident");
  const [queueIncidentJiraResolveTransitionId, setQueueIncidentJiraResolveTransitionId] = useState("");
  const [queueIncidentPolicyAlertCode, setQueueIncidentPolicyAlertCode] = useState("");
  const [queueIncidentPolicyEnabled, setQueueIncidentPolicyEnabled] = useState(true);
  const [queueIncidentPolicyPriority, setQueueIncidentPolicyPriority] = useState(100);
  const [queueIncidentPolicyProviderOverride, setQueueIncidentPolicyProviderOverride] = useState<
    "inherit" | "webhook" | "pagerduty" | "jira"
  >("inherit");
  const [queueIncidentPolicyOpenWebhookUrl, setQueueIncidentPolicyOpenWebhookUrl] = useState("");
  const [queueIncidentPolicyResolveWebhookUrl, setQueueIncidentPolicyResolveWebhookUrl] = useState("");
  const [queueIncidentPolicySeverityCsv, setQueueIncidentPolicySeverityCsv] = useState("critical=critical,watch=warning");
  const [queueIncidentPolicyOpenOnHealthCsv, setQueueIncidentPolicyOpenOnHealthCsv] = useState("");
  const [queueIncidentPolicyConfigOverrideJson, setQueueIncidentPolicyConfigOverrideJson] = useState("{}");
  const [queueIncidentPolicySimulationBusy, setQueueIncidentPolicySimulationBusy] = useState(false);
  const [queueIncidentPolicySimulationHealth, setQueueIncidentPolicySimulationHealth] = useState<"healthy" | "watch" | "critical">(
    "critical",
  );
  const [queueIncidentPolicySimulationAdditionalAlertCodesCsv, setQueueIncidentPolicySimulationAdditionalAlertCodesCsv] =
    useState("");
  const [queueIncidentPolicySimulationResult, setQueueIncidentPolicySimulationResult] =
    useState<CalibrationQueueIncidentPolicySimulationPayload | null>(null);
  const [queueIncidentPreflightPresetKey, setQueueIncidentPreflightPresetKey] = useState("");
  const [queueIncidentPreflightPresetName, setQueueIncidentPreflightPresetName] = useState("");
  const [queueIncidentPreflightEnabled, setQueueIncidentPreflightEnabled] = useState(true);
  const [queueIncidentPreflightAlertCode, setQueueIncidentPreflightAlertCode] = useState("queue_depth_critical");
  const [queueIncidentPreflightHealth, setQueueIncidentPreflightHealth] = useState<"healthy" | "watch" | "critical">("critical");
  const [queueIncidentPreflightAdditionalAlertCodesCsv, setQueueIncidentPreflightAdditionalAlertCodesCsv] = useState("");
  const [queueIncidentPreflightExpectedDecision, setQueueIncidentPreflightExpectedDecision] =
    useState<"open" | "skip" | "invalid_ok">("open");
  const [queueIncidentPreflightRequiredProvider, setQueueIncidentPreflightRequiredProvider] = useState<
    "inherit" | "webhook" | "pagerduty" | "jira"
  >("inherit");
  const [queueIncidentPreflightRunBeforeLiveSync, setQueueIncidentPreflightRunBeforeLiveSync] = useState(true);
  const [queueIncidentPreflightSeverity, setQueueIncidentPreflightSeverity] = useState<"info" | "warning" | "critical">("warning");
  const [queueIncidentPreflightStrictMode, setQueueIncidentPreflightStrictMode] = useState(true);
  const [queueIncidentPreflightIncludeDisabled, setQueueIncidentPreflightIncludeDisabled] = useState(false);
  const [queueIncidentPreflightRunBeforeSyncOnly, setQueueIncidentPreflightRunBeforeSyncOnly] = useState(true);
  const [queueIncidentPreflightRecordAudit, setQueueIncidentPreflightRecordAudit] = useState(true);
  const [queueIncidentSyncEnforcementBusy, setQueueIncidentSyncEnforcementBusy] = useState(false);
  const [queueIncidentSyncEnforcementMode, setQueueIncidentSyncEnforcementMode] = useState<"off" | "block" | "pause">("off");
  const [queueIncidentSyncEnforcementPauseHours, setQueueIncidentSyncEnforcementPauseHours] = useState(4);
  const [queueIncidentSyncEnforcementCriticalThreshold, setQueueIncidentSyncEnforcementCriticalThreshold] = useState(1);
  const [queueIncidentOpenOnHealthCsv, setQueueIncidentOpenOnHealthCsv] = useState("critical");
  const [queueIncidentAutoResolve, setQueueIncidentAutoResolve] = useState(true);
  const [queueIncidentCooldownMinutes, setQueueIncidentCooldownMinutes] = useState(30);
  const [queueIncidentTimeoutSec, setQueueIncidentTimeoutSec] = useState(10);
  const [queuePauseHours, setQueuePauseHours] = useState(2);
  const [queuePauseReason, setQueuePauseReason] = useState("");
  const [queueLagSlaMinutes, setQueueLagSlaMinutes] = useState(20);
  const [queueDepthWarn, setQueueDepthWarn] = useState(12);
  const [selectedOperationRunId, setSelectedOperationRunId] = useState<string | null>(null);
  const [selectedOperationRun, setSelectedOperationRun] = useState<CalibrationOperationRun | null>(null);
  const [operationEvents, setOperationEvents] = useState<CalibrationOperationEvent[]>([]);
  const [operationEventsCursor, setOperationEventsCursor] = useState(0);
  const operationEventsCursorRef = useRef(0);
  const queueAuditSectionRef = useRef<HTMLDivElement | null>(null);
  const [queueSseEnabled, setQueueSseEnabled] = useState(false);
  const [queueSseStatus, setQueueSseStatus] = useState<"idle" | "connecting" | "connected" | "fallback">("idle");
  const [operationActionLoading, setOperationActionLoading] = useState<string | null>(null);
  const [operationToken, setOperationToken] = useState(makeOperationToken);
  const [operationConfirmed, setOperationConfirmed] = useState(false);
  const [confirmationPhrase, setConfirmationPhrase] = useState("");
  const [observabilityDays, setObservabilityDays] = useState(30);
  const [loadingObservability, setLoadingObservability] = useState(false);
  const [observability, setObservability] = useState<ScheduleObservabilityPayload | null>(null);
  const [compareProjectIds, setCompareProjectIds] = useState("");
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [observabilityCompare, setObservabilityCompare] = useState<ObservabilityComparePayload | null>(null);
  const [selectedCompareProjectId, setSelectedCompareProjectId] = useState<string | null>(null);
  const [loadingCompareDrilldown, setLoadingCompareDrilldown] = useState(false);
  const [observabilityCompareDrilldown, setObservabilityCompareDrilldown] =
    useState<ObservabilityCompareDrilldownPayload | null>(null);
  const [form, setForm] = useState<ScheduleFormState>(DEFAULT_FORM);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const raw = window.localStorage.getItem(INCIDENT_SYNC_FLEET_VIEW_STORAGE_KEY);
      if (!raw) {
        return;
      }
      const payload = JSON.parse(raw) as Record<string, unknown>;
      const projectFilter = String(payload.project_filter || "").trim();
      const nameFilter = String(payload.name_filter || "").trim();
      const statusFilter = String(payload.status_filter || "").trim().toLowerCase();
      const enabledFilter = String(payload.enabled_filter || "").trim().toLowerCase();
      const dueOnly = Boolean(payload.due_only);
      const compactMode = Boolean(payload.compact_mode);
      const pageSize = Math.max(10, Math.min(200, Number(payload.page_size || 25)));
      const sortBy = String(payload.sort_by || "").trim().toLowerCase();
      const sortDir = String(payload.sort_dir || "").trim().toLowerCase();
      if (projectFilter) {
        setQueueIncidentSyncScheduleFleetProjectFilter(projectFilter.slice(0, 256));
      }
      if (nameFilter) {
        setQueueIncidentSyncScheduleFleetNameFilter(nameFilter.slice(0, 256));
      }
      if (["ok", "partial_failure", "failed", "skipped", "never"].includes(statusFilter)) {
        setQueueIncidentSyncScheduleFleetStatusFilter(statusFilter as "ok" | "partial_failure" | "failed" | "skipped" | "never");
      }
      if (enabledFilter === "enabled" || enabledFilter === "disabled") {
        setQueueIncidentSyncScheduleFleetEnabledFilter(enabledFilter);
      }
      setQueueIncidentSyncScheduleFleetDueOnly(dueOnly);
      setQueueIncidentSyncScheduleFleetCompactMode(compactMode);
      setQueueIncidentSyncScheduleFleetPageSize(pageSize);
      if (
        sortBy === "next_run_at" ||
        sortBy === "updated_at" ||
        sortBy === "last_run_at" ||
        sortBy === "name" ||
        sortBy === "project_id" ||
        sortBy === "status"
      ) {
        setQueueIncidentSyncScheduleFleetSortBy(sortBy);
      }
      if (sortDir === "asc" || sortDir === "desc") {
        setQueueIncidentSyncScheduleFleetSortDir(sortDir);
      }
    } catch {
      return;
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const payload = {
      project_filter: queueIncidentSyncScheduleFleetProjectFilter.trim(),
      name_filter: queueIncidentSyncScheduleFleetNameFilter.trim(),
      status_filter: queueIncidentSyncScheduleFleetStatusFilter,
      enabled_filter: queueIncidentSyncScheduleFleetEnabledFilter,
      due_only: queueIncidentSyncScheduleFleetDueOnly,
      compact_mode: queueIncidentSyncScheduleFleetCompactMode,
      page_size: queueIncidentSyncScheduleFleetPageSize,
      sort_by: queueIncidentSyncScheduleFleetSortBy,
      sort_dir: queueIncidentSyncScheduleFleetSortDir,
    };
    try {
      window.localStorage.setItem(INCIDENT_SYNC_FLEET_VIEW_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      return;
    }
  }, [
    queueIncidentSyncScheduleFleetCompactMode,
    queueIncidentSyncScheduleFleetDueOnly,
    queueIncidentSyncScheduleFleetEnabledFilter,
    queueIncidentSyncScheduleFleetNameFilter,
    queueIncidentSyncScheduleFleetPageSize,
    queueIncidentSyncScheduleFleetProjectFilter,
    queueIncidentSyncScheduleFleetSortBy,
    queueIncidentSyncScheduleFleetSortDir,
    queueIncidentSyncScheduleFleetStatusFilter,
  ]);

  const loadSchedules = useCallback(async () => {
    if (!projectId.trim()) {
      setSchedules([]);
      return;
    }
    setLoadingSchedules(true);
    try {
      const payload = await apiFetch<{ schedules: GatekeeperCalibrationSchedule[] }>(
        apiUrl,
        `/v1/gatekeeper/calibration/schedules?project_id=${encodeURIComponent(projectId)}&limit=200`,
      );
      setSchedules(payload.schedules ?? []);
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Schedule list unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
      setSchedules([]);
    } finally {
      setLoadingSchedules(false);
    }
  }, [apiUrl, projectId]);

  useEffect(() => {
    void loadSchedules();
  }, [loadSchedules]);

  const loadOperationRuns = useCallback(
    async (silent = false) => {
      if (!projectId.trim()) {
        setOperationRuns([]);
        setSelectedOperationRun(null);
        setSelectedOperationRunId(null);
        setOperationEvents([]);
        setOperationEventsCursor(0);
        return;
      }
      if (!silent) {
        setLoadingOperationRuns(true);
      }
      try {
        const payload = await apiFetch<{ project_id: string; runs: CalibrationOperationRun[] }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/runs?project_id=${encodeURIComponent(projectId)}&limit=40`,
        );
        const rows = Array.isArray(payload.runs) ? payload.runs : [];
        setOperationRuns(rows);
        if (rows.length > 0) {
          setSelectedOperationRunId((current) => current ?? rows[0].id);
        } else {
          setSelectedOperationRunId(null);
          setSelectedOperationRun(null);
          setOperationEvents([]);
          setOperationEventsCursor(0);
        }
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Operation queue unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      } finally {
        if (!silent) {
          setLoadingOperationRuns(false);
        }
      }
    },
    [apiUrl, projectId],
  );

  const loadQueueThroughput = useCallback(
    async (silent = false) => {
      if (!projectId.trim()) {
        setQueueThroughput(null);
        return;
      }
      if (!silent) {
        setLoadingQueueThroughput(true);
      }
      try {
        const payload = await apiFetch<CalibrationQueueThroughput>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput?project_id=${encodeURIComponent(projectId)}&window_hours=24`,
        );
        setQueueThroughput(payload);
        if (!silent && payload?.control) {
          setQueueLagSlaMinutes(Math.max(1, Math.min(1440, Number(payload.control.worker_lag_sla_minutes || 20))));
          setQueueDepthWarn(Math.max(1, Math.min(50000, Number(payload.control.queue_depth_warn || 12))));
          const enforcementModeRaw = String(payload.control.incident_preflight_enforcement_mode || "off").trim().toLowerCase();
          setQueueIncidentSyncEnforcementMode(
            enforcementModeRaw === "block" || enforcementModeRaw === "pause" ? enforcementModeRaw : "off",
          );
          setQueueIncidentSyncEnforcementPauseHours(
            Math.max(1, Math.min(168, Number(payload.control.incident_preflight_pause_hours || 4))),
          );
          setQueueIncidentSyncEnforcementCriticalThreshold(
            Math.max(1, Math.min(100, Number(payload.control.incident_preflight_critical_fail_threshold || 1))),
          );
        }
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Queue throughput unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueThroughput(null);
      } finally {
        if (!silent) {
          setLoadingQueueThroughput(false);
        }
      }
    },
    [apiUrl, projectId],
  );

  const loadQueueThroughputCompare = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueCompare(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          limit: "30",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        }
        const payload = await apiFetch<CalibrationQueueThroughputCompare>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput/compare?${query.toString()}`,
        );
        setQueueThroughputCompare(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Queue command center unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueThroughputCompare(null);
      } finally {
        if (!silent) {
          setLoadingQueueCompare(false);
        }
      }
    },
    [apiUrl, queueCompareProjectIds],
  );

  const loadQueueAutoscaling = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueAutoscaling(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          history_hours: "72",
          limit: "30",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueAutoscalingPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput/recommendations?${query.toString()}`,
        );
        setQueueAutoscaling(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Autoscaling recommendations unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueAutoscaling(null);
      } finally {
        if (!silent) {
          setLoadingQueueAutoscaling(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueGovernanceDigest = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueGovernanceDigest(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          audit_days: "7",
          limit: "30",
          top_n: "5",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueGovernanceDigest>(
          apiUrl,
          `/v1/intelligence/queue/governance_digest?${query.toString()}`,
        );
        setQueueGovernanceDigest(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Queue governance digest unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueGovernanceDigest(null);
      } finally {
        if (!silent) {
          setLoadingQueueGovernanceDigest(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidentEscalationDigest = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentEscalationDigest(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          incident_sla_hours: "24",
          limit: "30",
          top_n: "10",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentEscalationDigest>(
          apiUrl,
          `/v1/intelligence/queue/incident_escalation_digest?${query.toString()}`,
        );
        setQueueIncidentEscalationDigest(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident escalation digest unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentEscalationDigest(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentEscalationDigest(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueOwnerRollups = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueOwnerRollups(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          sla_hours: "24",
          limit: "50",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueOwnerRollupsPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput/owners?${query.toString()}`,
        );
        setQueueOwnerRollups(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Owner rollups unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueOwnerRollups(null);
      } finally {
        if (!silent) {
          setLoadingQueueOwnerRollups(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueGovernanceDrift = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueGovernanceDrift(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          audit_days: "7",
          limit: "50",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueGovernanceDriftPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/governance/drift?${query.toString()}`,
        );
        setQueueGovernanceDrift(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Governance drift unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueGovernanceDrift(null);
      } finally {
        if (!silent) {
          setLoadingQueueGovernanceDrift(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidentSloBoard = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentSloBoard(true);
      }
      try {
        const query = new URLSearchParams({
          window_hours: "24",
          incident_window_days: "30",
          mttr_sla_hours: "24",
          mtta_proxy_sla_minutes: "15",
          rotation_lag_sla_hours: "168",
          secret_max_age_days: "30",
          limit: "50",
          top_n: "12",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentSloBoardPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/slo_board?${query.toString()}`,
        );
        setQueueIncidentSloBoard(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident SLO board unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentSloBoard(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentSloBoard(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueAudit = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueAudit(true);
      }
      try {
        const payload = await apiFetch<CalibrationQueueAuditPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput/audit?days=30&limit=120`,
        );
        setQueueAudit(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Queue audit unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueAudit(null);
      } finally {
        if (!silent) {
          setLoadingQueueAudit(false);
        }
      }
    },
    [apiUrl],
  );

  const loadQueueIncidentHooks = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentHooks(true);
      }
      try {
        const query = new URLSearchParams({
          limit: "200",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentHooksPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/hooks?${query.toString()}`,
        );
        setQueueIncidentHooks(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident hooks unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentHooks(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentHooks(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidentPolicies = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentPolicies(true);
      }
      try {
        const query = new URLSearchParams({
          limit: "500",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentPoliciesPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/policies?${query.toString()}`,
        );
        setQueueIncidentPolicies(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident policies unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentPolicies(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentPolicies(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidentPreflightPresets = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentPreflightPresets(true);
      }
      try {
        const query = new URLSearchParams({
          limit: "500",
          include_disabled: "true",
          run_before_live_sync_only: "false",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentPreflightPresetsPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/preflight/presets?${query.toString()}`,
        );
        setQueueIncidentPreflightPresets(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident preflight presets unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentPreflightPresets(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentPreflightPresets(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidents = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidents(true);
      }
      try {
        const query = new URLSearchParams({
          limit: "120",
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const payload = await apiFetch<CalibrationQueueIncidentsPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents?${query.toString()}`,
        );
        setQueueIncidents(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Queue incidents unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidents(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidents(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds],
  );

  const loadQueueIncidentSyncSchedules = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentSyncSchedules(true);
      }
      try {
        const query = new URLSearchParams({
          limit: "300",
        });
        const requested = queueCompareProjectIds.trim();
        const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (targetProjectId) {
          query.set("project_id", targetProjectId);
        }
        const payload = await apiFetch<CalibrationQueueIncidentSyncSchedulesPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/sync/schedules?${query.toString()}`,
        );
        setQueueIncidentSyncSchedules(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident sync schedules unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentSyncSchedules(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentSyncSchedules(false);
        }
      }
    },
    [apiUrl, projectId, queueCompareProjectIds, queueIncidentProjectId],
  );

  const loadQueueIncidentSyncScheduleFleet = useCallback(
    async (silent = false) => {
      if (!silent) {
        setLoadingQueueIncidentSyncScheduleFleet(true);
      }
      try {
        const pageSize = Math.max(10, Math.min(200, Number(queueIncidentSyncScheduleFleetPageSize || 25)));
        const page = Math.max(1, Number(queueIncidentSyncScheduleFleetPage || 1));
        const resolvedOffset = (page - 1) * pageSize;
        const query = new URLSearchParams({
          limit: String(pageSize),
          offset: String(resolvedOffset),
          due_only: queueIncidentSyncScheduleFleetDueOnly ? "true" : "false",
          sort_by: queueIncidentSyncScheduleFleetSortBy,
          sort_dir: queueIncidentSyncScheduleFleetSortDir,
        });
        const requested = queueCompareProjectIds.trim();
        if (requested) {
          query.set("project_ids", requested);
        } else if (projectId.trim()) {
          query.set("project_id", projectId.trim());
        }
        const projectFilter = queueIncidentSyncScheduleFleetProjectFilter.trim();
        if (projectFilter) {
          query.set("project_contains", projectFilter.slice(0, 256));
        }
        const nameFilter = queueIncidentSyncScheduleFleetNameFilter.trim();
        if (nameFilter) {
          query.set("name_contains", nameFilter.slice(0, 256));
        }
        if (queueIncidentSyncScheduleFleetStatusFilter !== "all") {
          query.set("status", queueIncidentSyncScheduleFleetStatusFilter);
        }
        if (queueIncidentSyncScheduleFleetEnabledFilter !== "all") {
          query.set("enabled", queueIncidentSyncScheduleFleetEnabledFilter === "enabled" ? "true" : "false");
        }
        const payload = await apiFetch<CalibrationQueueIncidentSyncSchedulesPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/sync/schedules?${query.toString()}`,
        );
        setQueueIncidentSyncScheduleFleetPayload(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident sync fleet unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentSyncScheduleFleetPayload(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentSyncScheduleFleet(false);
        }
      }
    },
    [
      apiUrl,
      projectId,
      queueCompareProjectIds,
      queueIncidentSyncScheduleFleetDueOnly,
      queueIncidentSyncScheduleFleetEnabledFilter,
      queueIncidentSyncScheduleFleetNameFilter,
      queueIncidentSyncScheduleFleetPage,
      queueIncidentSyncScheduleFleetPageSize,
      queueIncidentSyncScheduleFleetProjectFilter,
      queueIncidentSyncScheduleFleetSortBy,
      queueIncidentSyncScheduleFleetSortDir,
      queueIncidentSyncScheduleFleetStatusFilter,
    ],
  );

  const loadQueueIncidentSyncScheduleTimeline = useCallback(
    async (requestedScheduleId: string | null = null, silent = false) => {
      const allRows = [
        ...(Array.isArray(queueIncidentSyncSchedules?.schedules) ? queueIncidentSyncSchedules.schedules : []),
        ...(Array.isArray(queueIncidentSyncScheduleFleetPayload?.schedules)
          ? queueIncidentSyncScheduleFleetPayload.schedules
          : []),
      ].filter((item, index, items) => {
        const currentId = String(item?.id || "").trim();
        return currentId.length > 0 && items.findIndex((candidate) => String(candidate?.id || "").trim() === currentId) === index;
      });
      const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
      const selectedByName =
        allRows.find(
          (item) =>
            item.project_id === targetProjectId &&
            item.name === queueIncidentSyncScheduleName.trim(),
        ) || null;
      const resolvedScheduleId =
        (requestedScheduleId && requestedScheduleId.trim()) ||
        selectedByName?.id ||
        allRows.find((item) => item.project_id === targetProjectId)?.id ||
        null;
      if (!resolvedScheduleId) {
        setQueueIncidentSyncScheduleTimeline(null);
        return;
      }
      const matchedSchedule = allRows.find((item) => item.id === resolvedScheduleId) || null;
      const resolvedProjectId = String(matchedSchedule?.project_id || targetProjectId).trim();
      if (!silent) {
        setLoadingQueueIncidentSyncScheduleTimeline(true);
      }
      try {
        const query = new URLSearchParams({
          days: "30",
          limit: "120",
        });
        if (resolvedProjectId) {
          query.set("project_id", resolvedProjectId);
        }
        const payload = await apiFetch<CalibrationQueueIncidentSyncScheduleTimelinePayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/sync/schedules/${encodeURIComponent(resolvedScheduleId)}/timeline?${query.toString()}`,
        );
        setQueueIncidentSyncScheduleTimeline(payload);
        setQueueIncidentSyncScheduleTimelineScheduleId(String(payload.schedule_id || resolvedScheduleId));
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Incident sync run timeline unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setQueueIncidentSyncScheduleTimeline(null);
      } finally {
        if (!silent) {
          setLoadingQueueIncidentSyncScheduleTimeline(false);
        }
      }
    },
    [
      apiUrl,
      projectId,
      queueIncidentProjectId,
      queueIncidentSyncScheduleFleetPayload,
      queueIncidentSyncScheduleName,
      queueIncidentSyncSchedules,
    ],
  );

  const saveQueueIncidentSyncSchedule = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project is required",
        message: "Set project id before saving incident sync schedule.",
      });
      return;
    }
    const normalizedName = queueIncidentSyncScheduleName.trim();
    if (!normalizedName) {
      notifications.show({
        color: "orange",
        title: "Schedule name is required",
        message: "Choose a non-empty schedule name.",
      });
      return;
    }
    const computedIntervalMinutes =
      queueIncidentSyncSchedulePreset === "custom"
        ? Math.max(5, Math.min(10080, Number(queueIncidentSyncScheduleIntervalMinutes || 60)))
        : INCIDENT_SYNC_SCHEDULE_PRESET_INTERVALS[queueIncidentSyncSchedulePreset] || 240;
    setQueueIncidentSyncScheduleBusy(true);
    try {
      const payload = await apiFetch<{ status: string; schedule: CalibrationQueueIncidentSyncSchedule }>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/sync/schedules",
        {
          method: "PUT",
          body: {
            project_id: targetProjectId,
            name: normalizedName,
            enabled: queueIncidentSyncScheduleEnabled,
            preset: queueIncidentSyncSchedulePreset,
            interval_minutes: queueIncidentSyncSchedulePreset === "custom" ? computedIntervalMinutes : null,
            window_hours: Math.max(1, Math.min(168, Number(queueIncidentSyncScheduleWindowHours || 24))),
            batch_size: Math.max(1, Math.min(200, Number(queueIncidentSyncScheduleBatchSize || 50))),
            sync_limit: Math.max(1, Math.min(200, Number(queueIncidentSyncScheduleLimit || 50))),
            dry_run: queueIncidentSyncScheduleDryRun,
            force_resolve: queueIncidentSyncScheduleForceResolve,
            preflight_enforcement_mode: queueIncidentSyncSchedulePreflightMode,
            preflight_pause_hours:
              queueIncidentSyncSchedulePreflightMode === "off" || queueIncidentSyncSchedulePreflightMode === "inherit"
                ? null
                : Math.max(1, Math.min(168, Number(queueIncidentSyncSchedulePreflightPauseHours || 4))),
            preflight_critical_fail_threshold:
              queueIncidentSyncSchedulePreflightMode === "off" || queueIncidentSyncSchedulePreflightMode === "inherit"
                ? null
                : Math.max(1, Math.min(100, Number(queueIncidentSyncSchedulePreflightCriticalThreshold || 1))),
            preflight_include_run_before_live_sync_only: queueIncidentSyncSchedulePreflightRunBeforeOnly,
            preflight_record_audit: queueIncidentSyncSchedulePreflightRecordAudit,
            requested_by: reviewer.trim() || "web_ui",
            next_run_at: queueIncidentSyncScheduleNextRunAt.trim() || null,
            updated_by: reviewer.trim() || "web_ui",
          },
        },
      );
      setQueueIncidentSyncScheduleName(String(payload.schedule?.name || normalizedName));
      await Promise.all([
        loadQueueIncidentSyncSchedules(true),
        loadQueueIncidentSyncScheduleFleet(true),
        loadQueueAudit(true),
        loadQueueIncidentSyncScheduleTimeline(String(payload.schedule?.id || ""), true),
      ]);
      notifications.show({
        color: "teal",
        title: "Incident sync schedule saved",
        message: `${targetProjectId}: ${normalizedName}`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Could not save incident sync schedule",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentSyncScheduleBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueIncidentSyncScheduleFleet,
    loadQueueIncidentSyncSchedules,
    loadQueueIncidentSyncScheduleTimeline,
    projectId,
    queueIncidentProjectId,
    queueIncidentSyncScheduleBatchSize,
    queueIncidentSyncScheduleDryRun,
    queueIncidentSyncScheduleEnabled,
    queueIncidentSyncScheduleForceResolve,
    queueIncidentSyncScheduleIntervalMinutes,
    queueIncidentSyncScheduleLimit,
    queueIncidentSyncScheduleName,
    queueIncidentSyncScheduleNextRunAt,
    queueIncidentSyncSchedulePreflightCriticalThreshold,
    queueIncidentSyncSchedulePreflightMode,
    queueIncidentSyncSchedulePreflightPauseHours,
    queueIncidentSyncSchedulePreflightRecordAudit,
    queueIncidentSyncSchedulePreflightRunBeforeOnly,
    queueIncidentSyncSchedulePreset,
    queueIncidentSyncScheduleWindowHours,
    reviewer,
  ]);

  const deleteQueueIncidentSyncSchedule = useCallback(
    async (schedule: CalibrationQueueIncidentSyncSchedule) => {
      const targetProjectId = String(schedule.project_id || "").trim();
      const scheduleId = String(schedule.id || "").trim();
      if (!targetProjectId || !scheduleId) {
        return;
      }
      setQueueIncidentSyncScheduleDeleteBusyId(scheduleId);
      try {
        await apiFetch<{ status: string }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/incidents/sync/schedules/${encodeURIComponent(scheduleId)}?project_id=${encodeURIComponent(targetProjectId)}&updated_by=${encodeURIComponent(reviewer.trim() || "web_ui")}`,
          { method: "DELETE" },
        );
        if (queueIncidentSyncScheduleName.trim() === schedule.name) {
          setQueueIncidentSyncScheduleName("");
        }
        await Promise.all([
          loadQueueIncidentSyncSchedules(true),
          loadQueueIncidentSyncScheduleFleet(true),
          loadQueueAudit(true),
          loadQueueIncidentSyncScheduleTimeline(null, true),
        ]);
        notifications.show({
          color: "teal",
          title: "Incident sync schedule deleted",
          message: `${targetProjectId}: ${schedule.name}`,
        });
      } catch (error) {
        notifications.show({
          color: "orange",
          title: "Could not delete incident sync schedule",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setQueueIncidentSyncScheduleDeleteBusyId(null);
      }
    },
    [
      apiUrl,
      loadQueueAudit,
      loadQueueIncidentSyncScheduleFleet,
      loadQueueIncidentSyncSchedules,
      loadQueueIncidentSyncScheduleTimeline,
      queueIncidentSyncScheduleName,
      reviewer,
    ],
  );

  const runQueueIncidentSyncSchedules = useCallback(
    async (scheduleId: string | null = null) => {
      const requestedProjects = queueCompareProjectIds
        .split(",")
        .map((item) => item.trim())
        .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
      const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
      const allRows = Array.isArray(queueIncidentSyncSchedules?.schedules) ? queueIncidentSyncSchedules.schedules : [];
      const selectedSchedule =
        allRows.find(
          (item) =>
            item.project_id === targetProjectId &&
            item.name === queueIncidentSyncScheduleName.trim(),
        ) || null;
      const effectiveScheduleId =
        scheduleId ||
        (queueIncidentSyncScheduleRunSelectedOnly ? (selectedSchedule?.id || null) : null);
      if (queueIncidentSyncScheduleRunSelectedOnly && !effectiveScheduleId) {
        notifications.show({
          color: "orange",
          title: "Schedule is required",
          message: "Select a schedule to run, or disable selected-only mode.",
        });
        return;
      }
      setQueueIncidentSyncScheduleRunBusy(true);
      try {
        const payload = await apiFetch<CalibrationQueueIncidentSyncScheduleRunPayload>(
          apiUrl,
          "/v1/gatekeeper/calibration/operations/incidents/sync/schedules/run",
          {
            method: "POST",
            body: {
              project_id: requestedProjects.length === 0 ? targetProjectId || null : null,
              project_ids: requestedProjects.length > 0 ? requestedProjects : null,
              schedule_ids: effectiveScheduleId ? [effectiveScheduleId] : null,
              actor: reviewer.trim() || "web_ui",
              force_run: queueIncidentSyncScheduleRunForce,
              skip_due_check: queueIncidentSyncScheduleRunSkipDue,
              limit: 200,
            },
          },
        );
        setQueueIncidentSyncScheduleRunResult(payload);
        const firstResult = Array.isArray(payload.results) && payload.results.length > 0 ? payload.results[0] : null;
        const selectedRunScheduleId = firstResult?.schedule_id || effectiveScheduleId || null;
        setQueueIncidentSyncScheduleRunSelectedScheduleId(selectedRunScheduleId);
        setQueueIncidentSyncScheduleTimelineScheduleId(selectedRunScheduleId);
        setQueueAuditFocusEventId(
          firstResult?.audit_event_id != null && Number.isFinite(Number(firstResult.audit_event_id))
            ? Number(firstResult.audit_event_id)
            : null,
        );
        await Promise.all([
          loadQueueIncidentSyncSchedules(true),
          loadQueueIncidentSyncScheduleFleet(true),
          loadQueueIncidents(true),
          loadQueueThroughputCompare(true),
          loadQueueGovernanceDigest(true),
          loadQueueOwnerRollups(true),
          loadQueueGovernanceDrift(true),
          loadQueueIncidentSloBoard(true),
          loadQueueAudit(true),
          loadQueueIncidentSyncScheduleTimeline(selectedRunScheduleId, true),
        ]);
        notifications.show({
          color: payload.summary.failed > 0 ? "orange" : "teal",
          title: "Incident sync schedules executed",
          message: `executed ${payload.summary.executed}/${payload.summary.schedules_total}, failed ${payload.summary.failed}, blocked ${payload.summary.blocked}, paused ${payload.summary.paused}`,
        });
      } catch (error) {
        notifications.show({
          color: "orange",
          title: "Incident sync schedule run failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setQueueIncidentSyncScheduleRunBusy(false);
      }
    },
    [
      apiUrl,
      loadQueueAudit,
      loadQueueGovernanceDrift,
      loadQueueGovernanceDigest,
      loadQueueIncidentSloBoard,
      loadQueueIncidentSyncSchedules,
      loadQueueIncidentSyncScheduleFleet,
      loadQueueIncidentSyncScheduleTimeline,
      loadQueueIncidents,
      loadQueueOwnerRollups,
      loadQueueThroughputCompare,
      projectId,
      queueCompareProjectIds,
      queueIncidentProjectId,
      queueIncidentSyncScheduleName,
      queueIncidentSyncScheduleRunForce,
      queueIncidentSyncScheduleRunSelectedOnly,
      queueIncidentSyncScheduleRunSkipDue,
      queueIncidentSyncSchedules,
      reviewer,
    ],
  );

  const loadOperationRunDetail = useCallback(
    async (runId: string, silent = false) => {
      if (!projectId.trim() || !runId) {
        return;
      }
      try {
        const payload = await apiFetch<{
          run: CalibrationOperationRun;
          events: CalibrationOperationEvent[];
        }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/runs/${encodeURIComponent(runId)}?project_id=${encodeURIComponent(projectId)}&event_limit=200`,
        );
        setSelectedOperationRun(payload.run ?? null);
        const rows = Array.isArray(payload.events) ? payload.events : [];
        setOperationEvents(rows);
        setOperationEventsCursor(rows.length > 0 ? rows[rows.length - 1].id : 0);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Operation detail unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      }
    },
    [apiUrl, projectId],
  );

  const loadOperationRunEvents = useCallback(
    async (runId: string, silent = true) => {
      if (!projectId.trim() || !runId) {
        return;
      }
      try {
        const payload = await apiFetch<{
          run: CalibrationOperationRun;
          events: CalibrationOperationEvent[];
          next_event_id: number;
          terminal: boolean;
        }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/runs/${encodeURIComponent(runId)}/events?project_id=${encodeURIComponent(projectId)}&after_event_id=${encodeURIComponent(String(operationEventsCursor))}&limit=200`,
        );
        setSelectedOperationRun(payload.run ?? null);
        const nextRows = Array.isArray(payload.events) ? payload.events : [];
        if (nextRows.length > 0) {
          setOperationEvents((prev) => {
            const merged = [...prev, ...nextRows];
            return merged.slice(-300);
          });
          setOperationEventsCursor(nextRows[nextRows.length - 1].id);
        }
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Operation events unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
      }
    },
    [apiUrl, operationEventsCursor, projectId],
  );

  useEffect(() => {
    operationEventsCursorRef.current = operationEventsCursor;
  }, [operationEventsCursor]);

  useEffect(() => {
    void loadOperationRuns();
  }, [loadOperationRuns]);

  useEffect(() => {
    void loadQueueThroughput();
  }, [loadQueueThroughput]);

  useEffect(() => {
    if (projectId.trim() && !queueCompareProjectIds.trim()) {
      setQueueCompareProjectIds(projectId.trim());
    }
  }, [projectId, queueCompareProjectIds]);

  useEffect(() => {
    if (projectId.trim() && !queueOwnerProjectId.trim()) {
      setQueueOwnerProjectId(projectId.trim());
    }
  }, [projectId, queueOwnerProjectId]);

  useEffect(() => {
    if (projectId.trim() && !queueIncidentProjectId.trim()) {
      setQueueIncidentProjectId(projectId.trim());
    }
  }, [projectId, queueIncidentProjectId]);

  useEffect(() => {
    void loadQueueThroughputCompare();
  }, [loadQueueThroughputCompare]);

  useEffect(() => {
    void loadQueueAutoscaling();
  }, [loadQueueAutoscaling]);

  useEffect(() => {
    void loadQueueGovernanceDigest();
  }, [loadQueueGovernanceDigest]);

  useEffect(() => {
    void loadQueueIncidentEscalationDigest();
  }, [loadQueueIncidentEscalationDigest]);

  useEffect(() => {
    void loadQueueOwnerRollups();
  }, [loadQueueOwnerRollups]);

  useEffect(() => {
    void loadQueueGovernanceDrift();
  }, [loadQueueGovernanceDrift]);

  useEffect(() => {
    void loadQueueIncidentSloBoard();
  }, [loadQueueIncidentSloBoard]);

  useEffect(() => {
    void loadQueueAudit();
  }, [loadQueueAudit]);

  useEffect(() => {
    void loadQueueIncidentHooks();
  }, [loadQueueIncidentHooks]);

  useEffect(() => {
    void loadQueueIncidentPolicies();
  }, [loadQueueIncidentPolicies]);

  useEffect(() => {
    void loadQueueIncidentPreflightPresets();
  }, [loadQueueIncidentPreflightPresets]);

  useEffect(() => {
    void loadQueueIncidents();
  }, [loadQueueIncidents]);

  useEffect(() => {
    void loadQueueIncidentSyncSchedules();
  }, [loadQueueIncidentSyncSchedules]);

  useEffect(() => {
    void loadQueueIncidentSyncScheduleFleet();
  }, [loadQueueIncidentSyncScheduleFleet]);

  useEffect(() => {
    const rows = Array.isArray(queueIncidentSyncScheduleRunResult?.results) ? queueIncidentSyncScheduleRunResult.results : [];
    if (rows.length === 0) {
      setQueueIncidentSyncScheduleRunSelectedScheduleId(null);
      return;
    }
    const selected = queueIncidentSyncScheduleRunSelectedScheduleId;
    if (!selected || !rows.some((item) => item.schedule_id === selected)) {
      setQueueIncidentSyncScheduleRunSelectedScheduleId(rows[0].schedule_id);
    }
  }, [queueIncidentSyncScheduleRunResult, queueIncidentSyncScheduleRunSelectedScheduleId]);

  useEffect(() => {
    const rows = [
      ...(Array.isArray(queueIncidentSyncSchedules?.schedules) ? queueIncidentSyncSchedules.schedules : []),
      ...(Array.isArray(queueIncidentSyncScheduleFleetPayload?.schedules)
        ? queueIncidentSyncScheduleFleetPayload.schedules
        : []),
    ].filter((item, index, items) => {
      const currentId = String(item?.id || "").trim();
      return currentId.length > 0 && items.findIndex((candidate) => String(candidate?.id || "").trim() === currentId) === index;
    });
    if (rows.length === 0) {
      setQueueIncidentSyncScheduleTimelineScheduleId(null);
      setQueueIncidentSyncScheduleTimeline(null);
      return;
    }
    if (
      queueIncidentSyncScheduleTimelineScheduleId &&
      rows.some((item) => item.id === queueIncidentSyncScheduleTimelineScheduleId)
    ) {
      return;
    }
    const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
    const selectedByName =
      rows.find(
        (item) =>
          item.project_id === targetProjectId &&
          item.name === queueIncidentSyncScheduleName.trim(),
      ) || null;
    const fallbackId = selectedByName?.id || rows.find((item) => item.project_id === targetProjectId)?.id || rows[0]?.id || null;
    setQueueIncidentSyncScheduleTimelineScheduleId(fallbackId);
  }, [
    projectId,
    queueIncidentProjectId,
    queueIncidentSyncScheduleFleetPayload,
    queueIncidentSyncScheduleName,
    queueIncidentSyncScheduleTimelineScheduleId,
    queueIncidentSyncSchedules,
  ]);

  useEffect(() => {
    if (!queueIncidentSyncScheduleTimelineScheduleId) {
      setQueueIncidentSyncScheduleTimeline(null);
      return;
    }
    void loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true);
  }, [loadQueueIncidentSyncScheduleTimeline, queueIncidentSyncScheduleTimelineScheduleId]);

  useEffect(() => {
    setQueueIncidentSyncScheduleFleetPage(1);
  }, [
    queueCompareProjectIds,
    queueIncidentSyncScheduleFleetDueOnly,
    queueIncidentSyncScheduleFleetEnabledFilter,
    queueIncidentSyncScheduleFleetNameFilter,
    queueIncidentSyncScheduleFleetSortBy,
    queueIncidentSyncScheduleFleetSortDir,
    queueIncidentSyncScheduleFleetProjectFilter,
    queueIncidentSyncScheduleFleetStatusFilter,
    queueIncidentSyncScheduleFleetPageSize,
  ]);

  useEffect(() => {
    const paging =
      queueIncidentSyncScheduleFleetPayload &&
      typeof queueIncidentSyncScheduleFleetPayload.paging === "object" &&
      queueIncidentSyncScheduleFleetPayload.paging != null
        ? queueIncidentSyncScheduleFleetPayload.paging
        : null;
    if (!paging) {
      return;
    }
    const pageSize = Math.max(10, Math.min(200, Number(paging.limit || queueIncidentSyncScheduleFleetPageSize || 25)));
    const total = Math.max(0, Number(paging.total || 0));
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (queueIncidentSyncScheduleFleetPage > totalPages) {
      setQueueIncidentSyncScheduleFleetPage(totalPages);
    }
  }, [queueIncidentSyncScheduleFleetPage, queueIncidentSyncScheduleFleetPageSize, queueIncidentSyncScheduleFleetPayload]);

  useEffect(() => {
    if (queueIncidentSyncSchedulePreset === "custom") {
      return;
    }
    const mapped = INCIDENT_SYNC_SCHEDULE_PRESET_INTERVALS[queueIncidentSyncSchedulePreset];
    if (mapped && mapped !== queueIncidentSyncScheduleIntervalMinutes) {
      setQueueIncidentSyncScheduleIntervalMinutes(mapped);
    }
  }, [queueIncidentSyncScheduleIntervalMinutes, queueIncidentSyncSchedulePreset]);

  useEffect(() => {
    const targetProjectId = queueIncidentProjectId.trim() || projectId.trim();
    if (!targetProjectId) {
      return;
    }
    const allRows = Array.isArray(queueIncidentSyncSchedules?.schedules) ? queueIncidentSyncSchedules.schedules : [];
    const projectRows = allRows.filter((item) => item.project_id === targetProjectId);
    if (projectRows.length === 0) {
      return;
    }
    const selectedName = queueIncidentSyncScheduleName.trim();
    const selectedExists = selectedName ? projectRows.some((item) => item.name === selectedName) : false;
    if (selectedName && !selectedExists) {
      return;
    }
    const matched = selectedName ? projectRows.find((item) => item.name === selectedName) : projectRows[0];
    if (!matched) {
      return;
    }
    setQueueIncidentSyncScheduleName(String(matched.name || "default"));
    const presetValue = String(matched.preset || "hourly").trim().toLowerCase();
    setQueueIncidentSyncSchedulePreset(
      presetValue === "hourly" ||
        presetValue === "every_4h" ||
        presetValue === "daily" ||
        presetValue === "weekly" ||
        presetValue === "custom"
        ? presetValue
        : "custom",
    );
    setQueueIncidentSyncScheduleEnabled(Boolean(matched.enabled));
    setQueueIncidentSyncScheduleIntervalMinutes(Math.max(5, Math.min(10080, Number(matched.interval_minutes || 240))));
    setQueueIncidentSyncScheduleWindowHours(Math.max(1, Math.min(168, Number(matched.window_hours || 24))));
    setQueueIncidentSyncScheduleBatchSize(Math.max(1, Math.min(200, Number(matched.batch_size || 50))));
    setQueueIncidentSyncScheduleLimit(Math.max(1, Math.min(200, Number(matched.sync_limit || 50))));
    setQueueIncidentSyncScheduleDryRun(Boolean(matched.dry_run));
    setQueueIncidentSyncScheduleForceResolve(Boolean(matched.force_resolve));
    const preflightModeRaw = String(matched.preflight_enforcement_mode || "inherit").trim().toLowerCase();
    setQueueIncidentSyncSchedulePreflightMode(
      preflightModeRaw === "off" || preflightModeRaw === "block" || preflightModeRaw === "pause"
        ? preflightModeRaw
        : "inherit",
    );
    setQueueIncidentSyncSchedulePreflightPauseHours(Math.max(1, Math.min(168, Number(matched.preflight_pause_hours || 4))));
    setQueueIncidentSyncSchedulePreflightCriticalThreshold(
      Math.max(1, Math.min(100, Number(matched.preflight_critical_fail_threshold || 1))),
    );
    setQueueIncidentSyncSchedulePreflightRunBeforeOnly(Boolean(matched.preflight_include_run_before_live_sync_only));
    setQueueIncidentSyncSchedulePreflightRecordAudit(Boolean(matched.preflight_record_audit));
    setQueueIncidentSyncScheduleNextRunAt(matched.next_run_at || "");
  }, [projectId, queueIncidentProjectId, queueIncidentSyncScheduleName, queueIncidentSyncSchedules]);

  useEffect(() => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      return;
    }
    const hooks = Array.isArray(queueIncidentHooks?.hooks) ? queueIncidentHooks.hooks : [];
    const matched = hooks.find((item) => item.project_id === targetProjectId);
    if (!matched) {
      return;
    }
    const provider = (matched.provider || "webhook").toLowerCase();
    const providerConfig = matched.provider_config && typeof matched.provider_config === "object" ? matched.provider_config : {};
    setQueueIncidentHookEnabled(Boolean(matched.enabled));
    setQueueIncidentProvider(provider);
    setQueueIncidentOpenWebhookUrl(matched.open_webhook_url || "");
    setQueueIncidentResolveWebhookUrl(matched.resolve_webhook_url || "");
    if (provider === "webhook") {
      const headers =
        providerConfig && typeof providerConfig.headers === "object" && providerConfig.headers != null
          ? providerConfig.headers
          : {};
      setQueueIncidentWebhookHeadersJson(JSON.stringify(headers, null, 2));
    } else {
      setQueueIncidentWebhookHeadersJson("{}");
    }
    setQueueIncidentPagerdutyRoutingKey(
      provider === "pagerduty" ? String(providerConfig.routing_key || "") : "",
    );
    setQueueIncidentPagerdutyDedupPrefix(
      provider === "pagerduty" ? String(providerConfig.dedup_key_prefix || "synapse-queue") : "synapse-queue",
    );
    setQueueIncidentJiraBaseUrl(provider === "jira" ? String(providerConfig.base_url || "") : "");
    setQueueIncidentJiraProjectKey(provider === "jira" ? String(providerConfig.project_key || "") : "");
    setQueueIncidentJiraAuthMode(
      provider === "jira" && String(providerConfig.auth_mode || "").toLowerCase() === "bearer" ? "bearer" : "basic",
    );
    setQueueIncidentJiraEmail(provider === "jira" ? String(providerConfig.email || "") : "");
    setQueueIncidentJiraApiToken(provider === "jira" ? String(providerConfig.api_token || "") : "");
    setQueueIncidentJiraIssueType(provider === "jira" ? String(providerConfig.issue_type || "Incident") : "Incident");
    setQueueIncidentJiraResolveTransitionId(provider === "jira" ? String(providerConfig.resolve_transition_id || "") : "");
    setQueueIncidentOpenOnHealthCsv(
      Array.isArray(matched.open_on_health) && matched.open_on_health.length > 0 ? matched.open_on_health.join(",") : "critical",
    );
    setQueueIncidentAutoResolve(Boolean(matched.auto_resolve));
    setQueueIncidentCooldownMinutes(Math.max(1, Math.min(1440, Number(matched.cooldown_minutes || 30))));
    setQueueIncidentTimeoutSec(Math.max(1, Math.min(60, Number(matched.timeout_sec || 10))));
  }, [queueIncidentHooks, queueIncidentProjectId]);

  useEffect(() => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      return;
    }
    const rows = Array.isArray(queueIncidentPreflightPresets?.presets) ? queueIncidentPreflightPresets.presets : [];
    const projectRows = rows.filter((item) => item.project_id === targetProjectId);
    if (projectRows.length === 0) {
      setQueueIncidentPreflightPresetKey("");
      return;
    }
    const existingByKey = queueIncidentPreflightPresetKey.trim();
    const matched =
      projectRows.find((item) => item.preset_key === existingByKey) ||
      projectRows.find((item) => item.run_before_live_sync) ||
      projectRows[0];
    if (!matched) {
      return;
    }
    setQueueIncidentPreflightPresetKey(String(matched.preset_key || ""));
    setQueueIncidentPreflightPresetName(String(matched.name || ""));
    setQueueIncidentPreflightEnabled(Boolean(matched.enabled));
    setQueueIncidentPreflightAlertCode(String(matched.alert_code || "queue_depth_critical"));
    setQueueIncidentPreflightHealth(
      matched.health === "healthy" || matched.health === "watch" || matched.health === "critical" ? matched.health : "critical",
    );
    setQueueIncidentPreflightAdditionalAlertCodesCsv(
      Array.isArray(matched.additional_alert_codes) ? matched.additional_alert_codes.join(",") : "",
    );
    setQueueIncidentPreflightExpectedDecision(
      matched.expected_decision === "skip" || matched.expected_decision === "invalid_ok" ? matched.expected_decision : "open",
    );
    setQueueIncidentPreflightRequiredProvider(
      matched.required_provider === "webhook" || matched.required_provider === "pagerduty" || matched.required_provider === "jira"
        ? matched.required_provider
        : "inherit",
    );
    setQueueIncidentPreflightRunBeforeLiveSync(Boolean(matched.run_before_live_sync));
    setQueueIncidentPreflightSeverity(
      matched.severity === "info" || matched.severity === "critical" ? matched.severity : "warning",
    );
    setQueueIncidentPreflightStrictMode(Boolean(matched.strict_mode));
  }, [queueIncidentPreflightPresetKey, queueIncidentPreflightPresets, queueIncidentProjectId]);

  useEffect(() => {
    if (!selectedOperationRunId) {
      setSelectedOperationRun(null);
      setOperationEvents([]);
      setOperationEventsCursor(0);
      return;
    }
    setOperationEvents([]);
    setOperationEventsCursor(0);
    void loadOperationRunDetail(selectedOperationRunId, true);
  }, [loadOperationRunDetail, selectedOperationRunId]);

  const hasActiveOperation = useMemo(
    () => operationRuns.some((item) => ["queued", "running", "cancel_requested"].includes(item.status)),
    [operationRuns],
  );

  useEffect(() => {
    const intervalMs = hasActiveOperation ? 2500 : 9000;
    const timer = globalThis.setInterval(() => {
      void loadOperationRuns(true);
      void loadQueueThroughput(true);
      void loadQueueThroughputCompare(true);
      void loadQueueAutoscaling(true);
      void loadQueueGovernanceDigest(true);
      void loadQueueIncidentEscalationDigest(true);
      void loadQueueOwnerRollups(true);
      void loadQueueGovernanceDrift(true);
      void loadQueueIncidentSloBoard(true);
      void loadQueueAudit(true);
      void loadQueueIncidentHooks(true);
      void loadQueueIncidentPolicies(true);
      void loadQueueIncidentPreflightPresets(true);
      void loadQueueIncidents(true);
      void loadQueueIncidentSyncSchedules(true);
      void loadQueueIncidentSyncScheduleFleet(true);
      if (queueIncidentSyncScheduleTimelineScheduleId) {
        void loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true);
      }
      if (selectedOperationRunId) {
        void loadOperationRunEvents(selectedOperationRunId, true);
      }
    }, intervalMs);
    return () => {
      globalThis.clearInterval(timer);
    };
  }, [
    hasActiveOperation,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentEscalationDigest,
    loadQueueOwnerRollups,
    loadQueueGovernanceDrift,
    loadQueueIncidentSloBoard,
    loadQueueIncidentHooks,
    loadQueueIncidentPolicies,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidents,
    loadQueueIncidentSyncSchedules,
    loadQueueIncidentSyncScheduleFleet,
    loadQueueIncidentSyncScheduleTimeline,
    queueIncidentSyncScheduleTimelineScheduleId,
    loadOperationRunEvents,
    loadOperationRuns,
    loadQueueAudit,
    loadQueueThroughput,
    loadQueueThroughputCompare,
    selectedOperationRunId,
  ]);

  useEffect(() => {
    if (!queueSseEnabled || !selectedOperationRunId || !projectId.trim()) {
      setQueueSseStatus("idle");
      return;
    }
    const root = apiUrl.replace(/\/+$/, "");
    const query = new URLSearchParams({
      project_id: projectId,
      after_event_id: String(Math.max(0, operationEventsCursorRef.current)),
      timeout_sec: "120",
      poll_interval_ms: "750",
    });
    const streamUrl = `${root}/v1/gatekeeper/calibration/operations/runs/${encodeURIComponent(selectedOperationRunId)}/stream?${query.toString()}`;
    const source = new EventSource(streamUrl);
    let closed = false;
    setQueueSseStatus("connecting");

    source.addEventListener("open", () => {
      if (!closed) {
        setQueueSseStatus("connected");
      }
    });
    source.addEventListener("progress", (event) => {
      if (closed) {
        return;
      }
      try {
        const item = JSON.parse(event.data) as CalibrationOperationEvent;
        if (typeof item?.id !== "number") {
          return;
        }
        setOperationEvents((prev) => {
          const hasEvent = prev.some((row) => row.id === item.id);
          if (hasEvent) {
            return prev;
          }
          return [...prev, item].slice(-300);
        });
        setOperationEventsCursor((prev) => Math.max(prev, item.id));
      } catch {
        return;
      }
    });
    source.addEventListener("status", (event) => {
      if (closed) {
        return;
      }
      try {
        const payload = JSON.parse(event.data) as {
          status?: string;
          progress_percent?: number;
          progress_phase?: string;
          terminal?: boolean;
          cursor?: number;
        };
        if (typeof payload.cursor === "number") {
          setOperationEventsCursor((prev) => Math.max(prev, payload.cursor ?? 0));
        }
        setSelectedOperationRun((prev) => {
          if (!prev) {
            return prev;
          }
          return {
            ...prev,
            status: payload.status ?? prev.status,
            progress_percent:
              typeof payload.progress_percent === "number" ? payload.progress_percent : prev.progress_percent,
            progress_phase: payload.progress_phase ?? prev.progress_phase,
            updated_at: new Date().toISOString(),
          };
        });
        if (payload.terminal) {
          setQueueSseStatus("idle");
          source.close();
          void loadOperationRuns(true);
          void loadQueueThroughput(true);
          void loadQueueThroughputCompare(true);
          void loadQueueAutoscaling(true);
          void loadQueueGovernanceDigest(true);
          void loadQueueIncidentEscalationDigest(true);
          void loadQueueAudit(true);
        }
      } catch {
        return;
      }
    });
    source.addEventListener("done", () => {
      if (closed) {
        return;
      }
      setQueueSseStatus("idle");
      source.close();
    });
    source.addEventListener("timeout", () => {
      if (closed) {
        return;
      }
      setQueueSseStatus("fallback");
      source.close();
    });
    source.onerror = () => {
      if (closed) {
        return;
      }
      setQueueSseStatus("fallback");
      source.close();
    };

    return () => {
      closed = true;
      source.close();
    };
  }, [
    apiUrl,
    loadOperationRuns,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentEscalationDigest,
    loadQueueAudit,
    loadQueueThroughput,
    loadQueueThroughputCompare,
    projectId,
    queueSseEnabled,
    selectedOperationRunId,
  ]);

  const loadObservability = useCallback(async () => {
    if (!projectId.trim()) {
      setObservability(null);
      return;
    }
    setLoadingObservability(true);
    try {
      const payload = await apiFetch<ScheduleObservabilityPayload>(
        apiUrl,
        `/v1/gatekeeper/calibration/schedules/observability?project_id=${encodeURIComponent(projectId)}&days=${encodeURIComponent(String(observabilityDays))}&limit=200`,
      );
      setObservability(payload);
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Observability unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
      setObservability(null);
    } finally {
      setLoadingObservability(false);
    }
  }, [apiUrl, observabilityDays, projectId]);

  useEffect(() => {
    void loadObservability();
  }, [loadObservability]);

  const loadObservabilityCompare = useCallback(async () => {
    setLoadingCompare(true);
    try {
      const params = new URLSearchParams({
        days: String(observabilityDays),
        limit: "30",
      });
      const requestedRaw = compareProjectIds.trim();
      if (requestedRaw) {
        params.set("project_ids", requestedRaw);
      }
      const payload = await apiFetch<ObservabilityComparePayload>(
        apiUrl,
        `/v1/gatekeeper/calibration/observability/compare?${params.toString()}`,
      );
      setObservabilityCompare(payload);
      const rows = Array.isArray(payload.projects) ? payload.projects : [];
      setSelectedCompareProjectId((current) => {
        if (current && rows.some((item) => item.project_id === current)) {
          return current;
        }
        return rows.length > 0 ? rows[0].project_id : null;
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Cross-project compare unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
      setObservabilityCompare(null);
      setSelectedCompareProjectId(null);
      setObservabilityCompareDrilldown(null);
    } finally {
      setLoadingCompare(false);
    }
  }, [apiUrl, compareProjectIds, observabilityDays]);

  useEffect(() => {
    if (projectId.trim() && !compareProjectIds.trim()) {
      setCompareProjectIds(projectId.trim());
    }
  }, [compareProjectIds, projectId]);

  useEffect(() => {
    void loadObservabilityCompare();
  }, [loadObservabilityCompare]);

  const loadObservabilityCompareDrilldown = useCallback(
    async (targetProjectId: string, silent = false) => {
      if (!targetProjectId.trim()) {
        setObservabilityCompareDrilldown(null);
        return;
      }
      if (!silent) {
        setLoadingCompareDrilldown(true);
      }
      try {
        const query = new URLSearchParams({
          project_id: targetProjectId,
          days: String(observabilityDays),
          include_neighbors: "2",
        });
        const payload = await apiFetch<ObservabilityCompareDrilldownPayload>(
          apiUrl,
          `/v1/gatekeeper/calibration/observability/compare/drilldown?${query.toString()}`,
        );
        setObservabilityCompareDrilldown(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Compare drill-down unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setObservabilityCompareDrilldown(null);
      } finally {
        if (!silent) {
          setLoadingCompareDrilldown(false);
        }
      }
    },
    [apiUrl, observabilityDays],
  );

  useEffect(() => {
    if (!selectedCompareProjectId) {
      setObservabilityCompareDrilldown(null);
      return;
    }
    void loadObservabilityCompareDrilldown(selectedCompareProjectId, true);
  }, [loadObservabilityCompareDrilldown, selectedCompareProjectId]);

  const refreshCompareDrilldown = useCallback(async () => {
    if (!selectedCompareProjectId) {
      return;
    }
    await loadObservabilityCompareDrilldown(selectedCompareProjectId, true);
  }, [loadObservabilityCompareDrilldown, selectedCompareProjectId]);

  const previewOperations = useCallback(
    async (forceRun: boolean) => {
      if (!projectId.trim()) {
        return;
      }
      setOperationLoading(true);
      try {
        const query = new URLSearchParams({
          project_id: projectId,
          skip_due_check: String(skipDueCheckForOps),
          force_run: String(forceRun),
          timeout_sec: "1200",
        });
        const payload = await apiFetch<{
          status: string;
          operation: CalibrationOperationPayload;
          safety?: { required_confirmation_phrase?: string };
        }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/preview?${query.toString()}`,
        );
        setOperationResult(payload.operation ?? null);
        const requiredPhrase = payload.safety?.required_confirmation_phrase;
        if (requiredPhrase && !confirmationPhrase.trim()) {
          setConfirmationPhrase(requiredPhrase);
        }
        notifications.show({
          color: "teal",
          title: forceRun ? "Dry-run prepared" : "Due preview loaded",
          message: forceRun ? "Dry-run execution plan prepared for immediate run." : "Due-state analysis completed.",
        });
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Preview failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setOperationLoading(false);
      }
    },
    [apiUrl, confirmationPhrase, projectId, skipDueCheckForOps],
  );

  const runOperations = useCallback(
    async (dryRun: boolean) => {
      if (!projectId.trim()) {
        return;
      }
      setOperationExecuting(true);
      try {
        const payload = await apiFetch<{
          status: string;
          run: CalibrationOperationRun;
          queue_paused?: boolean;
          queue_resume_at?: string | null;
        }>(
          apiUrl,
          "/v1/gatekeeper/calibration/operations/queue",
          {
            method: "POST",
            body: {
              project_id: projectId,
              requested_by: reviewer.trim() || "web_ui",
              operation_token: dryRun ? null : operationToken.trim(),
              confirm: dryRun ? false : operationConfirmed,
              confirmation_phrase: dryRun ? null : confirmationPhrase.trim() || null,
              dry_run: dryRun,
              max_attempts: 3,
              force_run: true,
              skip_due_check: skipDueCheckForOps,
              timeout_sec: 1200,
              fail_on_alert: false,
            },
          },
        );
        const queuedRun = payload.run ?? null;
        if (queuedRun?.id) {
          setSelectedOperationRunId(queuedRun.id);
        }
        notifications.show({
          color: payload.queue_paused ? "yellow" : dryRun ? "blue" : "teal",
          title: dryRun ? "Dry-run queued" : "Manual run queued",
          message: payload.queue_paused
            ? `Queued but paused until ${fmtDate(payload.queue_resume_at ?? null)}.`
            : dryRun
              ? "Dry-run queued. Live progress will stream in the operation timeline."
              : "Manual run queued. Worker will execute and stream progress events.",
        });
        if (!dryRun) {
          setOperationToken(makeOperationToken());
          setOperationConfirmed(false);
          setConfirmationPhrase("");
        }
        await loadOperationRuns();
        await loadQueueThroughput();
        await loadQueueThroughputCompare(true);
        await loadQueueAutoscaling(true);
        await loadQueueGovernanceDigest(true);
        await loadQueueAudit(true);
        if (queuedRun?.id) {
          await loadOperationRunDetail(queuedRun.id, true);
        }
        await loadSchedules();
        await loadObservability();
        await loadObservabilityCompare();
        await refreshCompareDrilldown();
        await Promise.resolve(onRefresh?.());
      } catch (error) {
        notifications.show({
          color: "red",
          title: dryRun ? "Dry-run queue failed" : "Manual run queue failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setOperationExecuting(false);
      }
    },
    [
      apiUrl,
      confirmationPhrase,
      loadObservability,
      loadObservabilityCompare,
      refreshCompareDrilldown,
      loadOperationRunDetail,
      loadOperationRuns,
      loadQueueAutoscaling,
      loadQueueGovernanceDigest,
      loadQueueAudit,
      loadQueueThroughput,
      loadQueueThroughputCompare,
      loadSchedules,
      onRefresh,
      operationConfirmed,
      operationToken,
      projectId,
      reviewer,
      skipDueCheckForOps,
    ],
  );

  const saveQueueControls = useCallback(async () => {
    if (!projectId.trim()) {
      return;
    }
    setQueueControlsBusy(true);
    try {
      await apiFetch<{
        status: string;
        control: CalibrationQueueControl;
        throughput: CalibrationQueueThroughput;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/control", {
        method: "PUT",
        body: {
          project_id: projectId,
          worker_lag_sla_minutes: Math.max(1, Math.min(1440, Number(queueLagSlaMinutes || 20))),
          queue_depth_warn: Math.max(1, Math.min(50000, Number(queueDepthWarn || 12))),
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughput(),
        loadQueueThroughputCompare(true),
        loadQueueAutoscaling(true),
        loadQueueGovernanceDigest(true),
        loadQueueAudit(true),
      ]);
      notifications.show({
        color: "teal",
        title: "Queue controls saved",
        message: "Worker lag SLA and depth warning were updated.",
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Queue controls unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueControlsBusy(false);
    }
  }, [apiUrl, loadQueueAudit, loadQueueAutoscaling, loadQueueGovernanceDigest, loadQueueThroughput, loadQueueThroughputCompare, projectId, queueDepthWarn, queueLagSlaMinutes, reviewer]);

  const pauseQueue = useCallback(async () => {
    if (!projectId.trim()) {
      return;
    }
    setQueueControlsBusy(true);
    try {
      await apiFetch<{
        status: string;
        control: CalibrationQueueControl;
        throughput: CalibrationQueueThroughput;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/pause", {
        method: "POST",
        body: {
          project_id: projectId,
          pause_hours: Math.max(1, Math.min(168, Number(queuePauseHours || 1))),
          reason: queuePauseReason.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughput(),
        loadQueueThroughputCompare(true),
        loadQueueAutoscaling(true),
        loadQueueGovernanceDigest(true),
        loadQueueAudit(true),
        loadOperationRuns(),
      ]);
      notifications.show({
        color: "yellow",
        title: "Queue paused",
        message: "New queued runs will wait until pause window expires or manual resume.",
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Pause queue failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueControlsBusy(false);
    }
  }, [apiUrl, loadOperationRuns, loadQueueAudit, loadQueueAutoscaling, loadQueueGovernanceDigest, loadQueueThroughput, loadQueueThroughputCompare, projectId, queuePauseHours, queuePauseReason, reviewer]);

  const resumeQueue = useCallback(async () => {
    if (!projectId.trim()) {
      return;
    }
    setQueueControlsBusy(true);
    try {
      await apiFetch<{
        status: string;
        control: CalibrationQueueControl;
        throughput: CalibrationQueueThroughput;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/resume", {
        method: "POST",
        body: {
          project_id: projectId,
          reason: queuePauseReason.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughput(),
        loadQueueThroughputCompare(true),
        loadQueueAutoscaling(true),
        loadQueueGovernanceDigest(true),
        loadQueueAudit(true),
        loadOperationRuns(),
      ]);
      notifications.show({
        color: "teal",
        title: "Queue resumed",
        message: "Worker can pick queued calibration operations again.",
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Resume queue failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueControlsBusy(false);
    }
  }, [apiUrl, loadOperationRuns, loadQueueAudit, loadQueueAutoscaling, loadQueueGovernanceDigest, loadQueueThroughput, loadQueueThroughputCompare, projectId, queuePauseReason, reviewer]);

  const bulkPauseQueue = useCallback(async () => {
    const targets = (queueThroughputCompare?.projects ?? []).map((item) => item.project_id).filter(Boolean);
    if (targets.length === 0) {
      notifications.show({
        color: "orange",
        title: "No command-center projects",
        message: "Refresh queue command center and select project ids first.",
      });
      return;
    }
    setQueueBulkBusy(true);
    try {
      await apiFetch<{
        status: string;
        projects_total: number;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/bulk_pause", {
        method: "POST",
        body: {
          project_ids: targets,
          pause_hours: Math.max(1, Math.min(168, Number(queuePauseHours || 1))),
          reason: queuePauseReason.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughput(),
        loadQueueThroughputCompare(),
        loadQueueAutoscaling(),
        loadQueueGovernanceDigest(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
        loadOperationRuns(),
      ]);
      notifications.show({
        color: "yellow",
        title: "Bulk queue pause applied",
        message: `Paused ${targets.length} project queues.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Bulk pause failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueBulkBusy(false);
    }
  }, [
    apiUrl,
    loadOperationRuns,
    loadQueueAudit,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueThroughput,
    loadQueueThroughputCompare,
    queuePauseHours,
    queuePauseReason,
    queueThroughputCompare?.projects,
    reviewer,
  ]);

  const bulkResumeQueue = useCallback(async () => {
    const targets = (queueThroughputCompare?.projects ?? []).map((item) => item.project_id).filter(Boolean);
    if (targets.length === 0) {
      notifications.show({
        color: "orange",
        title: "No command-center projects",
        message: "Refresh queue command center and select project ids first.",
      });
      return;
    }
    setQueueBulkBusy(true);
    try {
      await apiFetch<{
        status: string;
        projects_total: number;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/bulk_resume", {
        method: "POST",
        body: {
          project_ids: targets,
          reason: queuePauseReason.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughput(),
        loadQueueThroughputCompare(),
        loadQueueAutoscaling(),
        loadQueueGovernanceDigest(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
        loadOperationRuns(),
      ]);
      notifications.show({
        color: "teal",
        title: "Bulk queue resume applied",
        message: `Resumed ${targets.length} project queues.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Bulk resume failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueBulkBusy(false);
    }
  }, [
    apiUrl,
    loadOperationRuns,
    loadQueueAudit,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueThroughput,
    loadQueueThroughputCompare,
    queuePauseReason,
    queueThroughputCompare?.projects,
    reviewer,
  ]);

  const exportQueueCommandCenterCsv = useCallback(async () => {
    setQueueExportBusy(true);
    try {
      const query = new URLSearchParams({
        window_hours: "24",
        limit: "30",
        format: "csv",
      });
      const requested = queueCompareProjectIds.trim();
      if (requested) {
        query.set("project_ids", requested);
      }
      const root = apiUrl.replace(/\/+$/, "");
      const response = await fetch(
        `${root}/v1/gatekeeper/calibration/operations/throughput/compare/export?${query.toString()}`,
        {
          method: "GET",
        },
      );
      const raw = await response.text();
      if (!response.ok) {
        throw new Error(`${response.status} ${raw}`);
      }
      const blob = new Blob([raw], { type: "text/csv;charset=utf-8" });
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      anchor.href = href;
      anchor.download = `synapse-queue-command-center-${stamp}.csv`;
      anchor.click();
      URL.revokeObjectURL(href);
      const lines = raw.trim() ? raw.trim().split(/\r?\n/).length - 1 : 0;
      notifications.show({
        color: "teal",
        title: "Queue CSV exported",
        message: `Exported ${Math.max(0, lines)} project rows.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "CSV export failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueExportBusy(false);
    }
  }, [apiUrl, queueCompareProjectIds]);

  const sendQueueCommandCenterWebhookSnapshot = useCallback(async () => {
    const requested = queueCompareProjectIds.trim();
    const targets = requested
      .split(",")
      .map((item) => item.trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    if (!queueWebhookUrl.trim()) {
      notifications.show({
        color: "orange",
        title: "Webhook URL required",
        message: "Provide webhook URL to send command-center snapshot.",
      });
      return;
    }
    setQueueExportBusy(true);
    try {
      await apiFetch<{
        status: string;
        channel: string;
        projects_total: number;
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/compare/export/webhook", {
        method: "POST",
        body: {
          webhook_url: queueWebhookUrl.trim(),
          requested_by: reviewer.trim() || "web_ui",
          project_ids: targets.length > 0 ? targets : null,
          window_hours: 24,
          limit: 30,
          include_csv: false,
          timeout_sec: 10,
        },
      });
      await Promise.all([
        loadQueueThroughputCompare(true),
        loadQueueAutoscaling(true),
        loadQueueGovernanceDigest(true),
        loadQueueOwnerRollups(true),
        loadQueueGovernanceDrift(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
        loadQueueIncidentHooks(true),
        loadQueueIncidentPolicies(true),
        loadQueueIncidentPreflightPresets(true),
        loadQueueIncidents(true),
      ]);
      notifications.show({
        color: "teal",
        title: "Queue snapshot delivered",
        message: `Webhook snapshot sent for ${targets.length > 0 ? targets.length : "active"} projects.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Webhook export failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueExportBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueOwnerRollups,
    loadQueueGovernanceDrift,
    loadQueueIncidentHooks,
    loadQueueIncidentPolicies,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidents,
    loadQueueThroughputCompare,
    queueCompareProjectIds,
    queueWebhookUrl,
    reviewer,
  ]);

  const saveQueueOwnershipRouting = useCallback(async () => {
    const targetProjectId = queueOwnerProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set target project id for ownership routing update.",
      });
      return;
    }
    setQueueOwnershipBusy(true);
    try {
      await apiFetch<{ status: string; ownership: CalibrationQueueOwnership }>(apiUrl, "/v1/gatekeeper/calibration/operations/ownership", {
        method: "PUT",
        body: {
          project_id: targetProjectId,
          owner_name: queueOwnerName.trim() || null,
          owner_contact: queueOwnerContact.trim() || null,
          oncall_channel: queueOncallChannel.trim() || null,
          escalation_channel: queueEscalationChannel.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      await Promise.all([
        loadQueueThroughputCompare(true),
        loadQueueAutoscaling(true),
        loadQueueGovernanceDigest(true),
        loadQueueOwnerRollups(true),
        loadQueueGovernanceDrift(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
        loadQueueIncidentHooks(true),
        loadQueueIncidentPolicies(true),
        loadQueueIncidentPreflightPresets(true),
        loadQueueIncidents(true),
      ]);
      notifications.show({
        color: "teal",
        title: "Ownership routing saved",
        message: `${targetProjectId}: queue ownership and escalation channels updated.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Ownership routing failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueOwnershipBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueAutoscaling,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueOwnerRollups,
    loadQueueGovernanceDrift,
    loadQueueIncidentHooks,
    loadQueueIncidentPolicies,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidents,
    loadQueueThroughputCompare,
    queueEscalationChannel,
    queueOncallChannel,
    queueOwnerContact,
    queueOwnerName,
    queueOwnerProjectId,
    reviewer,
  ]);

  const saveQueueIncidentHook = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set target project id for incident hook routing.",
      });
      return;
    }
    const openOn = queueIncidentOpenOnHealthCsv
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    const provider = (queueIncidentProvider || "webhook").toLowerCase();
    let providerConfig: Record<string, unknown> = {};
    if (provider === "webhook") {
      let headers: Record<string, string> = {};
      const rawHeaders = queueIncidentWebhookHeadersJson.trim();
      if (rawHeaders) {
        try {
          const parsed = JSON.parse(rawHeaders) as unknown;
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            headers = Object.entries(parsed).reduce<Record<string, string>>((acc, [key, value]) => {
              const name = String(key || "").trim();
              const val = String(value ?? "").trim();
              if (!name || !val) {
                return acc;
              }
              acc[name] = val;
              return acc;
            }, {});
          }
        } catch (error) {
          notifications.show({
            color: "orange",
            title: "Webhook headers JSON invalid",
            message: error instanceof Error ? error.message : String(error),
          });
          return;
        }
      }
      providerConfig = { headers };
      if (queueIncidentHookEnabled && !queueIncidentOpenWebhookUrl.trim()) {
        notifications.show({
          color: "orange",
          title: "Open webhook URL required",
          message: "Enabled webhook provider requires open webhook URL.",
        });
        return;
      }
    } else if (provider === "pagerduty") {
      providerConfig = {
        routing_key: queueIncidentPagerdutyRoutingKey.trim() || null,
        dedup_key_prefix: queueIncidentPagerdutyDedupPrefix.trim() || "synapse-queue",
      };
      if (queueIncidentHookEnabled && !queueIncidentPagerdutyRoutingKey.trim()) {
        notifications.show({
          color: "orange",
          title: "PagerDuty routing key required",
          message: "Enabled PagerDuty adapter requires routing key.",
        });
        return;
      }
    } else if (provider === "jira") {
      providerConfig = {
        base_url: queueIncidentJiraBaseUrl.trim() || null,
        project_key: queueIncidentJiraProjectKey.trim() || null,
        auth_mode: queueIncidentJiraAuthMode,
        email: queueIncidentJiraEmail.trim() || null,
        api_token: queueIncidentJiraApiToken.trim() || null,
        issue_type: queueIncidentJiraIssueType.trim() || "Incident",
        resolve_transition_id: queueIncidentJiraResolveTransitionId.trim() || null,
      };
      if (queueIncidentHookEnabled && !queueIncidentJiraBaseUrl.trim()) {
        notifications.show({
          color: "orange",
          title: "Jira base URL required",
          message: "Enabled Jira adapter requires base URL.",
        });
        return;
      }
      if (queueIncidentHookEnabled && !queueIncidentJiraProjectKey.trim()) {
        notifications.show({
          color: "orange",
          title: "Jira project key required",
          message: "Set Jira project key for issue creation.",
        });
        return;
      }
      if (queueIncidentHookEnabled && !queueIncidentJiraApiToken.trim()) {
        notifications.show({
          color: "orange",
          title: "Jira API token required",
          message: "Enabled Jira adapter requires API token.",
        });
        return;
      }
      if (queueIncidentHookEnabled && queueIncidentJiraAuthMode === "basic" && !queueIncidentJiraEmail.trim()) {
        notifications.show({
          color: "orange",
          title: "Jira email required",
          message: "Basic auth mode requires Jira email.",
        });
        return;
      }
      if (
        queueIncidentHookEnabled &&
        queueIncidentAutoResolve &&
        !queueIncidentJiraResolveTransitionId.trim() &&
        !queueIncidentResolveWebhookUrl.trim()
      ) {
        notifications.show({
          color: "orange",
          title: "Resolve path required",
          message: "Set Jira resolve transition id or resolve webhook URL.",
        });
        return;
      }
    } else {
      notifications.show({
        color: "orange",
        title: "Unsupported provider",
        message: `Provider "${provider}" is not supported.`,
      });
      return;
    }
    setQueueIncidentHookBusy(true);
    try {
      await apiFetch<{ status: string; hook: CalibrationQueueIncidentHook }>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/hooks",
        {
          method: "PUT",
          body: {
            project_id: targetProjectId,
            enabled: queueIncidentHookEnabled,
            provider,
            open_webhook_url: queueIncidentOpenWebhookUrl.trim() || null,
            resolve_webhook_url: queueIncidentResolveWebhookUrl.trim() || null,
            provider_config: providerConfig,
            open_on_health: openOn.length > 0 ? openOn : ["critical"],
            auto_resolve: queueIncidentAutoResolve,
            cooldown_minutes: Math.max(1, Math.min(1440, Math.trunc(Number(queueIncidentCooldownMinutes || 30)))),
            timeout_sec: Math.max(1, Math.min(60, Math.trunc(Number(queueIncidentTimeoutSec || 10)))),
            updated_by: reviewer.trim() || "web_ui",
          },
        },
      );
      await Promise.all([
        loadQueueIncidentHooks(true),
        loadQueueIncidentPolicies(true),
        loadQueueIncidentPreflightPresets(true),
        loadQueueIncidents(true),
        loadQueueThroughputCompare(true),
        loadQueueGovernanceDigest(true),
        loadQueueOwnerRollups(true),
        loadQueueGovernanceDrift(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
        loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true),
      ]);
      notifications.show({
        color: "teal",
        title: "Incident hook saved",
        message: `${targetProjectId}: queue incident auto-ticket hook updated.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Incident hook save failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentHookBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueGovernanceDrift,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueIncidentHooks,
    loadQueueIncidentPolicies,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidents,
    loadQueueOwnerRollups,
    loadQueueThroughputCompare,
    queueIncidentAutoResolve,
    queueIncidentCooldownMinutes,
    queueIncidentHookEnabled,
    queueIncidentJiraApiToken,
    queueIncidentJiraAuthMode,
    queueIncidentJiraBaseUrl,
    queueIncidentJiraEmail,
    queueIncidentJiraIssueType,
    queueIncidentJiraProjectKey,
    queueIncidentJiraResolveTransitionId,
    queueIncidentOpenOnHealthCsv,
    queueIncidentOpenWebhookUrl,
    queueIncidentPagerdutyDedupPrefix,
    queueIncidentPagerdutyRoutingKey,
    queueIncidentProvider,
    queueIncidentProjectId,
    queueIncidentResolveWebhookUrl,
    queueIncidentTimeoutSec,
    queueIncidentWebhookHeadersJson,
    reviewer,
  ]);

  const saveQueueIncidentPolicy = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set target project id for incident policy.",
      });
      return;
    }
    const alertCode = queueIncidentPolicyAlertCode.trim().toLowerCase();
    if (!alertCode) {
      notifications.show({
        color: "orange",
        title: "Alert code required",
        message: "Set alert code to route (for example: queue_depth_critical).",
      });
      return;
    }
    const severityByHealth: Record<string, string> = {};
    for (const token of queueIncidentPolicySeverityCsv.split(",")) {
      const [rawKey, rawValue] = token.split("=").map((item) => item.trim());
      if (!rawKey || !rawValue) {
        continue;
      }
      const key = rawKey.toLowerCase();
      if (!["healthy", "watch", "critical"].includes(key)) {
        continue;
      }
      severityByHealth[key] = rawValue;
    }
    const openOn = queueIncidentPolicyOpenOnHealthCsv
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    let providerConfigOverride: Record<string, unknown> = {};
    const rawConfig = queueIncidentPolicyConfigOverrideJson.trim();
    if (rawConfig) {
      try {
        const parsed = JSON.parse(rawConfig) as unknown;
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          providerConfigOverride = parsed as Record<string, unknown>;
        }
      } catch (error) {
        notifications.show({
          color: "orange",
          title: "Policy config JSON invalid",
          message: error instanceof Error ? error.message : String(error),
        });
        return;
      }
    }
    setQueueIncidentPolicyBusy(true);
    try {
      const providerOverride = queueIncidentPolicyProviderOverride === "inherit" ? null : queueIncidentPolicyProviderOverride;
      await apiFetch<{ status: string; policy: CalibrationQueueIncidentPolicy }>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/policies",
        {
          method: "PUT",
          body: {
            project_id: targetProjectId,
            alert_code: alertCode,
            enabled: queueIncidentPolicyEnabled,
            priority: Math.max(1, Math.min(1000, Math.trunc(Number(queueIncidentPolicyPriority || 100)))),
            provider_override: providerOverride,
            open_webhook_url: queueIncidentPolicyOpenWebhookUrl.trim() || null,
            resolve_webhook_url: queueIncidentPolicyResolveWebhookUrl.trim() || null,
            provider_config_override: providerConfigOverride,
            severity_by_health: severityByHealth,
            open_on_health: openOn,
            updated_by: reviewer.trim() || "web_ui",
          },
        },
      );
      await Promise.all([
        loadQueueIncidentPolicies(true),
        loadQueueIncidentHooks(true),
        loadQueueIncidentPreflightPresets(true),
        loadQueueIncidents(true),
        loadQueueThroughputCompare(true),
        loadQueueGovernanceDigest(true),
        loadQueueOwnerRollups(true),
        loadQueueGovernanceDrift(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
      ]);
      notifications.show({
        color: "teal",
        title: "Incident policy saved",
        message: `${targetProjectId}: ${alertCode} routing policy updated.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Incident policy save failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentPolicyBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueGovernanceDrift,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueIncidentHooks,
    loadQueueIncidentPolicies,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidents,
    loadQueueOwnerRollups,
    loadQueueThroughputCompare,
    queueIncidentPolicyAlertCode,
    queueIncidentPolicyConfigOverrideJson,
    queueIncidentPolicyEnabled,
    queueIncidentPolicyOpenOnHealthCsv,
    queueIncidentPolicyOpenWebhookUrl,
    queueIncidentPolicyPriority,
    queueIncidentPolicyProviderOverride,
    queueIncidentPolicyResolveWebhookUrl,
    queueIncidentPolicySeverityCsv,
    queueIncidentProjectId,
    reviewer,
  ]);

  const simulateQueueIncidentPolicyRoute = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set target project id for simulation.",
      });
      return;
    }
    const alertCode = queueIncidentPolicyAlertCode.trim().toLowerCase();
    if (!alertCode) {
      notifications.show({
        color: "orange",
        title: "Alert code required",
        message: "Set alert code to simulate policy routing.",
      });
      return;
    }
    const additionalAlertCodes = queueIncidentPolicySimulationAdditionalAlertCodesCsv
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter((item, index, all) => item.length > 0 && item !== alertCode && all.indexOf(item) === index);
    setQueueIncidentPolicySimulationBusy(true);
    try {
      const payload = await apiFetch<CalibrationQueueIncidentPolicySimulationPayload>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/policies/simulate",
        {
          method: "POST",
          body: {
            project_id: targetProjectId,
            alert_code: alertCode,
            health: queueIncidentPolicySimulationHealth,
            additional_alert_codes: additionalAlertCodes,
            include_secrets: false,
            actor: reviewer.trim() || "web_ui",
          },
        },
      );
      setQueueIncidentPolicySimulationResult(payload);
      await loadQueueAudit(true);
      notifications.show({
        color: payload.status === "ok" ? "teal" : "orange",
        title: payload.status === "ok" ? "Policy simulation complete" : "Policy simulation invalid",
        message: `${targetProjectId}: ${alertCode} on ${payload.health}.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Policy simulation failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentPolicySimulationBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    queueIncidentPolicyAlertCode,
    queueIncidentPolicySimulationAdditionalAlertCodesCsv,
    queueIncidentPolicySimulationHealth,
    queueIncidentProjectId,
    reviewer,
  ]);

  const saveQueueIncidentPreflightPreset = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set target project id for preflight preset.",
      });
      return;
    }
    const name = queueIncidentPreflightPresetName.trim();
    if (!name) {
      notifications.show({
        color: "orange",
        title: "Preset name required",
        message: "Set preset name to save incident preflight checks.",
      });
      return;
    }
    const alertCode = queueIncidentPreflightAlertCode.trim().toLowerCase();
    if (!alertCode) {
      notifications.show({
        color: "orange",
        title: "Alert code required",
        message: "Set primary alert code for preflight simulation.",
      });
      return;
    }
    const additionalAlertCodes = queueIncidentPreflightAdditionalAlertCodesCsv
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter((item, index, all) => item.length > 0 && item !== alertCode && all.indexOf(item) === index);
    const presetKeyRaw = queueIncidentPreflightPresetKey.trim().toLowerCase();
    setQueueIncidentPreflightPresetBusy(true);
    try {
      await apiFetch<{ status: string; preset: CalibrationQueueIncidentPreflightPreset }>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/preflight/presets",
        {
          method: "PUT",
          body: {
            project_id: targetProjectId,
            preset_key: presetKeyRaw || null,
            name,
            enabled: queueIncidentPreflightEnabled,
            alert_code: alertCode,
            health: queueIncidentPreflightHealth,
            additional_alert_codes: additionalAlertCodes,
            expected_decision: queueIncidentPreflightExpectedDecision,
            required_provider: queueIncidentPreflightRequiredProvider === "inherit" ? null : queueIncidentPreflightRequiredProvider,
            run_before_live_sync: queueIncidentPreflightRunBeforeLiveSync,
            severity: queueIncidentPreflightSeverity,
            strict_mode: queueIncidentPreflightStrictMode,
            updated_by: reviewer.trim() || "web_ui",
          },
        },
      );
      await Promise.all([loadQueueIncidentPreflightPresets(true), loadQueueAudit(true)]);
      notifications.show({
        color: "teal",
        title: "Preflight preset saved",
        message: `${targetProjectId}: ${name} is ready for queue incident preflight checks.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Preflight preset save failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentPreflightPresetBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueIncidentPreflightPresets,
    queueIncidentPreflightAdditionalAlertCodesCsv,
    queueIncidentPreflightAlertCode,
    queueIncidentPreflightEnabled,
    queueIncidentPreflightExpectedDecision,
    queueIncidentPreflightHealth,
    queueIncidentPreflightPresetKey,
    queueIncidentPreflightPresetName,
    queueIncidentPreflightRequiredProvider,
    queueIncidentPreflightRunBeforeLiveSync,
    queueIncidentPreflightSeverity,
    queueIncidentPreflightStrictMode,
    queueIncidentProjectId,
    reviewer,
  ]);

  const runQueueIncidentPreflightChecks = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    const requestedProjects = queueCompareProjectIds
      .split(",")
      .map((item) => item.trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    if (requestedProjects.length === 0 && !targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project id required",
        message: "Set project id (or compare project list) to run preflight checks.",
      });
      return;
    }
    setQueueIncidentPreflightRunBusy(true);
    try {
      const payload = await apiFetch<CalibrationQueueIncidentPreflightRunPayload>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/preflight/run",
        {
          method: "POST",
          body: {
            project_id: requestedProjects.length === 0 ? targetProjectId : null,
            project_ids: requestedProjects.length > 0 ? requestedProjects : null,
            include_disabled: queueIncidentPreflightIncludeDisabled,
            include_run_before_live_sync_only: queueIncidentPreflightRunBeforeSyncOnly,
            actor: reviewer.trim() || "web_ui",
            record_audit: queueIncidentPreflightRecordAudit,
            limit: 100,
          },
        },
      );
      setQueueIncidentPreflightRunResult(payload);
      await Promise.all([loadQueueAudit(true), loadQueueIncidentPreflightPresets(true)]);
      notifications.show({
        color: Number(payload.summary.failed || 0) > 0 ? "orange" : "teal",
        title: Number(payload.summary.failed || 0) > 0 ? "Preflight checks found issues" : "Preflight checks passed",
        message: `checks ${payload.summary.checks_total}, failed ${payload.summary.failed}, critical alerts ${payload.summary.alerts_by_severity.critical}`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Preflight run failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentPreflightRunBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueIncidentPreflightPresets,
    queueCompareProjectIds,
    queueIncidentPreflightIncludeDisabled,
    queueIncidentPreflightRecordAudit,
    queueIncidentPreflightRunBeforeSyncOnly,
    queueIncidentProjectId,
    reviewer,
  ]);

  const saveQueueIncidentSyncEnforcement = useCallback(async () => {
    const targetProjectId = queueIncidentProjectId.trim();
    if (!targetProjectId) {
      notifications.show({
        color: "orange",
        title: "Project is required",
        message: "Set project id to update live sync preflight enforcement mode.",
      });
      return;
    }
    setQueueIncidentSyncEnforcementBusy(true);
    try {
      await apiFetch<{ status: string; control: CalibrationQueueControl }>(
        apiUrl,
        "/v1/gatekeeper/calibration/operations/incidents/sync/enforcement",
        {
          method: "PUT",
          body: {
            project_id: targetProjectId,
            incident_preflight_enforcement_mode: queueIncidentSyncEnforcementMode,
            incident_preflight_pause_hours: Math.max(1, Math.min(168, Number(queueIncidentSyncEnforcementPauseHours || 4))),
            incident_preflight_critical_fail_threshold: Math.max(
              1,
              Math.min(100, Number(queueIncidentSyncEnforcementCriticalThreshold || 1)),
            ),
            updated_by: reviewer.trim() || "web_ui",
          },
        },
      );
      await Promise.all([loadQueueThroughput(true), loadQueueThroughputCompare(true), loadQueueAudit(true)]);
      notifications.show({
        color: "teal",
        title: "Sync enforcement saved",
        message: `${targetProjectId}: mode ${queueIncidentSyncEnforcementMode}, pause ${queueIncidentSyncEnforcementPauseHours}h, threshold ${queueIncidentSyncEnforcementCriticalThreshold}.`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Sync enforcement save failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentSyncEnforcementBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueThroughput,
    loadQueueThroughputCompare,
    queueIncidentProjectId,
    queueIncidentSyncEnforcementCriticalThreshold,
    queueIncidentSyncEnforcementMode,
    queueIncidentSyncEnforcementPauseHours,
    reviewer,
  ]);

  const syncQueueIncidentHooks = useCallback(async () => {
    const requested = queueCompareProjectIds.trim();
    const targets = requested
      .split(",")
      .map((item) => item.trim())
      .filter((item, index, all) => item.length > 0 && all.indexOf(item) === index);
    setQueueIncidentSyncBusy(true);
    try {
      const payload = await apiFetch<{
        summary: { opened: number; resolved: number; failed: number; noop: number; blocked?: number; paused?: number };
      }>(apiUrl, "/v1/gatekeeper/calibration/operations/incidents/sync", {
        method: "POST",
        body: {
          project_ids: targets.length > 0 ? targets : null,
          actor: reviewer.trim() || "web_ui",
          window_hours: 24,
          dry_run: false,
          force_resolve: false,
          preflight_enforcement_mode: "inherit",
          preflight_include_run_before_live_sync_only: true,
          preflight_record_audit: queueIncidentPreflightRecordAudit,
          limit: 50,
        },
      });
      await Promise.all([
        loadQueueIncidentPolicies(true),
        loadQueueIncidentPreflightPresets(true),
        loadQueueIncidentSyncSchedules(true),
        loadQueueIncidentSyncScheduleFleet(true),
        loadQueueIncidents(true),
        loadQueueThroughputCompare(true),
        loadQueueGovernanceDigest(true),
        loadQueueOwnerRollups(true),
        loadQueueGovernanceDrift(true),
        loadQueueIncidentSloBoard(true),
        loadQueueAudit(true),
      ]);
      notifications.show({
        color: payload.summary.failed > 0 || Number(payload.summary.blocked || 0) > 0 || Number(payload.summary.paused || 0) > 0 ? "orange" : "teal",
        title: "Incident hooks synced",
        message: `opened ${payload.summary.opened}, resolved ${payload.summary.resolved}, failed ${payload.summary.failed}, blocked ${Number(payload.summary.blocked || 0)}, paused ${Number(payload.summary.paused || 0)}`,
      });
    } catch (error) {
      notifications.show({
        color: "orange",
        title: "Incident sync failed",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setQueueIncidentSyncBusy(false);
    }
  }, [
    apiUrl,
    loadQueueAudit,
    loadQueueGovernanceDrift,
    loadQueueGovernanceDigest,
    loadQueueIncidentSloBoard,
    loadQueueIncidentSyncSchedules,
    loadQueueIncidentSyncScheduleFleet,
    loadQueueIncidentSyncScheduleTimeline,
    loadQueueIncidentPreflightPresets,
    loadQueueIncidentPolicies,
    loadQueueIncidents,
    loadQueueOwnerRollups,
    loadQueueThroughputCompare,
    queueCompareProjectIds,
    queueIncidentPreflightRecordAudit,
    queueIncidentSyncScheduleTimelineScheduleId,
    reviewer,
  ]);

  const annotateQueueAuditEvent = useCallback(
    async (event: CalibrationQueueAuditPayload["events"][number], mode: "acknowledge" | "resolve") => {
      if (!event?.id || !event.project_id) {
        return;
      }
      const busyKey = `${mode}:${event.id}`;
      setQueueAuditActionBusyId(busyKey);
      try {
        await apiFetch<{ status: string }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/throughput/audit/${encodeURIComponent(String(event.id))}/${mode}`,
          {
            method: "POST",
            body: {
              project_id: event.project_id,
              created_by: reviewer.trim() || "web_ui",
              note: mode === "resolve" ? "resolved_from_queue_audit_panel" : "acknowledged_from_queue_audit_panel",
              follow_up_owner: queueOwnerName.trim() || null,
            },
          },
        );
        await loadQueueAudit(true);
        await loadQueueGovernanceDigest(true);
        notifications.show({
          color: mode === "resolve" ? "teal" : "blue",
          title: mode === "resolve" ? "Audit event resolved" : "Audit event acknowledged",
          message: `${event.project_id} • ${event.action} • event #${event.id}`,
        });
      } catch (error) {
        notifications.show({
          color: "orange",
          title: mode === "resolve" ? "Resolve failed" : "Acknowledge failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setQueueAuditActionBusyId(null);
      }
    },
    [apiUrl, loadQueueAudit, loadQueueGovernanceDigest, queueOwnerName, reviewer],
  );

  const applyQueueRecommendation = useCallback(
    async (item: CalibrationQueueAutoscalingRecommendation) => {
      const targetProjectId = item.project_id.trim();
      if (!targetProjectId) {
        return;
      }
      setQueueRecommendationBusyProjectId(targetProjectId);
      try {
        await apiFetch<{
          status: string;
          project_id: string;
          applied: {
            worker_lag_sla_minutes: number;
            queue_depth_warn: number;
          };
        }>(apiUrl, "/v1/gatekeeper/calibration/operations/throughput/recommendations/apply", {
          method: "POST",
          body: {
            project_id: targetProjectId,
            updated_by: reviewer.trim() || "web_ui",
            window_hours: item.window_hours || 24,
            history_hours: item.history_hours || 72,
            apply_worker_lag_sla: true,
            apply_queue_depth_warn: true,
            reason: "applied_from_autoscaling_panel",
          },
        });
        await Promise.all([
          loadQueueThroughput(true),
          loadQueueThroughputCompare(true),
          loadQueueAutoscaling(true),
          loadQueueGovernanceDigest(true),
          loadQueueAudit(true),
          loadOperationRuns(true),
        ]);
        notifications.show({
          color: "teal",
          title: "Recommendation applied",
          message: `${targetProjectId}: queue controls updated from autoscaling recommendation.`,
        });
      } catch (error) {
        notifications.show({
          color: "orange",
          title: "Apply recommendation failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setQueueRecommendationBusyProjectId(null);
      }
    },
    [apiUrl, loadOperationRuns, loadQueueAudit, loadQueueAutoscaling, loadQueueGovernanceDigest, loadQueueThroughput, loadQueueThroughputCompare, projectId, reviewer],
  );

  const cancelOperationRun = useCallback(
    async (run: CalibrationOperationRun) => {
      if (!projectId.trim()) {
        return;
      }
      setOperationActionLoading(run.id);
      try {
        await apiFetch<{ status: string; run: CalibrationOperationRun }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/runs/${encodeURIComponent(run.id)}/cancel`,
          {
            method: "POST",
            body: {
              project_id: projectId,
              requested_by: reviewer.trim() || "web_ui",
              reason: "cancelled_from_dashboard",
            },
          },
        );
        notifications.show({
          color: "orange",
          title: "Cancel requested",
          message: `Run ${run.id.slice(0, 8)} moved to cancel flow.`,
        });
        await loadOperationRuns(true);
        await loadQueueThroughput(true);
        await loadQueueThroughputCompare(true);
        await loadQueueAutoscaling(true);
        await loadQueueGovernanceDigest(true);
        await loadQueueAudit(true);
        if (selectedOperationRunId === run.id) {
          await loadOperationRunDetail(run.id, true);
        }
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Cancel failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setOperationActionLoading(null);
      }
    },
    [apiUrl, loadOperationRunDetail, loadOperationRuns, loadQueueAudit, loadQueueAutoscaling, loadQueueGovernanceDigest, loadQueueThroughput, loadQueueThroughputCompare, projectId, reviewer, selectedOperationRunId],
  );

  const retryOperationRun = useCallback(
    async (run: CalibrationOperationRun) => {
      if (!projectId.trim()) {
        return;
      }
      setOperationActionLoading(run.id);
      try {
        const retryToken = run.dry_run ? null : `${operationToken.trim()}-r${Date.now().toString(36)}`;
        const payload = await apiFetch<{ status: string; run: CalibrationOperationRun }>(
          apiUrl,
          `/v1/gatekeeper/calibration/operations/runs/${encodeURIComponent(run.id)}/retry`,
          {
            method: "POST",
            body: {
              project_id: projectId,
              requested_by: reviewer.trim() || "web_ui",
              operation_token: retryToken,
              confirm: run.dry_run ? false : operationConfirmed,
              confirmation_phrase: run.dry_run ? null : confirmationPhrase.trim() || null,
              force_run: true,
              skip_due_check: skipDueCheckForOps,
            },
          },
        );
        const queuedRun = payload.run;
        if (queuedRun?.id) {
          setSelectedOperationRunId(queuedRun.id);
          await loadOperationRunDetail(queuedRun.id, true);
        }
        notifications.show({
          color: "teal",
          title: "Retry queued",
          message: `Retry created for run ${run.id.slice(0, 8)}.`,
        });
        await loadOperationRuns(true);
        await loadQueueThroughput(true);
        await loadQueueThroughputCompare(true);
        await loadQueueAutoscaling(true);
        await loadQueueGovernanceDigest(true);
        await loadQueueAudit(true);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Retry failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setOperationActionLoading(null);
      }
    },
    [
      apiUrl,
      confirmationPhrase,
      loadOperationRunDetail,
      loadOperationRuns,
      loadQueueAudit,
      loadQueueAutoscaling,
      loadQueueGovernanceDigest,
      loadQueueThroughput,
      loadQueueThroughputCompare,
      operationConfirmed,
      operationToken,
      projectId,
      reviewer,
      skipDueCheckForOps,
    ],
  );

  const applyPresetDefaults = useCallback((preset: "nightly" | "weekly") => {
    const profile = PRESET_CONFIGS[preset];
    setForm((prev) => ({
      ...prev,
      preset,
      interval_hours: profile.interval_hours,
      lookback_days: profile.lookback_days,
      limit_rows: profile.limit_rows,
      holdout_ratio: profile.holdout_ratio,
      top_k: profile.top_k,
      weights: profile.weights,
      confidences: profile.confidences,
      score_thresholds: profile.score_thresholds,
    }));
  }, []);

  const startEdit = useCallback((schedule: GatekeeperCalibrationSchedule) => {
    setEditingScheduleId(schedule.id);
    setForm({
      name: schedule.name,
      enabled: schedule.enabled,
      preset: schedule.preset === "weekly" ? "weekly" : "nightly",
      interval_hours: schedule.interval_hours,
      lookback_days: schedule.lookback_days,
      limit_rows: schedule.limit_rows,
      holdout_ratio: schedule.holdout_ratio,
      split_seed: schedule.split_seed,
      weights: (schedule.weights ?? []).join(","),
      confidences: (schedule.confidences ?? []).join(","),
      score_thresholds: (schedule.score_thresholds ?? []).join(","),
      top_k: schedule.top_k,
      allow_guardrail_fail: schedule.allow_guardrail_fail,
      snapshot_note: schedule.snapshot_note ?? "",
    });
  }, []);

  const resetForm = useCallback(() => {
    setEditingScheduleId(null);
    setForm(DEFAULT_FORM);
  }, []);

  const saveSchedule = useCallback(async () => {
    if (!projectId.trim()) {
      return;
    }
    const errors = validateForm(form);
    if (errors.length > 0) {
      notifications.show({
        color: "orange",
        title: "Schedule validation failed",
        message: errors[0],
      });
      return;
    }
    const weights = parseThresholdCsv(form.weights).values;
    const confidences = parseThresholdCsv(form.confidences).values;
    const scoreThresholds = parseThresholdCsv(form.score_thresholds).values;
    setSavingSchedule(true);
    try {
      await apiFetch<{ status: string; schedule: GatekeeperCalibrationSchedule }>(apiUrl, "/v1/gatekeeper/calibration/schedules", {
        method: "PUT",
        body: {
          project_id: projectId,
          name: form.name.trim(),
          enabled: form.enabled,
          preset: form.preset,
          interval_hours: form.interval_hours,
          lookback_days: form.lookback_days,
          limit_rows: form.limit_rows,
          holdout_ratio: form.holdout_ratio,
          split_seed: form.split_seed.trim(),
          weights,
          confidences,
          score_thresholds: scoreThresholds,
          top_k: form.top_k,
          allow_guardrail_fail: form.allow_guardrail_fail,
          snapshot_note: form.snapshot_note.trim() || null,
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      notifications.show({
        color: "teal",
        title: editingScheduleId ? "Schedule updated" : "Schedule created",
        message: `Calibration schedule ${form.name.trim()} saved.`,
      });
      resetForm();
      await loadSchedules();
      await loadObservability();
      await loadObservabilityCompare();
      await refreshCompareDrilldown();
      await Promise.resolve(onRefresh?.());
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Could not save schedule",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSavingSchedule(false);
    }
  }, [
    apiUrl,
    editingScheduleId,
    form,
    loadObservability,
    loadObservabilityCompare,
    refreshCompareDrilldown,
    loadSchedules,
    onRefresh,
    projectId,
    resetForm,
    reviewer,
  ]);

  const deleteSchedule = useCallback(
    async (schedule: GatekeeperCalibrationSchedule) => {
      if (!projectId.trim()) {
        return;
      }
      setDeletingScheduleId(schedule.id);
      try {
        await apiFetch<{ status: string }>(
          apiUrl,
          `/v1/gatekeeper/calibration/schedules/${encodeURIComponent(schedule.id)}?project_id=${encodeURIComponent(projectId)}`,
          {
            method: "DELETE",
          },
        );
        notifications.show({
          color: "teal",
          title: "Schedule deleted",
          message: `${schedule.name} removed.`,
        });
        if (editingScheduleId === schedule.id) {
          resetForm();
        }
        await loadSchedules();
        await loadObservability();
        await loadObservabilityCompare();
        await refreshCompareDrilldown();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Could not delete schedule",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setDeletingScheduleId(null);
      }
    },
    [apiUrl, editingScheduleId, loadObservability, loadObservabilityCompare, loadSchedules, projectId, refreshCompareDrilldown, resetForm],
  );

  const activePreset = PRESET_CONFIGS[form.preset];
  const validationErrors = useMemo(() => validateForm(form), [form]);
  const effectiveInterval = form.interval_hours ?? activePreset.interval_hours;
  const operationSummary =
    operationResult?.summary && typeof operationResult.summary === "object"
      ? (operationResult.summary as CalibrationOperationSummary)
      : null;
  const operationRows = Array.isArray(operationSummary?.results) ? operationSummary.results : [];
  const expectedConfirmationPhrase = projectId.trim() ? `RUN ${projectId.trim()}` : "RUN <project_id>";
  const liveRunUnlocked =
    projectId.trim().length > 0 &&
    operationConfirmed &&
    confirmationPhrase.trim() === expectedConfirmationPhrase &&
    operationToken.trim().length >= 8;
  const queueRows = operationRuns.slice(0, 10);
  const selectedQueueRun =
    selectedOperationRun ??
    (selectedOperationRunId ? operationRuns.find((item) => item.id === selectedOperationRunId) ?? null : null);
  const selectedQueueRunTerminal = selectedQueueRun ? ["succeeded", "failed", "canceled"].includes(selectedQueueRun.status) : true;
  const observabilityRows = Array.isArray(observability?.schedules) ? observability.schedules : [];
  const compareRows = Array.isArray(observabilityCompare?.projects) ? observabilityCompare.projects : [];
  const queueCommandCenterRows = Array.isArray(queueThroughputCompare?.projects) ? queueThroughputCompare.projects : [];
  const queueCommandCenterByProjectId = useMemo(() => {
    const mapping = new Map<string, CalibrationQueueThroughput>();
    for (const item of queueCommandCenterRows) {
      const projectKey = String(item?.project_id || "").trim();
      if (!projectKey) {
        continue;
      }
      mapping.set(projectKey, item);
    }
    return mapping;
  }, [queueCommandCenterRows]);
  const queueCommandCenterEnforcementSummary = useMemo(
    () =>
      queueCommandCenterRows.reduce(
        (acc, item) => {
          const mode = normalizeIncidentPreflightEnforcementMode(item.control?.incident_preflight_enforcement_mode);
          acc[mode] += 1;
          return acc;
        },
        { off: 0, block: 0, pause: 0 } as Record<"off" | "block" | "pause", number>,
      ),
    [queueCommandCenterRows],
  );
  const queueAutoscalingRows = Array.isArray(queueAutoscaling?.recommendations) ? queueAutoscaling.recommendations : [];
  const queueDigestTopCongestion = Array.isArray(queueGovernanceDigest?.top_congestion) ? queueGovernanceDigest.top_congestion : [];
  const queueDigestUnreviewedPauses = Array.isArray(queueGovernanceDigest?.unreviewed_pauses)
    ? queueGovernanceDigest.unreviewed_pauses
    : [];
  const queueEscalationCandidates = Array.isArray(queueIncidentEscalationDigest?.escalation_candidates)
    ? queueIncidentEscalationDigest.escalation_candidates
    : [];
  const queueEscalationOwnershipGaps = Array.isArray(queueIncidentEscalationDigest?.ownership_gaps)
    ? queueIncidentEscalationDigest.ownership_gaps
    : [];
  const queueEscalationAges = queueIncidentEscalationDigest?.age_buckets ?? {
    under_1h: 0,
    between_1h_4h: 0,
    between_4h_12h: 0,
    between_12h_24h: 0,
    between_24h_72h: 0,
    over_72h: 0,
    unknown: 0,
  };
  const queueEscalationAgeTotal = Math.max(
    1,
    queueEscalationAges.under_1h +
      queueEscalationAges.between_1h_4h +
      queueEscalationAges.between_4h_12h +
      queueEscalationAges.between_12h_24h +
      queueEscalationAges.between_24h_72h +
      queueEscalationAges.over_72h +
      queueEscalationAges.unknown,
  );
  const queueIncidentHookRows = Array.isArray(queueIncidentHooks?.hooks) ? queueIncidentHooks.hooks : [];
  const queueIncidentPolicyRows = Array.isArray(queueIncidentPolicies?.policies) ? queueIncidentPolicies.policies : [];
  const queueIncidentPreflightRows = Array.isArray(queueIncidentPreflightPresets?.presets)
    ? queueIncidentPreflightPresets.presets
    : [];
  const queueIncidentSyncScheduleRows = Array.isArray(queueIncidentSyncSchedules?.schedules)
    ? queueIncidentSyncSchedules.schedules
    : [];
  const queueIncidentSyncScheduleTargetProjectId = queueIncidentProjectId.trim() || projectId.trim();
  const queueIncidentSyncScheduleProjectRows = queueIncidentSyncScheduleRows.filter(
    (item) => item.project_id === queueIncidentSyncScheduleTargetProjectId,
  );
  const queueIncidentSyncScheduleStatusSummary = queueIncidentSyncScheduleProjectRows.reduce(
    (acc, item) => {
      const key = String(item.last_status || "never").trim().toLowerCase();
      if (key === "ok") acc.ok += 1;
      else if (key === "partial_failure") acc.partial_failure += 1;
      else if (key === "failed") acc.failed += 1;
      else if (key === "skipped") acc.skipped += 1;
      else acc.never += 1;
      return acc;
    },
    { ok: 0, partial_failure: 0, failed: 0, skipped: 0, never: 0 },
  );
  const queueIncidentSyncScheduleDueRows = queueIncidentSyncScheduleProjectRows.filter((item) => {
    if (!item.enabled || !item.next_run_at) {
      return false;
    }
    const ts = new Date(item.next_run_at).getTime();
    return Number.isFinite(ts) && ts <= Date.now();
  });
  const queueIncidentSyncScheduleHeatmapRows = useMemo(() => {
    const byHour = new Map<number, { hour: string; runs: number; failed: number; partial_failure: number }>();
    for (let hour = 0; hour < 24; hour += 1) {
      byHour.set(hour, { hour: `${String(hour).padStart(2, "0")}:00`, runs: 0, failed: 0, partial_failure: 0 });
    }
    for (const schedule of queueIncidentSyncScheduleProjectRows) {
      if (!schedule.last_run_at) {
        continue;
      }
      const date = new Date(schedule.last_run_at);
      const hour = date.getHours();
      const bucket = byHour.get(hour);
      if (!bucket) {
        continue;
      }
      bucket.runs += 1;
      const status = String(schedule.last_status || "").trim().toLowerCase();
      if (status === "failed") {
        bucket.failed += 1;
      } else if (status === "partial_failure") {
        bucket.partial_failure += 1;
      }
    }
    return Array.from(byHour.values());
  }, [queueIncidentSyncScheduleProjectRows]);
  const queueIncidentSyncScheduleFleetRows = Array.isArray(queueIncidentSyncScheduleFleetPayload?.schedules)
    ? queueIncidentSyncScheduleFleetPayload.schedules
    : [];
  const queueIncidentSyncScheduleFleetPaging = queueIncidentSyncScheduleFleetPayload?.paging ?? {
    limit: Math.max(10, Math.min(200, Number(queueIncidentSyncScheduleFleetPageSize || 25))),
    offset: Math.max(0, (Math.max(1, Number(queueIncidentSyncScheduleFleetPage || 1)) - 1) * Number(queueIncidentSyncScheduleFleetPageSize || 25)),
    has_more: false,
    total: queueIncidentSyncScheduleFleetRows.length,
  };
  const queueIncidentSyncScheduleFleetPageSizeNormalized = Math.max(
    10,
    Math.min(200, Number(queueIncidentSyncScheduleFleetPaging.limit || queueIncidentSyncScheduleFleetPageSize || 25)),
  );
  const queueIncidentSyncScheduleFleetTotal = Math.max(
    0,
    Number(
      queueIncidentSyncScheduleFleetPaging.total == null
        ? queueIncidentSyncScheduleFleetRows.length
        : queueIncidentSyncScheduleFleetPaging.total,
    ),
  );
  const queueIncidentSyncScheduleFleetTotalPages = Math.max(
    1,
    Math.ceil(queueIncidentSyncScheduleFleetTotal / queueIncidentSyncScheduleFleetPageSizeNormalized),
  );
  const queueIncidentSyncScheduleFleetCurrentPage = Math.max(
    1,
    Math.min(queueIncidentSyncScheduleFleetPage, queueIncidentSyncScheduleFleetTotalPages),
  );
  const queueIncidentSyncScheduleFleetStartIndex = Math.max(0, Number(queueIncidentSyncScheduleFleetPaging.offset || 0));
  const queueIncidentSyncScheduleFleetPagedRows = queueIncidentSyncScheduleFleetRows;
  const queueIncidentSyncScheduleFleetHasMore = Boolean(queueIncidentSyncScheduleFleetPaging.has_more);
  const queueIncidentSyncScheduleFleetRangeStart =
    queueIncidentSyncScheduleFleetTotal === 0 ? 0 : queueIncidentSyncScheduleFleetStartIndex + 1;
  const queueIncidentSyncScheduleFleetRangeEnd = Math.min(
    queueIncidentSyncScheduleFleetTotal,
    queueIncidentSyncScheduleFleetStartIndex + queueIncidentSyncScheduleFleetPagedRows.length,
  );
  const queueAuditEventsById = useMemo(() => {
    const mapping = new Map<number, CalibrationQueueAuditPayload["events"][number]>();
    for (const event of queueAudit?.events ?? []) {
      if (Number.isFinite(Number(event.id))) {
        mapping.set(Number(event.id), event);
      }
    }
    return mapping;
  }, [queueAudit]);
  const queueIncidentSyncScheduleRunRows = Array.isArray(queueIncidentSyncScheduleRunResult?.results)
    ? queueIncidentSyncScheduleRunResult.results
    : [];
  const queueIncidentSyncScheduleSelectedRunRow =
    queueIncidentSyncScheduleRunSelectedScheduleId == null
      ? queueIncidentSyncScheduleRunRows[0] ?? null
      : queueIncidentSyncScheduleRunRows.find((item) => item.schedule_id === queueIncidentSyncScheduleRunSelectedScheduleId) ??
        queueIncidentSyncScheduleRunRows[0] ??
        null;
  const queueIncidentSyncScheduleSelectedRunAuditEvent =
    queueIncidentSyncScheduleSelectedRunRow?.audit_event_id != null
      ? queueAuditEventsById.get(Number(queueIncidentSyncScheduleSelectedRunRow.audit_event_id)) ?? null
      : null;
  const queueIncidentSyncScheduleTimelineSummary = queueIncidentSyncScheduleTimeline?.summary ?? {
    runs_total: 0,
    ok: 0,
    partial_failure: 0,
    failed: 0,
    skipped: 0,
    unknown: 0,
    latest_status: null,
    latest_run_at: null,
  };
  const queueIncidentSyncScheduleTimelineTrendRows = Array.isArray(queueIncidentSyncScheduleTimeline?.trend)
    ? queueIncidentSyncScheduleTimeline.trend.map((item) => ({
        ...item,
        day_label: String(item.day || "").slice(5),
      }))
    : [];
  const queueIncidentSyncScheduleTimelineFailureRows = Array.isArray(queueIncidentSyncScheduleTimeline?.failure_classes)
    ? queueIncidentSyncScheduleTimeline.failure_classes
    : [];
  const queueIncidentSyncScheduleTimelineRuns = Array.isArray(queueIncidentSyncScheduleTimeline?.runs)
    ? queueIncidentSyncScheduleTimeline.runs
    : [];
  const queueIncidentPreflightRunSummary = queueIncidentPreflightRunResult?.summary ?? {
    projects_total: 0,
    presets_total: 0,
    checks_total: 0,
    passed: 0,
    failed: 0,
    alerts_total: 0,
    alerts_by_severity: { info: 0, warning: 0, critical: 0 },
  };
  const queueIncidentPreflightAlertRows = Array.isArray(queueIncidentPreflightRunResult?.alerts)
    ? queueIncidentPreflightRunResult.alerts
    : [];
  const queueIncidentPreflightRollupRows = Array.isArray(queueIncidentPreflightRunResult?.project_rollups)
    ? queueIncidentPreflightRunResult.project_rollups
    : [];
  const queueIncidentRows = Array.isArray(queueIncidents?.incidents) ? queueIncidents.incidents : [];
  const queueOpenIncidentRows = queueIncidentRows.filter((item) => item.status === "open");
  const queueIncidentPolicySimulationTraceRows = Array.isArray(queueIncidentPolicySimulationResult?.route_trace?.candidate_policies)
    ? queueIncidentPolicySimulationResult.route_trace.candidate_policies
    : [];
  const queueIncidentSloRows = Array.isArray(queueIncidentSloBoard?.leaderboard) ? queueIncidentSloBoard.leaderboard : [];
  const queueIncidentSloTrendRows = Array.isArray(queueIncidentSloBoard?.trends)
    ? queueIncidentSloBoard.trends.map((item) => ({
        day: String(item.day || "").slice(5),
        opened_incidents: Number(item.opened_incidents || 0),
        resolved_incidents: Number(item.resolved_incidents || 0),
        mtta_proxy_minutes_p90: item.mtta_proxy_minutes_p90 == null ? 0 : Number(item.mtta_proxy_minutes_p90),
        mttr_minutes_p90: item.mttr_minutes_p90 == null ? 0 : Number(item.mttr_minutes_p90),
      }))
    : [];
  const queueIncidentSloSummary = queueIncidentSloBoard?.summary ?? {
    projects_total: 0,
    open_incidents: 0,
    open_incidents_over_mttr_sla: 0,
    resolved_incidents_window: 0,
    mtta_proxy_minutes: { count: 0, avg: null, p50: null, p90: null },
    mttr_minutes: { count: 0, avg: null, p50: null, p90: null },
    projects_mtta_over_sla: 0,
    projects_mttr_over_sla: 0,
    rotation_lag_projects_over_sla: 0,
    secret_required_total: 0,
    secret_missing_required: 0,
    secret_stale_required: 0,
    secret_posture: { healthy: 0, watch: 0, critical: 0 },
    slo_status: { healthy: 0, watch: 0, critical: 0 },
  };
  const queueIncidentSloSecretPostureRows = [
    { posture: "healthy", projects: Number(queueIncidentSloSummary.secret_posture.healthy || 0) },
    { posture: "watch", projects: Number(queueIncidentSloSummary.secret_posture.watch || 0) },
    { posture: "critical", projects: Number(queueIncidentSloSummary.secret_posture.critical || 0) },
  ];

  return (
    <Paper withBorder radius="md" p="sm" mb="md">
      <Group justify="space-between" align="center" mb={8}>
        <Stack gap={2}>
          <Text fw={700}>Calibration Schedule Management</Text>
          <Text size="xs" c="dimmed">
            Configure nightly/weekly calibration jobs with validated parameter grids and run cadence previews.
          </Text>
        </Stack>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconRefresh size={14} />}
          loading={loadingSchedules}
          onClick={() =>
            void Promise.all([
              loadSchedules(),
              loadObservability(),
              loadObservabilityCompare(),
              refreshCompareDrilldown(),
              loadOperationRuns(),
              loadQueueThroughput(),
              loadQueueThroughputCompare(),
              loadQueueAutoscaling(),
              loadQueueGovernanceDigest(),
              loadQueueIncidentEscalationDigest(),
              loadQueueOwnerRollups(),
              loadQueueGovernanceDrift(),
              loadQueueIncidentSloBoard(),
              loadQueueAudit(),
              loadQueueIncidentHooks(),
              loadQueueIncidentPolicies(),
              loadQueueIncidentPreflightPresets(),
              loadQueueIncidents(),
            ])
          }
          disabled={!projectId.trim()}
        >
          Refresh schedules
        </Button>
      </Group>

      <Paper withBorder radius="md" p="xs" mb="sm">
        <Group justify="space-between" align="start" mb={6}>
          <Stack gap={2}>
            <Text fw={700}>Calibration Operations</Text>
            <Text size="xs" c="dimmed">
              Manual trigger, due-state preview, and exact scheduler command preview for production execution.
            </Text>
          </Stack>
          <Switch
            size="sm"
            label="Skip due-check"
            checked={skipDueCheckForOps}
            onChange={(event) => setSkipDueCheckForOps(event.currentTarget.checked)}
          />
        </Group>

        <Group gap={8} mb={8}>
          <Button
            size="xs"
            variant="light"
            loading={operationLoading}
            onClick={() => void previewOperations(false)}
            disabled={!projectId.trim()}
          >
            Preview due-state
          </Button>
          <Button
            size="xs"
            variant="light"
            color="blue"
            loading={operationLoading}
            onClick={() => void previewOperations(true)}
            disabled={!projectId.trim()}
          >
            Dry-run preview
          </Button>
          <Button
            size="xs"
            color="blue"
            variant="outline"
            loading={operationExecuting}
            onClick={() => void runOperations(true)}
            disabled={!projectId.trim()}
          >
            Dry-run now
          </Button>
          <Button
            size="xs"
            color="teal"
            loading={operationExecuting}
            onClick={() => void runOperations(false)}
            disabled={!liveRunUnlocked}
          >
            Run now
          </Button>
        </Group>

        <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={8}>
          <Paper withBorder radius="md" p="xs">
            <Text size="xs" c="dimmed" fw={700}>
              Safety checkpoint
            </Text>
            <Text size="xs" c="dimmed">
              Type confirmation phrase before live run.
            </Text>
            <Text size="xs" ff="monospace">
              {expectedConfirmationPhrase}
            </Text>
            <TextInput
              size="xs"
              mt={6}
              label="Confirmation phrase"
              placeholder={expectedConfirmationPhrase}
              value={confirmationPhrase}
              onChange={(event) => setConfirmationPhrase(event.currentTarget.value)}
            />
            <Switch
              mt={6}
              size="sm"
              label="I understand this launches production calibration"
              checked={operationConfirmed}
              onChange={(event) => setOperationConfirmed(event.currentTarget.checked)}
            />
          </Paper>
          <Paper withBorder radius="md" p="xs">
            <Text size="xs" c="dimmed" fw={700}>
              Operation token
            </Text>
            <Text size="xs" c="dimmed">
              Idempotency token for live runs.
            </Text>
            <TextInput size="xs" mt={6} value={operationToken} onChange={(event) => setOperationToken(event.currentTarget.value)} />
            <Button size="xs" variant="subtle" mt={6} onClick={() => setOperationToken(makeOperationToken())}>
              Regenerate token
            </Button>
          </Paper>
          <Paper withBorder radius="md" p="xs">
            <Text size="xs" c="dimmed" fw={700}>
              Live run readiness
            </Text>
            <Badge variant="light" color={liveRunUnlocked ? "teal" : "gray"} mt={4}>
              {liveRunUnlocked ? "ready" : "locked"}
            </Badge>
            <Text size="xs" c="dimmed" mt={6}>
              run lock scope: project-level
            </Text>
            <Text size="xs" c="dimmed">
              token length: {operationToken.trim().length}
            </Text>
          </Paper>
        </SimpleGrid>

        {!operationResult && (
          <Text size="xs" c="dimmed">
            Run preview to see due schedules and generated scheduler command.
          </Text>
        )}

        {operationResult && (
          <Stack gap={6}>
            <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm">
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Operation status
                </Text>
                <Badge variant="light" color={runStatusColor(operationSummary?.status)}>
                  {operationSummary?.status ?? "unknown"}
                </Badge>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Executed schedules
                </Text>
                <Text size="sm" fw={700}>
                  {operationSummary?.executed_count ?? 0} / {operationSummary?.total_schedules ?? 0}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Alerts
                </Text>
                <Text size="sm" fw={700}>
                  {operationSummary?.alerts_count ?? 0}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Runtime
                </Text>
                <Text size="sm" fw={700}>
                  {Math.max(0, Number(operationResult.process?.duration_ms ?? 0))} ms
                </Text>
              </Paper>
            </SimpleGrid>

            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed" fw={700}>
                Command preview
              </Text>
              <Text size="xs" ff="monospace">
                {operationResult.command_preview}
              </Text>
            </Paper>

            <Stack gap={4}>
              <Text size="xs" c="dimmed" fw={700}>
                Schedule results
              </Text>
              {operationRows.length === 0 && (
                <Text size="xs" c="dimmed">
                  No schedule results returned.
                </Text>
              )}
              {operationRows.map((item, index) => (
                <Paper key={`operation-result-${item.schedule_name}-${index}`} withBorder radius="md" p="xs">
                  <Group justify="space-between" align="center">
                    <Stack gap={2}>
                      <Text size="sm" fw={600}>
                        {item.schedule_name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        due: {item.due ? "yes" : "no"} • due_at: {fmtDate(item.due_at)} • last_snapshot: {fmtDate(item.last_snapshot_at)}
                      </Text>
                    </Stack>
                    <Badge variant="light" color={operationResultColor(item.status)}>
                      {item.status}
                    </Badge>
                  </Group>
                </Paper>
              ))}
            </Stack>
          </Stack>
        )}

        <Paper withBorder radius="md" p="xs" mt={8}>
          <Group justify="space-between" align="center" mb={6}>
            <Stack gap={2}>
              <Text size="xs" fw={700} c="dimmed">
                Async Operation Queue
              </Text>
              <Text size="xs" c="dimmed">
                Queue-backed execution with live progress, cancel, and retry.
              </Text>
            </Stack>
            <Group gap={8} align="end">
              <Stack gap={2}>
                <Switch
                  size="sm"
                  label="Live SSE stream"
                  checked={queueSseEnabled}
                  onChange={(event) => setQueueSseEnabled(event.currentTarget.checked)}
                />
                <Text size="xs" c="dimmed">
                  {queueSseEnabled ? `stream ${queueSseStatus}` : "stream disabled (polling)"}
                </Text>
              </Stack>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconRefresh size={14} />}
                loading={
                  loadingOperationRuns ||
                  loadingQueueThroughput ||
                  loadingQueueCompare ||
                  loadingQueueAutoscaling ||
                  loadingQueueGovernanceDigest ||
                  loadingQueueIncidentEscalationDigest ||
                  loadingQueueAudit
                }
                onClick={() =>
                  void Promise.all([
                    loadOperationRuns(),
                    loadQueueThroughput(),
                    loadQueueThroughputCompare(),
                    loadQueueAutoscaling(),
                    loadQueueGovernanceDigest(),
                    loadQueueIncidentEscalationDigest(),
                    loadQueueAudit(),
                  ])
                }
              >
                Refresh queue
              </Button>
            </Group>
          </Group>

          {queueThroughput && (
            <Paper withBorder radius="md" p="xs" mb={8}>
              <Group justify="space-between" align="center" mb={6}>
                <Stack gap={2}>
                  <Text size="xs" c="dimmed" fw={700}>
                    Queue Throughput Controls
                  </Text>
                  <Text size="xs" c="dimmed">
                    Monitor worker lag/depth and pause or resume queue windows.
                  </Text>
                </Stack>
                <Badge variant="light" color={healthColor(queueThroughput.health)}>
                  {queueThroughput.health}
                </Badge>
              </Group>

              <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb={6}>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Depth
                  </Text>
                  <Text size="sm" fw={700}>
                    {queueThroughput.queue.depth_total} (q {queueThroughput.queue.queued}, r {queueThroughput.queue.running})
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Oldest queued
                  </Text>
                  <Text size="sm" fw={700}>
                    {queueThroughput.queue.oldest_queued_age_minutes == null
                      ? "—"
                      : `${queueThroughput.queue.oldest_queued_age_minutes.toFixed(1)}m`}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Worker lag p90
                  </Text>
                  <Text size="sm" fw={700}>
                    {queueThroughput.worker_lag.lag_minutes.p90 == null
                      ? "—"
                      : `${queueThroughput.worker_lag.lag_minutes.p90.toFixed(1)}m`}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Queue state
                  </Text>
                  <Badge variant="light" color={queueThroughput.control.pause_active ? "yellow" : "teal"} mt={2}>
                    {queueThroughput.control.pause_active ? "paused" : "active"}
                  </Badge>
                </Paper>
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={6}>
                <NumberInput
                  label="Lag SLA (minutes)"
                  min={1}
                  max={1440}
                  value={queueLagSlaMinutes}
                  onChange={(value) => setQueueLagSlaMinutes(Math.max(1, Math.min(1440, asNumber(value, 20))))}
                />
                <NumberInput
                  label="Depth warning"
                  min={1}
                  max={50000}
                  value={queueDepthWarn}
                  onChange={(value) => setQueueDepthWarn(Math.max(1, Math.min(50000, asNumber(value, 12))))}
                />
                <Button
                  mt={22}
                  size="xs"
                  variant="light"
                  loading={queueControlsBusy}
                  onClick={() => void saveQueueControls()}
                >
                  Save controls
                </Button>
              </SimpleGrid>

              <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={6}>
                <NumberInput
                  label="Pause window (hours)"
                  min={1}
                  max={168}
                  value={queuePauseHours}
                  onChange={(value) => setQueuePauseHours(Math.max(1, Math.min(168, asNumber(value, 2))))}
                />
                <TextInput
                  label="Pause reason"
                  placeholder="maintenance window"
                  value={queuePauseReason}
                  onChange={(event) => setQueuePauseReason(event.currentTarget.value)}
                />
                <Group gap={6} mt={22}>
                  <Button
                    size="xs"
                    color="yellow"
                    variant="light"
                    leftSection={<IconPlayerPause size={14} />}
                    loading={queueControlsBusy}
                    onClick={() => void pauseQueue()}
                  >
                    Pause queue
                  </Button>
                  <Button
                    size="xs"
                    color="teal"
                    variant="light"
                    leftSection={<IconPlayerPlay size={14} />}
                    loading={queueControlsBusy}
                    onClick={() => void resumeQueue()}
                  >
                    Resume queue
                  </Button>
                </Group>
              </SimpleGrid>

              {queueThroughput.alerts.length > 0 && (
                <Stack gap={3}>
                  {queueThroughput.alerts.map((item, index) => (
                    <Text key={`queue-alert-${item.code}-${index}`} size="xs" c="dimmed">
                      {item.code}: {item.message}
                    </Text>
                  ))}
                </Stack>
              )}

              <Paper withBorder radius="md" p="xs" mt={8}>
                <Group justify="space-between" align="end" mb={6}>
                  <Stack gap={2}>
                    <Text size="xs" c="dimmed" fw={700}>
                      Queue Command Center
                    </Text>
                    <Text size="xs" c="dimmed">
                      Cross-project queue health with bulk pause/resume windows.
                    </Text>
                  </Stack>
                  <Group gap={8} align="end">
                    <TextInput
                      label="Projects (csv)"
                      placeholder="omega_demo,project_b,project_c"
                      value={queueCompareProjectIds}
                      onChange={(event) => setQueueCompareProjectIds(event.currentTarget.value)}
                    />
                    <Button
                      size="xs"
                      variant="light"
                      loading={loadingQueueCompare}
                      leftSection={<IconRefresh size={14} />}
                      onClick={() =>
                        void Promise.all([
                          loadQueueThroughputCompare(),
                          loadQueueAutoscaling(),
                          loadQueueGovernanceDigest(),
                          loadQueueIncidentEscalationDigest(),
                          loadQueueOwnerRollups(),
                          loadQueueGovernanceDrift(),
                          loadQueueIncidentSloBoard(),
                          loadQueueIncidentHooks(),
                          loadQueueIncidentPolicies(),
                          loadQueueIncidentPreflightPresets(),
                          loadQueueIncidentSyncSchedules(),
                          loadQueueIncidentSyncScheduleFleet(),
                          loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true),
                          loadQueueIncidents(),
                        ])
                      }
                    >
                      Refresh command center
                    </Button>
                  </Group>
                </Group>

                <Group gap={6} mb={6}>
                  <Button
                    size="xs"
                    color="yellow"
                    variant="light"
                    leftSection={<IconPlayerPause size={14} />}
                    loading={queueBulkBusy}
                    onClick={() => void bulkPauseQueue()}
                  >
                    Bulk pause window
                  </Button>
                  <Button
                    size="xs"
                    color="teal"
                    variant="light"
                    leftSection={<IconPlayerPlay size={14} />}
                    loading={queueBulkBusy}
                    onClick={() => void bulkResumeQueue()}
                  >
                    Bulk resume now
                  </Button>
                </Group>

                <Group gap={6} mb={6}>
                  <Badge variant="light" color={incidentPreflightEnforcementColor("block")}>
                    preflight block {queueCommandCenterEnforcementSummary.block}
                  </Badge>
                  <Badge variant="light" color={incidentPreflightEnforcementColor("pause")}>
                    preflight pause {queueCommandCenterEnforcementSummary.pause}
                  </Badge>
                  <Badge variant="light" color={incidentPreflightEnforcementColor("off")}>
                    preflight off {queueCommandCenterEnforcementSummary.off}
                  </Badge>
                  <Text size="xs" c="dimmed">
                    enforced projects {queueCommandCenterEnforcementSummary.block + queueCommandCenterEnforcementSummary.pause}/
                    {queueCommandCenterRows.length}
                  </Text>
                </Group>

                <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={6}>
                  <Button
                    size="xs"
                    variant="light"
                    color="blue"
                    leftSection={<IconDeviceFloppy size={14} />}
                    loading={queueExportBusy}
                    onClick={() => void exportQueueCommandCenterCsv()}
                  >
                    Export CSV snapshot
                  </Button>
                  <TextInput
                    label="Webhook snapshot URL"
                    placeholder="https://hooks.example.com/synapse/queue"
                    value={queueWebhookUrl}
                    onChange={(event) => setQueueWebhookUrl(event.currentTarget.value)}
                  />
                  <Button
                    size="xs"
                    variant="light"
                    color="grape"
                    loading={queueExportBusy}
                    onClick={() => void sendQueueCommandCenterWebhookSnapshot()}
                  >
                    Send webhook snapshot
                  </Button>
                </SimpleGrid>

                <Paper withBorder radius="md" p="xs" mb={6}>
                  <Stack gap={2} mb={6}>
                    <Text size="xs" c="dimmed" fw={700}>
                      Ownership routing
                    </Text>
                    <Text size="xs" c="dimmed">
                      Map project queue incidents to an owner and escalation channels.
                    </Text>
                  </Stack>
                  <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={6}>
                    <TextInput
                      label="Project"
                      placeholder="omega_demo"
                      value={queueOwnerProjectId}
                      onChange={(event) => setQueueOwnerProjectId(event.currentTarget.value)}
                    />
                    <TextInput
                      label="Owner name"
                      placeholder="Ops On-call"
                      value={queueOwnerName}
                      onChange={(event) => setQueueOwnerName(event.currentTarget.value)}
                    />
                    <TextInput
                      label="Owner contact"
                      placeholder="ops@company.com"
                      value={queueOwnerContact}
                      onChange={(event) => setQueueOwnerContact(event.currentTarget.value)}
                    />
                  </SimpleGrid>
                  <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm">
                    <TextInput
                      label="On-call channel"
                      placeholder="#ops-oncall"
                      value={queueOncallChannel}
                      onChange={(event) => setQueueOncallChannel(event.currentTarget.value)}
                    />
                    <TextInput
                      label="Escalation channel"
                      placeholder="#ops-escalation"
                      value={queueEscalationChannel}
                      onChange={(event) => setQueueEscalationChannel(event.currentTarget.value)}
                    />
                    <Button
                      mt={22}
                      size="xs"
                      variant="light"
                      loading={queueOwnershipBusy}
                      onClick={() => void saveQueueOwnershipRouting()}
                    >
                      Save ownership routing
                    </Button>
                  </SimpleGrid>
                </Paper>

                <Paper withBorder radius="md" p="xs" mb={6}>
                  <Group justify="space-between" align="start" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Incident auto-ticket hooks
                      </Text>
                      <Text size="xs" c="dimmed">
                        Open/resolve external incident tickets from queue health transitions.
                      </Text>
                    </Stack>
                    <Group gap={6}>
                      <Button
                        size="xs"
                        variant="light"
                        leftSection={<IconRefresh size={14} />}
                        loading={
                          loadingQueueIncidentHooks ||
                          loadingQueueIncidentPolicies ||
                          loadingQueueIncidentPreflightPresets ||
                          loadingQueueIncidentSyncSchedules ||
                          loadingQueueIncidents
                        }
                        onClick={() =>
                          void Promise.all([
                            loadQueueIncidentHooks(),
                            loadQueueIncidentPolicies(),
                            loadQueueIncidentPreflightPresets(),
                            loadQueueIncidentSyncSchedules(),
                            loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true),
                            loadQueueIncidents(),
                          ])
                        }
                      >
                        Refresh incident state
                      </Button>
                      <Button
                        size="xs"
                        color="grape"
                        variant="light"
                        loading={queueIncidentSyncBusy}
                        onClick={() => void syncQueueIncidentHooks()}
                      >
                        Sync incident hooks
                      </Button>
                    </Group>
                  </Group>

                  <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm" mb={6}>
                    <TextInput
                      label="Project"
                      placeholder="omega_demo"
                      value={queueIncidentProjectId}
                      onChange={(event) => setQueueIncidentProjectId(event.currentTarget.value)}
                    />
                    <Select
                      label="Provider adapter"
                      data={[
                        { value: "webhook", label: "Webhook (generic)" },
                        { value: "pagerduty", label: "PagerDuty preset" },
                        { value: "jira", label: "Jira preset" },
                      ]}
                      value={queueIncidentProvider}
                      onChange={(value) => setQueueIncidentProvider((value as "webhook" | "pagerduty" | "jira") || "webhook")}
                    />
                    <TextInput
                      label="Open endpoint override"
                      placeholder={
                        queueIncidentProvider === "pagerduty"
                          ? "https://events.pagerduty.com/v2/enqueue"
                          : queueIncidentProvider === "jira"
                            ? "https://jira.example.com/rest/api/2/issue"
                            : "https://hooks.example.com/incidents/open"
                      }
                      value={queueIncidentOpenWebhookUrl}
                      onChange={(event) => setQueueIncidentOpenWebhookUrl(event.currentTarget.value)}
                    />
                    <TextInput
                      label="Resolve endpoint override"
                      placeholder={
                        queueIncidentProvider === "jira"
                          ? "https://jira.example.com/rest/api/2/issue/{id}/transitions"
                          : "https://hooks.example.com/incidents/resolve"
                      }
                      value={queueIncidentResolveWebhookUrl}
                      onChange={(event) => setQueueIncidentResolveWebhookUrl(event.currentTarget.value)}
                    />
                  </SimpleGrid>
                  {queueIncidentProvider === "webhook" && (
                    <Textarea
                      label="Webhook headers (JSON)"
                      autosize
                      minRows={2}
                      maxRows={6}
                      placeholder='{"Authorization":"Bearer ..."}'
                      value={queueIncidentWebhookHeadersJson}
                      onChange={(event) => setQueueIncidentWebhookHeadersJson(event.currentTarget.value)}
                      mb={6}
                    />
                  )}
                  {queueIncidentProvider === "pagerduty" && (
                    <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mb={6}>
                      <TextInput
                        label="PagerDuty routing key"
                        placeholder="PAGERDUTY_EVENTS_ROUTING_KEY"
                        value={queueIncidentPagerdutyRoutingKey}
                        onChange={(event) => setQueueIncidentPagerdutyRoutingKey(event.currentTarget.value)}
                      />
                      <TextInput
                        label="Dedup key prefix"
                        placeholder="synapse-queue"
                        value={queueIncidentPagerdutyDedupPrefix}
                        onChange={(event) => setQueueIncidentPagerdutyDedupPrefix(event.currentTarget.value)}
                      />
                    </SimpleGrid>
                  )}
                  {queueIncidentProvider === "jira" && (
                    <Stack gap="xs" mb={6}>
                      <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm">
                        <TextInput
                          label="Jira base URL"
                          placeholder="https://jira.example.com"
                          value={queueIncidentJiraBaseUrl}
                          onChange={(event) => setQueueIncidentJiraBaseUrl(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Jira project key"
                          placeholder="OPS"
                          value={queueIncidentJiraProjectKey}
                          onChange={(event) => setQueueIncidentJiraProjectKey(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Issue type"
                          placeholder="Incident"
                          value={queueIncidentJiraIssueType}
                          onChange={(event) => setQueueIncidentJiraIssueType(event.currentTarget.value)}
                        />
                      </SimpleGrid>
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <Select
                          label="Auth mode"
                          data={[
                            { value: "basic", label: "Basic (email + token)" },
                            { value: "bearer", label: "Bearer token" },
                          ]}
                          value={queueIncidentJiraAuthMode}
                          onChange={(value) => setQueueIncidentJiraAuthMode(value === "bearer" ? "bearer" : "basic")}
                        />
                        <TextInput
                          label="Jira email"
                          placeholder="ops@example.com"
                          value={queueIncidentJiraEmail}
                          onChange={(event) => setQueueIncidentJiraEmail(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Jira API token"
                          placeholder="jira_api_token"
                          value={queueIncidentJiraApiToken}
                          onChange={(event) => setQueueIncidentJiraApiToken(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Resolve transition id"
                          placeholder="31"
                          value={queueIncidentJiraResolveTransitionId}
                          onChange={(event) => setQueueIncidentJiraResolveTransitionId(event.currentTarget.value)}
                        />
                      </SimpleGrid>
                    </Stack>
                  )}
                  <Text size="xs" c="dimmed" mb={6}>
                    Secret adapter fields are masked on read. Keep masked value to preserve current secret, or enter a new value to rotate.
                  </Text>
                  <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm" mb={6}>
                    <TextInput
                      label="Open on health (csv)"
                      placeholder="critical"
                      value={queueIncidentOpenOnHealthCsv}
                      onChange={(event) => setQueueIncidentOpenOnHealthCsv(event.currentTarget.value)}
                    />
                    <NumberInput
                      label="Cooldown (minutes)"
                      min={1}
                      max={1440}
                      value={queueIncidentCooldownMinutes}
                      onChange={(value) => setQueueIncidentCooldownMinutes(Math.max(1, Math.min(1440, asNumber(value, 30))))}
                    />
                    <NumberInput
                      label="Webhook timeout (sec)"
                      min={1}
                      max={60}
                      value={queueIncidentTimeoutSec}
                      onChange={(value) => setQueueIncidentTimeoutSec(Math.max(1, Math.min(60, asNumber(value, 10))))}
                    />
                    <Button mt={22} size="xs" variant="light" loading={queueIncidentHookBusy} onClick={() => void saveQueueIncidentHook()}>
                      Save incident hook
                    </Button>
                  </SimpleGrid>
                  <Group gap={12} mb={6}>
                    <Switch
                      size="sm"
                      label="Incident hook enabled"
                      checked={queueIncidentHookEnabled}
                      onChange={(event) => setQueueIncidentHookEnabled(event.currentTarget.checked)}
                    />
                    <Switch
                      size="sm"
                      label="Auto resolve on recovery"
                      checked={queueIncidentAutoResolve}
                      onChange={(event) => setQueueIncidentAutoResolve(event.currentTarget.checked)}
                    />
                  </Group>

                  {queueIncidentHookRows.length > 0 && (
                    <Stack gap={2} mb={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Active hook configs
                      </Text>
                      {queueIncidentHookRows.slice(0, 5).map((hook) => (
                        <Text key={`queue-hook-${hook.project_id}`} size="xs" c="dimmed">
                          {hook.project_id} • {hook.provider} • {hook.enabled ? "enabled" : "disabled"} • open on{" "}
                          {hook.open_on_health.join(",")}
                          {" • "}
                          cooldown {hook.cooldown_minutes}m
                        </Text>
                      ))}
                    </Stack>
                  )}

                  <Paper withBorder radius="md" p="xs" mb={6}>
                    <Stack gap={4}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Alert-to-incident policy template
                      </Text>
                      <Text size="xs" c="dimmed">
                        Route specific alert codes to provider presets and override severity mapping.
                      </Text>
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <TextInput
                          label="Alert code"
                          placeholder="queue_depth_critical"
                          value={queueIncidentPolicyAlertCode}
                          onChange={(event) => setQueueIncidentPolicyAlertCode(event.currentTarget.value)}
                        />
                        <NumberInput
                          label="Priority"
                          min={1}
                          max={1000}
                          value={queueIncidentPolicyPriority}
                          onChange={(value) =>
                            setQueueIncidentPolicyPriority(Math.max(1, Math.min(1000, asNumber(value, 100))))
                          }
                        />
                        <Select
                          label="Provider override"
                          data={[
                            { value: "inherit", label: "Inherit hook provider" },
                            { value: "webhook", label: "Webhook (generic)" },
                            { value: "pagerduty", label: "PagerDuty preset" },
                            { value: "jira", label: "Jira preset" },
                          ]}
                          value={queueIncidentPolicyProviderOverride}
                          onChange={(value) =>
                            setQueueIncidentPolicyProviderOverride(
                              (value as "inherit" | "webhook" | "pagerduty" | "jira") || "inherit",
                            )
                          }
                        />
                        <Button mt={22} size="xs" variant="light" loading={queueIncidentPolicyBusy} onClick={() => void saveQueueIncidentPolicy()}>
                          Save incident policy
                        </Button>
                      </SimpleGrid>
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <TextInput
                          label="Open endpoint override (optional)"
                          placeholder="https://..."
                          value={queueIncidentPolicyOpenWebhookUrl}
                          onChange={(event) => setQueueIncidentPolicyOpenWebhookUrl(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Resolve endpoint override (optional)"
                          placeholder="https://..."
                          value={queueIncidentPolicyResolveWebhookUrl}
                          onChange={(event) => setQueueIncidentPolicyResolveWebhookUrl(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Severity map (csv)"
                          placeholder="critical=critical,watch=warning"
                          value={queueIncidentPolicySeverityCsv}
                          onChange={(event) => setQueueIncidentPolicySeverityCsv(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Open on health override (csv)"
                          placeholder="critical"
                          value={queueIncidentPolicyOpenOnHealthCsv}
                          onChange={(event) => setQueueIncidentPolicyOpenOnHealthCsv(event.currentTarget.value)}
                        />
                      </SimpleGrid>
                      <Textarea
                        label="Provider config override (JSON)"
                        autosize
                        minRows={2}
                        maxRows={6}
                        placeholder='{"routing_key":"..."}'
                        value={queueIncidentPolicyConfigOverrideJson}
                        onChange={(event) => setQueueIncidentPolicyConfigOverrideJson(event.currentTarget.value)}
                      />
                      <Switch
                        size="sm"
                        label="Policy enabled"
                        checked={queueIncidentPolicyEnabled}
                        onChange={(event) => setQueueIncidentPolicyEnabled(event.currentTarget.checked)}
                      />
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <Select
                          label="Simulation health"
                          data={[
                            { value: "critical", label: "critical" },
                            { value: "watch", label: "watch" },
                            { value: "healthy", label: "healthy" },
                          ]}
                          value={queueIncidentPolicySimulationHealth}
                          onChange={(value) =>
                            setQueueIncidentPolicySimulationHealth((value as "healthy" | "watch" | "critical") || "critical")
                          }
                        />
                        <TextInput
                          label="Additional alert codes (csv)"
                          placeholder="worker_lag_spike,timeout_burst"
                          value={queueIncidentPolicySimulationAdditionalAlertCodesCsv}
                          onChange={(event) => setQueueIncidentPolicySimulationAdditionalAlertCodesCsv(event.currentTarget.value)}
                        />
                        <Button
                          mt={22}
                          size="xs"
                          variant="default"
                          loading={queueIncidentPolicySimulationBusy}
                          onClick={() => void simulateQueueIncidentPolicyRoute()}
                        >
                          Simulate policy route
                        </Button>
                      </SimpleGrid>
                      {queueIncidentPolicySimulationResult && (
                        <Paper withBorder radius="md" p="xs">
                          <Stack gap={3}>
                            <Group gap={8}>
                              <Text size="xs" fw={700}>
                                Simulation decision
                              </Text>
                              <Badge
                                size="xs"
                                color={queueIncidentPolicySimulationResult.decision.should_open_incident ? "teal" : "yellow"}
                                variant="light"
                              >
                                {queueIncidentPolicySimulationResult.decision.should_open_incident ? "would open incident" : "would not open"}
                              </Badge>
                              <Text size="xs" c="dimmed">
                                provider {queueIncidentPolicySimulationResult.effective_hook.provider}
                              </Text>
                            </Group>
                            <Text size="xs" c="dimmed">
                              matched policy{" "}
                              {queueIncidentPolicySimulationResult.matched_policy
                                ? `${queueIncidentPolicySimulationResult.matched_policy.alert_code} (p${queueIncidentPolicySimulationResult.matched_policy.priority})`
                                : "none"}
                              {" • "}
                              health {queueIncidentPolicySimulationResult.health}
                            </Text>
                            {queueIncidentPolicySimulationResult.decision.skip_reason && (
                              <Text size="xs" c="orange">
                                skip reason: {queueIncidentPolicySimulationResult.decision.skip_reason}
                              </Text>
                            )}
                            {queueIncidentPolicySimulationTraceRows.slice(0, 5).map((trace) => (
                              <Text key={`queue-policy-sim-trace-${trace.id || trace.alert_code}-${trace.priority}`} size="xs" c="dimmed">
                                {trace.matched ? "✓" : "•"} {trace.alert_code} • p{trace.priority} •{" "}
                                {trace.provider_override || "inherit"} • {trace.enabled ? "enabled" : "disabled"}
                              </Text>
                            ))}
                          </Stack>
                        </Paper>
                      )}
                    </Stack>
                  </Paper>

                  <Paper withBorder radius="md" p="xs" mb={6}>
                    <Stack gap={4}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Incident preflight presets
                      </Text>
                      <Text size="xs" c="dimmed">
                        Queue dry-run checks before live sync windows. Failing checks create actionable audit alerts.
                      </Text>
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <TextInput
                          label="Preflight key (optional)"
                          placeholder="queue-depth-critical-open"
                          value={queueIncidentPreflightPresetKey}
                          onChange={(event) => setQueueIncidentPreflightPresetKey(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Preflight name"
                          placeholder="Queue depth critical should open incident"
                          value={queueIncidentPreflightPresetName}
                          onChange={(event) => setQueueIncidentPreflightPresetName(event.currentTarget.value)}
                        />
                        <TextInput
                          label="Preflight alert code"
                          placeholder="queue_depth_critical"
                          value={queueIncidentPreflightAlertCode}
                          onChange={(event) => setQueueIncidentPreflightAlertCode(event.currentTarget.value)}
                        />
                        <Button
                          mt={22}
                          size="xs"
                          variant="light"
                          loading={queueIncidentPreflightPresetBusy}
                          onClick={() => void saveQueueIncidentPreflightPreset()}
                        >
                          Save preflight preset
                        </Button>
                      </SimpleGrid>
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <Select
                          label="Preflight health"
                          data={[
                            { value: "critical", label: "critical" },
                            { value: "watch", label: "watch" },
                            { value: "healthy", label: "healthy" },
                          ]}
                          value={queueIncidentPreflightHealth}
                          onChange={(value) =>
                            setQueueIncidentPreflightHealth((value as "healthy" | "watch" | "critical") || "critical")
                          }
                        />
                        <Select
                          label="Expected decision"
                          data={[
                            { value: "open", label: "must open incident" },
                            { value: "skip", label: "must skip incident" },
                            { value: "invalid_ok", label: "invalid route accepted" },
                          ]}
                          value={queueIncidentPreflightExpectedDecision}
                          onChange={(value) =>
                            setQueueIncidentPreflightExpectedDecision((value as "open" | "skip" | "invalid_ok") || "open")
                          }
                        />
                        <Select
                          label="Required provider"
                          data={[
                            { value: "inherit", label: "No provider lock" },
                            { value: "webhook", label: "Webhook (generic)" },
                            { value: "pagerduty", label: "PagerDuty preset" },
                            { value: "jira", label: "Jira preset" },
                          ]}
                          value={queueIncidentPreflightRequiredProvider}
                          onChange={(value) =>
                            setQueueIncidentPreflightRequiredProvider(
                              (value as "inherit" | "webhook" | "pagerduty" | "jira") || "inherit",
                            )
                          }
                        />
                        <Select
                          label="Preflight severity"
                          data={[
                            { value: "info", label: "info" },
                            { value: "warning", label: "warning" },
                            { value: "critical", label: "critical" },
                          ]}
                          value={queueIncidentPreflightSeverity}
                          onChange={(value) =>
                            setQueueIncidentPreflightSeverity((value as "info" | "warning" | "critical") || "warning")
                          }
                        />
                      </SimpleGrid>
                      <TextInput
                        label="Preflight additional alert codes (csv)"
                        placeholder="worker_lag_spike,timeout_burst"
                        value={queueIncidentPreflightAdditionalAlertCodesCsv}
                        onChange={(event) => setQueueIncidentPreflightAdditionalAlertCodesCsv(event.currentTarget.value)}
                      />
                      <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm">
                        <Select
                          label="Live sync enforcement mode"
                          data={[
                            { value: "off", label: "off (observe only)" },
                            { value: "block", label: "block sync on critical fails" },
                            { value: "pause", label: "pause queue on critical fails" },
                          ]}
                          value={queueIncidentSyncEnforcementMode}
                          onChange={(value) =>
                            setQueueIncidentSyncEnforcementMode((value as "off" | "block" | "pause") || "off")
                          }
                        />
                        <NumberInput
                          label="Enforcement pause hours"
                          min={1}
                          max={168}
                          step={1}
                          value={queueIncidentSyncEnforcementPauseHours}
                          onChange={(value) =>
                            setQueueIncidentSyncEnforcementPauseHours(Math.max(1, Math.min(168, Number(value || 4))))
                          }
                        />
                        <NumberInput
                          label="Critical preflight threshold"
                          min={1}
                          max={100}
                          step={1}
                          value={queueIncidentSyncEnforcementCriticalThreshold}
                          onChange={(value) =>
                            setQueueIncidentSyncEnforcementCriticalThreshold(Math.max(1, Math.min(100, Number(value || 1))))
                          }
                        />
                        <Button
                          mt={22}
                          size="xs"
                          variant="light"
                          loading={queueIncidentSyncEnforcementBusy}
                          onClick={() => void saveQueueIncidentSyncEnforcement()}
                        >
                          Save sync enforcement
                        </Button>
                      </SimpleGrid>
                      <Group gap={12}>
                        <Switch
                          size="sm"
                          label="Preflight preset enabled"
                          checked={queueIncidentPreflightEnabled}
                          onChange={(event) => setQueueIncidentPreflightEnabled(event.currentTarget.checked)}
                        />
                        <Switch
                          size="sm"
                          label="Run before live sync"
                          checked={queueIncidentPreflightRunBeforeLiveSync}
                          onChange={(event) => setQueueIncidentPreflightRunBeforeLiveSync(event.currentTarget.checked)}
                        />
                        <Switch
                          size="sm"
                          label="Strict mode"
                          checked={queueIncidentPreflightStrictMode}
                          onChange={(event) => setQueueIncidentPreflightStrictMode(event.currentTarget.checked)}
                        />
                      </Group>
                      <Group gap={12}>
                        <Switch
                          size="sm"
                          label="Include disabled presets"
                          checked={queueIncidentPreflightIncludeDisabled}
                          onChange={(event) => setQueueIncidentPreflightIncludeDisabled(event.currentTarget.checked)}
                        />
                        <Switch
                          size="sm"
                          label="Run only before-live-sync presets"
                          checked={queueIncidentPreflightRunBeforeSyncOnly}
                          onChange={(event) => setQueueIncidentPreflightRunBeforeSyncOnly(event.currentTarget.checked)}
                        />
                        <Switch
                          size="sm"
                          label="Record preflight audit events"
                          checked={queueIncidentPreflightRecordAudit}
                          onChange={(event) => setQueueIncidentPreflightRecordAudit(event.currentTarget.checked)}
                        />
                        <Button
                          size="xs"
                          variant="default"
                          loading={queueIncidentPreflightRunBusy}
                          onClick={() => void runQueueIncidentPreflightChecks()}
                        >
                          Run preflight checks
                        </Button>
                      </Group>
                      {queueIncidentPreflightRunResult && (
                        <SimpleGrid cols={{ base: 1, xl: 6 }} spacing="sm">
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Projects
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.projects_total}
                            </Text>
                          </Paper>
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Presets
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.presets_total}
                            </Text>
                          </Paper>
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Checks
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.checks_total}
                            </Text>
                          </Paper>
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Passed
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.passed}
                            </Text>
                          </Paper>
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Failed
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.failed}
                            </Text>
                          </Paper>
                          <Paper withBorder radius="md" p="xs">
                            <Text size="xs" c="dimmed">
                              Critical alerts
                            </Text>
                            <Text size="sm" fw={700}>
                              {queueIncidentPreflightRunSummary.alerts_by_severity.critical}
                            </Text>
                          </Paper>
                        </SimpleGrid>
                      )}
                      {queueIncidentPreflightRollupRows.length > 0 && (
                        <Stack gap={2}>
                          <Text size="xs" c="dimmed" fw={700}>
                            Project rollups
                          </Text>
                          {queueIncidentPreflightRollupRows.slice(0, 6).map((item) => (
                            <Text key={`preflight-rollup-${item.project_id}`} size="xs" c="dimmed">
                              {item.project_id} • checks {item.checks_total} • passed {item.passed} • failed {item.failed} • critical{" "}
                              {item.critical_alerts}
                            </Text>
                          ))}
                        </Stack>
                      )}
                      {queueIncidentPreflightAlertRows.length > 0 && (
                        <Stack gap={2}>
                          <Text size="xs" c="dimmed" fw={700}>
                            Preflight alerts
                          </Text>
                          {queueIncidentPreflightAlertRows.slice(0, 8).map((item) => (
                            <Text
                              key={`preflight-alert-${item.project_id}-${item.preset_key}-${item.severity}`}
                              size="xs"
                              c={item.severity === "critical" ? "red" : item.severity === "warning" ? "orange" : "dimmed"}
                            >
                              {item.project_id} • {item.preset_key} • {item.fail_reasons.join(",") || "failed"} • provider{" "}
                              {item.simulation.provider_after_policy || "unknown"}
                              {item.recommendation ? ` • ${item.recommendation}` : ""}
                            </Text>
                          ))}
                        </Stack>
                      )}
                      {loadingQueueIncidentPreflightPresets && (
                        <Text size="xs" c="dimmed">
                          Loading preflight presets...
                        </Text>
                      )}
                      {queueIncidentPreflightRows.length > 0 && (
                        <Stack gap={2}>
                          <Text size="xs" c="dimmed" fw={700}>
                            Saved preflight presets
                          </Text>
                          {queueIncidentPreflightRows.slice(0, 8).map((preset) => (
                            <Text key={`queue-preflight-${preset.id || preset.preset_key}`} size="xs" c="dimmed">
                              {preset.project_id} • {preset.preset_key} • {preset.expected_decision} •{" "}
                              {preset.required_provider || "provider-inherit"} • {preset.enabled ? "enabled" : "disabled"}
                            </Text>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>

                  <Paper withBorder radius="md" p="xs" mb={6}>
                    <Group justify="space-between" align="start" mb={6}>
                      <Stack gap={2}>
                        <Text size="xs" c="dimmed" fw={700}>
                          Incident sync schedules
                        </Text>
                        <Text size="xs" c="dimmed">
                          Persisted unattended sync windows with preflight gating, last-run visibility, and due backlog control.
                        </Text>
                      </Stack>
                      <Group gap={6}>
                        <Button
                          size="xs"
                          variant="light"
                          leftSection={<IconRefresh size={14} />}
                          loading={loadingQueueIncidentSyncSchedules || loadingQueueIncidentSyncScheduleTimeline}
                          onClick={() =>
                            void Promise.all([
                              loadQueueIncidentSyncSchedules(),
                              loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, true),
                            ])
                          }
                        >
                          Refresh incident schedules
                        </Button>
                        <Button
                          size="xs"
                          color="grape"
                          variant="light"
                          loading={queueIncidentSyncScheduleRunBusy}
                          onClick={() => void runQueueIncidentSyncSchedules()}
                        >
                          Run incident sync schedules
                        </Button>
                      </Group>
                    </Group>
                    <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm" mb={6}>
                      <TextInput
                        label="Project"
                        placeholder="omega_demo"
                        value={queueIncidentProjectId}
                        onChange={(event) => setQueueIncidentProjectId(event.currentTarget.value)}
                      />
                      <TextInput
                        label="Incident sync schedule name"
                        placeholder="default"
                        value={queueIncidentSyncScheduleName}
                        onChange={(event) => setQueueIncidentSyncScheduleName(event.currentTarget.value)}
                      />
                      <Select
                        label="Schedule preset"
                        data={[
                          { value: "hourly", label: "Hourly (60m)" },
                          { value: "every_4h", label: "Every 4h (240m)" },
                          { value: "daily", label: "Daily (1440m)" },
                          { value: "weekly", label: "Weekly (10080m)" },
                          { value: "custom", label: "Custom" },
                        ]}
                        value={queueIncidentSyncSchedulePreset}
                        onChange={(value) =>
                          setQueueIncidentSyncSchedulePreset(
                            value === "hourly" || value === "daily" || value === "weekly" || value === "custom" ? value : "every_4h",
                          )
                        }
                      />
                      <NumberInput
                        label="Custom interval (minutes)"
                        min={5}
                        max={10080}
                        value={queueIncidentSyncScheduleIntervalMinutes}
                        disabled={queueIncidentSyncSchedulePreset !== "custom"}
                        onChange={(value) =>
                          setQueueIncidentSyncScheduleIntervalMinutes(Math.max(5, Math.min(10080, Number(value || 240))))
                        }
                      />
                      <Button
                        mt={22}
                        size="xs"
                        variant="light"
                        loading={queueIncidentSyncScheduleBusy}
                        onClick={() => void saveQueueIncidentSyncSchedule()}
                      >
                        Save incident sync schedule
                      </Button>
                    </SimpleGrid>
                    <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm" mb={6}>
                      <NumberInput
                        label="Sync window (hours)"
                        min={1}
                        max={168}
                        value={queueIncidentSyncScheduleWindowHours}
                        onChange={(value) => setQueueIncidentSyncScheduleWindowHours(Math.max(1, Math.min(168, Number(value || 24))))}
                      />
                      <NumberInput
                        label="Batch size"
                        min={1}
                        max={200}
                        value={queueIncidentSyncScheduleBatchSize}
                        onChange={(value) => setQueueIncidentSyncScheduleBatchSize(Math.max(1, Math.min(200, Number(value || 50))))}
                      />
                      <NumberInput
                        label="Sync limit"
                        min={1}
                        max={200}
                        value={queueIncidentSyncScheduleLimit}
                        onChange={(value) => setQueueIncidentSyncScheduleLimit(Math.max(1, Math.min(200, Number(value || 50))))}
                      />
                      <Select
                        label="Schedule preflight mode"
                        data={[
                          { value: "inherit", label: "inherit project mode" },
                          { value: "off", label: "off" },
                          { value: "block", label: "block" },
                          { value: "pause", label: "pause" },
                        ]}
                        value={queueIncidentSyncSchedulePreflightMode}
                        onChange={(value) =>
                          setQueueIncidentSyncSchedulePreflightMode(
                            value === "off" || value === "block" || value === "pause" ? value : "inherit",
                          )
                        }
                      />
                      <TextInput
                        label="Next run at (ISO, optional)"
                        placeholder="2026-04-01T12:00:00Z"
                        value={queueIncidentSyncScheduleNextRunAt}
                        onChange={(event) => setQueueIncidentSyncScheduleNextRunAt(event.currentTarget.value)}
                      />
                    </SimpleGrid>
                    <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mb={6}>
                      <NumberInput
                        label="Preflight pause hours"
                        min={1}
                        max={168}
                        value={queueIncidentSyncSchedulePreflightPauseHours}
                        disabled={
                          queueIncidentSyncSchedulePreflightMode === "off" || queueIncidentSyncSchedulePreflightMode === "inherit"
                        }
                        onChange={(value) =>
                          setQueueIncidentSyncSchedulePreflightPauseHours(Math.max(1, Math.min(168, Number(value || 4))))
                        }
                      />
                      <NumberInput
                        label="Preflight critical threshold"
                        min={1}
                        max={100}
                        value={queueIncidentSyncSchedulePreflightCriticalThreshold}
                        disabled={
                          queueIncidentSyncSchedulePreflightMode === "off" || queueIncidentSyncSchedulePreflightMode === "inherit"
                        }
                        onChange={(value) =>
                          setQueueIncidentSyncSchedulePreflightCriticalThreshold(Math.max(1, Math.min(100, Number(value || 1))))
                        }
                      />
                    </SimpleGrid>
                    <Group gap={12} mb={6}>
                      <Switch
                        size="sm"
                        label="Schedule enabled"
                        checked={queueIncidentSyncScheduleEnabled}
                        onChange={(event) => setQueueIncidentSyncScheduleEnabled(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Dry run only"
                        checked={queueIncidentSyncScheduleDryRun}
                        onChange={(event) => setQueueIncidentSyncScheduleDryRun(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Force resolve on recovery"
                        checked={queueIncidentSyncScheduleForceResolve}
                        onChange={(event) => setQueueIncidentSyncScheduleForceResolve(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Preflight run-before-only"
                        checked={queueIncidentSyncSchedulePreflightRunBeforeOnly}
                        onChange={(event) => setQueueIncidentSyncSchedulePreflightRunBeforeOnly(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Record preflight audit"
                        checked={queueIncidentSyncSchedulePreflightRecordAudit}
                        onChange={(event) => setQueueIncidentSyncSchedulePreflightRecordAudit(event.currentTarget.checked)}
                      />
                    </Group>
                    <Group gap={12} mb={6}>
                      <Switch
                        size="sm"
                        label="Run selected schedule only"
                        checked={queueIncidentSyncScheduleRunSelectedOnly}
                        onChange={(event) => setQueueIncidentSyncScheduleRunSelectedOnly(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Force run now"
                        checked={queueIncidentSyncScheduleRunForce}
                        onChange={(event) => setQueueIncidentSyncScheduleRunForce(event.currentTarget.checked)}
                      />
                      <Switch
                        size="sm"
                        label="Skip due check"
                        checked={queueIncidentSyncScheduleRunSkipDue}
                        onChange={(event) => setQueueIncidentSyncScheduleRunSkipDue(event.currentTarget.checked)}
                      />
                    </Group>
                    <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Schedules in project
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSyncScheduleProjectRows.length}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Due backlog
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSyncScheduleDueRows.length}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Last run ok
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSyncScheduleStatusSummary.ok}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Last run partial
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSyncScheduleStatusSummary.partial_failure}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Last run failed
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSyncScheduleStatusSummary.failed}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                    <Paper withBorder radius="md" p="xs" mb={6}>
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        Failure heatmap by hour (last run status)
                      </Text>
                      {queueIncidentSyncScheduleHeatmapRows.some((item) => item.runs > 0) ? (
                        <BarChart
                          h={180}
                          data={queueIncidentSyncScheduleHeatmapRows}
                          dataKey="hour"
                          withLegend
                          withTooltip
                          series={[
                            { name: "runs", color: "blue.4", label: "Runs" },
                            { name: "partial_failure", color: "yellow.6", label: "Partial" },
                            { name: "failed", color: "red.6", label: "Failed" },
                          ]}
                        />
                      ) : (
                        <Text size="xs" c="dimmed">
                          Heatmap will appear after first schedule executions.
                        </Text>
                      )}
                    </Paper>
                    <Stack gap={3} mb={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Project schedules
                      </Text>
                      {queueIncidentSyncScheduleProjectRows.length === 0 && (
                        <Text size="xs" c="dimmed">
                          No incident sync schedules configured for this project.
                        </Text>
                      )}
                      {queueIncidentSyncScheduleProjectRows.map((schedule) => (
                        <Paper key={`incident-sync-schedule-${schedule.id}`} withBorder radius="md" p="xs">
                          <Group justify="space-between" align="start">
                            <Stack gap={2}>
                              <Text size="sm" fw={600}>
                                {schedule.name}
                              </Text>
                              <Text size="xs" c="dimmed">
                                preset {schedule.preset} • every {schedule.interval_minutes}m • window {schedule.window_hours}h
                                {" • "}
                                limit {schedule.sync_limit}
                              </Text>
                              <Text size="xs" c="dimmed">
                                next {fmtDate(schedule.next_run_at)} • last {fmtDate(schedule.last_run_at)}
                              </Text>
                              <Text size="xs" c="dimmed">
                                preflight {schedule.preflight_enforcement_mode}
                                {schedule.preflight_critical_fail_threshold != null
                                  ? ` • critical >= ${schedule.preflight_critical_fail_threshold}`
                                  : ""}
                                {schedule.preflight_pause_hours != null ? ` • pause ${schedule.preflight_pause_hours}h` : ""}
                              </Text>
                            </Stack>
                            <Group gap={6}>
                              <Badge variant="light" color={schedule.enabled ? "teal" : "gray"}>
                                {schedule.enabled ? "enabled" : "disabled"}
                              </Badge>
                              <Badge variant="light" color={incidentSyncScheduleStatusColor(schedule.last_status)}>
                                {schedule.last_status || "never"}
                              </Badge>
                              {queueIncidentSyncScheduleDueRows.some((item) => item.id === schedule.id) && (
                                <Badge variant="light" color="orange">
                                  due
                                </Badge>
                              )}
                              <Button
                                size="xs"
                                variant="subtle"
                                onClick={() => {
                                  setQueueIncidentProjectId(schedule.project_id);
                                  setQueueIncidentSyncScheduleName(schedule.name);
                                  setQueueIncidentSyncScheduleTimelineScheduleId(schedule.id);
                                  void loadQueueIncidentSyncScheduleTimeline(schedule.id, true);
                                }}
                              >
                                Load
                              </Button>
                              <Button
                                size="xs"
                                variant="subtle"
                                color="grape"
                                loading={queueIncidentSyncScheduleRunBusy}
                                onClick={() => void runQueueIncidentSyncSchedules(schedule.id)}
                              >
                                Run
                              </Button>
                              <Button
                                size="xs"
                                color="red"
                                variant="subtle"
                                loading={queueIncidentSyncScheduleDeleteBusyId === schedule.id}
                                onClick={() => void deleteQueueIncidentSyncSchedule(schedule)}
                              >
                                Delete
                              </Button>
                            </Group>
                          </Group>
                        </Paper>
                      ))}
                    </Stack>
                    <Paper withBorder radius="md" p="xs" mb={6}>
                      <Stack gap={6}>
                        <Group justify="space-between" align="end">
                          <Stack gap={2}>
                            <Text size="xs" c="dimmed" fw={700}>
                              Fleet schedule table
                            </Text>
                            <Text size="xs" c="dimmed">
                              Optimized list for multi-project operations (filters, compact mode, pagination).
                            </Text>
                          </Stack>
                          <Text size="xs" c="dimmed">
                            showing {queueIncidentSyncScheduleFleetRangeStart}-{queueIncidentSyncScheduleFleetRangeEnd} of{" "}
                            {queueIncidentSyncScheduleFleetTotal}
                          </Text>
                        </Group>
                        <SimpleGrid cols={{ base: 1, xl: 7 }} spacing="sm">
                          <TextInput
                            label="Fleet project filter"
                            placeholder="omega_demo"
                            value={queueIncidentSyncScheduleFleetProjectFilter}
                            onChange={(event) => setQueueIncidentSyncScheduleFleetProjectFilter(event.currentTarget.value)}
                          />
                          <TextInput
                            label="Fleet schedule filter"
                            placeholder="default"
                            value={queueIncidentSyncScheduleFleetNameFilter}
                            onChange={(event) => setQueueIncidentSyncScheduleFleetNameFilter(event.currentTarget.value)}
                          />
                          <Select
                            label="Fleet status filter"
                            data={[
                              { value: "all", label: "all statuses" },
                              { value: "ok", label: "ok" },
                              { value: "partial_failure", label: "partial_failure" },
                              { value: "failed", label: "failed" },
                              { value: "skipped", label: "skipped" },
                              { value: "never", label: "never" },
                            ]}
                            value={queueIncidentSyncScheduleFleetStatusFilter}
                            onChange={(value) =>
                              setQueueIncidentSyncScheduleFleetStatusFilter(
                                value === "ok" ||
                                  value === "partial_failure" ||
                                  value === "failed" ||
                                  value === "skipped" ||
                                  value === "never"
                                  ? value
                                  : "all",
                              )
                            }
                          />
                          <Select
                            label="Fleet enabled filter"
                            data={[
                              { value: "all", label: "all" },
                              { value: "enabled", label: "enabled" },
                              { value: "disabled", label: "disabled" },
                            ]}
                            value={queueIncidentSyncScheduleFleetEnabledFilter}
                            onChange={(value) =>
                              setQueueIncidentSyncScheduleFleetEnabledFilter(
                                value === "enabled" || value === "disabled" ? value : "all",
                              )
                            }
                          />
                          <Select
                            label="Fleet page size"
                            data={[
                              { value: "25", label: "25" },
                              { value: "50", label: "50" },
                              { value: "100", label: "100" },
                              { value: "200", label: "200" },
                            ]}
                            value={String(queueIncidentSyncScheduleFleetPageSize)}
                            onChange={(value) =>
                              setQueueIncidentSyncScheduleFleetPageSize(
                                Math.max(10, Math.min(200, Number(value || "25"))),
                              )
                            }
                          />
                          <Select
                            label="Fleet sort by"
                            data={[
                              { value: "next_run_at", label: "next run" },
                              { value: "updated_at", label: "updated at" },
                              { value: "last_run_at", label: "last run" },
                              { value: "name", label: "name" },
                              { value: "project_id", label: "project" },
                              { value: "status", label: "status" },
                            ]}
                            value={queueIncidentSyncScheduleFleetSortBy}
                            onChange={(value) =>
                              setQueueIncidentSyncScheduleFleetSortBy(
                                value === "next_run_at" ||
                                  value === "updated_at" ||
                                  value === "last_run_at" ||
                                  value === "name" ||
                                  value === "project_id" ||
                                  value === "status"
                                  ? value
                                  : "next_run_at",
                              )
                            }
                          />
                          <Select
                            label="Fleet sort direction"
                            data={[
                              { value: "asc", label: "ascending" },
                              { value: "desc", label: "descending" },
                            ]}
                            value={queueIncidentSyncScheduleFleetSortDir}
                            onChange={(value) =>
                              setQueueIncidentSyncScheduleFleetSortDir(value === "desc" ? "desc" : "asc")
                            }
                          />
                        </SimpleGrid>
                        <Group gap={12} justify="space-between" align="center">
                          <Group gap={12}>
                            <Switch
                              size="sm"
                              label="Fleet due only"
                              checked={queueIncidentSyncScheduleFleetDueOnly}
                              onChange={(event) => setQueueIncidentSyncScheduleFleetDueOnly(event.currentTarget.checked)}
                            />
                            <Switch
                              size="sm"
                              label="Compact row mode"
                              checked={queueIncidentSyncScheduleFleetCompactMode}
                              onChange={(event) => setQueueIncidentSyncScheduleFleetCompactMode(event.currentTarget.checked)}
                            />
                          </Group>
                          <Group gap={6}>
                            <Button
                              size="xs"
                              variant="light"
                              leftSection={<IconRefresh size={14} />}
                              loading={loadingQueueIncidentSyncScheduleFleet}
                              onClick={() => void loadQueueIncidentSyncScheduleFleet()}
                            >
                              Refresh fleet
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              disabled={loadingQueueIncidentSyncScheduleFleet || queueIncidentSyncScheduleFleetCurrentPage <= 1}
                              onClick={() =>
                                setQueueIncidentSyncScheduleFleetPage((prev) =>
                                  Math.max(1, Math.min(queueIncidentSyncScheduleFleetTotalPages, prev - 1)),
                                )
                              }
                            >
                              Prev page
                            </Button>
                            <Text size="xs" c="dimmed">
                              page {queueIncidentSyncScheduleFleetCurrentPage}/{queueIncidentSyncScheduleFleetTotalPages}
                            </Text>
                            <Button
                              size="xs"
                              variant="subtle"
                              disabled={
                                loadingQueueIncidentSyncScheduleFleet ||
                                !queueIncidentSyncScheduleFleetHasMore ||
                                queueIncidentSyncScheduleFleetCurrentPage >= queueIncidentSyncScheduleFleetTotalPages
                              }
                              onClick={() =>
                                setQueueIncidentSyncScheduleFleetPage((prev) =>
                                  Math.max(1, Math.min(queueIncidentSyncScheduleFleetTotalPages, prev + 1)),
                                )
                              }
                            >
                              Next page
                            </Button>
                          </Group>
                        </Group>
                        <Stack gap={queueIncidentSyncScheduleFleetCompactMode ? 2 : 4}>
                          {queueIncidentSyncScheduleFleetPagedRows.length === 0 && (
                            <Text size="xs" c="dimmed">
                              No schedules match current fleet filters.
                            </Text>
                          )}
                          {queueIncidentSyncScheduleFleetPagedRows.map((schedule) => (
                            <Paper
                              key={`incident-sync-fleet-${schedule.id}`}
                              withBorder
                              radius="md"
                              p="xs"
                              data-testid={`incident-sync-fleet-row-${schedule.id}`}
                            >
                              <Group justify="space-between" align="start">
                                <Stack gap={queueIncidentSyncScheduleFleetCompactMode ? 1 : 2}>
                                  <Text size="xs" fw={600}>
                                    {schedule.project_id} • {schedule.name}
                                  </Text>
                                  <Text size="xs" c="dimmed">
                                    {queueIncidentSyncScheduleFleetCompactMode
                                      ? `${schedule.preset} • ${schedule.interval_minutes}m • ${schedule.last_status || "never"}`
                                      : `preset ${schedule.preset} • every ${schedule.interval_minutes}m • window ${schedule.window_hours}h • limit ${schedule.sync_limit}`}
                                  </Text>
                                  {!queueIncidentSyncScheduleFleetCompactMode && (
                                    <Text size="xs" c="dimmed">
                                      next {fmtDate(schedule.next_run_at)} • last {fmtDate(schedule.last_run_at)} • preflight{" "}
                                      {schedule.preflight_enforcement_mode}
                                    </Text>
                                  )}
                                </Stack>
                                <Group gap={6}>
                                  <Badge variant="light" color={schedule.enabled ? "teal" : "gray"}>
                                    {schedule.enabled ? "enabled" : "disabled"}
                                  </Badge>
                                  <Badge variant="light" color={incidentSyncScheduleStatusColor(schedule.last_status)}>
                                    {schedule.last_status || "never"}
                                  </Badge>
                                  {schedule.enabled &&
                                    schedule.next_run_at &&
                                    Number.isFinite(new Date(schedule.next_run_at).getTime()) &&
                                    new Date(schedule.next_run_at).getTime() <= Date.now() && (
                                      <Badge variant="light" color="orange">
                                        due
                                      </Badge>
                                    )}
                                  <Button
                                    size="xs"
                                    variant="subtle"
                                    onClick={() => {
                                      setQueueIncidentProjectId(schedule.project_id);
                                      setQueueIncidentSyncScheduleName(schedule.name);
                                      setQueueIncidentSyncScheduleTimelineScheduleId(schedule.id);
                                      void loadQueueIncidentSyncScheduleTimeline(schedule.id, true);
                                    }}
                                  >
                                    Load
                                  </Button>
                                  <Button
                                    size="xs"
                                    variant="subtle"
                                    color="grape"
                                    loading={queueIncidentSyncScheduleRunBusy}
                                    onClick={() => void runQueueIncidentSyncSchedules(schedule.id)}
                                  >
                                    Run
                                  </Button>
                                  <Button
                                    size="xs"
                                    color="red"
                                    variant="subtle"
                                    loading={queueIncidentSyncScheduleDeleteBusyId === schedule.id}
                                    onClick={() => void deleteQueueIncidentSyncSchedule(schedule)}
                                  >
                                    Delete
                                  </Button>
                                </Group>
                              </Group>
                            </Paper>
                          ))}
                        </Stack>
                      </Stack>
                    </Paper>
                    <Paper withBorder radius="md" p="xs" mb={6}>
                      <Group justify="space-between" align="center" mb={6}>
                        <Stack gap={2}>
                          <Text size="xs" c="dimmed" fw={700}>
                            Incident sync run timeline
                          </Text>
                          <Text size="xs" c="dimmed">
                            {queueIncidentSyncScheduleTimeline?.schedule
                              ? `${queueIncidentSyncScheduleTimeline.schedule.project_id} • ${queueIncidentSyncScheduleTimeline.schedule.name}`
                              : "Select or run a schedule to populate timeline history."}
                          </Text>
                        </Stack>
                        <Button
                          size="xs"
                          variant="light"
                          leftSection={<IconRefresh size={14} />}
                          loading={loadingQueueIncidentSyncScheduleTimeline}
                          disabled={!queueIncidentSyncScheduleTimelineScheduleId}
                          onClick={() =>
                            void loadQueueIncidentSyncScheduleTimeline(queueIncidentSyncScheduleTimelineScheduleId, false)
                          }
                        >
                          Refresh run timeline
                        </Button>
                      </Group>
                      {queueIncidentSyncScheduleTimeline ? (
                        <Stack gap={6}>
                          <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm">
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed">
                                Runs in window
                              </Text>
                              <Text size="sm" fw={700}>
                                {queueIncidentSyncScheduleTimelineSummary.runs_total}
                              </Text>
                            </Paper>
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed">
                                Ok
                              </Text>
                              <Text size="sm" fw={700}>
                                {queueIncidentSyncScheduleTimelineSummary.ok}
                              </Text>
                            </Paper>
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed">
                                Partial
                              </Text>
                              <Text size="sm" fw={700}>
                                {queueIncidentSyncScheduleTimelineSummary.partial_failure}
                              </Text>
                            </Paper>
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed">
                                Failed
                              </Text>
                              <Text size="sm" fw={700}>
                                {queueIncidentSyncScheduleTimelineSummary.failed}
                              </Text>
                            </Paper>
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed">
                                Latest run
                              </Text>
                              <Text size="sm" fw={700}>
                                {fmtDate(queueIncidentSyncScheduleTimelineSummary.latest_run_at)}
                              </Text>
                            </Paper>
                          </SimpleGrid>
                          <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed" fw={700} mb={4}>
                                Status trend
                              </Text>
                              {queueIncidentSyncScheduleTimelineTrendRows.length > 0 ? (
                                <LineChart
                                  h={220}
                                  data={queueIncidentSyncScheduleTimelineTrendRows}
                                  dataKey="day_label"
                                  withLegend
                                  withTooltip
                                  curveType="monotone"
                                  series={[
                                    { name: "ok", color: "teal.6", label: "Ok" },
                                    { name: "partial_failure", color: "yellow.6", label: "Partial" },
                                    { name: "failed", color: "red.6", label: "Failed" },
                                    { name: "skipped", color: "gray.6", label: "Skipped" },
                                  ]}
                                />
                              ) : (
                                <Text size="xs" c="dimmed">
                                  Trend appears after first runs in selected window.
                                </Text>
                              )}
                            </Paper>
                            <Paper withBorder radius="md" p="xs">
                              <Text size="xs" c="dimmed" fw={700} mb={4}>
                                Failure class breakdown
                              </Text>
                              {queueIncidentSyncScheduleTimelineFailureRows.length > 0 ? (
                                <BarChart
                                  h={220}
                                  data={queueIncidentSyncScheduleTimelineFailureRows.slice(0, 8)}
                                  dataKey="code"
                                  withTooltip
                                  series={[{ name: "count", color: "red.6", label: "Runs" }]}
                                />
                              ) : (
                                <Text size="xs" c="dimmed">
                                  No failure classes in selected window.
                                </Text>
                              )}
                            </Paper>
                          </SimpleGrid>
                          <Stack gap={3}>
                            <Text size="xs" c="dimmed" fw={700}>
                              Latest timeline runs
                            </Text>
                            {queueIncidentSyncScheduleTimelineRuns.length === 0 && (
                              <Text size="xs" c="dimmed">
                                No run events captured for this schedule yet.
                              </Text>
                            )}
                            {queueIncidentSyncScheduleTimelineRuns.slice(0, 8).map((item) => (
                              <Paper key={`incident-sync-timeline-${item.audit_event_id}`} withBorder radius="md" p="xs">
                                <Group justify="space-between" align="start">
                                  <Stack gap={2}>
                                    <Text size="xs" fw={600}>
                                      {item.action} • {fmtDate(item.created_at)}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                      actor {item.actor}
                                      {item.reason ? ` • ${item.reason}` : ""}
                                      {item.next_run_at ? ` • next ${fmtDate(item.next_run_at)}` : ""}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                      opened {item.sync_summary.opened}, resolved {item.sync_summary.resolved}, failed{" "}
                                      {item.sync_summary.failed}, blocked {item.sync_summary.blocked}, paused {item.sync_summary.paused}
                                    </Text>
                                    {item.failure_classes.length > 0 && (
                                      <Text size="xs" c="dimmed">
                                        classes: {item.failure_classes.join(", ")}
                                      </Text>
                                    )}
                                    {item.error && (
                                      <Text size="xs" c="red">
                                        {item.error}
                                      </Text>
                                    )}
                                  </Stack>
                                  <Group gap={6}>
                                    <Badge variant="light" color={incidentSyncScheduleStatusColor(item.status)}>
                                      {item.status}
                                    </Badge>
                                    <Button
                                      size="xs"
                                      variant="subtle"
                                      color="blue"
                                      onClick={() => {
                                        setQueueAuditFocusEventId(Number(item.audit_event_id));
                                        queueAuditSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                                      }}
                                    >
                                      Open audit #{item.audit_event_id}
                                    </Button>
                                  </Group>
                                </Group>
                              </Paper>
                            ))}
                          </Stack>
                        </Stack>
                      ) : (
                        <Text size="xs" c="dimmed">
                          Timeline will appear once schedule history is available.
                        </Text>
                      )}
                    </Paper>
                    {queueIncidentSyncScheduleRunResult && (
                      <Paper withBorder radius="md" p="xs">
                        <Stack gap={6}>
                          <Group gap={8}>
                            <Text size="xs" fw={700}>
                              Last schedule run
                            </Text>
                            <Badge
                              size="xs"
                              variant="light"
                              color={queueIncidentSyncScheduleRunResult.status === "ok" ? "teal" : "orange"}
                            >
                              {queueIncidentSyncScheduleRunResult.status}
                            </Badge>
                            <Text size="xs" c="dimmed">
                              generated {fmtDate(queueIncidentSyncScheduleRunResult.generated_at)}
                            </Text>
                          </Group>
                          <Text size="xs" c="dimmed">
                            executed {queueIncidentSyncScheduleRunResult.summary.executed}/
                            {queueIncidentSyncScheduleRunResult.summary.schedules_total} • failed{" "}
                            {queueIncidentSyncScheduleRunResult.summary.failed} • blocked{" "}
                            {queueIncidentSyncScheduleRunResult.summary.blocked} • paused{" "}
                            {queueIncidentSyncScheduleRunResult.summary.paused}
                          </Text>
                          <Stack gap={4}>
                            {queueIncidentSyncScheduleRunRows.slice(0, 8).map((item) => (
                              <Paper
                                key={`incident-sync-run-${item.schedule_id}`}
                                withBorder
                                radius="md"
                                p="xs"
                                style={{
                                  cursor: "pointer",
                                  borderColor:
                                    queueIncidentSyncScheduleSelectedRunRow?.schedule_id === item.schedule_id
                                      ? "var(--mantine-color-grape-5)"
                                      : undefined,
                                }}
                                onClick={() => {
                                  setQueueIncidentSyncScheduleRunSelectedScheduleId(item.schedule_id);
                                  setQueueIncidentSyncScheduleTimelineScheduleId(item.schedule_id);
                                  void loadQueueIncidentSyncScheduleTimeline(item.schedule_id, true);
                                }}
                              >
                                <Group justify="space-between" align="start">
                                  <Stack gap={2}>
                                    <Text size="xs" fw={600}>
                                      {item.project_id} • {item.name}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                      status {item.status}
                                      {item.sync_summary
                                        ? ` • opened ${item.sync_summary.opened}, resolved ${item.sync_summary.resolved}, failed ${item.sync_summary.failed}`
                                        : ""}
                                      {item.audit_event_id != null ? ` • audit #${item.audit_event_id}` : ""}
                                    </Text>
                                    {item.error && (
                                      <Text size="xs" c="red">
                                        {item.error}
                                      </Text>
                                    )}
                                  </Stack>
                                  <Group gap={6}>
                                    <Badge variant="light" color={incidentSyncScheduleStatusColor(item.status)}>
                                      {item.status}
                                    </Badge>
                                    <Button
                                      size="xs"
                                      variant="subtle"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      setQueueIncidentSyncScheduleRunSelectedScheduleId(item.schedule_id);
                                      setQueueIncidentSyncScheduleTimelineScheduleId(item.schedule_id);
                                      void loadQueueIncidentSyncScheduleTimeline(item.schedule_id, true);
                                    }}
                                  >
                                    Open trace
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant="subtle"
                                      color="grape"
                                      loading={queueIncidentSyncScheduleRunBusy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void runQueueIncidentSyncSchedules(item.schedule_id);
                                      }}
                                    >
                                      Retry
                                    </Button>
                                  </Group>
                                </Group>
                              </Paper>
                            ))}
                          </Stack>
                          {queueIncidentSyncScheduleSelectedRunRow && (
                            <Paper withBorder radius="md" p="xs">
                              <Stack gap={4}>
                                <Group justify="space-between" align="center">
                                  <Text size="xs" fw={700}>
                                    Run drill-down • {queueIncidentSyncScheduleSelectedRunRow.project_id} /{" "}
                                    {queueIncidentSyncScheduleSelectedRunRow.name}
                                  </Text>
                                  <Group gap={6}>
                                    <Badge
                                      variant="light"
                                      color={incidentSyncScheduleStatusColor(queueIncidentSyncScheduleSelectedRunRow.status)}
                                    >
                                      {queueIncidentSyncScheduleSelectedRunRow.status}
                                    </Badge>
                                    {queueIncidentSyncScheduleSelectedRunRow.audit_event_id != null && (
                                      <Button
                                        size="xs"
                                        variant="subtle"
                                        color="blue"
                                        onClick={() => {
                                          setQueueAuditFocusEventId(Number(queueIncidentSyncScheduleSelectedRunRow.audit_event_id));
                                          queueAuditSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                                        }}
                                      >
                                        Open audit #{queueIncidentSyncScheduleSelectedRunRow.audit_event_id}
                                      </Button>
                                    )}
                                  </Group>
                                </Group>
                                <Text size="xs" c="dimmed">
                                  actor {queueIncidentSyncScheduleSelectedRunRow.run_actor}
                                  {queueIncidentSyncScheduleSelectedRunRow.sync_generated_at
                                    ? ` • generated ${fmtDate(queueIncidentSyncScheduleSelectedRunRow.sync_generated_at)}`
                                    : ""}
                                </Text>
                                {queueIncidentSyncScheduleSelectedRunAuditEvent && (
                                  <Text size="xs" c="dimmed">
                                    audit event #{queueIncidentSyncScheduleSelectedRunAuditEvent.id} •{" "}
                                    {queueIncidentSyncScheduleSelectedRunAuditEvent.action} •{" "}
                                    {fmtDate(queueIncidentSyncScheduleSelectedRunAuditEvent.created_at)}
                                  </Text>
                                )}
                                {queueIncidentSyncScheduleSelectedRunRow.sync_trace && (
                                  <Textarea
                                    readOnly
                                    label="Sync trace payload"
                                    autosize
                                    minRows={8}
                                    maxRows={20}
                                    value={JSON.stringify(queueIncidentSyncScheduleSelectedRunRow.sync_trace, null, 2)}
                                  />
                                )}
                                {queueIncidentSyncScheduleSelectedRunRow.error && (
                                  <Text size="xs" c="red">
                                    Error: {queueIncidentSyncScheduleSelectedRunRow.error}
                                  </Text>
                                )}
                              </Stack>
                            </Paper>
                          )}
                        </Stack>
                      </Paper>
                    )}
                  </Paper>

                  {queueIncidentPolicyRows.length > 0 && (
                    <Stack gap={2} mb={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Active alert policies
                      </Text>
                      {queueIncidentPolicyRows.slice(0, 8).map((policy) => (
                        <Text key={`queue-policy-${policy.id}`} size="xs" c="dimmed">
                          {policy.project_id} • {policy.alert_code} • p{policy.priority} •{" "}
                          {policy.provider_override || "inherit"} • {policy.enabled ? "enabled" : "disabled"}
                        </Text>
                      ))}
                    </Stack>
                  )}

                  {queueOpenIncidentRows.length > 0 && (
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Open incidents
                      </Text>
                      {queueOpenIncidentRows.slice(0, 8).map((incident) => (
                        <Text key={`queue-open-incident-${incident.id}`} size="xs" c="dimmed">
                          {incident.project_id} • {incident.external_provider} • {incident.trigger_health}
                          {incident.external_ticket_id ? ` • ticket ${incident.external_ticket_id}` : ""}
                          {incident.external_ticket_url ? ` • ${incident.external_ticket_url}` : ""}
                        </Text>
                      ))}
                    </Stack>
                  )}
                  {queueOpenIncidentRows.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No open queue incidents currently.
                    </Text>
                  )}
                </Paper>

                {queueCommandCenterRows.length === 0 && (
                  <Text size="xs" c="dimmed">
                    No projects found for queue command center.
                  </Text>
                )}

                <Stack gap={4}>
                  {queueCommandCenterRows.map((item) => {
                    const enforcementMode = normalizeIncidentPreflightEnforcementMode(
                      item.control?.incident_preflight_enforcement_mode,
                    );
                    const enforcementPauseHours = Math.max(
                      1,
                      Math.min(168, Number(item.control?.incident_preflight_pause_hours || 4)),
                    );
                    const enforcementCriticalThreshold = Math.max(
                      1,
                      Math.min(100, Number(item.control?.incident_preflight_critical_fail_threshold || 1)),
                    );
                    return (
                      <Paper key={`queue-command-${item.project_id}`} withBorder radius="md" p="xs">
                        <Group justify="space-between" align="center">
                          <Stack gap={2}>
                            <Text size="sm" fw={700}>
                              {item.project_id}
                            </Text>
                            <Text size="xs" c="dimmed">
                              depth {item.queue.depth_total} • queued {item.queue.queued} • running {item.queue.running}
                            </Text>
                            <Text size="xs" c="dimmed">
                              preflight {enforcementMode} • critical &gt;= {enforcementCriticalThreshold} • pause{" "}
                              {enforcementPauseHours}h
                            </Text>
                            <Text size="xs" c="dimmed">
                              owner {item.ownership?.owner_name || "unassigned"}
                              {item.ownership?.oncall_channel ? ` • on-call ${item.ownership.oncall_channel}` : ""}
                            </Text>
                            {item.incident?.status === "open" && (
                              <Text size="xs" c="dimmed">
                                incident open
                                {item.incident.external_ticket_id ? ` • ticket ${item.incident.external_ticket_id}` : ""}
                              </Text>
                            )}
                          </Stack>
                          <Group gap={6}>
                            <Badge variant="light" color={healthColor(item.health)}>
                              {item.health}
                            </Badge>
                            <Badge variant="light" color={incidentPreflightEnforcementColor(enforcementMode)}>
                              preflight {enforcementMode}
                            </Badge>
                            <Badge variant="light" color={item.control.pause_active ? "yellow" : "teal"}>
                              {item.control.pause_active ? "paused" : "active"}
                            </Badge>
                            {item.incident?.status === "open" && (
                              <Badge variant="light" color="red">
                                incident open
                              </Badge>
                            )}
                          </Group>
                        </Group>
                      </Paper>
                    );
                  })}
                </Stack>

                <Paper ref={queueAuditSectionRef} withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Queue autoscaling recommendations
                      </Text>
                      <Text size="xs" c="dimmed">
                        Rolling history recommendations for worker concurrency and lag budget tuning.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueAutoscaling}
                      onClick={() => void loadQueueAutoscaling()}
                    >
                      Refresh autoscaling
                    </Button>
                  </Group>
                  {queueAutoscalingRows.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No autoscaling recommendations yet.
                    </Text>
                  )}
                  <Stack gap={4}>
                    {queueAutoscalingRows.slice(0, 10).map((item) => (
                      <Paper key={`queue-autoscaling-${item.project_id}`} withBorder radius="md" p="xs">
                        <Group justify="space-between" align="center">
                          <Stack gap={2}>
                            <Text size="sm" fw={700}>
                              {item.project_id}
                            </Text>
                            <Text size="xs" c="dimmed">
                              workers {item.current.worker_concurrency_estimate} → {item.recommendation.worker_concurrency_target}
                              {" • "}
                              lag SLA {item.current.worker_lag_sla_minutes}m → {item.recommendation.worker_lag_sla_minutes}m
                              {" • "}
                              depth warn {item.current.queue_depth_warn} → {item.recommendation.queue_depth_warn}
                            </Text>
                          </Stack>
                          <Group gap={6}>
                            <Badge variant="light" color={healthColor(item.health)}>
                              {item.health}
                            </Badge>
                            <Badge
                              variant="light"
                              color={item.recommendation.worker_concurrency_delta > 0 ? "orange" : item.recommendation.worker_concurrency_delta < 0 ? "blue" : "teal"}
                            >
                              workers delta {item.recommendation.worker_concurrency_delta >= 0 ? "+" : ""}
                              {item.recommendation.worker_concurrency_delta}
                            </Badge>
                            <Badge variant="light" color="gray">
                              confidence {(Number(item.recommendation.confidence || 0) * 100).toFixed(0)}%
                            </Badge>
                            <Button
                              size="xs"
                              variant="light"
                              loading={queueRecommendationBusyProjectId === item.project_id}
                              onClick={() => void applyQueueRecommendation(item)}
                            >
                              Apply controls
                            </Button>
                          </Group>
                        </Group>
                        {item.actions.length > 0 && (
                          <Stack gap={2} mt={4}>
                            {item.actions.slice(0, 2).map((action) => (
                              <Text key={`queue-autoscaling-${item.project_id}-${action.id}`} size="xs" c="dimmed">
                                [{action.priority}] {action.title}
                              </Text>
                            ))}
                          </Stack>
                        )}
                      </Paper>
                    ))}
                  </Stack>
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Cross-project incident SLO board
                      </Text>
                      <Text size="xs" c="dimmed">
                        MTTA/MTTR posture, rotation lag, and secret rotation hygiene in one live board.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueIncidentSloBoard}
                      onClick={() => void loadQueueIncidentSloBoard()}
                    >
                      Refresh SLO board
                    </Button>
                  </Group>
                  {queueIncidentSloBoard && (
                    <SimpleGrid cols={{ base: 1, xl: 6 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Projects tracked
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.projects_total}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Open incidents
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.open_incidents}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Over MTTR SLA
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.open_incidents_over_mttr_sla}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          MTTA p90
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.mtta_proxy_minutes.p90 == null
                            ? "—"
                            : `${queueIncidentSloSummary.mtta_proxy_minutes.p90}m`}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          MTTR p90
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.mttr_minutes.p90 == null ? "—" : `${queueIncidentSloSummary.mttr_minutes.p90}m`}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Secret gaps
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentSloSummary.secret_missing_required} missing • {queueIncidentSloSummary.secret_stale_required} stale
                        </Text>
                      </Paper>
                    </SimpleGrid>
                  )}
                  <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mb={6}>
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        MTTA/MTTR p90 trend
                      </Text>
                      {queueIncidentSloTrendRows.length > 0 ? (
                        <LineChart
                          h={220}
                          data={queueIncidentSloTrendRows}
                          dataKey="day"
                          withLegend
                          withTooltip
                          curveType="monotone"
                          series={[
                            { name: "mtta_proxy_minutes_p90", color: "cyan.6", label: "MTTA p90 (m)" },
                            { name: "mttr_minutes_p90", color: "orange.6", label: "MTTR p90 (m)" },
                            { name: "opened_incidents", color: "blue.5", label: "Opened" },
                            { name: "resolved_incidents", color: "teal.6", label: "Resolved" },
                          ]}
                        />
                      ) : (
                        <Text size="xs" c="dimmed">
                          No SLO trend data yet.
                        </Text>
                      )}
                    </Paper>
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        Secret posture by project
                      </Text>
                      {queueIncidentSloSecretPostureRows.some((item) => item.projects > 0) ? (
                        <BarChart
                          h={220}
                          data={queueIncidentSloSecretPostureRows}
                          dataKey="posture"
                          withTooltip
                          series={[{ name: "projects", color: "grape.6", label: "Projects" }]}
                        />
                      ) : (
                        <Text size="xs" c="dimmed">
                          No secret-dependent adapters detected in scope.
                        </Text>
                      )}
                    </Paper>
                  </SimpleGrid>
                  <Stack gap={4}>
                    {queueIncidentSloRows.slice(0, 8).map((item) => (
                      <Paper key={`queue-incident-slo-${item.project_id}`} withBorder radius="md" p="xs">
                        <Group justify="space-between" align="start">
                          <Stack gap={2}>
                            <Text size="sm" fw={700}>
                              {item.project_id}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {item.slo_status} • health {item.health} • depth {item.queue_depth}
                              {item.incident.open ? ` • open age ${item.incident.open_age_minutes ?? "—"}m` : " • no open incident"}
                            </Text>
                            <Text size="xs" c="dimmed">
                              MTTA {item.slo.mtta_proxy_value_minutes == null ? "—" : `${item.slo.mtta_proxy_value_minutes}m`} / SLA{" "}
                              {item.slo.mtta_proxy_sla_minutes}m • MTTR{" "}
                              {item.slo.mttr_value_minutes == null ? "—" : `${item.slo.mttr_value_minutes}m`} / SLA{" "}
                              {item.slo.mttr_sla_minutes}m
                            </Text>
                            <Text size="xs" c="dimmed">
                              owner {item.ownership.owner_name ?? "unassigned"} • rotation lag{" "}
                              {item.ownership.rotation_lag_hours == null ? "—" : `${item.ownership.rotation_lag_hours.toFixed(1)}h`}
                            </Text>
                            <Text size="xs" c="dimmed">
                              secrets {item.secrets.configured}/{item.secrets.required} • missing {item.secrets.missing_required} • stale{" "}
                              {item.secrets.stale_required}
                            </Text>
                          </Stack>
                          <Group gap={6} align="flex-start">
                            <Badge variant="light" color={healthColor(item.slo_status)}>
                              {item.slo_status}
                            </Badge>
                            <Badge variant="light" color={incidentRiskColor(item.risk_score)}>
                              risk {item.risk_score}
                            </Badge>
                            {item.slo.mttr_over_sla && (
                              <Badge variant="light" color="red">
                                mttr breach
                              </Badge>
                            )}
                            {item.slo.mtta_proxy_over_sla && (
                              <Badge variant="light" color="orange">
                                mtta breach
                              </Badge>
                            )}
                          </Group>
                        </Group>
                      </Paper>
                    ))}
                    {queueIncidentSloRows.length === 0 && (
                      <Text size="xs" c="dimmed">
                        No incident SLO signals yet.
                      </Text>
                    )}
                  </Stack>
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Incident escalation digest
                      </Text>
                      <Text size="xs" c="dimmed">
                        Prioritized unresolved incidents with ownership/routing gaps for on-call escalation.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueIncidentEscalationDigest}
                      onClick={() => void loadQueueIncidentEscalationDigest()}
                    >
                      Refresh escalation digest
                    </Button>
                  </Group>
                  {queueIncidentEscalationDigest && (
                    <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Open incidents
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentEscalationDigest.summary.open_incidents}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Over SLA
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentEscalationDigest.summary.open_incidents_over_sla}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Routing ready
                        </Text>
                        <Text size="sm" fw={700}>
                          {asPercent(queueIncidentEscalationDigest.summary.routing_ready_rate)}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Missing escalation channel
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentEscalationDigest.summary.incidents_missing_escalation_channel}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Ownership gap projects
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueIncidentEscalationDigest.summary.ownership_gap_projects}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                  )}
                  {queueIncidentEscalationDigest && (
                    <Stack gap={4} mb={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Incident age distribution
                      </Text>
                      <Progress
                        size="md"
                        radius="xl"
                        sections={[
                          { value: (queueEscalationAges.under_1h / queueEscalationAgeTotal) * 100, color: "teal" },
                          { value: (queueEscalationAges.between_1h_4h / queueEscalationAgeTotal) * 100, color: "lime" },
                          { value: (queueEscalationAges.between_4h_12h / queueEscalationAgeTotal) * 100, color: "yellow" },
                          { value: (queueEscalationAges.between_12h_24h / queueEscalationAgeTotal) * 100, color: "orange" },
                          { value: (queueEscalationAges.between_24h_72h / queueEscalationAgeTotal) * 100, color: "red" },
                          { value: (queueEscalationAges.over_72h / queueEscalationAgeTotal) * 100, color: "grape" },
                          { value: (queueEscalationAges.unknown / queueEscalationAgeTotal) * 100, color: "gray" },
                        ]}
                      />
                      <Text size="xs" c="dimmed">
                        &lt;1h {queueEscalationAges.under_1h} • 1-4h {queueEscalationAges.between_1h_4h} • 4-12h{" "}
                        {queueEscalationAges.between_4h_12h} • 12-24h {queueEscalationAges.between_12h_24h} • 24-72h{" "}
                        {queueEscalationAges.between_24h_72h} • &gt;72h {queueEscalationAges.over_72h} • unknown{" "}
                        {queueEscalationAges.unknown}
                      </Text>
                    </Stack>
                  )}
                  <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        Escalation queue
                      </Text>
                      <Stack gap={4}>
                        {queueEscalationCandidates.slice(0, 6).map((item) => (
                          <Paper key={`queue-escalation-${item.project_id}`} withBorder radius="md" p="xs">
                            <Group justify="space-between" align="start">
                              <Stack gap={2}>
                                <Text size="sm" fw={700}>
                                  {item.project_id}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  provider {item.incident.external_provider || "unknown"} • opened {fmtDate(item.incident.opened_at)}
                                  {item.incident.age_minutes == null ? "" : ` • age ${item.incident.age_minutes.toFixed(1)}m`}
                                  {item.incident.ticket_id ? ` • ticket ${item.incident.ticket_id}` : ""}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  owner {item.ownership.owner_name ?? "unassigned"} • oncall {item.ownership.oncall_channel ?? "missing"} •
                                  escalation {item.ownership.escalation_channel ?? "missing"}
                                </Text>
                                {item.missing_fields.length > 0 && (
                                  <Text size="xs" c="dimmed">
                                    missing: {item.missing_fields.join(", ")}
                                  </Text>
                                )}
                                <Text size="xs" c="dimmed">
                                  next action: {item.recommended_action.replace(/_/g, " ")}
                                </Text>
                              </Stack>
                              <Stack gap={4} align="flex-end">
                                <Badge variant="light" color={incidentRiskColor(item.risk_score)}>
                                  risk {item.risk_score}
                                </Badge>
                                <Badge variant="light" color={healthColor(item.health)}>
                                  {item.health}
                                </Badge>
                                {item.over_sla && (
                                  <Badge variant="light" color="red">
                                    over sla
                                  </Badge>
                                )}
                              </Stack>
                            </Group>
                          </Paper>
                        ))}
                        {queueEscalationCandidates.length === 0 && (
                          <Text size="xs" c="dimmed">
                            No open incidents currently.
                          </Text>
                        )}
                      </Stack>
                    </Paper>

                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed" fw={700} mb={4}>
                        Ownership gaps
                      </Text>
                      <Stack gap={4}>
                        {queueEscalationOwnershipGaps.slice(0, 6).map((item) => (
                          <Paper key={`queue-escalation-gap-${item.project_id}`} withBorder radius="md" p="xs">
                            <Group justify="space-between" align="center">
                              <Stack gap={2}>
                                <Text size="sm" fw={700}>
                                  {item.project_id}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  {item.health} • depth {item.queue_depth}
                                  {item.incident_open ? " • incident open" : ""}
                                  {item.incident_age_minutes == null ? "" : ` • incident age ${item.incident_age_minutes.toFixed(1)}m`}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  missing: {item.missing_fields.join(", ")}
                                </Text>
                              </Stack>
                              <Badge variant="light" color={item.gap_score >= 8 ? "red" : item.gap_score >= 5 ? "orange" : "yellow"}>
                                gap {item.gap_score}
                              </Badge>
                            </Group>
                          </Paper>
                        ))}
                        {queueEscalationOwnershipGaps.length === 0 && (
                          <Text size="xs" c="dimmed">
                            No ownership gaps detected.
                          </Text>
                        )}
                      </Stack>
                    </Paper>
                  </SimpleGrid>
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Governance drift dashboard
                      </Text>
                      <Text size="xs" c="dimmed">
                        Ownership coverage drift and unresolved pause-age distribution.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueGovernanceDrift}
                      onClick={() => void loadQueueGovernanceDrift()}
                    >
                      Refresh governance drift
                    </Button>
                  </Group>
                  {queueGovernanceDrift && (
                    <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Owner coverage
                        </Text>
                        <Text size="sm" fw={700}>
                          {(Number(queueGovernanceDrift.summary.ownership_coverage.owner_name_rate || 0) * 100).toFixed(0)}%
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Unresolved pauses
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDrift.summary.unresolved_pauses}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Critical without owner
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDrift.summary.critical_without_owner}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Incidents without owner
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDrift.summary.open_incidents_without_owner}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                  )}
                  {queueGovernanceDrift && (
                    <Stack gap={2} mb={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Pause age buckets
                      </Text>
                      <Text size="xs" c="dimmed">
                        &lt;1h {queueGovernanceDrift.pause_age_buckets.under_1h} • 1-4h {queueGovernanceDrift.pause_age_buckets.between_1h_4h}
                        {" • "}
                        4-12h {queueGovernanceDrift.pause_age_buckets.between_4h_12h} • 12-24h {queueGovernanceDrift.pause_age_buckets.between_12h_24h}
                        {" • "}
                        &gt;24h {queueGovernanceDrift.pause_age_buckets.over_24h}
                      </Text>
                    </Stack>
                  )}
                  <Stack gap={4}>
                    {(queueGovernanceDrift?.drift_projects ?? []).slice(0, 8).map((item) => (
                      <Paper key={`queue-drift-${item.project_id}`} withBorder radius="md" p="xs">
                        <Group justify="space-between" align="center">
                          <Stack gap={2}>
                            <Text size="sm" fw={700}>
                              {item.project_id}
                            </Text>
                            <Text size="xs" c="dimmed">
                              risk {item.risk_score} • {item.health} • depth {item.queue_depth}
                              {item.pause_age_minutes == null ? "" : ` • pause age ${item.pause_age_minutes.toFixed(1)}m`}
                              {item.incident_open ? " • incident open" : ""}
                            </Text>
                            {item.missing_fields.length > 0 && (
                              <Text size="xs" c="dimmed">
                                missing: {item.missing_fields.join(", ")}
                              </Text>
                            )}
                          </Stack>
                          <Badge variant="light" color={item.risk_score >= 6 ? "red" : item.risk_score >= 3 ? "yellow" : "teal"}>
                            risk {item.risk_score}
                          </Badge>
                        </Group>
                      </Paper>
                    ))}
                    {(!queueGovernanceDrift || queueGovernanceDrift.drift_projects.length === 0) && (
                      <Text size="xs" c="dimmed">
                        No governance drift signals detected.
                      </Text>
                    )}
                  </Stack>
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Daily queue governance digest
                      </Text>
                      <Text size="xs" c="dimmed">
                        Top congestion and unreviewed pause windows for daily operations review.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueGovernanceDigest}
                      onClick={() => void loadQueueGovernanceDigest()}
                    >
                      Refresh digest
                    </Button>
                  </Group>
                  {queueGovernanceDigest && (
                    <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Projects
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDigest.summary.projects_total}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Critical/watch
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDigest.summary.critical_projects} / {queueGovernanceDigest.summary.watch_projects}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Unreviewed pauses
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDigest.summary.unreviewed_pauses}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Open incidents
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueGovernanceDigest.summary.open_incidents}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                  )}
                  {queueDigestTopCongestion.length === 0 && queueDigestUnreviewedPauses.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No queue governance digest data yet.
                    </Text>
                  )}
                  {queueDigestTopCongestion.length > 0 && (
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Top congestion
                      </Text>
                      {queueDigestTopCongestion.slice(0, 5).map((item) => (
                        <Text key={`queue-digest-congestion-${item.project_id}`} size="xs" c="dimmed">
                          {item.project_id} • {item.health} • depth {item.queue_depth}
                          {item.ownership?.owner_name ? ` • owner ${item.ownership.owner_name}` : ""}
                          {item.incident?.status === "open" ? " • incident open" : ""}
                          {item.queued_wait_p90_minutes == null ? "" : ` • wait p90 ${item.queued_wait_p90_minutes}m`}
                        </Text>
                      ))}
                    </Stack>
                  )}
                  {queueDigestUnreviewedPauses.length > 0 && (
                    <Stack gap={2} mt={6}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Unreviewed pauses
                      </Text>
                      {queueDigestUnreviewedPauses.slice(0, 5).map((item) => (
                        <Text key={`queue-digest-pause-${item.project_id}`} size="xs" c="dimmed">
                          {item.project_id} • {item.latest_action} • actor {item.latest_actor ?? "unknown"}
                          {item.ownership?.owner_name ? ` • owner ${item.ownership.owner_name}` : ""}
                          {item.pause_age_minutes == null ? "" : ` • age ${item.pause_age_minutes.toFixed(1)}m`}
                        </Text>
                      ))}
                    </Stack>
                  )}
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Owner queue performance rollups
                      </Text>
                      <Text size="xs" c="dimmed">
                        SLA/MTTR and congestion metrics grouped by owner and on-call channel.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueOwnerRollups}
                      onClick={() => void loadQueueOwnerRollups()}
                    >
                      Refresh owner rollups
                    </Button>
                  </Group>
                  {queueOwnerRollups && (
                    <SimpleGrid cols={{ base: 1, xl: 4 }} spacing="sm" mb={6}>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Owners
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueOwnerRollups.summary.owners_total}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Open incidents
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueOwnerRollups.summary.open_incidents}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          Pending governance events
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueOwnerRollups.summary.pending_events}
                        </Text>
                      </Paper>
                      <Paper withBorder radius="md" p="xs">
                        <Text size="xs" c="dimmed">
                          SLA breaches
                        </Text>
                        <Text size="sm" fw={700}>
                          {queueOwnerRollups.summary.sla_breaches}
                        </Text>
                      </Paper>
                    </SimpleGrid>
                  )}
                  <Stack gap={4}>
                    {(queueOwnerRollups?.owners ?? []).slice(0, 6).map((owner) => (
                      <Paper key={`queue-owner-rollup-${owner.owner_key}`} withBorder radius="md" p="xs">
                        <Group justify="space-between" align="center">
                          <Stack gap={2}>
                            <Text size="sm" fw={700}>
                              {owner.owner_name}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {owner.oncall_channel} • projects {owner.projects_total} • depth total {owner.queue_depth_total}
                            </Text>
                            <Text size="xs" c="dimmed">
                              critical/watch {owner.health.critical}/{owner.health.watch} • incidents {owner.open_incidents}
                              {" • "}
                              MTTR p90 {owner.governance.mttr_minutes.p90 == null ? "—" : `${owner.governance.mttr_minutes.p90}m`}
                              {" • "}
                              SLA breaches {owner.governance.sla_breaches}
                            </Text>
                          </Stack>
                          <Group gap={6}>
                            <Badge variant="light" color={owner.health.critical > 0 ? "red" : owner.health.watch > 0 ? "yellow" : "teal"}>
                              {owner.health.critical > 0 ? "critical" : owner.health.watch > 0 ? "watch" : "healthy"}
                            </Badge>
                            <Badge variant="light" color={owner.governance.sla_breaches > 0 ? "orange" : "teal"}>
                              SLA {owner.governance.sla_breaches > 0 ? "breach" : "ok"}
                            </Badge>
                          </Group>
                        </Group>
                      </Paper>
                    ))}
                    {(!queueOwnerRollups || queueOwnerRollups.owners.length === 0) && (
                      <Text size="xs" c="dimmed">
                        No owner rollups yet.
                      </Text>
                    )}
                  </Stack>
                </Paper>

                <Paper withBorder radius="md" p="xs" mt={8}>
                  <Group justify="space-between" align="center" mb={6}>
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed" fw={700}>
                        Queue governance audit
                      </Text>
                      <Text size="xs" c="dimmed">
                        Who changed queue controls, when, and why.
                      </Text>
                    </Stack>
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconRefresh size={14} />}
                      loading={loadingQueueAudit}
                      onClick={() => void loadQueueAudit()}
                    >
                      Refresh audit
                    </Button>
                  </Group>
                  <Stack gap={3}>
                    {(!queueAudit || queueAudit.events.length === 0) && (
                      <Text size="xs" c="dimmed">
                        No queue-control events in current window.
                      </Text>
                    )}
                    {(queueAudit?.events ?? []).slice(0, 10).map((event) => (
                      <Paper
                        key={`queue-audit-${event.id}`}
                        withBorder
                        radius="md"
                        p="xs"
                        style={{
                          borderColor:
                            queueAuditFocusEventId != null && Number(event.id) === queueAuditFocusEventId
                              ? "var(--mantine-color-grape-5)"
                              : undefined,
                        }}
                      >
                        <Group justify="space-between" align="center">
                          <Stack gap={2}>
                            <Text size="xs" c="dimmed">
                              #{event.id} • {fmtDate(event.created_at)} • {event.project_id} • {event.action} • {event.actor}
                              {event.reason ? ` • ${event.reason}` : ""}
                              {event.paused_until ? ` • until ${fmtDate(event.paused_until)}` : ""}
                            </Text>
                            {event.annotation && (
                              <Text size="xs" c="dimmed">
                                {event.annotation.status} by {event.annotation.created_by ?? "unknown"}
                                {event.annotation.follow_up_owner ? ` • owner ${event.annotation.follow_up_owner}` : ""}
                              </Text>
                            )}
                          </Stack>
                          <Group gap={6}>
                            {event.annotation?.status === "resolved" ? (
                              <Badge variant="light" color="teal">
                                resolved
                              </Badge>
                            ) : (
                              <>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="blue"
                                  loading={queueAuditActionBusyId === `acknowledge:${event.id}`}
                                  onClick={() => void annotateQueueAuditEvent(event, "acknowledge")}
                                >
                                  Acknowledge
                                </Button>
                                <Button
                                  size="xs"
                                  variant="light"
                                  color="teal"
                                  loading={queueAuditActionBusyId === `resolve:${event.id}`}
                                  onClick={() => void annotateQueueAuditEvent(event, "resolve")}
                                >
                                  Resolve
                                </Button>
                              </>
                            )}
                          </Group>
                        </Group>
                      </Paper>
                    ))}
                  </Stack>
                </Paper>
              </Paper>
            </Paper>
          )}

          {queueRows.length === 0 && (
            <Text size="xs" c="dimmed">
              No queued/running/completed operations yet.
            </Text>
          )}

          <Stack gap={6}>
            {queueRows.map((run) => {
              const isActive = ["queued", "running", "cancel_requested"].includes(run.status);
              const canCancel = run.status === "queued" || run.status === "running" || run.status === "cancel_requested";
              const canRetry = run.status === "failed" || run.status === "canceled";
              return (
                <Paper
                  key={`queue-run-${run.id}`}
                  withBorder
                  radius="md"
                  p="xs"
                  style={{
                    cursor: "pointer",
                    borderColor: selectedOperationRunId === run.id ? "var(--mantine-color-blue-4)" : undefined,
                  }}
                  onClick={() => setSelectedOperationRunId(run.id)}
                >
                  <Group justify="space-between" align="center" mb={4}>
                    <Stack gap={2}>
                      <Text size="sm" fw={700}>
                        {run.id.slice(0, 8)} • {run.dry_run ? "dry-run" : "live"}
                      </Text>
                      <Text size="xs" c="dimmed">
                        phase {run.progress_phase ?? "—"} • attempt {run.attempt_no}/{run.max_attempts} • created {fmtDate(run.created_at)}
                      </Text>
                    </Stack>
                    <Group gap={6}>
                      <Badge variant="light" color={operationResultColor(run.status)}>
                        {run.status}
                      </Badge>
                      <Button
                        size="xs"
                        variant="subtle"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedOperationRunId(run.id);
                        }}
                      >
                        Inspect
                      </Button>
                      <Button
                        size="xs"
                        variant="light"
                        color="orange"
                        loading={operationActionLoading === run.id}
                        disabled={!canCancel}
                        onClick={(event) => {
                          event.stopPropagation();
                          void cancelOperationRun(run);
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="xs"
                        variant="light"
                        color="teal"
                        loading={operationActionLoading === run.id}
                        disabled={!canRetry}
                        onClick={(event) => {
                          event.stopPropagation();
                          void retryOperationRun(run);
                        }}
                      >
                        Retry
                      </Button>
                    </Group>
                  </Group>
                  <Progress
                    size="sm"
                    radius="xl"
                    value={Math.max(0, Math.min(100, Number(run.progress_percent || 0)))}
                    color={isActive ? "cyan" : run.status === "succeeded" ? "teal" : run.status === "failed" ? "red" : "gray"}
                  />
                </Paper>
              );
            })}
          </Stack>

          {selectedQueueRun && (
            <Paper withBorder radius="md" p="xs" mt={8}>
              <Group justify="space-between" align="center" mb={6}>
                <Stack gap={2}>
                  <Text size="sm" fw={700}>
                    Selected run {selectedQueueRun.id.slice(0, 8)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    status {selectedQueueRun.status} • worker {selectedQueueRun.worker_id ?? "—"} • heartbeat {fmtDate(selectedQueueRun.heartbeat_at)}
                  </Text>
                </Stack>
                <Group gap={6}>
                  <Badge variant="light" color={operationResultColor(selectedQueueRun.status)}>
                    {selectedQueueRun.status}
                  </Badge>
                  <Button
                    size="xs"
                    variant="light"
                    onClick={() => void loadOperationRunDetail(selectedQueueRun.id)}
                    leftSection={<IconRefresh size={14} />}
                  >
                    Reload detail
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    onClick={() => void loadOperationRunEvents(selectedQueueRun.id, false)}
                    disabled={selectedQueueRunTerminal}
                  >
                    Pull new events
                  </Button>
                </Group>
              </Group>

              <Text size="xs" c="dimmed" mb={4}>
                token {selectedQueueRun.operation_token} • updated {fmtDate(selectedQueueRun.updated_at)}
              </Text>
              {!!selectedQueueRun.error_message && (
                <Text size="xs" c="red" mb={6}>
                  {selectedQueueRun.error_message}
                </Text>
              )}

              <Stack gap={4}>
                {operationEvents.length === 0 && (
                  <Text size="xs" c="dimmed">
                    No progress events yet.
                  </Text>
                )}
                {operationEvents.slice(-16).map((event) => (
                  <Paper key={`run-event-${event.id}`} withBorder radius="md" p="xs">
                    <Group justify="space-between" align="center">
                      <Stack gap={2}>
                        <Text size="xs" fw={700}>
                          {event.event_type} • {event.phase ?? "—"}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {event.message}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {fmtDate(event.created_at)}
                        </Text>
                      </Stack>
                      <Badge variant="light" color={operationResultColor(event.phase ?? event.event_type)}>
                        {event.progress_percent == null ? "—" : `${event.progress_percent.toFixed(1)}%`}
                      </Badge>
                    </Group>
                  </Paper>
                ))}
              </Stack>
            </Paper>
          )}
        </Paper>
      </Paper>

      <Paper withBorder radius="md" p="xs" mb="sm">
        <Group justify="space-between" align="center" mb={6}>
          <Stack gap={2}>
            <Text fw={700}>Schedule Observability</Text>
            <Text size="xs" c="dimmed">
              Per-schedule success trend, failure classes, and SLO-style health badges.
            </Text>
          </Stack>
          <Group gap={8}>
            <NumberInput
              label="Window (days)"
              min={1}
              max={365}
              value={observabilityDays}
              onChange={(value) => setObservabilityDays(Math.max(1, Math.min(365, asNumber(value, 30))))}
              styles={{ root: { width: 150 } }}
            />
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              loading={loadingObservability}
              onClick={() => void loadObservability()}
            >
              Refresh observability
            </Button>
          </Group>
        </Group>

        {observabilityRows.length === 0 && (
          <Text size="xs" c="dimmed">
            No observability data in the selected window yet.
          </Text>
        )}

        <Stack gap={6}>
          {observabilityRows.map((item) => (
            <Paper key={`observability-${item.schedule_id}`} withBorder radius="md" p="xs">
              <Group justify="space-between" align="center" mb={4}>
                <Stack gap={2}>
                  <Text size="sm" fw={700}>
                    {item.schedule_name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {item.preset} • last run {fmtDate(item.last_run_at)} • last status {item.last_status ?? "unknown"}
                  </Text>
                </Stack>
                <Group gap={6}>
                  <Badge variant="light" color={healthColor(item.slo.health)}>
                    {item.slo.health}
                  </Badge>
                  <Badge variant="light" color={item.enabled ? "teal" : "gray"}>
                    {item.enabled ? "enabled" : "disabled"}
                  </Badge>
                </Group>
              </Group>

              <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb={6}>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Success rate
                  </Text>
                  <Text size="sm" fw={700}>
                    {asPercent(item.slo.success_rate)}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Alert rate
                  </Text>
                  <Text size="sm" fw={700}>
                    {asPercent(item.slo.alert_rate)}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Failed runs
                  </Text>
                  <Text size="sm" fw={700}>
                    {item.window.failed}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Executed in window
                  </Text>
                  <Text size="sm" fw={700}>
                    {item.window.executed}
                  </Text>
                </Paper>
              </SimpleGrid>

              <Progress
                size="sm"
                radius="xl"
                sections={[
                  { value: Math.max(0, Math.min(100, item.slo.success_rate * 100)), color: "teal" },
                  { value: Math.max(0, Math.min(100, item.slo.alert_rate * 100)), color: "yellow" },
                  { value: Math.max(0, Math.min(100, item.slo.failure_rate * 100)), color: "red" },
                ]}
                mb={6}
              />

              <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed" fw={700}>
                    Top failure classes
                  </Text>
                  {item.top_failure_classes.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No failures in selected window.
                    </Text>
                  )}
                  <Group gap={6} mt={4}>
                    {item.top_failure_classes.map((failure) => (
                      <Badge key={`${item.schedule_id}-${failure.code}`} variant="light" color="red">
                        {failure.code} ({failure.count})
                      </Badge>
                    ))}
                  </Group>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed" fw={700}>
                    14-day trend
                  </Text>
                  <Stack gap={2} mt={4}>
                    {item.trend.slice(-6).map((day) => (
                      <Text key={`${item.schedule_id}-${day.day}`} size="xs" c="dimmed">
                        {day.day}: ok {day.ok}, alert {day.alert}, failed {day.failed}, skipped {day.skipped}
                      </Text>
                    ))}
                  </Stack>
                </Paper>
              </SimpleGrid>
            </Paper>
          ))}
        </Stack>
      </Paper>

      <Paper withBorder radius="md" p="xs" mb="sm">
        <Group justify="space-between" align="center" mb={6}>
          <Stack gap={2}>
            <Text fw={700}>Cross-Project Observability</Text>
            <Text size="xs" c="dimmed">
              Compare SLO health across projects and spot drift hotspots quickly.
            </Text>
          </Stack>
          <Group gap={8} align="end">
            <TextInput
              label="Projects (csv)"
              placeholder="omega_demo,project_b,project_c"
              value={compareProjectIds}
              onChange={(event) => setCompareProjectIds(event.currentTarget.value)}
            />
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              loading={loadingCompare}
              onClick={() => void Promise.all([loadObservabilityCompare(), refreshCompareDrilldown()])}
            >
              Refresh compare
            </Button>
          </Group>
        </Group>

        {compareRows.length === 0 && (
          <Text size="xs" c="dimmed">
            No projects found for compare window.
          </Text>
        )}

        <Stack gap={6}>
          {compareRows.map((item) => {
            const queueCommandCenterItem = queueCommandCenterByProjectId.get(item.project_id);
            const comparePreflightMode = normalizeIncidentPreflightEnforcementMode(
              queueCommandCenterItem?.control?.incident_preflight_enforcement_mode,
            );
            const comparePreflightPauseHours = Math.max(
              1,
              Math.min(168, Number(queueCommandCenterItem?.control?.incident_preflight_pause_hours || 4)),
            );
            const comparePreflightCriticalThreshold = Math.max(
              1,
              Math.min(100, Number(queueCommandCenterItem?.control?.incident_preflight_critical_fail_threshold || 1)),
            );
            return (
              <Paper
                key={`compare-${item.project_id}`}
                withBorder
                radius="md"
                p="xs"
                style={{
                  cursor: "pointer",
                  borderColor: selectedCompareProjectId === item.project_id ? "var(--mantine-color-blue-4)" : undefined,
                }}
                onClick={() => setSelectedCompareProjectId(item.project_id)}
              >
                <Group justify="space-between" align="center">
                  <Stack gap={2}>
                    <Text size="sm" fw={700}>
                      {item.project_id}
                    </Text>
                    <Text size="xs" c="dimmed">
                      schedules {item.enabled_schedules}/{item.schedules_total} enabled • last run {fmtDate(item.last_run_at)}
                    </Text>
                  </Stack>
                  <Group gap={6}>
                    <Badge variant="light" color={healthColor(item.slo.health)}>
                      {item.slo.health}
                    </Badge>
                    {queueCommandCenterItem && (
                      <Badge variant="light" color={incidentPreflightEnforcementColor(comparePreflightMode)}>
                        preflight {comparePreflightMode}
                      </Badge>
                    )}
                    <Badge variant="light" color="blue">
                      drift {item.slo.drift_index.toFixed(2)}
                    </Badge>
                    <Button
                      size="xs"
                      variant="subtle"
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedCompareProjectId(item.project_id);
                      }}
                    >
                      Open timelines
                    </Button>
                  </Group>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  success {asPercent(item.slo.success_rate)} • alert {asPercent(item.slo.alert_rate)} • failure{" "}
                  {asPercent(item.slo.failure_rate)}
                </Text>
                {queueCommandCenterItem && (
                  <Text size="xs" c="dimmed" mt={2}>
                    queue depth {queueCommandCenterItem.queue.depth_total} • preflight {comparePreflightMode} • critical &gt;={" "}
                    {comparePreflightCriticalThreshold} • pause {comparePreflightPauseHours}h
                  </Text>
                )}
              </Paper>
            );
          })}
        </Stack>

        {observabilityCompareDrilldown && (
          <Paper withBorder radius="md" p="xs" mt={8}>
            <Group justify="space-between" align="center" mb={6}>
              <Stack gap={2}>
                <Text fw={700}>Compare Drill-down</Text>
                <Text size="xs" c="dimmed">
                  {observabilityCompareDrilldown.project_id} • rank{" "}
                  {observabilityCompareDrilldown.rank_position ?? "—"} / {observabilityCompareDrilldown.total_projects}
                </Text>
              </Stack>
              <Button
                size="xs"
                variant="light"
                leftSection={<IconRefresh size={14} />}
                loading={loadingCompareDrilldown}
                onClick={() =>
                  void loadObservabilityCompareDrilldown(observabilityCompareDrilldown.project_id, false)
                }
              >
                Refresh drill-down
              </Button>
            </Group>

            <SimpleGrid cols={{ base: 1, xl: 3 }} spacing="sm" mb={6}>
              {(observabilityCompareDrilldown.neighbors ?? []).map((neighbor) => (
                <Paper
                  key={`neighbor-${neighbor.project_id}`}
                  withBorder
                  radius="md"
                  p="xs"
                  style={{
                    cursor: "pointer",
                    borderColor:
                      neighbor.project_id === observabilityCompareDrilldown.project_id
                        ? "var(--mantine-color-blue-4)"
                        : undefined,
                  }}
                  onClick={() => setSelectedCompareProjectId(neighbor.project_id)}
                >
                  <Group justify="space-between" align="center">
                    <Text size="xs" fw={700}>
                      {neighbor.project_id}
                    </Text>
                    <Badge variant="light" color={healthColor(neighbor.slo.health)}>
                      {neighbor.slo.health}
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed" mt={4}>
                    drift {neighbor.slo.drift_index.toFixed(2)} • success {asPercent(neighbor.slo.success_rate)}
                  </Text>
                </Paper>
              ))}
            </SimpleGrid>

            <Stack gap={6}>
              {(
                Array.isArray(observabilityCompareDrilldown.schedule_observability?.schedules)
                  ? observabilityCompareDrilldown.schedule_observability.schedules
                  : []
              ).map((item) => (
                <Paper key={`drilldown-schedule-${item.schedule_id}`} withBorder radius="md" p="xs">
                  <Group justify="space-between" align="center" mb={4}>
                    <Stack gap={2}>
                      <Text size="sm" fw={700}>
                        {item.schedule_name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {item.preset} • last run {fmtDate(item.last_run_at)} • status {item.last_status ?? "unknown"}
                      </Text>
                    </Stack>
                    <Badge variant="light" color={healthColor(item.slo.health)}>
                      {item.slo.health}
                    </Badge>
                  </Group>
                  <Progress
                    size="sm"
                    radius="xl"
                    sections={[
                      { value: Math.max(0, Math.min(100, item.slo.success_rate * 100)), color: "teal" },
                      { value: Math.max(0, Math.min(100, item.slo.alert_rate * 100)), color: "yellow" },
                      { value: Math.max(0, Math.min(100, item.slo.failure_rate * 100)), color: "red" },
                    ]}
                    mb={6}
                  />
                  <Text size="xs" c="dimmed">
                    success {asPercent(item.slo.success_rate)} • alert {asPercent(item.slo.alert_rate)} • failure{" "}
                    {asPercent(item.slo.failure_rate)} • executed {item.window.executed}
                  </Text>
                  <Stack gap={2} mt={4}>
                    {item.trend.slice(-4).map((day) => (
                      <Text key={`drilldown-trend-${item.schedule_id}-${day.day}`} size="xs" c="dimmed">
                        {day.day}: ok {day.ok}, alert {day.alert}, failed {day.failed}, skipped {day.skipped}
                      </Text>
                    ))}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          </Paper>
        )}
      </Paper>

      <SimpleGrid cols={{ base: 1, md: 3, xl: 6 }} spacing="sm" mb="sm">
        <TextInput
          label="Schedule name"
          placeholder="omega-nightly"
          value={form.name}
          onChange={(event) => setForm((prev) => ({ ...prev, name: event.currentTarget.value }))}
        />
        <Select
          label="Preset"
          data={[
            { value: "nightly", label: "Nightly" },
            { value: "weekly", label: "Weekly" },
          ]}
          value={form.preset}
          onChange={(value) => setForm((prev) => ({ ...prev, preset: value === "weekly" ? "weekly" : "nightly" }))}
        />
        <NumberInput
          label="Interval hours"
          description={`effective ${effectiveInterval}h`}
          placeholder={String(activePreset.interval_hours)}
          min={1}
          max={4320}
          value={form.interval_hours}
          onChange={(value) =>
            setForm((prev) => ({
              ...prev,
              interval_hours: value === "" || value == null ? null : Math.max(1, Math.min(4320, asNumber(value, 24))),
            }))
          }
        />
        <NumberInput
          label="Lookback days"
          min={1}
          max={365}
          value={form.lookback_days}
          onChange={(value) =>
            setForm((prev) => ({ ...prev, lookback_days: Math.max(1, Math.min(365, asNumber(value, 60))) }))
          }
        />
        <NumberInput
          label="Limit rows"
          min={100}
          max={200000}
          step={500}
          value={form.limit_rows}
          onChange={(value) =>
            setForm((prev) => ({ ...prev, limit_rows: Math.max(100, Math.min(200000, asNumber(value, 20000))) }))
          }
        />
        <NumberInput
          label="Holdout ratio"
          min={0.01}
          max={0.99}
          step={0.01}
          decimalScale={2}
          value={form.holdout_ratio}
          onChange={(value) =>
            setForm((prev) => ({
              ...prev,
              holdout_ratio: Math.max(0.01, Math.min(0.99, Number(asNumber(value, 0.3).toFixed(2)))),
            }))
          }
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="sm">
        <TextInput
          label="Split seed"
          value={form.split_seed}
          onChange={(event) => setForm((prev) => ({ ...prev, split_seed: event.currentTarget.value }))}
        />
        <NumberInput
          label="Top K"
          min={1}
          max={20}
          value={form.top_k}
          onChange={(value) => setForm((prev) => ({ ...prev, top_k: Math.max(1, Math.min(20, asNumber(value, 5))) }))}
        />
        <TextInput
          label="Weights grid"
          description="comma-separated, ascending [0..1]"
          value={form.weights}
          onChange={(event) => setForm((prev) => ({ ...prev, weights: event.currentTarget.value }))}
        />
        <TextInput
          label="Confidences grid"
          description="comma-separated, ascending [0..1]"
          value={form.confidences}
          onChange={(event) => setForm((prev) => ({ ...prev, confidences: event.currentTarget.value }))}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }} spacing="sm" mb="sm">
        <TextInput
          label="Score thresholds"
          description="comma-separated, ascending [0..1]"
          value={form.score_thresholds}
          onChange={(event) => setForm((prev) => ({ ...prev, score_thresholds: event.currentTarget.value }))}
        />
        <Textarea
          label="Snapshot note"
          minRows={1}
          maxRows={3}
          autosize
          value={form.snapshot_note}
          onChange={(event) => setForm((prev) => ({ ...prev, snapshot_note: event.currentTarget.value }))}
        />
        <Stack gap={6}>
          <Switch
            label="Schedule enabled"
            checked={form.enabled}
            onChange={(event) => setForm((prev) => ({ ...prev, enabled: event.currentTarget.checked }))}
          />
          <Switch
            label="Allow guardrail fail"
            checked={form.allow_guardrail_fail}
            onChange={(event) => setForm((prev) => ({ ...prev, allow_guardrail_fail: event.currentTarget.checked }))}
          />
        </Stack>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mb="sm">
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed" fw={700}>
            Preset profile
          </Text>
          <Text size="sm" fw={600}>
            {activePreset.label}
          </Text>
          <Text size="xs" c="dimmed">
            {activePreset.description}
          </Text>
          <Text size="xs" c="dimmed">
            interval {activePreset.interval_hours}h • lookback {activePreset.lookback_days}d • limit {activePreset.limit_rows}
          </Text>
          <Button size="xs" variant="subtle" onClick={() => applyPresetDefaults(form.preset)} mt={6}>
            Apply preset defaults
          </Button>
        </Paper>
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed" fw={700}>
            Validation hints
          </Text>
          {validationErrors.length === 0 ? (
            <Text size="sm" c="teal">
              Ready to save.
            </Text>
          ) : (
            <Stack gap={2}>
              {validationErrors.slice(0, 4).map((item, index) => (
                <Text key={`validation-${index}`} size="xs" c="red">
                  {item}
                </Text>
              ))}
              {validationErrors.length > 4 && (
                <Text size="xs" c="dimmed">
                  +{validationErrors.length - 4} more
                </Text>
              )}
            </Stack>
          )}
        </Paper>
      </SimpleGrid>

      <Group gap={8} mb="sm">
        <Button
          size="xs"
          color="teal"
          leftSection={<IconDeviceFloppy size={14} />}
          loading={savingSchedule}
          onClick={() => void saveSchedule()}
          disabled={!projectId.trim()}
        >
          {editingScheduleId ? "Update schedule" : "Create schedule"}
        </Button>
        {editingScheduleId && (
          <Button size="xs" variant="light" onClick={resetForm}>
            Cancel edit
          </Button>
        )}
      </Group>

      <Stack gap={6}>
        {schedules.length === 0 && (
          <Text size="sm" c="dimmed">
            No schedules configured for this project.
          </Text>
        )}
        {schedules.map((schedule) => (
          <Paper key={`schedule-${schedule.id}`} withBorder radius="md" p="xs" data-testid={`calibration-schedule-row-${schedule.id}`}>
            <Group justify="space-between" align="center" mb={4}>
              <Stack gap={2}>
                <Text size="sm" fw={700}>
                  {schedule.name}
                </Text>
                <Text size="xs" c="dimmed">
                  {schedule.preset} • interval {schedule.interval_hours ?? PRESET_CONFIGS[schedule.preset === "weekly" ? "weekly" : "nightly"].interval_hours}h • lookback {schedule.lookback_days}d
                </Text>
              </Stack>
              <Group gap={6}>
                <Badge variant="light" color={schedule.enabled ? "teal" : "gray"}>
                  {schedule.enabled ? "enabled" : "disabled"}
                </Badge>
                <Badge variant="light" color={runStatusColor(schedule.last_status)}>
                  {schedule.last_status || "no runs"}
                </Badge>
                <Button size="xs" variant="subtle" onClick={() => startEdit(schedule)}>
                  Edit
                </Button>
                <Button
                  size="xs"
                  color="red"
                  variant="subtle"
                  leftSection={<IconTrash size={12} />}
                  loading={deletingScheduleId === schedule.id}
                  onClick={() => void deleteSchedule(schedule)}
                >
                  Delete
                </Button>
              </Group>
            </Group>
            <Text size="xs" c="dimmed">
              Last run: {fmtDate(schedule.last_run_at)} • updated by {schedule.updated_by ?? "unknown"} at {fmtDate(schedule.updated_at)}
            </Text>
          </Paper>
        ))}
      </Stack>
    </Paper>
  );
}
