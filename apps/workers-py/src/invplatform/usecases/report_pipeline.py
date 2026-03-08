from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, TypeVar


RecordT = TypeVar("RecordT")


def parse_path(
    path: Path,
    *,
    debug: bool = False,
    parse_invoice_fn: Callable[[Path, bool], RecordT],
    split_municipal_multi_invoice_fn: Callable[[Path, RecordT, bool], List[RecordT]],
) -> List[RecordT]:
    record = parse_invoice_fn(path, debug)
    return split_municipal_multi_invoice_fn(path, record, debug)


def parse_paths(
    paths: Iterable[Path],
    *,
    debug: bool = False,
    parse_invoice_fn: Callable[[Path, bool], RecordT],
    split_municipal_multi_invoice_fn: Callable[[Path, RecordT, bool], List[RecordT]],
) -> List[RecordT]:
    records: List[RecordT] = []
    for path in paths:
        records.extend(
            parse_path(
                path,
                debug=debug,
                parse_invoice_fn=parse_invoice_fn,
                split_municipal_multi_invoice_fn=split_municipal_multi_invoice_fn,
            )
        )
    return records
