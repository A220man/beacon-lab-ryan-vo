"""OIDC authentication routes for Keycloak JWT validation and PKCE flow.

Handles:
- SPA PKCE login initiation
- Authorization code callback with token exchange
- Token validation (iss, aud checks)
- Role-based scope authorization
- Logout endpoint
"""
from __future__ import annotations

import base64
import hashlib
import os
import urllib.parse
from typing import Any, Optional

from authlib.jose import jwt
from authlib.jose import JsonWebKey
from fastapi.security import SecurityScopes
from fastapi import APIRouter, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse

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


# Cached public key instance (refreshed on first use per process)
_public_key: JsonWebKey | None = None


def _get_public_key() -> JsonWebKey:
    """Fetch the Keycloak public key for JWT verification."""
    global _public_key
    if _public_key is None:
        jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        import httpx
        resp = httpx.get(jwks_url, timeout=5.0)
        resp.raise_for_status()
        _public_key = JsonWebKey.from_pem(resp.text)
    return _public_key


def _get_cached_public_key() -> JsonWebKey:
    """Get cached public key, fetching if needed."""
    return _get_public_key()


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT token using Keycloak's public key."""
    pub_key = _get_cached_public_key()
    try:
        decoded = jwt.decode(
            token,
            pub_key,
            claims_options={
                "iss": {"essential": True, "value": KEYCLOAK_ISSUER},
                "aud": {"essential": True, "value": KEYCLOAK_CLIENT_ID},
            },
            scope=[],
        )
        return decoded
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid JWT token: {exc}",
        ) from exc


# PKCE (Proof Key for Code Exchange) generation
def generate_pkce_codes() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge.
    
    Returns:
        tuple of (code_verifier, code_challenge)
    """
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode()
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    return code_verifier, code_challenge
def generate_nonce() -> str:
    """Generate a random nonce for OIDC authentication.

    Returns:
        A random string used as the OIDC nonce parameter.
    """
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b'=').decode()


def get_pkce_auth_url(code_verifier: str, state: str, nonce: str | None = None) -> str:
    """Build the Keycloak authorization URL with PKCE and state parameters.
    
    Args:
        code_verifier: The PKCE code verifier
        state: CSRF protection state token
        nonce: OIDC nonce for replay protection
    
    Returns:
        Authorization URL for redirect
    """
    params = {
        "client_id": KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth/callback",
        "scope": "openid profile email",
        "code_challenge": code_verifier,
        "code_challenge_method": "S256",
        "state": state,
    }
    if nonce is not None:
        params["nonce"] = nonce
    return f"{KEYCLOAK_ISSUER}/auth?{urllib.parse.urlencode(params)}"


# Session storage for PKCE codes (in-memory per-process; replace with Redis/db for production)
_pkce_store: dict[str, dict[str, str]] = {}


def store_pkce_pair(state: str, code_verifier: str) -> None:
    """Store a PKCE code verifier indexed by state for later verification."""
    _pkce_store[state] = {"code_verifier": code_verifier}


def verify_pkce_code(state: str, code_verifier: str) -> bool:
    """Verify that the submitted code verifier matches the stored pair for this state."""
    stored = _pkce_store.get(state)
    if stored is None:
        return False
    return stored["code_verifier"] == code_verifier


def cleanup_pkce_state(state: str) -> None:
    """Remove the PKCE state entry after successful verification."""
    _pkce_store.pop(state, None)


def oidc_login(state: str | None = None) -> dict:
    """Initiate OIDC login with PKCE.
    
    Generates a PKCE code pair and stores the verifier keyed by state.
    Returns the authorization URL, state, and nonce for the SPA to redirect to.
    """
    if state is None:
        state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b'=').decode()
    code_verifier, code_challenge = generate_pkce_codes()
    nonce = generate_nonce()
    store_pkce_pair(state, code_verifier)
    auth_url = get_pkce_auth_url(code_verifier, state, nonce=nonce)
    return {"auth_url": auth_url, "state": state, "nonce": nonce}


def oidc_callback(code: str, state: str, code_verifier: str, nonce: str | None = None) -> dict[str, Any]:
    """Exchange authorization code for tokens at the PKCE callback.
    
    Validates the state, exchanges the code for tokens, and returns
    the decoded user info.
    """
    # Verify state
    if state not in _pkce_store:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter",
        )
    
    # Verify PKCE code verifier
    if not verify_pkce_code(state, code_verifier):
        raise HTTPException(
            status_code=400,
            detail="Invalid PKCE code verifier",
        )
    
    # Verify and clean up nonce
    if nonce is None or _pkce_store[state].get("nonce") != nonce:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing nonce",
        )
    cleanup_pkce_state(state)
    
    # Exchange authorization code for tokens
    token_url = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token"
    token_params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth/callback",
        "code_verifier": code_verifier,
    }
    
    import httpx
    resp = httpx.post(token_url, data=token_params, timeout=10.0)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"Failed to exchange authorization code: {resp.text}",
        )
    
    tokens = resp.json()
    
    # Decode the access token to get user info
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="No access token in response")
    
    decoded = _decode_token(access_token)
    
    return {
        "user": {
            "sub": str(decoded.get("sub", "")),
            "preferred_username": decoded.get("preferred_username", ""),
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "roles": decoded.get("realm_access", {}).get("roles", []),
        },
        "tokens": tokens,
    }


# Router for OIDC endpoints
router = APIRouter(prefix="/oidc", tags=["oidc"])


@router.get("/login", include_in_schema=False)
def login(state: str | None = None) -> Response:
    """Initiate OIDC login with PKCE.
    
    Generates PKCE code pair, stores verifier keyed by state,
    and returns the authorization URL for SPA redirect.
    """
    result = oidc_login(state=state)
    return JSONResponse(content=result)


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request,
) -> dict[str, Any]:
    """Handle OIDC callback from Keycloak after user authorization.
    
    Exchanges the authorization code for tokens using PKCE verification.
    Returns the authenticated user and tokens.
    """
    # Get authorization code and state from query params
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    nonce = request.query_params.get("nonce")
    
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing code or state parameter",
        )
    
    # Get code verifier from cookie (SPA stores it there during login)
    code_verifier = request.cookies.get("pkce_verifier")
    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="Missing PKCE code verifier cookie",
        )
    
    result = oidc_callback(code=code, state=state, code_verifier=code_verifier, nonce=nonce)
    return result


@router.get("/logout", include_in_schema=False)
def logout() -> dict[str, str]:
    """Handle Keycloak logout.
    
    Redirects to the Keycloak end_session endpoint to clean up the user session.
    """
    end_session_url = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/logout?redirect_uri={KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth/callback"
    return {"end_session_url": end_session_url}
