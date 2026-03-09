from __future__ import annotations

import argparse
import os

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import Base
from invplatform.saas.worker import run_parse_job


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one SaaS parse job by id.")
    parser.add_argument("parse_job_id", help="Parse job id")
    parser.add_argument(
        "--database-url",
        default="sqlite:///./invoices_saas.db",
        help="SQLAlchemy database URL (default: sqlite:///./invoices_saas.db)",
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
    status = run_parse_job(session_factory=session_factory, parse_job_id=args.parse_job_id)
    print(f"{args.parse_job_id}: {status.value}")


if __name__ == "__main__":
    main()
