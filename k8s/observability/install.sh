#!/usr/bin/env bash
# Deploy the full observability stack to the monitoring namespace.
# Prerequisites: helm, kubectl configured for your EKS cluster.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Adding Helm repos..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo "==> Installing kube-prometheus-stack..."
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f "$SCRIPT_DIR/kube-prometheus-stack-values.yaml" \
  --wait --timeout 10m

echo "==> Installing Loki..."
helm upgrade --install loki grafana/loki \
  --namespace monitoring \
  -f "$SCRIPT_DIR/loki-values.yaml" \
  --wait --timeout 5m

echo "==> Installing Promtail..."
helm upgrade --install promtail grafana/promtail \
  --namespace monitoring \
  -f "$SCRIPT_DIR/promtail-values.yaml" \
  --wait --timeout 5m

echo "==> Applying PrometheusRule alert definitions..."
kubectl apply -f "$SCRIPT_DIR/prometheus-rules.yaml"

echo "==> Applying Grafana dashboards..."
kubectl apply -f "$SCRIPT_DIR/grafana-dashboard-service-overview.yaml"
kubectl apply -f "$SCRIPT_DIR/grafana-dashboard-infrastructure.yaml"
kubectl apply -f "$SCRIPT_DIR/grafana-dashboard-incident.yaml"

echo "==> Applying Alertmanager routing config..."
kubectl apply -f "$SCRIPT_DIR/../alertmanager/alertmanager-config.yaml"

echo ""
echo "Observability stack deployed successfully!"
echo "  Grafana:      kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
echo "  Prometheus:   kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090"
echo "  Alertmanager: kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093"
