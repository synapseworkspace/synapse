# Synapse SDK Observability Starter Pack

This folder provides a production-like quick pack for SDK trace/metrics observability:

- OpenTelemetry Collector (`otlp` ingest at `:4317`/`:4318`)
- Prometheus (`:9090`)
- Tempo (`:3200`)
- Grafana (`:3300` by default) with preprovisioned Synapse SDK dashboard
- Datadog dashboard JSON quick pack for one-click import
- Prometheus alert rules quick pack (transport failures, queue growth, proposal drop)
- Datadog monitor quick pack for baseline SDK SLO alerts

## 1. Start Local Observability Stack

From repository root:

```bash
docker compose -f infra/observability/docker-compose.sdk-observability.yml up -d
```

Service endpoints:

- Grafana: `http://localhost:3300` (`admin` / `admin` by default, override with `SYNAPSE_GRAFANA_PORT`)
- Prometheus: `http://localhost:9090`
- OTLP HTTP ingest: `http://localhost:4318`
- OTLP gRPC ingest: `localhost:4317`

## 2. Emit Real Synapse SDK Telemetry

Run smoke generator (Python):

```bash
python3 -m venv /tmp/synapse-otel-venv
source /tmp/synapse-otel-venv/bin/activate
pip install requests opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
PYTHONPATH=/Users/maksimborisov/synapse/packages/synapse-sdk-py/src \
python3 /Users/maksimborisov/synapse/scripts/run_sdk_otel_smoke.py
```

The script sends SDK bridge metrics/spans to `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4318`).

## 3. Open Prebuilt Grafana Dashboard

Dashboard is auto-provisioned under folder `Synapse`:

- `Synapse SDK Trace Observability`

It includes:

- SDK debug events throughput by event class
- Knowledge proposals throughput
- Transport failure throughput + ratio
- p50/p95 flush batch size
- p50/p95 in-memory queue size

## 4. Import Datadog Quick Pack

Dashboard JSON:

- `infra/observability/datadog/synapse-sdk-trace-quickpack.json`

Import via Datadog API:

```bash
curl -sS -X POST "https://api.datadoghq.com/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  -H "Content-Type: application/json" \
  --data @infra/observability/datadog/synapse-sdk-trace-quickpack.json
```

## 5. Baseline Alert Packs

Prometheus rule file (auto-loaded by local stack):

- `infra/observability/prometheus-rules-sdk-alerts.yaml`

Datadog monitor quick pack:

- `infra/observability/datadog/synapse-sdk-alert-monitors.json`

Import Datadog monitors:

```bash
jq -c '.monitors[]' infra/observability/datadog/synapse-sdk-alert-monitors.json | \
while read -r monitor; do
  curl -sS -X POST "https://api.datadoghq.com/api/v1/monitor" \
    -H "DD-API-KEY: $DD_API_KEY" \
    -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
    -H "Content-Type: application/json" \
    --data "$monitor"
done
```

Included baseline alerts:

- `transport failure ratio`: elevated send failure ratio under active SDK traffic.
- `queue growth`: queue pressure growth vs prior window.
- `proposal drop`: no proposals under sustained event traffic.

## 6. Stop Stack

```bash
docker compose -f infra/observability/docker-compose.sdk-observability.yml down
```
