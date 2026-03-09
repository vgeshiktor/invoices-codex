from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Protocol
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    sha256: str


class StorageBackend(Protocol):
    def save_bytes(self, key: str, data: bytes) -> StoredObject: ...

    def read_bytes(self, key: str) -> bytes: ...

    def resolve_local_path(self, key: str) -> Path: ...

    def delete(self, key: str) -> None: ...


def _normalize_key(key: str) -> str:
    return key.lstrip("/").replace("..", "_")


class LocalStorageBackend:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, key: str) -> Path:
        safe_key = _normalize_key(key)
        return self.root / safe_key

    def save_bytes(self, key: str, data: bytes) -> StoredObject:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest())

    def read_bytes(self, key: str) -> bytes:
        return self._abs(key).read_bytes()

    def resolve_local_path(self, key: str) -> Path:
        return self._abs(key)

    def delete(self, key: str) -> None:
        path = self._abs(key)
        if path.exists():
            path.unlink()


class S3StorageBackend:
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        client: object | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        local_cache_dir: Path | None = None,
    ):
        if not bucket:
            raise ValueError("s3 bucket is required")
        self.bucket = bucket
        self.prefix = _normalize_key(prefix).rstrip("/")
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self._client = client or self._build_client(
            endpoint_url=endpoint_url, region_name=region_name
        )
        self.cache_dir = local_cache_dir or (Path(tempfile.gettempdir()) / "invplatform_s3_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _build_client(self, endpoint_url: str | None, region_name: str | None) -> object:
        try:
            import boto3  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("boto3 is required for s3 storage backend") from exc
        return boto3.client("s3", endpoint_url=endpoint_url, region_name=region_name)

    def _client_obj(self) -> object:
        return self._client

    def _object_key(self, key: str) -> str:
        safe_key = _normalize_key(key)
        if not self.prefix:
            return safe_key
        return f"{self.prefix}/{safe_key}"

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(self._object_key(key).encode("utf-8")).hexdigest()
        ext = Path(key).suffix
        return self.cache_dir / f"{digest}{ext}"

    def save_bytes(self, key: str, data: bytes) -> StoredObject:
        object_key = self._object_key(key)
        client = self._client_obj()
        # boto3 client is dynamically typed.
        getattr(client, "put_object")(Bucket=self.bucket, Key=object_key, Body=data)
        return StoredObject(key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest())

    def read_bytes(self, key: str) -> bytes:
        object_key = self._object_key(key)
        client = self._client_obj()
        response = getattr(client, "get_object")(Bucket=self.bucket, Key=object_key)
        body = response["Body"].read()
        return bytes(body)

    def resolve_local_path(self, key: str) -> Path:
        path = self._cache_path(key)
        if path.exists():
            return path
        data = self.read_bytes(key)
        path.write_bytes(data)
        return path

    def delete(self, key: str) -> None:
        object_key = self._object_key(key)
        client = self._client_obj()
        getattr(client, "delete_object")(Bucket=self.bucket, Key=object_key)
        cached = self._cache_path(key)
        if cached.exists():
            cached.unlink()


@dataclass(frozen=True)
class S3StorageConfig:
    bucket: str
    prefix: str
    endpoint_url: str | None
    region_name: str | None


def parse_s3_storage_url(storage_url: str) -> S3StorageConfig:
    parsed = urlparse(storage_url)
    if parsed.scheme != "s3":
        raise ValueError(f"not an s3 url: {storage_url}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    endpoint_url = qs.get("endpoint_url", [None])[0]
    region_name = qs.get("region", [None])[0]
    return S3StorageConfig(
        bucket=bucket,
        prefix=prefix,
        endpoint_url=endpoint_url,
        region_name=region_name,
    )


def build_storage(storage_url: str | None = None) -> StorageBackend:
    url = storage_url or "local://./data/saas_storage"
    if url.startswith("local://"):
        return LocalStorageBackend(Path(url.removeprefix("local://")))
    if url.startswith("s3://"):
        config = parse_s3_storage_url(url)
        return S3StorageBackend(
            bucket=config.bucket,
            prefix=config.prefix,
            endpoint_url=config.endpoint_url,
            region_name=config.region_name,
        )
    raise ValueError(f"unsupported storage url: {url}")
