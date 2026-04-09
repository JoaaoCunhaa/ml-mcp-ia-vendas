import os
from dotenv import load_dotenv
import logging

# Carrega o .env pelo caminho absoluto do arquivo config.py.
# Necessário para o MCP Inspector, que pode rodar de outro diretório.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Configurações de Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Banco de Dados (Postgres)
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5435")
}

# Integração Mobiauto
MOBI_SECRET = os.getenv("MOBI_SECRET")
URL_AWS_TOKEN = os.getenv("URL_AWS_TOKEN")

# API de Precificação
PRECIFICACAO_API_URL = os.getenv("PRECIFICACAO_API_URL")

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()

TIMEOUT      = int(os.getenv("API_TIMEOUT",      30))
FIPE_TIMEOUT = int(os.getenv("FIPE_TIMEOUT",     60))