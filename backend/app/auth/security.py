'''
Conceito : Como funciona a autenticaçao com JWT

Fluxo completo :
Usuário faz POST /auth/login com email + senha
Servidor verifica a senha contra o hash no banco
Servidor cria um JWT assinado com SECRET_KEY
Cliente recebe o JWT e guarda (localStorage, cookie, etc.)
Em cada request, cliente envia o JWT no header:
Authorization: Bearer <token>
Servidor valida a assinatura do JWT
Se válido, extrai user_id e tenant_id do payload
Injeta na rota via dependency

'''
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt 
from passlib.context import CryptContext
from app.logs.config import logger
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis de ambiente do .env

#Configuracoes lidas do ambiente
#Secret_key : NUNCA deve ser hardcoded no código, sempre usar variavel de ambiente
SECRET_KEY = os.getenv("SECRET_KEY")
if SECRET_KEY is None:
    raise EnvironmentError("SECRET_KEY environment variable is not set")
#Algoritmo de assinatura do JWT
#HS256 é o mais comum, mas pode ser substituido por RS256 (com chaves assimetricas) para mais segurança
# RS256 exige mais configuração (chaves publicas/privadas) mas é recomendado para produção
ALGORITHM = os.getenv("ALGORITHM", "HS256")
#Tempo de expiração do token (ex: 30 minutos)
#60 minitos. Em producao, tokens curtos + refresh tokens são mais seguros
try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
except ValueError:
    logger.warning("Invalid ACCESS_TOKEN_EXPIRE_MINUTES; falling back to 60")
    ACCESS_TOKEN_EXPIRE_MINUTES = 60

#Contexto de hashing de senha (bcrypt)
'''
CryptContext gerencia o algoritmo de hash e verifica senhas antigas automaticamente
bcrypt adiciona salt automático e tem custo configurável (rounds)
auto = deprecate automaticamente hashes antigos se o algoritmo mudar, for recomendado para produção
'''
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_passoword(plain_password : str) -> str:
    ''' 
    Gera o hash bcrypt de uma senha em texto puro

    bcrypt é intencionalmente lento (custo configuravel) para dificultar
    ataques de força bruta. O salt é embutido no hash resultante.

    Exemplo: 
    hash_passoword("minhasenha123") -> "$2b$12$KIXQ1...resto do hash..."
       -> $2b$12 indica bcrypt com custo 12

    '''
    return _pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password : str) -> bool:
    '''
    Docstring para verify_password
    
    :param plain_password: Descrição
    :type plain_password: str
    :param hashed_password: Descrição
    :type hashed_password: str
    :return: Descrição
    :rtype: bool
    '''
    return _pwd_context.verify(plain_password, hashed_password)

#JWT - Craicao e validacao

def create_access_token(
        subject :str,
        tenant_slug : str,
        role : str,
        user_id : int,
        expires_delta : Optional[timedelta] = None,
    ) -> str:
    '''
    Cria um JWT assinado com as informaçoes do usuario

        O payload (claims) do token contem:
        - sub: assunto do token (normalmente user_id ou email)
        - tenant: slug do tenant do usuario (para multi-tenancy)
        - role: papel do usuario (ex: admin, user)
        - user_id: ID do usuario (pode ser redundante com sub, mas facilita acessoo)
        - exp: timestamp de expiração (obrigatório para segurança)

        IMPORTANTE : Nao coloque informaçoes sensiveis no payload no JWT, pois ele pode ser decodificado por qualquer um (mesmo sem a chave secreta). O segredo é apenas para assinar e validar, nao para criptografar.
        O JWT é apenas codificado em base64, nao criptografado - qualquer um 
        pode ler o conteudo. A assinatura so garante que ele nao foi altearado.

        Args:
                subject:     email do usuário (claim "sub")
                tenant_slug: slug do tenant para filtrar dados
                user_id:     ID do usuário no banco
                role:        papel do usuário
                expires_delta: tempo de expiração customizado (usa o padrão se None)

            Returns:
                String do JWT assinado.
    '''
    #Define quando o token expira - é um timestamp UTC
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)))
    #Cria o payload do token
    payload = {
        "sub": subject, #subject = quem é o usuario
        "tenant_slug": tenant_slug, #qual tenant esse usuario pertence
        "role": role, #ID no banco (para queries diretas)
        "user_id": user_id, #papel (para autorizaçao)
        "exp": expire #quando expira 
    }
    #Assina e retorna o token
    # Garantir que SECRET_KEY não é None para satisfazer verificadores de tipo
    assert SECRET_KEY is not None, "SECRET_KEY must be set"
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Token criado para user_id={user_id} com expiração em {expire.isoformat()}")
    return token

def decode_access_token(token: str) -> dict:
    """
    Valida e decodifica um JWT.

    Verifica:
        1. Assinatura (foi criado com nossa SECRET_KEY?)
        2. Expiração (o claim 'exp' ainda está no futuro?)
        3. Algoritmo (usa HS256?)

    Args:
        token: string do JWT recebido no header Authorization

    Returns:
        Dict com o payload decodificado.

    Raises:
        JWTError: se o token for inválido, expirado ou adulterado.
    """
    #jwr.decode() valida assinatura + expiraçao automaticamente
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    logger.debug(f"Token decodificado com sucesso: {payload}")
    return payload 