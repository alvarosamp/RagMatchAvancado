from sqlalchemy  import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.logs.config import logger 

#Engine = conexao com o banco
engine = create_engine(settings.database_url, pool_pre_ping=True)

#Sessionlocal = classe que cria sessões de banco de dados
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db(): #cada request cria uma sessão de banco de dados nova, e a sessão é fechada ao final da request
    '''
    Dependency que fornece uma sessão de banco de dados para as rotas do FastAPI
    -abre a sessao
    - entrega pra rota
    - fecha ao final
    '''
    
    db = SessionLocal()
    try:
        logger.info("Sessão de banco de dados criada com sucesso.")
        yield db
    finally:
        db.close()
        logger.info("Sessão de banco de dados fechada.")