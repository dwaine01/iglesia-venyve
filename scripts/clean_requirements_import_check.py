"""Clean requirements sanity check for PIL and server import."""

import importlib
import os
import sys

from dotenv import load_dotenv


def main() -> int:
    importlib.import_module("PIL")

    backend_dir = "/app/backend"
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    load_dotenv(os.path.join(backend_dir, ".env"), override=False)
    os.chdir(backend_dir)
    importlib.import_module("server")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())