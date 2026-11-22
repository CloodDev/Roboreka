"""Allow running the Roboreka server via `python -m roboreka`."""

from __future__ import annotations

from roboreka.cli import main_server

if __name__ == "__main__":
    raise SystemExit(main_server())
