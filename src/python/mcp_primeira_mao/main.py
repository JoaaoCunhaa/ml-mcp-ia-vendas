import os
import sys

# Garante que o diretório do script está no sys.path independente do CWD.
# Necessário para o MCP Inspector, que pode rodar python main.py de outro diretório.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import re
import httpx
from typing import Optional
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from services.inventory_aggregator import InventoryAggregator
from services.fipe_service import FipeService
from services.pricing_service import PricingService
from services.mobiauto_proposal_service import MobiautoProposalService
from utils.helpers import normalizar_placa
from config import logger

# ── Webhooks internos ──────────────────────────────────────────────
_WH_COMPRA = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_comprar"
_WH_VENDA  = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_vender"

async def _disparar_webhook(url: str, payload: dict, nome: str) -> bool:
    """Envia POST para o webhook interno. Aguarda confirmação antes de retornar."""
    payload_limpo = {k: v for k, v in payload.items() if v not in (None, "", [])}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload_limpo)
            if resp.is_success:
                logger.info(f"[webhook.{nome}] Enviado | status={resp.status_code} | campos={list(payload_limpo.keys())}")
                return True
            logger.warning(f"[webhook.{nome}] Resposta inesperada | status={resp.status_code} | body={resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[webhook.{nome}] Falha ao enviar | {type(e).__name__}: {e}")
        return False

mcp = FastMCP("PrimeiraMaoSaga")

# ── Verificação de domínio para ChatGPT Apps (OpenAI) ──────────────
# Token configurado em .env → OPENAI_CHALLENGE_TOKEN
@mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def _openai_domain_challenge(request: Request) -> PlainTextResponse:
    token = os.getenv("OPENAI_CHALLENGE_TOKEN", "")
    logger.info("[openai-challenge] Verificação de domínio solicitada")
    return PlainTextResponse(token)

# ─────────────────────────────────────────────────────────────
# INSTRUÇÃO GLOBAL DE RENDERIZAÇÃO DE CARDS DE VEÍCULOS
#
# Campos disponíveis em cada veículo:
#   titulo_card, url_imagem, loja_unidade, modelYear, km,
#   colorName, preco_formatado, link_ofertas,
#   makeName, modelName, trimName, plate, id
#
# Formato obrigatório do card:
#
#   ![{titulo_card}]({url_imagem})
#   ### **{titulo_card}**
#   | Campo | Valor |
#   |---|---|
#   | 📍 Loja | {loja_unidade} |
#   | 🗓️ Ano | {modelYear} |
#   | 📏 KM | {km} km |
#   | 🎨 Cor | {colorName} |
#   ## 💰 {preco_formatado}
#   [🛒 Ver oferta no site](link_ofertas)
#   ---
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# HELPERS DE BUSCA — extração de palavras-chave em linguagem natural
# ─────────────────────────────────────────────────────────────

_STOPWORDS = {
    "quero", "um", "uma", "me", "mostra", "mostrar", "preciso", "de", "para",
    "com", "que", "o", "a", "os", "as", "tem", "ter", "ver", "buscar",
    "procurar", "algum", "alguma", "e", "ou", "do", "da", "dos", "das",
    "no", "na", "nos", "nas", "em", "por", "se", "mais", "mas", "nao",
    "não", "sim", "ok", "carro", "veiculo", "veículo", "modelo", "marca",
    "cor", "ano", "gostaria", "queria", "seria", "possivel", "possível",
    "teria", "tenha", "qual", "quais", "ta", "tá", "ai", "aí", "é",
    "esta", "está", "esse", "essa", "aquele", "aquela", "meu", "minha",
    "seu", "sua", "tipo", "tem", "tiver", "ja", "já", "so", "só",
}

def _parece_id_ou_placa(termo: str) -> bool:
    """True se o termo tem formato de placa brasileira ou ID numérico."""
    t = termo.strip().upper().replace("-", "").replace(" ", "")
    return bool(
        re.match(r'^[A-Z]{3}\d{4}$', t) or        # placa antiga: ABC1234
        re.match(r'^[A-Z]{3}\d[A-Z]\d{2}$', t) or  # placa Mercosul: ABC1D23
        re.match(r'^\d{5,10}$', t)                 # ID numérico
    )

def _extrair_palavras_chave(consulta: str) -> list:
    """Extrai termos significativos ignorando stopwords e artigos."""
    palavras = re.split(r'[\s,;.!?/\\]+', consulta.lower().strip())
    return [p for p in palavras if p and p not in _STOPWORDS and len(p) >= 2]

def _score_veiculo(v: dict, palavras: list) -> int:
    """Conta quantas palavras-chave batem nos campos do veículo."""
    campos_str = " ".join([
        str(v.get("makeName",    "")),
        str(v.get("modelName",   "")),
        str(v.get("trimName",    "")),
        str(v.get("colorName",   "")),
        str(v.get("modelYear",   "")),
        str(v.get("loja_unidade","")),
        str(v.get("plate",       "")),
        str(v.get("id",          "")),
    ]).lower()
    return sum(1 for p in palavras if p in campos_str)


# ─────────────────────────────────────────────────────────────
# HELPERS DE RENDERIZAÇÃO — pré-renderiza Markdown no servidor
# O LLM apenas faz output do campo pronto, sem precisar montar templates.
# ─────────────────────────────────────────────────────────────

def _fmt_km(km) -> str:
    """Formata quilometragem: 32000 → '32.000'"""
    if km is None or km == "":
        return ""
    try:
        n = int(float(str(km).replace(".", "").replace(",", "")))
        return f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(km)


def _renderizar_card(v: dict, mostrar_placa: bool = False) -> str:
    """Gera o bloco Markdown completo de um card de veículo."""
    url_img = v.get("url_imagem") or ""
    titulo  = v.get("titulo_card") or "Veículo"
    loja    = v.get("loja_unidade") or ""
    ano     = str(v.get("modelYear") or "")
    cor     = v.get("colorName") or ""
    placa   = v.get("plate") or ""
    preco   = v.get("preco_formatado") or "R$ --"
    link    = v.get("link_ofertas") or "https://www.primeiramaosaga.com.br/gradedeofertas"
    km_fmt  = _fmt_km(v.get("km"))

    linhas = []
    if url_img:
        linhas.append(f"![{titulo}]({url_img})")
    linhas.append(f"### **{titulo}**")
    linhas.append("| | |")
    linhas.append("|---|---|")
    if loja:
        linhas.append(f"| 📍 Loja | {loja} |")
    if ano:
        linhas.append(f"| 🗓️ Ano | {ano} |")
    if km_fmt:
        linhas.append(f"| 📏 KM | {km_fmt} km |")
    if cor:
        linhas.append(f"| 🎨 Cor | {cor} |")
    if placa and mostrar_placa:
        linhas.append(f"| 🔖 Placa | {placa} |")
    linhas.append("")
    linhas.append(f"## 💰 {preco}")
    linhas.append(f"[🛒 Ver oferta no site]({link})")
    linhas.append("")
    linhas.append("---")
    return "\n".join(linhas)


def _renderizar_cards(
    veiculos: list,
    mensagem: str = None,
    aviso: str = None,
    mostrar_placa: bool = False,
) -> str:
    """Gera Markdown de uma lista de cards, com mensagem e aviso opcionais."""
    partes = []
    if mensagem:
        partes.append(f"> {mensagem}\n")
    for v in veiculos:
        partes.append(_renderizar_card(v, mostrar_placa=mostrar_placa))
    if aviso:
        partes.append(f"\n*{aviso}*")
    return "\n".join(partes)


# Instrução de interação pós-card (comportamento conversacional — não pré-renderizável)
_INSTRUCAO_OPCOES_COMPRA = (
    "AÇÃO PÓS-CARDS — quando o cliente demonstrar interesse em comprar um veículo específico "
    "('quero esse', 'como compro?', 'pode reservar?', etc.), ofereça OBRIGATORIAMENTE as duas opções:\n"
    "  1️⃣ [🛒 Ver oferta no site](https://www.primeiramaosaga.com.br/gradedeofertas)\n"
    "  2️⃣ Falar com consultor — peça nome e telefone e chame criar_lead_compra.\n"
    "Após criar_lead_compra retornar com sucesso, diga: "
    "'Um consultor Saga entrará em contato em breve sobre o veículo escolhido.'"
)


# ─────────────────────────────────────────────────────────────
# FUNÇÕES INTERNAS DE LEAD — chamadas automaticamente pelas tools
# Não são expostas como tools MCP — o LLM não as chama diretamente.
# ─────────────────────────────────────────────────────────────

async def _criar_lead_compra(
    nome_cliente: str,
    telefone_cliente: str,
    email_cliente: str = "",
    titulo_card: str = None,
    veiculo_id: str = None,
    preco_formatado: str = None,
    loja_unidade: str = None,
    plate: str = None,
    modelYear: str = None,
    km: str = None,
    colorName: str = None,
    observacao: str = None,
) -> dict:
    """Cria lead de compra no CRM e dispara webhook interno."""
    mensagem_crm = (
        f"Veículo de interesse: {titulo_card or ''} | "
        f"Loja: {loja_unidade or ''} | Placa: {plate or ''} | "
        f"Ano: {modelYear or ''} | KM: {km or ''} | Cor: {colorName or ''} | "
        f"Preço: {preco_formatado or ''}"
    ).strip(" |")

    logger.info(f"[_criar_lead_compra] Iniciando | veiculo='{titulo_card}' | loja='{loja_unidade}' | cliente='{nome_cliente}' | tel='{telefone_cliente}'")

    resultado = await MobiautoProposalService.criar_lead(
        intention_type="BUY",
        nome=nome_cliente,
        telefone=telefone_cliente,
        email=email_cliente,
        loja_nome=loja_unidade,
        mensagem=observacao or mensagem_crm,
    )

    lead_id = (resultado.get("response") or {}).get("id")
    await _disparar_webhook(_WH_COMPRA, {
        "lead_id":          lead_id,
        "nome_cliente":     nome_cliente,
        "telefone_cliente": telefone_cliente,
        "email_cliente":    email_cliente,
        "titulo_card":      titulo_card,
        "veiculo_id":       veiculo_id,
        "preco_formatado":  preco_formatado,
        "loja_unidade":     loja_unidade,
        "plate":            plate,
        "modelYear":        modelYear,
        "km":               km,
        "colorName":        colorName,
        "dealer_id":        resultado.get("dealer_id"),
        "observacao":       observacao,
    }, "cliente_quer_comprar")

    logger.info(f"[_criar_lead_compra] Concluído | success={resultado.get('success')} | dealer_id={resultado.get('dealer_id')} | cliente='{nome_cliente}'")
    return {
        "registrado":   resultado.get("success", False),
        "dealer_id":    resultado.get("dealer_id"),
        "fallback_url": "https://www.primeiramaosaga.com.br/gradedeofertas",
        "mensagem": (
            f"Lead de compra criado com sucesso para {nome_cliente}."
            if resultado.get("success") else
            f"Falha ao criar lead no CRM: {resultado.get('error', 'erro desconhecido')}. "
            "Use o link do site como alternativa."
        ),
    }


async def _criar_lead_venda(
    nome_cliente: str,
    telefone_cliente: str,
    email_cliente: str = "",
    placa: str = None,
    km: str = None,
    veiculo_descricao: str = None,
    valor_proposta: str = None,
    preco_formatado: str = None,
    marca: str = None,
    modelo: str = None,
    ano_modelo: str = None,
    cor: str = None,
    uf: str = None,
    observacao: str = None,
) -> dict:
    """Cria lead de venda no CRM e dispara webhook interno."""
    mensagem_crm = (
        f"Veículo para venda: {veiculo_descricao or ''} | "
        f"Placa: {placa or ''} | KM: {km or ''} | "
        f"Marca: {marca or ''} | Modelo: {modelo or ''} | Ano: {ano_modelo or ''} | "
        f"Cor: {cor or ''} | UF: {uf or ''} | "
        f"Proposta Saga: {preco_formatado or valor_proposta or 'a avaliar'}"
    ).strip(" |")

    logger.info(f"[_criar_lead_venda] Iniciando | placa={placa} | km={km} | uf={uf} | cliente='{nome_cliente}' | tel='{telefone_cliente}'")

    resultado = await MobiautoProposalService.criar_lead(
        intention_type="SELL",
        nome=nome_cliente,
        telefone=telefone_cliente,
        email=email_cliente,
        uf_fallback=uf or "GO",
        mensagem=observacao or mensagem_crm,
    )

    lead_id = (resultado.get("response") or {}).get("id")
    await _disparar_webhook(_WH_VENDA, {
        "lead_id":           lead_id,
        "nome_cliente":      nome_cliente,
        "telefone_cliente":  telefone_cliente,
        "email_cliente":     email_cliente,
        "placa":             placa,
        "km":                km,
        "veiculo_descricao": veiculo_descricao,
        "valor_proposta":    valor_proposta,
        "preco_formatado":   preco_formatado,
        "marca":             marca,
        "modelo":            modelo,
        "ano_modelo":        ano_modelo,
        "cor":               cor,
        "uf":                uf,
        "dealer_id":         resultado.get("dealer_id"),
        "observacao":        observacao,
    }, "cliente_quer_vender")

    logger.info(f"[_criar_lead_venda] Concluído | success={resultado.get('success')} | dealer_id={resultado.get('dealer_id')} | cliente='{nome_cliente}'")
    return {
        "registrado":   resultado.get("success", False),
        "dealer_id":    resultado.get("dealer_id"),
        "fallback_url": "https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente",
        "mensagem": (
            f"Lead de venda criado com sucesso para {nome_cliente}."
            if resultado.get("success") else
            f"Falha ao criar lead no CRM: {resultado.get('error', 'erro desconhecido')}. "
            "Use o link de venda online como alternativa."
        ),
    }


# ─────────────────────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False, destructiveHint=False))
async def listar_lojas():
    """
    Lista todas as lojas Primeira Mão Saga cadastradas com nome, cidade e UF.

    OUTPUT: exiba o campo `lojas_markdown` diretamente ao usuário, exatamente como retornado.
    Adicione no rodapé a fonte dos dados e o total de lojas.
    """
    logger.info("[listar_lojas] Chamada iniciada")
    resultado = await InventoryAggregator.obter_lista_lojas()
    fonte = InventoryAggregator._ultima_fonte or "desconhecida"
    logger.info(f"[listar_lojas] Concluída | Total: {len(resultado)} | fonte={fonte}")

    linhas = [
        f"📍 **{l['nome']}** — {l.get('cidade', 'N/A')} / {l.get('uf', 'N/A')}"
        for l in resultado
    ]
    lojas_md = "\n".join(linhas) if linhas else "Nenhuma loja encontrada."
    lojas_md += f"\n\n*Total: {len(resultado)} lojas | Fonte: {fonte}*"

    return {
        "lojas_markdown": lojas_md,
        "lojas":          resultado,
        "total":          len(resultado),
        "fonte_dados":    fonte,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False))
async def estoque_total(
    pagina: Optional[int] = 1,
    # ── Lead automático de compra ──────────────────────────────
    # Preencha estes campos quando o cliente confirmar que quer falar com consultor.
    # O lead é criado internamente — NÃO chame nenhuma outra ferramenta para isso.
    nome_cliente: Optional[str] = None,
    telefone_cliente: Optional[str] = None,
    email_cliente: Optional[str] = None,
    titulo_card: Optional[str] = None,
    veiculo_id: Optional[str] = None,
    preco_formatado: Optional[str] = None,
    loja_unidade: Optional[str] = None,
    plate: Optional[str] = None,
    modelYear: Optional[str] = None,
    km: Optional[str] = None,
    colorName: Optional[str] = None,
    observacao: Optional[str] = None,
):
    """
    Exibe o estoque de veículos disponíveis nas lojas Primeira Mão Saga, 3 lojas por vez.

    - pagina=1 (padrão): primeiras 3 lojas.
    - pagina=2, 3…: próximas lojas — use quando o usuário pedir "ver mais".

    OUTPUT: exiba o campo `cards_markdown` diretamente ao usuário — os cards já estão
    formatados com imagem, tabela de detalhes, preço e botão de oferta.
    NÃO exiba nenhum campo do bloco `_meta`.

    CRIAR LEAD DE COMPRA (automático):
      Quando o cliente quiser falar com um consultor, chame esta ferramenta novamente
      passando nome_cliente + telefone_cliente + dados do veículo escolhido.
      O lead é registrado internamente — NÃO existe outra ferramenta para isso.
      Retorno: campo `lead` com registrado=true/false e mensagem de confirmação.
    """
    # ── Lead automático: criação interna quando cliente confirma interesse ──
    if nome_cliente and telefone_cliente:
        logger.info(f"[estoque_total] Lead automático de compra | cliente='{nome_cliente}' | veiculo='{titulo_card}'")
        return await _criar_lead_compra(
            nome_cliente=nome_cliente,
            telefone_cliente=telefone_cliente,
            email_cliente=email_cliente or "",
            titulo_card=titulo_card,
            veiculo_id=veiculo_id,
            preco_formatado=preco_formatado,
            loja_unidade=loja_unidade,
            plate=plate,
            modelYear=modelYear,
            km=km,
            colorName=colorName,
            observacao=observacao,
        )

    logger.info(f"[estoque_total] Chamada iniciada | pagina={pagina}")
    resultado = await InventoryAggregator.buscar_estoque_paginado(pagina=pagina)

    veiculos       = resultado["veiculos"]
    tem_mais       = resultado["tem_mais"]
    pagina_atual   = resultado["pagina"]
    total_paginas  = resultado["total_paginas"]
    fonte          = resultado["fonte_lojas"]
    lojas_buscadas = resultado["lojas_buscadas"]

    logger.info(
        f"[estoque_total] Concluída | veículos={len(veiculos)} | "
        f"pagina={pagina_atual}/{total_paginas} | fonte={fonte}"
    )

    aviso = (
        f"Página {pagina_atual} de {total_paginas} — diga **'ver mais'** para ver as próximas lojas."
        if tem_mais else
        f"Última página ({pagina_atual} de {total_paginas}) — todas as lojas foram exibidas."
    )

    if not veiculos:
        cards_md = (
            "> Não há veículos disponíveis no estoque no momento. "
            "Tente novamente em instantes ou entre em contato com uma de nossas lojas."
        )
    else:
        cards_md = _renderizar_cards(veiculos, aviso=aviso)

    return {
        "cards_markdown": cards_md,
        "_meta": {
            "total_veiculos": len(veiculos),
            "pagina":         pagina_atual,
            "total_paginas":  total_paginas,
            "lojas_buscadas": lojas_buscadas,
            "fonte_lojas":    fonte,
            "nota":           "Bloco interno — NÃO exibir ao cliente.",
        },
        "veiculos": veiculos,
        "aviso":    aviso,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False))
async def buscar_veiculo(
    consulta: Optional[str] = None,
    # ── Lead automático de compra ──────────────────────────────
    # Preencha estes campos quando o cliente confirmar que quer falar com consultor.
    # O lead é criado internamente — NÃO chame nenhuma outra ferramenta para isso.
    nome_cliente: Optional[str] = None,
    telefone_cliente: Optional[str] = None,
    email_cliente: Optional[str] = None,
    titulo_card: Optional[str] = None,
    veiculo_id: Optional[str] = None,
    preco_formatado: Optional[str] = None,
    loja_unidade: Optional[str] = None,
    plate: Optional[str] = None,
    modelYear: Optional[str] = None,
    km: Optional[str] = None,
    colorName: Optional[str] = None,
    observacao: Optional[str] = None,
):
    """
    Busca curinga: encontra veículos a partir de qualquer descrição em linguagem natural.
    Exemplos: "quero um corolla branco 2019", "hb20 prata", "abc1234", "SUV abaixo de 80 mil".

    Estratégia em 4 fases — NUNCA retorna vazio:
      1. ID ou placa exata → busca direta em todas as lojas.
      2. Todos os termos batem (AND) → resultado preciso.
      3. Parte dos termos bate (OR, ordenado por relevância) → similares.
      4. Nenhum termo bate → sugestões do estoque disponível.

    OUTPUT: exiba o campo `cards_markdown` diretamente ao usuário — os cards já estão
    formatados com imagem, tabela de detalhes, placa, preço e botão de oferta.

    CRIAR LEAD DE COMPRA (automático):
      Quando o cliente quiser falar com um consultor, chame esta ferramenta novamente
      passando nome_cliente + telefone_cliente + dados do veículo escolhido.
      O lead é registrado internamente — NÃO existe outra ferramenta para isso.
      Retorno: campo `lead` com registrado=true/false e mensagem de confirmação.
    """
    # ── Lead automático: criação interna quando cliente confirma interesse ──
    if nome_cliente and telefone_cliente:
        logger.info(f"[buscar_veiculo] Lead automático de compra | cliente='{nome_cliente}' | veiculo='{titulo_card}'")
        return await _criar_lead_compra(
            nome_cliente=nome_cliente,
            telefone_cliente=telefone_cliente,
            email_cliente=email_cliente or "",
            titulo_card=titulo_card,
            veiculo_id=veiculo_id,
            preco_formatado=preco_formatado,
            loja_unidade=loja_unidade,
            plate=plate,
            modelYear=modelYear,
            km=km,
            colorName=colorName,
            observacao=observacao,
        )

    if not consulta or not consulta.strip():
        # Sem consulta: retorna estoque da primeira página como sugestão
        return await estoque_total(pagina=1)

    logger.info(f"[buscar_veiculo] Chamada iniciada | consulta='{consulta}'")
    termo = consulta.strip()

    # ── Fase 1: ID ou placa exata (só executa se o termo parece placa/ID) ──
    if _parece_id_ou_placa(termo):
        resultado_exato = await InventoryAggregator.buscar_veiculo_especifico(termo)
        if resultado_exato:
            logger.info(f"[buscar_veiculo] Fase 1 — encontrado por ID/placa")
            return {
                "cards_markdown": _renderizar_cards([resultado_exato], mostrar_placa=True),
                "total":    1,
                "veiculos": [resultado_exato],
            }

    # ── Carrega TODO o estoque de TODAS as lojas ──
    estoque = await InventoryAggregator.buscar_estoque_consolidado(limit=None)
    logger.info(f"[buscar_veiculo] Estoque carregado | {len(estoque)} veículos em todas as lojas")

    # Extrai palavras-chave ignorando artigos/stopwords ("quero", "um", "cor", etc.)
    palavras = _extrair_palavras_chave(consulta)
    if not palavras:
        palavras = [termo.lower()]  # fallback: usa o termo bruto
    logger.info(f"[buscar_veiculo] Palavras-chave extraídas | {palavras}")

    # ── Fase 2: AND — veículos que batem com TODOS os termos ──
    res_and = [v for v in estoque if _score_veiculo(v, palavras) == len(palavras)]
    if res_and:
        logger.info(f"[buscar_veiculo] Fase 2 (AND) — {len(res_and)} resultados exatos")
        veiculos_and = res_and[:40]
        return {
            "cards_markdown": _renderizar_cards(veiculos_and, mostrar_placa=True),
            "total":    len(veiculos_and),
            "veiculos": veiculos_and,
        }

    # ── Fase 3: OR com ranking — ordena por quantos termos batem ──
    scored = [
        (v, _score_veiculo(v, palavras))
        for v in estoque
        if _score_veiculo(v, palavras) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored:
        res_or = [v for v, _ in scored[:40]]
        top_score = scored[0][1]
        logger.info(f"[buscar_veiculo] Fase 3 (OR) — {len(res_or)} similares | top_score={top_score}/{len(palavras)}")
        msg_or = f"Não encontramos exatamente \"{consulta}\", mas veja as opções mais próximas:"
        return {
            "cards_markdown": _renderizar_cards(res_or, mensagem=msg_or, mostrar_placa=True),
            "total":    len(res_or),
            "veiculos": res_or,
        }

    # ── Fase 4: Sem nenhuma correspondência — retorna sugestões gerais ──
    sugestoes = [v for v in estoque if v.get("url_imagem")][:20]
    logger.info(f"[buscar_veiculo] Fase 4 — sem resultado, sugerindo {len(sugestoes)} veículos")

    if not sugestoes:
        cards_md_f4 = (
            f"> Não encontramos **\"{consulta}\"** e não há veículos disponíveis no estoque no momento. "
            "Tente novamente em breve ou entre em contato com uma de nossas lojas."
        )
    else:
        msg_f4 = f"Não encontramos \"{consulta}\" no estoque atual. Confira outras opções disponíveis:"
        cards_md_f4 = _renderizar_cards(sugestoes, mensagem=msg_f4, mostrar_placa=True)

    return {
        "cards_markdown": cards_md_f4,
        "total":    len(sugestoes),
        "veiculos": sugestoes,
    }


# ─────────────────────────────────────────────────────────────
# FUNÇÕES INTERNAS (não são tools)
# ─────────────────────────────────────────────────────────────

async def _buscar_fipe(placa_limpa: str) -> dict:
    """Consulta a FIPE pela placa para alimentar o payload de precificação."""
    logger.info(f"[_buscar_fipe] Consultando FIPE | placa={placa_limpa}")
    resultado = await FipeService.consultar_por_placa(placa_limpa)
    if "error" in resultado:
        logger.warning(f"[_buscar_fipe] Erro | placa={placa_limpa} | detalhe={resultado}")
    else:
        logger.info(
            f"[_buscar_fipe] Dados obtidos | marca={resultado.get('marca')} "
            f"| modelo={resultado.get('modelo')} | ano={resultado.get('ano_modelo')} "
            f"| valor_fipe={resultado.get('valor_fipe')} | combustivel={resultado.get('combustivel')} "
            f"| codigo_fipe={resultado.get('codigo_fipe')}"
        )
    return resultado


# ─────────────────────────────────────────────────────────────
# TOOL: AVALIAÇÃO DE VEÍCULO DO CLIENTE (com botão de venda embutido)
# ─────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False))
async def avaliar_veiculo(
    placa: str,
    km: str,
    uf: Optional[str] = None,
    cor: Optional[str] = None,
    existe_zero_km: Optional[str] = None,
    # ── Lead automático de venda ───────────────────────────────
    # Preencha estes campos quando o cliente confirmar que quer prosseguir com a venda.
    # O lead é criado internamente — NÃO chame nenhuma outra ferramenta para isso.
    nome_cliente: Optional[str] = None,
    telefone_cliente: Optional[str] = None,
    email_cliente: Optional[str] = None,
    observacao: Optional[str] = None,
):
    """
    Calcula a proposta de compra/troca do veículo do cliente.

    PERGUNTE ao cliente APENAS: placa e km.

    NÃO pergunte uf, cor nem existe_zero_km — preencha-os SOMENTE se o cliente
    já tiver mencionado espontaneamente na conversa (ex: "meu carro é branco",
    "sou de SP", "sei que tem versão 0km"). Caso contrário, deixe em branco.

    Todos os dados técnicos (versão, carroceria, combustível, valor FIPE, etc.)
    vêm automaticamente da FIPE pela placa — não pergunte nada disso.

    OUTPUT: exiba o campo `proposta_markdown` diretamente ao usuário — já formatado.
    Após exibir, aguarde a resposta do cliente e siga o fluxo:
      - Se confirmar venda → peça nome e telefone → chame avaliar_veiculo novamente
        passando placa, km E nome_cliente + telefone_cliente.
        O lead de venda é criado automaticamente — NÃO existe outra ferramenta para isso.
        O retorno conterá o campo `lead` com registrado=true/false e mensagem de confirmação.
        Fallback se lead.registrado=false: exiba `url_venda`.
      - Se recusar → encerre sem chamar nenhuma ferramenta.
    """
    placa_limpa = normalizar_placa(placa)
    logger.info(f"[avaliar_veiculo] Chamada iniciada | placa={placa_limpa} | km={km} | uf={uf} | cor={cor} | existe_zero_km={existe_zero_km}")

    fipe = await _buscar_fipe(placa_limpa)

    if "error" in fipe:
        logger.warning(f"[avaliar_veiculo] Falha FIPE | placa={placa_limpa} | detalhe={fipe}")
        return {
            "error":    "Não foi possível consultar a FIPE.",
            "detalhe":  fipe,
            "mensagem": "Verifique a placa informada e tente novamente.",
        }

    # Campos técnicos: todos vêm da FIPE
    # Campos contextuais (uf, cor, existe_zero_km): do cliente se mencionou, senão padrão
    dados = {
        "placa":            placa_limpa,
        "km":               km,
        "valor_fipe":       str(fipe.get("valor_fipe") or ""),
        "marca":            fipe.get("marca")       or "",
        "modelo":           fipe.get("modelo")      or "",
        "versao":           fipe.get("versao")      or "",
        "tipo_combustivel": fipe.get("combustivel") or "",
        "ano_modelo":       str(fipe.get("ano_modelo") or ""),
        "codigo_fipe":      fipe.get("codigo_fipe") or "",
        "tipo_carroceria":  fipe.get("carroceria")  or "",
        "tipo":             "carro",
        "uf":               uf             or "GO",
        "cor":              cor            or "não",
        "existe_zero_km":   existe_zero_km or "não",
    }

    logger.info(
        f"[avaliar_veiculo] Payload montado | placa={placa_limpa} | km={km} "
        f"| valor_fipe={dados['valor_fipe']} | uf={dados['uf']} | cor={dados['cor']} "
        f"| combustivel={dados['tipo_combustivel']} | ano={dados['ano_modelo']}"
    )

    resultado = await PricingService.calcular_compra(dados)
    logger.info(f"[avaliar_veiculo] Retorno precificação | placa={placa_limpa} | resposta={resultado}")

    if "error" in resultado:
        logger.warning(f"[avaliar_veiculo] Erro precificação | placa={placa_limpa} | detalhe={resultado}")
        return resultado

    URL_VENDA = "https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente"
    valor_proposta = resultado.get("Valor_proposta_compra") or resultado.get("valor_proposta_compra")

    try:
        valor_numerico = float(
            str(valor_proposta).replace(",", ".").replace("R$", "").strip()
        ) if valor_proposta else 0
    except (ValueError, TypeError):
        valor_numerico = 0

    veiculo_descricao = f"{fipe.get('marca', '')} {fipe.get('modelo', '')} {fipe.get('ano_modelo', '')}".strip()

    km_fmt = _fmt_km(km)

    if not valor_numerico:
        mensagem_zero = (
            f"Para a placa **{placa_limpa}** com **{km_fmt} km**, não foi possível gerar "
            "uma proposta automática. A orientação é levar o carro presencialmente para avaliação."
        )
        proposta_md = (
            f"**{veiculo_descricao}**  \n"
            f"🔖 Placa: {placa_limpa} | 📏 {km_fmt} km\n\n"
            f"---\n\n"
            f"{mensagem_zero}\n\n"
            f"Deseja que um consultor entre em contato para agendar a avaliação? "
            f"Se sim, informe seu **nome** e **telefone**."
        )
        logger.info(f"[avaliar_veiculo] Valor zerado | placa={placa_limpa} — orientando avaliação presencial")
        base = {
            "proposta_markdown":   proposta_md,
            "proposta_disponivel": False,
            "veiculo_descricao":   veiculo_descricao,
            "url_venda":           URL_VENDA,
        }
        if nome_cliente and telefone_cliente:
            logger.info(f"[avaliar_veiculo] Lead automático de venda (valor zero) | cliente='{nome_cliente}' | placa={placa_limpa}")
            base["lead"] = await _criar_lead_venda(
                nome_cliente=nome_cliente,
                telefone_cliente=telefone_cliente,
                email_cliente=email_cliente or "",
                placa=placa_limpa,
                km=km,
                veiculo_descricao=veiculo_descricao,
                marca=fipe.get("marca"),
                modelo=fipe.get("modelo"),
                ano_modelo=str(fipe.get("ano_modelo") or ""),
                cor=cor,
                uf=uf,
                observacao=observacao,
            )
        return base

    preco_fmt = f"R$ {valor_proposta}"
    proposta_md = (
        f"## 💰 Proposta de Compra — Saga Primeira Mão\n\n"
        f"| | |\n"
        f"|---|---|\n"
        f"| 🚗 Veículo | {veiculo_descricao} |\n"
        f"| 🔖 Placa | {placa_limpa} |\n"
        f"| 📏 KM | {km_fmt} km |\n\n"
        f"### Valor oferecido pela Saga:\n"
        f"# {preco_fmt}\n\n"
        f"---\n\n"
        f"Gostaria de prosseguir com a venda? Informe seu **nome** e **telefone** "
        f"para que um consultor entre em contato."
    )
    logger.info(f"[avaliar_veiculo] Proposta gerada | placa={placa_limpa} | valor={valor_proposta}")
    base = {
        "proposta_markdown":     proposta_md,
        "proposta_disponivel":   True,
        "veiculo_descricao":     veiculo_descricao,
        "Valor_proposta_compra": valor_proposta,
        "preco_formatado":       preco_fmt,
        "url_venda":             URL_VENDA,
    }
    if nome_cliente and telefone_cliente:
        logger.info(f"[avaliar_veiculo] Lead automático de venda | cliente='{nome_cliente}' | placa={placa_limpa} | valor={valor_proposta}")
        base["lead"] = await _criar_lead_venda(
            nome_cliente=nome_cliente,
            telefone_cliente=telefone_cliente,
            email_cliente=email_cliente or "",
            placa=placa_limpa,
            km=km,
            veiculo_descricao=veiculo_descricao,
            valor_proposta=str(valor_proposta),
            preco_formatado=preco_fmt,
            marca=fipe.get("marca"),
            modelo=fipe.get("modelo"),
            ano_modelo=str(fipe.get("ano_modelo") or ""),
            cor=cor,
            uf=uf,
            observacao=observacao,
        )
    return base


if __name__ == "__main__":
    os.chdir(_HERE)

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "sse":
        port = int(os.getenv("PORT", 8000))
        logger.info(f"Iniciando MCP em modo SSE na porta {port}")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
