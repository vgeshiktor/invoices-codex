from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKey


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyMaterial:
    plain_text: str
    key_prefix: str
    key_hash: str


def generate_api_key() -> ApiKeyMaterial:
    plain = secrets.token_urlsafe(32)
    return ApiKeyMaterial(plain_text=plain, key_prefix=plain[:8], key_hash=hash_api_key(plain))


def resolve_tenant_id_from_api_key(session: Session, raw_key: str) -> str | None:
    key_hash = hash_api_key(raw_key)
    api_key = session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    ).scalar_one_or_none()
    if api_key is None or api_key.revoked:
        return None
    return api_key.tenant_id
