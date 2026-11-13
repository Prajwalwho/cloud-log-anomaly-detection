"""
Configuration for the backend API, loaded from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "cla_db"
    postgres_user: str = "cla_user"
    postgres_password: str = "change_me"
    postgres_pool_max: int = 10

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "logs"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_anomalies: str = "anomalies.detected"
    kafka_topic_alerts: str = "alerts.events"
    api_group_id: str = "api-group"

    # Live feed (/ws/live)
    live_kafka_enabled: bool = True          # tests without Kafka switch the listener off
    live_ping_s: float = 30.0                # api-contracts.md §4
    live_queue_size: int = 100               # per browser; a full queue closes that connection

    # HTTP
    cors_origins: str = "http://localhost:5173"      # Vite dev server (dashboard, Phase 9)
    dependency_timeout_s: float = 3.0               # health checks and pool waits

    @property
    def postgres_conninfo(self) -> str:
        return (f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
                f"user={self.postgres_user} password={self.postgres_password} connect_timeout=3")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]