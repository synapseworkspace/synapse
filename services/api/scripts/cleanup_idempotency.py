from __future__ import annotations

import argparse

from app.db import get_conn
from app.idempotency import cleanup_expired_requests_now


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete expired idempotency request records")
    parser.add_argument("--batch-size", type=int, default=1000, help="Maximum rows to delete per run")
    args = parser.parse_args()

    with get_conn() as conn:
        deleted = cleanup_expired_requests_now(conn, batch_size=args.batch_size)
    print(f"deleted={deleted}")


if __name__ == "__main__":
    main()
