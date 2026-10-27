from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "user_db"
    postgres_user: str = "user_user"
    postgres_password: str = "user_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5435
    app_host: str = "127.0.0.1"
    app_port: int = 8081

    jwt_secret: str = "lesson-secret-key-at-least-32b"
    jwt_expire_minutes: int = 1440

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    cors_origins: str = "http://127.0.0.1:8082,http://localhost:8082"

    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
