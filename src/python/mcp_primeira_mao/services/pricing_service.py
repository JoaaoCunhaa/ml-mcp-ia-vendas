import httpx
from config import PRECIFICACAO_API_URL, TIMEOUT, logger

class PricingService:
    @staticmethod
    async def buscar_fipe(placa: str):
        url = f"{PRECIFICACAO_API_URL}/fipe"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params={"placa": placa.upper().strip()})
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data]

    @staticmethod
    async def calcular_compra(dados_veiculo: dict):
        """Recebe o dicionário de dados e consulta a API de precificação"""
        url = f"{PRECIFICACAO_API_URL}/carro/compra"
        params = {
            "placa": dados_veiculo.get("placa"),
            "valor_fipe": str(dados_veiculo.get("valor_fipe")),
            "marca": dados_veiculo.get("marca"),
            "modelo": dados_veiculo.get("modelo"),
            "versao": dados_veiculo.get("versao"),
            "tipo_combustivel": dados_veiculo.get("tipo_combustivel"),
            "ano_modelo": str(dados_veiculo.get("ano_modelo")),
            "uf": dados_veiculo.get("uf", "GO").upper(),
            "km": str(dados_veiculo.get("km", "0")),
            "codigo_fipe": dados_veiculo.get("codigo_fipe"),
            "cor": dados_veiculo.get("cor"),
            "existe_zero_km": dados_veiculo.get("existe_zero_km", "Não"),
            "tipo_carroceria": dados_veiculo.get("tipo_carroceria"),
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()