from __future__ import annotations

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from app.intelligence import INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY


@dataclass(slots=True)
class DigestRecord:
    id: UUID
    project_id: str
    digest_kind: str
    digest_date: str
    headline: str
    summary_markdown: str
    payload: dict[str, Any]


@dataclass(slots=True)
class DeliveryTarget:
    id: UUID
    project_id: str
    channel: str
    target: str
    enabled: bool
    config: dict[str, Any]


_ESCALATION_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
_ESCALATION_WEEKDAY_TO_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
_ESCALATION_OWNER_FIELD_DEFAULTS = {
    "critical": "escalation_channel",
    "warning": "oncall_channel",
    "info": "oncall_channel",
}


class IntelligenceDeliveryEngine:
    """Delivers ready intelligence digests to configured channels."""

    def dispatch_ready(
        self,
        conn,
        *,
        project_ids: list[str] | None = None,
        digest_kind: str = "daily",
        limit: int = 100,
    ) -> dict[str, Any]:
        digests = self._list_ready_digests(conn, project_ids=project_ids, digest_kind=digest_kind, limit=limit)
        summary = {
            "picked": len(digests),
            "digests_sent": 0,
            "digests_failed": 0,
            "attempts_sent": 0,
            "attempts_failed": 0,
            "attempts_skipped": 0,
            "results": [],
        }
        for digest in digests:
            result = self.dispatch_digest(conn, digest_id=digest.id)
            summary["digests_sent"] += 1 if result["digest_status"] == "sent" else 0
            summary["digests_failed"] += 1 if result["digest_status"] == "failed" else 0
            summary["attempts_sent"] += int(result["attempts_sent"])
            summary["attempts_failed"] += int(result["attempts_failed"])
            summary["attempts_skipped"] += int(result["attempts_skipped"])
            summary["results"].append(result)
        return summary

    def dispatch_digest(self, conn, *, digest_id: UUID) -> dict[str, Any]:
        digest = self._load_digest(conn, digest_id=digest_id)
        if digest is None:
            return {"digest_id": str(digest_id), "digest_status": "missing", "attempts_sent": 0, "attempts_failed": 0, "attempts_skipped": 0}

        targets = self._list_targets(conn, project_id=digest.project_id)
        attempts_sent = 0
        attempts_failed = 0
        attempts_skipped = 0

        if not targets:
            attempts_skipped += 1
            self._record_attempt(
                conn,
                digest_id=digest.id,
                project_id=digest.project_id,
                channel="system",
                target="no_targets_configured",
                status="skipped",
                provider_message_id=None,
                error_message=None,
                response_payload={"reason": "no_enabled_targets"},
            )
            return {
                "digest_id": str(digest.id),
                "project_id": digest.project_id,
                "digest_status": "ready",
                "attempts_sent": attempts_sent,
                "attempts_failed": attempts_failed,
                "attempts_skipped": attempts_skipped,
            }

        for target in targets:
            if not self._target_accepts_digest_kind(target=target, digest=digest):
                attempts_skipped += 1
                self._record_attempt(
                    conn,
                    digest_id=digest.id,
                    project_id=digest.project_id,
                    channel=target.channel,
                    target=target.target,
                    status="skipped",
                    provider_message_id=None,
                    error_message=None,
                    response_payload={
                        "reason": "digest_kind_filtered",
                        "digest_kind": digest.digest_kind,
                        "allowed_digest_kinds": self._target_digest_kinds(target),
                    },
                )
                continue
            if self._target_should_skip_incident_escalation(target=target, digest=digest):
                attempts_skipped += 1
                self._record_attempt(
                    conn,
                    digest_id=digest.id,
                    project_id=digest.project_id,
                    channel=target.channel,
                    target=target.target,
                    status="skipped",
                    provider_message_id=None,
                    error_message=None,
                    response_payload={
                        "reason": "incident_escalation_over_sla_required",
                        "digest_kind": digest.digest_kind,
                        "open_incidents_over_sla": (
                            ((digest.payload.get("snapshot") or {}).get("summary") or {}).get("open_incidents_over_sla")
                            if isinstance(digest.payload, dict)
                            else 0
                        ),
                    },
                )
                continue
            playbook = self._target_incident_escalation_playbook(target=target)
            severity = self._derive_incident_escalation_severity(digest=digest)
            should_suppress, quiet_meta = self._target_should_suppress_for_quiet_hours(
                target=target,
                digest=digest,
                severity=severity,
                playbook=playbook,
            )
            if should_suppress:
                attempts_skipped += 1
                self._record_attempt(
                    conn,
                    digest_id=digest.id,
                    project_id=digest.project_id,
                    channel=target.channel,
                    target=target.target,
                    status="skipped",
                    provider_message_id=None,
                    error_message=None,
                    response_payload={
                        "reason": "incident_escalation_quiet_hours",
                        "digest_kind": digest.digest_kind,
                        "severity": severity,
                        "quiet_hours": quiet_meta,
                    },
                )
                continue

            routes = self._build_target_delivery_routes(
                target=target,
                digest=digest,
                severity=severity,
                playbook=playbook,
            )
            if not routes:
                attempts_skipped += 1
                self._record_attempt(
                    conn,
                    digest_id=digest.id,
                    project_id=digest.project_id,
                    channel=target.channel,
                    target=target.target,
                    status="skipped",
                    provider_message_id=None,
                    error_message=None,
                    response_payload={
                        "reason": "no_delivery_routes",
                        "digest_kind": digest.digest_kind,
                        "severity": severity,
                    },
                )
                continue

            for route in routes:
                route_target = str(route.get("recipient") or target.target)
                route_error = str(route.get("error") or "").strip()
                if route_error:
                    attempts_skipped += 1
                    self._record_attempt(
                        conn,
                        digest_id=digest.id,
                        project_id=digest.project_id,
                        channel=target.channel,
                        target=route_target,
                        status="skipped",
                        provider_message_id=None,
                        error_message=None,
                        response_payload={
                            "reason": route_error,
                            "route_type": route.get("route_type"),
                            "route_source": route.get("route_source"),
                            "severity": severity,
                        },
                    )
                    continue

                attempt_status = "failed"
                provider_message_id: str | None = None
                error_message: str | None = None
                response_payload: dict[str, Any] = {}
                route_context = {
                    "severity": severity,
                    "route_type": route.get("route_type"),
                    "route_source": route.get("route_source"),
                    "recipient": route_target,
                    "channel_override": route.get("channel_override"),
                }
                route_meta = route.get("meta")
                if isinstance(route_meta, dict):
                    route_context.update(route_meta)
                try:
                    response_payload = self._send_target(
                        target=target,
                        digest=digest,
                        send_target=str(route.get("send_target") or target.target),
                        render_context=route_context,
                    )
                    provider_message_id = str(response_payload.get("message_id") or "")
                    attempt_status = "sent"
                    attempts_sent += 1
                except Exception as exc:
                    attempts_failed += 1
                    error_message = str(exc)
                self._record_attempt(
                    conn,
                    digest_id=digest.id,
                    project_id=digest.project_id,
                    channel=target.channel,
                    target=route_target,
                    status=attempt_status,
                    provider_message_id=provider_message_id if provider_message_id else None,
                    error_message=error_message,
                    response_payload={
                        **response_payload,
                        "routing": route_context,
                    },
                )

        digest_status = "ready"
        if attempts_sent > 0:
            digest_status = "sent"
            self._mark_digest_sent(conn, digest_id=digest.id)
        elif attempts_failed > 0:
            digest_status = "failed"
            self._mark_digest_failed(conn, digest_id=digest.id)

        return {
            "digest_id": str(digest.id),
            "project_id": digest.project_id,
            "digest_status": digest_status,
            "attempts_sent": attempts_sent,
            "attempts_failed": attempts_failed,
            "attempts_skipped": attempts_skipped,
        }

    def _send_target(
        self,
        *,
        target: DeliveryTarget,
        digest: DigestRecord,
        send_target: str | None = None,
        render_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        destination = str(send_target or target.target).strip() or target.target
        if target.channel == "slack_webhook":
            return self._send_slack_webhook(
                target,
                digest,
                webhook_url=destination,
                channel_override=(
                    str(render_context.get("channel_override") or "").strip()
                    if isinstance(render_context, dict)
                    else None
                ),
                render_context=render_context,
            )
        if target.channel == "email_smtp":
            return self._send_email_smtp(target, digest, recipient=destination, render_context=render_context)
        raise ValueError(f"unsupported delivery channel: {target.channel}")

    def _send_slack_webhook(
        self,
        target: DeliveryTarget,
        digest: DigestRecord,
        *,
        webhook_url: str,
        channel_override: str | None,
        render_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        body = self._build_slack_payload(digest=digest, channel_override=channel_override, render_context=render_context)
        timeout_s = float(target.config.get("timeout_seconds", 8))
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8") if response else ""
                return {"status_code": int(response.status), "body": raw, "message_id": response.headers.get("x-slack-req-id")}
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8") if err.fp is not None else ""
            raise RuntimeError(f"slack_webhook_http_error:{err.code}:{raw}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"slack_webhook_network_error:{err}") from err

    def _send_email_smtp(
        self,
        target: DeliveryTarget,
        digest: DigestRecord,
        *,
        recipient: str,
        render_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        config = target.config or {}
        host = str(config.get("host") or "").strip()
        if not host:
            raise ValueError("email_smtp requires config.host")
        port = int(config.get("port", 587))
        username = str(config.get("username") or "").strip() or None
        password = str(config.get("password") or "").strip() or None
        use_tls = bool(config.get("use_tls", True))
        use_ssl = bool(config.get("use_ssl", False))
        from_email = str(config.get("from_email") or username or "").strip()
        if not from_email:
            raise ValueError("email_smtp requires config.from_email (or username)")

        subject_prefix = str(config.get("subject_prefix") or "[Synapse]").strip()
        severity = (
            self._normalize_incident_escalation_severity(render_context.get("severity"), default="")
            if isinstance(render_context, dict) and render_context.get("severity") is not None
            else None
        )
        msg = EmailMessage()
        msg["From"] = from_email
        msg["To"] = recipient
        severity_prefix = f"[{severity.upper()}] " if isinstance(severity, str) and severity else ""
        msg["Subject"] = f"{subject_prefix} {severity_prefix}{self._digest_subject_label(digest)} {digest.digest_date}: {digest.headline}"
        msg.set_content(digest.summary_markdown)

        timeout_s = float(config.get("timeout_seconds", 10))
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host=host, port=port, timeout=timeout_s, context=context) as server:
                if username:
                    server.login(username, password or "")
                server.send_message(msg)
        else:
            with smtplib.SMTP(host=host, port=port, timeout=timeout_s) as server:
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                if username:
                    server.login(username, password or "")
                server.send_message(msg)
        return {"status_code": 250, "message_id": msg.get("Message-ID", "")}

    def _digest_subject_label(self, digest: DigestRecord) -> str:
        if digest.digest_kind == INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            return "Incident Escalation Pulse"
        if digest.digest_kind == "weekly":
            return "Intelligence Weekly"
        return "Intelligence Daily"

    def _build_slack_payload(
        self,
        *,
        digest: DigestRecord,
        channel_override: str | None = None,
        render_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        severity = (
            self._normalize_incident_escalation_severity(render_context.get("severity"), default="")
            if isinstance(render_context, dict) and render_context.get("severity") is not None
            else ""
        )
        severity_prefix = f"[{severity.upper()}] " if severity else ""
        route_type = str(render_context.get("route_type") or "").strip() if isinstance(render_context, dict) else ""
        route_recipient = str(render_context.get("recipient") or "").strip() if isinstance(render_context, dict) else ""
        route_line = (
            f"• Route: `{route_type or 'default'}` -> `{route_recipient}`"
            if route_type or route_recipient
            else None
        )
        if digest.digest_kind == INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            snapshot = digest.payload.get("snapshot") if isinstance(digest.payload, dict) else {}
            summary = snapshot.get("summary") if isinstance(snapshot, dict) else {}
            over_sla = int(summary.get("open_incidents_over_sla") or 0)
            open_total = int(summary.get("open_incidents") or 0)
            routing_ready = int(summary.get("routing_ready_open_incidents") or 0)
            candidates = (
                snapshot.get("over_sla_candidates")
                if isinstance(snapshot, dict) and isinstance(snapshot.get("over_sla_candidates"), list)
                else []
            )
            if not candidates:
                candidates = (
                    snapshot.get("escalation_candidates")
                    if isinstance(snapshot, dict) and isinstance(snapshot.get("escalation_candidates"), list)
                    else []
                )
            top_lines: list[str] = []
            for item in candidates[:5]:
                if not isinstance(item, dict):
                    continue
                project_id = str(item.get("project_id") or digest.project_id)
                age = item.get("age_minutes")
                action = str(item.get("recommended_action") or "monitor_until_next_sync")
                ticket = str(item.get("ticket_id") or "").strip() or "missing_ticket"
                top_lines.append(f"• `{project_id}` age={age}m action={action} ticket={ticket}")
            detail = "\n".join(top_lines) if top_lines else "• No active escalation candidates."
            if route_line:
                detail = f"{detail}\n{route_line}"
            title = f"*{severity_prefix}Queue Incident Escalation Pulse ({digest.digest_date})*"
            headline = f"*{over_sla}/{open_total} over SLA* • routing ready {routing_ready}/{open_total}"
            payload = {
                "text": f"{digest.headline}\n{digest.summary_markdown}",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": title}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": headline}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": detail[:2900]}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": digest.summary_markdown[:2900]}},
                ],
            }
            if channel_override:
                payload["channel"] = channel_override
            return payload
        payload = {
            "text": f"{digest.headline}\n{digest.summary_markdown}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{severity_prefix}Synapse Intelligence ({digest.digest_date})*"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{digest.headline}*"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": digest.summary_markdown[:2900]}},
            ],
        }
        if route_line:
            payload["blocks"].insert(2, {"type": "section", "text": {"type": "mrkdwn", "text": route_line}})
        if channel_override:
            payload["channel"] = channel_override
        return payload

    def _target_digest_kinds(self, target: DeliveryTarget) -> list[str]:
        config = target.config if isinstance(target.config, dict) else {}
        raw = config.get("digest_kinds")
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            kind = str(item or "").strip().lower()
            if not kind or kind in out:
                continue
            out.append(kind[:64])
        return out

    def _target_accepts_digest_kind(self, *, target: DeliveryTarget, digest: DigestRecord) -> bool:
        allowed = self._target_digest_kinds(target)
        if not allowed:
            return True
        return digest.digest_kind in set(allowed)

    def _target_should_skip_incident_escalation(self, *, target: DeliveryTarget, digest: DigestRecord) -> bool:
        if digest.digest_kind != INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            return False
        config = target.config if isinstance(target.config, dict) else {}
        require_over_sla = bool(config.get("incident_escalation_require_over_sla", True))
        if not require_over_sla:
            return False
        payload = digest.payload if isinstance(digest.payload, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        over_sla = int(summary.get("open_incidents_over_sla") or 0)
        return over_sla <= 0

    def _normalize_incident_escalation_severity(self, value: Any, *, default: str = "warning") -> str:
        text = str(value or default).strip().lower()
        if not text:
            text = default
        if text not in _ESCALATION_SEVERITY_RANK:
            return default
        return text

    def _target_incident_escalation_playbook(self, *, target: DeliveryTarget) -> dict[str, Any]:
        config = target.config if isinstance(target.config, dict) else {}
        raw = config.get("incident_escalation_playbook")
        if not isinstance(raw, dict):
            raw = {}

        owner_map = dict(_ESCALATION_OWNER_FIELD_DEFAULTS)
        owner_map_raw = raw.get("owner_tier_channels_by_severity")
        if isinstance(owner_map_raw, dict):
            for severity in _ESCALATION_SEVERITY_RANK:
                value = str(owner_map_raw.get(severity) or "").strip()
                if value in {"owner_name", "owner_contact", "oncall_channel", "escalation_channel"}:
                    owner_map[severity] = value

        fallback_recipients: list[str] = []
        fallback_raw = raw.get("owner_tier_fallback_recipients")
        if isinstance(fallback_raw, list):
            for item in fallback_raw:
                text = str(item or "").strip()
                if not text or text in fallback_recipients:
                    continue
                fallback_recipients.append(text[:512])
                if len(fallback_recipients) >= 20:
                    break

        fanout: dict[str, list[str]] = {severity: [] for severity in _ESCALATION_SEVERITY_RANK}
        fanout_raw = raw.get("severity_fanout")
        if isinstance(fanout_raw, dict):
            for severity in _ESCALATION_SEVERITY_RANK:
                rows = fanout_raw.get(severity)
                if not isinstance(rows, list):
                    continue
                out: list[str] = []
                for item in rows:
                    text = str(item or "").strip()
                    if not text or text in out:
                        continue
                    out.append(text[:512])
                    if len(out) >= 40:
                        break
                fanout[severity] = out

        quiet_hours: dict[str, Any] = {
            "enabled": False,
            "timezone": "UTC",
            "allow_severity_at_or_above": "critical",
            "windows": [],
        }
        quiet_raw = raw.get("quiet_hours")
        if isinstance(quiet_raw, dict):
            quiet_hours["enabled"] = bool(quiet_raw.get("enabled", False))
            timezone_name = str(quiet_raw.get("timezone") or "UTC").strip()[:64] or "UTC"
            quiet_hours["timezone"] = timezone_name
            quiet_hours["allow_severity_at_or_above"] = self._normalize_incident_escalation_severity(
                quiet_raw.get("allow_severity_at_or_above"),
                default="critical",
            )
            windows: list[dict[str, Any]] = []
            windows_raw = quiet_raw.get("windows")
            if isinstance(windows_raw, list):
                for row in windows_raw:
                    if not isinstance(row, dict):
                        continue
                    day_indexes = self._normalize_incident_weekdays(row.get("days"))
                    start_minutes = self._parse_quiet_hour_minutes(row.get("start"))
                    end_minutes = self._parse_quiet_hour_minutes(row.get("end"))
                    if not day_indexes or start_minutes is None or end_minutes is None:
                        continue
                    windows.append(
                        {
                            "days": day_indexes,
                            "start_minutes": start_minutes,
                            "end_minutes": end_minutes,
                            "start": self._format_quiet_hour_minutes(start_minutes),
                            "end": self._format_quiet_hour_minutes(end_minutes),
                        }
                    )
                    if len(windows) >= 24:
                        break
            quiet_hours["windows"] = windows

        return {
            "enabled": bool(raw.get("enabled", False)),
            "owner_tier_enabled": bool(raw.get("owner_tier_enabled", True)),
            "owner_tier_max_candidates": max(1, min(20, int(raw.get("owner_tier_max_candidates") or 5))),
            "owner_tier_channels_by_severity": owner_map,
            "owner_tier_fallback_recipients": fallback_recipients,
            "severity_fanout": fanout,
            "quiet_hours": quiet_hours,
        }

    def _derive_incident_escalation_severity(self, *, digest: DigestRecord) -> str:
        if digest.digest_kind != INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            return "info"
        payload = digest.payload if isinstance(digest.payload, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        over_sla = int(summary.get("open_incidents_over_sla") or 0)
        critical_open = int(summary.get("critical_open_incidents") or 0)
        open_total = int(summary.get("open_incidents") or 0)
        candidates = (
            snapshot.get("escalation_candidates")
            if isinstance(snapshot, dict) and isinstance(snapshot.get("escalation_candidates"), list)
            else []
        )
        max_risk_score = 0
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            max_risk_score = max(max_risk_score, int(candidate.get("risk_score") or 0))
        if over_sla > 0:
            return "critical"
        if critical_open > 0 or max_risk_score >= 10 or open_total >= 5:
            return "warning"
        return "info"

    def _target_should_suppress_for_quiet_hours(
        self,
        *,
        target: DeliveryTarget,
        digest: DigestRecord,
        severity: str,
        playbook: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        if digest.digest_kind != INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            return (False, {"enabled": False, "reason": "digest_kind_not_incident_escalation"})
        if not bool(playbook.get("enabled", False)):
            return (False, {"enabled": False, "reason": "playbook_disabled"})

        quiet_hours = playbook.get("quiet_hours") if isinstance(playbook.get("quiet_hours"), dict) else {}
        if not bool(quiet_hours.get("enabled", False)):
            return (False, {"enabled": False, "reason": "quiet_hours_disabled"})

        allow_threshold = self._normalize_incident_escalation_severity(
            quiet_hours.get("allow_severity_at_or_above"),
            default="critical",
        )
        effective_severity = self._normalize_incident_escalation_severity(severity, default="warning")
        if _ESCALATION_SEVERITY_RANK.get(effective_severity, 0) >= _ESCALATION_SEVERITY_RANK.get(allow_threshold, 2):
            return (
                False,
                {
                    "enabled": True,
                    "bypassed": True,
                    "reason": "severity_bypasses_quiet_hours",
                    "severity": effective_severity,
                    "allow_severity_at_or_above": allow_threshold,
                },
            )

        timezone_name = str(quiet_hours.get("timezone") or "UTC").strip() or "UTC"
        invalid_timezone = False
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = UTC
            invalid_timezone = True
            timezone_name = "UTC"

        now_local = datetime.now(UTC).astimezone(tz)
        minute_of_day = now_local.hour * 60 + now_local.minute
        weekday = now_local.weekday()
        previous_weekday = (weekday - 1) % 7

        windows = quiet_hours.get("windows") if isinstance(quiet_hours.get("windows"), list) else []
        for index, raw_window in enumerate(windows):
            if not isinstance(raw_window, dict):
                continue
            day_indexes = raw_window.get("days")
            if not isinstance(day_indexes, list) or not day_indexes:
                continue
            normalized_days = sorted({max(0, min(6, int(day))) for day in day_indexes})
            start_minutes = self._parse_quiet_hour_minutes(raw_window.get("start"))
            end_minutes = self._parse_quiet_hour_minutes(raw_window.get("end"))
            if start_minutes is None:
                start_minutes = (
                    int(raw_window.get("start_minutes"))
                    if isinstance(raw_window.get("start_minutes"), int)
                    else None
                )
            if end_minutes is None:
                end_minutes = (
                    int(raw_window.get("end_minutes"))
                    if isinstance(raw_window.get("end_minutes"), int)
                    else None
                )
            if start_minutes is None or end_minutes is None:
                continue
            if start_minutes == end_minutes:
                is_active = weekday in normalized_days
            elif start_minutes < end_minutes:
                is_active = weekday in normalized_days and start_minutes <= minute_of_day < end_minutes
            else:
                is_active = (
                    (weekday in normalized_days and minute_of_day >= start_minutes)
                    or (previous_weekday in normalized_days and minute_of_day < end_minutes)
                )
            if is_active:
                return (
                    True,
                    {
                        "enabled": True,
                        "timezone": timezone_name,
                        "severity": effective_severity,
                        "allow_severity_at_or_above": allow_threshold,
                        "invalid_timezone": invalid_timezone,
                        "matched_window": {
                            "index": index,
                            "days": normalized_days,
                            "start": self._format_quiet_hour_minutes(start_minutes),
                            "end": self._format_quiet_hour_minutes(end_minutes),
                        },
                        "local_time": now_local.isoformat(),
                    },
                )

        return (
            False,
            {
                "enabled": True,
                "timezone": timezone_name,
                "severity": effective_severity,
                "allow_severity_at_or_above": allow_threshold,
                "invalid_timezone": invalid_timezone,
                "reason": "outside_configured_windows",
                "local_time": now_local.isoformat(),
            },
        )

    def _build_target_delivery_routes(
        self,
        *,
        target: DeliveryTarget,
        digest: DigestRecord,
        severity: str,
        playbook: dict[str, Any],
    ) -> list[dict[str, Any]]:
        def base_route() -> dict[str, Any]:
            return {
                "recipient": target.target,
                "send_target": target.target,
                "channel_override": None,
                "route_type": "base_target",
                "route_source": "target",
                "meta": {"candidate_count": 0},
            }

        if digest.digest_kind != INTELLIGENCE_DIGEST_KIND_INCIDENT_ESCALATION_DAILY:
            return [base_route()]
        if not bool(playbook.get("enabled", False)):
            return [base_route()]

        routes: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        owner_routes_added = 0
        effective_severity = self._normalize_incident_escalation_severity(severity, default="warning")
        owner_field = str(
            (playbook.get("owner_tier_channels_by_severity") or {}).get(
                effective_severity,
                _ESCALATION_OWNER_FIELD_DEFAULTS.get(effective_severity, "oncall_channel"),
            )
            or _ESCALATION_OWNER_FIELD_DEFAULTS.get(effective_severity, "oncall_channel")
        ).strip()
        if owner_field not in {"owner_name", "owner_contact", "oncall_channel", "escalation_channel"}:
            owner_field = _ESCALATION_OWNER_FIELD_DEFAULTS.get(effective_severity, "oncall_channel")

        def add_route(
            *,
            recipient: str,
            route_type: str,
            route_source: str,
            meta: dict[str, Any] | None = None,
        ) -> None:
            recipient_text = str(recipient or "").strip()
            if not recipient_text:
                return
            if target.channel == "email_smtp" and "@" not in recipient_text:
                routes.append(
                    {
                        "recipient": recipient_text,
                        "send_target": recipient_text,
                        "channel_override": None,
                        "route_type": route_type,
                        "route_source": route_source,
                        "error": "invalid_email_recipient",
                        "meta": meta or {},
                    }
                )
                return
            if target.channel == "slack_webhook":
                send_target = target.target
                channel_override = recipient_text
            else:
                send_target = recipient_text
                channel_override = None
            route_key = (recipient_text, send_target, channel_override or "")
            if route_key in seen:
                return
            seen.add(route_key)
            routes.append(
                {
                    "recipient": recipient_text,
                    "send_target": send_target,
                    "channel_override": channel_override,
                    "route_type": route_type,
                    "route_source": route_source,
                    "meta": meta or {},
                }
            )

        snapshot = digest.payload.get("snapshot") if isinstance(digest.payload, dict) else {}
        over_sla_candidates = (
            snapshot.get("over_sla_candidates")
            if isinstance(snapshot, dict) and isinstance(snapshot.get("over_sla_candidates"), list)
            else []
        )
        escalation_candidates = (
            snapshot.get("escalation_candidates")
            if isinstance(snapshot, dict) and isinstance(snapshot.get("escalation_candidates"), list)
            else []
        )
        candidates = over_sla_candidates if over_sla_candidates else escalation_candidates

        if bool(playbook.get("owner_tier_enabled", True)):
            max_candidates = max(1, min(20, int(playbook.get("owner_tier_max_candidates") or 5)))
            for candidate in candidates[:max_candidates]:
                if not isinstance(candidate, dict):
                    continue
                ownership = candidate.get("ownership") if isinstance(candidate.get("ownership"), dict) else {}
                recipient = str(ownership.get(owner_field) or "").strip()
                if not recipient:
                    continue
                add_route(
                    recipient=recipient,
                    route_type="owner_tier",
                    route_source=owner_field,
                    meta={
                        "candidate_project_id": str(candidate.get("project_id") or digest.project_id),
                        "incident_id": str(candidate.get("incident_id") or ""),
                        "recommended_action": str(candidate.get("recommended_action") or ""),
                        "over_sla": bool(candidate.get("over_sla")),
                    },
                )
                owner_routes_added += 1

            if owner_routes_added <= 0:
                fallback_recipients = (
                    playbook.get("owner_tier_fallback_recipients")
                    if isinstance(playbook.get("owner_tier_fallback_recipients"), list)
                    else []
                )
                for recipient in fallback_recipients:
                    add_route(
                        recipient=str(recipient or ""),
                        route_type="owner_tier_fallback",
                        route_source=owner_field,
                        meta={"candidate_count": len(candidates)},
                    )

        severity_fanout = (
            playbook.get("severity_fanout")
            if isinstance(playbook.get("severity_fanout"), dict)
            else {}
        )
        fanout_recipients = severity_fanout.get(effective_severity)
        if isinstance(fanout_recipients, list):
            for recipient in fanout_recipients:
                add_route(
                    recipient=str(recipient or ""),
                    route_type="severity_fanout",
                    route_source=f"severity:{effective_severity}",
                    meta={"candidate_count": len(candidates)},
                )

        if not routes:
            return [base_route()]
        return routes

    def _parse_quiet_hour_minutes(self, value: Any) -> int | None:
        text = str(value or "").strip()
        if len(text) != 5 or ":" not in text:
            return None
        left, right = text.split(":", 1)
        if not left.isdigit() or not right.isdigit():
            return None
        hour = int(left)
        minute = int(right)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None
        return (hour * 60) + minute

    def _format_quiet_hour_minutes(self, value: int) -> str:
        minutes = max(0, min(1439, int(value)))
        hour = minutes // 60
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"

    def _normalize_incident_weekdays(self, value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        aliases = {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "mon": 0,
            "monday": 0,
            "tue": 1,
            "tues": 1,
            "tuesday": 1,
            "wed": 2,
            "weds": 2,
            "wednesday": 2,
            "thu": 3,
            "thur": 3,
            "thurs": 3,
            "thursday": 3,
            "fri": 4,
            "friday": 4,
            "sat": 5,
            "saturday": 5,
            "sun": 6,
            "sunday": 6,
        }
        out: list[int] = []
        for item in value:
            key = str(item or "").strip().lower()
            day = aliases.get(key)
            if day is None or day in out:
                continue
            out.append(day)
        return out

    def _list_ready_digests(
        self,
        conn,
        *,
        project_ids: list[str] | None,
        digest_kind: str,
        limit: int,
    ) -> list[DigestRecord]:
        params: list[Any] = [digest_kind]
        project_filter = ""
        if project_ids:
            project_filter = "AND project_id = ANY(%s)"
            params.append(project_ids)
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, project_id, digest_kind, digest_date, headline, summary_markdown, payload
                FROM intelligence_digests
                WHERE status = 'ready'
                  AND digest_kind = %s
                  {project_filter}
                ORDER BY digest_date ASC, generated_at ASC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
        return [
            DigestRecord(
                id=row[0],
                project_id=row[1],
                digest_kind=row[2],
                digest_date=row[3].isoformat(),
                headline=row[4],
                summary_markdown=row[5],
                payload=row[6] if isinstance(row[6], dict) else {},
            )
            for row in rows
        ]

    def _load_digest(self, conn, *, digest_id: UUID) -> DigestRecord | None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, project_id, digest_kind, digest_date, headline, summary_markdown, payload
                FROM intelligence_digests
                WHERE id = %s
                LIMIT 1
                """,
                (digest_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return DigestRecord(
            id=row[0],
            project_id=row[1],
            digest_kind=row[2],
            digest_date=row[3].isoformat(),
            headline=row[4],
            summary_markdown=row[5],
            payload=row[6] if isinstance(row[6], dict) else {},
        )

    def _list_targets(self, conn, *, project_id: str) -> list[DeliveryTarget]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, project_id, channel, target, enabled, config
                FROM intelligence_delivery_targets
                WHERE project_id = %s
                  AND enabled = TRUE
                ORDER BY updated_at DESC
                """,
                (project_id,),
            )
            rows = cur.fetchall()
        return [
            DeliveryTarget(
                id=row[0],
                project_id=row[1],
                channel=row[2],
                target=row[3],
                enabled=bool(row[4]),
                config=row[5] if isinstance(row[5], dict) else {},
            )
            for row in rows
        ]

    def _record_attempt(
        self,
        conn,
        *,
        digest_id: UUID,
        project_id: str,
        channel: str,
        target: str,
        status: str,
        provider_message_id: str | None,
        error_message: str | None,
        response_payload: dict[str, Any],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence_delivery_attempts (
                  id, digest_id, project_id, channel, target, status, provider_message_id, error_message, response_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid4(),
                    digest_id,
                    project_id,
                    channel,
                    target,
                    status,
                    provider_message_id,
                    error_message,
                    Jsonb(response_payload),
                ),
            )

    def _mark_digest_sent(self, conn, *, digest_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence_digests
                SET status = 'sent',
                    sent_at = NOW()
                WHERE id = %s
                """,
                (digest_id,),
            )

    def _mark_digest_failed(self, conn, *, digest_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence_digests
                SET status = 'failed',
                    sent_at = NULL
                WHERE id = %s
                """,
                (digest_id,),
            )
