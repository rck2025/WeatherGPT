"""
WeatherGPT Root Application Entry Point.

Exports:
    app: The FastAPI production application instance with full SIH voice hardening.
"""
from backend.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import os
    import socket
    import uvicorn

    def get_port():
        env_port = os.getenv("PORT")
        if env_port:
            return int(env_port)
        for p in [8000, 8080, 8008, 8888]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", p))
                    return p
                except OSError:
                    continue
        return 8080

    import sys
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    selected_port = get_port()
    print("\n=======================================================")
    print(f"WeatherGPT starting on http://127.0.0.1:{selected_port}")
    print(f"API Documentation: http://127.0.0.1:{selected_port}/docs")
    print("=======================================================\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=selected_port, reload=True)


