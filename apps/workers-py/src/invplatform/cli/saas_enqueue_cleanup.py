from __future__ import annotations

import argparse

from invplatform.saas.db import build_engine, build_session_factory
from invplatform.saas.models import Base
from invplatform.saas.queue import build_queue
from invplatform.saas.service import SaaSService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enqueue SaaS report cleanup task to the queue backend."
    )
    parser.add_argument(
        "--database-url",
        default="sqlite:///./invoices_saas.db",
        help="SQLAlchemy database URL (default: sqlite:///./invoices_saas.db)",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://127.0.0.1:6379/0",
        help="Redis URL for RQ queue backend (default: redis://127.0.0.1:6379/0)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Retention threshold in days (default: 30)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = build_engine(args.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = build_session_factory(engine)
    service = SaaSService(session_factory=session_factory, queue=build_queue(args.redis_url))
    job_id = service.enqueue_report_cleanup(retention_days=args.retention_days)
    print(f"cleanup_queue_job_id={job_id}")


if __name__ == "__main__":
    main()
