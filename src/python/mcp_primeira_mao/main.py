import os
import sys

# Garante que o diretório do script está no sys.path independente do CWD.
# Necessário para o MCP Inspector, que pode rodar python main.py de outro diretório.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import re
from typing import Optional
from fastmcp import FastMCP
from services.inventory_aggregator import InventoryAggregator
from services.fipe_service import FipeService
from services.pricing_service import PricingService
from utils.helpers import normalizar_placa
from config import logger

mcp = FastMCP("PrimeiraMaoSaga")

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


INSTRUCAO_CARD = """RENDERIZAÇÃO OBRIGATÓRIA — para cada veículo, monte o seguinte Card em Markdown:

```
![{titulo_card}]({url_imagem})
### **{titulo_card}**
| | |
|---|---|
| 📍 Loja | {loja_unidade} |
| 🗓️ Ano | {modelYear} |
| 📏 KM | {km} km |
| 🎨 Cor | {colorName} |

## 💰 {preco_formatado}
[🛒 Ver oferta no site]({link_ofertas})
```
---
Regras:
- A imagem DEVE aparecer antes do título
- Use a tabela para os detalhes (não lista simples)
- O preço em ## para destaque visual
- O botão [🛒 Ver oferta no site] SEMPRE com o link_ofertas do veículo
- Separe cada card com ---
- Tom: profissional e direto. Sem parágrafos longos entre cards."""


# ─────────────────────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────────────────────

@mcp.tool()
async def listar_lojas():
    """
    Lista todas as lojas Primeira Mão Saga cadastradas com nome, cidade e UF.

    RENDERIZAÇÃO: uma loja por linha no formato:
      📍 **{nome}** — {cidade} / {uf}
    Informe a fonte dos dados (banco ou arquivo local) no rodapé.
    """
    logger.info("[listar_lojas] Chamada iniciada")
    resultado = await InventoryAggregator.obter_lista_lojas()
    fonte = InventoryAggregator._ultima_fonte or "desconhecida"
    logger.info(f"[listar_lojas] Concluída | Total: {len(resultado)} | fonte={fonte}")
    return {
        "lojas": resultado,
        "total": len(resultado),
        "fonte_dados": fonte,
        "instrucao_renderizacao": (
            "Exiba cada loja em uma linha: 📍 **{nome}** — {cidade} / {uf}. "
            "Informe no rodapé: fonte dos dados e total de lojas."
        ),
    }


@mcp.tool()
async def estoque_total(pagina: Optional[int] = 1):
    """
    Exibe o estoque de veículos disponíveis nas lojas Primeira Mão Saga, 3 lojas por vez.

    - pagina=1 (padrão): primeiras 3 lojas.
    - pagina=2, 3…: próximas lojas — use quando o usuário pedir "ver mais".

    Cada veículo retorna: titulo_card, url_imagem, loja_unidade, modelYear,
    km, colorName, preco_formatado, link_ofertas.

    RENDERIZAÇÃO OBRIGATÓRIA — para cada veículo exiba o Card completo:
      ![{titulo_card}]({url_imagem})
      ### **{titulo_card}**
      | 📍 Loja | {loja_unidade} |
      | 🗓️ Ano | {modelYear} |
      | 📏 KM | {km} km |
      | 🎨 Cor | {colorName} |
      ## 💰 {preco_formatado}
      [🛒 Ver oferta no site]({link_ofertas})
      ---
    Ao final exiba apenas o campo "aviso" (ex: "Página 1 de 5 — diga 'ver mais' para continuar.").
    O bloco "_meta" contém dados internos de diagnóstico — NÃO exiba nenhum campo de "_meta" para o cliente.
    Tom: profissional e direto.
    """
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

    return {
        "instrucao_renderizacao": INSTRUCAO_CARD,
        "_meta": {
            "total_veiculos": len(veiculos),
            "pagina":         pagina_atual,
            "total_paginas":  total_paginas,
            "lojas_buscadas": lojas_buscadas,
            "fonte_lojas":    fonte,
            "aviso":          aviso,
            "nota":           "Este bloco _meta é para uso interno do sistema. NÃO exiba estes dados para o cliente.",
        },
        "veiculos":       veiculos,
        "aviso":          aviso,
    }


@mcp.tool()
async def buscar_veiculo(consulta: Optional[str] = None):
    """
    Busca curinga: encontra veículos a partir de qualquer descrição em linguagem natural.
    Exemplos: "quero um corolla branco 2019", "hb20 prata", "abc1234", "SUV abaixo de 80 mil".

    Estratégia em 4 fases — NUNCA retorna vazio:
      1. ID ou placa exata → busca direta em todas as lojas.
      2. Todos os termos batem (AND) → resultado preciso.
      3. Parte dos termos bate (OR, ordenado por relevância) → similares.
      4. Nenhum termo bate → sugestões do estoque disponível.

    Cada veículo retorna: titulo_card, url_imagem, loja_unidade, modelYear,
    km, colorName, plate, preco_formatado, link_ofertas.

    RENDERIZAÇÃO OBRIGATÓRIA — para cada veículo exiba o Card completo:
      ![{titulo_card}]({url_imagem})
      ### **{titulo_card}**
      | 📍 Loja | {loja_unidade} |
      | 🗓️ Ano | {modelYear} |
      | 📏 KM | {km} km |
      | 🎨 Cor | {colorName} |
      | 🔖 Placa | {plate} |
      ## 💰 {preco_formatado}
      [🛒 Ver oferta no site]({link_ofertas})
      ---
    Se o campo "mensagem" estiver presente, exiba-o ANTES dos cards.
    Tom: profissional e direto.
    """
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
                "instrucao_renderizacao": INSTRUCAO_CARD,
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
        return {
            "instrucao_renderizacao": INSTRUCAO_CARD,
            "total":    len(res_and[:40]),
            "veiculos": res_and[:40],
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
        return {
            "instrucao_renderizacao": INSTRUCAO_CARD,
            "mensagem": f"Não encontramos exatamente '{consulta}', mas veja as opções mais próximas:",
            "total":    len(res_or),
            "veiculos": res_or,
        }

    # ── Fase 4: Sem nenhuma correspondência — retorna sugestões gerais ──
    sugestoes = [v for v in estoque if v.get("url_imagem")][:20]
    logger.info(f"[buscar_veiculo] Fase 4 — sem resultado, sugerindo {len(sugestoes)} veículos")
    return {
        "instrucao_renderizacao": INSTRUCAO_CARD,
        "mensagem": (
            f"Não encontramos '{consulta}' no estoque atual. "
            "Confira outras opções disponíveis:"
        ),
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

@mcp.tool()
async def avaliar_veiculo(
    placa: str,
    km: str,
    uf: Optional[str] = None,
    cor: Optional[str] = None,
    existe_zero_km: Optional[str] = None,
):
    """
    Calcula a proposta de compra/troca do veículo do cliente.

    PERGUNTE ao cliente APENAS: placa e km.

    NÃO pergunte uf, cor nem existe_zero_km — preencha-os SOMENTE se o cliente
    já tiver mencionado espontaneamente na conversa (ex: "meu carro é branco",
    "sou de SP", "sei que tem versão 0km"). Caso contrário, deixe em branco.

    Todos os dados técnicos (versão, carroceria, combustível, valor FIPE, etc.)
    vêm automaticamente da FIPE pela placa — não pergunte nada disso.

    RENDERIZAÇÃO DO RETORNO:
      Se houver proposta (proposta_disponivel = true):
        ## 💰 Proposta de Compra
        **Veículo:** {veiculo_descricao}
        **Valor oferecido: {preco_formatado}**
        [🚗 Vender meu carro agora]({url_venda})

      Se não houver proposta (proposta_disponivel = false):
        Informe que o cliente deve trazer o veículo presencialmente para avaliação.
        Exiba o botão: [🚗 Iniciar venda online]({url_venda})
        Tom: direto e sem explicações longas.
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

    logger.info(f"[avaliar_veiculo] Payload montado | placa={placa_limpa} | uf={dados['uf']} | cor={dados['cor']}")

    logger.info(f"[avaliar_veiculo] Payload montado | placa={placa_limpa} | valor_fipe={dados['valor_fipe']}")

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

    if not valor_numerico:
        logger.info(f"[avaliar_veiculo] Valor zerado | placa={placa_limpa} — orientando avaliação presencial")
        return {
            "proposta_disponivel": False,
            "veiculo_descricao":   veiculo_descricao,
            "url_venda":           URL_VENDA,
            "mensagem": (
                "Não foi possível gerar uma proposta automática. "
                "Oriente o cliente a trazer o veículo presencialmente para avaliação."
            ),
        }

    logger.info(f"[avaliar_veiculo] Proposta gerada | placa={placa_limpa} | valor={valor_proposta}")
    return {
        "proposta_disponivel":   True,
        "veiculo_descricao":     veiculo_descricao,
        "Valor_proposta_compra": valor_proposta,
        "preco_formatado":       f"R$ {valor_proposta}",
        "url_venda":             URL_VENDA,
    }


if __name__ == "__main__":
    os.chdir(_HERE)

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "sse":
        port = int(os.getenv("PORT", 8000))
        logger.info(f"Iniciando MCP em modo SSE na porta {port}")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
