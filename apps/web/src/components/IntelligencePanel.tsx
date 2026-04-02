import { Badge, Button, Group, Paper, Select, SimpleGrid, Stack, Switch, Text, TextInput, Title } from "@mantine/core";
import { BarChart, LineChart } from "@mantine/charts";
import { notifications } from "@mantine/notifications";
import { IconRefresh } from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import GatekeeperRollbackPanel from "./GatekeeperRollbackPanel";
import GatekeeperSchedulePanel from "./GatekeeperSchedulePanel";

type DailyIntelligenceMetric = {
  metric_date: string;
  claims_created: number;
  drafts_created: number;
  drafts_approved: number;
  drafts_rejected: number;
  statements_added: number;
  conflicts_opened: number;
  conflicts_resolved: number;
  pending_drafts: number;
  open_conflicts: number;
  pages_touched: number;
  knowledge_velocity: number;
  computed_at: string;
};

type WeeklyIntelligenceItem = {
  week_start: string;
  week_end: string;
  days_covered: number;
  claims_created: number;
  drafts_created: number;
  drafts_approved: number;
  drafts_rejected: number;
  statements_added: number;
  conflicts_opened: number;
  conflicts_resolved: number;
  pages_touched: number;
  pending_drafts_end: number;
  open_conflicts_end: number;
  knowledge_velocity_sum: number;
  knowledge_velocity_avg: number;
};

type WeeklyWowMetric = {
  current: number;
  previous: number;
  delta_abs: number;
  delta_pct: number;
};

type WeeklyIntelligencePayload = {
  project_id: string;
  anchor_date: string;
  weeks: WeeklyIntelligenceItem[];
  wow: {
    week_start: string;
    comparisons: {
      drafts_approved: WeeklyWowMetric;
      statements_added: WeeklyWowMetric;
      conflicts_opened: WeeklyWowMetric;
      open_conflicts_end: WeeklyWowMetric;
      knowledge_velocity_avg: WeeklyWowMetric;
    };
  } | null;
};

type IntelligenceDigest = {
  id: string;
  digest_kind: string;
  digest_date: string;
  period_start: string;
  period_end: string;
  status: string;
  headline: string;
  summary_markdown: string;
  payload: Record<string, unknown>;
  generated_by: string;
  generated_at: string;
  sent_at: string | null;
};

type ConflictClassDrilldown = {
  conflict_type: string;
  opened_total: number;
  resolved_total: number;
  dismissed_total: number;
  open_total: number;
  mttr_hours_avg: number | null;
};

type WeeklyConflictDrilldown = {
  week_start: string;
  week_end: string;
  opened_total: number;
  resolved_total: number;
  dismissed_total: number;
  open_total: number;
  mttr_hours_avg: number | null;
  conflict_classes: ConflictClassDrilldown[];
};

type ConflictDrilldownPayload = {
  project_id: string;
  anchor_date: string;
  weeks: WeeklyConflictDrilldown[];
  top_conflict_types: Array<{
    conflict_type: string;
    opened_total: number;
    resolved_total: number;
    resolution_rate_pct: number;
    mttr_hours_avg: number | null;
  }>;
  overall: {
    opened_total: number;
    resolved_total: number;
    dismissed_total: number;
    open_total: number;
    mttr_hours_avg: number | null;
  };
};

type IntelligenceDeliveryTarget = {
  id: string;
  project_id: string;
  channel: string;
  target: string;
  enabled: boolean;
  config: Record<string, unknown>;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
};

type IntelligenceDeliveryAttempt = {
  id: string;
  digest_id: string;
  project_id: string;
  channel: string;
  target: string;
  status: string;
  provider_message_id: string | null;
  error_message: string | null;
  response_payload: Record<string, unknown>;
  attempted_at: string;
};

type GatekeeperConfigSnapshot = {
  id: string;
  project_id: string;
  source: "calibration_cycle" | "manual" | "rollback";
  approved_by: string;
  note: string | null;
  config: Record<string, unknown>;
  guardrails_met: boolean | null;
  holdout_meta: Record<string, unknown>;
  calibration_report: Record<string, unknown>;
  artifact_refs: Record<string, unknown>;
  created_at: string;
};

type GatekeeperCalibrationTrendPoint = {
  snapshot_id: string;
  created_at: string;
  source: string;
  guardrails_met: boolean | null;
  gate_status: "pass" | "watch" | "failed" | "unknown";
  metrics: {
    accuracy: number | null;
    macro_f1: number | null;
    golden_precision: number | null;
  };
  approval_gate: {
    approvals_last_7d: number;
    rejections_last_7d: number;
    approval_rate_last_7d: number | null;
  };
  holdout_meta: Record<string, unknown>;
};

type GatekeeperCalibrationTrendsPayload = {
  project_id: string;
  points: GatekeeperCalibrationTrendPoint[];
  summary: {
    latest_snapshot_id: string | null;
    latest_created_at: string | null;
    latest_gate_status: "pass" | "watch" | "failed" | "unknown" | string;
    latest_guardrails_met: boolean | null;
    latest_metrics: {
      accuracy: number | null;
      macro_f1: number | null;
      golden_precision: number | null;
    } | null;
    latest_approval_gate: {
      approvals_last_7d: number;
      rejections_last_7d: number;
      approval_rate_last_7d: number | null;
    } | null;
    deltas_vs_previous: {
      accuracy: number | null;
      macro_f1: number | null;
      golden_precision: number | null;
    };
  };
};

type GatekeeperCalibrationRunProject = {
  project_id: string;
  schedule_id: string | null;
  schedule_name: string | null;
  status: string;
  project_cycle_status: string | null;
  returncode: number | null;
  alerts: Array<Record<string, unknown>>;
  result: Record<string, unknown>;
  created_at: string;
};

type GatekeeperCalibrationRun = {
  run_id: string;
  status: string;
  started_at: string;
  finished_at: string;
  total_schedules: number;
  executed_count: number;
  alerts_count: number;
  summary: Record<string, unknown>;
  projects: GatekeeperCalibrationRunProject[];
};

type GatekeeperCalibrationRunsPayload = {
  runs: GatekeeperCalibrationRun[];
};

type GatekeeperCalibrationRunTrendsPayload = {
  project_id: string;
  days: number;
  since: string;
  timeline: Array<{
    day: string;
    ok: number;
    alert: number;
    partial_failure: number;
    executed: number;
    alerts_total: number;
  }>;
  summary: {
    executed_total: number;
    alert_total: number;
    partial_failure_total: number;
    alert_ratio: number;
    top_alert_codes: Array<{
      code: string;
      count: number;
    }>;
  };
};

type GatekeeperAlertTarget = {
  id: string;
  project_id: string;
  channel: string;
  target: string;
  enabled: boolean;
  config: Record<string, unknown>;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
};

type GatekeeperAlertAttempt = {
  id: string;
  run_id: string;
  project_id: string;
  channel: string;
  target: string;
  status: string;
  alert_codes: string[];
  error_message: string | null;
  response_payload: Record<string, unknown>;
  attempted_at: string;
};

type IntelligencePanelProps = {
  apiUrl: string;
  projectId: string;
  reviewer?: string;
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

function signedPercent(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(1)}%`;
}

function signedMetricDelta(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  const pct = value * 100;
  const prefix = pct > 0 ? "+" : "";
  return `${prefix}${pct.toFixed(2)} pp`;
}

function gateStatusColor(status: string): string {
  if (status === "pass") {
    return "teal";
  }
  if (status === "watch") {
    return "yellow";
  }
  if (status === "failed") {
    return "red";
  }
  return "gray";
}

function runStatusColor(status: string): string {
  if (status === "ok") return "teal";
  if (status === "alert") return "red";
  if (status === "partial_failure") return "orange";
  if (status === "preview") return "blue";
  return "gray";
}

function parseAlertCodes(raw: string): string[] {
  return raw
    .split(/[\n,\s]+/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function alertTargetRuleSummary(config: Record<string, unknown>): string {
  const minSeverityRaw = config.min_severity;
  const minSeverity =
    typeof minSeverityRaw === "string" && minSeverityRaw.trim()
      ? minSeverityRaw.trim()
      : "warning";
  const alertCodesRaw = config.alert_codes;
  const alertCodes = Array.isArray(alertCodesRaw)
    ? alertCodesRaw.map((item) => String(item).trim()).filter(Boolean)
    : [];
  if (alertCodes.length > 0) {
    return `min severity ${minSeverity} | codes ${alertCodes.join(", ")}`;
  }
  return `min severity ${minSeverity} | codes all`;
}

function extractDigestHighlights(payload: Record<string, unknown> | null): string[] {
  if (!payload) {
    return [];
  }
  const highlights = payload.highlights;
  if (Array.isArray(highlights)) {
    return highlights.map((item) => String(item)).filter(Boolean).slice(0, 4);
  }
  return Object.entries(payload)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`);
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

export default function IntelligencePanel({ apiUrl, projectId, reviewer = "web_ui" }: IntelligencePanelProps) {
  const [loadingIntelligence, setLoadingIntelligence] = useState(false);
  const [dailyMetrics, setDailyMetrics] = useState<DailyIntelligenceMetric[]>([]);
  const [weeklyTrends, setWeeklyTrends] = useState<WeeklyIntelligenceItem[]>([]);
  const [weeklyWow, setWeeklyWow] = useState<WeeklyIntelligencePayload["wow"]>(null);
  const [latestDigest, setLatestDigest] = useState<IntelligenceDigest | null>(null);
  const [conflictDrilldown, setConflictDrilldown] = useState<ConflictDrilldownPayload | null>(null);
  const [deliveryTargets, setDeliveryTargets] = useState<IntelligenceDeliveryTarget[]>([]);
  const [deliveryAttempts, setDeliveryAttempts] = useState<IntelligenceDeliveryAttempt[]>([]);
  const [configSnapshots, setConfigSnapshots] = useState<GatekeeperConfigSnapshot[]>([]);
  const [calibrationTrends, setCalibrationTrends] = useState<GatekeeperCalibrationTrendsPayload | null>(null);
  const [calibrationRuns, setCalibrationRuns] = useState<GatekeeperCalibrationRun[]>([]);
  const [calibrationRunTrends, setCalibrationRunTrends] = useState<GatekeeperCalibrationRunTrendsPayload | null>(null);
  const [gatekeeperAlertTargets, setGatekeeperAlertTargets] = useState<GatekeeperAlertTarget[]>([]);
  const [gatekeeperAlertAttempts, setGatekeeperAlertAttempts] = useState<GatekeeperAlertAttempt[]>([]);
  const [gatekeeperTargetChannel, setGatekeeperTargetChannel] = useState<"slack_webhook" | "email_smtp">("slack_webhook");
  const [gatekeeperTargetAddress, setGatekeeperTargetAddress] = useState("");
  const [gatekeeperTargetEnabled, setGatekeeperTargetEnabled] = useState(true);
  const [gatekeeperTargetMinSeverity, setGatekeeperTargetMinSeverity] = useState<"info" | "warning" | "critical">("warning");
  const [gatekeeperTargetCodes, setGatekeeperTargetCodes] = useState("");
  const [gatekeeperTargetSaving, setGatekeeperTargetSaving] = useState(false);
  const [gatekeeperTargetUpdatingId, setGatekeeperTargetUpdatingId] = useState<string | null>(null);
  const [gatekeeperTargetDeletingId, setGatekeeperTargetDeletingId] = useState<string | null>(null);

  const loadIntelligence = useCallback(async () => {
    if (!projectId.trim()) {
      setDailyMetrics([]);
      setWeeklyTrends([]);
      setWeeklyWow(null);
      setLatestDigest(null);
      setConflictDrilldown(null);
      setDeliveryTargets([]);
      setDeliveryAttempts([]);
      setConfigSnapshots([]);
      setCalibrationTrends(null);
      setCalibrationRuns([]);
      setCalibrationRunTrends(null);
      setGatekeeperAlertTargets([]);
      setGatekeeperAlertAttempts([]);
      return;
    }

    setLoadingIntelligence(true);
    const settled = await Promise.allSettled([
      apiFetch<{ metrics: DailyIntelligenceMetric[] }>(
        apiUrl,
        `/v1/intelligence/metrics/daily?project_id=${encodeURIComponent(projectId)}&limit=30`,
      ),
      apiFetch<WeeklyIntelligencePayload>(
        apiUrl,
        `/v1/intelligence/trends/weekly?project_id=${encodeURIComponent(projectId)}&weeks=8`,
      ),
      apiFetch<{ digest: IntelligenceDigest }>(
        apiUrl,
        `/v1/intelligence/digests/latest?project_id=${encodeURIComponent(projectId)}&kind=daily`,
      ),
      apiFetch<ConflictDrilldownPayload>(
        apiUrl,
        `/v1/intelligence/conflicts/drilldown?project_id=${encodeURIComponent(projectId)}&weeks=8&type_limit=8`,
      ),
      apiFetch<{ targets: IntelligenceDeliveryTarget[] }>(
        apiUrl,
        `/v1/intelligence/delivery/targets?project_id=${encodeURIComponent(projectId)}&limit=50`,
      ),
      apiFetch<{ attempts: IntelligenceDeliveryAttempt[] }>(
        apiUrl,
        `/v1/intelligence/delivery/attempts?project_id=${encodeURIComponent(projectId)}&limit=120`,
      ),
      apiFetch<{ snapshots: GatekeeperConfigSnapshot[] }>(
        apiUrl,
        `/v1/gatekeeper/config/snapshots?project_id=${encodeURIComponent(projectId)}&limit=12`,
      ),
      apiFetch<GatekeeperCalibrationTrendsPayload>(
        apiUrl,
        `/v1/gatekeeper/calibration/trends?project_id=${encodeURIComponent(projectId)}&limit=18`,
      ),
      apiFetch<GatekeeperCalibrationRunsPayload>(
        apiUrl,
        `/v1/gatekeeper/calibration/runs?project_id=${encodeURIComponent(projectId)}&limit=20`,
      ),
      apiFetch<GatekeeperCalibrationRunTrendsPayload>(
        apiUrl,
        `/v1/gatekeeper/calibration/runs/trends?project_id=${encodeURIComponent(projectId)}&days=30`,
      ),
      apiFetch<{ targets: GatekeeperAlertTarget[] }>(
        apiUrl,
        `/v1/gatekeeper/alerts/targets?project_id=${encodeURIComponent(projectId)}&limit=100`,
      ),
      apiFetch<{ attempts: GatekeeperAlertAttempt[] }>(
        apiUrl,
        `/v1/gatekeeper/alerts/attempts?project_id=${encodeURIComponent(projectId)}&limit=120`,
      ),
    ]);

    const failures: string[] = [];
    const metricResult = settled[0];
    if (metricResult.status === "fulfilled") {
      setDailyMetrics(metricResult.value.metrics ?? []);
    } else {
      failures.push("daily metrics");
      setDailyMetrics([]);
    }

    const trendResult = settled[1];
    if (trendResult.status === "fulfilled") {
      setWeeklyTrends(trendResult.value.weeks ?? []);
      setWeeklyWow(trendResult.value.wow ?? null);
    } else {
      failures.push("weekly trends");
      setWeeklyTrends([]);
      setWeeklyWow(null);
    }

    const digestResult = settled[2];
    if (digestResult.status === "fulfilled") {
      setLatestDigest(digestResult.value.digest ?? null);
    } else {
      const message = String(digestResult.reason ?? "");
      if (message.includes("404")) {
        setLatestDigest(null);
      } else {
        failures.push("latest digest");
        setLatestDigest(null);
      }
    }

    const drilldownResult = settled[3];
    if (drilldownResult.status === "fulfilled") {
      setConflictDrilldown(drilldownResult.value);
    } else {
      failures.push("conflict drilldown");
      setConflictDrilldown(null);
    }

    const targetsResult = settled[4];
    if (targetsResult.status === "fulfilled") {
      setDeliveryTargets(targetsResult.value.targets ?? []);
    } else {
      failures.push("delivery targets");
      setDeliveryTargets([]);
    }

    const attemptsResult = settled[5];
    if (attemptsResult.status === "fulfilled") {
      setDeliveryAttempts(attemptsResult.value.attempts ?? []);
    } else {
      failures.push("delivery attempts");
      setDeliveryAttempts([]);
    }

    const snapshotsResult = settled[6];
    if (snapshotsResult.status === "fulfilled") {
      setConfigSnapshots(snapshotsResult.value.snapshots ?? []);
    } else {
      failures.push("config snapshots");
      setConfigSnapshots([]);
    }
    const calibrationTrendsResult = settled[7];
    if (calibrationTrendsResult.status === "fulfilled") {
      setCalibrationTrends(calibrationTrendsResult.value);
    } else {
      failures.push("calibration trends");
      setCalibrationTrends(null);
    }
    const calibrationRunsResult = settled[8];
    if (calibrationRunsResult.status === "fulfilled") {
      setCalibrationRuns(calibrationRunsResult.value.runs ?? []);
    } else {
      failures.push("calibration run history");
      setCalibrationRuns([]);
    }
    const calibrationRunTrendsResult = settled[9];
    if (calibrationRunTrendsResult.status === "fulfilled") {
      setCalibrationRunTrends(calibrationRunTrendsResult.value);
    } else {
      failures.push("calibration run trends");
      setCalibrationRunTrends(null);
    }
    const gatekeeperTargetsResult = settled[10];
    if (gatekeeperTargetsResult.status === "fulfilled") {
      setGatekeeperAlertTargets(gatekeeperTargetsResult.value.targets ?? []);
    } else {
      failures.push("gatekeeper alert targets");
      setGatekeeperAlertTargets([]);
    }
    const gatekeeperAttemptsResult = settled[11];
    if (gatekeeperAttemptsResult.status === "fulfilled") {
      setGatekeeperAlertAttempts(gatekeeperAttemptsResult.value.attempts ?? []);
    } else {
      failures.push("gatekeeper alert attempts");
      setGatekeeperAlertAttempts([]);
    }

    if (failures.length > 0) {
      notifications.show({
        color: "orange",
        title: "Intelligence data partially unavailable",
        message: `Could not load: ${failures.join(", ")}`,
      });
    }
    setLoadingIntelligence(false);
  }, [apiUrl, projectId]);

  const saveGatekeeperAlertTarget = useCallback(async () => {
    if (!projectId.trim()) {
      return;
    }
    if (!gatekeeperTargetAddress.trim()) {
      notifications.show({
        color: "orange",
        title: "Target is required",
        message: "Enter webhook URL or email address for alert routing.",
      });
      return;
    }
    setGatekeeperTargetSaving(true);
    try {
      await apiFetch<{ target: GatekeeperAlertTarget }>(apiUrl, "/v1/gatekeeper/alerts/targets", {
        method: "PUT",
        body: {
          project_id: projectId,
          channel: gatekeeperTargetChannel,
          target: gatekeeperTargetAddress.trim(),
          enabled: gatekeeperTargetEnabled,
          config: {
            min_severity: gatekeeperTargetMinSeverity,
            alert_codes: parseAlertCodes(gatekeeperTargetCodes),
          },
          updated_by: reviewer.trim() || "web_ui",
        },
      });
      notifications.show({
        color: "teal",
        title: "Alert target saved",
        message: "Gatekeeper routing target is now active in scheduler deliveries.",
      });
      setGatekeeperTargetAddress("");
      setGatekeeperTargetCodes("");
      await loadIntelligence();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Could not save target",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setGatekeeperTargetSaving(false);
    }
  }, [
    apiUrl,
    gatekeeperTargetAddress,
    gatekeeperTargetChannel,
    gatekeeperTargetCodes,
    gatekeeperTargetEnabled,
    gatekeeperTargetMinSeverity,
    loadIntelligence,
    projectId,
    reviewer,
  ]);

  const toggleGatekeeperAlertTarget = useCallback(
    async (target: GatekeeperAlertTarget, enabled: boolean) => {
      if (!projectId.trim()) {
        return;
      }
      setGatekeeperTargetUpdatingId(target.id);
      try {
        await apiFetch<{ target: GatekeeperAlertTarget }>(apiUrl, "/v1/gatekeeper/alerts/targets", {
          method: "PUT",
          body: {
            project_id: projectId,
            channel: target.channel,
            target: target.target,
            enabled,
            config: target.config,
            updated_by: reviewer.trim() || "web_ui",
          },
        });
        await loadIntelligence();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Could not update target",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setGatekeeperTargetUpdatingId(null);
      }
    },
    [apiUrl, loadIntelligence, projectId, reviewer],
  );

  const deleteGatekeeperAlertTarget = useCallback(
    async (target: GatekeeperAlertTarget) => {
      if (!projectId.trim()) {
        return;
      }
      setGatekeeperTargetDeletingId(target.id);
      try {
        await apiFetch<{ status: string }>(
          apiUrl,
          `/v1/gatekeeper/alerts/targets/${encodeURIComponent(target.id)}?project_id=${encodeURIComponent(projectId)}`,
          {
            method: "DELETE",
          },
        );
        notifications.show({
          color: "teal",
          title: "Target removed",
          message: `${target.channel} target deleted from routing.`,
        });
        await loadIntelligence();
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Could not delete target",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setGatekeeperTargetDeletingId(null);
      }
    },
    [apiUrl, loadIntelligence, projectId],
  );

  useEffect(() => {
    void loadIntelligence();
  }, [loadIntelligence]);

  const latestMetric = dailyMetrics.length > 0 ? dailyMetrics[0] : null;
  const velocitySeries = useMemo(
    () =>
      [...dailyMetrics].reverse().map((item) => ({
        date: item.metric_date.slice(5),
        knowledge_velocity: Number(item.knowledge_velocity.toFixed(3)),
        drafts_approved: item.drafts_approved,
        pending_drafts: item.pending_drafts,
      })),
    [dailyMetrics],
  );
  const weeklyConflictSeries = weeklyTrends.map((item) => ({
    week: item.week_start.slice(5),
    conflicts_opened: item.conflicts_opened,
    conflicts_resolved: item.conflicts_resolved,
    open_conflicts_end: item.open_conflicts_end,
  }));
  const digestHighlights = extractDigestHighlights(latestDigest?.payload ?? null);
  const conflictTopTypes = conflictDrilldown?.top_conflict_types ?? [];
  const weeklyConflictDrilldown = conflictDrilldown?.weeks ?? [];
  const enabledTargets = deliveryTargets.filter((item) => item.enabled);
  const deliverySent = deliveryAttempts.filter((item) => item.status === "sent").length;
  const deliveryFailed = deliveryAttempts.filter((item) => item.status === "failed").length;
  const deliveryTotal = deliveryAttempts.length;
  const deliveryRatedTotal = deliverySent + deliveryFailed;
  const deliverySuccessRate = deliveryRatedTotal > 0 ? (deliverySent / deliveryRatedTotal) * 100 : 0;
  const lastFailedAttempt = deliveryAttempts.find((item) => item.status === "failed") ?? null;
  const channelStats = Array.from(
    deliveryAttempts
      .reduce(
        (acc, item) => {
          const key = item.channel || "unknown";
          const prev = acc.get(key) ?? { channel: key, sent: 0, failed: 0, total: 0 };
          prev.total += 1;
          if (item.status === "sent") prev.sent += 1;
          if (item.status === "failed") prev.failed += 1;
          acc.set(key, prev);
          return acc;
        },
        new Map<string, { channel: string; sent: number; failed: number; total: number }>(),
      )
      .values(),
  );
  const latestSnapshot = configSnapshots.length > 0 ? configSnapshots[0] : null;
  const snapshotsGuardrailsMet = configSnapshots.filter((item) => item.guardrails_met === true).length;
  const snapshotsGuardrailsFailed = configSnapshots.filter((item) => item.guardrails_met === false).length;
  const latestSnapshotConfig = (latestSnapshot?.config ?? {}) as Record<string, unknown>;
  const latestSnapshotArtifacts = (latestSnapshot?.artifact_refs ?? {}) as Record<string, unknown>;
  const latestSnapshotArtifactEntries = Object.entries(latestSnapshotArtifacts).filter(([, value]) => value != null);
  const calibrationPoints = calibrationTrends?.points ?? [];
  const calibrationSummary = calibrationTrends?.summary ?? null;
  const latestCalibrationRun = calibrationRuns.length > 0 ? calibrationRuns[0] : null;
  const calibrationRunTimeline = calibrationRunTrends?.timeline ?? [];
  const calibrationRunTopAlertCodes = calibrationRunTrends?.summary?.top_alert_codes ?? [];
  const gatekeeperTargetsEnabled = gatekeeperAlertTargets.filter((item) => item.enabled).length;
  const gatekeeperAttemptsSent = gatekeeperAlertAttempts.filter((item) => item.status === "sent").length;
  const gatekeeperAttemptsFailed = gatekeeperAlertAttempts.filter((item) => item.status === "failed").length;
  const gatekeeperAttemptsRated = gatekeeperAttemptsSent + gatekeeperAttemptsFailed;
  const gatekeeperSuccessRate = gatekeeperAttemptsRated > 0 ? (gatekeeperAttemptsSent / gatekeeperAttemptsRated) * 100 : 0;
  const gatekeeperLastFailure = gatekeeperAlertAttempts.find((item) => item.status === "failed") ?? null;
  const calibrationMetricSeries = useMemo(
    () =>
      [...calibrationPoints].reverse().map((point) => ({
        snapshot: point.created_at.slice(5, 16).replace("T", " "),
        accuracy: point.metrics.accuracy != null ? Number((point.metrics.accuracy * 100).toFixed(2)) : null,
        macro_f1: point.metrics.macro_f1 != null ? Number((point.metrics.macro_f1 * 100).toFixed(2)) : null,
        golden_precision:
          point.metrics.golden_precision != null ? Number((point.metrics.golden_precision * 100).toFixed(2)) : null,
      })),
    [calibrationPoints],
  );
  const calibrationApprovalSeries = useMemo(
    () =>
      [...calibrationPoints].reverse().map((point) => ({
        snapshot: point.created_at.slice(5, 16).replace("T", " "),
        approvals_7d: point.approval_gate.approvals_last_7d,
        rejections_7d: point.approval_gate.rejections_last_7d,
      })),
    [calibrationPoints],
  );

  return (
    <Paper radius="xl" p="lg" className="intelligence-panel">
      <Group justify="space-between" align="center" mb="sm">
        <Stack gap={2}>
          <Text className="eyebrow">Intelligence Pulse</Text>
          <Title order={3}>Knowledge Velocity Dashboard</Title>
          <Text size="sm" c="dimmed">
            Daily/weekly learning signal from Synapse Intelligence APIs.
          </Text>
        </Stack>
        <Button
          variant="light"
          color="teal"
          leftSection={<IconRefresh size={16} />}
          loading={loadingIntelligence}
          onClick={() => void loadIntelligence()}
          disabled={!projectId.trim()}
        >
          Refresh Intelligence
        </Button>
      </Group>

      <SimpleGrid cols={{ base: 1, md: 2, lg: 4 }} spacing="sm" mb="md">
        <Paper withBorder radius="lg" p="md" className="metric-card">
          <Text size="xs" c="dimmed">
            Knowledge Velocity (today)
          </Text>
          <Title order={2}>{latestMetric ? latestMetric.knowledge_velocity.toFixed(2) : "—"}</Title>
          <Text size="xs" c="dimmed">
            metric date: {latestMetric ? latestMetric.metric_date : "n/a"}
          </Text>
        </Paper>
        <Paper withBorder radius="lg" p="md" className="metric-card">
          <Text size="xs" c="dimmed">
            Pending approvals
          </Text>
          <Title order={2}>{latestMetric ? latestMetric.pending_drafts : "—"}</Title>
          <Text size="xs" c="dimmed">
            open moderation queue
          </Text>
        </Paper>
        <Paper withBorder radius="lg" p="md" className="metric-card">
          <Text size="xs" c="dimmed">
            Open conflicts
          </Text>
          <Title order={2}>{latestMetric ? latestMetric.open_conflicts : "—"}</Title>
          <Text size="xs" c="dimmed">
            unresolved contradiction load
          </Text>
        </Paper>
        <Paper withBorder radius="lg" p="md" className="metric-card">
          <Text size="xs" c="dimmed">
            Weekly WoW (velocity)
          </Text>
          <Title order={2}>
            {weeklyWow ? signedPercent(weeklyWow.comparisons.knowledge_velocity_avg.delta_pct) : "—"}
          </Title>
          <Text size="xs" c="dimmed">
            vs previous week
          </Text>
        </Paper>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
        <Paper withBorder radius="lg" p="md">
          <Group justify="space-between" mb="xs">
            <Text fw={700}>Daily trend</Text>
            <Badge variant="light" color="teal">
              30d
            </Badge>
          </Group>
          {velocitySeries.length > 0 ? (
            <LineChart
              h={240}
              data={velocitySeries}
              dataKey="date"
              withLegend
              withTooltip
              curveType="monotone"
              series={[
                { name: "knowledge_velocity", color: "teal.6", label: "Knowledge Velocity" },
                { name: "drafts_approved", color: "cyan.6", label: "Drafts Approved" },
              ]}
              valueFormatter={(value) => `${value}`}
            />
          ) : (
            <Text size="sm" c="dimmed">
              No daily metrics yet. Run `run_intelligence_digest.py` to populate baseline data.
            </Text>
          )}
        </Paper>

        <Paper withBorder radius="lg" p="md">
          <Group justify="space-between" mb="xs">
            <Text fw={700}>Weekly conflict trend</Text>
            <Badge variant="light" color="orange">
              8w
            </Badge>
          </Group>
          {weeklyConflictSeries.length > 0 ? (
            <BarChart
              h={240}
              data={weeklyConflictSeries}
              dataKey="week"
              withLegend
              withTooltip
              series={[
                { name: "conflicts_opened", color: "orange.6", label: "Opened" },
                { name: "conflicts_resolved", color: "teal.6", label: "Resolved" },
                { name: "open_conflicts_end", color: "yellow.7", label: "Open End" },
              ]}
            />
          ) : (
            <Text size="sm" c="dimmed">
              Weekly trend is not ready yet for this project.
            </Text>
          )}
        </Paper>
      </SimpleGrid>

      <Paper withBorder radius="lg" p="md" mt="md" className="digest-card">
        <Group justify="space-between" align="center" mb={6}>
          <Text fw={700}>Latest Daily Digest</Text>
          <Badge variant="light" color={latestDigest ? "blue" : "gray"}>
            {latestDigest ? latestDigest.digest_date : "not generated"}
          </Badge>
        </Group>
        {latestDigest ? (
          <Stack gap={6}>
            <Text fw={600}>{latestDigest.headline || "Digest headline not provided"}</Text>
            <Text size="sm" c="dimmed">
              period: {latestDigest.period_start} - {latestDigest.period_end} | generated: {fmtDate(latestDigest.generated_at)}
            </Text>
            <Text size="sm">{latestDigest.summary_markdown || "Summary is empty."}</Text>
            {digestHighlights.length > 0 && (
              <Stack gap={4}>
                {digestHighlights.map((line, index) => (
                  <Paper key={`digest-highlight-${index}`} withBorder radius="md" p="xs">
                    <Text size="sm">{line}</Text>
                  </Paper>
                ))}
              </Stack>
            )}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">
            No digest for this project yet.
          </Text>
        )}
      </Paper>

      <Paper withBorder radius="lg" p="md" mt="md">
        <Group justify="space-between" align="center" mb="sm">
          <Text fw={700}>Conflict Drill-down (MTTR + Classes)</Text>
          <Badge variant="light" color="orange">
            {conflictDrilldown?.overall.mttr_hours_avg ?? "—"}h MTTR
          </Badge>
        </Group>

        {conflictTopTypes.length > 0 && (
          <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="md">
            {conflictTopTypes.map((item) => (
              <Paper key={`top-conflict-${item.conflict_type}`} withBorder radius="md" p="sm">
                <Group justify="space-between" align="flex-start">
                  <Text fw={600} size="sm">
                    {item.conflict_type}
                  </Text>
                  <Badge variant="light" color="orange">
                    {item.opened_total}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed">
                  resolved: {item.resolved_total} | rate: {item.resolution_rate_pct.toFixed(1)}%
                </Text>
                <Text size="xs" c="dimmed">
                  MTTR: {item.mttr_hours_avg ?? "—"}h
                </Text>
              </Paper>
            ))}
          </SimpleGrid>
        )}

        {weeklyConflictDrilldown.length > 0 ? (
          <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
            {weeklyConflictDrilldown.map((week) => (
              <Paper key={`drilldown-week-${week.week_start}`} withBorder radius="md" p="sm">
                <Group justify="space-between" mb={6}>
                  <Text fw={700} size="sm">
                    {week.week_start} - {week.week_end}
                  </Text>
                  <Badge variant="light" color="teal">
                    MTTR {week.mttr_hours_avg ?? "—"}h
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed" mb={8}>
                  opened {week.opened_total} | resolved {week.resolved_total} | open {week.open_total}
                </Text>
                <Stack gap={6}>
                  {week.conflict_classes.length === 0 && (
                    <Text size="xs" c="dimmed">
                      No conflicts in this week.
                    </Text>
                  )}
                  {week.conflict_classes.map((item) => (
                    <Paper key={`${week.week_start}-${item.conflict_type}`} withBorder radius="md" p="xs">
                      <Group justify="space-between" align="center">
                        <Text size="sm" fw={600}>
                          {item.conflict_type}
                        </Text>
                        <Badge variant="light" color="orange">
                          {item.opened_total}
                        </Badge>
                      </Group>
                      <Text size="xs" c="dimmed">
                        resolved {item.resolved_total}, open {item.open_total}, MTTR {item.mttr_hours_avg ?? "—"}h
                      </Text>
                    </Paper>
                  ))}
                </Stack>
              </Paper>
            ))}
          </SimpleGrid>
        ) : (
          <Text size="sm" c="dimmed">
            Drill-down metrics are not available for this project yet.
          </Text>
        )}
      </Paper>

      <Paper withBorder radius="lg" p="md" mt="md">
        <Group justify="space-between" align="center" mb="sm">
          <Text fw={700}>Digest Delivery Observability</Text>
          <Badge variant="light" color={deliverySuccessRate >= 95 ? "teal" : deliverySuccessRate >= 80 ? "yellow" : "red"}>
            success {deliverySuccessRate.toFixed(1)}%
          </Badge>
        </Group>

        <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="md">
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Enabled targets
            </Text>
            <Title order={3}>{enabledTargets.length}</Title>
          </Paper>
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Attempts (window)
            </Text>
            <Title order={3}>{deliveryTotal}</Title>
          </Paper>
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Sent
            </Text>
            <Title order={3}>{deliverySent}</Title>
          </Paper>
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Failed
            </Text>
            <Title order={3}>{deliveryFailed}</Title>
          </Paper>
        </SimpleGrid>

        {channelStats.length > 0 && (
          <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="md">
            {channelStats.map((item) => {
              const rate = item.sent + item.failed > 0 ? (item.sent / (item.sent + item.failed)) * 100 : 0;
              return (
                <Paper key={`channel-${item.channel}`} withBorder radius="md" p="sm">
                  <Group justify="space-between" align="center">
                    <Text fw={700} size="sm">
                      {item.channel}
                    </Text>
                    <Badge variant="light" color={rate >= 95 ? "teal" : rate >= 80 ? "yellow" : "red"}>
                      {rate.toFixed(1)}%
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed">
                    sent {item.sent} | failed {item.failed} | total {item.total}
                  </Text>
                </Paper>
              );
            })}
          </SimpleGrid>
        )}

        {lastFailedAttempt ? (
          <Paper withBorder radius="md" p="sm" mb="md">
            <Text size="xs" c="dimmed" fw={700}>
              Last failure
            </Text>
            <Text size="sm">
              {lastFailedAttempt.channel} at {fmtDate(lastFailedAttempt.attempted_at)}: {lastFailedAttempt.error_message || "unknown error"}
            </Text>
          </Paper>
        ) : (
          <Text size="sm" c="dimmed" mb="md">
            No failed delivery attempts in current window.
          </Text>
        )}

        <Stack gap={6}>
          {deliveryTargets.length === 0 && (
            <Text size="sm" c="dimmed">
              No delivery targets configured.
            </Text>
          )}
          {deliveryTargets.map((target) => (
            <Paper key={target.id} withBorder radius="md" p="xs">
              <Group justify="space-between" align="center">
                <Text size="sm" fw={600}>
                  {target.channel}
                </Text>
                <Badge variant="light" color={target.enabled ? "teal" : "gray"}>
                  {target.enabled ? "enabled" : "disabled"}
                </Badge>
              </Group>
              <Text size="xs" c="dimmed">
                {target.target}
              </Text>
            </Paper>
          ))}
        </Stack>
      </Paper>

      <Paper withBorder radius="lg" p="md" mt="md">
        <Group justify="space-between" align="center" mb="sm">
          <Text fw={700}>Calibration Snapshot History</Text>
          <Badge
            variant="light"
            color={
              snapshotsGuardrailsFailed > 0 ? "red" : snapshotsGuardrailsMet > 0 ? "teal" : "gray"
            }
          >
            {configSnapshots.length} snapshots
          </Badge>
        </Group>

        <SimpleGrid cols={{ base: 1, md: 3 }} spacing="sm" mb="md">
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Latest snapshot
            </Text>
            <Title order={4}>{latestSnapshot ? fmtDate(latestSnapshot.created_at) : "—"}</Title>
          </Paper>
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Guardrails met
            </Text>
            <Title order={4}>{snapshotsGuardrailsMet}</Title>
          </Paper>
          <Paper withBorder radius="md" p="sm">
            <Text size="xs" c="dimmed">
              Guardrails failed
            </Text>
            <Title order={4}>{snapshotsGuardrailsFailed}</Title>
          </Paper>
        </SimpleGrid>

        <Paper withBorder radius="md" p="sm" mb="md">
          <Group justify="space-between" align="center" mb={6}>
            <Text fw={700}>Scheduler Run History (30d)</Text>
            <Badge variant="light" color={runStatusColor(latestCalibrationRun?.status ?? "unknown")}>
              {latestCalibrationRun ? latestCalibrationRun.status : "no runs"}
            </Badge>
          </Group>
          <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb="sm">
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Latest run
              </Text>
              <Text size="sm" fw={700}>
                {latestCalibrationRun ? fmtDate(latestCalibrationRun.finished_at) : "—"}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Executed
              </Text>
              <Text size="sm" fw={700}>
                {latestCalibrationRun ? latestCalibrationRun.executed_count : 0}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Alerts
              </Text>
              <Text size="sm" fw={700}>
                {latestCalibrationRun ? latestCalibrationRun.alerts_count : 0}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Alert ratio
              </Text>
              <Text size="sm" fw={700}>
                {calibrationRunTrends ? `${(calibrationRunTrends.summary.alert_ratio * 100).toFixed(1)}%` : "—"}
              </Text>
            </Paper>
          </SimpleGrid>

          {calibrationRunTimeline.length > 0 ? (
            <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
              <BarChart
                h={220}
                data={calibrationRunTimeline}
                dataKey="day"
                withLegend
                withTooltip
                series={[
                  { name: "ok", color: "teal.6", label: "OK" },
                  { name: "alert", color: "red.6", label: "Alert" },
                  { name: "partial_failure", color: "orange.6", label: "Partial failure" },
                ]}
              />
              <Stack gap={6}>
                <Text size="xs" c="dimmed" fw={700}>
                  Top alert codes
                </Text>
                {calibrationRunTopAlertCodes.length === 0 && (
                  <Text size="sm" c="dimmed">
                    No alert codes in selected window.
                  </Text>
                )}
                {calibrationRunTopAlertCodes.map((item) => (
                  <Paper key={`alert-code-${item.code}`} withBorder radius="md" p="xs">
                    <Group justify="space-between" align="center">
                      <Text size="sm" fw={600}>
                        {item.code}
                      </Text>
                      <Badge variant="light" color="red">
                        {item.count}
                      </Badge>
                    </Group>
                  </Paper>
                ))}
              </Stack>
            </SimpleGrid>
          ) : (
            <Text size="sm" c="dimmed">
              Run history is not available for this project yet.
            </Text>
          )}
        </Paper>

        <GatekeeperSchedulePanel apiUrl={apiUrl} projectId={projectId} reviewer={reviewer} onRefresh={loadIntelligence} />

        <Paper withBorder radius="md" p="sm" mb="md">
          <Group justify="space-between" align="center" mb={6}>
            <Text fw={700}>Gatekeeper Alert Delivery</Text>
            <Badge variant="light" color={gatekeeperSuccessRate >= 95 ? "teal" : gatekeeperSuccessRate >= 80 ? "yellow" : "red"}>
              success {gatekeeperSuccessRate.toFixed(1)}%
            </Badge>
          </Group>
          <SimpleGrid cols={{ base: 1, md: 4 }} spacing="sm" mb="sm">
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Enabled targets
              </Text>
              <Text size="sm" fw={700}>
                {gatekeeperTargetsEnabled}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Attempts
              </Text>
              <Text size="sm" fw={700}>
                {gatekeeperAlertAttempts.length}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Sent
              </Text>
              <Text size="sm" fw={700}>
                {gatekeeperAttemptsSent}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Failed
              </Text>
              <Text size="sm" fw={700}>
                {gatekeeperAttemptsFailed}
              </Text>
            </Paper>
          </SimpleGrid>

          <Paper withBorder radius="md" p="xs" mb="sm">
            <Text size="xs" c="dimmed" fw={700} mb={6}>
              Routing management
            </Text>
            <SimpleGrid cols={{ base: 1, md: 2, xl: 5 }} spacing="sm">
              <Select
                label="Channel"
                data={[
                  { value: "slack_webhook", label: "Slack Webhook" },
                  { value: "email_smtp", label: "SMTP Email" },
                ]}
                value={gatekeeperTargetChannel}
                onChange={(value) =>
                  setGatekeeperTargetChannel(value === "email_smtp" ? "email_smtp" : "slack_webhook")
                }
              />
              <TextInput
                label={gatekeeperTargetChannel === "slack_webhook" ? "Webhook URL" : "Email address"}
                placeholder={
                  gatekeeperTargetChannel === "slack_webhook"
                    ? "https://hooks.slack.com/services/..."
                    : "ops-alerts@example.com"
                }
                value={gatekeeperTargetAddress}
                onChange={(event) => setGatekeeperTargetAddress(event.currentTarget.value)}
              />
              <Select
                label="Min severity"
                data={[
                  { value: "info", label: "Info" },
                  { value: "warning", label: "Warning" },
                  { value: "critical", label: "Critical" },
                ]}
                value={gatekeeperTargetMinSeverity}
                onChange={(value) =>
                  setGatekeeperTargetMinSeverity(value === "info" || value === "critical" ? value : "warning")
                }
              />
              <TextInput
                label="Alert codes (optional)"
                placeholder="precision_drop, high_alert_ratio"
                value={gatekeeperTargetCodes}
                onChange={(event) => setGatekeeperTargetCodes(event.currentTarget.value)}
              />
              <Stack gap={6} justify="flex-end">
                <Switch
                  label="Enabled"
                  checked={gatekeeperTargetEnabled}
                  onChange={(event) => setGatekeeperTargetEnabled(event.currentTarget.checked)}
                />
                <Button
                  size="xs"
                  color="teal"
                  loading={gatekeeperTargetSaving}
                  onClick={() => void saveGatekeeperAlertTarget()}
                  disabled={!projectId.trim()}
                >
                  Save target
                </Button>
              </Stack>
            </SimpleGrid>
          </Paper>

          {gatekeeperLastFailure ? (
            <Paper withBorder radius="md" p="xs" mb="sm">
              <Text size="xs" c="dimmed" fw={700}>
                Last failure
              </Text>
              <Text size="sm">
                {gatekeeperLastFailure.channel} at {fmtDate(gatekeeperLastFailure.attempted_at)}:{" "}
                {gatekeeperLastFailure.error_message || "unknown error"}
              </Text>
            </Paper>
          ) : (
            <Text size="sm" c="dimmed" mb="sm">
              No failed gatekeeper alerts in current window.
            </Text>
          )}

          <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
            <Stack gap={6}>
              <Text size="xs" c="dimmed" fw={700}>
                Targets
              </Text>
              {gatekeeperAlertTargets.length === 0 && (
                <Text size="sm" c="dimmed">
                  No gatekeeper alert targets configured.
                </Text>
              )}
              {gatekeeperAlertTargets.map((target) => (
                <Paper key={`gatekeeper-target-${target.id}`} withBorder radius="md" p="xs">
                  <Group justify="space-between" align="center">
                    <Text size="sm" fw={600}>
                      {target.channel}
                    </Text>
                    <Group gap={6}>
                      <Badge variant="light" color={target.enabled ? "teal" : "gray"}>
                        {target.enabled ? "enabled" : "disabled"}
                      </Badge>
                      <Button
                        size="xs"
                        variant="subtle"
                        loading={gatekeeperTargetUpdatingId === target.id}
                        onClick={() => void toggleGatekeeperAlertTarget(target, !target.enabled)}
                        disabled={!projectId.trim()}
                      >
                        {target.enabled ? "Disable" : "Enable"}
                      </Button>
                      <Button
                        size="xs"
                        color="red"
                        variant="subtle"
                        loading={gatekeeperTargetDeletingId === target.id}
                        onClick={() => void deleteGatekeeperAlertTarget(target)}
                        disabled={!projectId.trim()}
                      >
                        Delete
                      </Button>
                    </Group>
                  </Group>
                  <Text size="xs" c="dimmed">
                    {target.target}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {alertTargetRuleSummary(target.config)}
                  </Text>
                </Paper>
              ))}
            </Stack>

            <Stack gap={6}>
              <Text size="xs" c="dimmed" fw={700}>
                Recent attempts
              </Text>
              {gatekeeperAlertAttempts.slice(0, 8).map((attempt) => (
                <Paper key={`gatekeeper-attempt-${attempt.id}`} withBorder radius="md" p="xs">
                  <Group justify="space-between" align="center">
                    <Text size="sm" fw={600}>
                      {attempt.channel}
                    </Text>
                    <Badge variant="light" color={attempt.status === "sent" ? "teal" : attempt.status === "failed" ? "red" : "gray"}>
                      {attempt.status}
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed">
                    run {attempt.run_id} | {fmtDate(attempt.attempted_at)}
                  </Text>
                  {attempt.alert_codes.length > 0 && (
                    <Text size="xs" c="dimmed">
                      codes: {attempt.alert_codes.join(", ")}
                    </Text>
                  )}
                </Paper>
              ))}
              {gatekeeperAlertAttempts.length === 0 && (
                <Text size="sm" c="dimmed">
                  No gatekeeper alert attempts yet.
                </Text>
              )}
            </Stack>
          </SimpleGrid>
        </Paper>

        <Paper withBorder radius="md" p="sm" mb="md">
          <Group justify="space-between" align="center" mb={6}>
            <Text fw={700}>Guardrail Trend</Text>
            <Badge variant="light" color={gateStatusColor(calibrationSummary?.latest_gate_status ?? "unknown")}>
              gate {calibrationSummary?.latest_gate_status ?? "unknown"}
            </Badge>
          </Group>
          <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="sm">
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Accuracy
              </Text>
              <Text size="sm" fw={700}>
                {calibrationSummary?.latest_metrics?.accuracy != null
                  ? `${(calibrationSummary.latest_metrics.accuracy * 100).toFixed(2)}%`
                  : "—"}
              </Text>
              <Text size="xs" c="dimmed">
                Δ {signedMetricDelta(calibrationSummary?.deltas_vs_previous?.accuracy)}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Macro F1
              </Text>
              <Text size="sm" fw={700}>
                {calibrationSummary?.latest_metrics?.macro_f1 != null
                  ? `${(calibrationSummary.latest_metrics.macro_f1 * 100).toFixed(2)}%`
                  : "—"}
              </Text>
              <Text size="xs" c="dimmed">
                Δ {signedMetricDelta(calibrationSummary?.deltas_vs_previous?.macro_f1)}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Golden precision
              </Text>
              <Text size="sm" fw={700}>
                {calibrationSummary?.latest_metrics?.golden_precision != null
                  ? `${(calibrationSummary.latest_metrics.golden_precision * 100).toFixed(2)}%`
                  : "—"}
              </Text>
              <Text size="xs" c="dimmed">
                Δ {signedMetricDelta(calibrationSummary?.deltas_vs_previous?.golden_precision)}
              </Text>
            </Paper>
            <Paper withBorder radius="md" p="xs">
              <Text size="xs" c="dimmed">
                Approval gate (7d)
              </Text>
              <Text size="sm" fw={700}>
                {calibrationSummary?.latest_approval_gate?.approval_rate_last_7d != null
                  ? `${calibrationSummary.latest_approval_gate.approval_rate_last_7d.toFixed(1)}%`
                  : "—"}
              </Text>
              <Text size="xs" c="dimmed">
                +{calibrationSummary?.latest_approval_gate?.approvals_last_7d ?? 0} / -
                {calibrationSummary?.latest_approval_gate?.rejections_last_7d ?? 0}
              </Text>
            </Paper>
          </SimpleGrid>

          {calibrationMetricSeries.length > 0 ? (
            <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
              <LineChart
                h={220}
                data={calibrationMetricSeries}
                dataKey="snapshot"
                withLegend
                withTooltip
                series={[
                  { name: "accuracy", color: "teal.6", label: "Accuracy %" },
                  { name: "macro_f1", color: "blue.6", label: "Macro F1 %" },
                  { name: "golden_precision", color: "orange.6", label: "Golden Precision %" },
                ]}
              />
              <BarChart
                h={220}
                data={calibrationApprovalSeries}
                dataKey="snapshot"
                withLegend
                withTooltip
                series={[
                  { name: "approvals_7d", color: "teal.6", label: "Approvals 7d" },
                  { name: "rejections_7d", color: "red.6", label: "Rejections 7d" },
                ]}
              />
            </SimpleGrid>
          ) : (
            <Text size="sm" c="dimmed">
              Guardrail trend data will appear after first calibration snapshots.
            </Text>
          )}
        </Paper>

        {latestSnapshot ? (
          <Paper withBorder radius="md" p="sm" mb="md">
            <Group justify="space-between" align="center" mb={6}>
              <Text fw={700}>Latest Approved Config</Text>
              <Badge
                variant="light"
                color={
                  latestSnapshot.guardrails_met === true
                    ? "teal"
                    : latestSnapshot.guardrails_met === false
                      ? "red"
                      : "gray"
                }
              >
                {latestSnapshot.guardrails_met === true
                  ? "guardrails met"
                  : latestSnapshot.guardrails_met === false
                    ? "guardrails failed"
                    : "guardrails unknown"}
              </Badge>
            </Group>
            <Text size="xs" c="dimmed" mb={8}>
              source: {latestSnapshot.source} | approved_by: {latestSnapshot.approved_by}
            </Text>
            <SimpleGrid cols={{ base: 1, md: 2, xl: 4 }} spacing="sm" mb="sm">
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  min_score_for_golden
                </Text>
                <Text size="sm" fw={700}>
                  {String(latestSnapshotConfig.min_score_for_golden ?? "—")}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  llm_score_weight
                </Text>
                <Text size="sm" fw={700}>
                  {String(latestSnapshotConfig.llm_score_weight ?? "—")}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  llm_min_confidence
                </Text>
                <Text size="sm" fw={700}>
                  {String(latestSnapshotConfig.llm_min_confidence ?? "—")}
                </Text>
              </Paper>
              <Paper withBorder radius="md" p="xs">
                <Text size="xs" c="dimmed">
                  llm_model
                </Text>
                <Text size="sm" fw={700}>
                  {String(latestSnapshotConfig.llm_model ?? "—")}
                </Text>
              </Paper>
            </SimpleGrid>

            <Stack gap={4}>
              <Text size="xs" c="dimmed" fw={700}>
                Artifact refs
              </Text>
              {latestSnapshotArtifactEntries.length === 0 && (
                <Text size="xs" c="dimmed">
                  No artifacts attached.
                </Text>
              )}
              {latestSnapshotArtifactEntries.map(([key, value]) => {
                const rendered = String(value);
                const isLink = rendered.startsWith("http://") || rendered.startsWith("https://");
                return (
                  <Paper key={`artifact-${key}`} withBorder radius="md" p="xs">
                    <Text size="xs" c="dimmed">
                      {key}
                    </Text>
                    {isLink ? (
                      <Text size="sm" component="a" href={rendered} target="_blank" rel="noreferrer">
                        {rendered}
                      </Text>
                    ) : (
                      <Text size="sm" ff="monospace">
                        {rendered}
                      </Text>
                    )}
                  </Paper>
                );
              })}
            </Stack>
          </Paper>
        ) : (
          <Text size="sm" c="dimmed" mb="md">
            No calibration snapshots yet for this project.
          </Text>
        )}

        <GatekeeperRollbackPanel apiUrl={apiUrl} projectId={projectId} reviewer={reviewer} snapshots={configSnapshots} onRefresh={loadIntelligence} />

        <Stack gap={6}>
          {configSnapshots.map((snapshot) => (
            <Paper key={snapshot.id} withBorder radius="md" p="xs">
              <Group justify="space-between" align="center">
                <Text size="sm" fw={600}>
                  {fmtDate(snapshot.created_at)}
                </Text>
                <Badge
                  variant="light"
                  color={snapshot.guardrails_met === true ? "teal" : snapshot.guardrails_met === false ? "red" : "gray"}
                >
                  {snapshot.source}
                </Badge>
              </Group>
              <Text size="xs" c="dimmed">
                by {snapshot.approved_by} | guardrails{" "}
                {snapshot.guardrails_met === true ? "met" : snapshot.guardrails_met === false ? "failed" : "unknown"}
              </Text>
            </Paper>
          ))}
        </Stack>
      </Paper>
    </Paper>
  );
}
