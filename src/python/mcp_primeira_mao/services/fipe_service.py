import httpx
from config import PRECIFICACAO_API_URL, TIMEOUT, logger

class FipeService:
    @staticmethod
    async def consultar_por_placa(placa: str):
        """
        Realiza a busca exatamente como o fluxo n8n:
        - Endpoint: {PRECIFICACAO_API_URL}/fipe
        - Método: GET
        - Parâmetro: ?placa=SBY3C19
        """
        # Equivalente ao node 'normaliza_placa' do n8n (body.placa -> placa)
        placa_limpa = placa.upper().replace("-", "").strip()

        url = f"{PRECIFICACAO_API_URL}/fipe"
        params = {"placa": placa_limpa}

        logger.info(f"Iniciando busca_fipe | URL: {url} | Placa: {placa_limpa}")

        try:
            # Equivalente ao node 'busca_fipe' do n8n (GET com query param)
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, params=params)

                if resp.is_error:
                    logger.error(f"Erro na API FIPE: {resp.status_code} - {resp.text}")
                    return {
                        "error": f"Erro {resp.status_code}",
                        "mensagem": "Falha na comunicação com a API de precificação.",
                        "detalhe": resp.text
                    }

                dados_raw = resp.json()

                # n8n retorna os itens como lista; pegamos o primeiro elemento
                dados = dados_raw[0] if isinstance(dados_raw, list) and len(dados_raw) > 0 else dados_raw

                if not dados:
                    return {"error": "Não encontrado", "mensagem": "Placa não localizada na base Saga."}

                logger.info(f"Busca FIPE realizada com sucesso | Placa: {placa_limpa}")

                return {
                    "placa": placa_limpa,
                    "marca": dados.get("marca"),
                    "modelo": dados.get("modelo"),
                    "ano_modelo": str(dados.get("ano_modelo") or dados.get("anoModelo") or ""),
                    "valor_fipe": dados.get("valor") or dados.get("preco") or 0,
                    "combustivel": dados.get("combustivel") or "Flex",
                    "codigo_fipe": dados.get("codigo_fipe") or dados.get("codigoFipe") or "",
                    "mes_referencia": dados.get("mes_referencia", "Mês atual")
                }

        except httpx.ConnectError as exc:
            logger.error(f"Erro de conexão com a API FIPE: {str(exc)}")
            return {
                "error": "Conexão falhou",
                "mensagem": "Não foi possível estabelecer conexão com o servidor da Saga.",
                "tecnico": str(exc)
            }
        except Exception as e:
            logger.exception(f"Erro inesperado no FipeService: {e}")
            return {"error": "Erro interno", "detalhe": str(e)}