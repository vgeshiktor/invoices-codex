from __future__ import annotations

import argparse
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ worker loop for SaaS parse/report jobs.")
    parser.add_argument(
        "--database-url",
        default="sqlite:///./invoices_saas.db",
        help="SQLAlchemy database URL used by task functions.",
    )
    parser.add_argument(
        "--storage-url",
        default="local://./data/saas_storage",
        help="Storage backend URL used by task functions.",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://127.0.0.1:6379/0",
        help="Redis URL for queue backend (default: redis://127.0.0.1:6379/0).",
    )
    parser.add_argument("--queue", default="invoices", help="RQ queue name (default: invoices).")
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Process all currently queued jobs and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["SAAS_DATABASE_URL"] = args.database_url
    os.environ["SAAS_STORAGE_URL"] = args.storage_url

    try:
        from redis import Redis  # type: ignore[import-untyped]
        from rq import Queue, Worker  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("rq and redis are required to run the SaaS RQ worker loop.") from exc

    connection = Redis.from_url(args.redis_url)
    queue = Queue(name=args.queue, connection=connection)
    worker = Worker([queue], connection=connection)
    worker.work(with_scheduler=True, burst=args.burst)


if __name__ == "__main__":
    main()
