#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import os
import time
from typing import Any
from uuid import uuid4

from synapse_sdk import Claim, EvidenceRef, Synapse, SynapseConfig, build_opentelemetry_bridge


class MemoryTransport:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.claims: list[Any] = []

    def send_events(self, events: list[Any], *, idempotency_key: str | None = None) -> None:
        self.events.extend(events)

    def propose_fact(self, claim: Any, *, idempotency_key: str | None = None) -> None:
        self.claims.append(claim)

    def ingest_memory_backfill(self, batch_payload: dict[str, Any], *, idempotency_key: str | None = None) -> None:
        return None


def _load_otel_sdk() -> dict[str, Any]:
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ModuleNotFoundError as exc:
        missing = str(exc).split("'")[1] if "'" in str(exc) else "opentelemetry dependency"
        raise RuntimeError(
            "Missing OpenTelemetry dependency: "
            f"{missing}. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http"
        ) from exc

    return {
        "metrics": metrics,
        "trace": trace,
        "OTLPMetricExporter": OTLPMetricExporter,
        "OTLPSpanExporter": OTLPSpanExporter,
        "MeterProvider": MeterProvider,
        "PeriodicExportingMetricReader": PeriodicExportingMetricReader,
        "Resource": Resource,
        "TracerProvider": TracerProvider,
        "BatchSpanProcessor": BatchSpanProcessor,
    }


def _configure_otel(*, endpoint: str, service_name: str) -> tuple[Any, Any]:
    otel = _load_otel_sdk()
    metrics = otel["metrics"]
    trace = otel["trace"]
    Resource = otel["Resource"]
    TracerProvider = otel["TracerProvider"]
    BatchSpanProcessor = otel["BatchSpanProcessor"]
    OTLPSpanExporter = otel["OTLPSpanExporter"]
    MeterProvider = otel["MeterProvider"]
    PeriodicExportingMetricReader = otel["PeriodicExportingMetricReader"]
    OTLPMetricExporter = otel["OTLPMetricExporter"]

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "synapse",
            "deployment.environment": os.getenv("SYNAPSE_ENV", "local"),
        }
    )

    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", timeout=5)
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter, schedule_delay_millis=250))
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(service_name)

    metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", timeout=5)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=1000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(service_name)

    return tracer, meter


def _normalize_endpoint(raw: str) -> str:
    value = raw.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        return f"http://{value}"
    return value


def run_smoke() -> dict[str, Any]:
    endpoint = _normalize_endpoint(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"))
    service_name = os.getenv("SYNAPSE_OTEL_SERVICE_NAME", "synapse-sdk-smoke")
    project_id = os.getenv("SYNAPSE_OTEL_PROJECT_ID", "sdk_observability_demo")

    tracer, meter = _configure_otel(endpoint=endpoint, service_name=service_name)
    bridge = build_opentelemetry_bridge(
        project_id=project_id,
        tracer=tracer,
        meter=meter,
        service_name=service_name,
    )

    transport = MemoryTransport()
    synapse = Synapse(
        SynapseConfig(
            api_url="http://localhost:8080",
            project_id=project_id,
        ),
        transport=transport,
    )
    synapse.set_telemetry_sink(bridge)
    synapse.set_debug_mode(True)

    class RoutingAgent:
        def evaluate_order(self, order_id: str, notes: str) -> dict[str, str]:
            return {
                "order_id": order_id,
                "insight": notes,
            }

    monitored = synapse.monitor(
        RoutingAgent(),
        integration="openclaw",
        include_methods=["evaluate_order"],
        capture_arguments=True,
        capture_results=True,
    )

    @synapse.collect_insight(
        category="access_policy",
        entity_key="bc_omega",
        min_confidence=0.05,
        integration="openclaw",
        source_type="tool_output",
        flush_after_propose=False,
    )
    def extract_gate_policy() -> str:
        return "Gate policy update: BC Omega is card-only after 10:00."

    for idx in range(8):
        monitored.evaluate_order(
            f"order-{idx}",
            "Gate policy update: BC Omega is card-only after 10:00.",
        )
        extract_gate_policy()
        synapse.capture(
            event_type="tool_result",
            payload={
                "integration": "openclaw",
                "phase": "smoke_probe",
                "iteration": idx,
            },
            agent_id="agent_dispatch",
            session_id="smoke-session-1",
            tags=["integration:openclaw", "smoke"],
        )

    manual_claim = Claim(
        id=str(uuid4()),
        schema_version="v1",
        project_id=project_id,
        entity_key="warehouse_1",
        category="warehouse_status",
        claim_text="Warehouse #1 is closed for sanitation until 2026-04-05.",
        status="draft",
        confidence=0.88,
        metadata={"source": "sdk_otel_smoke"},
        evidence=[
            EvidenceRef(
                source_type="external_event",
                source_id="smoke-seed-warehouse-1",
                observed_at=datetime.now(UTC).isoformat(),
            )
        ],
    )
    synapse.propose_fact(manual_claim)

    synapse.flush()
    time.sleep(2.2)

    shutdown_error: str | None = None
    try:
        from opentelemetry import metrics, trace

        trace_provider = trace.get_tracer_provider()
        if hasattr(trace_provider, "force_flush"):
            trace_provider.force_flush()
        if hasattr(trace_provider, "shutdown"):
            trace_provider.shutdown()

        meter_provider = metrics.get_meter_provider()
        if hasattr(meter_provider, "force_flush"):
            meter_provider.force_flush()
        if hasattr(meter_provider, "shutdown"):
            meter_provider.shutdown()
    except Exception as exc:  # pragma: no cover - best effort shutdown
        shutdown_error = f"{type(exc).__name__}: {exc}"

    return {
        "otel_endpoint": endpoint,
        "project_id": project_id,
        "service_name": service_name,
        "captured_events": len(transport.events),
        "proposed_claims": len(transport.claims),
        "debug_records": len(synapse.get_debug_records(limit=5000)),
        "shutdown_error": shutdown_error,
    }


def main() -> int:
    try:
        summary = run_smoke()
    except RuntimeError as exc:
        print(f"[run_sdk_otel_smoke] {exc}")
        return 2
    except Exception as exc:
        print(f"[run_sdk_otel_smoke] unexpected failure: {type(exc).__name__}: {exc}")
        return 1

    print("[run_sdk_otel_smoke] completed")
    for key, value in summary.items():
        print(f"  - {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
