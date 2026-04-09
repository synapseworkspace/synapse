#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/6] Validate JSON schemas"
for f in packages/synapse-schema/schemas/v1/*.json; do
  jq . "$f" >/dev/null
done

echo "[2/6] Python compile checks"
python3 -m compileall -q \
  packages/synapse-sdk-py/src \
  services/api/app \
  services/api/scripts \
  services/mcp/app \
  services/mcp/scripts \
  services/shared \
  services/worker/app \
  services/worker/scripts \
  demos
python3 -m py_compile scripts/integration_moderation_backfill.py
python3 -m py_compile scripts/eval_synthesis_regression.py
python3 -m py_compile scripts/eval_gatekeeper_regression.py
python3 -m py_compile scripts/build_gatekeeper_holdout_from_db.py
python3 -m py_compile scripts/eval_mcp_retrieval_regression.py
python3 -m py_compile scripts/benchmark_mcp_retrieval.py
python3 -m py_compile scripts/check_mcp_retrieval_trend.py
python3 -m py_compile scripts/apply_gatekeeper_calibration.py
python3 -m py_compile scripts/run_gatekeeper_calibration_cycle.py
python3 -m py_compile scripts/run_gatekeeper_calibration_scheduler.py
python3 -m py_compile scripts/monitor_gatekeeper_drift.py
python3 -m py_compile scripts/calibrate_gatekeeper_llm_thresholds.py
python3 -m py_compile scripts/integration_openclaw_mcp_runtime.py
python3 -m py_compile scripts/integration_openclaw_runtime_contract.py
python3 -m py_compile scripts/integration_core_loop.py
python3 -m py_compile scripts/integration_legacy_sync_queue_processing.py
python3 -m py_compile scripts/integration_lifecycle_telemetry.py
python3 -m py_compile scripts/check_queue_governance_policy.py
python3 -m py_compile scripts/check_release_versions.py
python3 -m py_compile scripts/bump_release_version.py
python3 -m py_compile scripts/check_python_package_install_smoke.py
python3 -m py_compile scripts/generate_release_evidence_bundle.py
python3 -m py_compile scripts/check_publish_hygiene.py
python3 -m py_compile scripts/generate_sdk_api_reference.py
python3 -m py_compile scripts/check_repo_hygiene.py
python3 -m py_compile scripts/check_registry_package_availability.py
python3 -m py_compile scripts/check_api_web_compat_contract.py
python3 -m py_compile scripts/run_performance_tuning_advisor.py
python3 -m py_compile scripts/verify_openclaw_provenance.py
python3 -m py_compile scripts/smoke_openclaw_provenance_verification.py
python3 -m py_compile scripts/check_mcp_api_retrieval_parity.py
python3 -m py_compile scripts/eval_legacy_seed_regression.py
python3 -m py_compile scripts/check_openclaw_docs_canonical.py
python3 -m py_compile scripts/check_operations_runbook_parity.py
python3 -m py_compile scripts/check_cookbook_snapshots.py
python3 -m py_compile scripts/check_framework_adapter_contracts.py
python3 -m py_compile scripts/check_framework_native_bindings.py
python3 -m py_compile scripts/check_framework_quickstart_parity.py
python3 -m py_compile scripts/check_synapse_cli_adoption_ops.py
python3 -m py_compile scripts/benchmark_agentic_onboarding.py
python3 -m py_compile scripts/check_positioning_consistency.py
python3 -m py_compile scripts/check_core_slo_guardrails.py
python3 -m py_compile scripts/check_operational_slo_guardrails.py
python3 -m py_compile scripts/capture_operational_slo_snapshots.py
python3 -m py_compile scripts/check_release_error_budget.py
python3 -m py_compile scripts/run_reliability_drills.py
python3 -m py_compile scripts/export_enterprise_governance_pack.py
python3 -m py_compile scripts/check_selfhost_stack_defaults.py
python3 -m py_compile scripts/check_legacy_sync_wal_connector.py
python3 scripts/check_api_web_compat_contract.py

echo "[2.1/6] Worker routing unit tests"
python3 -m unittest discover -s services/worker/tests -p 'test_*.py' >/dev/null

echo "[2.2/6] Python SDK legacy/adoption contract tests"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python3 -m unittest \
  packages/synapse-sdk-py/tests/test_legacy_import_methods.py >/dev/null

echo "[3/6] TypeScript typecheck"
npm exec --yes --package typescript@5.8.3 -- tsc -p packages/synapse-sdk-ts/tsconfig.json --noEmit
npm exec --yes --package typescript@5.8.3 -- tsc -p packages/synapse-openclaw-plugin/tsconfig.json --noEmit
npm exec --yes --package typescript@5.8.3 -- tsc -p packages/synapse-sdk-ts/tsconfig.json
node --input-type=module - <<'JS'
import assert from "node:assert/strict";
import {
  MCPContextHelper,
  Synapse,
  buildOpenClawBootstrapOptions,
  collectOpenClawBootstrapRecords,
  listOpenClawBootstrapPresets
} from "./packages/synapse-sdk-ts/dist/index.js";

const runtime = {
  handlers: {},
  tools: {},
  memory: {
    exportAll() {
      return [
        { source_id: "mem-1", content: "Warehouse #2 ramp is broken.", entity_key: "warehouse_2", category: "logistics" },
        "BC Omega now requires a physical key-card after 10:00."
      ];
    }
  },
  event_log: [
    {
      event_name: "tool:result",
      payload: {
        result: "Driver reported gate-card requirement for BC Omega.",
        entity_key: "bc_omega",
        category: "access",
        source_id: "evt-1"
      }
    }
  ],
  on(eventName, handler) {
    this.handlers[eventName] = handler;
  },
  register_tool(name, handler, description) {
    this.tools[name] = { handler, description };
  }
};

process.env.SYNAPSE_API_URL = "http://localhost:8080";
process.env.SYNAPSE_PROJECT_ID = "omega_env";

const presets = listOpenClawBootstrapPresets();
assert.ok(presets.some((item) => item.preset === "hybrid"), presets);
const directRecords = collectOpenClawBootstrapRecords(runtime, { preset: "hybrid", maxRecords: 10 });
assert.ok(directRecords.length >= 2, directRecords);
const manual = buildOpenClawBootstrapOptions({ preset: "event_log", maxRecords: 10 });
assert.equal(typeof manual.provider, "function");
assert.throws(
  () => new MCPContextHelper("p", async () => ({ results: [] }), { defaultContextPolicyProfile: "strict" }),
  /unsupported context policy profile/
);
assert.throws(
  () => new MCPContextHelper("p", async () => ({ results: [] }), { defaultContextPolicyProfile: "default" }),
  /unsupported context policy profile/
);

const transport = {
  events: [],
  claims: [],
  backfills: [],
  requests: [],
  async sendEvents(events) {
    this.events.push(...events);
  },
  async proposeFact(claim) {
    this.claims.push(claim);
  },
  async ingestMemoryBackfill(payload) {
    this.backfills.push(payload);
  },
  async requestJson(path, options = {}) {
    this.requests.push({
      path,
      method: String(options.method || "GET").toUpperCase(),
      payload: options.payload || {},
      params: options.params || {}
    });
    if (path === "/v1/mcp/retrieval/explain" && options.method === "GET") {
      const params = options.params || {};
      return {
        results: [
          {
            statement_text: `retrieved:${String(params.q || "")}`,
            page: { slug: "bc-omega", entity_key: params.related_entity_key || "bc_omega" }
          }
        ],
        revision: "r-ts-smoke"
      };
    }
    if (path === "/v1/tasks" && options.method === "GET") {
      return { tasks: [] };
    }
    return {};
  }
};

const synapse = new Synapse({ apiUrl: "http://localhost:8080", projectId: "omega_demo" }, transport);
const envSynapse = Synapse.fromEnv({}, transport);
assert.equal(envSynapse.projectId, "omega_env");
synapse.setDebugMode({ enabled: true, maxRecords: 200 });
synapse.attach(runtime, {
  integration: "openclaw",
  openclawBootstrapPreset: "hybrid",
  openclawBootstrapMaxRecords: 10,
  openclawBootstrapChunkSize: 2
});
await new Promise((resolve) => setTimeout(resolve, 20));

assert.ok(transport.backfills.length >= 1, transport.backfills);
assert.ok(typeof runtime.handlers["tool:result"] === "function", runtime.handlers);
assert.ok(typeof runtime.tools["synapse_search_wiki"]?.handler === "function", runtime.tools);
assert.ok(typeof runtime.tools["synapse_propose_to_wiki"]?.handler === "function", runtime.tools);
const toolSearchResult = await runtime.tools["synapse_search_wiki"].handler("omega gate", { limit: 2, filters: { entity_key: "bc_omega" } });
assert.ok(Array.isArray(toolSearchResult) && toolSearchResult.length >= 1, toolSearchResult);
const toolProposal = await runtime.tools["synapse_propose_to_wiki"].handler({
  entity_key: "bc_omega",
  category: "access",
  claim_text: "BC Omega requires cards after 10:00",
  source_id: "ts-smoke-source"
});
assert.equal(toolProposal.status, "queued", toolProposal);
runtime.handlers["tool:result"]({ sessionKey: "s-1", result: "driver confirmed policy" });
const debugNames = new Set(synapse.getDebugRecords().map((item) => item.event));
assert.ok(debugNames.has("attach_openclaw_bootstrap_preset_enabled"), debugNames);
assert.ok(debugNames.has("attach_bootstrap_completed"), debugNames);
assert.ok(debugNames.has("attach_completed"), debugNames);
assert.ok(debugNames.has("attach_openclaw_search_auto_enabled"), debugNames);
const onboardingMetrics = synapse.getOnboardingMetrics(200);
assert.ok((onboardingMetrics.attachEventsTotal ?? 0) >= 1, onboardingMetrics);

class LangGraphLikeRunner {
  invoke(payload) {
    return { framework: "langgraph", payload };
  }
  async ainvoke(payload) {
    return { framework: "langgraph", payload, mode: "async" };
  }
  *stream(payload) {
    yield { framework: "langgraph", payload, chunk: 1 };
    yield { framework: "langgraph", payload, chunk: 2 };
  }
}

class LangChainLikeRunner {
  invoke(payload) {
    return { framework: "langchain", payload };
  }
  call(payload) {
    return { framework: "langchain", payload, via: "call" };
  }
}

class CrewAiLikeRunner {
  kickoff() {
    return { framework: "crewai", status: "ok" };
  }
}

class NativeLangChainBoundRunner {
  constructor(callbacks = []) {
    this.callbacks = callbacks;
  }
  invoke(payload) {
    for (const callback of this.callbacks) {
      if (typeof callback.on_chain_start === "function") {
        callback.on_chain_start({ name: "native_chain" }, payload, { run_id: "ts-lc-run-1", parent_run_id: "ts-parent-1" });
      } else if (typeof callback.handleChainStart === "function") {
        callback.handleChainStart({ name: "native_chain" }, payload, "ts-lc-run-1", "ts-parent-1", {});
      }
    }
    const result = { result: `native:${String(payload?.input ?? "unknown")}` };
    for (const callback of this.callbacks) {
      if (typeof callback.on_chain_end === "function") {
        callback.on_chain_end(result, { run_id: "ts-lc-run-1", parent_run_id: "ts-parent-1" });
      } else if (typeof callback.handleChainEnd === "function") {
        callback.handleChainEnd(result, "ts-lc-run-1", "ts-parent-1", {});
      }
    }
    return result;
  }
}

class NativeLangChainRuntime {
  withConfig(config) {
    return new NativeLangChainBoundRunner(Array.isArray(config?.callbacks) ? config.callbacks : []);
  }
}

class NativeCrewRuntime {
  constructor() {
    this.listeners = {};
    this.stepCallback = undefined;
  }
  on(eventName, handler) {
    this.listeners[eventName] = handler;
  }
  kickoff() {
    const started = this.listeners["crew_started"];
    if (typeof started === "function") started({ status: "started" });
    if (typeof this.stepCallback === "function") this.stepCallback({ phase: "plan" });
    const completed = this.listeners["crew_completed"];
    if (typeof completed === "function") completed({ status: "completed" });
    return { status: "ok" };
  }
}

const frameworkSynapse = new Synapse({ apiUrl: "http://localhost:8080", projectId: "framework_smoke" }, transport);
frameworkSynapse.setDebugMode({ enabled: true, maxRecords: 500 });

const lg = frameworkSynapse.attach(new LangGraphLikeRunner());
lg.invoke({ question: "gate policy" });
for (const _item of lg.stream({ question: "gate policy" })) {
  // consume stream
}
await lg.ainvoke({ question: "gate policy" });

const lc = frameworkSynapse.attach(new LangChainLikeRunner());
lc.invoke({ question: "route update" });
lc.call({ question: "route update" });

const crewRunner = frameworkSynapse.attach(new CrewAiLikeRunner());
crewRunner.kickoff();

const nativeLangChain = frameworkSynapse.bindLangchain(new NativeLangChainRuntime(), { fallbackMonitor: false, sessionId: "native-lc" });
const nativeLcResult = nativeLangChain.invoke({ input: "hello" });
assert.equal(nativeLcResult.result, "native:hello", nativeLcResult);

const nativeLangGraph = frameworkSynapse.bindLanggraph(new NativeLangChainRuntime(), { fallbackMonitor: false, sessionId: "native-lg" });
const nativeLgResult = nativeLangGraph.invoke({ input: "graph" });
assert.equal(nativeLgResult.result, "native:graph", nativeLgResult);

const nativeCrew = frameworkSynapse.bindCrewAi(new NativeCrewRuntime(), { sessionId: "native-crewai" });
nativeCrew.kickoff();

const frozenRunner = Object.preventExtensions({
  invoke(payload) {
    return { ok: true, payload };
  }
});
const fallbackNative = frameworkSynapse.bindLangchain(frozenRunner, {
  fallbackMonitor: true,
  monitorIncludeMethods: ["invoke"],
  sessionId: "native-fallback"
});
fallbackNative.invoke({ input: "fallback" });

await frameworkSynapse.flush();

await synapse.bulkReviewWikiDrafts({
  reviewedBy: "ops_reviewer",
  action: "approve",
  dryRun: true,
  limit: 12,
  filter: { category: "policy", source_system: "postgres_sql" }
});
await synapse.getAdoptionPipelineVisibility({
  days: 7,
  sourceSystems: ["postgres_sql"],
  namespaces: ["ops"]
});
await synapse.getAdoptionRejectionDiagnostics({ days: 7, sampleLimit: 3 });
await synapse.enableAdoptionSafeMode({
  updatedBy: "ops_admin",
  dryRun: true,
  note: "ci safe-mode dry-run"
});
await synapse.runAdoptionProjectReset({
  requestedBy: "ops_admin",
  scopes: ["drafts", "wiki"],
  cascadeCleanupOrphanDraftPages: true,
  dryRun: true
});
await synapse.executeAdoptionSyncPreset({
  updatedBy: "ops_admin",
  dryRun: true,
  syncProcessorLookbackMinutes: 60,
  failOnSyncProcessorUnavailable: true,
  autoApplySafeModeOnCritical: false
});
await synapse.listWikiDrafts({ status: "pending_review", limit: 25 });
await synapse.getAdoptionSyncCursorHealth({ staleAfterHours: 72 });

const hasBulkReview = transport.requests.some((req) => req.path === "/v1/wiki/drafts/bulk-review" && req.method === "POST");
const hasListDrafts = transport.requests.some((req) => req.path === "/v1/wiki/drafts" && req.method === "GET");
const hasProjectReset = transport.requests.some((req) => req.path === "/v1/adoption/project-reset" && req.method === "POST");
const hasCursorHealth = transport.requests.some((req) => req.path === "/v1/adoption/sync/cursor-health" && req.method === "GET");
const hasPipelineVisibility = transport.requests.some((req) => req.path === "/v1/adoption/pipeline/visibility" && req.method === "GET");
const hasRejectionDiagnostics = transport.requests.some((req) => req.path === "/v1/adoption/rejections/diagnostics" && req.method === "GET");
const hasSafeMode = transport.requests.some((req) => req.path === "/v1/adoption/safe-mode/enable" && req.method === "POST");
const syncPresetCall = transport.requests.find((req) => req.path === "/v1/adoption/sync-presets/execute" && req.method === "POST");
assert.equal(hasBulkReview, true, transport.requests);
assert.equal(hasListDrafts, true, transport.requests);
assert.equal(hasProjectReset, true, transport.requests);
assert.equal(hasCursorHealth, true, transport.requests);
assert.equal(hasPipelineVisibility, true, transport.requests);
assert.equal(hasRejectionDiagnostics, true, transport.requests);
assert.equal(hasSafeMode, true, transport.requests);
assert.equal(Boolean(syncPresetCall), true, transport.requests);
assert.equal(syncPresetCall?.payload?.auto_apply_safe_mode_on_critical, false, syncPresetCall);
assert.equal(syncPresetCall?.payload?.sync_processor_lookback_minutes, 60, syncPresetCall);
assert.equal(syncPresetCall?.payload?.fail_on_sync_processor_unavailable, true, syncPresetCall);

const frameworkDebug = frameworkSynapse.getDebugRecords();
const frameworkAttachIntegrations = new Set(
  frameworkDebug
    .filter((item) => item.event === "attach_started")
    .map((item) => String(item.details?.integration || ""))
    .filter(Boolean)
);
assert.ok(frameworkAttachIntegrations.has("langgraph"), frameworkAttachIntegrations);
assert.ok(frameworkAttachIntegrations.has("langchain"), frameworkAttachIntegrations);
assert.ok(frameworkAttachIntegrations.has("crewai"), frameworkAttachIntegrations);
assert.ok(frameworkDebug.some((item) => item.event === "native_framework_bound"), frameworkDebug.map((item) => item.event));
assert.ok(frameworkDebug.some((item) => item.event === "native_framework_fallback_monitor"), frameworkDebug.map((item) => item.event));

console.log("ts openclaw bootstrap preset smoke ok");
JS
npm --prefix packages/synapse-openclaw-plugin install --silent
npm --prefix packages/synapse-openclaw-plugin run test >/dev/null
npm --prefix apps/web install --silent
npm --prefix apps/web run build >/dev/null

echo "[3.1/6] Web browser e2e (Playwright)"
if [[ "${SYNAPSE_SKIP_WEB_E2E:-0}" == "1" ]]; then
  echo "web e2e skipped (SYNAPSE_SKIP_WEB_E2E=1)"
else
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT_DIR/.cache/ms-playwright}"
  mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"
  npm --prefix apps/web run e2e:install >/dev/null
  WEB_E2E_SCOPE="${SYNAPSE_WEB_E2E_SCOPE:-}"
  if [[ -z "$WEB_E2E_SCOPE" ]]; then
    if [[ "${CI:-0}" == "1" || "${GITHUB_ACTIONS:-0}" == "true" ]]; then
      WEB_E2E_SCOPE="smoke"
    else
      WEB_E2E_SCOPE="full"
    fi
  fi
  if [[ "$WEB_E2E_SCOPE" == "smoke" ]]; then
    npm --prefix apps/web run e2e -- \
      --grep "visual snapshot: wiki route|visual snapshot: operations route" \
      --workers=1 \
      --max-failures=1 >/dev/null
  else
    npm --prefix apps/web run e2e >/dev/null
  fi
fi

echo "[4/6] Shell script syntax"
bash -n scripts/m1_smoke_e2e.sh
bash -n scripts/apply_migrations.sh
bash -n scripts/run_selfhost_core_acceptance.sh
bash -n scripts/run_selfhost_backup_restore_drill.sh
bash -n scripts/run_selfhost_dr_ci_acceptance.sh
bash -n scripts/run_oss_rc_dress_rehearsal.sh
bash -n scripts/run_contributor_guardrails.sh

echo "[4.1/6] Release version alignment"
python3 scripts/check_release_versions.py >/dev/null

echo "[4.2/6] Publish hygiene consistency"
python3 scripts/check_publish_hygiene.py >/dev/null

echo "[4.3/6] SDK API reference freshness"
python3 scripts/generate_sdk_api_reference.py --check >/dev/null

echo "[4.4/6] Repository hygiene"
python3 scripts/check_repo_hygiene.py >/dev/null

echo "[4.5/6] OpenClaw docs canonical references"
python3 scripts/check_openclaw_docs_canonical.py >/dev/null

echo "[4.51/6] Framework quickstart parity"
python3 scripts/check_framework_quickstart_parity.py >/dev/null

echo "[4.55/6] Self-hosted stack defaults and docs consistency"
python3 scripts/check_selfhost_stack_defaults.py >/dev/null

echo "[4.57/6] Agentic onboarding benchmark guardrails"
python3 scripts/benchmark_agentic_onboarding.py \
  --scenario all \
  --summary-only \
  --min-balanced-useful-rate 0.40 \
  --max-balanced-first-approved-minutes 40 \
  --min-balanced-published-new 4 >/dev/null

echo "[4.58/6] Positioning consistency (Agentic Wiki + L2)"
python3 scripts/check_positioning_consistency.py >/dev/null

echo "[4.6/6] Release error-budget policy gate"
python3 scripts/check_release_error_budget.py \
  --history-jsonl eval/reliability_error_budget_sample.jsonl \
  --window-days 0 \
  --min-samples 4 \
  --max-failure-rate 0.2 \
  --max-consecutive-failures 2 >/dev/null

echo "[4.7/6] Reliability drill profiles"
python3 scripts/run_reliability_drills.py \
  --snapshot-json eval/operational_slo_snapshot_sample.json \
  --max-steady-ingest-p95-ms 1200 \
  --max-steady-moderation-p90-minutes 720 \
  --burst-latency-multiplier 1.35 \
  --max-burst-ingest-p95-ms 1700 \
  --max-burst-moderation-open-backlog 60 \
  --degraded-ingest-events-max 0 \
  --degraded-ingest-p99-min-ms 3000 >/dev/null

echo "[4.8/6] Lifecycle telemetry integration smoke (optional)"
if [[ "${SYNAPSE_RUN_DB_INTEGRATION:-0}" == "1" ]]; then
  python3 scripts/integration_lifecycle_telemetry.py --request-timeout 10 >/dev/null
else
  echo "lifecycle telemetry integration skipped (SYNAPSE_RUN_DB_INTEGRATION=0)"
fi

echo "[5/6] Python monitor/openclaw smoke (offline)"
SYNAPSE_CI_VENV="${SYNAPSE_CI_VENV:-/tmp/synapse-ci-venv}"
rm -rf "$SYNAPSE_CI_VENV"
python3 -m venv "$SYNAPSE_CI_VENV"
source "$SYNAPSE_CI_VENV/bin/activate"
if ! python -m pip --version >/dev/null 2>&1; then
  python -m ensurepip --upgrade >/dev/null 2>&1 || true
fi
python -m pip install -q --upgrade pip
python -m pip install -q requests mcp
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python - <<'PY'
import os
from synapse_sdk import (
    BootstrapMemoryOptions,
    EvidenceRef,
    ExtractedInsight,
    InsightContext,
    MCPContextHelper,
    OpenTelemetryBridge,
    Synapse,
    SynthesisContext,
    Task,
    TaskComment,
    TaskLink,
    list_context_policy_profiles,
)
from synapse_sdk.types import Claim, MemoryBackfillRecord, SynapseConfig
from synapse_sdk.integrations.openclaw import OpenClawConnector

class MemoryTransport:
    def __init__(self):
        self.events = []
        self.claims = []
        self.backfills = []
        self.requests = []
        self.tasks = {}
        self.task_events = {}
        self.task_links = {}
    def send_events(self, events, *, idempotency_key=None):
        self.events.extend(events)
    def propose_fact(self, claim, *, idempotency_key=None):
        self.claims.append((claim, idempotency_key))
    def ingest_memory_backfill(self, batch_payload, *, idempotency_key=None):
        self.backfills.append((batch_payload, idempotency_key))
    def request_json(self, path, *, method="GET", payload=None, params=None, idempotency_key=None):
        params = params or {}
        payload = payload or {}
        self.requests.append(
            {
                "path": str(path),
                "method": str(method).upper(),
                "payload": dict(payload),
                "params": dict(params),
            }
        )
        project_id = params.get("project_id") or payload.get("project_id") or "p"
        if path == "/v1/tasks" and method == "POST":
            task_id = payload.get("task_id") or "task-1"
            task = {
                "id": str(task_id),
                "project_id": str(project_id),
                "title": str(payload.get("title", "")),
                "description": payload.get("description"),
                "status": str(payload.get("status", "todo")),
                "priority": str(payload.get("priority", "normal")),
                "source": str(payload.get("source", "human")),
                "assignee": payload.get("assignee"),
                "entity_key": payload.get("entity_key"),
                "category": payload.get("category"),
                "due_at": payload.get("due_at"),
                "created_by": payload.get("created_by"),
                "updated_by": payload.get("updated_by") or payload.get("created_by"),
                "metadata": payload.get("metadata") or {},
                "created_at": "2026-04-02T00:00:00Z",
                "updated_at": "2026-04-02T00:00:00Z",
            }
            self.tasks[str(task_id)] = task
            self.task_events.setdefault(str(task_id), []).append({"event_type": "created", "payload": {"task": task}})
            return {"status": "created", "task": task}
        if path == "/v1/tasks" and method == "GET":
            return {"tasks": list(self.tasks.values())}
        if path.startswith("/v1/tasks/") and method == "GET":
            task_id = path.split("/")[3]
            task = self.tasks.get(task_id)
            return {
                "task": task,
                "events": self.task_events.get(task_id, []),
                "links": self.task_links.get(task_id, []),
            }
        if path.startswith("/v1/tasks/") and path.endswith("/status") and method == "POST":
            task_id = path.split("/")[3]
            task = self.tasks[task_id]
            task["status"] = str(payload.get("status", task["status"]))
            task["updated_by"] = payload.get("updated_by")
            self.task_events.setdefault(task_id, []).append({"event_type": "status_changed", "payload": payload})
            return {"status": "ok", "changed": True, "task": task}
        if path.startswith("/v1/tasks/") and path.endswith("/comments") and method == "POST":
            task_id = path.split("/")[3]
            self.task_events.setdefault(task_id, []).append({"event_type": "comment", "payload": payload})
            return {"status": "ok", "event_id": "evt-1"}
        if path.startswith("/v1/tasks/") and path.endswith("/links") and method == "POST":
            task_id = path.split("/")[3]
            link = {
                "id": "lnk-1",
                "task_id": task_id,
                "project_id": project_id,
                "link_type": payload.get("link_type"),
                "link_ref": payload.get("link_ref"),
                "note": payload.get("note"),
                "metadata": payload.get("metadata") or {},
                "created_by": payload.get("created_by"),
                "created_at": "2026-04-02T00:00:00Z",
            }
            self.task_links.setdefault(task_id, []).append(link)
            self.task_events.setdefault(task_id, []).append({"event_type": "link_added", "payload": payload})
            return {"status": "ok", "link": link}
        if path == "/v1/mcp/retrieval/explain" and method == "GET":
            query = str(params.get("q") or "").strip()
            return {
                "results": [
                    {
                        "statement_text": f"retrieved:{query}",
                        "page": {"slug": "bc-omega", "entity_key": params.get("related_entity_key") or "bc_omega"},
                    }
                ],
                "revision": "r-ci",
            }
        return {}

class Runner:
    def run(self, x):
        return {"ok": x + 1}

class RuntimeMemory:
    def export_all(self):
        return [
            {
                "source_id": "mem-1",
                "content": "Warehouse #2 ramp is broken.",
                "entity_key": "warehouse_2",
                "category": "logistics",
            },
            "BC Omega now requires a physical key-card after 10:00.",
        ]

class Runtime:
    def __init__(self):
        self.handlers = {}
        self.tools = {}
        self.memory = RuntimeMemory()
        self.event_log = [
            {
                "event_name": "tool:result",
                "payload": {
                    "result": "Driver reported gate-card requirement for BC Omega.",
                    "entity_key": "bc_omega",
                    "category": "access",
                    "source_id": "evt-1",
                },
            },
            {
                "event_name": "message:received",
                "payload": {
                    "message": "Customer asked to leave package at gatehouse.",
                    "entity_key": "cust-1",
                    "category": "delivery_notes",
                    "source_id": "evt-2",
                },
            },
        ]
    def on(self, event_name, handler):
        self.handlers[event_name] = handler
    def register_tool(self, name, handler, description=None):
        self.tools[name] = (handler, description)

transport = MemoryTransport()
client = Synapse(SynapseConfig(api_url='http://localhost:8080', project_id='p'), transport=transport)
client.set_debug_mode(True, max_records=500)

os.environ["SYNAPSE_API_URL"] = "http://localhost:8080"
os.environ["SYNAPSE_PROJECT_ID"] = "p_env"
from_env_client = Synapse.from_env(transport=transport)
assert from_env_client.project_id == "p_env"

monitored = client.monitor(Runner(), integration='generic', include_methods=['run'])
out = monitored.run(1)
assert out['ok'] == 2

attached_runner = client.attach(
    Runner(),
    integration="generic",
    bootstrap_memory=BootstrapMemoryOptions(
        records=[
            "Attach bootstrap: yard entry moved from courtyard to archway.",
            {
                "source_id": "attach-dialog-2",
                "content": "BC Omega requires physical key-card after 10:00.",
                "entity_key": "bc_omega",
                "category": "access",
            },
        ],
        source_system="ci_attach_bootstrap",
        chunk_size=1,
    ),
)
attached_out = attached_runner.run(2)
assert attached_out["ok"] == 3

connector = OpenClawConnector(client, search_knowledge=lambda query, limit, filters: [{"query": query}])
runtime = Runtime()
attached_runtime = client.attach(
    runtime,
    integration="openclaw",
    openclaw_bootstrap_preset="hybrid",
    openclaw_bootstrap_max_records=10,
    openclaw_bootstrap_chunk_size=2,
    openclaw_register_tools=False,
)
assert attached_runtime is runtime
connector.attach(runtime, hook_events=['tool:result'])
runtime.handlers['tool:result']({'sessionKey': 's-1', 'result': 'ok'})
runtime.tools['synapse_search_wiki'][0]('foo', limit=1)
runtime.tools['synapse_propose_to_wiki'][0](entity_key='u1', category='ops', claim_text='hello', source_id='src-1')

auto_runtime = Runtime()
client.attach(
    auto_runtime,
    integration="openclaw",
    openclaw_register_tools=True,
    openclaw_bootstrap_preset=None,
)
assert "synapse_search_wiki" in auto_runtime.tools, auto_runtime.tools.keys()
auto_search_rows = auto_runtime.tools["synapse_search_wiki"][0]("omega auto", limit=2, filters={"entity_key": "bc_omega"})
assert isinstance(auto_search_rows, list) and auto_search_rows, auto_search_rows
assert str(auto_search_rows[0].get("statement_text", "")).startswith("retrieved:"), auto_search_rows

mcp_calls = []
def fake_call_tool(name, arguments):
    mcp_calls.append((name, arguments))
    if name == "search_knowledge":
        return {"results": [{"statement_text": "Gate requires card", "page": {"slug": "bc-omega"}}], "revision": "r1"}
    if name == "get_entity_facts":
        return {"facts": [{"statement_text": "Card after 10:00"}], "revision": "r1"}
    if name == "get_recent_changes":
        return {"changes": [{"action": "approve", "created_at": "2026-03-31T10:00:00Z", "page": {"slug": "bc-omega"}}]}
    if name == "explain_conflicts":
        return {"conflicts": []}
    return {}

mcp_helper = MCPContextHelper(project_id="p", call_tool=fake_call_tool)
profiles = list_context_policy_profiles()
assert any(item.get("profile") == "strict_enforced" for item in profiles), profiles
strict_alias_rejected = False
try:
    mcp_helper.search_knowledge("omega strict alias", context_policy_profile="strict")
except ValueError:
    strict_alias_rejected = True
assert strict_alias_rejected, "expected strict alias to be rejected"
default_alias_rejected = False
try:
    mcp_helper.search_knowledge("omega default alias", context_policy_profile="default")
except ValueError:
    default_alias_rejected = True
assert default_alias_rejected, "expected default alias to be rejected"
ctx = mcp_helper.build_context(query="omega gate", entity_key="bc_omega", include_recent_changes=True)
assert len(ctx["search_results"]) == 1, ctx
assert len(ctx["entity_facts"]) == 1, ctx
assert len(ctx["recent_changes"]) == 1, ctx
assert int(ctx.get("policy_filtered_out", 0)) == 0, ctx
search_calls = [call for call in mcp_calls if call[0] == "search_knowledge"]
assert search_calls, mcp_calls
assert search_calls[0][1].get("context_policy_mode") == "enforced", search_calls
openclaw_cb = mcp_helper.make_openclaw_search_callback(default_filters={"entity_key": "bc_omega"})
cb_result = openclaw_cb(query="omega", limit=2, filters={"category": "access"})
assert isinstance(cb_result, list) and cb_result, cb_result
strict_cb = mcp_helper.make_openclaw_search_callback(
    default_filters={"entity_key": "bc_omega"},
    context_policy_profile="strict_enforced",
)
strict_result = strict_cb(query="omega strict", limit=1, filters={"category": "access"})
assert isinstance(strict_result, list), strict_result
strict_calls = [call for call in mcp_calls if call[0] == "search_knowledge" and call[1].get("query") == "omega strict"]
assert strict_calls, mcp_calls
assert strict_calls[0][1].get("context_policy_mode") == "enforced", strict_calls
assert float(strict_calls[0][1].get("min_retrieval_confidence")) == 0.6, strict_calls
assert any(call[0] == "search_knowledge" for call in mcp_calls), mcp_calls

class PriorityExtractor:
    name = "priority"
    def extract(self, context: InsightContext):
        text = str(context.result or "")
        if "priority" not in text.lower():
            return []
        return [ExtractedInsight(claim_text=text, category="operations", confidence=0.93)]

client.register_extractor(PriorityExtractor())

class ConfidenceFloorSynthesizer:
    name = "confidence_floor"
    contract_version = "v1"
    def synthesize(self, context: SynthesisContext):
        out = []
        for item in context.extracted_insights:
            confidence = item.confidence if item.confidence is not None else 0.0
            if confidence < 0.9:
                confidence = 0.9
            out.append(
                ExtractedInsight(
                    claim_text=item.claim_text,
                    category=item.category,
                    entity_key=item.entity_key,
                    confidence=confidence,
                    metadata=dict(item.metadata),
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                )
            )
        return out

client.register_synthesizer(ConfidenceFloorSynthesizer())

@client.collect_insight(category="delivery_rules")
def check_gate_access(building_id: str):
    return f"Priority rule: gate for {building_id} needs physical card"

check_gate_access("bc_omega")

batch_id = client.backfill_memory(
    [
        MemoryBackfillRecord(source_id='m1', content='Warehouse #1 closed for sanitation'),
        MemoryBackfillRecord(source_id='m2', content='BC Omega requires card access after 10:00', entity_key='bc_omega'),
    ],
    source_system='ci',
    chunk_size=1,
)
assert isinstance(batch_id, str) and batch_id
task_result = client.upsert_task(
    Task(title="Verify Omega gate policy", priority="high", entity_key="bc_omega"),
    created_by="ops_manager",
    task_id="task-1",
)
assert task_result["task"]["id"] == "task-1", task_result
listed_tasks = client.list_tasks(limit=10)
assert len(listed_tasks) >= 1, listed_tasks
task_detail = client.get_task("task-1")
assert task_detail.get("task", {}).get("title") == "Verify Omega gate policy", task_detail
client.update_task_status("task-1", status="in_progress", updated_by="ops_manager")
client.comment_task("task-1", created_by="ops_manager", comment=TaskComment(comment="driver confirmed"))
client.link_task("task-1", created_by="ops_manager", link=TaskLink(link_type="draft", link_ref="draft-123"))
task_detail = client.get_task("task-1")
assert task_detail.get("task", {}).get("status") == "in_progress", task_detail
assert len(task_detail.get("links", [])) >= 1, task_detail
client.bulk_review_wiki_drafts(
    reviewed_by="ops_reviewer",
    action="approve",
    dry_run=True,
    limit=12,
    filter={"category": "policy", "source_system": "postgres_sql"},
)
client.get_adoption_pipeline_visibility(
    days=7,
    source_systems=["postgres_sql"],
    namespaces=["ops"],
)
client.get_adoption_rejection_diagnostics(days=7, sample_limit=3)
client.enable_adoption_safe_mode(
    updated_by="ops_admin",
    dry_run=True,
    note="ci safe-mode dry-run",
)
client.run_adoption_project_reset(
    requested_by="ops_admin",
    scopes=["drafts", "wiki"],
    cascade_cleanup_orphan_draft_pages=True,
    dry_run=True,
)
client.execute_adoption_sync_preset(
    updated_by="ops_admin",
    dry_run=True,
    sync_processor_lookback_minutes=60,
    fail_on_sync_processor_unavailable=True,
    auto_apply_safe_mode_on_critical=False,
)
client.list_wiki_drafts(status="pending_review", limit=25)
client.get_adoption_sync_cursor_health(stale_after_hours=72)
client.flush()
assert len(transport.events) >= 3
assert len(transport.claims) >= 2
assert len(transport.backfills) >= 4
bulk_review_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/wiki/drafts/bulk-review" and req.get("method") == "POST"
    ),
    None,
)
list_drafts_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/wiki/drafts" and req.get("method") == "GET"
    ),
    None,
)
pipeline_visibility_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/pipeline/visibility" and req.get("method") == "GET"
    ),
    None,
)
rejection_diagnostics_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/rejections/diagnostics" and req.get("method") == "GET"
    ),
    None,
)
safe_mode_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/safe-mode/enable" and req.get("method") == "POST"
    ),
    None,
)
project_reset_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/project-reset" and req.get("method") == "POST"
    ),
    None,
)
cursor_health_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/sync/cursor-health" and req.get("method") == "GET"
    ),
    None,
)
sync_preset_call = next(
    (
        req
        for req in transport.requests
        if req.get("path") == "/v1/adoption/sync-presets/execute" and req.get("method") == "POST"
    ),
    None,
)
assert bulk_review_call is not None, transport.requests
assert list_drafts_call is not None, transport.requests
assert project_reset_call is not None, transport.requests
assert cursor_health_call is not None, transport.requests
assert pipeline_visibility_call is not None, transport.requests
assert rejection_diagnostics_call is not None, transport.requests
assert safe_mode_call is not None, transport.requests
assert sync_preset_call is not None, transport.requests
assert sync_preset_call.get("payload", {}).get("auto_apply_safe_mode_on_critical") is False, sync_preset_call
assert int(sync_preset_call.get("payload", {}).get("sync_processor_lookback_minutes") or 0) == 60, sync_preset_call
assert bool(sync_preset_call.get("payload", {}).get("fail_on_sync_processor_unavailable")) is True, sync_preset_call
event_trace_ids = [e.trace_id for e in transport.events if getattr(e, "trace_id", None)]
assert event_trace_ids, "missing trace ids in captured events"
debug_events = client.get_debug_records(limit=200)
debug_event_names = {item.get("event") for item in debug_events}
assert "collect_insight_proposed" in debug_event_names, f"missing collect_insight_proposed in debug log: {debug_event_names}"
assert "extractor_completed" in debug_event_names, f"missing extractor_completed in debug log: {debug_event_names}"
assert "synthesizer_completed" in debug_event_names, f"missing synthesizer_completed in debug log: {debug_event_names}"
assert "attach_bootstrap_completed" in debug_event_names, f"missing attach_bootstrap_completed in debug log: {debug_event_names}"
assert "attach_openclaw_bootstrap_preset_enabled" in debug_event_names, (
    f"missing attach_openclaw_bootstrap_preset_enabled in debug log: {debug_event_names}"
)
assert "attach_openclaw_search_auto_enabled" in debug_event_names, (
    f"missing attach_openclaw_search_auto_enabled in debug log: {debug_event_names}"
)
onboarding_metrics = client.get_onboarding_metrics(limit=200)
assert onboarding_metrics.get("attach_events_total", 0) >= 1, onboarding_metrics

class FailingTransport:
    def __init__(self):
        self.send_attempts = 0
    def send_events(self, events, *, idempotency_key=None):
        self.send_attempts += 1
        raise RuntimeError("down")
    def propose_fact(self, claim, *, idempotency_key=None):
        raise RuntimeError("down")
    def ingest_memory_backfill(self, batch_payload, *, idempotency_key=None):
        raise RuntimeError("down")

buffer_client = Synapse(
    SynapseConfig(api_url='http://localhost:8080', project_id='p', degradation_mode='buffer'),
    transport=FailingTransport(),
)
buffer_client.capture(event_type="system_signal", payload={"phase": "degradation_buffer"})
buffer_client.flush()
assert len(buffer_client._queue) == 1, f"expected buffered queue item, got {len(buffer_client._queue)}"
buffer_client.propose_fact(
    Claim(
        id="11111111-1111-1111-1111-111111111111",
        schema_version="v1",
        project_id="p",
        entity_key="entity",
        category="ops",
        claim_text="buffer mode claim",
        status="draft",
        evidence=[EvidenceRef(source_type="tool_output", source_id="src")],
    )
)
assert len(buffer_client._pending_claims) == 1, "expected pending claim in buffer mode"
buffer_client.backfill_memory([MemoryBackfillRecord(source_id="b1", content="buffer mode backfill")], chunk_size=1)
assert len(buffer_client._pending_backfill) == 1, "expected pending backfill in buffer mode"

drop_client = Synapse(
    SynapseConfig(api_url='http://localhost:8080', project_id='p', degradation_mode='drop'),
    transport=FailingTransport(),
)
drop_client.capture(event_type="system_signal", payload={"phase": "degradation_drop"})
drop_client.flush()
assert len(drop_client._queue) == 0, "drop mode should not keep failed event queue"
drop_client.propose_fact(
    Claim(
        id="22222222-2222-2222-2222-222222222222",
        schema_version="v1",
        project_id="p",
        entity_key="entity",
        category="ops",
        claim_text="drop mode claim",
        status="draft",
        evidence=[EvidenceRef(source_type="tool_output", source_id="src")],
    )
)
assert len(drop_client._pending_claims) == 0, "drop mode should not buffer claims"
drop_client.backfill_memory([MemoryBackfillRecord(source_id="d1", content="drop mode backfill")], chunk_size=1)
assert len(drop_client._pending_backfill) == 0, "drop mode should not buffer backfill"

sync_transport = MemoryTransport()
sync_client = Synapse(
    SynapseConfig(api_url='http://localhost:8080', project_id='p', degradation_mode='sync_flush'),
    transport=sync_transport,
)
sync_client.capture(event_type="system_signal", payload={"phase": "degradation_sync_flush"})
assert len(sync_transport.events) == 1, "sync_flush should flush immediately on capture"
assert len(sync_client._queue) == 0, "sync_flush should not leave queue items after successful send"

class DummyCounter:
    def __init__(self):
        self.total = 0
    def add(self, value, attributes=None):
        self.total += float(value)

class DummyHistogram:
    def __init__(self):
        self.values = []
    def record(self, value, attributes=None):
        self.values.append(float(value))

class DummySpan:
    def __init__(self, name):
        self.name = name
        self.ended = False
    def set_attribute(self, key, value):
        pass
    def add_event(self, name, attributes=None):
        pass
    def end(self):
        self.ended = True

class DummyTracer:
    def __init__(self):
        self.spans = []
    def start_span(self, name, attributes=None):
        span = DummySpan(name)
        self.spans.append(span)
        return span

class DummyMeter:
    def __init__(self):
        self.counters = {}
        self.histograms = {}
    def create_counter(self, name, description=None):
        counter = DummyCounter()
        self.counters[name] = counter
        return counter
    def create_histogram(self, name, description=None, unit=None):
        histogram = DummyHistogram()
        self.histograms[name] = histogram
        return histogram

otel_transport = MemoryTransport()
otel_client = Synapse(
    SynapseConfig(api_url='http://localhost:8080', project_id='p'),
    transport=otel_transport,
)
dummy_tracer = DummyTracer()
dummy_meter = DummyMeter()
otel_bridge = OpenTelemetryBridge(project_id=otel_client.project_id, tracer=dummy_tracer, meter=dummy_meter)
otel_client.set_telemetry_sink(otel_bridge)
otel_client.capture(event_type="system_signal", payload={"phase": "otel_mapping"})
otel_client.flush()
assert dummy_meter.counters["synapse.debug.events_total"].total >= 2, "otel bridge should receive debug events"
assert dummy_meter.histograms["synapse.flush.batch_size"].values, "otel bridge should record flush batch sizes"
assert any(span.ended for span in dummy_tracer.spans), "otel bridge should end mapped spans"
print('python smoke ok')
PY

echo "[5.05/6] Framework adapter contracts (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python3 scripts/check_framework_adapter_contracts.py >/dev/null

echo "[5.06/6] Framework native bindings contracts (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python3 scripts/check_framework_native_bindings.py >/dev/null

echo "[5.1/6] OpenClaw x MCP e2e (offline stdio)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python3 scripts/integration_openclaw_mcp_runtime.py --check

echo "[5.15/6] OpenClaw runtime contract matrix (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python3 scripts/integration_openclaw_runtime_contract.py --check

echo "[5.16/6] OpenClaw provenance verification smoke (offline)"
python3 scripts/smoke_openclaw_provenance_verification.py >/dev/null
echo "openclaw provenance verification smoke ok"

echo "[5.2/6] synapse-cli smoke (offline)"
CLI_EXTRACT_OUT=/tmp/synapse-cli-extract.json
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python -m synapse_sdk.cli extract \
  --text "BC Omega gate requires access card policy update" \
  --category access_policy \
  --entity-key bc_omega \
  --as-claims \
  --pretty > "$CLI_EXTRACT_OUT"
python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-cli-extract.json").read_text())
assert payload["counts"]["filtered"] >= 1, payload
assert payload["claims"], payload
print("synapse-cli extract smoke ok")
PY

cat > /tmp/synapse-cli-replay.jsonl <<'JSONL'
{"ts":"2026-03-31T10:00:00Z","event":"collect_insight_started","trace_id":"trace_cli_1","span_id":"span_1","details":{"function":"demo"}}
{"ts":"2026-03-31T10:00:01Z","event":"collect_insight_completed","trace_id":"trace_cli_1","span_id":"span_1","details":{"proposed_count":1}}
JSONL
CLI_REPLAY_OUT=/tmp/synapse-cli-replay-out.json
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python -m synapse_sdk.cli replay \
  --input /tmp/synapse-cli-replay.jsonl \
  --trace-id trace_cli_1 \
  --json > "$CLI_REPLAY_OUT"
python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-cli-replay-out.json").read_text())
assert payload["trace_id"] == "trace_cli_1", payload
assert payload["records_output"] == 2, payload
assert payload["timeline"][0]["event"] == "collect_insight_started", payload
print("synapse-cli replay smoke ok")
PY

CLI_DOCTOR_OUT=/tmp/synapse-cli-doctor.json
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python - <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import socket
import subprocess
import threading
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health":
            self._send({"status": "ok"})
            return
        if path == "/v1/tasks":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"tasks": []})
            return
        if path == "/v1/wiki/drafts":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"drafts": [], "total": 0})
            return
        if path == "/v1/mcp/retrieval/explain":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"results": [], "explainability": {"context_policy": {"mode": "advisory"}}})
            return
        self._send({"detail": "not_found"}, status=404)

    def log_message(self, fmt, *args):  # noqa: A003
        return

    def _send(self, payload, *, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


port = free_port()
server = HTTPServer(("127.0.0.1", port), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    cmd = [
        "python",
        "-m",
        "synapse_sdk.cli",
        "doctor",
        "--api-url",
        f"http://127.0.0.1:{port}",
        "--project-id",
        "omega_demo",
        "--strict",
        "--json",
    ]
    out = subprocess.check_output(cmd, text=True)
    payload = json.loads(out)
    assert payload["summary"]["failed"] == 0, payload
    assert payload["summary"]["ok"] >= 4, payload
    Path("/tmp/synapse-cli-doctor.json").write_text(json.dumps(payload), encoding="utf-8")
    print("synapse-cli doctor smoke ok")
finally:
    server.shutdown()
    server.server_close()
PY

PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python - <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlparse


class ShadowRetrievalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/v1/mcp/retrieval/explain":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"not_found"}')
            return
        q = ""
        params = parse_qs(parsed.query)
        if "q" in params and params["q"]:
            q = str(params["q"][0]).lower()
        if "omega" in q:
            statement = "BC Omega gate requires card"
        elif "warehouse" in q:
            statement = "Warehouse #1 is closed after 19:00"
        else:
            statement = "No signal"
        body = json.dumps({"results": [{"statement_text": statement}], "revision": "ci-shadow"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

with tempfile.TemporaryDirectory(prefix="synapse-cli-init-") as tmp:
    out = subprocess.check_output(
        [
            "python",
            "-m",
            "synapse_sdk.cli",
            "init",
            "--dir",
            tmp,
            "--project-id",
            "Omega Demo 2026",
            "--api-url",
            "http://localhost:8080",
            "--json",
        ],
        text=True,
    )
    payload = json.loads(out)
    assert payload["status"] == "ok", payload
    env_path = Path(payload["env_path"])
    assert env_path.exists(), payload
    content = env_path.read_text(encoding="utf-8")
    assert "SYNAPSE_PROJECT_ID=omega_demo_2026" in content, content
    assert "SYNAPSE_API_URL=http://localhost:8080" in content, content
    assert payload["quickstart_commands"], payload
    connect_out = subprocess.check_output(
        [
            "python",
            "-m",
            "synapse_sdk.cli",
            "connect",
            "openclaw",
            "--dir",
            tmp,
            "--env-file",
            ".env.synapse",
            "--runtime-var",
            "runtime",
            "--json",
        ],
        text=True,
    )
    connect_payload = json.loads(connect_out)
    assert connect_payload["status"] == "ok", connect_payload
    assert connect_payload["target"] == "openclaw", connect_payload
    snippet = str(connect_payload.get("snippet") or "")
    assert "synapse.attach(" in snippet, snippet
    assert "default_context_policy_profile" in snippet, snippet
    assert "adoption_mode=" in snippet, snippet
    assert "runtime," in snippet, snippet
    sample_path = Path(tmp) / "memory_export.jsonl"
    sample_path.write_text(
        "\n".join(
            [
                json.dumps({"source_id": "m1", "content": "BC Omega gate requires card", "entity_key": "bc_omega", "category": "access"}),
                json.dumps({"source_id": "m2", "content": "Warehouse #1 is closed after 19:00", "entity_key": "warehouse_1", "category": "operations"}),
            ]
        ),
        encoding="utf-8",
    )
    adopt_out = subprocess.check_output(
        [
            "python",
            "-m",
            "synapse_sdk.cli",
            "adopt",
            "--dir",
            tmp,
            "--env-file",
            ".env.synapse",
            "--sample-file",
            str(sample_path),
            "--adoption-mode",
            "observe_only",
            "--json",
        ],
        text=True,
    )
    adopt_payload = json.loads(adopt_out)
    assert adopt_payload["status"] == "ok", adopt_payload
    assert adopt_payload["target"] == "existing_memory_adoption", adopt_payload
    assert adopt_payload["adoption_mode"] == "observe_only", adopt_payload
    assert isinstance(adopt_payload.get("rollout_plan"), list) and adopt_payload["rollout_plan"], adopt_payload
    adopt_snippet = str(adopt_payload.get("snippet") or "")
    assert 'adoption_mode="observe_only"' in adopt_snippet, adopt_snippet
    shadow_server = HTTPServer(("127.0.0.1", 0), ShadowRetrievalHandler)
    shadow_thread = threading.Thread(target=shadow_server.serve_forever, daemon=True)
    shadow_thread.start()
    shadow_api_url = f"http://127.0.0.1:{shadow_server.server_port}"
    try:
        shadow_out = subprocess.check_output(
            [
                "python",
                "-m",
                "synapse_sdk.cli",
                "adopt",
                "--dir",
                tmp,
                "--env-file",
                ".env.synapse",
                "--sample-file",
                str(sample_path),
                "--api-url",
                shadow_api_url,
                "--shadow-retrieval-check",
                "--shadow-query",
                "bc omega gate card",
                "--json",
            ],
            text=True,
        )
        shadow_payload = json.loads(shadow_out)
        shadow_report = shadow_payload.get("shadow_retrieval_report")
        assert isinstance(shadow_report, dict), shadow_payload
        summary = shadow_report.get("summary")
        assert isinstance(summary, dict), shadow_report
        assert summary.get("queries_ok", 0) >= 1, summary
        assert summary.get("status") in {"ok", "partial"}, summary
    finally:
        shadow_server.shutdown()
        shadow_server.server_close()
print("synapse-cli connect openclaw smoke ok")
print("synapse-cli adopt smoke ok")
print("synapse-cli init smoke ok")
PY

echo "[5.25/6] synapse-cli verify core-loop smoke (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python - <<'PY'
import json
from pathlib import Path
import subprocess
import tempfile

STUB_SCRIPT = """#!/usr/bin/env python3
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--api-url")
parser.add_argument("--database-url")
parser.add_argument("--project-id")
parser.add_argument("--request-timeout", type=float, default=8.0)
parser.add_argument("--worker-mode")
parser.add_argument("--max-worker-cycles", type=int, default=5)
parser.add_argument("--worker-poll-interval", type=float, default=1.0)
parser.add_argument("--mcp-probe-mode")
parser.add_argument("--mcp-container-name")
parser.add_argument("--mcp-host")
parser.add_argument("--mcp-port", type=int)
args = parser.parse_args()

print(
    json.dumps(
        {
            "status": "ok",
            "project_id": args.project_id or "omega_demo",
            "batch_id": "batch_stub",
            "approved_draft_id": "draft_stub",
            "page_slug": "space/ops/bc-omega",
            "worker_mode": args.worker_mode or "local",
            "mcp_probe_mode": args.mcp_probe_mode or "local",
        }
    )
)
"""

with tempfile.TemporaryDirectory(prefix="synapse-cli-verify-core-loop-") as tmp:
    script_path = Path(tmp) / "integration_core_loop_stub.py"
    script_path.write_text(STUB_SCRIPT, encoding="utf-8")
    out = subprocess.check_output(
        [
            "python",
            "-m",
            "synapse_sdk.cli",
            "verify",
            "core-loop",
            "--script",
            str(script_path),
            "--project-id",
            "omega_demo",
            "--json",
        ],
        text=True,
    )
    payload = json.loads(out)
    assert payload["status"] == "ok", payload
    result = payload.get("result") or {}
    assert result.get("status") == "ok", payload
    assert result.get("project_id") == "omega_demo", payload
    assert payload.get("return_code") == 0, payload
    print("synapse-cli verify core-loop smoke ok")
PY

echo "[5.26/6] synapse-cli quickstart smoke (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python - <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health":
            self._send({"status": "ok"})
            return
        if path == "/v1/tasks":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"tasks": []})
            return
        if path == "/v1/wiki/drafts":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"drafts": [], "total": 0})
            return
        if path == "/v1/mcp/retrieval/explain":
            if not query.get("project_id"):
                self._send({"detail": "missing_project_id"}, status=422)
                return
            self._send({"results": [], "explainability": {"context_policy": {"mode": "advisory"}}})
            return
        self._send({"detail": "not_found"}, status=404)

    def log_message(self, fmt, *args):  # noqa: A003
        return

    def _send(self, payload, *, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


stub_script = """#!/usr/bin/env python3
import argparse
import json
parser = argparse.ArgumentParser()
parser.add_argument("--project-id")
parser.add_argument("--worker-mode")
parser.add_argument("--mcp-probe-mode")
parser.add_argument("--request-timeout")
parser.add_argument("--max-worker-cycles")
parser.add_argument("--worker-poll-interval")
parser.add_argument("--api-url")
parser.add_argument("--database-url")
parser.add_argument("--mcp-container-name")
parser.add_argument("--mcp-host")
parser.add_argument("--mcp-port")
args = parser.parse_args()
print(json.dumps({"status":"ok","project_id": args.project_id or "omega_demo","approved_draft_id":"draft_qs","page_slug":"space/ops/quickstart"}))
"""

port = free_port()
server = HTTPServer(("127.0.0.1", port), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    with tempfile.TemporaryDirectory(prefix="synapse-cli-quickstart-") as tmp:
        stub_path = Path(tmp) / "integration_core_loop_stub.py"
        stub_path.write_text(stub_script, encoding="utf-8")
        out = subprocess.check_output(
            [
                "python",
                "-m",
                "synapse_sdk.cli",
                "quickstart",
                "--dir",
                tmp,
                "--env-file",
                ".env.synapse",
                "--project-id",
                "omega_demo",
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--doctor-strict",
                "--verify-core-loop",
                "--verify-script",
                str(stub_path),
                "--json",
            ],
            text=True,
        )
        payload = json.loads(out)
        assert payload["status"] == "ok", payload
        summary = payload.get("summary") or {}
        assert summary.get("steps_total") == 4, payload
        assert summary.get("steps_failed") == 0, payload
        steps = payload.get("steps") or []
        names = [item.get("name") for item in steps if isinstance(item, dict)]
        assert names == ["init", "doctor", "connect_openclaw", "verify_core_loop"], payload
        print("synapse-cli quickstart smoke ok")
finally:
    server.shutdown()
    server.server_close()
PY

echo "[5.27/6] synapse-cli adoption ops smoke (offline)"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python scripts/check_synapse_cli_adoption_ops.py >/dev/null

echo "[5.45/6] Cookbook snapshot stability"
PYTHONPATH="$ROOT_DIR/packages/synapse-sdk-py/src" python scripts/check_cookbook_snapshots.py >/dev/null

deactivate

echo "[5.5/6] Worker deterministic logic smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from app.wiki_engine import WikiSynthesisEngine

engine = WikiSynthesisEngine()
payload = {
    "id": "11111111-1111-1111-1111-111111111111",
    "project_id": "p",
    "entity_key": "omega_gate",
    "category": "access",
    "claim_text": "Entry is card-only after 10:00",
    "evidence": [{"source_id": "dialog-1"}],
}
summary = engine.debug_explain_claim(payload)
assert "omega_gate" in summary
assert "fingerprint" in summary
print("worker smoke ok")
PY

echo "[5.6/6] Legacy import parser smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from pathlib import Path
import tempfile

from app.legacy_import import LegacyImporter, LegacySeedOrchestrator

with tempfile.TemporaryDirectory(prefix="synapse-legacy-import-") as tmp:
    root = Path(tmp)
    (root / "warehouse_notes.md").write_text(
        "Warehouse #1 is closed for sanitation.\n\nUse backup loading zone.",
        encoding="utf-8",
    )
    (root / "support.csv").write_text(
        "ticket_id,priority,summary\n1,high,Refund requested after delivery delay\n",
        encoding="utf-8",
    )
    (root / "rules.json").write_text(
        '{"access": {"omega_gate": "card only after 10:00"}}',
        encoding="utf-8",
    )
    importer = LegacyImporter(root_dir=root)
    result = importer.collect_records()
    assert len(result.records) >= 3, result
    categories = {item.get("category") for item in result.records}
    assert "warehouse_policy" in categories or "support_policy" in categories or "access_policy" in categories, categories
    seeded = LegacySeedOrchestrator().apply(
        records=result.records,
        source_type="local_dir",
        source_ref=str(root),
        project_id="omega_demo",
    )
    assert seeded.summary.get("seed_records") == len(seeded.records), seeded.summary
    assert seeded.summary.get("seed_pages", 0) >= 1, seeded.summary
    first = seeded.records[0]
    metadata = first.get("metadata") or {}
    assert isinstance(metadata.get("synapse_seed_plan"), dict), first
    assert isinstance(metadata.get("synapse_source_provenance"), dict), first
    assert metadata["synapse_seed_plan"].get("page_slug"), first
print("legacy import smoke ok")
PY

echo "[5.65/6] Notion legacy import smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from app.legacy_import import NotionImporter


class FakeNotionClient:
    def __init__(self):
        self.pages = {
            "rootpage": {
                "id": "rootpage",
                "url": "https://notion.so/rootpage",
                "last_edited_time": "2026-03-31T10:00:00.000Z",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Warehouse Ops"}]},
                    "Status": {"type": "select", "select": {"name": "Active"}},
                },
            },
            "childpage": {
                "id": "childpage",
                "url": "https://notion.so/childpage",
                "last_edited_time": "2026-03-31T11:00:00.000Z",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "BC Omega Access"}]},
                },
            },
            "dbpage1": {
                "id": "dbpage1",
                "url": "https://notion.so/dbpage1",
                "last_edited_time": "2026-03-31T12:00:00.000Z",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Driver Playbook"}]},
                    "Priority": {"type": "select", "select": {"name": "High"}},
                },
            },
        }
        self.blocks = {
            "rootpage": [
                {
                    "id": "b-root-1",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "Warehouse #1 closes at 20:00."}]},
                },
                {
                    "id": "childpage",
                    "type": "child_page",
                    "has_children": False,
                    "child_page": {"title": "BC Omega Access"},
                },
            ],
            "childpage": [
                {
                    "id": "b-child-1",
                    "type": "to_do",
                    "has_children": False,
                    "to_do": {
                        "checked": True,
                        "rich_text": [{"plain_text": "Gate requires physical card after 10:00"}],
                    },
                }
            ],
            "dbpage1": [
                {
                    "id": "b-db-1",
                    "type": "bulleted_list_item",
                    "has_children": False,
                    "bulleted_list_item": {"rich_text": [{"plain_text": "Driver Petrov skips calls after 17:00"}]},
                }
            ],
        }

    def get_page(self, page_id):
        return self.pages[page_id]

    def get_block_children(self, block_id):
        return self.blocks.get(block_id, [])

    def query_database(self, database_id, *, max_items=None):
        rows = [self.pages["dbpage1"]]
        if max_items is None:
            return rows
        return rows[:max_items]


client = FakeNotionClient()
importer = NotionImporter(client=client, max_pages=20)
root_result = importer.collect_from_root_page("rootpage")
assert len(root_result.records) >= 3, root_result
assert any(item["metadata"].get("source_connector") == "notion" for item in root_result.records), root_result.records
assert any(item["metadata"].get("notion_page_id") == "childpage" for item in root_result.records), root_result.records

db_result = importer.collect_from_database("db123")
assert len(db_result.records) >= 1, db_result
assert any("Driver Playbook" in item["metadata"].get("notion_title", "") for item in db_result.records), db_result.records
print("notion legacy import smoke ok")
PY

echo "[5.675/6] SQL legacy import mapping smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from app.legacy_import import SQLImporter

importer = SQLImporter(
    dsn="postgresql://example.invalid/db",
    query="SELECT id, note, updated_at FROM ops_kb_items WHERE updated_at > %(cursor)s",
    mapping={
        "source_id_field": "id",
        "content_field": "note",
        "entity_key_field": "driver_id",
        "category_field": "category",
        "observed_at_field": "updated_at",
        "metadata_fields": ["session_id"],
        "metadata_static": {"source": "ops_kb_items"},
    },
    source_id_prefix="hw",
)
row = {
    "id": 42,
    "note": "Gate for BC Omega is card-only after 10:00",
    "driver_id": "petrov",
    "category": "access_policy",
    "updated_at": "2026-04-03T12:00:00Z",
    "session_id": "s-1",
    "metadata": {"team": "ops"},
}
record = importer._map_row_to_record(row=row, row_index=1)
assert record is not None, "record should be produced for valid row"
assert record["source_id"] == "hw:42", record
assert "card-only" in record["content"], record
assert record["entity_key"] == "petrov", record
assert record["category"] == "access_policy", record
assert record["observed_at"] == "2026-04-03T12:00:00Z", record
assert record["metadata"]["team"] == "ops", record
assert record["metadata"]["source"] == "ops_kb_items", record
assert importer._extract_cursor_value(row=row, explicit_cursor_column="updated_at") == "2026-04-03T12:00:00Z"
print("sql legacy import mapping smoke ok")
PY

echo "[5.68/6] Legacy sync orchestration smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from hashlib import sha256

from app.legacy_import import LegacySeedOrchestrator
from app.legacy_sync import LegacySyncEngine

records = [
    {"source_id": "a", "content": "BC Omega gate requires card after 10:00", "metadata": {}},
    {"source_id": "b", "content": "Warehouse #1 closed for sanitation", "metadata": {}},
    {"source_id": "c", "content": "Warehouse #1 closed for sanitation", "metadata": {}},
]
known = {sha256("BC Omega gate requires card after 10:00".encode("utf-8")).hexdigest()}
delta = LegacySyncEngine.compute_record_delta(records, known)
assert delta["new_count"] == 1, delta
assert delta["duplicates_known"] == 1, delta
assert delta["duplicates_run"] == 1, delta
assert len(delta["all_fingerprints"]) == 2, delta
seeded = LegacySeedOrchestrator().apply(
    records=list(delta["new_records"]),
    source_type="local_dir",
    source_ref="/tmp/legacy",
    project_id="omega_demo",
    source_id="source-1",
    run_id="run-1",
    config={"seed_group_mode": "entity"},
)
assert len(seeded.records) == 1, seeded
first = seeded.records[0]
metadata = first.get("metadata") or {}
assert metadata.get("synapse_source_provenance", {}).get("run_id") == "run-1", first
assert metadata.get("synapse_seed_plan", {}).get("group_mode") == "entity", first
print("legacy sync smoke ok")
PY

echo "[5.685/6] Legacy seed regression evaluator"
PYTHONPATH="$ROOT_DIR/services/worker" python3 scripts/eval_legacy_seed_regression.py --summary-only
PYTHONPATH="$ROOT_DIR/services/worker" python3 scripts/check_legacy_sync_wal_connector.py

PYTHONPATH="$ROOT_DIR/services/worker" python3 services/worker/scripts/run_legacy_sync_scheduler.py --help >/dev/null
PYTHONPATH="$ROOT_DIR/services/worker" python3 services/worker/scripts/run_queue_incident_sync_scheduler.py --help >/dev/null

echo "[5.69/6] MCP runtime cache invalidation smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/mcp" python3 - <<'PY'
from app.runtime import SynapseKnowledgeRuntime


class FakeStore:
    def __init__(self):
        self.revision = "snapshot:r1"
        self.search_calls = 0
        self.fact_calls = 0
        self.change_calls = 0
        self.conflict_calls = 0

    def get_project_revision(self, project_id: str) -> str:
        return self.revision

    def search_knowledge(self, *, project_id: str, query: str, limit: int, entity_key, category, page_type, related_entity_key):
        self.search_calls += 1
        return [{"query": query, "limit": limit, "page_type": page_type, "related_entity_key": related_entity_key}]

    def get_entity_facts(self, *, project_id: str, entity_key: str, limit: int, category, include_non_current):
        self.fact_calls += 1
        return [{"entity_key": entity_key, "limit": limit, "include_non_current": include_non_current}]

    def get_recent_changes(self, *, project_id: str, limit: int, since_hours: int):
        self.change_calls += 1
        return [{"limit": limit, "since_hours": since_hours}]

    def explain_conflicts(self, *, project_id: str, limit: int, resolution_status, entity_key):
        self.conflict_calls += 1
        return [{"resolution_status": resolution_status, "entity_key": entity_key}]


store = FakeStore()
runtime = SynapseKnowledgeRuntime(store, cache_ttl_seconds=30, max_cache_entries=100)

first = runtime.search_knowledge(project_id="omega_demo", query="gate card", limit=5)
assert first["cached"] is False
assert store.search_calls == 1

second = runtime.search_knowledge(project_id="omega_demo", query="gate card", limit=5)
assert second["cached"] is True
assert store.search_calls == 1

store.revision = "snapshot:r2"
third = runtime.search_knowledge(project_id="omega_demo", query="gate card", limit=5)
assert third["cached"] is False, "cache should invalidate when revision changes"
assert store.search_calls == 2

facts_1 = runtime.get_entity_facts(project_id="omega_demo", entity_key="bc_omega", limit=10)
facts_2 = runtime.get_entity_facts(project_id="omega_demo", entity_key="bc_omega", limit=10)
assert facts_1["cached"] is False and facts_2["cached"] is True
assert store.fact_calls == 1

changes_1 = runtime.get_recent_changes(project_id="omega_demo", limit=10, since_hours=24)
changes_2 = runtime.get_recent_changes(project_id="omega_demo", limit=10, since_hours=24)
assert changes_1["cached"] is False and changes_2["cached"] is True
assert store.change_calls == 1

conflicts_1 = runtime.explain_conflicts(project_id="omega_demo", resolution_status="open", entity_key="bc_omega")
conflicts_2 = runtime.explain_conflicts(project_id="omega_demo", resolution_status="open", entity_key="bc_omega")
assert conflicts_1["cached"] is False and conflicts_2["cached"] is True
assert store.conflict_calls == 1

print("mcp runtime smoke ok")
PY
PYTHONPATH="$ROOT_DIR/services:$ROOT_DIR/services/api:$ROOT_DIR/services/mcp" \
  python3 scripts/check_mcp_api_retrieval_parity.py
PYTHONPATH="$ROOT_DIR/services/mcp" python3 services/mcp/scripts/run_mcp_server.py --help >/dev/null

echo "[5.7/6] Agent simulator logic smoke (offline)"
PYTHONPATH="$ROOT_DIR/services/worker" python3 - <<'PY'
from datetime import UTC, datetime

from app.simulator import AgentSimulatorEngine, SessionSnapshot

engine = AgentSimulatorEngine()
policies = [
    {
        "policy_id": "omega_gate_card_only",
        "entity_key": "bc_omega",
        "category": "access",
        "old_statement": "Gate is open for all deliveries.",
        "new_statement": "Gate is card-only after 10:00.",
    }
]
sessions = [
    SessionSnapshot.from_text(
        session_id="sess-1",
        text="driver at bc_omega gate entered without card; manual override used after 10:00",
        when=datetime(2026, 3, 31, 9, 0, tzinfo=UTC),
        event_count=6,
    ),
    SessionSnapshot.from_text(
        session_id="sess-2",
        text="Customer asked for new delivery window tomorrow.",
        when=datetime(2026, 3, 31, 9, 5, tzinfo=UTC),
        event_count=3,
    ),
]
result = engine.simulate_from_snapshots(policy_changes=policies, sessions=sessions, relevance_floor=0.1)
assert result["sessions_scanned"] == 2, result
assert result["findings_total"] >= 1, result
assert result["severity_counts"]["high"] + result["severity_counts"]["critical"] >= 1, result
assert result["top_findings"][0]["policy_id"] == "omega_gate_card_only", result
print("agent simulator smoke ok")
PY
PYTHONPATH="$ROOT_DIR/services/worker" python3 services/worker/scripts/run_agent_simulator_scheduler.py --help >/dev/null

echo "[5.72/6] Agent simulator scheduler template smoke (offline)"
SCHED_PREVIEW=/tmp/synapse-simulator-scheduler-preview.json
PYTHONPATH="$ROOT_DIR/services/worker" python3 services/worker/scripts/run_agent_simulator_scheduler.py \
  --dry-run \
  --schedules-json '{
    "schedules": [
      {
        "project_id": "omega_demo",
        "template_id": "gate_access_card_only",
        "template_params": {"entity_key": "bc_omega", "location_name": "BC Omega"},
        "preset": "daily"
      },
      {
        "project_id": "omega_demo",
        "template_id": "warehouse_quarantine",
        "template_params": {"entity_key": "warehouse_9", "warehouse_name": "Warehouse 9", "until_date": "2026-04-05"},
        "preset": "weekly"
      }
    ]
  }' > "$SCHED_PREVIEW"
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-simulator-scheduler-preview.json").read_text())
assert payload["status"] == "preview", payload
assert payload["queued_count"] == 2, payload
assert all(item["status"] == "would_queue" for item in payload["queued"]), payload
print("agent simulator scheduler smoke ok")
PY

echo "[5.75/6] Synthesis regression evaluator"
PYTHONPATH="$ROOT_DIR/services/worker" python3 scripts/eval_synthesis_regression.py --dataset eval/synthesis_cases.json --summary-only

echo "[5.85/6] Gatekeeper regression evaluator"
PYTHONPATH="$ROOT_DIR/services/worker" python3 scripts/eval_gatekeeper_regression.py --dataset eval/gatekeeper_cases.json --summary-only

echo "[5.88/6] MCP retrieval regression evaluator"
PYTHONPATH="$ROOT_DIR/services/mcp" python3 scripts/eval_mcp_retrieval_regression.py --dataset eval/mcp_retrieval_cases.json --summary-only
PYTHONPATH="$ROOT_DIR/services/mcp" python3 scripts/benchmark_mcp_retrieval.py --help >/dev/null
python3 scripts/check_mcp_retrieval_trend.py \
  --latest-benchmark eval/mcp_benchmark_latest_sample.json \
  --history-file eval/mcp_benchmark_history_sample.jsonl \
  --baseline-window 2 \
  --min-baseline-runs 2 > /tmp/synapse-mcp-trend-smoke.json
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-mcp-trend-smoke.json").read_text())
assert payload["status"] == "ok", payload
recommendation = payload.get("recommended_context_policy_profile")
assert isinstance(recommendation, dict), payload
assert recommendation.get("profile") in {"advisory", "enforced", "strict_enforced", "off"}, recommendation
thresholds = recommendation.get("thresholds")
assert isinstance(thresholds, dict), recommendation
assert "context_policy_mode" in thresholds, recommendation
print("mcp trend context-policy recommendation smoke ok")
PY
python3 scripts/check_core_slo_guardrails.py \
  --benchmark-json eval/mcp_benchmark_latest_sample.json \
  --max-average-p95-ms 120 \
  --max-case-p95-ms 150 \
  --min-top1-accuracy 0.95 \
  --min-cases 2 >/tmp/synapse-core-slo-smoke.json
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-core-slo-smoke.json").read_text())
assert payload["status"] == "ok", payload
assert payload["benchmark"]["average_case_p95_ms"] is not None, payload
assert payload["benchmark"]["average_top1_accuracy"] is not None, payload
print("core slo guardrails smoke ok")
PY
python3 scripts/check_operational_slo_guardrails.py \
  --snapshot-json eval/operational_slo_snapshot_sample.json \
  --max-ingest-p95-ms 400 \
  --max-ingest-p99-ms 600 \
  --min-ingest-events 50 \
  --max-moderation-p90-minutes 180 \
  --max-moderation-open-backlog 20 \
  --max-moderation-blocked-conflicts 6 >/tmp/synapse-operational-slo-smoke.json
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-operational-slo-smoke.json").read_text())
assert payload["status"] == "ok", payload
assert payload["snapshot"]["ingest"]["p95_ms"] is not None, payload
assert payload["snapshot"]["moderation"]["p90_minutes"] is not None, payload
print("operational slo guardrails smoke ok")
PY
python3 scripts/run_performance_tuning_advisor.py --help >/dev/null
python3 scripts/verify_openclaw_provenance.py --help >/dev/null
./scripts/run_oss_rc_dress_rehearsal.sh --help >/dev/null
./scripts/run_contributor_guardrails.sh --help >/dev/null
./scripts/run_selfhost_dr_ci_acceptance.sh --help >/dev/null

echo "[5.885/6] Operations route runbook parity"
python3 scripts/check_operations_runbook_parity.py --path docs/operations-route-runbook.md

echo "[5.89/6] Queue governance policy assertions"
python3 scripts/check_queue_governance_policy.py \
  --window-hours 24 \
  --project-limit 100 \
  --max-critical-without-alert-target 0 \
  --max-congestion-without-owner 0 \
  --max-unreviewed-pauses 0

echo "[5.9/6] Gatekeeper calibration smoke"
CAL_OUT=/tmp/synapse-gatekeeper-calibration.json
PYTHONPATH="$ROOT_DIR/services/worker" python3 scripts/calibrate_gatekeeper_llm_thresholds.py \
  --dataset eval/gatekeeper_cases.json \
  --holdout-ratio 0.3 \
  --weights 0.35,0.5 \
  --confidences 0.65,0.7 \
  --score-thresholds 0.72 \
  --top-k 2 \
  --force-llm-assist > "$CAL_OUT"
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-gatekeeper-calibration.json").read_text())
assert payload["status"] == "ok", payload
assert payload["grid"]["evaluated"] >= 1, payload
best = payload["best_candidate"]
assert "config" in best and "holdout_metrics" in best, best
assert "recommended_gatekeeper_config_payload" in payload, payload
print("gatekeeper calibration smoke ok")
PY
python3 scripts/build_gatekeeper_holdout_from_db.py --help >/dev/null
python3 scripts/apply_gatekeeper_calibration.py --help >/dev/null
python3 scripts/run_gatekeeper_calibration_cycle.py --help >/dev/null
python3 scripts/run_gatekeeper_calibration_scheduler.py --help >/dev/null
python3 scripts/monitor_gatekeeper_drift.py --help >/dev/null
PYTHONPATH="$ROOT_DIR/services/worker" python3 services/worker/scripts/run_gatekeeper_calibration_operation_queue.py --help >/dev/null
CAL_SCHED_PREVIEW=/tmp/synapse-gatekeeper-calibration-scheduler-preview.json
python3 scripts/run_gatekeeper_calibration_scheduler.py \
  --dry-run \
  --skip-due-check \
  --schedules-json '{"schedules":[{"project_id":"omega_demo","preset":"nightly"},{"project_id":"beta_demo","preset":"weekly","interval_hours":120}]}' \
  > "$CAL_SCHED_PREVIEW"
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/synapse-gatekeeper-calibration-scheduler-preview.json").read_text())
assert payload["status"] == "preview", payload
assert payload["total_schedules"] == 2, payload
assert payload["results"][0]["status"] == "would_run", payload
print("gatekeeper calibration scheduler smoke ok")
PY

echo "[5.95/6] Core loop acceptance (opt-in)"
if [[ "${SYNAPSE_RUN_CORE_ACCEPTANCE:-0}" == "1" ]]; then
  ./scripts/integration_core_loop.py
else
  echo "core loop acceptance skipped (set SYNAPSE_RUN_CORE_ACCEPTANCE=1 to run)"
fi

echo "[5.96/6] Self-hosted clean compose acceptance (opt-in)"
if [[ "${SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE:-0}" == "1" ]]; then
  ./scripts/run_selfhost_core_acceptance.sh
else
  echo "self-hosted acceptance skipped (set SYNAPSE_RUN_SELFHOST_CORE_ACCEPTANCE=1 to run)"
fi

echo "[5.965/6] Self-hosted DR drill acceptance (opt-in)"
if [[ "${SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE:-0}" == "1" ]]; then
  ./scripts/run_selfhost_dr_ci_acceptance.sh
else
  echo "self-hosted DR acceptance skipped (set SYNAPSE_RUN_SELFHOST_DR_ACCEPTANCE=1 to run)"
fi

echo "[5.967/6] Self-hosted chaos drill acceptance (opt-in)"
if [[ "${SYNAPSE_RUN_SELFHOST_CHAOS_DRILL:-0}" == "1" ]]; then
  ./scripts/run_selfhost_chaos_drill.sh
else
  echo "self-hosted chaos drill skipped (set SYNAPSE_RUN_SELFHOST_CHAOS_DRILL=1 to run)"
fi

echo "[5.97/6] Self-hosted backup/restore drill script smoke"
./scripts/run_selfhost_backup_restore_drill.sh --help >/dev/null
./scripts/run_selfhost_chaos_drill.sh --help >/dev/null
./scripts/integration_legacy_sync_queue_processing.py --help >/dev/null

echo "[6/6] Cleanup artifacts"
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -name '*.pyc' -delete

echo "CI checks passed"
