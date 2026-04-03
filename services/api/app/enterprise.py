from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg import Connection
from psycopg.types.json import Jsonb


_PUBLIC_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
)
_AUTH_PATH_PREFIX = "/v1/auth/"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_OIDC_ALLOWED_ALGOS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
_DEFAULT_ADMIN_ROLES = {"admin", "tenant_admin"}


@dataclass(frozen=True, slots=True)
class EnterpriseSettings:
    auth_mode: str
    rbac_mode: str
    tenancy_mode: str
    oidc_issuer_url: str | None
    oidc_audience: str | None
    oidc_roles_claim: str
    oidc_tenant_claim: str
    oidc_email_claim: str
    oidc_session_ttl_minutes_default: int
    oidc_session_ttl_minutes_max: int


@dataclass(frozen=True, slots=True)
class AccessIdentity:
    subject: str
    email: str | None
    tenant_id: str | None
    roles: tuple[str, ...]
    auth_source: str
    claims: dict[str, Any]
    session_id: str | None = None

    def has_any_role(self, allowed_roles: set[str]) -> bool:
        if not allowed_roles:
            return True
        role_set = {item.strip().lower() for item in self.roles if item.strip()}
        return bool(role_set.intersection(allowed_roles))

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "email": self.email,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "auth_source": self.auth_source,
            "session_id": self.session_id,
            "claims": dict(self.claims),
        }


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    methods: set[str]
    pattern: re.Pattern[str]
    allowed_roles: set[str]
    action: str


_ROLE_AGENT = {"agent", "operator", "knowledge_editor", "tenant_admin", "admin"}
_ROLE_APPROVER = {"approver", "knowledge_editor", "tenant_admin", "admin"}
_ROLE_OPERATOR = {"operator", "tenant_admin", "admin"}
_ROLE_TENANT_ADMIN = {"tenant_admin", "admin"}
_ROLE_INCIDENT_ADMIN = {"incident_admin", "security_admin", "tenant_admin", "admin"}

_ROUTE_POLICIES: list[RoutePolicy] = [
    RoutePolicy({"POST"}, re.compile(r"^/v1/events$"), _ROLE_AGENT, "events_ingest"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/facts/proposals$"), _ROLE_AGENT, "facts_propose"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/backfill/memory$"), _ROLE_AGENT, "memory_backfill"),
    RoutePolicy(
        {"GET", "PUT", "DELETE"},
        re.compile(r"^/v1/adoption/source-ownership(?:/[^/]+)?$"),
        _ROLE_OPERATOR,
        "adoption_source_ownership",
    ),
    RoutePolicy({"POST"}, re.compile(r"^/v1/wiki/pages$"), _ROLE_APPROVER, "wiki_page_write"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/wiki/drafts/[^/]+/(approve|reject)$"), _ROLE_APPROVER, "wiki_moderation"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/wiki/auto-publish/run$"), _ROLE_OPERATOR, "wiki_auto_publish"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/tasks($|/[^/]+/(status|comments|links)$)"), _ROLE_OPERATOR, "task_mutation"),
    RoutePolicy({"PUT", "POST", "DELETE"}, re.compile(r"^/v1/gatekeeper/"), _ROLE_OPERATOR, "gatekeeper_mutation"),
    RoutePolicy(
        {"PUT"},
        re.compile(r"^/v1/gatekeeper/calibration/operations/incidents/(hooks|policies)$"),
        _ROLE_INCIDENT_ADMIN,
        "incident_secret_mutation",
    ),
    RoutePolicy({"PUT"}, re.compile(r"^/v1/intelligence/delivery/targets$"), _ROLE_OPERATOR, "intelligence_delivery_mutation"),
    RoutePolicy({"PUT", "POST"}, re.compile(r"^/v1/legacy-import/"), _ROLE_OPERATOR, "legacy_import_mutation"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/simulator/runs$"), _ROLE_OPERATOR, "simulator_run"),
    RoutePolicy({"POST"}, re.compile(r"^/v1/tenants$"), _ROLE_TENANT_ADMIN, "tenant_create"),
    RoutePolicy({"PUT", "DELETE"}, re.compile(r"^/v1/tenants/"), _ROLE_TENANT_ADMIN, "tenant_admin"),
]

_OIDC_METADATA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_OIDC_JWKS_CLIENT_CACHE: dict[str, tuple[float, Any]] = {}


def _env(name: str, default: str) -> str:
    return str(os.getenv(name, default) or default).strip()


def _normalize_mode(raw: str, *, allowed: set[str], default: str) -> str:
    value = str(raw or "").strip().lower()
    if value not in allowed:
        return default
    return value


def get_enterprise_settings() -> EnterpriseSettings:
    auth_mode = _normalize_mode(_env("SYNAPSE_AUTH_MODE", "open"), allowed={"open", "oidc"}, default="open")
    rbac_mode = _normalize_mode(_env("SYNAPSE_RBAC_MODE", "open"), allowed={"open", "enforce"}, default="open")
    tenancy_mode = _normalize_mode(_env("SYNAPSE_TENANCY_MODE", "open"), allowed={"open", "enforce"}, default="open")
    issuer = _env("SYNAPSE_OIDC_ISSUER_URL", "")
    audience = _env("SYNAPSE_OIDC_AUDIENCE", "")
    session_ttl_default = max(15, min(24 * 60, int(_env("SYNAPSE_OIDC_SESSION_TTL_MINUTES_DEFAULT", "480"))))
    session_ttl_max = max(session_ttl_default, min(60 * 24 * 30, int(_env("SYNAPSE_OIDC_SESSION_TTL_MINUTES_MAX", "10080"))))
    return EnterpriseSettings(
        auth_mode=auth_mode,
        rbac_mode=rbac_mode,
        tenancy_mode=tenancy_mode,
        oidc_issuer_url=issuer or None,
        oidc_audience=audience or None,
        oidc_roles_claim=_env("SYNAPSE_OIDC_ROLES_CLAIM", "roles"),
        oidc_tenant_claim=_env("SYNAPSE_OIDC_TENANT_CLAIM", "tenant_id"),
        oidc_email_claim=_env("SYNAPSE_OIDC_EMAIL_CLAIM", "email"),
        oidc_session_ttl_minutes_default=session_ttl_default,
        oidc_session_ttl_minutes_max=session_ttl_max,
    )


def auth_mode_payload(settings: EnterpriseSettings | None = None) -> dict[str, Any]:
    cfg = settings or get_enterprise_settings()
    return {
        "auth_mode": cfg.auth_mode,
        "rbac_mode": cfg.rbac_mode,
        "tenancy_mode": cfg.tenancy_mode,
        "oidc": {
            "issuer_configured": bool(cfg.oidc_issuer_url),
            "audience_configured": bool(cfg.oidc_audience),
            "roles_claim": cfg.oidc_roles_claim,
            "tenant_claim": cfg.oidc_tenant_claim,
            "email_claim": cfg.oidc_email_claim,
            "session_ttl_minutes_default": cfg.oidc_session_ttl_minutes_default,
            "session_ttl_minutes_max": cfg.oidc_session_ttl_minutes_max,
        },
    }


def _is_public_path(path: str) -> bool:
    for prefix in _PUBLIC_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def _session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_session_token() -> str:
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    return f"syns_{raw}"


def _as_optional_uuid(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(UUID(text))
    except Exception:
        return None


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    value = authorization.strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        token = value[7:].strip()
        return token or None
    return None


def extract_session_token(x_synapse_session: str | None, authorization: str | None) -> str | None:
    header_token = str(x_synapse_session or "").strip()
    if header_token:
        return header_token
    return _extract_bearer_token(authorization)


def _normalize_roles(value: Any) -> tuple[str, ...]:
    raw_values: list[str] = []
    if isinstance(value, str):
        raw_values = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_values = [str(item or "").strip() for item in value]
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        role = raw.lower().strip()
        if not role or role in seen:
            continue
        seen.add(role)
        out.append(role[:64])
    return tuple(out)


def _extract_claim_as_text(claims: dict[str, Any], key: str) -> str | None:
    value = claims.get(key)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _fetch_json(url: str, *, timeout_sec: float = 3.0) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=max(0.5, float(timeout_sec))) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "oidc_metadata_unavailable", "message": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail={"code": "oidc_metadata_invalid", "message": "OIDC metadata payload must be JSON object."},
        )
    return data


def _load_oidc_metadata(issuer_url: str, *, cache_ttl_seconds: int = 300) -> dict[str, Any]:
    issuer = issuer_url.rstrip("/")
    now = datetime.now(UTC).timestamp()
    cached = _OIDC_METADATA_CACHE.get(issuer)
    if cached and cached[0] > now:
        return cached[1]
    discovery_url = urljoin(f"{issuer}/", ".well-known/openid-configuration")
    payload = _fetch_json(discovery_url)
    jwks_uri = str(payload.get("jwks_uri") or "").strip()
    discovered_issuer = str(payload.get("issuer") or issuer).strip()
    if not jwks_uri:
        raise HTTPException(
            status_code=503,
            detail={"code": "oidc_jwks_uri_missing", "message": "OIDC discovery payload missing jwks_uri."},
        )
    value = {
        "issuer": discovered_issuer.rstrip("/"),
        "jwks_uri": jwks_uri,
    }
    _OIDC_METADATA_CACHE[issuer] = (now + max(30, int(cache_ttl_seconds)), value)
    return value


def _get_jwks_client(jwks_uri: str, *, cache_ttl_seconds: int = 300) -> Any:
    now = datetime.now(UTC).timestamp()
    cached = _OIDC_JWKS_CLIENT_CACHE.get(jwks_uri)
    if cached and cached[0] > now:
        return cached[1]
    try:
        import jwt
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "oidc_dependency_missing",
                "message": "PyJWT is required for OIDC mode. Install synapse-api with OIDC dependencies.",
            },
        ) from exc
    client = jwt.PyJWKClient(jwks_uri)
    _OIDC_JWKS_CLIENT_CACHE[jwks_uri] = (now + max(30, int(cache_ttl_seconds)), client)
    return client


def verify_oidc_token(token: str, settings: EnterpriseSettings) -> dict[str, Any]:
    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=400, detail={"code": "auth_mode_not_oidc"})
    issuer = settings.oidc_issuer_url
    if not issuer:
        raise HTTPException(
            status_code=500,
            detail={"code": "oidc_issuer_missing", "message": "SYNAPSE_OIDC_ISSUER_URL is required in OIDC mode."},
        )
    metadata = _load_oidc_metadata(issuer)
    jwks_client = _get_jwks_client(str(metadata["jwks_uri"]))
    try:
        import jwt
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "oidc_dependency_missing", "message": "PyJWT is required for OIDC mode."},
        ) from exc
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        options = {"verify_aud": bool(settings.oidc_audience)}
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_OIDC_ALLOWED_ALGOS,
            audience=settings.oidc_audience or None,
            issuer=str(metadata.get("issuer") or issuer).rstrip("/"),
            options=options,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "oidc_token_invalid", "message": str(exc)},
        ) from exc
    if not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail={"code": "oidc_claims_invalid"})
    return claims


def _identity_from_claims(claims: dict[str, Any], settings: EnterpriseSettings, *, auth_source: str) -> AccessIdentity:
    subject = _extract_claim_as_text(claims, "sub")
    if not subject:
        raise HTTPException(status_code=401, detail={"code": "oidc_sub_missing"})
    tenant_id = _as_optional_uuid(_extract_claim_as_text(claims, settings.oidc_tenant_claim))
    roles = _normalize_roles(claims.get(settings.oidc_roles_claim))
    email = _extract_claim_as_text(claims, settings.oidc_email_claim)
    return AccessIdentity(
        subject=subject,
        email=email,
        tenant_id=tenant_id,
        roles=roles,
        auth_source=auth_source,
        claims=claims,
    )


def _resolve_session_identity(conn: Connection[Any], token: str) -> AccessIdentity:
    token_hash = _session_token_hash(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, subject, email, tenant_id::text, roles, claims, auth_provider
            FROM auth_sessions
            WHERE session_token_hash = %s
              AND revoked_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            """,
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail={"code": "session_not_found"})
        cur.execute(
            """
            UPDATE auth_sessions
            SET last_seen_at = NOW()
            WHERE id = %s
            """,
            (row[0],),
        )
    return AccessIdentity(
        subject=str(row[1]),
        email=None if row[2] is None else str(row[2]),
        tenant_id=None if row[3] is None else str(row[3]),
        roles=_normalize_roles(row[4]),
        auth_source=f"session:{str(row[6] or 'unknown')}",
        claims=dict(row[5] or {}) if isinstance(row[5], dict) else {},
        session_id=str(row[0]),
    )


def resolve_identity(
    *,
    conn: Connection[Any] | None,
    settings: EnterpriseSettings,
    authorization: str | None,
    x_synapse_session: str | None,
    x_synapse_user: str | None,
    x_synapse_email: str | None,
    x_synapse_tenant_id: str | None,
    x_synapse_roles: str | None,
) -> AccessIdentity:
    session_token = str(x_synapse_session or "").strip() or None
    bearer_token = _extract_bearer_token(authorization)

    if session_token and conn is not None:
        return _resolve_session_identity(conn, session_token)
    if bearer_token and bearer_token.startswith("syns_") and conn is not None:
        return _resolve_session_identity(conn, bearer_token)
    if settings.auth_mode == "oidc":
        if not bearer_token:
            raise HTTPException(status_code=401, detail={"code": "authorization_required"})
        claims = verify_oidc_token(bearer_token, settings)
        return _identity_from_claims(claims, settings, auth_source="oidc")

    subject = str(x_synapse_user or "anonymous").strip() or "anonymous"
    email = str(x_synapse_email or "").strip() or None
    tenant_id = _as_optional_uuid(x_synapse_tenant_id)
    roles = _normalize_roles(x_synapse_roles or "")
    claims: dict[str, Any] = {}
    return AccessIdentity(
        subject=subject,
        email=email,
        tenant_id=tenant_id,
        roles=roles,
        auth_source="header",
        claims=claims,
    )


def create_oidc_session(
    *,
    conn: Connection[Any],
    settings: EnterpriseSettings,
    authorization: str | None,
    requested_ttl_minutes: int | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=400, detail={"code": "auth_mode_not_oidc"})
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "authorization_required"})

    claims = verify_oidc_token(token, settings)
    identity = _identity_from_claims(claims, settings, auth_source="oidc")
    ttl_minutes = settings.oidc_session_ttl_minutes_default
    if requested_ttl_minutes is not None:
        ttl_minutes = max(15, min(settings.oidc_session_ttl_minutes_max, int(requested_ttl_minutes)))
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=ttl_minutes)
    session_token = _generate_session_token()
    session_token_hash = _session_token_hash(session_token)
    session_id = uuid4()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth_sessions (
              id,
              session_token_hash,
              subject,
              email,
              tenant_id,
              roles,
              auth_provider,
              claims,
              metadata,
              issued_at,
              expires_at,
              last_seen_at
            )
            VALUES (
              %s, %s, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                session_id,
                session_token_hash,
                identity.subject,
                identity.email,
                identity.tenant_id,
                list(identity.roles),
                "oidc",
                Jsonb(identity.claims),
                Jsonb(dict(metadata or {})),
                issued_at,
                expires_at,
                issued_at,
            ),
        )
    return {
        "id": str(session_id),
        "session_token": session_token,
        "subject": identity.subject,
        "email": identity.email,
        "tenant_id": identity.tenant_id,
        "roles": list(identity.roles),
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "auth_source": "oidc",
    }


def get_session_payload(conn: Connection[Any], token: str) -> dict[str, Any]:
    token_hash = _session_token_hash(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              id,
              subject,
              email,
              tenant_id::text,
              roles,
              auth_provider,
              issued_at,
              expires_at,
              revoked_at,
              last_seen_at
            FROM auth_sessions
            WHERE session_token_hash = %s
            LIMIT 1
            """,
            (token_hash,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "session_not_found"})
    return {
        "id": str(row[0]),
        "subject": str(row[1]),
        "email": None if row[2] is None else str(row[2]),
        "tenant_id": None if row[3] is None else str(row[3]),
        "roles": list(_normalize_roles(row[4])),
        "auth_provider": str(row[5] or "unknown"),
        "issued_at": None if row[6] is None else row[6].isoformat(),
        "expires_at": None if row[7] is None else row[7].isoformat(),
        "revoked_at": None if row[8] is None else row[8].isoformat(),
        "last_seen_at": None if row[9] is None else row[9].isoformat(),
        "active": bool(row[8] is None and row[7] is not None and row[7] > datetime.now(UTC)),
    }


def revoke_session(conn: Connection[Any], token: str) -> bool:
    token_hash = _session_token_hash(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = NOW()
            WHERE session_token_hash = %s
              AND revoked_at IS NULL
            """,
            (token_hash,),
        )
        updated = cur.rowcount or 0
    return updated > 0


def _required_roles_for_request(method: str, path: str) -> set[str]:
    normalized_method = method.upper().strip()
    normalized_path = str(path or "").strip()
    for policy in _ROUTE_POLICIES:
        if normalized_method not in policy.methods:
            continue
        if policy.pattern.match(normalized_path):
            return set(policy.allowed_roles)
    if normalized_method in _SAFE_METHODS:
        return set()
    if normalized_path.startswith(_AUTH_PATH_PREFIX):
        return set()
    return set(_DEFAULT_ADMIN_ROLES)


def enforce_rbac(settings: EnterpriseSettings, identity: AccessIdentity, *, method: str, path: str) -> None:
    if settings.rbac_mode != "enforce":
        return
    required_roles = _required_roles_for_request(method, path)
    if not required_roles:
        return
    if identity.has_any_role(required_roles):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "rbac_forbidden",
            "required_roles": sorted(required_roles),
            "actor_roles": sorted(identity.roles),
            "path": path,
            "method": method.upper(),
        },
    )


def _collect_project_ids(value: Any, out: set[str], *, depth: int = 0) -> None:
    if depth > 4:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "project_id" and isinstance(item, str):
                project = item.strip()
                if project:
                    out.add(project)
                continue
            _collect_project_ids(item, out, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _collect_project_ids(item, out, depth=depth + 1)
        return


def collect_request_project_ids(*, query_params: dict[str, Any], body_payload: Any) -> set[str]:
    out: set[str] = set()
    query_project = str(query_params.get("project_id") or "").strip()
    if query_project:
        out.add(query_project)
    query_project_ids = str(query_params.get("project_ids") or "").strip()
    if query_project_ids:
        for item in query_project_ids.split(","):
            value = item.strip()
            if value:
                out.add(value)
    _collect_project_ids(body_payload, out, depth=0)
    return out


def enforce_tenancy(
    settings: EnterpriseSettings,
    identity: AccessIdentity,
    *,
    conn: Connection[Any],
    project_ids: set[str],
) -> None:
    if settings.tenancy_mode != "enforce":
        return
    if not project_ids:
        return
    if identity.has_any_role(_DEFAULT_ADMIN_ROLES):
        return
    actor = str(identity.subject or "").strip()
    if not actor:
        raise HTTPException(status_code=401, detail={"code": "identity_subject_required"})

    with conn.cursor() as cur:
        if identity.tenant_id:
            cur.execute(
                """
                SELECT tp.project_id
                FROM tenant_projects tp
                JOIN tenant_memberships tm
                  ON tm.tenant_id = tp.tenant_id
                 AND tm.user_id = %s
                 AND tm.status = 'active'
                WHERE tp.status = 'active'
                  AND tp.tenant_id = %s::uuid
                  AND tp.project_id = ANY(%s)
                """,
                (actor, identity.tenant_id, list(project_ids)),
            )
        else:
            cur.execute(
                """
                SELECT tp.project_id
                FROM tenant_projects tp
                JOIN tenant_memberships tm
                  ON tm.tenant_id = tp.tenant_id
                 AND tm.user_id = %s
                 AND tm.status = 'active'
                WHERE tp.status = 'active'
                  AND tp.project_id = ANY(%s)
                """,
                (actor, list(project_ids)),
            )
        allowed = {str(row[0]) for row in cur.fetchall() or []}
    blocked = sorted(project_ids - allowed)
    if blocked:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "tenant_project_access_denied",
                "subject": actor,
                "blocked_project_ids": blocked,
            },
        )


async def parse_json_body_safe(request: Any) -> Any:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return None
    try:
        raw = await request.body()
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def should_skip_guard(path: str, method: str) -> bool:
    if method.upper() == "OPTIONS":
        return True
    if _is_public_path(path):
        return True
    if path.startswith(_AUTH_PATH_PREFIX):
        return True
    return False
