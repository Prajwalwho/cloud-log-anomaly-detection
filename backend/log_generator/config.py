"""
Configuration for the log generator, loaded from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeneratorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kafka (used from Day 8)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_logs: str = "logs.raw"

    # Average number of user requests per second
    generator_rate: float = 20.0

    # Random seed for reproducible output; None = different every run
    generator_seed: int | None = None


settings = GeneratorSettings()