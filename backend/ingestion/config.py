"""
Configuration for the ingestion service, loaded from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_logs: str = "logs.raw"
    kafka_topic_deadletter: str = "logs.deadletter"
    ingestion_group_id: str = "ingestion-group"

    # Processing
    ingestion_batch_size: int = 500          # max messages per batch
    ingestion_poll_timeout_s: float = 1.0    # how long to wait for a batch

    # Elasticsearch (used from Day 10)
    elasticsearch_url: str = "http://localhost:9200"


settings = IngestionSettings()