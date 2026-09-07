"""
WeatherGPT Application Entry Point.

Exports:
    app: The FastAPI production application instance with full SIH voice hardening.
"""
from backend.main import app

__all__ = ["app"]
