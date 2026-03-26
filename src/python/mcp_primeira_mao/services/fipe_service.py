import httpx
from config import TIMEOUT, logger

class FipeService:
    @staticmethod
    async def consultar_por_placa(placa: str):
        """
        Consulta os dados técnicos e o valor da Tabela FIPE 
        utilizando a placa do veículo.
        """
        placa_limpa = placa.upper().replace("-", "").strip()
        
        url = f"https://api.sagametadados.com.br/fipe/v1/placa/{placa_limpa}"
        
        logger.info(f"Consultando FIPE para placa: {placa_limpa}")
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url)
                
                if resp.status_code != 200:
                    logger.warning(f"Placa {placa_limpa} não localizada na base FIPE.")
                    return {
                        "error": "Veículo não encontrado",
                        "mensagem": "Não conseguimos localizar os dados da FIPE para esta placa. Verifique se a placa está correta."
                    }
                
                dados = resp.json()
                
                return {
                    "placa": placa_limpa,
                    "marca": dados.get("marca"),
                    "modelo": dados.get("modelo"),
                    "ano_modelo": dados.get("ano_modelo") or dados.get("anoModelo"),
                    "valor_fipe": dados.get("valor") or dados.get("preco"),
                    "combustivel": dados.get("combustivel"),
                    "codigo_fipe": dados.get("codigo_fipe") or dados.get("codigoFipe"),
                    "mes_referencia": dados.get("mes_referencia", "Mês atual")
                }

        except httpx.ConnectError:
            logger.error("Falha de conexão com o serviço de FIPE.")
            return {"error": "Serviço indisponível", "mensagem": "O serviço de consulta FIPE está temporariamente fora do ar."}
        except Exception as e:
            logger.error(f"Erro inesperado na consulta FIPE: {e}")
            return {"error": "Erro interno", "detail": str(e)}