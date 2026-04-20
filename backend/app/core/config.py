#Concentrar a config do db
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("RUNNING_IN_DOCKER") == "1"


class Settings(BaseSettings):
    '''
    Essa classe le variaveis de ambiente automaticamente
    e cria atributos Python com esses valores 
    '''
    # Preferido no Docker Compose (já vem pronto)
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # Fallback (modo local / envs separados)
    postgres_db: str | None = Field(default=None, validation_alias="POSTGRES_DB")
    postgres_user: str | None = Field(default=None, validation_alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, validation_alias="POSTGRES_PASSWORD")
    postgres_host: str | None = Field(default=None, validation_alias="POSTGRES_HOST")
    postgres_port: str | None = Field(default=None, validation_alias="POSTGRES_PORT")

    @property
    def sqlalchemy_database_url(self) -> str:
        """URL para SQLAlchemy.

        Aceita DATABASE_URL (ex: postgresql://user:pass@db:5432/edital_matcher)
        ou monta a partir de POSTGRES_*.
        """

        if self.database_url:
            url = self.database_url
            # Normaliza para driver explícito quando vier "postgresql://"
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url

        missing = [
            name
            for name, value in {
                "POSTGRES_DB": self.postgres_db,
                "POSTGRES_USER": self.postgres_user,
                "POSTGRES_PASSWORD": self.postgres_password,
                "POSTGRES_HOST": self.postgres_host,
                "POSTGRES_PORT": self.postgres_port,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                "Config de banco incompleta. Defina DATABASE_URL ou as variáveis: "
                + ", ".join(missing)
            )

        postgres_host = self.postgres_host
        if postgres_host == "db" and not _running_in_docker():
            postgres_host = "localhost"

        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # Pydantic v2: configurações de leitura de env
    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False,
        env_file='../.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
settings = Settings()