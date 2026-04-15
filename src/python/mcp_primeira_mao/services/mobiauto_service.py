import httpx
from config import URL_AWS_TOKEN, MOBI_SECRET, TIMEOUT, logger
from utils.helpers import extrair_lista_veiculos

class MobiautoService:
    # Cache do token em memória — evita N requisições para N lojas
    _token_cache: str = None

    @staticmethod
    async def get_token(force_refresh: bool = False) -> str:
        if MobiautoService._token_cache and not force_refresh:
            logger.debug("[MobiautoService.get_token] Cache hit — reutilizando token existente")
            return MobiautoService._token_cache

        url = f"{URL_AWS_TOKEN}{MOBI_SECRET}"
        logger.info(f"[MobiautoService.get_token] Solicitando novo token | force_refresh={force_refresh}")
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, follow_redirects=False)
                resp.raise_for_status()
                MobiautoService._token_cache = resp.text.strip()
                logger.info(f"[MobiautoService.get_token] Token obtido e cacheado | status={resp.status_code}")
                return MobiautoService._token_cache
        except Exception as e:
            logger.error(f"[MobiautoService.get_token] Falha ao obter token | erro={type(e).__name__}: {e}")
            return None

    @staticmethod
    async def buscar_estoque(dealer_id: str, token: str, page_size: int = 30):
        """Busca o estoque de uma loja específica via ID. Recebe o token já obtido."""
        url = f"https://open-api.mobiauto.com.br/api/dealer/{dealer_id}/inventory/v1.0"
        # A API não suporta paginação — qualquer query param desconhecido retorna 204
        logger.debug(f"[MobiautoService.buscar_estoque] Iniciando | dealer_id={dealer_id}")
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 401:
                    # Token expirou — limpa cache e tenta uma vez com token novo
                    logger.warning(f"[MobiautoService.buscar_estoque] 401 — token expirado | dealer_id={dealer_id} — renovando token")
                    MobiautoService._token_cache = None
                    new_token = await MobiautoService.get_token(force_refresh=True)
                    if not new_token:
                        logger.error(f"[MobiautoService.buscar_estoque] Falha ao renovar token | dealer_id={dealer_id}")
                        return []
                    resp = await client.get(url, headers={"Authorization": f"Bearer {new_token}"})
                resp.raise_for_status()
                lista = extrair_lista_veiculos(resp.json())
                logger.debug(f"[MobiautoService.buscar_estoque] Concluído | dealer_id={dealer_id} | veículos={len(lista)}")
                return lista
        except Exception as e:
            logger.error(f"[MobiautoService.buscar_estoque] Erro | dealer_id={dealer_id} | {type(e).__name__}: {e}")
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