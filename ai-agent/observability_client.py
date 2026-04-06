import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


async def query_prometheus(
    base_url: str,
    query: str,
    timeout: float = 10.0,
) -> str:
    """Execute an instant PromQL query and return the result as a formatted string."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base_url}/api/v1/query",
                params={"query": query},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            return "No data"

        lines: list[str] = []
        for r in results:
            metric = r.get("metric", {})
            value = r.get("value", [None, "N/A"])[1]
            label_str = ", ".join(f"{k}={v}" for k, v in metric.items())
            lines.append(f"  {label_str}: {value}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Prometheus query failed: %s", e)
        return f"Query failed: {e}"


async def get_error_rate(base_url: str, service: str) -> str:
    """Get error rate for a service over the last 30 minutes."""
    # Try api-service style metrics first, then worker-service style
    query = (
        f'sum(rate(error_count_total{{endpoint=~".*"}}[30m])) '
        f'/ sum(rate(request_count_total{{endpoint=~".*"}}[30m])) * 100'
    )
    return await query_prometheus(base_url, query)


async def get_p99_latency(base_url: str, service: str) -> str:
    """Get p99 latency for a service over the last 30 minutes."""
    query = (
        'histogram_quantile(0.99, sum(rate(request_latency_seconds_bucket[30m])) by (le)) '
        '* 1000'
    )
    return await query_prometheus(base_url, query)


async def get_pod_restarts(base_url: str, namespace: str = "default") -> str:
    """Get pod restart count in the last 30 minutes."""
    query = f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}[30m])) by (pod)'
    return await query_prometheus(base_url, query)


async def query_loki_errors(
    base_url: str,
    service: str,
    limit: int = 50,
    timeout: float = 10.0,
) -> str:
    """Fetch recent error logs from Loki for a given service."""
    try:
        now = datetime.now(timezone.utc)
        end_ns = int(now.timestamp() * 1e9)
        start_ns = end_ns - int(30 * 60 * 1e9)  # 30 minutes ago

        query = f'{{app="{service}"}} |= "error" or {{app="{service}"}} |= "500"'

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": str(start_ns),
                    "end": str(end_ns),
                    "limit": limit,
                    "direction": "backward",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        streams = data.get("data", {}).get("result", [])
        if not streams:
            return "No error logs found"

        lines: list[str] = []
        for stream in streams:
            for value in stream.get("values", []):
                lines.append(value[1])

        return "\n".join(lines[:limit]) if lines else "No error logs found"
    except Exception as e:
        logger.error("Loki query failed: %s", e)
        return f"Log query failed: {e}"
