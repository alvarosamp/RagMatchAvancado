import logging 
import os

# Definir o diretório onde os logs serão armazenados
# Usando o diretório atual do código (relativo ao local onde o código está sendo executado)
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')

# Certifique-se de que o diretório de logs exista, caso contrário, crie
os.makedirs(LOG_DIR, exist_ok=True)

# Definir o caminho completo do arquivo de log
LOG_FILE_PATH = os.path.join(LOG_DIR, 'backend.app.log')

# Configurar o logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)