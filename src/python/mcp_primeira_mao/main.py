import os
import sys

# Garante que o diretório do script está no sys.path independente do CWD.
# Necessário para o MCP Inspector, que pode rodar python main.py de outro diretório.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import json
import re
import unicodedata
import urllib.parse
import httpx
from typing import Optional
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult as _ToolResult
from fastmcp.server.apps import AppConfig, ResourceCSP
from mcp.types import ToolAnnotations, TextContent
from starlette.requests import Request
from starlette.responses import PlainTextResponse, FileResponse, Response, JSONResponse
from services.inventory_aggregator import InventoryAggregator
from services.lambda_inventory_service import LambdaInventoryService
from services.fipe_service import FipeService
from services.pricing_service import PricingService
from services.mobiauto_proposal_service import MobiautoProposalService
from utils.helpers import normalizar_placa
from config import logger

# ── Webhooks internos ──────────────────────────────────────────────
_WH_COMPRA   = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_comprar"
_WH_VENDA    = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_vender"
_WIDGET_URL  = os.getenv("WIDGET_URL", "https://mcp-primeiramao.sagadatadriven.com.br/ui/vehicle-offers.html")

# Desabilita fallback Mobiauto — usa apenas Lambda AWS como fonte de estoque.
# Para reativar o fallback, mude para False.
_LAMBDA_APENAS = True

# AppConfig para buscar_veiculos — coloca _meta.ui no descritor da tool,
# indicando ao ChatGPT qual recurso MCP carregar como widget (ui://vehicle-offers).
_APP_COMPRA = AppConfig(
    resource_uri="ui://vehicle-offers",
    prefers_border=True,
    csp=ResourceCSP(
        connect_domains=["https://mcp-primeiramao.sagadatadriven.com.br"],
        resource_domains=[
            "https://mcp-primeiramao.sagadatadriven.com.br",
            "https://images.primeiramaosaga.com.br",
            "https://www.primeiramaosaga.com.br",
        ],
    ),
)

_APP_VENDA = AppConfig(
    resource_uri="ui://vehicle-offers",
    prefers_border=True,
    csp=ResourceCSP(
        connect_domains=["https://mcp-primeiramao.sagadatadriven.com.br"],
        resource_domains=["https://mcp-primeiramao.sagadatadriven.com.br"],
    ),
)

async def _disparar_webhook(url: str, payload: dict, nome: str) -> bool:
    """Envia POST para o webhook interno. Aguarda confirmação antes de retornar."""
    payload_limpo = {k: v for k, v in payload.items() if v not in (None, "", [])}
    logger.info(f"[webhook.{nome}] >>> DISPARANDO | url={url} | campos={list(payload_limpo.keys())}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload_limpo)
            if resp.is_success:
                logger.info(f"[webhook.{nome}] <<< OK | status={resp.status_code}")
                return True
            logger.warning(f"[webhook.{nome}] <<< FALHOU | status={resp.status_code} | body={resp.text[:300]}")
            return False
    except Exception as e:
        logger.error(f"[webhook.{nome}] <<< ERRO | {type(e).__name__}: {e}")
        return False

mcp = FastMCP("PrimeiraMaoSaga")

# ── Verificação de domínio para ChatGPT Apps (OpenAI) ──────────────
# Token configurado em .env → OPENAI_CHALLENGE_TOKEN
@mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def _openai_domain_challenge(request: Request) -> PlainTextResponse:
    token = os.getenv("OPENAI_CHALLENGE_TOKEN", "")
    logger.info(f"[openai-challenge] Verificação de domínio solicitada | token_configurado={bool(token)}")
    return PlainTextResponse(token)


# ── Debug: inspeciona o que o servidor MCP expõe ──────────────────
# Acesse /debug/inspect para ver tools registradas e seus _meta.
# Útil para confirmar que openai/outputTemplate está no descriptor.
@mcp.custom_route("/debug/inspect", methods=["GET"])
async def _debug_inspect(request: Request) -> JSONResponse:
    _BASE = "https://mcp-primeiramao.sagadatadriven.com.br"

    # ── tools_wire: exatamente o que ChatGPT lê em tools/list ──
    tools_wire = []
    try:
        for t in (await mcp.list_tools() or []):
            mcp_tool = t.to_mcp_tool()
            tools_wire.append({
                "name":  mcp_tool.name,
                "_meta": mcp_tool.meta,
            })
    except Exception as e:
        tools_wire = [{"error": str(e)}]

    # ── resources_wire: uri + mimeType + _meta (como o SDK serializa) ──
    resources_wire = []
    try:
        for r in (await mcp.list_resources() or []):
            mcp_res = r.to_mcp_resource()
            resources_wire.append({
                "uri":      str(mcp_res.uri),
                "mimeType": mcp_res.mimeType,
                "_meta":    mcp_res.meta,
            })
    except Exception as e:
        resources_wire = [{"error": str(e)}]

    # ── html_preview: HTML completo servido por ui://vehicle-offers (após substituição) ──
    html_preview = None
    try:
        with open(os.path.join(_UI_DIR, "vehicle-offers.html"), "r", encoding="utf-8") as _f:
            _raw = _f.read()
        _served = _raw.replace("STATIC_BASE", f"{_BASE}/static")
        html_preview = _served
    except Exception as e:
        html_preview = {"error": str(e)}

    # ── resource_preview: MIME + primeiros 400 chars via MCP resource ──
    resource_preview = None
    try:
        result = await mcp.read_resource("ui://vehicle-offers")
        contents = getattr(result, "contents", None) or []
        content = contents[0] if contents else result
        text = getattr(content, "text", None) or getattr(content, "data", None) or str(content)
        resource_preview = {
            "mimeType": getattr(content, "mimeType", None) or getattr(content, "mime_type", None),
            "preview":  str(text)[:400],
        }
    except Exception as e:
        resource_preview = {"error": str(e)}

    # ── static_js_status / static_css_status: arquivos em disco ──
    _js_path  = os.path.join(_UI_DIR, "vehicle-offers.js")
    _css_path = os.path.join(_UI_DIR, "vehicle-offers.css")
    static_js_status = {
        "url":    f"{_BASE}/static/vehicle-offers.js",
        "exists": os.path.isfile(_js_path),
        "size":   os.path.getsize(_js_path) if os.path.isfile(_js_path) else 0,
    }
    static_css_status = {
        "url":    f"{_BASE}/static/vehicle-offers.css",
        "exists": os.path.isfile(_css_path),
        "size":   os.path.getsize(_css_path) if os.path.isfile(_css_path) else 0,
    }

    # ── tool_result_preview: chama buscar_veiculos(Goiânia) e inspeciona o retorno ──
    tool_result_preview = None
    try:
        _tool = await mcp.get_tool("buscar_veiculos")
        if _tool:
            _call = await _tool.run({"cidade": "Goiânia"})
            _sc   = getattr(_call, "structured_content", None) or {}
            _cnt  = getattr(_call, "content", None)
            _content_text = None
            if isinstance(_cnt, list) and _cnt:
                _content_text = getattr(_cnt[0], "text", str(_cnt[0]))
            elif _cnt:
                _content_text = str(_cnt)
            tool_result_preview = {
                "content_text":                     _content_text,
                "structuredContent_type":           _sc.get("type") if isinstance(_sc, dict) else None,
                "structuredContent_vehicles_length": len(_sc.get("vehicles", [])) if isinstance(_sc, dict) else None,
                "structuredContent_preview":        str(_sc)[:300] if _sc else None,
            }
    except Exception as e:
        tool_result_preview = {"error": str(e)}

    return JSONResponse({
        "transport":           os.getenv("MCP_TRANSPORT", "stdio"),
        "tools_wire":          tools_wire,
        "resources_wire":      resources_wire,
        "html_preview":        html_preview,
        "resource_preview":    resource_preview,
        "static_js_status":    static_js_status,
        "static_css_status":   static_css_status,
        "tool_result_preview": tool_result_preview,
    })


# ── Serving estático da UI (arquivos separados) ────────────────────
# CSP definida no header HTTP — mais segura que meta tag no HTML.
# Com script-src 'self' e style-src 'self' (sem 'unsafe-inline').
_UI_DIR = os.path.join(_HERE, "ui")

_UI_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src https: data:; "
    "connect-src 'self'; "
    "frame-ancestors https://chatgpt.com https://*.chatgpt.com "
    "https://chat.openai.com https://*.chat.openai.com 'self';"
)

_MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
}

def _serve_ui_file(filename: str) -> Response:
    """Retorna um arquivo da pasta ui/ com CSP e cache headers corretos."""
    # Bloqueia path traversal — aceita apenas nomes sem separadores
    if "/" in filename or "\\" in filename or ".." in filename:
        return Response(status_code=404)
    path = os.path.join(_UI_DIR, filename)
    if not os.path.isfile(path):
        return Response(status_code=404)
    ext = os.path.splitext(filename)[1].lower()
    mime = _MIME_MAP.get(ext, "application/octet-stream")
    headers = {
        "Content-Security-Policy": _UI_CSP,
        "X-Content-Type-Options":  "nosniff",
        # X-Frame-Options omitido — frame-ancestors na CSP é a diretiva correta e
        # tem precedência. ALLOWALL é não-standard e ignorado em Firefox/Safari.
        "Cache-Control":           "no-store",
    }
    return FileResponse(path, media_type=mime, headers=headers)

@mcp.custom_route("/ui/vehicle-offers.html", methods=["GET"])
async def _serve_ui_html(request: Request) -> Response:
    # text/html;profile=mcp-app é o MIME type oficial do Apps SDK (OpenAI docs).
    # Sem ele o ChatGPT não reconhece a resposta como widget e cai no fallback textual.
    path = os.path.join(_UI_DIR, "vehicle-offers.html")
    if not os.path.isfile(path):
        return Response(status_code=404)
    headers = {
        "Content-Security-Policy": _UI_CSP,
        "X-Content-Type-Options":  "nosniff",
        "Cache-Control":           "no-store",
    }
    return FileResponse(path, media_type="text/html;profile=mcp-app", headers=headers)

@mcp.custom_route("/ui/vehicle-offers.css", methods=["GET"])
async def _serve_ui_css(request: Request) -> Response:
    return _serve_ui_file("vehicle-offers.css")

@mcp.custom_route("/ui/vehicle-offers.js", methods=["GET"])
async def _serve_ui_js(request: Request) -> Response:
    return _serve_ui_file("vehicle-offers.js")

# Rotas /static/ — usadas pelo resource ui://vehicle-offers (sem CSP meta inline)
@mcp.custom_route("/static/vehicle-offers.css", methods=["GET"])
async def _serve_static_css(request: Request) -> Response:
    return _serve_ui_file("vehicle-offers.css")

@mcp.custom_route("/static/vehicle-offers.js", methods=["GET"])
async def _serve_static_js(request: Request) -> Response:
    return _serve_ui_file("vehicle-offers.js")


@mcp.resource(
    "ui://vehicle-offers",
    mime_type="text/html;profile=mcp-app",
    meta={
        "openai/widgetDomain": "https://mcp-primeiramao.sagadatadriven.com.br",
        "openai/widgetCSP": {
            "connect_domains": [
                "https://mcp-primeiramao.sagadatadriven.com.br",
            ],
            "resource_domains": [
                "https://mcp-primeiramao.sagadatadriven.com.br",
                "https://images.primeiramaosaga.com.br",
                "https://www.primeiramaosaga.com.br",
            ],
        },
    },
)
async def _resource_vehicle_offers() -> str:
    """HTML do widget de veículos — carregado como recurso MCP pelo ChatGPT Apps."""
    with open(os.path.join(_UI_DIR, "vehicle-offers.html"), "r", encoding="utf-8") as f:
        html = f.read()
    base = "https://mcp-primeiramao.sagadatadriven.com.br"
    # STATIC_BASE é o placeholder do HTML — substitui com URL absoluta da rota /static/
    html = html.replace("STATIC_BASE", f"{base}/static")
    return html


async def _buscar_ofertas_json(cidade: str, consulta: str | None, filtros: dict | None = None) -> dict:
    """Lógica compartilhada entre /local/ofertas e /api/ofertas."""
    veiculos_brutos = await LambdaInventoryService.buscar(cidade, filtros)
    fonte = "lambda"
    lojas_cidade = []

    if not veiculos_brutos and not _LAMBDA_APENAS:
        # FALLBACK MOBIAUTO — desabilitado (_LAMBDA_APENAS = True)
        logger.info(f"[/api/ofertas] Lambda vazia para '{cidade}' — usando fallback Mobiauto")
        lojas        = await InventoryAggregator.obter_lista_lojas()
        lojas_cidade = _filtrar_lojas_por_cidade(lojas, cidade)
        if not lojas_cidade:
            return {"vehicles": [], "searchContext": {"city": cidade.upper()}, "message": f"Sem lojas em {cidade}"}
        veiculos_brutos = await InventoryAggregator.buscar_estoque_por_lojas(lojas_cidade, limit=25)
        fonte = "mobiauto"

    if not veiculos_brutos:
        return {"vehicles": [], "searchContext": {"city": cidade.upper()}, "message": f"Sem veículos encontrados em {cidade}"}

    logger.info(f"[/api/ofertas] fonte={fonte} | brutos={len(veiculos_brutos)}")
    veiculos_com_img = [v for v in veiculos_brutos if v.get("url_imagem")]

    if consulta:
        palavras = _extrair_palavras_chave(consulta)
        if palavras:
            scored = [(v, _score_veiculo(v, palavras)) for v in veiculos_com_img]
            scored.sort(key=lambda x: x[1], reverse=True)
            hits = [v for v, s in scored if s > 0]
            veiculos_com_img = (hits or veiculos_com_img)[:20]
        else:
            veiculos_com_img = veiculos_com_img[:20]
    else:
        veiculos_com_img = veiculos_com_img[:20]

    cards = [_veiculo_para_card(v) for v in veiculos_com_img]
    nomes_lojas = (
        list({v.get("loja_unidade", "") for v in veiculos_com_img if v.get("loja_unidade")})
        if fonte == "lambda"
        else [l["nome"] for l in lojas_cidade]
    )

    logger.info(f"[/api/ofertas] cidade='{cidade}' | fonte={fonte} | veículos={len(cards)}")
    return {"vehicles": cards, "searchContext": {"store": ", ".join(nomes_lojas), "city": cidade.upper()}}


@mcp.custom_route("/api/ofertas", methods=["GET"])
async def _api_ofertas(request: Request) -> Response:
    """Endpoint público para o widget em produção."""
    qp       = request.query_params
    cidade   = qp.get("cidade", "Goiânia")
    consulta = qp.get("consulta") or None
    filtros  = {k: qp.get(k) for k in ("marca","modelo","versao","preco_min","preco_max","km_max","ano_min","ano_max") if qp.get(k)}
    return JSONResponse(await _buscar_ofertas_json(cidade, consulta, filtros or None))


@mcp.custom_route("/local/ofertas", methods=["GET"])
async def _api_ofertas_local(request: Request) -> Response:
    """Endpoint REST para teste local do widget — mantido para compatibilidade."""
    host        = request.headers.get("host", "")
    client_host = request.client.host if request.client else ""
    is_local    = (
        host.startswith("localhost")
        or host.startswith("127.0.0.1")
        or client_host in ("127.0.0.1", "::1")
    )
    if not is_local:
        return Response(status_code=403)
    cidade   = request.query_params.get("cidade", "Goiânia")
    consulta = request.query_params.get("consulta") or None
    return JSONResponse(await _buscar_ofertas_json(cidade, consulta))


def _local_guard(request: Request) -> bool:
    """Retorna True se a requisição veio de localhost."""
    host        = request.headers.get("host", "")
    client_host = request.client.host if request.client else ""
    return (
        host.startswith("localhost")
        or host.startswith("127.0.0.1")
        or client_host in ("127.0.0.1", "::1")
    )


@mcp.custom_route("/local/formulario-venda", methods=["GET"])
async def _local_formulario_venda(request: Request) -> Response:
    """Endpoint local para testar o formulário de venda — aceita params via URL."""
    if not _local_guard(request):
        return Response(status_code=403)

    p              = request.query_params
    veiculo_descricao = p.get("veiculo", "Toyota Corolla 2.0 XEI 2021")
    placa          = p.get("placa",   "ABC1D23")
    km             = p.get("km",      "52000")
    valor_proposta = p.get("proposta","R$ 85.000,00")

    proposta_str = str(valor_proposta).strip()
    if proposta_str and not proposta_str.startswith("R$"):
        proposta_str = f"R$ {proposta_str}"

    return JSONResponse({
        "mode": "sell",
        "evaluation": {
            "vehicleDescription": veiculo_descricao,
            "plate":              placa,
            "km":                 km,
            "kmFormatted":        _fmt_km(km),
            "proposal":           proposta_str,
        },
        "searchContext": {"city": "GOIÂNIA/GO"},
    })


@mcp.custom_route("/local/registrar-compra", methods=["POST"])
async def _local_registrar_compra(request: Request) -> Response:
    """Endpoint local para teste de registro de interesse de compra."""
    if not _local_guard(request):
        return Response(status_code=403)
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    result = await _criar_lead_compra(
        nome_cliente     = body.get("nome_cliente", ""),
        telefone_cliente = body.get("telefone_cliente", ""),
        email_cliente    = body.get("email_cliente", ""),
        titulo_card      = body.get("titulo_veiculo") or body.get("titulo_card"),
        veiculo_id       = body.get("veiculo_id"),
        preco_formatado  = body.get("preco_formatado"),
        loja_unidade     = body.get("loja_unidade"),
        plate            = body.get("plate"),
        modelYear        = body.get("modelYear"),
        km               = body.get("km"),
        colorName        = body.get("colorName"),
        observacao       = body.get("observacao"),
    )
    return JSONResponse(result)


@mcp.custom_route("/local/registrar-venda", methods=["POST"])
async def _local_registrar_venda(request: Request) -> Response:
    """Endpoint local para teste de registro de interesse de venda."""
    if not _local_guard(request):
        return Response(status_code=403)
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    result = await _criar_lead_venda(
        nome_cliente      = body.get("nome_cliente", ""),
        telefone_cliente  = body.get("telefone_cliente", ""),
        email_cliente     = body.get("email_cliente", ""),
        placa             = body.get("placa"),
        km                = body.get("km"),
        veiculo_descricao = body.get("veiculo_descricao"),
        valor_proposta    = body.get("valor_proposta"),
        uf                = body.get("uf"),
        observacao        = body.get("observacao"),
    )
    return JSONResponse(result)


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

def _norm(s: str) -> str:
    """Normaliza texto para comparação: remove acentos, lowercase, strip."""
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()


def _filtrar_lojas_por_cidade(lojas: list, cidade: str) -> list:
    """Retorna lojas cujo nome, cidade ou UF contenham o termo informado (sem acento, case-insensitive)."""
    termo = _norm(cidade)
    return [
        l for l in lojas
        if termo in _norm(l.get("cidade") or "")
        or termo in _norm(l.get("uf") or "")
        or termo in _norm(l.get("nome") or "")
    ]


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
    """Gera o bloco Markdown de um card no estilo Localiza — imagem + specs + preço."""
    url_img     = v.get("url_imagem") or ""
    marca       = v.get("makeName") or ""
    modelo      = v.get("modelName") or ""
    versao      = v.get("trimName") or ""
    ano         = str(v.get("modelYear") or "")
    cor         = v.get("colorName") or ""
    placa       = v.get("plate") or ""
    loja        = v.get("loja_unidade") or ""
    preco       = v.get("preco_formatado") or "R$ --"
    link        = v.get("link_ofertas") or "https://www.primeiramaosaga.com.br/gradedeofertas"
    km_fmt      = _fmt_km(v.get("km"))
    carroceria  = v.get("carroceria") or ""
    transmissao = v.get("transmissao") or ""
    combustivel = v.get("combustivel") or ""
    portas      = v.get("portas") or ""
    opcionais   = v.get("opcionais") or []

    # ── Linha de categoria (ex: "Sedan · Automática · Flex · 4 portas") ──
    specs = [p for p in [carroceria, transmissao, combustivel,
                         f"{portas} portas" if portas else ""] if p]
    specs_str = " · ".join(specs) if specs else ""

    # ── Linha de detalhes (loja, km, cor, placa) ──
    detalhes = []
    if loja:
        detalhes.append(f"🏪 **{loja}**")
    if km_fmt:
        detalhes.append(f"📏 {km_fmt} km")
    if cor:
        detalhes.append(f"🎨 {cor}")
    if placa and mostrar_placa:
        detalhes.append(f"🔖 {placa}")
    detalhes_str = " · ".join(detalhes) if detalhes else ""

    # ── Opcionais destacados ──
    opcionais_str = " · ".join(opcionais[:4]) if opcionais else ""

    linhas = []
    if url_img:
        linhas.append(f"![{marca} {modelo} {ano}]({url_img})")
    linhas.append(f"### {marca} {modelo} {ano}")
    if versao:
        linhas.append(f"*{versao}*")
    if specs_str:
        linhas.append(f"**{specs_str}**")
    linhas.append("")
    if detalhes_str:
        linhas.append(detalhes_str)
    if opcionais_str:
        linhas.append(f"✅ {opcionais_str}")
    linhas.append("")
    linhas.append(f"### 💰 {preco}")
    linhas.append(f"[🌐 Ver oferta no site]({link})")
    linhas.append("")
    linhas.append("---")
    return "\n".join(linhas)


# CTA embutido no final de qualquer lista de cards — garante que o cliente sempre veja as opções
_CTA_OPCOES = (
    "\n---\n\n"
    "**Gostou de algum veículo?** 😊\n\n"
    "📲 **Falar com um consultor Saga** — informe seu **nome** e **telefone** e um consultor "
    "**entra em contato com você via WhatsApp** para ajudar na compra.\n\n"
    "Ou explore mais opções diretamente: "
    "[Livro de Ofertas Primeira Mão](https://www.primeiramaosaga.com.br/gradedeofertas)"
)


def _renderizar_cards(
    veiculos: list,
    mensagem: str = None,
    aviso: str = None,
    mostrar_placa: bool = False,
) -> str:
    """Gera Markdown de uma lista de cards com CTA embutido ao final."""
    partes = []
    if mensagem:
        partes.append(f"> {mensagem}\n")
    for v in veiculos:
        partes.append(_renderizar_card(v, mostrar_placa=mostrar_placa))
    if aviso:
        partes.append(f"\n*{aviso}*")
    if veiculos:
        partes.append(_CTA_OPCOES)
    return "\n".join(partes)


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
    wh_ok = await _disparar_webhook(_WH_COMPRA, {
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

    # Considera sucesso se Mobiauto CRM OU webhook interno capturou o lead
    success = resultado.get("success", False) or wh_ok
    status_log = "OK" if success else "FALHOU"
    logger.warning(
        f"[_criar_lead_compra] <<< {status_log} | mobi={resultado.get('success')} | wh={wh_ok} | "
        f"dealer_id={resultado.get('dealer_id')} | cliente='{nome_cliente}' | "
        f"mobi_erro={resultado.get('error', '-')} | detalhe={resultado.get('detalhe', '-')[:200]}"
    )
    return {
        "registrado":    success,
        "dealer_id":     resultado.get("dealer_id"),
        "fallback_url":  "https://www.primeiramaosaga.com.br/gradedeofertas",
        "_debug_error":  None if success else {
            "mobi_error":  resultado.get("error"),
            "mobi_detail": resultado.get("detalhe"),
            "dealer_id":   resultado.get("dealer_id"),
            "wh_ok":       wh_ok,
        },
        "mensagem": (
            f"Pronto, {nome_cliente}! Em breve um consultor da Saga entrará em contato com você via WhatsApp. "
            f"Enquanto isso, fique à vontade para ver a oferta no site: "
            f"https://www.primeiramaosaga.com.br/gradedeofertas"
            if success else
            f"Não foi possível registrar agora: {resultado.get('error', 'erro desconhecido')}. "
            "Acesse o site como alternativa."
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
    wh_ok = await _disparar_webhook(_WH_VENDA, {
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

    # Considera sucesso se Mobiauto CRM OU webhook interno capturou o lead
    success = resultado.get("success", False) or wh_ok
    status_log = "OK" if success else "FALHOU"
    logger.warning(
        f"[_criar_lead_venda] <<< {status_log} | mobi={resultado.get('success')} | wh={wh_ok} | "
        f"dealer_id={resultado.get('dealer_id')} | cliente='{nome_cliente}' | "
        f"mobi_erro={resultado.get('error', '-')} | detalhe={resultado.get('detalhe', '-')[:200]}"
    )
    return {
        "registrado":    success,
        "dealer_id":     resultado.get("dealer_id"),
        "fallback_url":  "https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente",
        "_debug_error":  None if success else {
            "mobi_error":  resultado.get("error"),
            "mobi_detail": resultado.get("detalhe"),
            "dealer_id":   resultado.get("dealer_id"),
            "wh_ok":       wh_ok,
        },
        "mensagem": (
            f"Pronto, {nome_cliente}! Um consultor da Saga entrará em contato com você em breve via WhatsApp "
            f"para prosseguir com a avaliação. Fique atento ao número informado."
            if success else
            f"Não foi possível registrar agora: {resultado.get('error', 'erro desconhecido')}. "
            "Acesse o link de avaliação online como alternativa."
        ),
    }


# ─────────────────────────────────────────────────────────────
# HELPER: mapeamento de veículo do inventário para contrato da UI
# ─────────────────────────────────────────────────────────────

def _veiculo_para_card(v: dict) -> dict:
    """Converte um veículo do inventário no contrato esperado pelo widget."""
    marca  = v.get("makeName",  "") or ""
    modelo = v.get("modelName", "") or ""
    versao = v.get("trimName",  "") or ""
    ano    = str(v.get("modelYear", "") or "").strip()
    # Ignora "nan" que pandas pode produzir via json.dumps
    if ano.lower() in ("nan", "none", ""):
        ano = ""

    titulo_parts = [p for p in [marca, modelo, ano] if p]
    title = " ".join(titulo_parts) or "Veículo disponível"

    # Preço: usa string formatada se disponível; senão passa o float para o JS formatar
    preco_fmt = v.get("preco_formatado") or ""
    if not preco_fmt:
        sale = v.get("salePrice") or v.get("price") or 0
        try:
            sale = float(sale)
        except (TypeError, ValueError):
            sale = 0.0
        preco_fmt = sale if sale > 0 else ""

    return {
        "id":           str(v.get("id", "")),
        "title":        title,
        "brand":        marca,
        "model":        modelo,
        "version":      versao,
        "year":         ano,
        "km":           str(v.get("km", "") or ""),
        "kmFormatted":  _fmt_km(v.get("km")),
        "transmission": v.get("transmissao", "") or "",
        "fuel":         v.get("combustivel", "") or "",
        "color":        v.get("colorName",   "") or "",
        "price":        preco_fmt,
        "imageUrl":     v.get("url_imagem",  "") or "",
        "images":       [{"url": u} for u in v.get("imagens_urls", []) if u],
        "store":        v.get("loja_unidade","") or "",
        "location":     v.get("loja_unidade","") or "",
        "link":         v.get("link_ofertas","") or "https://www.primeiramaosaga.com.br/gradedeofertas",
    }


# ─────────────────────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False, destructiveHint=False))
async def listar_lojas():
    """
    Lista todas as lojas Primeira Mão Saga cadastradas com nome, cidade e UF.

    NÃO USE para busca de carros, para descobrir cidades disponíveis ou para qualquer contexto de compra.
    Use SOMENTE quando o cliente perguntar explicitamente "quais são as lojas?" ou "onde vocês têm loja?".

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
async def estoque_total(cidade: Optional[str] = None):
    """
    NÃO USE — use `buscar_veiculos` (com 's') para exibir o widget visual de veículos.

    Esta ferramenta existe apenas para compatibilidade interna.
    Para qualquer listagem de carros, use `buscar_veiculos` com o parâmetro `cidade`.
    """
    if not cidade or not cidade.strip():
        return (
            "> Para mostrar os veículos disponíveis, preciso saber: "
            "**em qual cidade você procura o veículo?**"
        )

    logger.info(f"[estoque_total] Chamada iniciada | cidade='{cidade}'")
    lojas = await InventoryAggregator.obter_lista_lojas()
    fonte = InventoryAggregator._ultima_fonte or "desconhecida"

    lojas_cidade = _filtrar_lojas_por_cidade(lojas, cidade)
    logger.info(f"[estoque_total] Lojas encontradas para '{cidade}': {[l['nome'] for l in lojas_cidade]}")

    if not lojas_cidade:
        return (
            f"> Não encontramos lojas Primeira Mão em **{cidade}**. "
            "Tente outra cidade ou UF, ou [veja todas as opções no site]"
            "(https://www.primeiramaosaga.com.br/gradedeofertas)."
        )

    veiculos = await InventoryAggregator.buscar_estoque_por_lojas(lojas_cidade, limit=25)
    nomes_lojas = [l["nome"] for l in lojas_cidade]
    logger.info(f"[estoque_total] Concluída | veículos={len(veiculos)} | lojas={nomes_lojas} | fonte={fonte}")

    if not veiculos:
        return (
            f"> Não há veículos disponíveis no momento em **{cidade}**. "
            "Tente novamente em instantes ou entre em contato com uma de nossas lojas."
        )

    aviso = f"Exibindo até 25 veículos · Lojas em {cidade}: {', '.join(nomes_lojas)}"
    return _renderizar_cards(veiculos, aviso=aviso)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False))
async def buscar_veiculo(
    consulta: Optional[str] = None,
    cidade: Optional[str] = None,
):
    """
    NÃO USE PARA COMPRA DE VEÍCULOS — use `buscar_veiculos` (com 's') para isso.

    Esta ferramenta é reservada para busca por ID ou placa exata de um veículo específico
    já mencionado na conversa (ex: "me mostra detalhes do ABC1234").

    Para qualquer pedido de compra, marca, modelo ou listagem de carros:
    CHAME `buscar_veiculos` diretamente, sem perguntas.
    """
    if not consulta or not consulta.strip():
        return await estoque_total(cidade=cidade)

    logger.info(f"[buscar_veiculo] Chamada iniciada | consulta='{consulta}' | cidade='{cidade}'")
    termo = consulta.strip()

    # ── Fase 1: ID ou placa exata (só executa se o termo parece placa/ID) ──
    if _parece_id_ou_placa(termo):
        resultado_exato = await InventoryAggregator.buscar_veiculo_especifico(termo)
        if resultado_exato:
            logger.info(f"[buscar_veiculo] Fase 1 — encontrado por ID/placa")
            return _renderizar_cards([resultado_exato], mostrar_placa=True)

    # ── Carrega estoque: filtrado por cidade quando informada ──
    if cidade and cidade.strip():
        lojas = await InventoryAggregator.obter_lista_lojas()
        lojas_cidade = _filtrar_lojas_por_cidade(lojas, cidade)
        if lojas_cidade:
            logger.info(f"[buscar_veiculo] Buscando nas lojas de '{cidade}': {[l['nome'] for l in lojas_cidade]}")
            estoque = await InventoryAggregator.buscar_estoque_por_lojas(lojas_cidade, limit=200)
        else:
            logger.warning(f"[buscar_veiculo] Nenhuma loja em '{cidade}' — buscando em todas")
            estoque = await InventoryAggregator.buscar_estoque_consolidado(limit=None)
    else:
        estoque = await InventoryAggregator.buscar_estoque_consolidado(limit=None)

    logger.info(f"[buscar_veiculo] Estoque carregado | {len(estoque)} veículos")

    # Extrai palavras-chave ignorando artigos/stopwords ("quero", "um", "cor", etc.)
    palavras = _extrair_palavras_chave(consulta)
    if not palavras:
        palavras = [termo.lower()]  # fallback: usa o termo bruto
    logger.info(f"[buscar_veiculo] Palavras-chave extraídas | {palavras}")

    # ── Fase 2: AND — veículos que batem com TODOS os termos ──
    res_and = [v for v in estoque if _score_veiculo(v, palavras) == len(palavras)]
    if res_and:
        logger.info(f"[buscar_veiculo] Fase 2 (AND) — {len(res_and)} resultados exatos")
        veiculos_and = [v for v in res_and if v.get("url_imagem")][:25]
        return _renderizar_cards(veiculos_and, mostrar_placa=True)

    # ── Fase 3: OR com ranking — ordena por quantos termos batem ──
    scored = [
        (v, _score_veiculo(v, palavras))
        for v in estoque
        if _score_veiculo(v, palavras) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored:
        res_or = [v for v, _ in scored if v.get("url_imagem")][:25]
        top_score = scored[0][1]
        logger.info(f"[buscar_veiculo] Fase 3 (OR) — {len(res_or)} similares | top_score={top_score}/{len(palavras)}")
        msg_or = f"Não encontramos exatamente \"{consulta}\", mas veja as opções mais próximas:"
        return _renderizar_cards(res_or, mensagem=msg_or, mostrar_placa=True)

    # ── Fase 4: Sem nenhuma correspondência — retorna sugestões gerais ──
    sugestoes = [v for v in estoque if v.get("url_imagem")][:25]
    logger.info(f"[buscar_veiculo] Fase 4 — sem resultado, sugerindo {len(sugestoes)} veículos")

    if not sugestoes:
        return (
            f"> Não encontramos **\"{consulta}\"** e não há veículos disponíveis no estoque no momento. "
            "Tente novamente em breve ou entre em contato com uma de nossas lojas."
        )

    msg_f4 = f"Não encontramos \"{consulta}\" no estoque atual. Confira outras opções disponíveis:"
    return _renderizar_cards(sugestoes, mensagem=msg_f4, mostrar_placa=True)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False),
    app=_APP_COMPRA,
    # _APP_COMPRA já injeta _meta.ui.resourceUri no descriptor via AppConfig.
    # meta= adiciona openai/outputTemplate ao mesmo nível — obrigatório para ChatGPT Apps.
    meta={"openai/outputTemplate": "ui://vehicle-offers"},
)
async def buscar_veiculos(
    cidade: str,
    consulta: Optional[str] = None,
    marca: Optional[str] = None,
    modelo: Optional[str] = None,
    versao: Optional[str] = None,
    preco_min: Optional[float] = None,
    preco_max: Optional[float] = None,
    km_max: Optional[int] = None,
    ano_min: Optional[int] = None,
    ano_max: Optional[int] = None,
    task_progress: Optional[str] = None,
):
    """
    Retorna dados estruturados para o componente ui://vehicle-offers.
    Não gere tabela, bullets ou lista de veículos. Após a chamada, responda apenas com o content.text curto.

    ═══ REGRA ABSOLUTA — ANTES DE CHAMAR ═══
    CHAME IMEDIATAMENTE assim que cidade for conhecida.
    NÃO pergunte marca, modelo, tipo, preço ou qualquer filtro antes de chamar.
    ÚNICO caso para perguntar: cidade não foi mencionada. Pergunte SÓ: "Em qual cidade?"

    ═══ REGRA ABSOLUTA — APÓS RETORNAR ═══
    NÃO adicione texto. NÃO liste carros. NÃO descreva modelos, preços ou km.
    NÃO gere tabela, bullets, Markdown ou JSON com veículos.
    Aguarde o cliente falar. Se ele disser "picape", "HB20", etc.
    → chame buscar_veiculos IMEDIATAMENTE com esse filtro.
    Se ele disser nome + telefone → chame registrar_interesse_compra.

    ═══ EXEMPLOS ═══
    "quero um carro em Goiânia"       → buscar_veiculos(cidade="Goiânia")
    "tem Polo?" (cidade já conhecida) → buscar_veiculos(cidade="Goiânia", modelo="Polo")
    "HB20 até 60 mil em Brasília"     → buscar_veiculos(cidade="Brasília", modelo="HB20", preco_max=60000)

    Filtros opcionais — preencha APENAS com o que o cliente já informou espontaneamente:
    - marca, modelo, versao, consulta, preco_min, preco_max, km_max, ano_min, ano_max
    """
    if not cidade or not cidade.strip():
        return "Informe a cidade para buscar veículos."

    filtros = {k: v for k, v in {
        "marca":     marca,
        "modelo":    modelo,
        "versao":    versao,
        "preco_min": preco_min,
        "preco_max": preco_max,
        "km_max":    km_max,
        "ano_min":   ano_min,
        "ano_max":   ano_max,
    }.items() if v is not None}

    logger.info(f"[buscar_veiculos] Chamada | cidade='{cidade}' | consulta='{consulta}' | filtros={filtros}")

    veiculos_brutos = await LambdaInventoryService.buscar(cidade, filtros or None)

    if not veiculos_brutos:
        logger.warning(f"[buscar_veiculos] Lambda retornou vazio para '{cidade}'")
        return f"Não encontramos veículos disponíveis em {cidade} com esses critérios."

    n = len(veiculos_brutos)

    # Filtra com imagem e aplica scoring por consulta (texto livre)
    veiculos_com_img = [v for v in veiculos_brutos if v.get("url_imagem")]
    if consulta:
        palavras = _extrair_palavras_chave(consulta)
        if palavras:
            scored = [(v, _score_veiculo(v, palavras)) for v in veiculos_com_img]
            scored.sort(key=lambda x: x[1], reverse=True)
            hits = [v for v, s in scored if s > 0]
            veiculos_exibir = (hits or veiculos_com_img)[:20]
        else:
            veiculos_exibir = veiculos_com_img[:20]
    else:
        veiculos_exibir = veiculos_com_img[:20]

    # Monta URL do widget com todos os parâmetros de busca
    url_params: dict = {"cidade": cidade}
    if consulta:
        url_params["consulta"] = consulta
    url_params.update({k: str(v) for k, v in filtros.items()})
    widget_url = _WIDGET_URL + "?" + urllib.parse.urlencode(url_params)

    filtro_desc = ", ".join(f"{k}: {v}" for k, v in filtros.items())
    mensagem_header = (
        f"Encontrei {n} veículos em {cidade}"
        + (f" · {filtro_desc}" if filtro_desc else "")
    )

    cards = [_veiculo_para_card(v) for v in veiculos_exibir]
    nomes_lojas = list({v.get("loja_unidade", "") for v in veiculos_exibir if v.get("loja_unidade")})

    logger.info(f"[buscar_veiculos] → widget | n={n} | exibindo={len(veiculos_exibir)} | url={widget_url}")

    sc = {
        "type":          "vehicle_cards",
        "vehicles":      cards,
        "searchContext": {
            "city":  cidade.upper(),
            "store": ", ".join(nomes_lojas),
        },
    }

    return _ToolResult(
        content=TextContent(
            type="text",
            text=f"Encontrei veículos em {cidade}. Veja os cards abaixo.",
        ),
        structured_content=sc,
    )


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False, destructiveHint=False),
    app=_APP_VENDA,
    meta={"openai/outputTemplate": "ui://vehicle-offers"},
)
async def exibir_formulario_venda(
    veiculo_descricao: str,
    placa: Optional[str] = None,
    km: Optional[str] = None,
    valor_proposta: Optional[str] = None,
):
    """
    Exibe o formulário visual de venda — chame IMEDIATAMENTE após avaliar_veiculo.

    Mostra ao cliente um card com os dados do veículo e a proposta Saga,
    com formulário para informar nome e telefone. Um consultor entra em contato via WhatsApp.

    Parâmetros:
    - veiculo_descricao: descrição do veículo (ex: "Toyota Corolla 2.0 XEI 2021")
    - placa: placa do veículo avaliado
    - km: quilometragem (ex: "52000")
    - valor_proposta: proposta de compra calculada (ex: "85000" ou "R$ 85.000,00")

    Após exibir: NÃO peça nome/telefone no chat — o formulário visual os coleta.
    """
    proposta_str = str(valor_proposta or "").strip()
    if proposta_str and not proposta_str.startswith("R$"):
        proposta_str = f"R$ {proposta_str}"

    km_fmt = _fmt_km(km) if km else ""

    logger.info(
        f"[exibir_formulario_venda] veiculo='{veiculo_descricao}' | placa={placa} | "
        f"km={km} | proposta='{proposta_str}'"
    )

    # Passa todos os dados de avaliação como URL params — o widget lê direto,
    # sem precisar de chamada de API (funciona em produção e em iframe no ChatGPT).
    url_params: dict = {"mode": "sell", "veiculo": veiculo_descricao}
    if placa:        url_params["placa"]    = placa
    if km:           url_params["km"]       = km
    if km_fmt:       url_params["km_fmt"]   = km_fmt
    if proposta_str: url_params["proposta"] = proposta_str

    widget_url = _WIDGET_URL + "?" + urllib.parse.urlencode(url_params)

    texto = (
        f"Proposta Saga de {proposta_str} para {veiculo_descricao}. Formulário de contato exibido."
        if proposta_str else
        f"Formulário de avaliação exibido para {veiculo_descricao}."
    )

    return _ToolResult(
        content=TextContent(type="text", text=texto),
        structured_content={
            "mode":     "sell",
            "veiculo":  veiculo_descricao,
            "placa":    placa or "",
            "km":       km or "",
            "km_fmt":   km_fmt,
            "proposta": proposta_str,
        },
        meta={
            "openai/outputTemplate": widget_url,
        },
    )


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
):
    """
    Calcula a proposta de compra/troca do veículo do cliente.

    PERGUNTE ao cliente APENAS: placa e km.

    NÃO pergunte uf, cor nem existe_zero_km — preencha-os SOMENTE se o cliente
    já tiver mencionado espontaneamente na conversa (ex: "meu carro é branco",
    "sou de SP", "sei que tem versão 0km"). Caso contrário, deixe em branco.

    Todos os dados técnicos (versão, carroceria, combustível, valor FIPE, etc.)
    vêm automaticamente da FIPE pela placa — não pergunte nada disso.

    EXIBIÇÃO OBRIGATÓRIA: copie e cole o resultado desta ferramenta palavra por palavra.
    NÃO adicione texto próprio.

    Após exibir: chame IMEDIATAMENTE `exibir_formulario_venda` com veiculo_descricao, placa,
    km e valor_proposta para mostrar o formulário visual de contato ao cliente.
    O formulário coletará nome e telefone automaticamente — NÃO aguarde o cliente digitar no chat.
    Se o cliente recusar a proposta → encerre sem chamar nenhuma ferramenta.
    """
    placa_limpa = normalizar_placa(placa)
    logger.info(f"[avaliar_veiculo] Chamada iniciada | placa={placa_limpa} | km={km} | uf={uf} | cor={cor} | existe_zero_km={existe_zero_km}")

    fipe = await _buscar_fipe(placa_limpa)

    if "error" in fipe:
        logger.warning(f"[avaliar_veiculo] Falha FIPE | placa={placa_limpa} | detalhe={fipe}")
        return (
            f"> Não foi possível consultar a FIPE para a placa **{placa_limpa}**. "
            "Verifique a placa informada e tente novamente."
        )

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
        return (
            f"> Não foi possível calcular a proposta para a placa **{placa_limpa}**. "
            f"Detalhe: {resultado.get('error', 'erro desconhecido')}. "
            "Tente novamente ou [inicie pelo site]"
            "(https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente)."
        )

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
        logger.info(f"[avaliar_veiculo] Valor zerado | placa={placa_limpa} — orientando avaliação presencial")
        return (
            f"## 🚗 {veiculo_descricao}\n\n"
            f"🔖 Placa: **{placa_limpa}** · 📏 **{km_fmt} km**\n\n"
            f"---\n\n"
            f"Não foi possível gerar uma proposta automática para este veículo. "
            f"A avaliação precisa ser feita presencialmente.\n\n"
            f"📲 **Falar com um consultor Saga** — informe seu **nome** e **telefone** "
            f"e um consultor **entra em contato com você via WhatsApp** para agendar a avaliação presencial.\n\n"
            f"Ou se preferir iniciar pelo site: "
            f"[avaliação online](https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente)"
        )

    preco_fmt = f"R$ {valor_proposta}"
    logger.info(f"[avaliar_veiculo] Proposta gerada | placa={placa_limpa} | valor={valor_proposta}")
    return (
        f"## 🚗 {veiculo_descricao}\n\n"
        f"🔖 Placa: **{placa_limpa}** · 📏 **{km_fmt} km**\n\n"
        f"---\n\n"
        f"## 💰 Proposta Saga Primeira Mão\n\n"
        f"### {preco_fmt}\n\n"
        f"---\n\n"
        f"📲 **Fechar com um consultor Saga** — informe seu **nome** e **telefone** "
        f"e um consultor **entra em contato com você via WhatsApp** para concluir a venda.\n\n"
        f"Ou se preferir iniciar pelo site: "
        f"[avaliação online](https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente)"
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=False, destructiveHint=False))
async def registrar_interesse_compra(
    nome_cliente: str,
    telefone_cliente: str,
    titulo_veiculo: Optional[str] = None,
    loja_unidade: Optional[str] = None,
    preco_formatado: Optional[str] = None,
    plate: Optional[str] = None,
    veiculo_id: Optional[str] = None,
    email_cliente: Optional[str] = None,
    observacao: Optional[str] = None,
):
    """
    CHAME ESTA FERRAMENTA IMEDIATAMENTE quando o cliente fornecer nome e telefone
    após ver os cards de veículos. NÃO mostre link nem resuma — chame direto.

    Um consultor da Saga entrará em contato com o cliente via WhatsApp.
    NÃO é o cliente que liga — é o consultor que entra em contato.

    Obrigatórios: nome_cliente e telefone_cliente.
    Opcionais (melhora o lead): titulo_veiculo, loja_unidade, preco_formatado, veiculo_id.

    Após chamar: exiba APENAS o campo `mensagem` retornado.
    Se registrado=false, exiba o link `fallback_url` como alternativa.
    """
    logger.warning(
        f"[registrar_interesse_compra] >>> TOOL CHAMADA | cliente='{nome_cliente}' | "
        f"tel='{telefone_cliente}' | veiculo='{titulo_veiculo}' | loja='{loja_unidade}' | "
        f"veiculo_id='{veiculo_id}'"
    )
    return await _criar_lead_compra(
        nome_cliente=nome_cliente,
        telefone_cliente=telefone_cliente,
        email_cliente=email_cliente or "",
        titulo_card=titulo_veiculo,
        veiculo_id=veiculo_id,
        preco_formatado=preco_formatado,
        loja_unidade=loja_unidade,
        plate=plate,
        observacao=observacao,
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=False, destructiveHint=False))
async def registrar_interesse_venda(
    nome_cliente: str,
    telefone_cliente: str,
    placa: Optional[str] = None,
    km: Optional[str] = None,
    veiculo_descricao: Optional[str] = None,
    valor_proposta: Optional[str] = None,
    email_cliente: Optional[str] = None,
    observacao: Optional[str] = None,
):
    """
    CHAME ESTA FERRAMENTA IMEDIATAMENTE quando o cliente fornecer nome e telefone
    após ver a proposta de avaliar_veiculo. NÃO mostre link nem resuma — chame direto.

    Um consultor da Saga entrará em contato com o cliente via WhatsApp.
    NÃO é o cliente que liga — é o consultor que entra em contato.

    Obrigatórios: nome_cliente e telefone_cliente.
    Opcionais (melhora o lead): placa, km, veiculo_descricao.

    Após chamar: exiba APENAS o campo `mensagem` retornado.
    Se registrado=false, exiba o link `fallback_url` como alternativa.
    """
    logger.warning(f"[registrar_interesse_venda] >>> TOOL CHAMADA | cliente='{nome_cliente}' | tel='{telefone_cliente}' | placa={placa} | km={km} | veiculo='{veiculo_descricao}'")
    return await _criar_lead_venda(
        nome_cliente=nome_cliente,
        telefone_cliente=telefone_cliente,
        email_cliente=email_cliente or "",
        placa=placa,
        km=km,
        veiculo_descricao=veiculo_descricao,
        valor_proposta=valor_proposta,
        observacao=observacao,
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False, destructiveHint=False))
async def diagnostico_registro(
    nome_teste: str = "Teste",
    telefone_teste: str = "62999999999",
):
    """
    FERRAMENTA DE DIAGNÓSTICO — chame apenas para depurar falhas de registro.
    Testa a criação de lead na API Mobiauto e retorna o erro exato.
    NÃO use em produção para clientes reais.
    """
    logger.warning(f"[diagnostico_registro] Iniciando teste de diagnóstico")
    resultado = await MobiautoProposalService.criar_lead(
        intention_type="BUY",
        nome=nome_teste,
        telefone=telefone_teste,
        email="",
        mensagem="[TESTE DIAGNÓSTICO — NÃO É LEAD REAL]",
    )
    logger.warning(f"[diagnostico_registro] Resultado: {resultado}")
    return {
        "success":   resultado.get("success"),
        "error":     resultado.get("error"),
        "detalhe":   resultado.get("detalhe"),
        "dealer_id": resultado.get("dealer_id"),
        "response":  resultado.get("response"),
    }


# Remove a chave "fastmcp" do _meta antes de enviar ao ChatGPT.
# FastMCP injeta "fastmcp": {"tags": []} em todo _meta via get_meta().
# Isso é ruído desnecessário no descriptor — o ChatGPT lê apenas as chaves que conhece.
_WIDGET_TOOLS = {"buscar_veiculos", "exibir_formulario_venda"}
_WIDGET_RESOURCES = {"ui://vehicle-offers"}

def _strip_fastmcp(meta: dict | None) -> dict | None:
    """Remove a chave 'fastmcp' injetada pelo FastMCP — não relevante para o ChatGPT."""
    if not meta:
        return meta
    clean = {k: v for k, v in meta.items() if k != "fastmcp"}
    return clean if clean else None

try:
    from fastmcp.tools.base import Tool as _FastMCPTool
    _orig_tool_to_mcp = _FastMCPTool.to_mcp_tool

    def _to_mcp_tool_clean(self, **overrides):
        mcp_tool = _orig_tool_to_mcp(self, **overrides)
        if self.name in _WIDGET_TOOLS:
            mcp_tool.meta = _strip_fastmcp(mcp_tool.meta)
        return mcp_tool

    _FastMCPTool.to_mcp_tool = _to_mcp_tool_clean
    logger.info(f"[meta-patch] Tool.to_mcp_tool patcheado — 'fastmcp' removido de: {_WIDGET_TOOLS}")
except Exception as _e:
    logger.warning(f"[meta-patch] Falha ao patchear Tool.to_mcp_tool: {_e}")

try:
    from fastmcp.resources.base import Resource as _FastMCPResource
    _orig_res_to_mcp = _FastMCPResource.to_mcp_resource

    def _to_mcp_resource_clean(self, **overrides):
        mcp_res = _orig_res_to_mcp(self, **overrides)
        if str(getattr(self, "uri", "")) in _WIDGET_RESOURCES:
            mcp_res.meta = _strip_fastmcp(mcp_res.meta)
        return mcp_res

    _FastMCPResource.to_mcp_resource = _to_mcp_resource_clean
    logger.info(f"[meta-patch] Resource.to_mcp_resource patcheado — 'fastmcp' removido de: {_WIDGET_RESOURCES}")
except Exception as _e:
    logger.warning(f"[meta-patch] Falha ao patchear Resource.to_mcp_resource: {_e}")


if __name__ == "__main__":
    os.chdir(_HERE)

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "sse":
        port = int(os.getenv("PORT", 8000))
        logger.info(f"Iniciando MCP em modo SSE na porta {port}")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
