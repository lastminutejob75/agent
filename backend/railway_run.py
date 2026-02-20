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
        "python -m backend.run_migration 009 || true; "
        "python -m backend.run_migration 010 || true; "
        "python -m backend.run_migration 011 || true; "
        "python -m backend.run_migration 012 || true; "
        "python -m backend.run_migration 013 || true; "
        "python -m backend.run_migration 014 || true; "
        "python -m backend.run_migration 015 || true; "
        "python -m backend.run_migration 016 || true; "
        "python -m backend.run_migration 017 || true; "
        "python -m backend.run_migration 018 || true; "
        "echo 'Migrations done'"
    )
    subprocess.Popen(
        ["sh", "-c", cmd],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Pré-import pour que toute erreur d'import remonte dans les logs Railway
    try:
        import uvicorn
        print("Importing backend.main ...", flush=True)
        import backend.main as _m  # noqa: F401
        print(f"App loaded. Binding 0.0.0.0:{port_int} ...", flush=True)
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=port_int,
            workers=1,
        )
    except Exception as e:
        print(f"FATAL uvicorn: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"railway_run error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
