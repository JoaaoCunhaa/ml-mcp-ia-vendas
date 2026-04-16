"""
Teste completo de todas as tools e funções internas do MCP PrimeiraMao.

Cobre:
  T01 - listar_lojas
  T02 - estoque_total (retorna string com cards markdown)
  T03 - registrar_interesse_compra (tool explícita de lead de compra)
  T04 - buscar_veiculo (Fase 2 AND - retorna string)
  T05 - buscar_veiculo (Fase 4 sem resultado - retorna string)
  T06 - buscar_veiculo (sem consulta - fallback para estoque_total)
  T07 - registrar_interesse_compra (segunda chamada - via buscar_veiculo flow)
  T08 - avaliar_veiculo (so proposta, retorna string)
  T09 - registrar_interesse_venda (tool explícita de lead de venda)
  T10 - _criar_lead_compra (funcao interna direta)
  T11 - _criar_lead_venda (funcao interna direta)
  T12 - _disparar_webhook compra (funcao interna direta)
  T13 - _disparar_webhook venda (funcao interna direta)

Uso:
  python test_tools.py
"""

import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Importa as funcoes do MCP (o bloco __main__ nao sera executado)
from main import (
    listar_lojas,
    estoque_total,
    buscar_veiculo,
    avaliar_veiculo,
    registrar_interesse_compra,
    registrar_interesse_venda,
    _criar_lead_compra,
    _criar_lead_venda,
    _disparar_webhook,
    _WH_COMPRA,
    _WH_VENDA,
)

SEP  = "=" * 60
SEP2 = "-" * 60

PASSOU = "[ OK ]"
FALHOU = "[FALHA]"

resultados = []


def checar(nome: str, condicao: bool, detalhe: str = ""):
    status = PASSOU if condicao else FALHOU
    resultados.append((nome, condicao))
    print(f"  {status}  {nome}")
    if detalhe:
        print(f"         {detalhe}")
    if not condicao:
        print(f"         *** FALHOU — verifique acima ***")


# ─────────────────────────────────────────────────────────────
# T01 — listar_lojas
# ─────────────────────────────────────────────────────────────

async def test_listar_lojas():
    print(f"\n{SEP}")
    print("T01 — listar_lojas")
    print(SEP)
    r = await listar_lojas()
    print(f"  total    : {r.get('total')}")
    print(f"  fonte    : {r.get('fonte_dados')}")
    print(f"  markdown : {r.get('lojas_markdown', '')[:120]}...")

    checar("retorna total > 0",             r.get("total", 0) > 0,      f"total={r.get('total')}")
    checar("lojas_markdown nao vazio",       bool(r.get("lojas_markdown")))
    checar("campo lojas eh lista",           isinstance(r.get("lojas"), list))
    checar("fallback quando vazio ausente",  "Nenhuma loja" not in r.get("lojas_markdown", "") or r.get("total", 0) == 0)
    return r


# ─────────────────────────────────────────────────────────────
# T02 — estoque_total (retorna string com cards markdown)
# ─────────────────────────────────────────────────────────────

async def test_estoque_total_navegacao():
    print(f"\n{SEP}")
    print("T02 — estoque_total (busca por cidade 'Goiania')")
    print(SEP)
    r = await estoque_total(cidade="Goiania")
    print(f"  tipo     : {type(r).__name__}")
    print(f"  tamanho  : {len(r) if isinstance(r, str) else 'N/A'} chars")
    print(f"  preview  : {str(r)[:120]}...")

    checar("retorna string",             isinstance(r, str),  f"tipo={type(r).__name__}")
    checar("string nao vazia",           bool(r and r.strip()))
    checar("contem imagem markdown",     "![" in r or ">" in r,  "deve ter imagem ou mensagem de aviso")
    return r


# ─────────────────────────────────────────────────────────────
# T03 — registrar_interesse_compra (tool explicita)
# ─────────────────────────────────────────────────────────────

async def test_registrar_interesse_compra():
    print(f"\n{SEP}")
    print("T03 — registrar_interesse_compra (tool explicita)")
    print(SEP)
    r = await registrar_interesse_compra(
        nome_cliente="Teste Compra T03",
        telefone_cliente="62999990003",
        email_cliente="t03@sagadatadriven.com.br",
        titulo_veiculo="Honda Civic 2021",
        loja_unidade="Primeira Mão GO BURITI",
        plate="TST0003",
        preco_formatado="R$ 89.900,00",
        observacao="Teste automatico T03 — registrar_interesse_compra",
    )
    print(f"  registrado : {r.get('registrado')}")
    print(f"  dealer_id  : {r.get('dealer_id')}")
    print(f"  mensagem   : {r.get('mensagem')}")
    print(f"  fallback   : {r.get('fallback_url')}")

    checar("campo registrado presente",  "registrado" in r)
    checar("lead registrado com sucesso", r.get("registrado") is True, f"mensagem={r.get('mensagem')}")
    checar("dealer_id preenchido",        bool(r.get("dealer_id")))
    checar("fallback_url presente",       bool(r.get("fallback_url")))
    return r


# ─────────────────────────────────────────────────────────────
# T04 — buscar_veiculo (busca normal Fase 2 AND - retorna string)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_normal():
    print(f"\n{SEP}")
    print("T04 — buscar_veiculo (busca 'honda')")
    print(SEP)
    r = await buscar_veiculo(consulta="honda")
    print(f"  tipo     : {type(r).__name__}")
    print(f"  tamanho  : {len(r) if isinstance(r, str) else 'N/A'} chars")
    print(f"  preview  : {str(r)[:120]}...")

    checar("retorna string",          isinstance(r, str),  f"tipo={type(r).__name__}")
    checar("string nao vazia",        bool(r and r.strip()))
    checar("contem imagem markdown",  "![" in r or ">" in r)
    return r


# ─────────────────────────────────────────────────────────────
# T05 — buscar_veiculo (Fase 4 — sem resultado)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_sem_resultado():
    print(f"\n{SEP}")
    print("T05 — buscar_veiculo (consulta improvavel — Fase 4)")
    print(SEP)
    r = await buscar_veiculo(consulta="marcaxyzimpossivelzz")
    print(f"  tipo    : {type(r).__name__}")
    print(f"  preview : {str(r)[:200]}...")

    checar("retorna string",                  isinstance(r, str),  f"tipo={type(r).__name__}")
    checar("string nao vazia",                bool(r and r.strip()))
    checar("contem mensagem de nao encontrado ou cards", "Não encontramos" in r or "![" in r)
    return r


# ─────────────────────────────────────────────────────────────
# T06 — buscar_veiculo (sem consulta — fallback para estoque_total)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_sem_consulta():
    print(f"\n{SEP}")
    print("T06 — buscar_veiculo (sem consulta — delega para estoque_total)")
    print(SEP)
    r = await buscar_veiculo(consulta=None)
    print(f"  tipo    : {type(r).__name__}")
    print(f"  preview : {str(r)[:80]}...")

    checar("retorna string",  isinstance(r, str),  f"tipo={type(r).__name__}")
    checar("string nao vazia", bool(r and r.strip()))
    return r


# ─────────────────────────────────────────────────────────────
# T07 — registrar_interesse_compra (segunda chamada — validacao de flow)
# ─────────────────────────────────────────────────────────────

async def test_registrar_interesse_compra_2():
    print(f"\n{SEP}")
    print("T07 — registrar_interesse_compra (segunda chamada)")
    print(SEP)
    r = await registrar_interesse_compra(
        nome_cliente="Teste Compra T07",
        telefone_cliente="62999990007",
        email_cliente="t07@sagadatadriven.com.br",
        titulo_veiculo="Toyota Corolla 2022",
        loja_unidade="Primeira Mão GO APARECIDA",
        plate="TST0007",
        preco_formatado="R$ 115.000,00",
        observacao="Teste automatico T07 — registrar_interesse_compra",
    )
    print(f"  registrado : {r.get('registrado')}")
    print(f"  dealer_id  : {r.get('dealer_id')}")
    print(f"  mensagem   : {r.get('mensagem')}")
    print(f"  fallback   : {r.get('fallback_url')}")

    checar("campo registrado presente",   "registrado" in r)
    checar("lead registrado com sucesso",  r.get("registrado") is True, f"mensagem={r.get('mensagem')}")
    checar("dealer_id preenchido",         bool(r.get("dealer_id")))
    checar("fallback_url presente",        bool(r.get("fallback_url")))
    return r


# ─────────────────────────────────────────────────────────────
# T08 — avaliar_veiculo (retorna string com proposta)
# ─────────────────────────────────────────────────────────────

async def test_avaliar_veiculo_proposta():
    print(f"\n{SEP}")
    print("T08 — avaliar_veiculo (proposta, sem lead)")
    print("  placa=RUR9J56 | km=38000")
    print(SEP)
    r = await avaliar_veiculo(placa="RUR9J56", km="38000")
    print(f"  tipo     : {type(r).__name__}")
    print(f"  tamanho  : {len(r) if isinstance(r, str) else 'N/A'} chars")
    print(f"  preview  : {str(r)[:120]}...")

    checar("retorna string",          isinstance(r, str),  f"tipo={type(r).__name__}")
    checar("string nao vazia",        bool(r and r.strip()))
    checar("contem placa no markdown", "RUR9J56" in r or ">" in r)
    checar("sem erro de FIPE",        "Não foi possível consultar a FIPE" not in r, f"detalhe={str(r)[:100]}")
    return r


# ─────────────────────────────────────────────────────────────
# T09 — registrar_interesse_venda (tool explicita)
# ─────────────────────────────────────────────────────────────

async def test_registrar_interesse_venda():
    print(f"\n{SEP}")
    print("T09 — registrar_interesse_venda (tool explicita)")
    print(SEP)
    r = await registrar_interesse_venda(
        nome_cliente="Teste Venda T09",
        telefone_cliente="62999990009",
        email_cliente="t09@sagadatadriven.com.br",
        placa="RUR9J56",
        km="38000",
        veiculo_descricao="Honda Civic 2021",
        observacao="Teste automatico T09 — registrar_interesse_venda",
    )
    print(f"  registrado : {r.get('registrado')}")
    print(f"  dealer_id  : {r.get('dealer_id')}")
    print(f"  mensagem   : {r.get('mensagem')}")
    print(f"  fallback   : {r.get('fallback_url')}")

    checar("campo registrado presente",   "registrado" in r)
    checar("lead registrado com sucesso",  r.get("registrado") is True, f"mensagem={r.get('mensagem')}")
    checar("dealer_id preenchido",         bool(r.get("dealer_id")))
    checar("fallback_url presente",        bool(r.get("fallback_url")))
    return r


# ─────────────────────────────────────────────────────────────
# T10 — _criar_lead_compra (funcao interna direta)
# ─────────────────────────────────────────────────────────────

async def test_criar_lead_compra_direto():
    print(f"\n{SEP}")
    print("T10 — _criar_lead_compra (funcao interna direta)")
    print(SEP)
    r = await _criar_lead_compra(
        nome_cliente="Teste Direto T10",
        telefone_cliente="62999990010",
        email_cliente="t10@sagadatadriven.com.br",
        titulo_card="Hyundai HB20 2020",
        loja_unidade="SN GO BURITI",
        plate="TST0010",
        modelYear="2020",
        km="45000",
        colorName="Branco",
        preco_formatado="R$ 65.000,00",
        observacao="Teste automatico T10 — _criar_lead_compra direto",
    )
    print(f"  registrado : {r.get('registrado')}")
    print(f"  dealer_id  : {r.get('dealer_id')}")
    print(f"  mensagem   : {r.get('mensagem')}")
    print(f"  fallback   : {r.get('fallback_url')}")

    checar("registrado True",        r.get("registrado") is True, f"mensagem={r.get('mensagem')}")
    checar("dealer_id preenchido",   bool(r.get("dealer_id")))
    checar("fallback_url presente",  bool(r.get("fallback_url")))
    return r


# ─────────────────────────────────────────────────────────────
# T11 — _criar_lead_venda (funcao interna direta)
# ─────────────────────────────────────────────────────────────

async def test_criar_lead_venda_direto():
    print(f"\n{SEP}")
    print("T11 — _criar_lead_venda (funcao interna direta)")
    print(SEP)
    r = await _criar_lead_venda(
        nome_cliente="Teste Direto T11",
        telefone_cliente="62999990011",
        email_cliente="t11@sagadatadriven.com.br",
        placa="TST1T11",
        km="60000",
        veiculo_descricao="Honda Fit EX 2018",
        valor_proposta="28500.00",
        preco_formatado="R$ 28.500,00",
        marca="Honda",
        modelo="Fit",
        ano_modelo="2018",
        cor="Prata",
        uf="GO",
        observacao="Teste automatico T11 — _criar_lead_venda direto",
    )
    print(f"  registrado : {r.get('registrado')}")
    print(f"  dealer_id  : {r.get('dealer_id')}")
    print(f"  mensagem   : {r.get('mensagem')}")
    print(f"  fallback   : {r.get('fallback_url')}")

    checar("registrado True",        r.get("registrado") is True, f"mensagem={r.get('mensagem')}")
    checar("dealer_id preenchido",   bool(r.get("dealer_id")))
    checar("fallback_url presente",  bool(r.get("fallback_url")))
    return r


# ─────────────────────────────────────────────────────────────
# T12/T13 — _disparar_webhook (funcao interna direta)
# ─────────────────────────────────────────────────────────────

async def test_disparar_webhook():
    print(f"\n{SEP}")
    print("T12 — _disparar_webhook compra")
    print(SEP)
    ok_c = await _disparar_webhook(_WH_COMPRA, {
        "lead_id":         "TESTE-T12",
        "nome_cliente":    "Teste Webhook T12",
        "telefone_cliente": "62999990012",
        "titulo_card":     "Honda Civic 2021",
        "loja_unidade":    "SN GO BURITI",
        "dealer_id":       "18405",
        "observacao":      "Teste automatico T12",
    }, "cliente_quer_comprar")
    print(f"  webhook compra : {'OK' if ok_c else 'FALHOU'}")
    checar("webhook compra enviado", ok_c)

    print(f"\n{SEP}")
    print("T13 — _disparar_webhook venda")
    print(SEP)
    ok_v = await _disparar_webhook(_WH_VENDA, {
        "lead_id":           "TESTE-T13",
        "nome_cliente":      "Teste Webhook T13",
        "telefone_cliente":  "62999990013",
        "placa":             "TST1T13",
        "veiculo_descricao": "Honda Fit 2018",
        "dealer_id":         "18415",
        "observacao":        "Teste automatico T13",
    }, "cliente_quer_vender")
    print(f"  webhook venda  : {'OK' if ok_v else 'FALHOU'}")
    checar("webhook venda enviado", ok_v)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

async def main():
    print(f"\n{SEP}")
    print("  SUITE DE TESTES — MCP PrimeiraMao")
    print(f"{SEP}")

    await test_listar_lojas()
    await test_estoque_total_navegacao()
    await test_registrar_interesse_compra()
    await test_buscar_veiculo_normal()
    await test_buscar_veiculo_sem_resultado()
    await test_buscar_veiculo_sem_consulta()
    await test_registrar_interesse_compra_2()
    await test_avaliar_veiculo_proposta()
    await test_registrar_interesse_venda()
    await test_criar_lead_compra_direto()
    await test_criar_lead_venda_direto()
    await test_disparar_webhook()

    # ── Resumo ────────────────────────────────────────────────
    ok  = sum(1 for _, v in resultados if v)
    nok = sum(1 for _, v in resultados if not v)

    print(f"\n{SEP}")
    print(f"  RESUMO: {ok} OK  |  {nok} FALHOU  |  {len(resultados)} total")
    print(SEP)
    if nok:
        print("\n  Testes que falharam:")
        for nome, v in resultados:
            if not v:
                print(f"    - {nome}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
