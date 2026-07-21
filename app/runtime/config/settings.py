from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = "Mollis Runtime"
    APP_VERSION: str = "0.1.0"

    LOG_LEVEL: str = "INFO"

    MAX_TASKS: int = 100

    DEBUG: bool = True


settings = Settings()