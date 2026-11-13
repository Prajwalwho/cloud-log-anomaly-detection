"""
Configuration for the detection service, loaded from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
        protected_namespaces=(),   # allows field names starting with "model"
    )

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_logs: str = "logs.raw"
    kafka_topic_anomalies: str = "anomalies.detected"
    detection_group_id: str = "detection-group"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "cla_db"
    postgres_user: str = "cla_user"
    postgres_password: str = "change_me"

    # Models and windows
    models_dir: str = "models/trained"
    window_s: float = 60.0
    grace_s: float = 5.0
    services: str = "api-gateway,auth-service,order-service,payment-service,inventory-service"

    @property
    def service_list(self) -> list[str]:
        return [s.strip() for s in self.services.split(",") if s.strip()]

    @property
    def postgres_conninfo(self) -> str:
        return (f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
                f"user={self.postgres_user} password={self.postgres_password}")