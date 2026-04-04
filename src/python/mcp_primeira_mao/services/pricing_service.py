import httpx
from config import PRECIFICACAO_API_URL, TIMEOUT, logger

class PricingService:
    @staticmethod
    async def calcular_compra(dados_veiculo: dict):
        """
        Envia os dados do veículo para calcular a oferta de compra.
        Espelha o node 'precifica' do n8n: GET /carro/compra com query params.
        """
        url = f"{PRECIFICACAO_API_URL}/carro/compra"

        # Fallbacks para evitar parâmetros vazios ou "None" (equivalente ao node 'normaliza_dados')
        params = {
            "placa": dados_veiculo.get("placa", "").upper(),
            "valor_fipe": str(dados_veiculo.get("valor_fipe") or 0),
            "marca": dados_veiculo.get("marca") or "Não Informada",
            "modelo": dados_veiculo.get("modelo") or "Não Informado",
            "versao": dados_veiculo.get("versao") or "não",
            "tipo_combustivel": dados_veiculo.get("tipo_combustivel") or "Flex",
            "ano_modelo": str(dados_veiculo.get("ano_modelo") or ""),
            "uf": dados_veiculo.get("uf", "GO").upper(),
            "tipo": dados_veiculo.get("tipo") or "não",
            "km": str(dados_veiculo.get("km") or "0"),
            "codigo_fipe": dados_veiculo.get("codigo_fipe") or "",
            "cor": dados_veiculo.get("cor") or "Não Informada",
            "existe_zero_km": dados_veiculo.get("existe_zero_km") or "não",
            "tipo_carroceria": dados_veiculo.get("tipo_carroceria") or "não"
        }

        logger.info(f"Solicitando precificação Saga | Placa: {params['placa']}")

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, params=params)
                
                if resp.status_code == 400:
                    # Log detalhado do motivo da rejeição da API
                    logger.error(f"Erro 400 na Precificação | Detalhe: {resp.text} | Params: {params}")
                    return {"error": "Dados inválidos", "mensagem": "A API de precificação rejeitou os dados enviados."}
                
                resp.raise_for_status()
                logger.info(f"Precificação realizada com sucesso | Placa: {params['placa']}")
                return resp.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"Erro de status HTTP na precificação: {e.response.status_code} - {e.response.text}")
            return {"error": "Erro na API", "mensagem": "Falha na comunicação com o servidor de compra."}
        except Exception as e:
            logger.exception(f"Erro inesperado no PricingService: {e}")
            return {"error": "Erro interno", "mensagem": "Ocorreu uma falha ao processar a avaliação."}