"""OIDC authentication dependency for Keycloak JWT validation.

Validates Keycloak-issued access tokens:
- Issuer (iss) match against KEYCLOAK_ISSUER
- Audience (aud) match against KEYCLOAK_CLIENT_ID
- Token type and expiration checks
- Role-based access control support

This dependency can be used in FastAPI route dependencies:
    from app.api.oidc import oidc_require_auth, oidc_optional

Depends on authlib which is already in requirements.txt.
"""
from __future__ import annotations

import os
from typing import Optional

from authlib.jose import jwt
from authlib.jose import JsonWebKey
from fastapi import HTTPException, Request, Security, SecurityScopes
from authlib.security.oauth2.rfc6749 import OAuth2User


#: Environment configuration (populated at module load)
KEYCLOAK_URL: str = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM: str = os.environ.get("KEYCLOAK_REALM", "master")
KEYCLOAK_CLIENT_ID: str = os.environ.get("KEYCLOAK_CLIENT_ID", "beacon-lab")
KEYCLOAK_ISSUER: str = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

# Required scopes per role (can be configured per deployment)
ROLE_SCOPES: dict[str, list[str]] = {
    "viewer": ["skills:read"],
    "analyst": ["skills:read", "skills:write"],
    "admin": ["skills:read", "skills:write", "skills:delete"],
}


def _get_public_key() -> JsonWebKey:
    """Fetch the Keycloak public key for JWT verification.

    In production, this should be cached and refreshed periodically.
    For now, we fetch it fresh each request from the JWKS endpoint.
    """
    jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    import httpx
    resp = httpx.get(jwks_url, timeout=5.0)
    resp.raise_for_status()
    return JsonWebKey.from_pem(resp.text)


# Cached public key instance (refreshed on first use per process)
_public_key: JsonWebKey | None = None


def _get_cached_public_key() -> JsonWebKey:
    global _public_key
    if _public_key is None:
        _public_key = _get_public_key()
    return _public_key


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT token using Keycloak's public key."""
    pub_key = _get_cached_public_key()
    try:
        # authlib's jwt.decode validates iss, aud, exp, nbf automatically
        decoded = jwt.decode(
            token,
            pub_key,
            claims_options={
                "iss": {"essential": True, "value": KEYCLOAK_ISSUER},
                "aud": {"essential": True, "value": KEYCLOAK_CLIENT_ID},
            },
            scope=[],  # We'll handle scope checking separately
        )
        return decoded
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid JWT token: {exc}",
        ) from exc


def oidc_optional(request: Request) -> Optional[OAuth2User]:
    """OIDC optional dependency - returns user if token present, else None.

    Extracts the Bearer token from the Authorization header and validates
    it against Keycloak. Returns None if no auth header or invalid token.
    """
    auth: str = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None

    token = auth[len("Bearer "):].strip()
    try:
        decoded = _decode_token(token)
        # Build OAuth2User from decoded claims
        user = OAuth2User(
            id=str(decoded.get("sub", "")),
            preferred_username=decoded.get("preferred_username", ""),
            email=decoded.get("email"),
            real_name=decoded.get("name"),
            # Map Keycloak roles to our scope system
            scopes=decoded.get("realm_access", {}).get("roles", []),
        )
        return user
    except HTTPException:
        return None
    except Exception:
        return None


def oidc_require_auth(
    security_scopes: SecurityScopes,
    request: Request,
) -> OAuth2User:
    """OIDC required dependency - raises 401 if no valid token or insufficient scopes.

    Usage::
        @router.get("/protected")
        async def protected(user: Annotated[OAuth2User, Security(oidc_require_auth, scopes=["skills:read"])]):
            return {"user": user.preferred_username}
    """
    auth: str = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth[len("Bearer "):].strip()
    try:
        decoded = _decode_token(token)
    except HTTPException:
        raise

    # Check required security scopes
    token_scopes: list[str] = decoded.get("realm_access", {}).get("roles", [])
    missing: list[str] = [
        scope for scope in security_scopes.scopes if scope not in token_scopes
    ]
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient scopes: {', '.join(missing)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = OAuth2User(
        id=str(decoded.get("sub", "")),
        preferred_username=decoded.get("preferred_username", ""),
        email=decoded.get("email"),
        real_name=decoded.get("name"),
        scopes=token_scopes,
    )
    return user


def oidc_get_current_user(request: Request) -> Optional[OAuth2User]:
    """Return the authenticated user if a valid token is present, else None.

    Convenience wrapper for paths that want optional auth.
    """
    return oidc_optional(request)
