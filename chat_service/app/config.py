from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "chat_db"
    postgres_user: str = "chat_user"
    postgres_password: str = "chat_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    app_host: str = "127.0.0.1"
    app_port: int = 8082

    jwt_secret: str = "lesson-secret-key-at-least-32b"
    jwt_expire_minutes: int = 1440

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

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


settings = Settings()