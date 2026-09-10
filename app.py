"""
WeatherGPT Root Application Entry Point.

Exports:
    app: The FastAPI production application instance with full SIH voice hardening.
"""
from backend.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
