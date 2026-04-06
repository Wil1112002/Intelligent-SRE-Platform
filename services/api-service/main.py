import asyncio
import random
import time

from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="api-service", version="1.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter(
    "request_count",
    "Total request count",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0],
)
ERROR_COUNT = Counter(
    "error_count",
    "Total error count",
    ["endpoint"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    REQUEST_COUNT.labels(method="GET", endpoint="/health", status="200").inc()
    return {"status": "healthy"}


@app.get("/process")
async def process() -> dict[str, str | float]:
    start = time.perf_counter()

    # Simulate work: random sleep 50-500ms
    delay = random.uniform(0.05, 0.5)
    await asyncio.sleep(delay)

    # 10% chance of error
    if random.random() < 0.10:
        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(method="GET", endpoint="/process").observe(duration)
        REQUEST_COUNT.labels(method="GET", endpoint="/process", status="500").inc()
        ERROR_COUNT.labels(endpoint="/process").inc()
        return Response(
            content='{"error": "Internal processing failure", "duration_s": '
            + f"{duration:.3f}" + "}",
            status_code=500,
            media_type="application/json",
        )

    duration = time.perf_counter() - start
    REQUEST_LATENCY.labels(method="GET", endpoint="/process").observe(duration)
    REQUEST_COUNT.labels(method="GET", endpoint="/process", status="200").inc()
    return {"status": "processed", "duration_s": round(duration, 3)}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
