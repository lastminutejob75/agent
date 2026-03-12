"""Compatibility shim for legacy imports.

`main.py` imports `from backend import vapi` and expects a `router`.
Expose the current Vapi router from `backend.routes.voice`.
"""

from backend.routes.voice import router

