from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKey


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyMaterial:
    plain_text: str
    key_prefix: str
    key_hash: str


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    tenant_id: str
    membership_id: str
    session_id: str
    exp: int


def generate_api_key() -> ApiKeyMaterial:
    plain = secrets.token_urlsafe(32)
    return ApiKeyMaterial(plain_text=plain, key_prefix=plain[:8], key_hash=hash_api_key(plain))


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def slugify_tenant_name(raw_name: str) -> str:
    value = raw_name.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        return "tenant"
    return value[:64]


def hash_password(password: str, iterations: int = 120_000) -> str:
    if not password:
        raise ValueError("password cannot be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt=salt, iterations=iterations
    )
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.urlsafe_b64encode(salt).decode('ascii')}$"
        f"{base64.urlsafe_b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algo, iter_raw, salt_raw, digest_raw = encoded_hash.split("$", maxsplit=3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_raw)
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
    except Exception:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt=salt, iterations=iterations
    )
    return hmac.compare_digest(candidate, expected)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + pad).encode("ascii"))


def issue_access_token(
    *,
    secret: str,
    user_id: str,
    tenant_id: str,
    membership_id: str,
    session_id: str,
    expires_at: datetime,
) -> str:
    exp = int(expires_at.replace(tzinfo=timezone.utc).timestamp())
    payload = {
        "v": 1,
        "sub": user_id,
        "tid": tenant_id,
        "mid": membership_id,
        "sid": session_id,
        "exp": exp,
        "jti": secrets.token_hex(8),
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    signature_b64 = _b64url_encode(signature.digest())
    return f"v1.{payload_b64}.{signature_b64}"


def decode_access_token(
    token: str, *, secret: str, now: datetime | None = None
) -> tuple[AccessTokenClaims | None, str | None]:
    if not token:
        return None, "missing"
    try:
        version, payload_b64, signature_b64 = token.split(".", maxsplit=2)
        if version != "v1":
            return None, "invalid"
        expected_sig = hmac.new(
            secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
        ).digest()
        parsed_sig = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, parsed_sig):
            return None, "invalid"
        payload = json.loads(_b64url_decode(payload_b64))
        claims = AccessTokenClaims(
            user_id=str(payload["sub"]),
            tenant_id=str(payload["tid"]),
            membership_id=str(payload["mid"]),
            session_id=str(payload["sid"]),
            exp=int(payload["exp"]),
        )
    except Exception:
        return None, "invalid"

    now_ts = int((now or datetime.now(timezone.utc)).timestamp())
    if claims.exp <= now_ts:
        return None, "expired"
    return claims, None


def resolve_tenant_id_from_api_key(session: Session, raw_key: str) -> str | None:
    key_hash = hash_api_key(raw_key)
    api_key = session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    ).scalar_one_or_none()
    if api_key is None or api_key.revoked:
        return None
    return api_key.tenant_id
