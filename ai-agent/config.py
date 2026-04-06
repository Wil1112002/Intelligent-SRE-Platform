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
    remediation_namespace: str = "default"

    # Kubernetes
    in_cluster: bool = True

    model_config = {"env_prefix": "SRE_AGENT_"}


settings = Settings()
