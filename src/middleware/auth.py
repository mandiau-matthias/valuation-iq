"""
JWT Authentication Middleware for ValuationIQ

BANK-GRADE SECURITY: Validates JWT tokens with dedicated service account support.

Supports two authentication modes:
1. User Authentication: JWT tokens from Supabase Auth / Titan API (for user-facing requests)
2. Service Authentication: Dedicated service tokens for Titan API → ValuationIQ calls

Integration:
- Titan API: Generates JWT tokens (Supabase Auth + custom JWT + service tokens)
- Mercury/Venus: Frontends that initiate login
- ValuationIQ: Validates tokens and protects endpoints

Token Extraction:
1. HTTP-only cookie (primary, most secure for user auth)
2. Authorization header (for API clients and service-to-service auth)

Security Features:
- Service account whitelist with action-based permissions
- Dedicated service token validation (role=service)
- Request path validation for service accounts
"""

import hashlib
import os
import time
from functools import lru_cache
from typing import Optional, Protocol, Union

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import ClientDisconnect

from src.config import settings
from src.middleware.request_signature import RequestSignatureConfig, verify_hmac_request_signature
from src.middleware.service_permissions import (
    REQUEST_SIGNATURE_MAX_AGE_SECONDS,
    SERVICE_TOKEN_MAX_AGE_SECONDS,
    ServiceAccount,
    extract_action_from_path,
    get_service_allowed_actions,
    validate_service_token_issued_at,
)
from src.security import jwt_hmac

logger = structlog.get_logger(__name__)


class JwtRuntime(Protocol):
    def decode(self, token: str, secret: str, *, algorithms: list[str]) -> dict[str, object]:
        """Decode a JWT payload after verifying its signature."""


@lru_cache(maxsize=1)
def _get_jose_runtime() -> tuple[type[Exception], JwtRuntime, None]:
    """Return the internal HMAC JWT runtime used for shared-secret auth."""
    return jwt_hmac.JWTError, jwt_hmac, None


def _require_jose() -> tuple[type[Exception], JwtRuntime]:
    JWTError, jwt, import_error = _get_jose_runtime()
    if jwt is None or JWTError is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication runtime unavailable: {import_error}",
        )
    return JWTError, jwt


# JWT Configuration (from centralized settings)
JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # For Supabase tokens (optional fallback)

# BANK-GRADE: Request signature configuration
# Service signing secret (for HMAC request verification)
SERVICE_SIGNING_SECRET = os.getenv("SERVICE_SIGNING_SECRET") or JWT_SECRET


def _secret_fingerprint(secret: str) -> str:
    """Non-reversible 8-hex fingerprint of a shared secret.

    Lets ops compare the SERVICE_SIGNING_SECRET/JWT_SECRET configured on Titan
    vs ValuationIQ from logs WITHOUT exposing the secret: a 32-bit prefix of
    SHA-256 is enough for an equality check against a high-entropy secret and
    cannot be brute-forced back to the secret.
    """
    if not secret:
        return "none"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]


# Diagnostics (non-leaking): which env var the verifier secret came from and its
# one-way fingerprint, so a PYTHON-401 "Invalid request signature" can be traced
# to a shared-secret mismatch vs a canonicalization mismatch across services.
SERVICE_SIGNING_SECRET_SOURCE = (
    "SERVICE_SIGNING_SECRET"
    if os.getenv("SERVICE_SIGNING_SECRET")
    else ("JWT_SECRET" if JWT_SECRET else "none")
)
SERVICE_SIGNING_SECRET_FINGERPRINT = _secret_fingerprint(SERVICE_SIGNING_SECRET or "")

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)


def _request_signature_config() -> RequestSignatureConfig:
    """Build request-signature config from the active auth module settings."""
    active_secret = SERVICE_SIGNING_SECRET or ""
    return RequestSignatureConfig(
        secret=active_secret,
        source=SERVICE_SIGNING_SECRET_SOURCE,
        fingerprint=_secret_fingerprint(active_secret),
        max_age_seconds=REQUEST_SIGNATURE_MAX_AGE_SECONDS,
    )


def verify_request_signature(
    request: Request,
    body: bytes,
    *,
    require_signature: bool = False,
) -> bool:
    """
    BANK-GRADE: Verify HMAC request signature for request integrity

    Validates that:
    1. Request has required signature headers
    2. Timestamp is within allowed window (prevents replay attacks)
    3. HMAC signature matches expected value

    Args:
        request: FastAPI request object
        body: Raw request body bytes

    Returns:
        True if signature is valid, False otherwise

    Note: By default this remains an optional compatibility verifier. Service
    authentication paths pass ``require_signature=True`` so internal service
    credentials must also prove request integrity.
    """
    return verify_hmac_request_signature(
        request,
        body,
        config=_request_signature_config(),
        require_signature=require_signature,
        logger=logger,
        now=time.time,
    )


async def require_request_signature(request: Request) -> None:
    """Require a valid HMAC signature on an authenticated service request."""
    if getattr(request.state, "service_signature_verified", False):
        return

    try:
        body = await request.body()
    except ClientDisconnect:
        # Client aborted before the body finished streaming — there is nothing
        # left to respond to. Surface a handled 4xx instead of letting the bare
        # ClientDisconnect bubble up as an unhandled ExceptionGroup traceback
        # (the audit-trail middleware already guards its own body read the same
        # way; this is the last unguarded request.body() on a prod-reachable path).
        logger.debug("Client disconnected before request body was received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client disconnected before request body was received",
        ) from None

    if verify_request_signature(request, body, require_signature=True):
        request.state.service_signature_verified = True
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid request signature",
        headers={"WWW-Authenticate": "Bearer"},
    )


class User:
    """
    User model (matches Titan API structure)

    Attributes:
        id: Unique user identifier
        email: User email address
        name: User full name (optional)
        role: User role (user, admin, etc.)
        email_verified: Whether email is verified
    """

    def __init__(
        self,
        id: str,
        email: str,
        name: Optional[str] = None,
        role: str = "user",
        email_verified: bool = False,
    ):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self.email_verified = email_verified


def extract_token_from_cookie(request: Request) -> Optional[str]:
    """
    Extract JWT from HTTP-only cookie (primary method)

    Cookie name: upswitch_session
    This cookie is set by Titan API on successful login.

    Args:
        request: FastAPI request object

    Returns:
        JWT token string or None if not found
    """
    return request.cookies.get("upswitch_session")


def extract_token_from_header(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """
    Extract JWT from Authorization header (fallback for API clients)

    Header format: Authorization: Bearer <token>

    Args:
        credentials: HTTP Bearer credentials from FastAPI

    Returns:
        JWT token string or None if not provided
    """
    if isinstance(credentials, HTTPAuthorizationCredentials):
        return credentials.credentials
    return None


def extract_bearer_token_from_request(request: Request) -> Optional[str]:
    """Extract a bearer token directly from a request Authorization header."""
    authorization = request.headers.get("authorization")
    if not authorization:
        return None

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None

    stripped_token = token.strip()
    return stripped_token or None


def is_service_token(token: str) -> bool:
    """Return True when a bearer token is a valid ValuationIQ service JWT."""
    JWTError, jwt = _require_jose()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return False

    return payload.get("role") == "service"


def verify_jwt_token(token: str) -> dict[str, object]:
    """
    Verify and decode JWT token

    Supports both:
    1. Custom JWT tokens (from Titan API)
    2. Supabase Auth tokens

    Args:
        token: JWT token string

    Returns:
        Decoded JWT payload as dictionary

    Raises:
        HTTPException: If token is invalid or expired (401)
    """
    JWTError, jwt = _require_jose()

    logger.debug(
        "JWT validation attempt",
        token_length=len(token),
        has_jwt_secret=bool(JWT_SECRET),
        has_supabase_secret=bool(SUPABASE_JWT_SECRET),
    )

    try:
        # Try custom JWT first (Titan API tokens)
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        logger.info(
            "JWT validated with custom secret",
            user_id=payload.get("sub"),
            payload_keys=list(payload.keys()),
        )
        return payload
    except JWTError as e:
        logger.warning(
            "JWT validation with custom secret failed", error=str(e), error_type=type(e).__name__
        )

        # Try Supabase JWT if custom fails
        if SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=[JWT_ALGORITHM])
                logger.info(
                    "JWT validated with Supabase secret",
                    user_id=payload.get("sub"),
                    payload_keys=list(payload.keys()),
                )
                return payload
            except JWTError as e2:
                logger.warning(
                    "JWT validation with Supabase secret also failed",
                    error=str(e2),
                    error_type=type(e2).__name__,
                )

        logger.error(
            "JWT validation failed on both secrets",
            custom_error=str(e),
            has_supabase_fallback=bool(SUPABASE_JWT_SECRET),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_service_token(token: str, request_path: str) -> ServiceAccount:
    """
    BANK-GRADE: Verify and validate service token for service-to-service auth

    This function specifically validates tokens from trusted services (e.g., Titan API).
    It performs additional checks beyond standard JWT validation:

    1. Token signature validation (JWT_SECRET)
    2. Role verification (must be "service")
    3. Service account whitelist check
    4. Action permission validation (based on request path)
    5. Token age validation (prevents replay attacks)

    Args:
        token: JWT token string
        request_path: The request path being accessed (for permission checking)

    Returns:
        ServiceAccount object if valid

    Raises:
        HTTPException: 401 if token is invalid, 403 if service not authorized
    """
    JWTError, jwt = _require_jose()

    try:
        # Decode the token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Check if this is a service token
        role = payload.get("role")
        if role != "service":
            logger.warning(
                "Service auth attempted with non-service token",
                role=role,
                sub=payload.get("sub"),
                path=request_path,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Service authentication required"
            )

        # Get service ID
        service_id_value = payload.get("sub")
        if not isinstance(service_id_value, str) or not service_id_value:
            logger.error("Service token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid service token: missing service ID",
            )
        service_id = service_id_value

        allowed_actions = get_service_allowed_actions(service_id)
        if allowed_actions is None:
            logger.error(
                "Unknown service attempted access", service_id=service_id, path=request_path
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Service '{service_id}' is not authorized",
            )

        # Extract action from request path
        # Path format: /api/v1/valuation/calculate -> "calculate"
        # Path format: /api/v1/conversation/step -> "conversation"
        action = extract_action_from_path(request_path)

        # Check if action is permitted
        if action not in allowed_actions:
            logger.warning(
                "Service attempted unauthorized action",
                service_id=service_id,
                action=action,
                allowed_actions=allowed_actions,
                path=request_path,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Service '{service_id}' is not authorized for action '{action}'",
            )

        # Check token age (replay attack protection)
        try:
            issued_at = validate_service_token_issued_at(payload.get("iat"), int(time.time()))
        except ValueError as exc:
            reason = str(exc)
            logger.warning(
                "Service token rejected by iat policy",
                service_id=service_id,
                reason=reason,
                max_age_seconds=SERVICE_TOKEN_MAX_AGE_SECONDS,
            )
            detail = "Service token expired" if reason == "iat_expired" else "Invalid service token"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail) from exc

        logger.info(
            "Service authenticated successfully",
            service_id=service_id,
            action=action,
            path=request_path,
        )

        return ServiceAccount(id=service_id, allowed_actions=allowed_actions, issued_at=issued_at)

    except JWTError as e:
        logger.error(
            "Service token validation failed",
            error=str(e),
            error_type=type(e).__name__,
            path=request_path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Get current authenticated user

    Extraction order:
    1. HTTP-only cookie (primary, most secure)
    2. Authorization header (fallback for API clients)

    This function is used as a FastAPI dependency:
    ```python
    @router.post("/endpoint")
    async def endpoint(user: User = Depends(get_current_user)):
        # user is guaranteed to be authenticated
        pass
    ```

    Args:
        request: FastAPI request object
        credentials: Optional Bearer token from Authorization header

    Returns:
        User object with authenticated user details

    Raises:
        HTTPException: 401 if no valid authentication found
    """
    # Try cookie first (primary method)
    token = extract_token_from_cookie(request)

    # Fallback to header (for API clients)
    if not token:
        token = extract_token_from_header(credentials)
    if not token:
        # Middleware and tests may call this dependency directly, outside
        # FastAPI's HTTPBearer injection. In that case, read the raw header so
        # auth logging sees the same token the route dependency will validate.
        token = extract_bearer_token_from_request(request)

    if not token:
        logger.info(
            "No authentication token provided", path=request.url.path, method=request.method
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = verify_jwt_token(token)

    # Extract user from payload (matches Titan API structure)
    user_id_value = payload.get("sub")
    raw_email = payload.get("email")
    raw_name = payload.get("name")
    raw_role = payload.get("role", "user")
    email = raw_email if isinstance(raw_email, str) else ""
    name = raw_name if isinstance(raw_name, str) else None
    role = raw_role if isinstance(raw_role, str) else "user"
    email_verified = bool(payload.get("email_verified", False))

    if not isinstance(user_id_value, str) or not user_id_value:
        logger.error("Token missing user ID", payload_keys=list(payload.keys()))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
    user_id = user_id_value

    if role == "service":
        logger.warning(
            "Service token rejected on user-auth path",
            service_id=user_id,
            path=request.url.path,
            method=request.method,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User authentication required",
        )

    user = User(id=user_id, email=email, name=name, role=role, email_verified=email_verified)

    logger.info(
        "User authenticated",
        user_id=user.id,
        has_email=bool(user.email),
        path=request.url.path,
        method=request.method,
    )

    return user


async def get_current_user_optional(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Get current user (optional) - returns None if not authenticated

    Useful for endpoints that work with or without auth:
    ```python
    @router.get("/endpoint")
    async def endpoint(user: Optional[User] = Depends(get_current_user_optional)):
        if user:
            # Personalized response for authenticated users
            pass
        else:
            # Generic response for anonymous users
            pass
    ```

    Args:
        request: FastAPI request object
        credentials: Optional Bearer token from Authorization header

    Returns:
        User object if authenticated, None otherwise
    """
    token = (
        extract_token_from_cookie(request)
        or extract_token_from_header(credentials)
        or extract_bearer_token_from_request(request)
    )
    if not token:
        return None

    try:
        if is_service_token(token):
            return None
    except HTTPException:
        return None

    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


# Convenience aliases for FastAPI dependencies
async def require_auth(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    FastAPI dependency for protected routes

    Usage:
    ```python
    from src.middleware.auth import require_auth, User

    @router.post("/protected-endpoint")
    async def protected_endpoint(user: User = Depends(require_auth)):
        # user is guaranteed to be authenticated
        pass
    ```
    """
    return await get_current_user(request, credentials)


async def optional_auth(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    FastAPI dependency for optional auth

    Usage:
    ```python
    from src.middleware.auth import optional_auth, User

    @router.get("/optional-endpoint")
    async def optional_endpoint(user: Optional[User] = Depends(optional_auth)):
        if user:
            # Authenticated user
            pass
        else:
            # Anonymous user
            pass
    ```
    """
    return await get_current_user_optional(request, credentials)


# ============================================================================
# BANK-GRADE: Service-to-Service Authentication
# ============================================================================


async def require_service_auth(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> ServiceAccount:
    """
    BANK-GRADE: FastAPI dependency for service-to-service authentication

    This dependency validates that the request comes from an authorized service
    (e.g., Titan API calling ValuationIQ).

    Security Features:
    - Service account whitelist verification
    - Action-based permission checking
    - Token age validation (replay attack protection)

    Usage:
    ```python
    from src.middleware.auth import require_service_auth, ServiceAccount

    @router.post("/internal-endpoint")
    async def internal_endpoint(service: ServiceAccount = Depends(require_service_auth)):
        # Only authorized services can call this endpoint
        # service.id contains the service identifier (e.g., "titan-api-service")
        pass
    ```

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header

    Returns:
        ServiceAccount if authenticated and authorized

    Raises:
        HTTPException: 401 if token is invalid, 403 if service not authorized
    """
    # Extract token from Authorization header (services use header, not cookie)
    token = extract_token_from_header(credentials) or extract_bearer_token_from_request(request)

    if not token:
        logger.warning(
            "Service auth: No token provided", path=request.url.path, method=request.method
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify service token with path-based permission check, then require
    # request integrity so bearer replay without the signing secret is rejected.
    service = verify_service_token(token, request.url.path)
    await require_request_signature(request)
    return service


async def require_auth_or_service(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Union[User, ServiceAccount]:
    """
    BANK-GRADE: FastAPI dependency that accepts either user or service auth

    This is useful for endpoints that can be called by both:
    - End users (with user JWT)
    - Internal services (with service JWT)

    Usage:
    ```python
    from src.middleware.auth import require_auth_or_service, User, ServiceAccount

    @router.post("/flexible-endpoint")
    async def flexible_endpoint(
        auth: Union[User, ServiceAccount] = Depends(require_auth_or_service)
    ):
        if isinstance(auth, ServiceAccount):
            # Called by internal service
            pass
        else:
            # Called by user
            pass
    ```

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header

    Returns:
        User or ServiceAccount depending on token type

    Raises:
        HTTPException: 401 if no valid authentication found
    """
    header_token = extract_token_from_header(credentials) or extract_bearer_token_from_request(
        request
    )
    cookie_token = extract_token_from_cookie(request)

    if not header_token and not cookie_token:
        logger.info(
            "No authentication token provided", path=request.url.path, method=request.method
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Service credentials are accepted from the Authorization header only.
    # Cookie-carried tokens always go through the user-auth flow.
    if header_token and is_service_token(header_token):
        service = verify_service_token(header_token, request.url.path)
        await require_request_signature(request)
        return service

    return await get_current_user(request, credentials)
