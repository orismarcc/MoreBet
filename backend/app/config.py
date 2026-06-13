import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "change-me-in-production-use-long-random-string"


class Settings(BaseSettings):
    # env_file for local dev; extra="ignore" so stale/legacy keys in .env (e.g.
    # the old API-Football provider) never crash the app or the test suite.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Primary data provider: football-data.org (free tier covers current season)
    football_data_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    database_url: str
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Admin seeded on first boot. MUST be provided via env in production.
    admin_email: str = ""
    admin_password: str = ""

    # Claude API — per-matchup recommendation agent. Empty key disables the
    # /matches/recommend endpoint gracefully (503).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # the-odds-api — real bookmaker odds (value detection). Empty key simply
    # means recommendations come without market-odds comparison.
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


settings = Settings()

# Never run with the leaked default secret. If JWT_SECRET isn't provided we
# generate a strong random per-process secret instead — secure, but resets on
# restart (sessions re-login). In production we log loudly so the operator sets
# a persistent JWT_SECRET; we deliberately do NOT crash, so a missing env var
# can never take the live site down.
if settings.jwt_secret == _DEFAULT_JWT_SECRET:
    settings.jwt_secret = secrets.token_urlsafe(48)
    if settings.is_production:
        logger.error(
            "JWT_SECRET not set in production — using a random per-process secret. "
            "Sessions will reset on restart; set JWT_SECRET on the host for "
            "persistent logins."
        )
    else:
        logger.warning("JWT_SECRET not set — generated a random per-process secret (dev only).")
