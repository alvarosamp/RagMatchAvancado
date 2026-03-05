#Concentrar a config do db
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("RUNNING_IN_DOCKER") == "1"


class Settings(BaseSettings):
    '''
    Essa classe le variaveis de ambiente automaticamente
    e cria atributos Python com esses valores 
    '''
    postgres_db : str
    postgres_user : str
    postgres_password : str
    postgres_host : str
    postgres_port : str
    
    @property
    def database_url(self) -> str:
        '''
        monta a string de conexão com o banco de dados usando os atributos da classe 
        '''
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