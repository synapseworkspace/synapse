from __future__ import annotations

from typing import Any


class OpenTelemetryBridge:
    """Maps Synapse debug records into OpenTelemetry-style spans and metrics."""

    def __init__(
        self,
        *,
        project_id: str,
        tracer: Any | None = None,
        meter: Any | None = None,
        service_name: str = "synapse-sdk",
    ) -> None:
        self._project_id = project_id
        self._service_name = service_name
        self._tracer = tracer
        self._meter = meter
        self._active_spans: dict[str, Any] = {}

        self._events_total = _create_counter(meter, "synapse.debug.events_total", "Total Synapse debug events")
        self._proposals_total = _create_counter(
            meter, "synapse.knowledge.proposals_total", "Total knowledge proposals emitted by SDK"
        )
        self._transport_failures_total = _create_counter(
            meter, "synapse.transport.failures_total", "Total transport failures observed by SDK"
        )
        self._flush_batch_size = _create_histogram(
            meter, "synapse.flush.batch_size", "Observed flush batch size", unit="events"
        )
        self._queue_size = _create_histogram(
            meter, "synapse.queue.size", "Observed in-memory queue sizes", unit="events"
        )

    def __call__(self, record: dict[str, Any]) -> None:
        try:
            self._handle_record(record)
        except Exception:
            return

    def _handle_record(self, record: dict[str, Any]) -> None:
        event = str(record.get("event") or "")
        details = record.get("details") if isinstance(record.get("details"), dict) else {}
        attrs = self._build_attributes(record, event, details)

        _counter_add(self._events_total, 1, attrs)

        if event in {"propose_fact_sent", "collect_insight_proposed"}:
            _counter_add(self._proposals_total, 1, attrs)

        if "failed" in event or event.endswith("_dropped") or event.endswith("_requeued"):
            _counter_add(self._transport_failures_total, 1, attrs)

        if isinstance(details.get("batch_size"), (int, float)):
            _histogram_record(self._flush_batch_size, float(details["batch_size"]), attrs)
        if isinstance(details.get("queue_size"), (int, float)):
            _histogram_record(self._queue_size, float(details["queue_size"]), attrs)

        self._map_span(record, event, attrs, details)

    def _build_attributes(self, record: dict[str, Any], event: str, details: dict[str, Any]) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "synapse.project_id": self._project_id,
            "synapse.service_name": self._service_name,
            "synapse.event": event,
        }
        trace_id = record.get("trace_id")
        span_id = record.get("span_id")
        parent_span_id = record.get("parent_span_id")
        if trace_id:
            attrs["synapse.trace_id"] = str(trace_id)
        if span_id:
            attrs["synapse.span_id"] = str(span_id)
        if parent_span_id:
            attrs["synapse.parent_span_id"] = str(parent_span_id)

        integration = details.get("integration")
        if isinstance(integration, str) and integration:
            attrs["synapse.integration"] = integration

        for key in ("agent_id", "session_id", "function", "extractor", "synthesizer"):
            raw = details.get(key)
            if isinstance(raw, str) and raw:
                attrs[f"synapse.{key}"] = raw
        return attrs

    def _map_span(self, record: dict[str, Any], event: str, attrs: dict[str, Any], details: dict[str, Any]) -> None:
        if self._tracer is None:
            return
        operation = _operation_from_event(event)
        if not operation:
            return
        span_key = _span_key(record, operation)
        is_start = event.endswith("_started") or event.endswith("_start")
        is_end = (
            event.endswith("_completed")
            or event.endswith("_success")
            or event.endswith("_failed")
            or event.endswith("_dropped")
            or event.endswith("_requeued")
        )

        if is_start:
            span = _start_span(self._tracer, f"synapse.{operation}", attrs)
            if span is not None:
                self._active_spans[span_key] = span
            return

        if not is_end:
            return

        span = self._active_spans.pop(span_key, None)
        if span is None:
            span = _start_span(self._tracer, f"synapse.{operation}", attrs)
            if span is None:
                return
        _span_add_event(span, event, attrs)
        if "error_message" in details:
            _span_set_attribute(span, "synapse.error_message", str(details["error_message"]))
        _span_set_attribute(span, "synapse.status", "error" if "failed" in event or "dropped" in event else "ok")
        _span_end(span)


def build_opentelemetry_bridge(
    *,
    project_id: str,
    tracer: Any | None = None,
    meter: Any | None = None,
    service_name: str = "synapse-sdk",
) -> OpenTelemetryBridge:
    return OpenTelemetryBridge(project_id=project_id, tracer=tracer, meter=meter, service_name=service_name)


def _operation_from_event(event: str) -> str | None:
    for suffix in ("_started", "_completed", "_success", "_failed", "_dropped", "_requeued"):
        if event.endswith(suffix) and len(event) > len(suffix):
            return event[: -len(suffix)]
    if event.endswith("_start") and len(event) > len("_start"):
        return event[: -len("_start")]
    return None


def _span_key(record: dict[str, Any], operation: str) -> str:
    trace_id = str(record.get("trace_id") or "no-trace")
    span_id = str(record.get("span_id") or "no-span")
    return f"{trace_id}:{span_id}:{operation}"


def _create_counter(meter: Any | None, name: str, description: str) -> Any | None:
    if meter is None or not hasattr(meter, "create_counter"):
        return None
    factory = meter.create_counter
    try:
        return factory(name, description=description)
    except TypeError:
        return factory(name)


def _create_histogram(meter: Any | None, name: str, description: str, *, unit: str) -> Any | None:
    if meter is None or not hasattr(meter, "create_histogram"):
        return None
    factory = meter.create_histogram
    try:
        return factory(name, description=description, unit=unit)
    except TypeError:
        try:
            return factory(name, description=description)
        except TypeError:
            return factory(name)


def _counter_add(counter: Any | None, amount: float, attributes: dict[str, Any]) -> None:
    if counter is None:
        return
    try:
        counter.add(amount, attributes=attributes)
    except TypeError:
        counter.add(amount, attributes)


def _histogram_record(histogram: Any | None, value: float, attributes: dict[str, Any]) -> None:
    if histogram is None:
        return
    try:
        histogram.record(value, attributes=attributes)
    except TypeError:
        histogram.record(value, attributes)


def _start_span(tracer: Any, name: str, attributes: dict[str, Any]) -> Any | None:
    if tracer is None or not hasattr(tracer, "start_span"):
        return None
    try:
        return tracer.start_span(name, attributes=attributes)
    except TypeError:
        span = tracer.start_span(name)
        for key, value in attributes.items():
            _span_set_attribute(span, key, value)
        return span


def _span_add_event(span: Any, name: str, attributes: dict[str, Any]) -> None:
    if not hasattr(span, "add_event"):
        return
    try:
        span.add_event(name, attributes=attributes)
    except TypeError:
        span.add_event(name)


def _span_set_attribute(span: Any, key: str, value: Any) -> None:
    if hasattr(span, "set_attribute"):
        span.set_attribute(key, value)


def _span_end(span: Any) -> None:
    if hasattr(span, "end"):
        span.end()
