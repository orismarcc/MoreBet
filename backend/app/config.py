from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_football_key: str
    api_football_base_url: str = "https://v3.football.api-sports.io"
    database_url: str
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
