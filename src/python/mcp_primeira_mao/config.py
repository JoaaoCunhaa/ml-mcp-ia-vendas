import os
from dotenv import load_dotenv
import logging

load_dotenv()

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

# Configuração do MCP (Padrão: stdio para o Inspector)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()

TIMEOUT = int(os.getenv("API_TIMEOUT", 20))