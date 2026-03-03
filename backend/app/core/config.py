#Concentrar a config do db
from pydantic_settings import BaseSettings, SettingsConfigDict
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
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # Pydantic v2: configurações de leitura de env
    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False,
    )
settings = Settings()