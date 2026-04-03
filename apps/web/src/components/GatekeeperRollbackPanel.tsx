import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  Progress,
  ScrollArea,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconRefresh, IconX } from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useState } from "react";

type GatekeeperConfigSnapshot = {
  id: string;
  source: "calibration_cycle" | "manual" | "rollback";
  approved_by: string;
  note: string | null;
  config: Record<string, unknown>;
  guardrails_met: boolean | null;
  created_at: string;
};

type RollbackApprovalEvent = {
  actor: string;
  action: string;
  note: string | null;
  created_at: string | null;
};

type GatekeeperRollbackPreview = {
  project_id: string;
  snapshot_id: string;
  lookback_days: number;
  limit: number;
  config_diff: Record<
    string,
    {
      current: unknown;
      target: unknown;
    }
  >;
  impact: {
    decisions_scanned: number;
    changed_total: number;
    changed_ratio: number;
    changed_from_golden: number;
    changed_to_golden: number;
    risk_level: "low" | "medium" | "high" | string;
    tier_counts_current: Record<string, number>;
    tier_counts_target_estimated: Record<string, number>;
    transitions: Record<string, number>;
  };
  changed_samples: Array<{
    claim_id: string;
    from_tier: string;
    to_tier: string;
    score_current: number;
    score_estimated: number;
    updated_at: string;
    reason: string | null;
  }>;
  generated_at: string;
};

type GatekeeperRollbackRequest = {
  id: string;
  project_id: string;
  snapshot_id: string;
  status: "pending_approval" | "applied" | "rejected" | "failed" | string;
  requested_by: string;
  required_approvals: number;
  approvals: RollbackApprovalEvent[];
  preview: GatekeeperRollbackPreview | Record<string, unknown>;
  note: string | null;
  rejection_reason: string | null;
  applied_by: string | null;
  applied_snapshot_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

type RollbackRankedItem = {
  count: number;
  share: number;
};

type GatekeeperRollbackMetrics = {
  project_id: string;
  days: number;
  sla_hours: number;
  limit: number;
  sampled_requests: number;
  since: string;
  summary: {
    total_requests: number;
    pending_approval: number;
    applied: number;
    rejected: number;
    failed: number;
    other: number;
    resolved_total: number;
    approval_rate: number;
    rejection_rate: number;
    failure_rate: number;
    resolution_rate: number;
    pending_sla_breaches: number;
    max_pending_age_hours: number | null;
  };
  lead_time_hours: {
    first_approval: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
    resolution: {
      count: number;
      avg: number | null;
      p50: number | null;
      p90: number | null;
    };
  };
  rejection_causes: Array<RollbackRankedItem & { reason: string }>;
  risk_levels: Array<RollbackRankedItem & { risk_level: string }>;
  top_risk_drivers: Array<RollbackRankedItem & { driver: string }>;
  transition_drivers: Array<RollbackRankedItem & { transition: string }>;
  pending_sla_breaches: Array<{
    request_id: string;
    age_hours: number;
    risk_level: string;
    created_at: string;
  }>;
  generated_at: string;
};

type GatekeeperRollbackAttribution = {
  project_id: string;
  days: number;
  group_by: "cohort" | "actor" | string;
  sampled_requests: number;
  since: string;
  cohorts: Array<{
    cohort: string;
    approvals: number;
    requests_involved: number;
    applied_involved: number;
    rejected_involved: number;
    failed_involved: number;
    applied_rate: number;
    avg_first_approval_lead_hours: number | null;
    p50_first_approval_lead_hours: number | null;
    latest_approval_at: string | null;
  }>;
  timeline: Array<{
    day: string;
    applied: number;
    rejected: number;
    failed: number;
    resolved_total: number;
  }>;
  summary: {
    cohorts_total: number;
    resolved_total: number;
    applied_total: number;
    applied_rate: number;
  };
  generated_at: string;
};

type GatekeeperRollbackAttributionDrilldown = {
  project_id: string;
  cohort: string;
  group_by: "cohort" | "actor" | string;
  days: number;
  since: string;
  sample_limit: number;
  request_limit: number;
  sampled_requests: number;
  summary: {
    approvals: number;
    requests_involved: number;
    pending_approval: number;
    applied: number;
    rejected: number;
    failed: number;
    other: number;
    resolved_total: number;
    applied_rate: number;
    resolution_rate: number;
    avg_first_approval_lead_hours: number | null;
    p50_first_approval_lead_hours: number | null;
    p90_first_approval_lead_hours: number | null;
    avg_resolution_lead_hours: number | null;
    p50_resolution_lead_hours: number | null;
    p90_resolution_lead_hours: number | null;
    latest_approval_at: string | null;
  };
  timeline: Array<{
    day: string;
    applied: number;
    rejected: number;
    failed: number;
    resolved_total: number;
  }>;
  requests: Array<{
    request_id: string;
    snapshot_id: string;
    status: string;
    requested_by: string;
    required_approvals: number;
    approval_count: number;
    matched_approvals: number;
    matched_actors: string[];
    approvers: string[];
    cohorts: string[];
    created_at: string;
    resolved_at: string | null;
    first_approval_at: string | null;
    first_approval_lead_hours: number | null;
    resolution_lead_hours: number | null;
    risk_level: string;
    changed_ratio: number;
    changed_total: number;
    decisions_scanned: number;
    config_diff_keys: string[];
    top_transitions: Array<{ transition: string; count: number }>;
    note: string | null;
    rejection_reason: string | null;
    error_message: string | null;
    causal_trace: Array<{
      event_type: string;
      actor: string | null;
      created_at: string | null;
      note: string | null;
      matched: boolean;
    }>;
  }>;
  generated_at: string;
};

type GatekeeperRollbackPanelProps = {
  apiUrl: string;
  projectId: string;
  reviewer: string;
  snapshots: GatekeeperConfigSnapshot[];
  onRefresh?: () => Promise<void> | void;
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

function rollbackStatusColor(status: string): string {
  if (status === "pending_approval") return "yellow";
  if (status === "applied") return "teal";
  if (status === "rejected") return "orange";
  if (status === "failed") return "red";
  return "gray";
}

function rollbackRiskColor(risk: string): string {
  if (risk === "low") return "teal";
  if (risk === "medium") return "yellow";
  if (risk === "high") return "red";
  return "gray";
}

function asNumber(value: number | string, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function asPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function asHours(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }
  return `${value.toFixed(2)}h`;
}

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  if (text.includes(",") || text.includes("\"") || text.includes("\n")) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }
  return text;
}

function normalizeApprovalEvents(raw: unknown): RollbackApprovalEvent[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const event = item as Record<string, unknown>;
      return {
        actor: String(event.actor ?? "unknown"),
        action: String(event.action ?? "unknown"),
        note: event.note == null ? null : String(event.note),
        created_at: event.created_at == null ? null : String(event.created_at),
      };
    })
    .filter((item): item is RollbackApprovalEvent => item !== null);
}

function previewFromUnknown(raw: unknown): GatekeeperRollbackPreview | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const value = raw as Record<string, unknown>;
  if (!value.impact || typeof value.impact !== "object") {
    return null;
  }
  return value as GatekeeperRollbackPreview;
}

function approvedCount(events: RollbackApprovalEvent[]): number {
  return events.filter((item) => item.action === "approved").length;
}

function actorAlreadyRecorded(events: RollbackApprovalEvent[], actor: string): boolean {
  const normalized = actor.trim();
  if (!normalized) {
    return false;
  }
  return events.some((item) => item.actor.trim() === normalized);
}

async function apiFetch<T>(
  apiUrl: string,
  path: string,
  options?: {
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
  },
): Promise<T> {
  const root = apiUrl.replace(/\/+$/, "");
  let sessionHeader: Record<string, string> = {};
  try {
    const raw = window.localStorage.getItem("synapse_web_console_v4");
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
  const response = await fetch(`${root}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...sessionHeader,
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

export default function GatekeeperRollbackPanel({
  apiUrl,
  projectId,
  reviewer,
  snapshots,
  onRefresh,
}: GatekeeperRollbackPanelProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "pending_approval" | "applied" | "rejected" | "failed">("all");
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [requests, setRequests] = useState<GatekeeperRollbackRequest[]>([]);
  const [preview, setPreview] = useState<GatekeeperRollbackPreview | null>(null);
  const [previewSnapshotId, setPreviewSnapshotId] = useState<string | null>(null);
  const [previewingSnapshotId, setPreviewingSnapshotId] = useState<string | null>(null);
  const [creatingSnapshotId, setCreatingSnapshotId] = useState<string | null>(null);
  const [actingRequestId, setActingRequestId] = useState<string | null>(null);
  const [requiredApprovals, setRequiredApprovals] = useState(2);
  const [lookbackDays, setLookbackDays] = useState(30);
  const [sampleSize, setSampleSize] = useState(25);
  const [metricsPreset, setMetricsPreset] = useState<"7" | "30" | "90" | "custom">("30");
  const [metricsDays, setMetricsDays] = useState(30);
  const [slaHours, setSlaHours] = useState(24);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [metrics, setMetrics] = useState<GatekeeperRollbackMetrics | null>(null);
  const [attributionGroupBy, setAttributionGroupBy] = useState<"cohort" | "actor">("cohort");
  const [loadingAttribution, setLoadingAttribution] = useState(false);
  const [attribution, setAttribution] = useState<GatekeeperRollbackAttribution | null>(null);
  const [selectedAttributionCohort, setSelectedAttributionCohort] = useState<string | null>(null);
  const [loadingAttributionDrilldown, setLoadingAttributionDrilldown] = useState(false);
  const [attributionDrilldown, setAttributionDrilldown] = useState<GatekeeperRollbackAttributionDrilldown | null>(null);
  const [requestNote, setRequestNote] = useState("");
  const [approveNotes, setApproveNotes] = useState<Record<string, string>>({});
  const [rejectReasons, setRejectReasons] = useState<Record<string, string>>({});

  const actor = reviewer.trim() || "web_ui";

  const loadRequests = useCallback(async () => {
    if (!projectId.trim()) {
      setRequests([]);
      setPreview(null);
      setPreviewSnapshotId(null);
      return;
    }
    setLoadingRequests(true);
    try {
      const query =
        statusFilter === "all"
          ? `/v1/gatekeeper/config/rollback/requests?project_id=${encodeURIComponent(projectId)}&limit=80`
          : `/v1/gatekeeper/config/rollback/requests?project_id=${encodeURIComponent(projectId)}&status=${encodeURIComponent(statusFilter)}&limit=80`;
      const payload = await apiFetch<{ requests: Array<Record<string, unknown>> }>(apiUrl, query);
      const normalized = (payload.requests ?? []).map((item) => ({
        id: String(item.id ?? ""),
        project_id: String(item.project_id ?? projectId),
        snapshot_id: String(item.snapshot_id ?? ""),
        status: String(item.status ?? "pending_approval"),
        requested_by: String(item.requested_by ?? "unknown"),
        required_approvals: Number(item.required_approvals ?? 2),
        approvals: normalizeApprovalEvents(item.approvals),
        preview:
          item.preview && typeof item.preview === "object"
            ? (item.preview as GatekeeperRollbackPreview | Record<string, unknown>)
            : {},
        note: item.note == null ? null : String(item.note),
        rejection_reason: item.rejection_reason == null ? null : String(item.rejection_reason),
        applied_by: item.applied_by == null ? null : String(item.applied_by),
        applied_snapshot_id: item.applied_snapshot_id == null ? null : String(item.applied_snapshot_id),
        error_message: item.error_message == null ? null : String(item.error_message),
        created_at: String(item.created_at ?? ""),
        updated_at: String(item.updated_at ?? ""),
        resolved_at: item.resolved_at == null ? null : String(item.resolved_at),
      }));
      setRequests(normalized);
    } catch (error) {
      setRequests([]);
      notifications.show({
        color: "orange",
        title: "Rollback queue unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setLoadingRequests(false);
    }
  }, [apiUrl, projectId, statusFilter]);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  const loadMetrics = useCallback(async () => {
    if (!projectId.trim()) {
      setMetrics(null);
      return;
    }
    setLoadingMetrics(true);
    try {
      const query = `/v1/gatekeeper/config/rollback/metrics?project_id=${encodeURIComponent(projectId)}&days=${encodeURIComponent(String(metricsDays))}&sla_hours=${encodeURIComponent(String(slaHours))}`;
      const payload = await apiFetch<GatekeeperRollbackMetrics>(apiUrl, query);
      setMetrics(payload);
    } catch (error) {
      setMetrics(null);
      notifications.show({
        color: "orange",
        title: "Rollback metrics unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setLoadingMetrics(false);
    }
  }, [apiUrl, metricsDays, projectId, slaHours]);

  useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  const loadAttribution = useCallback(async () => {
    if (!projectId.trim()) {
      setAttribution(null);
      setSelectedAttributionCohort(null);
      setAttributionDrilldown(null);
      return;
    }
    setLoadingAttribution(true);
    try {
      const query = `/v1/gatekeeper/config/rollback/attribution?project_id=${encodeURIComponent(projectId)}&days=${encodeURIComponent(String(metricsDays))}&group_by=${encodeURIComponent(attributionGroupBy)}`;
      const payload = await apiFetch<GatekeeperRollbackAttribution>(apiUrl, query);
      setAttribution(payload);
      const cohorts = Array.isArray(payload.cohorts) ? payload.cohorts : [];
      setSelectedAttributionCohort((current) => {
        if (current && cohorts.some((item) => item.cohort === current)) {
          return current;
        }
        return cohorts.length > 0 ? cohorts[0].cohort : null;
      });
    } catch (error) {
      setAttribution(null);
      setSelectedAttributionCohort(null);
      setAttributionDrilldown(null);
      notifications.show({
        color: "orange",
        title: "Rollback attribution unavailable",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setLoadingAttribution(false);
    }
  }, [apiUrl, attributionGroupBy, metricsDays, projectId]);

  useEffect(() => {
    void loadAttribution();
  }, [loadAttribution]);

  const loadAttributionDrilldown = useCallback(
    async (cohort: string, silent = false) => {
      if (!projectId.trim() || !cohort.trim()) {
        setAttributionDrilldown(null);
        return;
      }
      if (!silent) {
        setLoadingAttributionDrilldown(true);
      }
      try {
        const query = `/v1/gatekeeper/config/rollback/attribution/drilldown?project_id=${encodeURIComponent(projectId)}&days=${encodeURIComponent(String(metricsDays))}&group_by=${encodeURIComponent(attributionGroupBy)}&cohort=${encodeURIComponent(cohort)}&limit=120`;
        const payload = await apiFetch<GatekeeperRollbackAttributionDrilldown>(apiUrl, query);
        setAttributionDrilldown(payload);
      } catch (error) {
        if (!silent) {
          notifications.show({
            color: "orange",
            title: "Rollback drill-down unavailable",
            message: error instanceof Error ? error.message : String(error),
          });
        }
        setAttributionDrilldown(null);
      } finally {
        if (!silent) {
          setLoadingAttributionDrilldown(false);
        }
      }
    },
    [apiUrl, attributionGroupBy, metricsDays, projectId],
  );

  useEffect(() => {
    if (!selectedAttributionCohort) {
      setAttributionDrilldown(null);
      return;
    }
    void loadAttributionDrilldown(selectedAttributionCohort, true);
  }, [loadAttributionDrilldown, selectedAttributionCohort]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadRequests(), loadMetrics(), loadAttribution(), Promise.resolve(onRefresh?.())]);
  }, [loadAttribution, loadMetrics, loadRequests, onRefresh]);

  const exportMetricsCsv = useCallback(() => {
    if (!metrics) {
      notifications.show({
        color: "orange",
        title: "No metrics to export",
        message: "Load rollback governance metrics first.",
      });
      return;
    }
    const lines: string[] = [];
    lines.push("section,key,value,count,share");
    lines.push(`summary,total_requests,${csvEscape(metrics.summary.total_requests)},,`);
    lines.push(`summary,approval_rate,${csvEscape(metrics.summary.approval_rate)},,`);
    lines.push(`summary,rejection_rate,${csvEscape(metrics.summary.rejection_rate)},,`);
    lines.push(`summary,failure_rate,${csvEscape(metrics.summary.failure_rate)},,`);
    lines.push(`summary,pending_sla_breaches,${csvEscape(metrics.summary.pending_sla_breaches)},,`);
    lines.push(`summary,max_pending_age_hours,${csvEscape(metrics.summary.max_pending_age_hours ?? "")},,`);
    for (const item of metrics.rejection_causes) {
      lines.push(`rejection_cause,${csvEscape(item.reason)},,${csvEscape(item.count)},${csvEscape(item.share)}`);
    }
    for (const item of metrics.risk_levels) {
      lines.push(`risk_level,${csvEscape(item.risk_level)},,${csvEscape(item.count)},${csvEscape(item.share)}`);
    }
    for (const item of metrics.top_risk_drivers) {
      lines.push(`risk_driver,${csvEscape(item.driver)},,${csvEscape(item.count)},${csvEscape(item.share)}`);
    }
    for (const item of metrics.transition_drivers) {
      lines.push(`transition_driver,${csvEscape(item.transition)},,${csvEscape(item.count)},${csvEscape(item.share)}`);
    }
    for (const item of metrics.pending_sla_breaches) {
      lines.push(
        `pending_sla_breach,${csvEscape(item.request_id)},${csvEscape(item.age_hours)},,${csvEscape(item.risk_level)}`,
      );
    }
    const content = `${lines.join("\n")}\n`;
    const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `rollback-governance-${projectId || "project"}-${metrics.days}d.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    notifications.show({
      color: "teal",
      title: "CSV exported",
      message: "Rollback governance metrics exported.",
    });
  }, [metrics, projectId]);

  const previewSnapshot = useCallback(
    async (snapshotId: string) => {
      if (!projectId.trim()) {
        return;
      }
      setPreviewingSnapshotId(snapshotId);
      try {
        const payload = await apiFetch<{ preview: GatekeeperRollbackPreview }>(apiUrl, "/v1/gatekeeper/config/rollback/preview", {
          method: "POST",
          body: {
            project_id: projectId,
            snapshot_id: snapshotId,
            lookback_days: lookbackDays,
            limit: 5000,
            sample_size: sampleSize,
          },
        });
        setPreview(payload.preview);
        setPreviewSnapshotId(snapshotId);
        notifications.show({
          color: rollbackRiskColor(String(payload.preview.impact.risk_level)),
          title: "Rollback preview generated",
          message: `Risk: ${payload.preview.impact.risk_level}, changed decisions: ${payload.preview.impact.changed_total}`,
        });
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Preview failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setPreviewingSnapshotId(null);
      }
    },
    [apiUrl, lookbackDays, projectId, sampleSize],
  );

  const createRollbackRequest = useCallback(
    async (snapshotId: string) => {
      if (!projectId.trim()) {
        return;
      }
      setCreatingSnapshotId(snapshotId);
      try {
        const payload = await apiFetch<{ request: { preview?: GatekeeperRollbackPreview } }>(
          apiUrl,
          "/v1/gatekeeper/config/rollback/requests",
          {
            method: "POST",
            body: {
              project_id: projectId,
              snapshot_id: snapshotId,
              requested_by: actor,
              note: requestNote.trim() || null,
              required_approvals: requiredApprovals,
              lookback_days: lookbackDays,
              limit: 5000,
              sample_size: sampleSize,
            },
          },
        );
        const maybePreview = previewFromUnknown(payload.request?.preview);
        if (maybePreview) {
          setPreview(maybePreview);
          setPreviewSnapshotId(snapshotId);
        }
        setRequestNote("");
        await refreshAll();
        notifications.show({
          color: "teal",
          title: "Rollback request created",
          message: `Snapshot ${snapshotId} is now waiting for approval.`,
        });
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Could not create request",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setCreatingSnapshotId(null);
      }
    },
    [actor, apiUrl, lookbackDays, projectId, refreshAll, requestNote, requiredApprovals, sampleSize],
  );

  const approveRequest = useCallback(
    async (requestId: string) => {
      if (!projectId.trim()) {
        return;
      }
      setActingRequestId(`${requestId}:approve`);
      try {
        await apiFetch<{ status: string }>(apiUrl, `/v1/gatekeeper/config/rollback/requests/${requestId}/approve`, {
          method: "POST",
          body: {
            project_id: projectId,
            approved_by: actor,
            note: (approveNotes[requestId] ?? "").trim() || null,
          },
        });
        setApproveNotes((prev) => {
          const next = { ...prev };
          delete next[requestId];
          return next;
        });
        await refreshAll();
        notifications.show({
          color: "teal",
          title: "Approval recorded",
          message: "Rollback request updated.",
        });
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Approval failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setActingRequestId(null);
      }
    },
    [actor, apiUrl, approveNotes, projectId, refreshAll],
  );

  const rejectRequest = useCallback(
    async (requestId: string) => {
      if (!projectId.trim()) {
        return;
      }
      const reason = (rejectReasons[requestId] ?? "").trim();
      if (!reason) {
        notifications.show({
          color: "orange",
          title: "Reject reason required",
          message: "Add a short reason before rejecting rollback request.",
        });
        return;
      }
      setActingRequestId(`${requestId}:reject`);
      try {
        await apiFetch<{ status: string }>(apiUrl, `/v1/gatekeeper/config/rollback/requests/${requestId}/reject`, {
          method: "POST",
          body: {
            project_id: projectId,
            rejected_by: actor,
            reason,
          },
        });
        setRejectReasons((prev) => {
          const next = { ...prev };
          delete next[requestId];
          return next;
        });
        await refreshAll();
        notifications.show({
          color: "orange",
          title: "Request rejected",
          message: "Rollback request was rejected with audit reason.",
        });
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Reject failed",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setActingRequestId(null);
      }
    },
    [actor, apiUrl, projectId, refreshAll, rejectReasons],
  );

  const pendingRequests = requests.filter((item) => item.status === "pending_approval");
  const appliedRequests = requests.filter((item) => item.status === "applied");
  const failedRequests = requests.filter((item) => item.status === "failed");
  const highRiskPending = pendingRequests.filter((item) => previewFromUnknown(item.preview)?.impact.risk_level === "high").length;
  const selectedSnapshot = useMemo(
    () => snapshots.find((item) => item.id === previewSnapshotId) ?? null,
    [previewSnapshotId, snapshots],
  );

  return (
    <Paper withBorder radius="md" p="sm" mb="md">
      <Group justify="space-between" align="center" mb={8}>
        <Stack gap={2}>
          <Text fw={700}>Rollback Approval Workflow</Text>
          <Text size="xs" c="dimmed">
            Safe rollback flow: preview impact, create request, collect approvals, apply with audit trail.
          </Text>
        </Stack>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconRefresh size={14} />}
          loading={loadingRequests}
          onClick={() => void refreshAll()}
          disabled={!projectId.trim()}
        >
          Refresh Queue
        </Button>
      </Group>

      <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb="sm">
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed">
            Pending approvals
          </Text>
          <Title order={4}>{pendingRequests.length}</Title>
        </Paper>
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed">
            Applied rollbacks
          </Text>
          <Title order={4}>{appliedRequests.length}</Title>
        </Paper>
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed">
            High-risk pending
          </Text>
          <Title order={4}>{highRiskPending}</Title>
        </Paper>
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed">
            Failed requests
          </Text>
          <Title order={4}>{failedRequests.length}</Title>
        </Paper>
      </SimpleGrid>

      <Paper withBorder radius="md" p="xs" mb="sm">
        <Group justify="space-between" align="end" mb={8}>
          <Stack gap={2}>
            <Text fw={700}>Rollback Governance Metrics</Text>
            <Text size="xs" c="dimmed">
              Approval lead-time, rejection causes, and risk drivers across recent rollback requests.
            </Text>
          </Stack>
          <Group gap={8} align="end">
            <SegmentedControl
              size="xs"
              value={metricsPreset}
              onChange={(value) => {
                const preset = value as typeof metricsPreset;
                setMetricsPreset(preset);
                if (preset === "7") setMetricsDays(7);
                if (preset === "30") setMetricsDays(30);
                if (preset === "90") setMetricsDays(90);
              }}
              data={[
                { label: "7d", value: "7" },
                { label: "30d", value: "30" },
                { label: "90d", value: "90" },
                { label: "Custom", value: "custom" },
              ]}
            />
            <NumberInput
              label="Window (days)"
              min={1}
              max={365}
              value={metricsDays}
              onChange={(value) => {
                setMetricsPreset("custom");
                setMetricsDays(Math.max(1, Math.min(365, asNumber(value, 30))));
              }}
              styles={{ root: { width: 140 } }}
            />
            <NumberInput
              label="SLA (hours)"
              min={1}
              max={720}
              value={slaHours}
              onChange={(value) => setSlaHours(Math.max(1, Math.min(720, asNumber(value, 24))))}
              styles={{ root: { width: 140 } }}
            />
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              loading={loadingMetrics}
              onClick={() => void loadMetrics()}
            >
              Refresh Metrics
            </Button>
            <Button size="xs" variant="light" onClick={exportMetricsCsv} disabled={!metrics}>
              Export CSV
            </Button>
          </Group>
        </Group>

        {!metrics && (
          <Text size="sm" c="dimmed">
            Metrics will appear after rollback requests are captured.
          </Text>
        )}

        {metrics && (
          <Stack gap={8}>
            <SimpleGrid cols={{ base: 1, md: 6 }} spacing="sm">
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Approval rate
                </Text>
                <Text size="sm" fw={700}>
                  {asPercent(metrics.summary.approval_rate)}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Rejection rate
                </Text>
                <Text size="sm" fw={700}>
                  {asPercent(metrics.summary.rejection_rate)}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  First approval P50/P90
                </Text>
                <Text size="sm" fw={700}>
                  {asHours(metrics.lead_time_hours.first_approval.p50)} / {asHours(metrics.lead_time_hours.first_approval.p90)}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Resolution P50/P90
                </Text>
                <Text size="sm" fw={700}>
                  {asHours(metrics.lead_time_hours.resolution.p50)} / {asHours(metrics.lead_time_hours.resolution.p90)}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  SLA breaches
                </Text>
                <Text size="sm" fw={700}>
                  {metrics.summary.pending_sla_breaches}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  Max pending age
                </Text>
                <Text size="sm" fw={700}>
                  {asHours(metrics.summary.max_pending_age_hours)}
                </Text>
              </Paper>
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, xl: 5 }} spacing="sm">
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed" fw={700} mb={4}>
                  Rejection causes
                </Text>
                <Stack gap={4}>
                  {metrics.rejection_causes.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No rejected requests in current window.
                    </Text>
                  )}
                  {metrics.rejection_causes.map((item) => (
                    <Group key={`reject-cause-${item.reason}`} justify="space-between" align="start">
                      <Text size="xs" style={{ flex: 1 }}>
                        {item.reason}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {item.count} • {asPercent(item.share)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>

              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed" fw={700} mb={4}>
                  Risk levels
                </Text>
                <Stack gap={4}>
                  {metrics.risk_levels.map((item) => (
                    <Group key={`risk-level-${item.risk_level}`} justify="space-between" align="center">
                      <Badge variant="light" color={rollbackRiskColor(item.risk_level)}>
                        {item.risk_level}
                      </Badge>
                      <Text size="xs" c="dimmed">
                        {item.count} • {asPercent(item.share)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>

              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed" fw={700} mb={4}>
                  Top risk drivers
                </Text>
                <Stack gap={4}>
                  {metrics.top_risk_drivers.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No config deltas captured yet.
                    </Text>
                  )}
                  {metrics.top_risk_drivers.map((item) => (
                    <Group key={`risk-driver-${item.driver}`} justify="space-between" align="start">
                      <Text size="xs" ff="monospace">
                        {item.driver}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {item.count} • {asPercent(item.share)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>

              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed" fw={700} mb={4}>
                  Transition drivers
                </Text>
                <Stack gap={4}>
                  {metrics.transition_drivers.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No transition impact samples yet.
                    </Text>
                  )}
                  {metrics.transition_drivers.slice(0, 6).map((item) => (
                    <Group key={`transition-driver-${item.transition}`} justify="space-between" align="start">
                      <Text size="xs" ff="monospace">
                        {item.transition}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {item.count} • {asPercent(item.share)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>

              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed" fw={700} mb={4}>
                  Pending SLA breaches
                </Text>
                <Stack gap={4}>
                  {metrics.pending_sla_breaches.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No pending requests above SLA.
                    </Text>
                  )}
                  {metrics.pending_sla_breaches.map((item) => (
                    <Group key={`sla-breach-${item.request_id}`} justify="space-between" align="start">
                      <Text size="xs" ff="monospace">
                        {item.request_id.slice(0, 8)}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {asHours(item.age_hours)} • {item.risk_level}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>
            </SimpleGrid>

            <Paper withBorder radius="md" p="xs">
              <Group justify="space-between" align="end" mb={6}>
                <Stack gap={2}>
                  <Text size="xs" c="dimmed" fw={700}>
                    Rollback Attribution
                  </Text>
                  <Text size="xs" c="dimmed">
                    Approval cohorts, lead times, and decision outcomes.
                  </Text>
                </Stack>
                <Group gap={8} align="end">
                  <SegmentedControl
                    size="xs"
                    value={attributionGroupBy}
                    onChange={(value) => setAttributionGroupBy(value as "cohort" | "actor")}
                    data={[
                      { label: "Cohort", value: "cohort" },
                      { label: "Actor", value: "actor" },
                    ]}
                  />
                  <Button
                    size="xs"
                    variant="light"
                    loading={loadingAttribution}
                    onClick={() =>
                      void Promise.all([
                        loadAttribution(),
                        selectedAttributionCohort
                          ? loadAttributionDrilldown(selectedAttributionCohort, true)
                          : Promise.resolve(),
                      ])
                    }
                  >
                    Refresh Attribution
                  </Button>
                </Group>
              </Group>

              {!attribution && (
                <Text size="xs" c="dimmed">
                  Attribution data will appear after approval actions are recorded.
                </Text>
              )}

              {attribution && (
                <Stack gap={4}>
                  <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm">
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed">
                        Cohorts
                      </Text>
                      <Text size="sm" fw={700}>
                        {attribution.summary.cohorts_total}
                      </Text>
                    </Paper>
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed">
                        Resolved
                      </Text>
                      <Text size="sm" fw={700}>
                        {attribution.summary.resolved_total}
                      </Text>
                    </Paper>
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed">
                        Applied
                      </Text>
                      <Text size="sm" fw={700}>
                        {attribution.summary.applied_total}
                      </Text>
                    </Paper>
                    <Paper withBorder radius="md" p="xs">
                      <Text size="xs" c="dimmed">
                        Applied rate
                      </Text>
                      <Text size="sm" fw={700}>
                        {asPercent(attribution.summary.applied_rate)}
                      </Text>
                    </Paper>
                  </SimpleGrid>

                  <Stack gap={4}>
                    {attribution.cohorts.length === 0 && (
                      <Text size="xs" c="dimmed">
                        No attribution cohorts in current window.
                      </Text>
                    )}
                    {attribution.cohorts.slice(0, 8).map((item) => (
                      <Paper
                        key={`attribution-${item.cohort}`}
                        withBorder
                        radius="md"
                        p="xs"
                        style={{
                          cursor: "pointer",
                          borderColor:
                            selectedAttributionCohort === item.cohort ? "var(--mantine-color-blue-4)" : undefined,
                        }}
                        onClick={() => setSelectedAttributionCohort(item.cohort)}
                      >
                        <Group justify="space-between" align="start">
                          <Stack gap={2}>
                            <Text size="sm" fw={600}>
                              {item.cohort}
                            </Text>
                            <Text size="xs" c="dimmed">
                              approvals {item.approvals} • requests {item.requests_involved}
                            </Text>
                          </Stack>
                          <Text size="xs" c="dimmed">
                            applied {asPercent(item.applied_rate)} • lead {asHours(item.avg_first_approval_lead_hours)}
                          </Text>
                        </Group>
                        <Group justify="flex-end" mt={6}>
                          <Button
                            size="xs"
                            variant="subtle"
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedAttributionCohort(item.cohort);
                            }}
                          >
                            Open traces
                          </Button>
                        </Group>
                      </Paper>
                    ))}
                  </Stack>

                  {attributionDrilldown && (
                    <Paper withBorder radius="md" p="xs">
                      <Group justify="space-between" align="center" mb={6}>
                        <Stack gap={2}>
                          <Text size="sm" fw={700}>
                            Rollback Causal Traces
                          </Text>
                          <Text size="xs" c="dimmed">
                            {attributionDrilldown.cohort} • approvals {attributionDrilldown.summary.approvals} • requests{" "}
                            {attributionDrilldown.summary.requests_involved}
                          </Text>
                        </Stack>
                        <Button
                          size="xs"
                          variant="light"
                          loading={loadingAttributionDrilldown}
                          onClick={() => void loadAttributionDrilldown(attributionDrilldown.cohort)}
                        >
                          Refresh traces
                        </Button>
                      </Group>

                      <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb={6}>
                        <Paper withBorder radius="md" p="xs">
                          <Text size="xs" c="dimmed">
                            Applied rate
                          </Text>
                          <Text size="sm" fw={700}>
                            {asPercent(attributionDrilldown.summary.applied_rate)}
                          </Text>
                        </Paper>
                        <Paper withBorder radius="md" p="xs">
                          <Text size="xs" c="dimmed">
                            Resolution rate
                          </Text>
                          <Text size="sm" fw={700}>
                            {asPercent(attributionDrilldown.summary.resolution_rate)}
                          </Text>
                        </Paper>
                        <Paper withBorder radius="md" p="xs">
                          <Text size="xs" c="dimmed">
                            First approval (p50)
                          </Text>
                          <Text size="sm" fw={700}>
                            {asHours(attributionDrilldown.summary.p50_first_approval_lead_hours)}
                          </Text>
                        </Paper>
                        <Paper withBorder radius="md" p="xs">
                          <Text size="xs" c="dimmed">
                            Resolution (p50)
                          </Text>
                          <Text size="sm" fw={700}>
                            {asHours(attributionDrilldown.summary.p50_resolution_lead_hours)}
                          </Text>
                        </Paper>
                      </SimpleGrid>

                      {attributionDrilldown.timeline.length > 0 && (
                        <Paper withBorder radius="md" p="xs" mb={6}>
                          <Text size="xs" c="dimmed" fw={700} mb={4}>
                            Resolution timeline
                          </Text>
                          <Stack gap={2}>
                            {attributionDrilldown.timeline.slice(-7).map((item) => (
                              <Text key={`trace-timeline-${item.day}`} size="xs" c="dimmed">
                                {item.day}: applied {item.applied}, rejected {item.rejected}, failed {item.failed}
                              </Text>
                            ))}
                          </Stack>
                        </Paper>
                      )}

                      <Stack gap={4}>
                        {attributionDrilldown.requests.length === 0 && (
                          <Text size="xs" c="dimmed">
                            No request-level traces for this cohort yet.
                          </Text>
                        )}
                        {attributionDrilldown.requests.slice(0, 10).map((item) => (
                          <Paper key={`rollback-trace-${item.request_id}`} withBorder radius="md" p="xs">
                            <Group justify="space-between" align="start">
                              <Stack gap={2}>
                                <Group gap={6}>
                                  <Text size="sm" fw={600}>
                                    {item.request_id.slice(0, 8)}
                                  </Text>
                                  <Badge variant="light" color={rollbackStatusColor(item.status)}>
                                    {item.status}
                                  </Badge>
                                  <Badge variant="light" color={rollbackRiskColor(item.risk_level)}>
                                    risk {item.risk_level}
                                  </Badge>
                                </Group>
                                <Text size="xs" c="dimmed">
                                  matched {item.matched_actors.join(", ") || "—"} • approvals {item.matched_approvals}/
                                  {item.approval_count} • changed {asPercent(item.changed_ratio)}
                                </Text>
                              </Stack>
                              <Text size="xs" c="dimmed">
                                lead {asHours(item.first_approval_lead_hours)} • resolved {asHours(item.resolution_lead_hours)}
                              </Text>
                            </Group>
                            <ScrollArea.Autosize mah={120} mt={4}>
                              <Stack gap={2}>
                                {item.causal_trace.map((event, index) => (
                                  <Text key={`trace-event-${item.request_id}-${index}`} size="xs" c={event.matched ? "blue" : "dimmed"}>
                                    {fmtDate(event.created_at)} • {event.event_type}
                                    {event.actor ? ` • ${event.actor}` : ""}
                                    {event.note ? ` • ${event.note}` : ""}
                                  </Text>
                                ))}
                              </Stack>
                            </ScrollArea.Autosize>
                          </Paper>
                        ))}
                      </Stack>
                    </Paper>
                  )}
                </Stack>
              )}
            </Paper>

            <Text size="xs" c="dimmed">
              Window since {fmtDate(metrics.since)} • sampled {metrics.sampled_requests} requests • updated {fmtDate(metrics.generated_at)}
            </Text>
          </Stack>
        )}
      </Paper>

      <SimpleGrid cols={{ base: 1, md: 3, xl: 4 }} spacing="sm" mb="sm">
        <NumberInput
          label="Required approvals"
          min={1}
          max={5}
          value={requiredApprovals}
          onChange={(value) => setRequiredApprovals(Math.max(1, Math.min(5, asNumber(value, 2))))}
        />
        <NumberInput
          label="Preview lookback (days)"
          min={1}
          max={365}
          value={lookbackDays}
          onChange={(value) => setLookbackDays(Math.max(1, Math.min(365, asNumber(value, 30))))}
        />
        <NumberInput
          label="Sample changed claims"
          min={1}
          max={200}
          value={sampleSize}
          onChange={(value) => setSampleSize(Math.max(1, Math.min(200, asNumber(value, 25))))}
        />
        <Textarea
          label="Request note"
          minRows={1}
          maxRows={3}
          autosize
          placeholder="Why this rollback should be applied"
          value={requestNote}
          onChange={(event) => setRequestNote(event.currentTarget.value)}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mb="sm">
        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed" fw={700} mb={6}>
            Select snapshot
          </Text>
          <Stack gap={6}>
            {snapshots.length === 0 && (
              <Text size="sm" c="dimmed">
                No snapshots available.
              </Text>
            )}
            {snapshots.map((snapshot) => (
              <Paper key={`rollback-snapshot-${snapshot.id}`} withBorder radius="md" p="xs">
                <Group justify="space-between" align="center">
                  <Stack gap={2}>
                    <Text size="sm" fw={600}>
                      {fmtDate(snapshot.created_at)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {snapshot.source} • by {snapshot.approved_by}
                    </Text>
                  </Stack>
                  <Group gap={6}>
                    <Badge variant="light" color={snapshot.guardrails_met === true ? "teal" : snapshot.guardrails_met === false ? "red" : "gray"}>
                      {snapshot.guardrails_met === true ? "guardrails met" : snapshot.guardrails_met === false ? "guardrails failed" : "guardrails ?"}
                    </Badge>
                    <Button
                      size="xs"
                      variant={previewSnapshotId === snapshot.id ? "filled" : "light"}
                      loading={previewingSnapshotId === snapshot.id}
                      onClick={() => void previewSnapshot(snapshot.id)}
                    >
                      Preview
                    </Button>
                    <Button
                      size="xs"
                      color="orange"
                      loading={creatingSnapshotId === snapshot.id}
                      onClick={() => void createRollbackRequest(snapshot.id)}
                    >
                      Request rollback
                    </Button>
                  </Group>
                </Group>
              </Paper>
            ))}
          </Stack>
        </Paper>

        <Paper withBorder radius="md" p="xs">
          <Text size="xs" c="dimmed" fw={700} mb={6}>
            Selected preview
          </Text>
          {!preview && (
            <Text size="sm" c="dimmed">
              Pick snapshot and click Preview to compute rollback impact.
            </Text>
          )}
          {preview && (
            <Stack gap={6}>
              <Group justify="space-between" align="center">
                <Text size="sm" fw={700}>
                  Snapshot: {selectedSnapshot ? fmtDate(selectedSnapshot.created_at) : preview.snapshot_id}
                </Text>
                <Badge variant="light" color={rollbackRiskColor(preview.impact.risk_level)}>
                  risk {preview.impact.risk_level}
                </Badge>
              </Group>
              <SimpleGrid cols={{ base: 1, md: 3 }} spacing="sm">
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Changed decisions
                  </Text>
                  <Text size="sm" fw={700}>
                    {preview.impact.changed_total} / {preview.impact.decisions_scanned}
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    Changed ratio
                  </Text>
                  <Text size="sm" fw={700}>
                    {(preview.impact.changed_ratio * 100).toFixed(1)}%
                  </Text>
                </Paper>
                <Paper withBorder radius="md" p="xs">
                  <Text size="xs" c="dimmed">
                    From golden
                  </Text>
                  <Text size="sm" fw={700}>
                    {preview.impact.changed_from_golden}
                  </Text>
                </Paper>
              </SimpleGrid>

              <Stack gap={4}>
                <Text size="xs" c="dimmed" fw={700}>
                  Config diff
                </Text>
                {Object.entries(preview.config_diff).length === 0 && (
                  <Text size="sm" c="dimmed">
                    No material config diff detected.
                  </Text>
                )}
                {Object.entries(preview.config_diff).map(([key, value]) => (
                  <Paper key={`config-diff-${key}`} withBorder radius="md" p="xs">
                    <Text size="xs" c="dimmed">
                      {key}
                    </Text>
                    <Text size="sm">
                      {String(value.current ?? "—")} → {String(value.target ?? "—")}
                    </Text>
                  </Paper>
                ))}
              </Stack>

              <Stack gap={4}>
                <Text size="xs" c="dimmed" fw={700}>
                  Changed sample
                </Text>
                {preview.changed_samples.length === 0 && (
                  <Text size="sm" c="dimmed">
                    No tier changes in sampled decisions.
                  </Text>
                )}
                {preview.changed_samples.slice(0, 6).map((item) => (
                  <Paper key={`sample-${item.claim_id}`} withBorder radius="md" p="xs">
                    <Text size="sm" fw={600}>
                      {item.from_tier} → {item.to_tier}
                    </Text>
                    <Text size="xs" c="dimmed">
                      claim {item.claim_id} • score {item.score_current.toFixed(3)} → {item.score_estimated.toFixed(3)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {item.reason ?? "No rationale"}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          )}
        </Paper>
      </SimpleGrid>

      <Paper withBorder radius="md" p="xs">
        <Group justify="space-between" align="center" mb={6}>
          <Text fw={700}>Rollback request queue</Text>
          <SegmentedControl
            size="xs"
            value={statusFilter}
            onChange={(value) => setStatusFilter(value as typeof statusFilter)}
            data={[
              { label: "All", value: "all" },
              { label: "Pending", value: "pending_approval" },
              { label: "Applied", value: "applied" },
              { label: "Rejected", value: "rejected" },
              { label: "Failed", value: "failed" },
            ]}
          />
        </Group>

        <ScrollArea h={340} type="auto">
          <Stack gap={8}>
            {requests.length === 0 && (
              <Text size="sm" c="dimmed">
                No rollback requests for current filter.
              </Text>
            )}
            {requests.map((request) => {
              const requestPreview = previewFromUnknown(request.preview);
              const events = request.approvals;
              const doneApprovals = approvedCount(events);
              const progress = Math.min(100, (doneApprovals / Math.max(1, request.required_approvals)) * 100);
              const actorLocked = actorAlreadyRecorded(events, actor);
              const createdAt = new Date(request.created_at);
              const requestAgeHours = Number.isFinite(createdAt.getTime())
                ? Math.max(0, (Date.now() - createdAt.getTime()) / (1000 * 60 * 60))
                : 0;
              const isPendingSlaBreach = request.status === "pending_approval" && requestAgeHours >= slaHours;
              return (
                <Paper key={`rollback-request-${request.id}`} withBorder radius="md" p="xs">
                  <Group justify="space-between" align="center" mb={4}>
                    <Text size="sm" fw={700}>
                      {request.id}
                    </Text>
                    <Group gap={6}>
                      <Badge variant="light" color={rollbackStatusColor(request.status)}>
                        {request.status}
                      </Badge>
                      <Badge variant="light" color={rollbackRiskColor(requestPreview?.impact.risk_level ?? "unknown")}>
                        risk {requestPreview?.impact.risk_level ?? "unknown"}
                      </Badge>
                      {isPendingSlaBreach && (
                        <Badge variant="light" color="red">
                          SLA breach {asHours(requestAgeHours)}
                        </Badge>
                      )}
                    </Group>
                  </Group>

                  <Text size="xs" c="dimmed">
                    snapshot {request.snapshot_id} • requested by {request.requested_by} • updated {fmtDate(request.updated_at)}
                  </Text>
                  <Text size="xs" c="dimmed" mb={4}>
                    approvals {doneApprovals}/{request.required_approvals}
                  </Text>
                  <Progress value={progress} size="sm" radius="xl" mb={6} />

                  {request.note && (
                    <Text size="xs" c="dimmed">
                      note: {request.note}
                    </Text>
                  )}
                  {request.rejection_reason && (
                    <Text size="xs" c="orange">
                      rejection: {request.rejection_reason}
                    </Text>
                  )}
                  {request.error_message && (
                    <Text size="xs" c="red">
                      error: {request.error_message}
                    </Text>
                  )}

                  <Stack gap={4} mt={6}>
                    <Text size="xs" c="dimmed" fw={700}>
                      Audit trail
                    </Text>
                    {events.length === 0 && (
                      <Text size="xs" c="dimmed">
                        No audit events.
                      </Text>
                    )}
                    {events.map((event, index) => (
                      <Paper key={`event-${request.id}-${index}`} withBorder radius="md" p="xs">
                        <Text size="xs">
                          {event.action} by {event.actor}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {fmtDate(event.created_at)} {event.note ? `• ${event.note}` : ""}
                        </Text>
                      </Paper>
                    ))}
                  </Stack>

                  {request.status === "pending_approval" && (
                    <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm" mt={8}>
                      <TextInput
                        label="Approve note"
                        placeholder="Optional approval context"
                        value={approveNotes[request.id] ?? ""}
                        onChange={(event) =>
                          setApproveNotes((prev) => ({
                            ...prev,
                            [request.id]: event.currentTarget.value,
                          }))
                        }
                        disabled={actorLocked}
                      />
                      <TextInput
                        label="Reject reason"
                        placeholder="Required for reject"
                        value={rejectReasons[request.id] ?? ""}
                        onChange={(event) =>
                          setRejectReasons((prev) => ({
                            ...prev,
                            [request.id]: event.currentTarget.value,
                          }))
                        }
                        disabled={actorLocked}
                      />
                      <Group gap={8}>
                        <Button
                          size="xs"
                          color="teal"
                          leftSection={<IconCheck size={14} />}
                          loading={actingRequestId === `${request.id}:approve`}
                          onClick={() => void approveRequest(request.id)}
                          disabled={actorLocked}
                        >
                          Approve
                        </Button>
                        <Button
                          size="xs"
                          color="orange"
                          variant="light"
                          leftSection={<IconX size={14} />}
                          loading={actingRequestId === `${request.id}:reject`}
                          onClick={() => void rejectRequest(request.id)}
                          disabled={actorLocked}
                        >
                          Reject
                        </Button>
                      </Group>
                      {actorLocked && (
                        <Text size="xs" c="dimmed">
                          Your actor is already recorded in this request. Use a different reviewer account for 4-eyes approval.
                        </Text>
                      )}
                    </SimpleGrid>
                  )}
                </Paper>
              );
            })}
          </Stack>
        </ScrollArea>
      </Paper>
    </Paper>
  );
}
