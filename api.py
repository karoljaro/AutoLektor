"""Minimal HTTP API entry point for AutoLektor."""

from fastapi import FastAPI

app = FastAPI(title="AutoLektor API")


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple readiness signal for n8n and local checks."""
    return {"status": "ok"}
