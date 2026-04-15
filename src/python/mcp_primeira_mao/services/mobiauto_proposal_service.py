"""
Serviço de criação de leads (propostas) na API Mobiauto CRM.
Suporta dois tipos: BUY (compra) e SELL (venda de veículo do cliente).

Endpoints:
  POST https://open-api.mobiauto.com.br/api/proposal/v1.0/{dealer_id}
  Auth: Bearer {token Mobiauto} — mesmo token usado para o estoque
"""

import httpx
from config import logger

PROPOSAL_BASE_URL = "https://open-api.mobiauto.com.br/api/proposal/v1.0"
PROPOSAL_TIMEOUT  = 15
GROUP_ID          = "948"

# Provider para fluxo de COMPRA (cliente quer comprar da Saga)
_PROVIDER_BUY = {
    "id":     11,
    "name":   "Site",
    "origin": "Internet",
    "providerCampaign": [
        {"provider": "Site", "campaign": ""}
    ],
}

# Provider para fluxo de VENDA (cliente quer vender o carro para a Saga)
_PROVIDER_SELL = {
    "id":     245,
    "name":   "Primeira Mão - Avaliação",
    "origin": "Internet",
    "providerCampaign": [
        {"provider": "Primeira Mão - Avaliação", "campaign": ""}
    ],
}


class MobiautoProposalService:

    # ── Lookup de dealer_id ────────────────────────────────────────────

    @staticmethod
    def _dealer_por_nome(loja_nome: str, lojas: list) -> str | None:
        """Depara nome da loja → dealerid (codigo_svm). Tenta exato, depois parcial."""
        if not loja_nome or not lojas:
            return None
        busca = loja_nome.lower().strip()
        for loja in lojas:
            if loja["nome"].lower().strip() == busca:
                return loja["codigo_svm"]
        # Parcial (ex: "SN GO BURITI" contido em "SN GO BURITI PREMIUM")
        for loja in lojas:
            if busca in loja["nome"].lower():
                return loja["codigo_svm"]
        return None

    @staticmethod
    def _dealer_por_uf(uf: str, lojas: list) -> str | None:
        """Retorna o primeiro dealerid de lojas com a UF informada."""
        if not uf or not lojas:
            return None
        uf_up = uf.upper().strip()
        for loja in lojas:
            if loja.get("uf", "").upper() == uf_up:
                return loja["codigo_svm"]
        return None

    # ── Criação de lead ────────────────────────────────────────────────

    @staticmethod
    async def criar_lead(
        intention_type: str,
        nome: str,
        telefone: str,
        email: str = "",
        loja_nome: str = None,
        uf_fallback: str = None,
        mensagem: str = "",
    ) -> dict:
        """
        Cria um lead na API Mobiauto.

        Parâmetros:
          intention_type : "BUY"  → cliente quer comprar um veículo da Saga
                           "SELL" → cliente quer vender o veículo para a Saga
          nome           : Nome do cliente
          telefone       : Telefone do cliente
          email          : E-mail (opcional; usa espaço se vazio pois a API exige o campo)
          loja_nome      : Nome da loja (usado para BUY — obtém dealer_id pelo nome)
          uf_fallback    : UF do cliente (fallback para SELL sem loja específica)
          mensagem       : Mensagem interna opcional (placa, km, etc.)

        Retorna dict com:
          success: bool
          dealer_id: str  (se success)
          error: str      (se não success)
        """
        # Importações locais para evitar circular import
        from services.inventory_aggregator import InventoryAggregator
        from services.mobiauto_service import MobiautoService

        # 1. Token
        token = await MobiautoService.get_token()
        if not token:
            logger.error("[MobiautoProposalService] Sem token Mobiauto — abortando")
            return {"success": False, "error": "Sem token de autenticação Mobiauto"}

        # 2. Lista de lojas para depara
        lojas = await InventoryAggregator.obter_lista_lojas()

        # 3. Resolve dealer_id com prioridade: nome → uf → primeira loja disponível
        dealer_id = None
        dealer_origem = ""

        if loja_nome:
            dealer_id = MobiautoProposalService._dealer_por_nome(loja_nome, lojas)
            if dealer_id:
                dealer_origem = f"loja_nome='{loja_nome}'"

        if not dealer_id and uf_fallback:
            dealer_id = MobiautoProposalService._dealer_por_uf(uf_fallback, lojas)
            if dealer_id:
                dealer_origem = f"uf_fallback='{uf_fallback}'"

        if not dealer_id and lojas:
            dealer_id = lojas[0]["codigo_svm"]
            dealer_origem = f"primeira_loja='{lojas[0]['nome']}'"

        if not dealer_id:
            logger.error("[MobiautoProposalService] Nenhum dealer_id disponível — sem lojas carregadas")
            return {"success": False, "error": "Nenhum dealer_id disponível"}

        logger.info(
            f"[MobiautoProposalService] dealer_id={dealer_id} | origem={dealer_origem} | "
            f"type={intention_type} | cliente='{nome}' | tel='{telefone}'"
        )

        # 4. Monta body
        provider = _PROVIDER_BUY if intention_type == "BUY" else _PROVIDER_SELL
        body = {
            "callcenter":    True,
            "intentionType": intention_type,
            "user": {
                "email":        email or " ",
                "dealerId":     dealer_id,
                "name":         nome,
                "phone":        telefone,
                "departmentId": "0",
            },
            "message":  mensagem or "",
            "origin":   1,
            "whatsapp": False,
            "provider": provider,
            "status":   "NEW",
            "groupId":  GROUP_ID,
            "tags":     [f"MCP_{'Compra' if intention_type == 'BUY' else 'Venda'}"],
        }

        # 5. POST na API
        url = f"{PROPOSAL_BASE_URL}/{dealer_id}"
        logger.info(f"[MobiautoProposalService] POST {url}")

        try:
            async with httpx.AsyncClient(timeout=PROPOSAL_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )

                if resp.is_success:
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text
                    logger.info(
                        f"[MobiautoProposalService] Lead criado | status={resp.status_code} | "
                        f"dealer_id={dealer_id} | type={intention_type} | response={body}"
                    )
                    return {"success": True, "status_code": resp.status_code, "dealer_id": dealer_id, "response": body}

                logger.error(
                    f"[MobiautoProposalService] HTTP {resp.status_code} | "
                    f"body={resp.text[:400]}"
                )
                return {
                    "success":    False,
                    "error":      f"HTTP {resp.status_code}",
                    "detalhe":    resp.text[:400],
                    "dealer_id":  dealer_id,
                }

        except httpx.ReadTimeout:
            logger.error(f"[MobiautoProposalService] Timeout ({PROPOSAL_TIMEOUT}s) | dealer_id={dealer_id}")
            return {"success": False, "error": f"Timeout após {PROPOSAL_TIMEOUT}s"}

        except Exception as exc:
            logger.exception(f"[MobiautoProposalService] Erro inesperado | {type(exc).__name__}: {exc}")
            return {"success": False, "error": f"{type(exc).__name__}: {exc}"}
