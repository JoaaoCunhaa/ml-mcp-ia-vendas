import httpx
from config import URL_AWS_TOKEN, MOBI_SECRET, TIMEOUT, logger
from utils.helpers import extrair_lista_veiculos

class MobiautoService:
    # Cache do token em memória — evita N requisições para N lojas
    _token_cache: str = None

    @staticmethod
    async def get_token(force_refresh: bool = False) -> str:
        if MobiautoService._token_cache and not force_refresh:
            return MobiautoService._token_cache

        url = f"{URL_AWS_TOKEN}{MOBI_SECRET}"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, follow_redirects=False)
                resp.raise_for_status()
                MobiautoService._token_cache = resp.text.strip()
                logger.info("[MobiautoService] Token obtido e cacheado")
                return MobiautoService._token_cache
        except Exception as e:
            logger.error(f"Erro Token Mobiauto: {e}")
            return None

    @staticmethod
    async def buscar_estoque(dealer_id: str, token: str, page_size: int = 30):
        """Busca o estoque de uma loja específica via ID. Recebe o token já obtido."""
        url = f"https://open-api.mobiauto.com.br/api/dealer/{dealer_id}/inventory/v1.0"
        # A API não suporta paginação — qualquer query param desconhecido retorna 204
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 401:
                    # Token expirou — limpa cache e tenta uma vez com token novo
                    logger.warning(f"[MobiautoService] Token expirado para loja {dealer_id} — renovando")
                    MobiautoService._token_cache = None
                    new_token = await MobiautoService.get_token(force_refresh=True)
                    if not new_token:
                        return []
                    resp = await client.get(url, headers={"Authorization": f"Bearer {new_token}"}, params=params)
                resp.raise_for_status()
                return extrair_lista_veiculos(resp.json())
        except Exception as e:
            logger.error(f"Erro Estoque {dealer_id}: {e}")
            return []

    @staticmethod
    async def buscar_veiculo_por_placa(placa: str, dealer_id: str):
        """Filtra um veículo por placa dentro do estoque de um dealer."""
        token = await MobiautoService.get_token()
        if not token:
            return {}
        estoque = await MobiautoService.buscar_estoque(dealer_id, token=token)
        placa_up = placa.upper().replace("-", "").strip()
        return next((v for v in estoque if str(v.get("plate", "")).replace("-", "").upper() == placa_up), {})