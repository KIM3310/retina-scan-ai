"""OIDC integration for federated authentication.

Validates ID tokens from a hospital IdP (Keycloak / Okta / Azure AD), maps
IdP group membership to application roles, and establishes a session bound
to a purpose-of-use declaration.

This module is research code. Before production:
- Penetration test the token validation flow.
- Audit replay-protection and signature verification.
- Verify the role-mapping against compliance officer's written policy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

try:
    # In a real deployment, use `authlib` or `python-jose` for JWT handling.
    # We import lazily so this module imports cleanly without the dep.
    from authlib.integrations.requests_client import OAuth2Session  # type: ignore
    from authlib.jose import JsonWebToken, JsonWebKey  # type: ignore
    _AUTHLIB_AVAILABLE = True
except ImportError:  # pragma: no cover — production needs this dependency
    _AUTHLIB_AVAILABLE = False

from access.roles import Role, PurposeOfUse


@dataclass
class OIDCConfig:
    issuer: str
    client_id: str
    client_secret: str
    discovery_url: str  # typically f"{issuer}/.well-known/openid-configuration"
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email", "groups"])
    group_claim: str = "groups"
    role_mapping: dict[str, Role] = field(default_factory=dict)
    allowed_purposes: list[PurposeOfUse] = field(
        default_factory=lambda: list(PurposeOfUse)
    )
    session_ttl_seconds: int = 8 * 3600
    jwks_cache_seconds: int = 3600


@dataclass
class Session:
    session_id: str
    user_id: str
    display_name: str
    email: str
    role: Role
    purpose: PurposeOfUse
    mfa_verified_at: float  # unix timestamp
    expires_at: float
    issued_at: float
    source_ip: str | None = None
    user_agent: str | None = None
    break_glass_active: bool = False
    break_glass_reason: str | None = None


class OIDCClient:
    """OIDC client wiring.

    Typical flow:
        client = OIDCClient(config)
        authorization_url, state = client.authorization_url(redirect_uri, purpose)
        # ... redirect user to IdP, user returns with code ...
        session = client.complete_login(code, state, redirect_uri)
        # store session in your session store
    """

    def __init__(self, config: OIDCConfig) -> None:
        if not _AUTHLIB_AVAILABLE:
            raise RuntimeError(
                "oidc_integration requires the `authlib` and `requests` packages. "
                "Install via: pip install authlib requests"
            )
        self.config = config
        self._jwks: Any = None
        self._jwks_fetched_at: float = 0.0
        self._oauth_metadata: Any = None

    # -------------------------------------------------
    # Authorization URL construction (start of flow)
    # -------------------------------------------------
    def authorization_url(
        self, redirect_uri: str, purpose: PurposeOfUse
    ) -> tuple[str, str]:
        """Return (authorization_url, state).

        Include purpose as a custom parameter so the user's purpose-of-use
        declaration is audited at the IdP side as well.
        """
        session = OAuth2Session(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scope=" ".join(self.config.scopes),
        )
        metadata = self._discovery()
        url, state = session.create_authorization_url(
            metadata["authorization_endpoint"],
            redirect_uri=redirect_uri,
            kwargs={"purpose_of_use": purpose.value},
        )
        return url, state

    # -------------------------------------------------
    # Code exchange and session establishment
    # -------------------------------------------------
    def complete_login(
        self,
        code: str,
        state: str,
        redirect_uri: str,
        source_ip: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        session = OAuth2Session(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=redirect_uri,
        )
        metadata = self._discovery()
        token = session.fetch_token(
            metadata["token_endpoint"],
            code=code,
            state=state,
        )

        id_token = token["id_token"]
        claims = self._validate_and_decode(id_token)

        role = self._map_role(claims.get(self.config.group_claim, []))
        purpose_str = claims.get("purpose_of_use") or PurposeOfUse.TREATMENT.value
        purpose = PurposeOfUse(purpose_str)

        now = time.time()
        import uuid

        return Session(
            session_id="sess_" + uuid.uuid4().hex,
            user_id=claims.get("sub", ""),
            display_name=claims.get("name", ""),
            email=claims.get("email", ""),
            role=role,
            purpose=purpose,
            mfa_verified_at=now if claims.get("amr") and "mfa" in claims["amr"] else 0.0,
            issued_at=now,
            expires_at=now + self.config.session_ttl_seconds,
            source_ip=source_ip,
            user_agent=user_agent,
        )

    # -------------------------------------------------
    # Validation helpers
    # -------------------------------------------------
    def _validate_and_decode(self, id_token: str) -> dict:
        jwks = self._get_jwks()
        jwt = JsonWebToken(["RS256", "ES256", "PS256"])
        claims = jwt.decode(
            id_token,
            key=jwks,
            claims_options={
                "iss": {"essential": True, "value": self.config.issuer},
                "aud": {"essential": True, "value": self.config.client_id},
                "exp": {"essential": True},
            },
        )
        claims.validate()
        return dict(claims)

    def _get_jwks(self) -> Any:
        if self._jwks is None or (time.time() - self._jwks_fetched_at) > self.config.jwks_cache_seconds:
            metadata = self._discovery()
            import requests

            resp = requests.get(metadata["jwks_uri"], timeout=10)
            resp.raise_for_status()
            self._jwks = JsonWebKey.import_key_set(resp.json())
            self._jwks_fetched_at = time.time()
        return self._jwks

    def _discovery(self) -> dict:
        if self._oauth_metadata is None:
            import requests

            resp = requests.get(self.config.discovery_url, timeout=10)
            resp.raise_for_status()
            self._oauth_metadata = resp.json()
        return self._oauth_metadata

    def _map_role(self, groups: list[str]) -> Role:
        for group in groups:
            if group in self.config.role_mapping:
                return self.config.role_mapping[group]
        raise PermissionError("User has no role mapping for known groups: " + ", ".join(groups))


# -----------------------------
# Example configs (copy into your deployment config)
# -----------------------------

EXAMPLE_KEYCLOAK_CONFIG = """
oidc:
  issuer: https://idp.hospital.example.com/realms/clinical
  client_id: retina-scan-ai
  client_secret_ref: vault:secret/retina/oidc#client_secret
  discovery_url: https://idp.hospital.example.com/realms/clinical/.well-known/openid-configuration
  scopes: [openid, profile, email, groups]
  group_claim: groups
  role_mapping:
    radiology-physicians: Radiologist
    ophthalmology-physicians: Ophthalmologist
    radiology-techs: Technician
    research-team: Researcher
    compliance-team: ComplianceOfficer
    system-admins: SystemAdmin
"""

EXAMPLE_OKTA_CONFIG = """
oidc:
  issuer: https://hospital.okta.com
  client_id: 0oabc...
  client_secret_ref: vault:secret/retina/oidc#client_secret
  discovery_url: https://hospital.okta.com/.well-known/openid-configuration
  scopes: [openid, profile, email, groups]
  group_claim: groups
  role_mapping:
    Radiology: Radiologist
    Ophthalmology: Ophthalmologist
    # ...
"""

EXAMPLE_AZURE_AD_CONFIG = """
oidc:
  issuer: https://login.microsoftonline.com/TENANT_ID/v2.0
  client_id: app-registration-guid
  client_secret_ref: vault:secret/retina/oidc#client_secret
  discovery_url: https://login.microsoftonline.com/TENANT_ID/v2.0/.well-known/openid-configuration
  scopes: [openid, profile, email, "User.Read"]
  group_claim: groups   # requires Azure AD group claims config
  role_mapping:
    RadiologyGroupObjectId: Radiologist
    # ...
"""
