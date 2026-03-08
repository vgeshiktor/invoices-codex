from __future__ import annotations

from typing import Dict, Optional, Set


def duplicate_by_hash(digest: str, known_hashes: Set[str]) -> bool:
    return digest in known_hashes


def duplicate_of_hash(digest: str, hash_to_path: Dict[str, str]) -> Optional[str]:
    return hash_to_path.get(digest)


def remember_hash(
    digest: str, path: str, known_hashes: Set[str], hash_to_path: Dict[str, str]
) -> None:
    known_hashes.add(digest)
    hash_to_path[digest] = path


def duplicate_by_text_fingerprint(fingerprint: Optional[str], seen_fingerprints: Set[str]) -> bool:
    return bool(fingerprint and fingerprint in seen_fingerprints)


def duplicate_of_text(
    fingerprint: Optional[str], fingerprint_to_path: Dict[str, str]
) -> Optional[str]:
    if not fingerprint:
        return None
    return fingerprint_to_path.get(fingerprint)


def remember_text_fingerprint(
    fingerprint: Optional[str],
    path: str,
    seen_fingerprints: Set[str],
    fingerprint_to_path: Dict[str, str],
) -> None:
    if not fingerprint:
        return
    seen_fingerprints.add(fingerprint)
    fingerprint_to_path[fingerprint] = path


def duplicate_by_stem(stem: str, seen_stems: Set[str]) -> bool:
    return stem in seen_stems


def remember_stem(stem: str, seen_stems: Set[str]) -> None:
    seen_stems.add(stem)
