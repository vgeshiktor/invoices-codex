from __future__ import annotations

import argparse
import os

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import Base
from invplatform.saas.worker import run_report_retention_cleanup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SaaS report retention cleanup.")
    parser.add_argument(
        "--database-url",
        default="sqlite:///./invoices_saas.db",
        help="SQLAlchemy database URL (default: sqlite:///./invoices_saas.db)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Delete reports older than this many days (default: 30).",
    )
    parser.add_argument(
        "--storage-url",
        default="local://./data/saas_storage",
        help="Storage backend URL (default: local://./data/saas_storage).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = build_engine(args.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine)
    os.environ["SAAS_STORAGE_URL"] = args.storage_url
    deleted = run_report_retention_cleanup(
        session_factory=session_factory,
        retention_days=args.retention_days,
    )
    print(f"deleted_reports={deleted}")


if __name__ == "__main__":
    main()
