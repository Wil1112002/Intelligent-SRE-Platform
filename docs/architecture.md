# Architecture

## Overview

The Intelligent SRE Platform is a production-realistic environment that demonstrates end-to-end SRE ownership. It runs on AWS EKS and combines infrastructure provisioning, full-stack observability, AI-assisted incident response, and a developer CLI.

## Components

### Infrastructure Layer

- **AWS VPC** — Isolated network with public and private subnets across 2 availability zones
- **AWS EKS** — Managed Kubernetes cluster (v1.29) with a managed node group (t3.medium, 2-4 nodes)
- **NGINX Ingress Controller** — Routes external traffic to internal services via an AWS NLB
- **Terraform** — All infrastructure is defined as code in `terraform/`

### Application Layer

Two lightweight FastAPI microservices simulate realistic production workloads:

| Service | Purpose | Failure Modes |
|---------|---------|--------------|
| **api-service** | Simulates a request/response API | Random 50-500ms latency, 10% error rate |
| **worker-service** | Simulates background job processing | Random 100-800ms latency, 5% error rate, gradual memory leak |

Both expose Prometheus metrics at `/metrics` and are deployed via Helm charts.

### Observability Layer

All deployed in the `monitoring` namespace:

- **Prometheus** (kube-prometheus-stack) — Metrics collection with 7-day retention. Scrapes services via ServiceMonitor CRDs.
- **Grafana** — Three pre-configured dashboards: Service Overview, Infrastructure, Incident View.
- **Loki** — Log aggregation in single-binary mode with S3 backend storage.
- **Promtail** — DaemonSet collecting logs from all pods and shipping to Loki.
- **Alertmanager** — Routes alerts by severity to the AI triage agent webhook.

### AI Triage Layer

The AI Triage Agent (`sre-agent` namespace) is the core differentiator:

1. **Receives** Alertmanager webhook when alerts fire
2. **Gathers context** by querying Prometheus (metrics) and Loki (logs)
3. **Triages** by sending structured context to Claude API for analysis
4. **Stores** results in SQLite for historical querying
5. **Remediates** by executing safe Kubernetes actions (restart, scale)

RBAC is tightly scoped — the agent can only read pods and patch/scale deployments in the `default` namespace.

### CLI Layer (srekit)

A Python CLI built with Typer and Rich that provides:

- `scan` — Cluster health overview (deployments, services, nodes)
- `audit` — Security and best-practice findings
- `incident list/get/ask` — Query and interact with incident history
- `report` — Generate AI-written weekly summaries

## Data Flow

```
Traffic → api-service/worker-service
              │
              ├─ Metrics → Prometheus → Alert Rules
              │                              │
              ├─ Logs → Promtail → Loki      │ (threshold breached)
              │                              ▼
              │                        Alertmanager
              │                              │
              │                              ▼
              │                     AI Triage Agent
              │                        │    │    │
              │     Query metrics ◄────┘    │    └───► Claude API
              │     Query logs    ◄─────────┘              │
              │                                            ▼
              │                                    Triage Result
              │                                        │
              ├─── Remediation (restart/scale) ◄───────┤
              │                                        │
              │                                   SQLite DB
              │                                        │
              └────────────────────────────── srekit CLI queries
```

## Namespaces

| Namespace | Contents |
|-----------|----------|
| `default` | api-service, worker-service |
| `monitoring` | Prometheus, Grafana, Loki, Promtail, Alertmanager |
| `sre-agent` | AI Triage Agent |
| `ingress-nginx` | NGINX Ingress Controller |

## Security Considerations

- Claude API key stored as Kubernetes Secret, referenced via `secretKeyRef` (never in manifests)
- AI agent has least-privilege RBAC (read pods, patch deployments in `default` only)
- No containers configured to run as root in the Helm charts
- All services have resource requests and limits set
- All services have liveness and readiness probes
