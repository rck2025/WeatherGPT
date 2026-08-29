"""
backend.services.language
─────────────────────────
Public exports used by main.py (the central orchestrator):

  language_service  — LanguageService singleton (pre/post language steps)
  language_router   — FastAPI APIRouter for /voice/* endpoints
"""
from backend.services.language.service import language_service
from backend.services.language.router import router as language_router

__all__ = ["language_service", "language_router"]
