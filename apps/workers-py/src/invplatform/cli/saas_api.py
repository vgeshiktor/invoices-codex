from __future__ import annotations

import argparse
import os

from invplatform.saas.api import ApiAppConfig, create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Invoices SaaS API service.")
    parser.add_argument(
        "--database-url",
        default="sqlite:///./invoices_saas.db",
        help="SQLAlchemy database URL (default: sqlite:///./invoices_saas.db)",
    )
    parser.add_argument(
        "--redis-url",
        default=None,
        help="Optional Redis URL for RQ queue backend (default: in-memory queue)",
    )
    parser.add_argument(
        "--upload-dir",
        default=None,
        help="Deprecated alias for local storage root (maps to --storage-url local://<dir>).",
    )
    parser.add_argument(
        "--storage-url",
        default="local://./data/saas_storage",
        help="Storage backend URL (default: local://./data/saas_storage).",
    )
    parser.add_argument(
        "--control-plane-api-key",
        default=os.environ.get("SAAS_CONTROL_PLANE_API_KEY"),
        help="Optional control-plane key for tenant bootstrap/list endpoints.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage_url = args.storage_url
    if args.upload_dir:
        storage_url = f"local://{args.upload_dir}"

    app = create_app(
        ApiAppConfig(
            database_url=args.database_url,
            redis_url=args.redis_url,
            storage_url=storage_url,
            control_plane_api_key=args.control_plane_api_key,
        )
    )

    try:
        import uvicorn  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("uvicorn is required to run the SaaS API CLI command.") from exc

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
