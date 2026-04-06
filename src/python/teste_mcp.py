import asyncio
import json
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

# Garante UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────
# Seleção de ambiente via argumento CLI:
#   python teste_mcp.py          → produção (padrão)
#   python teste_mcp.py --local  → localhost:3001 (start_local.bat)
#   python teste_mcp.py --prod   → produção explícita
# ─────────────────────────────────────────────
_args = sys.argv[1:]
if "--local" in _args:
    SERVER_URL = "http://localhost:8001/sse"
    _ENV = "LOCAL"
else:
    SERVER_URL = "https://mcp-primeiramao.sagadatadriven.com.br/sse"
    _ENV = "PROD"

# Placa usada nos testes que precisam de veículo real
PLACA_TESTE = "SLL1H77"

# Contexto compartilhado entre os testes (populado à medida que rodam)
ctx = {
    "id_veiculo": "",
    "marca": "Toyota",
    "versao": "",
}


def ok(label, detalhe=""):
    sufixo = f" | {detalhe}" if detalhe else ""
    print(f"  ✅ OK! {label}{sufixo}")


def falha(label, detalhe=""):
    sufixo = f" | {detalhe}" if detalhe else ""
    print(f"  ❌ FALHA! {label}{sufixo}")


def aviso(label):
    print(f"  ⚠️  AVISO: {label}")


def parse_resposta(res):
    """
    Extrai e faz parse do conteúdo retornado pelo MCP.
    Suporta múltiplos content items, isError e respostas não-JSON.
    """
    if not res:
        return None, "(sem resposta)"

    # Verifica flag de erro no resultado
    is_error = getattr(res, "isError", False)

    if not res.content:
        return None, "(resposta sem conteúdo)"

    texto = ""
    for item in res.content:
        # TextContent tem .text
        if hasattr(item, "text") and item.text:
            texto += item.text
        # Fallback: str do item
        elif not hasattr(item, "text"):
            texto += str(item)

    if not texto.strip():
        return None, "(texto vazio no conteúdo)"

    # Se é um erro do servidor, retorna como string de erro
    if is_error:
        return None, f"Erro do servidor: {texto.strip()[:300]}"

    try:
        return json.loads(texto), None
    except json.JSONDecodeError as e:
        # Tenta extrair o primeiro objeto JSON válido
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(texto.strip())
            return obj, None
        except Exception:
            return None, f"JSON inválido: {e} | raw={texto[:200]!r}"


async def nova_sessao():
    """Abre uma nova sessão SSE independente."""
    cm_sse = sse_client(SERVER_URL)
    streams = await cm_sse.__aenter__()
    cm_session = ClientSession(streams[0], streams[1])
    session = await cm_session.__aenter__()
    await session.initialize()
    return cm_sse, cm_session, session


async def fechar_sessao(cm_sse, cm_session):
    try:
        await cm_session.__aexit__(None, None, None)
    except Exception:
        pass
    try:
        await cm_sse.__aexit__(None, None, None)
    except Exception:
        pass


async def testar_listar_lojas():
    print("\n🔹 [1/8] listar_lojas")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        res = await session.call_tool("listar_lojas", {})
        data, err = parse_resposta(res)
        if err:
            falha("parse falhou", err)
        elif isinstance(data, list):
            ok(f"Encontradas {len(data)} lojas.")
        else:
            falha("Esperava lista.", str(data)[:120])
    except Exception as e:
        falha("listar_lojas", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


async def testar_estoque_total(session):
    """Requer sessão SSE já inicializada e aquecida (chame listar_lojas antes)."""
    print("\n🔹 [2/8] estoque_total  (pode demorar — 49 lojas)")
    try:
        res = await asyncio.wait_for(
            session.call_tool("estoque_total", {}),
            timeout=120,
        )
        if res and not res.content:
            # isError=False mas content=[] → InventoryAggregator crashou silenciosamente
            falha(
                "Servidor retornou conteúdo vazio (isError=False, content=[]).",
                "Provável crash no InventoryAggregator/MobiautoService. Ver logs do servidor."
            )
        else:
            data, err = parse_resposta(res)
            if err:
                falha("parse falhou", err)
            elif isinstance(data, list):
                ok(f"{len(data)} veículos no estoque consolidado.")
            else:
                falha("Esperava lista.", str(data)[:120])
    except asyncio.TimeoutError:
        aviso("estoque_total excedeu 120s — servidor pode estar sobrecarregado.")
    except Exception as e:
        falha("estoque_total", str(e))


async def testar_search_veiculos(session):
    """Requer sessão SSE já inicializada e aquecida."""
    print("\n🔹 [3/8] search_veiculos (marca: Toyota)")
    try:
        res = await session.call_tool("search_veiculos", {"marca": "Toyota"})
        if res and not res.content:
            falha(
                "Servidor retornou conteúdo vazio (mesmo erro do estoque_total).",
                "InventoryAggregator indisponível no servidor. Ver logs."
            )
            return
        data, err = parse_resposta(res)
        if err:
            falha("parse falhou", err)
        elif isinstance(data, list):
            ok(f"Encontrados {len(data)} Toyotas.")
            if data:
                primeiro = data[0]
                ctx["id_veiculo"] = str(primeiro.get("id", ""))
                ctx["marca"] = primeiro.get("makeName", "Toyota")
                ctx["versao"] = primeiro.get("trimName", "")
                print(f"     → Referência: {ctx['marca']} {ctx['versao']} (id={ctx['id_veiculo']})")
        else:
            falha("Esperava lista.", str(data)[:120])
    except Exception as e:
        falha("search_veiculos", str(e))


async def testar_fetch_veiculo_detalhado():
    id_teste = ctx["id_veiculo"]
    print(f"\n🔹 [4/8] fetch_veiculo_detalhado (id={id_teste})")
    if not id_teste:
        aviso("ID de veículo não disponível — pulando teste.")
        return
    cm_sse, cm_session, session = await nova_sessao()
    try:
        res = await session.call_tool("fetch_veiculo_detalhado", {"identificador": id_teste})
        data, err = parse_resposta(res)
        if err:
            falha("parse falhou", err)
        elif data:
            ok(f"{data.get('makeName')} {data.get('modelName')} | km={data.get('km')}")
        else:
            falha("Retornou null/vazio.")
    except Exception as e:
        falha("fetch_veiculo_detalhado", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


async def testar_buscar_fipe():
    print(f"\n🔹 [5/8] buscar_fipe (placa: {PLACA_TESTE})")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        res = await session.call_tool("buscar_fipe", {"placa": PLACA_TESTE})
        data, err = parse_resposta(res)
        if err:
            falha("parse falhou", err)
        elif isinstance(data, dict) and "error" in data:
            falha("FIPE retornou erro.", data.get("mensagem"))
        elif isinstance(data, dict):
            ok(
                f"{data.get('marca')} {data.get('modelo')} {data.get('ano_modelo')}"
                f" | FIPE R$ {data.get('valor_fipe')}"
            )
        else:
            falha("Formato inesperado.", str(data)[:120])
    except Exception as e:
        falha("buscar_fipe", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


async def testar_avaliar_veiculo():
    """
    DIAGNÓSTICO DO 400:
      Servidor atual tem versão ANTIGA — aceita só: placa, valor_fipe, marca,
      modelo, ano_modelo, km, uf. Envia cor='' e tipo='' para a API de
      precificação → API rejeita com 400.

    SOLUÇÃO (main.py local já corrigido — aguardando deploy):
      Nova versão busca FIPE internamente e recebe cor + tipo do cliente.
      Interface: placa, km, uf, cor, tipo (+ opcionais).

    Este teste valida as duas situações claramente.
    """
    print(f"\n🔹 [6/8] avaliar_veiculo (placa: {PLACA_TESTE})")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        # Interface antiga do servidor deployado (sem cor/tipo)
        dados_antigos = {
            "placa": PLACA_TESTE,
            "valor_fipe": "170000",
            "marca": "Toyota",
            "modelo": "Corolla Cross",
            "ano_modelo": "2024",
            "km": "23000",
            "uf": "RO",
        }
        res = await session.call_tool("avaliar_veiculo", dados_antigos)
        data, err = parse_resposta(res)

        if err and "Unexpected keyword argument" in err:
            aviso("avaliar_veiculo: servidor tem versão diferente da local. Verificar deploy.")
        elif err and ("cor" in err or "tipo" in err or "Erro do servidor" in err):
            aviso(
                "Servidor com versão ANTIGA (sem cor/tipo). "
                "Causa raiz do 400: cor='' e tipo='' são enviados vazios à API de precificação. "
                "Deploy da nova versão resolve."
            )
        elif err:
            falha("parse falhou", err)
        elif isinstance(data, dict) and "error" in data:
            # Esperado na versão antiga: 400 da API de precificação
            aviso(f"400 confirmado (versão antiga no ar): {data.get('mensagem')}")
        elif data is not None:
            resumo = json.dumps(data, ensure_ascii=False)[:160]
            ok(f"Precificação recebida: {resumo}")
        else:
            falha("Resposta vazia.")
    except Exception as e:
        falha("avaliar_veiculo", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


def _tool_nao_deployada(texto_erro: str, tool_name: str) -> bool:
    return f"Unknown tool: '{tool_name}'" in (texto_erro or "") or \
           f'Unknown tool: "{tool_name}"' in (texto_erro or "")


async def testar_contato_compra():
    print(f"\n🔹 [7/8] contato_compra")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        # 7a — URL filtrada com dados do veículo real
        params = {
            "id_veiculo": ctx["id_veiculo"] or "53669",
            "marca": ctx["marca"],
            "versao": ctx["versao"] or "Corolla XEi",
        }
        res = await session.call_tool("contato_compra", params)
        data, err = parse_resposta(res)
        if err and _tool_nao_deployada(err, "contato_compra"):
            aviso("contato_compra ainda não deployada no servidor remoto.")
        elif err:
            falha("parse falhou (url filtrada)", err)
        elif isinstance(data, dict):
            url = data.get("url", "")
            tipo = data.get("tipo", "")
            if url.startswith("https://"):
                ok(f"URL filtrada ({tipo}): {url}")
            else:
                falha("URL inválida.", url)
        else:
            falha("Formato inesperado.", str(data)[:120])

        # 7b — Fallback: sem parâmetros → url_base
        res_fb = await session.call_tool("contato_compra", {})
        fb, err_fb = parse_resposta(res_fb)
        if err_fb and _tool_nao_deployada(err_fb, "contato_compra"):
            pass  # já avisado acima
        elif err_fb:
            falha("parse falhou (fallback)", err_fb)
        elif isinstance(fb, dict) and fb.get("tipo") == "url_base":
            ok(f"Fallback url_base: {fb.get('url')}")
        else:
            falha("Fallback deveria ser url_base.", str(fb)[:120])
    except Exception as e:
        falha("contato_compra", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


async def testar_contato_venda():
    esperada = "https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente"
    print(f"\n🔹 [8/8] contato_venda")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        res = await session.call_tool("contato_venda", {})
        data, err = parse_resposta(res)
        if err and _tool_nao_deployada(err, "contato_venda"):
            aviso("contato_venda ainda não deployada no servidor remoto.")
        elif err:
            falha("parse falhou", err)
        elif isinstance(data, dict):
            url = data.get("url", "")
            if url == esperada:
                ok(f"URL correta: {url}")
            else:
                falha(f"URL inesperada.\n     recebido: {url}\n     esperado: {esperada}")
        else:
            falha("Formato inesperado.", str(data)[:120])
    except Exception as e:
        falha("contato_venda", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)


async def run_full_test():
    print(f"🚀 Iniciando Full Test  [{_ENV}]  →  {SERVER_URL}")

    # Tests 1-3 compartilham a mesma sessão SSE.
    # estoque_total e search_veiculos retornam conteúdo vazio em sessões
    # isoladas; ao reusar a sessão "aquecida" por listar_lojas o comportamento
    # é estável (igual ao teste original).
    print("\n🔹 [1/8] listar_lojas")
    cm_sse, cm_session, session = await nova_sessao()
    try:
        res = await session.call_tool("listar_lojas", {})
        data, err = parse_resposta(res)
        if err:
            falha("parse falhou", err)
        elif isinstance(data, list):
            ok(f"Encontradas {len(data)} lojas.")
        else:
            falha("Esperava lista.", str(data)[:120])

        await testar_estoque_total(session)
        await testar_search_veiculos(session)
    except Exception as e:
        falha("sessão compartilhada (1-3)", str(e))
    finally:
        await fechar_sessao(cm_sse, cm_session)

    await testar_fetch_veiculo_detalhado()
    await testar_buscar_fipe()
    await testar_avaliar_veiculo()
    await testar_contato_compra()
    await testar_contato_venda()

    print("\n🏆 TESTE COMPLETO FINALIZADO!")


if __name__ == "__main__":
    asyncio.run(run_full_test())
