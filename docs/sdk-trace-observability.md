# SDK Trace Observability (OTel -> Grafana/Datadog)

Last updated: 2026-04-02

This guide provides a complete path from Synapse SDK telemetry to ready dashboards.

## What is included

1. Local observability stack:
   - OpenTelemetry Collector
   - Prometheus
   - Tempo
   - Grafana (preprovisioned Synapse dashboard)
2. Datadog dashboard quick pack JSON.
3. Baseline alert packs (Prometheus rules + Datadog monitor payloads).
4. Telemetry smoke generator (`scripts/run_sdk_otel_smoke.py`) for immediate data flow validation.

## 1. Launch observability stack

```bash
cd /Users/maksimborisov/synapse
docker compose -f infra/observability/docker-compose.sdk-observability.yml up -d
```

References:
- stack runbook: `/Users/maksimborisov/synapse/infra/observability/README.md`
- collector config: `/Users/maksimborisov/synapse/infra/observability/otel-collector.yaml`

## 2. Wire SDK OpenTelemetry bridge

Python:

```python
from synapse_sdk import Synapse, SynapseConfig, build_opentelemetry_bridge
from opentelemetry import metrics, trace

synapse = Synapse(
    SynapseConfig(api_url="http://localhost:8080", project_id="water_delivery_logistics")
)
bridge = build_opentelemetry_bridge(
    project_id=synapse.project_id,
    tracer=trace.get_tracer("synapse-sdk"),
    meter=metrics.get_meter("synapse-sdk"),
    service_name="dispatch-agent",
)
synapse.set_telemetry_sink(bridge)
```

TypeScript:

```ts
import { Synapse, createOpenTelemetryBridge } from "@synapseworkspace/sdk";
import { metrics, trace } from "@opentelemetry/api";

const synapse = new Synapse({
  apiUrl: "http://localhost:8080",
  projectId: "water_delivery_logistics"
});

const bridge = createOpenTelemetryBridge({
  projectId: synapse.projectId,
  tracer: trace.getTracer("synapse-sdk"),
  meter: metrics.getMeter("synapse-sdk"),
  serviceName: "dispatch-agent"
});

synapse.setTelemetrySink(bridge.sink());
```

## 3. Emit sample telemetry

```bash
python3 -m venv /tmp/synapse-otel-venv
source /tmp/synapse-otel-venv/bin/activate
pip install requests opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/scripts/run_sdk_otel_smoke.py
```

This script emits:
- debug lifecycle event metrics;
- transport failure counters;
- proposal counters;
- operation spans for monitor/extractor/synthesizer/flush flows.

## 4. Use Grafana dashboard

Open `http://localhost:3300` (or your `SYNAPSE_GRAFANA_PORT`) and navigate to:

- Folder `Synapse`
- Dashboard `Synapse SDK Trace Observability`

The dashboard is provisioned from:

- `/Users/maksimborisov/synapse/infra/observability/grafana/dashboards/synapse-sdk-trace-overview.json`

## 5. Use Datadog quick pack

Dashboard payload:

- `/Users/maksimborisov/synapse/infra/observability/datadog/synapse-sdk-trace-quickpack.json`

Import example:

```bash
curl -sS -X POST "https://api.datadoghq.com/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  -H "Content-Type: application/json" \
  --data @/Users/maksimborisov/synapse/infra/observability/datadog/synapse-sdk-trace-quickpack.json
```

## 6. Enable baseline alerts

Prometheus rules (auto-mounted in local stack):

- `/Users/maksimborisov/synapse/infra/observability/prometheus-rules-sdk-alerts.yaml`

Datadog monitor quick pack:

- `/Users/maksimborisov/synapse/infra/observability/datadog/synapse-sdk-alert-monitors.json`

Bulk import Datadog monitors:

```bash
jq -c '.monitors[]' /Users/maksimborisov/synapse/infra/observability/datadog/synapse-sdk-alert-monitors.json | \
while read -r monitor; do
  curl -sS -X POST "https://api.datadoghq.com/api/v1/monitor" \
    -H "DD-API-KEY: $DD_API_KEY" \
    -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
    -H "Content-Type: application/json" \
    --data "$monitor"
done
```

Alert baseline covers:
- transport failure ratio;
- queue growth pressure;
- proposal drop under active traffic.

## 7. Validate signal names

Default metric names produced by SDK OpenTelemetry bridge:

- `synapse.debug.events_total`
- `synapse.knowledge.proposals_total`
- `synapse.transport.failures_total`
- `synapse.flush.batch_size` (histogram)
- `synapse.queue.size` (histogram)

Prometheus-normalized names in this stack:

- `synapse_debug_events_total`
- `synapse_knowledge_proposals_total`
- `synapse_transport_failures_total`
- `synapse_flush_batch_size_events_bucket|sum|count`
- `synapse_queue_size_events_bucket|sum|count`

Key tags/attributes:

- `synapse.project_id`
- `synapse.integration`
- `synapse.event`
- `synapse.trace_id`
- `synapse.span_id`
