"""Runtime configuration loaded from environment and an optional YAML file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


class SettingsConfigurationError(RuntimeError):
    """Raised when an optional settings YAML file cannot be used safely."""


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Load non-secret defaults from the configured YAML file.

    This source has lower precedence than initialization arguments, environment variables, and
    `.env`, so deployment secrets and explicit overrides always win.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        config_path = os.environ.get("TOUCHORDERS_CONFIG_FILE")
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    def get_field_value(
        self,
        field: Any,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}

        try:
            parsed = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise SettingsConfigurationError(
                f"Unable to load configuration file {self._path}: {exc}"
            ) from exc

        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise SettingsConfigurationError(
                f"Configuration file {self._path} must contain a YAML mapping."
            )
        return parsed


class Settings(BaseSettings):
    """Process-wide runtime settings.

    OpenAI credentials are deliberately not a setting: the architecture requires
    ``llm.gateway`` to be their sole reader in Stage 7. The Stage 0 process can therefore run
    its liveness endpoint with no external credentials.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("TOUCHORDERS_ENVIRONMENT", "ENVIRONMENT"),
    )
    service_name: str = Field(default="touchorders-agent-core")
    database_url: str = Field(
        default="sqlite:///./touchorders.db",
        validation_alias=AliasChoices("DB_URL", "TOUCHORDERS_DATABASE_URL"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("TOUCHORDERS_LOG_LEVEL", "LOG_LEVEL"),
    )
    log_json: bool = Field(
        default=True,
        validation_alias=AliasChoices("TOUCHORDERS_LOG_JSON", "LOG_JSON"),
    )
    firebase_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FIREBASE_DATABASE_URL", "TOUCHORDERS_FIREBASE_DATABASE_URL"
        ),
    )
    firebase_service_account_json: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FIREBASE_SERVICE_ACCOUNT_JSON",
            "TOUCHORDERS_FIREBASE_SERVICE_ACCOUNT_JSON",
        ),
    )
    firebase_credentials_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FIREBASE_CREDENTIALS_PATH", "TOUCHORDERS_FIREBASE_CREDENTIALS_PATH"
        ),
    )
    auth_jwt_issuer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_JWT_ISSUER", "TOUCHORDERS_AUTH_JWT_ISSUER"),
    )
    auth_jwt_audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTH_JWT_AUDIENCE", "TOUCHORDERS_AUTH_JWT_AUDIENCE"
        ),
    )
    auth_api_key_pepper: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTH_API_KEY_PEPPER", "TOUCHORDERS_AUTH_API_KEY_PEPPER"
        ),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlSettingsSource(settings_cls),
        )

    @property
    def is_production(self) -> bool:
        """Whether this process is running in the production environment."""

        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated, process-wide settings instance."""

    try:
        return Settings()
    except ValidationError as exc:
        raise SettingsConfigurationError(f"Invalid runtime configuration: {exc}") from exc


def clear_settings_cache() -> None:
    """Clear cached settings for tests and controlled process reconfiguration."""

    get_settings.cache_clear()
