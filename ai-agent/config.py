from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Prometheus
    prometheus_url: str = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"

    # Loki
    loki_url: str = "http://loki.monitoring.svc.cluster.local:3100"

    # Database
    db_path: str = "/data/incidents.db"

    # Remediation
    remediation_enabled: bool = True
    # When False, remediation is dry-run: the agent logs and records what *would* have
    # happened but does not patch any Kubernetes resources. Flip to True only when
    # you are comfortable with the agent restarting/scaling deployments unattended.
    remediation_auto_execute: bool = False
    remediation_namespace: str = "default"

    # Webhook authentication. If set, requests to /webhook must present this token via
    # the `Authorization: Bearer <token>` or `X-Webhook-Token: <token>` header.
    # If empty, the webhook is unauthenticated (local dev only — a warning is logged).
    webhook_token: str = ""

    # Kubernetes
    in_cluster: bool = True

    model_config = {"env_prefix": "SRE_AGENT_"}


settings = Settings()
