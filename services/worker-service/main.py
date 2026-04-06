import asyncio
import random
import time

from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="worker-service", version="1.0.0")

# Simulated memory leak storage
_leak_store: list[bytes] = []

# Prometheus metrics
JOB_COUNT = Counter(
    "job_count",
    "Total jobs executed",
    ["status"],
)
JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Job duration in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0],
)
MEMORY_USAGE = Gauge(
    "memory_usage_bytes",
    "Simulated memory usage in bytes",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/run")
async def run_job() -> dict[str, str | float] | Response:
    start = time.perf_counter()

    # Simulate background job: random sleep 100-800ms
    delay = random.uniform(0.1, 0.8)
    await asyncio.sleep(delay)

    # Gradual memory growth to simulate a leak (~1KB per request)
    _leak_store.append(b"\x00" * 1024)
    MEMORY_USAGE.set(len(_leak_store) * 1024)

    duration = time.perf_counter() - start

    # 5% chance of panic (500)
    if random.random() < 0.05:
        JOB_COUNT.labels(status="error").inc()
        JOB_DURATION.observe(duration)
        return Response(
            content='{"error": "Job panic: unexpected failure", "duration_s": '
            + f"{duration:.3f}" + "}",
            status_code=500,
            media_type="application/json",
        )

    JOB_COUNT.labels(status="success").inc()
    JOB_DURATION.observe(duration)
    return {
        "status": "completed",
        "duration_s": round(duration, 3),
        "memory_allocated_bytes": len(_leak_store) * 1024,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
