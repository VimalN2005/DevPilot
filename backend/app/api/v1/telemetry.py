from fastapi import APIRouter
from app.core.telemetry import telemetry_collector

router = APIRouter(prefix="/telemetry", tags=["Observability & Telemetry"])


@router.get("/metrics")
async def get_observability_metrics():
    """
    Real-time production AI metrics dashboard data:
    Requests, avg latency, error rate, token usage, estimated cost, RAG accuracy.
    """
    return telemetry_collector.get_metrics()


@router.get("/logs")
async def get_recent_logs():
    """Retrieve raw telemetry audit logs for recent AI invocations."""
    return telemetry_collector.logs[:50]
