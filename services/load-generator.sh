#!/usr/bin/env bash
# Simple load generator for the SRE platform sample services.
# Usage: ./load-generator.sh [API_BASE] [WORKER_BASE] [RPS]
#
# Defaults assume port-forwarded or ingress-accessible services.

API_BASE="${1:-http://localhost:8001}"
WORKER_BASE="${2:-http://localhost:8002}"
RPS="${3:-5}"  # Requests per second (total, split across endpoints)

INTERVAL=$(echo "scale=4; 1 / $RPS" | bc)

echo "Load generator started"
echo "  API service:    $API_BASE"
echo "  Worker service: $WORKER_BASE"
echo "  Target RPS:     $RPS"
echo "  Press Ctrl+C to stop"
echo ""

while true; do
  # Rotate through endpoints
  curl -s -o /dev/null -w "%{http_code} %{time_total}s  GET $API_BASE/process\n" \
    "$API_BASE/process" &

  curl -s -o /dev/null -w "%{http_code} %{time_total}s  GET $WORKER_BASE/run\n" \
    "$WORKER_BASE/run" &

  # Occasional health checks
  if (( RANDOM % 5 == 0 )); then
    curl -s -o /dev/null "$API_BASE/health" &
    curl -s -o /dev/null "$WORKER_BASE/health" &
  fi

  sleep "$INTERVAL"
done
