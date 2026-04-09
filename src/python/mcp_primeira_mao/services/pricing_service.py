import httpx
from config import PRECIFICACAO_API_URL, TIMEOUT, logger

class PricingService:
    @staticmethod
    async def calcular_compra(dados_veiculo: dict):
        url = f"{PRECIFICACAO_API_URL}/carro/compra"

        params = {
            "placa":           dados_veiculo.get("placa", "").upper(),
            "valor_fipe":      str(dados_veiculo.get("valor_fipe") or 0),
            "marca":           dados_veiculo.get("marca")          or "",
            "modelo":          dados_veiculo.get("modelo")         or "",
            "versao":          dados_veiculo.get("versao")         or "",
            "tipo_combustivel":dados_veiculo.get("tipo_combustivel") or "",
            "ano_modelo":      str(dados_veiculo.get("ano_modelo") or ""),
            "uf":              dados_veiculo.get("uf", "GO").upper(),
            "tipo":            dados_veiculo.get("tipo")           or "carro",
            "km":              str(dados_veiculo.get("km")         or "0"),
            "codigo_fipe":     dados_veiculo.get("codigo_fipe")    or "",
            "cor":             dados_veiculo.get("cor")            or "",
            "existe_zero_km":  dados_veiculo.get("existe_zero_km") or "",
            "tipo_carroceria": dados_veiculo.get("tipo_carroceria") or "",
        }

        logger.info(f"[PricingService] Enviando precificação | placa={params['placa']} | params={params}")

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, params=params)

                if resp.status_code == 400:
                    logger.error(f"[PricingService] 400 Bad Request | body={resp.text[:500]} | params={params}")
                    return {
                        "error":   "Dados inválidos (400)",
                        "detalhe": resp.text[:500],
                        "params_enviados": params,
                    }

                if resp.is_error:
                    logger.error(f"[PricingService] HTTP {resp.status_code} | body={resp.text[:300]}")
                    return {
                        "error":   f"Erro HTTP {resp.status_code}",
                        "detalhe": resp.text[:300],
                    }

                logger.info(f"[PricingService] Sucesso | placa={params['placa']} | resposta={resp.text[:200]}")
                return resp.json()

        except httpx.ReadTimeout:
            logger.error(f"[PricingService] ReadTimeout | placa={params['placa']}")
            return {"error": "Timeout", "mensagem": "A API de precificação não respondeu no tempo limite."}
        except Exception as e:
            logger.exception(f"[PricingService] Erro inesperado: {type(e).__name__}: {e}")
            return {"error": "Erro interno", "tipo": type(e).__name__, "detalhe": str(e)}
