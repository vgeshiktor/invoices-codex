from __future__ import annotations

from pathlib import Path

import pytest

from invplatform.saas.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    build_storage,
    parse_s3_storage_url,
)


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objects[f"{Bucket}/{Key}"] = bytes(Body)

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        return {"Body": _FakeBody(self.objects[f"{Bucket}/{Key}"])}

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop(f"{Bucket}/{Key}", None)


def test_local_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorageBackend(tmp_path / "storage")
    stored = storage.save_bytes("uploads/t1/file.pdf", b"hello")
    assert stored.key == "uploads/t1/file.pdf"
    assert stored.size == 5
    assert storage.read_bytes(stored.key) == b"hello"
    assert storage.resolve_local_path(stored.key).exists()
    storage.delete(stored.key)
    assert not storage.resolve_local_path(stored.key).exists()


def test_build_storage_supports_local_url(tmp_path: Path) -> None:
    storage = build_storage(f"local://{tmp_path / 'root'}")
    stored = storage.save_bytes("a/b.bin", b"abc")
    assert stored.size == 3


def test_build_storage_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError):
        build_storage("ftp://example.com/path")


def test_parse_s3_storage_url() -> None:
    config = parse_s3_storage_url(
        "s3://invoice-bucket/prefix/path?region=us-east-1&endpoint_url=https://s3.local"
    )
    assert config.bucket == "invoice-bucket"
    assert config.prefix == "prefix/path"
    assert config.region_name == "us-east-1"
    assert config.endpoint_url == "https://s3.local"


def test_s3_storage_roundtrip_with_fake_client(tmp_path: Path) -> None:
    fake = _FakeS3Client()
    storage = S3StorageBackend(
        bucket="invoices",
        prefix="tenant-a",
        client=fake,
        local_cache_dir=tmp_path / "cache",
    )
    stored = storage.save_bytes("reports/r1.json", b'{"ok":true}')
    assert stored.size == len(b'{"ok":true}')
    assert stored.key == "reports/r1.json"
    assert storage.read_bytes("reports/r1.json") == b'{"ok":true}'

    local_path = storage.resolve_local_path("reports/r1.json")
    assert local_path.exists()
    assert local_path.read_bytes() == b'{"ok":true}'

    storage.delete("reports/r1.json")
    assert not local_path.exists()
