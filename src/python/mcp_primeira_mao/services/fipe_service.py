import asyncio
import httpx
from config import PRECIFICACAO_API_URL, FIPE_TIMEOUT, logger

MAX_TENTATIVAS = 3

class FipeService:
    @staticmethod
    async def consultar_por_placa(placa: str):
        placa_limpa = placa.upper().replace("-", "").strip()
        url = f"{PRECIFICACAO_API_URL}/fipe"
        params = {"placa": placa_limpa}

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            logger.info(f"[FipeService] Tentativa {tentativa}/{MAX_TENTATIVAS} | placa={placa_limpa}")
            try:
                async with httpx.AsyncClient(timeout=FIPE_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(url, params=params)

                    if resp.is_error:
                        logger.error(f"[FipeService] HTTP {resp.status_code} | body={resp.text[:300]}")
                        return {
                            "error": f"Erro HTTP {resp.status_code}",
                            "detalhe": resp.text[:500],
                        }

                    dados_raw = resp.json()
                    dados = dados_raw[0] if isinstance(dados_raw, list) and len(dados_raw) > 0 else dados_raw

                    if not dados:
                        return {"error": "Não encontrado", "mensagem": "Placa não localizada na base FIPE."}

                    logger.info(f"[FipeService] Sucesso | placa={placa_limpa} | tentativa={tentativa}")
                    return {
                        "placa":          placa_limpa,
                        "marca":          dados.get("marca"),
                        "modelo":         dados.get("modelo"),
                        "versao":         dados.get("versao")       or "",
                        "ano_modelo":     str(dados.get("ano_modelo") or dados.get("anoModelo") or ""),
                        "valor_fipe":     dados.get("valor_fipe")   or dados.get("valor") or dados.get("preco") or 0,
                        "combustivel":    dados.get("combustivel")  or "",
                        "codigo_fipe":    dados.get("codigo_fipe")  or dados.get("codigoFipe") or "",
                        "carroceria":     dados.get("carroceria")   or "",
                        "mes_referencia": dados.get("mes_referencia", ""),
                    }

            except httpx.ReadTimeout:
                logger.warning(f"[FipeService] ReadTimeout na tentativa {tentativa}/{MAX_TENTATIVAS} | placa={placa_limpa}")
                if tentativa < MAX_TENTATIVAS:
                    await asyncio.sleep(2)
                    continue
                return {
                    "error": "Timeout",
                    "mensagem": f"A API FIPE não respondeu após {MAX_TENTATIVAS} tentativas (timeout={FIPE_TIMEOUT}s). Tente novamente.",
                }

            except httpx.ConnectError as exc:
                logger.error(f"[FipeService] ConnectError | {exc}")
                return {
                    "error": "Conexão falhou",
                    "mensagem": "Não foi possível conectar ao servidor FIPE.",
                    "detalhe": str(exc),
                }

            except Exception as e:
                logger.exception(f"[FipeService] Erro inesperado: {type(e).__name__}: {e}")
                return {"error": "Erro interno", "tipo": type(e).__name__, "detalhe": str(e)}
