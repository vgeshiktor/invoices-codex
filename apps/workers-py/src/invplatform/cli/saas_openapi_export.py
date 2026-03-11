from __future__ import annotations

import argparse
import json
from pathlib import Path

from invplatform.saas.api import ApiAppConfig, create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a versioned OpenAPI spec snapshot for the SaaS API."
    )
    parser.add_argument(
        "--database-url",
        default="sqlite://",
        help="SQLAlchemy database URL used for app bootstrapping (default: sqlite://).",
    )
    parser.add_argument(
        "--storage-url",
        default="local://./data/saas_storage",
        help="Storage backend URL used for app bootstrapping.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output path for the snapshot. If omitted, uses "
            "integrations/openapi/saas-openapi.v<api-version>.json"
        ),
    )
    parser.add_argument(
        "--auth-access-token-secret",
        default="openapi-export-secret",
        help="Required auth secret used while bootstrapping the API app for export.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(
        ApiAppConfig(
            database_url=args.database_url,
            storage_url=args.storage_url,
            auth_access_token_secret=args.auth_access_token_secret,
            auth_cookie_secure=False,
        )
    )
    schema = app.openapi()
    info = schema.get("info", {})
    version = str(info.get("version", "0.1.0")).strip() or "0.1.0"

    output_path = (
        Path(args.output)
        if args.output
        else Path(f"integrations/openapi/saas-openapi.v{version}.json")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
