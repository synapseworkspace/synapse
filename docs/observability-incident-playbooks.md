# Synapse Observability Incident Playbooks

Last updated: 2026-04-02

Operational playbooks for baseline SDK alerts.

## Alert 1: Transport Failure Ratio Spike

Signal:
- `SynapseSDKTransportFailureRatioWarning`
- `SynapseSDKTransportFailureRatioCritical`

Immediate actions (0-15 min):
1. Confirm API/MCP availability and network path health.
2. Check recent deploys affecting transport, auth, gateway, DNS.
3. Inspect SDK degradation mode in affected services.

Containment:
1. If outage is external, set SDK mode to `buffer` for critical agents.
2. If memory pressure risk is high, set temporary backpressure and scoped `drop` for low-priority agents.

Resolution:
1. Restore upstream availability (API/gateway/secrets).
2. Drain buffered queue and monitor failure ratio normalization.

Exit criteria:
1. Failure ratio < 2% for 30 minutes.
2. Queue depth returns to project baseline.

## Alert 2: Queue Growth Detected

Signal:
- `SynapseSDKQueueGrowthDetected`

Immediate actions (0-20 min):
1. Verify worker throughput and synthesis cycle latency.
2. Check DB latency/lock contention and queue pause windows.
3. Identify affected projects and traffic anomalies.

Containment:
1. Pause non-critical ingestion projects temporarily.
2. Increase worker cycles/concurrency within DB safety limits.

Resolution:
1. Clear blocking bottleneck (DB, worker crash loop, heavy migration).
2. Resume paused projects in batches.

Exit criteria:
1. Queue growth ratio falls below 1.2 for 30 minutes.
2. Draft SLA breaches stop increasing.

## Alert 3: Proposal Drop Under Active Traffic

Signal:
- `SynapseSDKProposalDropDetected`

Immediate actions (0-20 min):
1. Confirm event ingest still active (`synapse_debug_events_total`).
2. Check extractor/synthesizer pipeline state.
3. Inspect gatekeeper thresholds and conflict saturation.

Containment:
1. Temporarily relax gatekeeper thresholds for stuck projects.
2. Run manual synthesis cycle to validate end-to-end path.

Resolution:
1. Fix extractor/plugin regression or normalization bug.
2. Reprocess affected windows if data quality is intact.

Exit criteria:
1. Proposal throughput returns to historical baseline.
2. Draft generation and moderation queue trends normalize.

## Standard Incident Template

1. Incident ID + start time.
2. Detection signal and impacted projects.
3. Hypothesis + validated root cause.
4. Mitigation timeline.
5. Follow-up actions with owners and deadlines.
