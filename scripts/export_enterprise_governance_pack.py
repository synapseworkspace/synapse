#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any

import psycopg


def _dt(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export enterprise governance pack (tenancy/auth/rbac) from Synapse DB.")
    parser.add_argument(
        "--database-url",
        default="postgresql://synapse:synapse@localhost:55432/synapse",
        help="Postgres DSN.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/governance-pack",
        help="Output directory for JSON/CSV/markdown governance artifacts.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="Audit lookback window (days) for moderation/queue events.",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Optional project filter for audit extracts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    now = datetime.now(UTC)
    since = now - timedelta(days=max(1, int(args.window_days)))

    tenants: list[dict[str, Any]] = []
    memberships: list[dict[str, Any]] = []
    project_bindings: list[dict[str, Any]] = []
    session_summary: dict[str, Any] = {}
    moderation_actions: list[dict[str, Any]] = []
    queue_audit: list[dict[str, Any]] = []

    with psycopg.connect(args.database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, slug, name, status, metadata, created_by, updated_by, created_at, updated_at
                FROM tenants
                ORDER BY created_at DESC
                """
            )
            for row in cur.fetchall() or []:
                tenants.append(
                    {
                        "id": str(row[0]),
                        "slug": str(row[1]),
                        "name": str(row[2]),
                        "status": str(row[3]),
                        "metadata": dict(row[4] or {}) if isinstance(row[4], dict) else {},
                        "created_by": None if row[5] is None else str(row[5]),
                        "updated_by": None if row[6] is None else str(row[6]),
                        "created_at": _dt(row[7]),
                        "updated_at": _dt(row[8]),
                    }
                )

            cur.execute(
                """
                SELECT id::text, tenant_id::text, user_id, email, display_name, roles, status, metadata, created_by, updated_by, created_at, updated_at
                FROM tenant_memberships
                ORDER BY updated_at DESC
                """
            )
            for row in cur.fetchall() or []:
                memberships.append(
                    {
                        "id": str(row[0]),
                        "tenant_id": str(row[1]),
                        "user_id": str(row[2]),
                        "email": None if row[3] is None else str(row[3]),
                        "display_name": None if row[4] is None else str(row[4]),
                        "roles": ",".join(str(item) for item in (row[5] or [])),
                        "status": str(row[6]),
                        "metadata": json.dumps(row[7], ensure_ascii=False) if isinstance(row[7], dict) else "{}",
                        "created_by": None if row[8] is None else str(row[8]),
                        "updated_by": None if row[9] is None else str(row[9]),
                        "created_at": _dt(row[10]),
                        "updated_at": _dt(row[11]),
                    }
                )

            cur.execute(
                """
                SELECT id::text, tenant_id::text, project_id, status, metadata, created_by, updated_by, created_at, updated_at
                FROM tenant_projects
                ORDER BY updated_at DESC
                """
            )
            for row in cur.fetchall() or []:
                project_bindings.append(
                    {
                        "id": str(row[0]),
                        "tenant_id": str(row[1]),
                        "project_id": str(row[2]),
                        "status": str(row[3]),
                        "metadata": json.dumps(row[4], ensure_ascii=False) if isinstance(row[4], dict) else "{}",
                        "created_by": None if row[5] is None else str(row[5]),
                        "updated_by": None if row[6] is None else str(row[6]),
                        "created_at": _dt(row[7]),
                        "updated_at": _dt(row[8]),
                    }
                )

            cur.execute(
                """
                SELECT
                  COUNT(*)::int AS sessions_total,
                  COUNT(*) FILTER (WHERE revoked_at IS NULL AND expires_at > NOW())::int AS sessions_active,
                  COUNT(*) FILTER (WHERE revoked_at IS NOT NULL)::int AS sessions_revoked,
                  COUNT(*) FILTER (WHERE expires_at <= NOW())::int AS sessions_expired
                FROM auth_sessions
                """
            )
            row = cur.fetchone()
            session_summary = {
                "sessions_total": int((row[0] if row else 0) or 0),
                "sessions_active": int((row[1] if row else 0) or 0),
                "sessions_revoked": int((row[2] if row else 0) or 0),
                "sessions_expired": int((row[3] if row else 0) or 0),
            }

            if args.project_id:
                cur.execute(
                    """
                    SELECT id::text, project_id, draft_id::text, action, reviewed_by, note, created_at
                    FROM wiki_moderation_actions
                    WHERE created_at >= %s
                      AND project_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5000
                    """,
                    (since, args.project_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id::text, project_id, draft_id::text, action, reviewed_by, note, created_at
                    FROM wiki_moderation_actions
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 5000
                    """,
                    (since,),
                )
            for row in cur.fetchall() or []:
                moderation_actions.append(
                    {
                        "id": str(row[0]),
                        "project_id": str(row[1]),
                        "draft_id": str(row[2]),
                        "action": str(row[3]),
                        "reviewed_by": None if row[4] is None else str(row[4]),
                        "note": None if row[5] is None else str(row[5]),
                        "created_at": _dt(row[6]),
                    }
                )

            if args.project_id:
                cur.execute(
                    """
                    SELECT id::text, project_id, action, actor, reason, created_at
                    FROM gatekeeper_calibration_queue_control_events
                    WHERE created_at >= %s
                      AND project_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5000
                    """,
                    (since, args.project_id),
                )
            else:
                cur.execute(
                    """
                    SELECT id::text, project_id, action, actor, reason, created_at
                    FROM gatekeeper_calibration_queue_control_events
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 5000
                    """,
                    (since,),
                )
            for row in cur.fetchall() or []:
                queue_audit.append(
                    {
                        "id": str(row[0]),
                        "project_id": str(row[1]),
                        "action": str(row[2]),
                        "actor": None if row[3] is None else str(row[3]),
                        "reason": None if row[4] is None else str(row[4]),
                        "created_at": _dt(row[5]),
                    }
                )

    tenant_index = {row["id"]: row for row in tenants}
    for membership in memberships:
        tenant_id = str(membership.get("tenant_id") or "")
        tenant = tenant_index.get(tenant_id)
        if tenant is None:
            continue
        members = tenant.setdefault("memberships", [])
        if isinstance(members, list):
            members.append(
                {
                    "user_id": membership["user_id"],
                    "roles": [item for item in str(membership["roles"]).split(",") if item],
                    "status": membership["status"],
                }
            )
    for binding in project_bindings:
        tenant_id = str(binding.get("tenant_id") or "")
        tenant = tenant_index.get(tenant_id)
        if tenant is None:
            continue
        projects = tenant.setdefault("projects", [])
        if isinstance(projects, list):
            projects.append(
                {
                    "project_id": binding["project_id"],
                    "status": binding["status"],
                }
            )

    summary = {
        "generated_at": now.isoformat(),
        "window_days": int(args.window_days),
        "project_filter": args.project_id,
        "tenants_total": len(tenants),
        "memberships_total": len(memberships),
        "project_bindings_total": len(project_bindings),
        "moderation_actions_window": len(moderation_actions),
        "queue_audit_window": len(queue_audit),
        "sessions": session_summary,
    }
    pack = {
        "summary": summary,
        "tenants": tenants,
        "memberships": memberships,
        "project_bindings": project_bindings,
        "moderation_actions": moderation_actions,
        "queue_control_events": queue_audit,
    }

    _write_json(output_dir / "enterprise_governance_pack.json", pack)
    _write_json(output_dir / "summary.json", summary)
    _write_csv(
        output_dir / "tenant_memberships.csv",
        memberships,
        [
            "id",
            "tenant_id",
            "user_id",
            "email",
            "display_name",
            "roles",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ],
    )
    _write_csv(
        output_dir / "tenant_project_bindings.csv",
        project_bindings,
        [
            "id",
            "tenant_id",
            "project_id",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ],
    )
    _write_csv(
        output_dir / "moderation_actions_window.csv",
        moderation_actions,
        ["id", "project_id", "draft_id", "action", "reviewed_by", "note", "created_at"],
    )
    _write_csv(
        output_dir / "queue_control_events_window.csv",
        queue_audit,
        ["id", "project_id", "action", "actor", "reason", "created_at"],
    )

    runbook_lines = [
        "# Enterprise Governance Runbook Pack",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Window days: `{summary['window_days']}`",
        f"- Project filter: `{summary['project_filter'] or 'none'}`",
        "",
        "## Coverage",
        f"- Tenants: `{summary['tenants_total']}`",
        f"- Memberships: `{summary['memberships_total']}`",
        f"- Project bindings: `{summary['project_bindings_total']}`",
        f"- Moderation actions in window: `{summary['moderation_actions_window']}`",
        f"- Queue control events in window: `{summary['queue_audit_window']}`",
        f"- Active auth sessions: `{session_summary.get('sessions_active', 0)}`",
        "",
        "## Operator Checklist",
        "1. Verify each active project has exactly one tenant binding in `tenant_project_bindings.csv`.",
        "2. Verify privileged roles (`admin`, `tenant_admin`, `security_admin`, `incident_admin`) in `tenant_memberships.csv` have current owners.",
        "3. Review `moderation_actions_window.csv` for anomalous reject/force patterns.",
        "4. Review `queue_control_events_window.csv` for repeated pause/resume churn.",
        "5. Revoke stale sessions if `sessions_active` exceeds expected operator count.",
        "",
        "## Artifact Index",
        "- `enterprise_governance_pack.json` (full machine-readable pack)",
        "- `summary.json`",
        "- `tenant_memberships.csv`",
        "- `tenant_project_bindings.csv`",
        "- `moderation_actions_window.csv`",
        "- `queue_control_events_window.csv`",
    ]
    (output_dir / "RUNBOOK.md").write_text("\n".join(runbook_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(output_dir),
                "summary": summary,
                "files": [
                    "enterprise_governance_pack.json",
                    "summary.json",
                    "tenant_memberships.csv",
                    "tenant_project_bindings.csv",
                    "moderation_actions_window.csv",
                    "queue_control_events_window.csv",
                    "RUNBOOK.md",
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
