"""Configuration for the alerting service, loaded from environment variables / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlertingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_anomalies: str = "anomalies.detected"
    kafka_topic_alerts: str = "alerts.events"
    alerting_group_id: str = "alerting-group"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "cla_db"
    postgres_user: str = "cla_user"
    postgres_password: str = "change_me"

    # Grouping
    alert_group_gap_s: float = 300.0        # anomalies of one service within 5 min belong to one alert
    alert_min_severity: str = "MEDIUM"      # lower anomalies never open an alert (they can join one)

    @property
    def postgres_conninfo(self) -> str:
        return (f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
                f"user={self.postgres_user} password={self.postgres_password} connect_timeout=5")