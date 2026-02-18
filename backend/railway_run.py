#!/usr/bin/env python3
"""
Point d'entrée Railway : lit PORT depuis l'env et lance uvicorn.
Garantit que l'app écoute sur le même port que celui utilisé par le healthcheck Railway.
"""
from __future__ import annotations

import os
import subprocess
import sys

def main() -> int:
    port = os.environ.get("PORT", "8000")
    try:
        port_int = int(port)
    except ValueError:
        port_int = 8000
    print(f"Starting server on port {port_int} (PORT={os.environ.get('PORT', 'not set')})", flush=True)
    # Migrations en arrière-plan (même ordre que l'ancien CMD)
    cmd = (
        "python -m backend.run_migration 005 || true; "
        "python -m backend.run_migration 003 || true; "
        "python -m backend.run_migration 004 || true; "
        "python -m backend.run_migration 006 || true; "
        "python -m backend.run_migration 007 || true; "
        "python -m backend.run_migration 008 || true; "
        "python -m backend.run_migration 008_call_sessions_messages_checkpoints.sql || true; "
        "echo 'Migrations done'"
    )
    subprocess.Popen(
        ["sh", "-c", cmd],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Uvicorn en avant-plan (remplace ce processus)
    os.execvp(
        "uvicorn",
        [
            "uvicorn", "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(port_int),
            "--workers", "2",
        ],
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
