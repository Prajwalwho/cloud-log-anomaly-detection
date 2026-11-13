"""Configuration for the alerting service, loaded from environment variables / .env."""
from pydantic import SecretStr
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

    # Grouping and lifecycle
    alert_group_gap_s: float = 300.0        # anomalies of one service within 5 min belong to one alert
    alert_min_severity: str = "MEDIUM"      # lower anomalies never open an alert (they can join one)
    alert_resolve_after_s: float = 300.0    # an alert without new anomalies for 5 min is resolved
    alert_resolve_check_s: float = 30.0     # how often quiet alerts are looked for

    # Notifications (Telegram). Without token and chat id, notifications are disabled.
    telegram_bot_token: SecretStr | None = None     # secret: only in .env, never printed
    telegram_chat_id: str | None = None
    notify_min_severity: str = "HIGH"

    @property
    def postgres_conninfo(self) -> str:
        return (f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
                f"user={self.postgres_user} password={self.postgres_password} connect_timeout=5")

    @property
    def telegram_token(self) -> str | None:
        return self.telegram_bot_token.get_secret_value() if self.telegram_bot_token else None