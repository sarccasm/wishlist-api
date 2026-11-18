#!/usr/bin/env python3

import os
import sys

import uvicorn


def check_dependencies() -> bool:
    try:
        import fastapi  # noqa: F401
        import redis  # noqa: F401
        import sqlalchemy  # noqa: F401
    except ImportError as exc:
        print(f"Dependencies are missing: {exc}", file=sys.stderr)
        return False
    return True


def main() -> None:
    if not check_dependencies():
        sys.exit(1)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        workers=int(os.getenv("WEB_CONCURRENCY", "1")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
