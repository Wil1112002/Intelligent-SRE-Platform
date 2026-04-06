# Intelligent SRE Platform

An end-to-end Site Reliability Engineering platform on AWS EKS demonstrating infrastructure provisioning, observability, AI-assisted incident response, and operational tooling.

## Architecture

```mermaid
graph TB
    subgraph AWS
        subgraph VPC
            subgraph EKS Cluster
                subgraph default namespace
                    API[api-service]
                    Worker[worker-service]
                end
                subgraph monitoring namespace
                    Prom[Prometheus]
                    Graf[Grafana]
                    Loki[Loki]
                    PT[Promtail]
                    AM[Alertmanager]
                end
                subgraph sre-agent namespace
                    Agent[AI Triage Agent]
                    DB[(SQLite)]
                end
                Ingress[NGINX Ingress]
            end
        end
        ECR[ECR]
        S3[S3 - Logs/State]
    end

    User[User / SRE] -->|srekit CLI| Agent
    User -->|browser| Graf
    API -->|metrics| Prom
    Worker -->|metrics| Prom
    PT -->|logs| Loki
    Prom -->|alerts| AM
    AM -->|webhook| Agent
    Agent -->|query metrics| Prom
    Agent -->|query logs| Loki
    Agent -->|triage| Claude[Claude API]
    Agent -->|remediate| API
    Agent -->|remediate| Worker
    Agent -->|store| DB
    Graf -->|datasource| Prom
    Graf -->|datasource| Loki
    Ingress --> API
    Ingress --> Worker
    Ingress --> Graf
```

## Prerequisites

- AWS account with CLI configured
- Terraform >= 1.5
- kubectl
- Helm >= 3.12
- Python >= 3.12
- Docker

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USER/intelligent-sre-platform.git
cd intelligent-sre-platform

# 2. Create S3 bucket for Terraform state
aws s3 mb s3://intelligent-sre-platform-tfstate --region us-east-1

# 3. Provision EKS cluster
cd terraform
terraform init
terraform apply
cd ..

# 4. Configure kubectl
aws eks update-kubeconfig --name intelligent-sre-dev --region us-east-1

# 5. Deploy observability stack
bash k8s/observability/install.sh

# 6. Build and push service images to ECR (or deploy locally)
docker build -t api-service services/api-service/
docker build -t worker-service services/worker-service/
docker build -t ai-agent ai-agent/

# 7. Deploy services via Helm
helm upgrade --install api-service k8s/apps/api-service/ -n default
helm upgrade --install worker-service k8s/apps/worker-service/ -n default

# 8. Create the API key secret and deploy the AI agent
kubectl create secret generic anthropic-api-key \
  --from-literal=api-key=YOUR_KEY -n sre-agent
helm upgrade --install ai-agent k8s/apps/ai-agent/ -n sre-agent

# 9. Install the CLI
pip install -e srekit/

# 10. Start generating traffic
bash services/load-generator.sh
```

## srekit CLI Usage

```bash
# Cluster health overview
srekit scan
srekit scan --namespace monitoring --output json

# Security and best-practice audit
srekit audit
srekit audit --namespace default --export report.md

# Incident management
srekit incident list
srekit incident list --severity critical --status open
srekit incident get 42

# AI-powered queries
srekit incident ask "what caused the most incidents this week?"

# Weekly report generation
srekit report
```

## Project Structure

```
.
├── terraform/              # EKS cluster, VPC, IAM (Terraform)
├── k8s/
│   ├── apps/               # Helm charts: api-service, worker-service, ai-agent
│   ├── observability/      # Prometheus, Grafana, Loki Helm values + dashboards
│   └── alertmanager/       # AlertmanagerConfig routing
├── services/
│   ├── api-service/        # FastAPI sample service A
│   ├── worker-service/     # FastAPI sample service B
│   └── load-generator.sh   # Traffic generator script
├── ai-agent/               # Alert webhook receiver + Claude triage logic
├── srekit/                 # Python CLI (Typer + Rich)
├── docs/
│   ├── architecture.md
│   └── runbooks/
└── .github/workflows/      # CI + deploy pipelines
```

## Observability

| Tool | Purpose | Access |
|------|---------|--------|
| Prometheus | Metrics collection + alerting | `kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090` |
| Grafana | Dashboards + visualization | `kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80` |
| Loki | Log aggregation | Accessed via Grafana datasource |
| Alertmanager | Alert routing | `kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093` |

### Pre-configured Dashboards

- **Service Overview** — request rate, error rate, p50/p95/p99 latency, worker memory
- **Infrastructure** — node CPU/memory/disk, pod count, restarts, network I/O
- **Incident View** — error rates + log panels side by side

### Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | Error rate > 5% over 2m | Warning |
| VeryHighErrorRate | Error rate > 15% over 2m | Critical |
| HighLatency | p99 > 1s over 5m | Warning |
| PodCrashLooping | > 3 restarts in 10m | Critical |
| MemoryLeak | Memory growth > 20% over 10m | Warning |

## AI Triage Agent

When an alert fires, the AI agent:
1. Receives the webhook from Alertmanager
2. Queries Prometheus for recent error rate, p99 latency, pod restarts
3. Queries Loki for recent error logs
4. Sends structured context to Claude API for root cause analysis
5. Saves the triage to SQLite
6. Optionally executes safe remediation (rollout restart, scale up)

## License

MIT
