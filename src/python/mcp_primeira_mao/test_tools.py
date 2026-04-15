"""
Teste completo de todas as tools e funções internas do MCP PrimeiraMao.

Cobre:
  T01 - listar_lojas
  T02 - estoque_total (navegacao)
  T03 - estoque_total (lead automatico de compra)
  T04 - buscar_veiculo (Fase 2 AND)
  T05 - buscar_veiculo (Fase 4 sem resultado - sugestoes)
  T06 - buscar_veiculo (sem consulta - fallback para estoque)
  T07 - buscar_veiculo (lead automatico de compra)
  T08 - avaliar_veiculo (so proposta, sem lead)
  T09 - avaliar_veiculo (lead automatico de venda - proposta valida)
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
# T02 — estoque_total (apenas navegacao, sem lead)
# ─────────────────────────────────────────────────────────────

async def test_estoque_total_navegacao():
    print(f"\n{SEP}")
    print("T02 — estoque_total (busca por cidade 'Goiania')")
    print(SEP)
    r = await estoque_total(cidade="Goiania")
    meta = r.get("_meta", {})
    print(f"  veiculos : {meta.get('total_veiculos')}")
    print(f"  cidade   : {meta.get('cidade')}")
    print(f"  lojas    : {meta.get('lojas_buscadas')}")
    print(f"  markdown : {r.get('cards_markdown', '')[:120]}...")

    checar("cards_markdown presente",  bool(r.get("cards_markdown")))
    checar("_meta presente",           bool(meta))
    checar("nao tem campo 'lead'",     "lead" not in r,  "lead nao deve aparecer sem nome_cliente")
    return r


# ─────────────────────────────────────────────────────────────
# T03 — estoque_total com lead automatico de compra
# ─────────────────────────────────────────────────────────────

async def test_estoque_total_lead_compra():
    print(f"\n{SEP}")
    print("T03 — estoque_total (lead automatico de compra)")
    print(SEP)
    r = await estoque_total(
        nome_cliente="Teste Compra T03",
        telefone_cliente="62999990003",
        email_cliente="t03@sagadatadriven.com.br",
        titulo_card="Honda Civic 2021",
        loja_unidade="SN GO BURITI",
        plate="TST0003",
        modelYear="2021",
        km="32000",
        colorName="Preto",
        preco_formatado="R$ 89.900,00",
        observacao="Teste automatico T03 — lead compra via estoque_total",
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
# T04 — buscar_veiculo (busca normal Fase 2 AND)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_normal():
    print(f"\n{SEP}")
    print("T04 — buscar_veiculo (busca 'honda')")
    print(SEP)
    r = await buscar_veiculo(consulta="honda")
    print(f"  total    : {r.get('total')}")
    print(f"  markdown : {r.get('cards_markdown', '')[:120]}...")

    checar("cards_markdown presente",  bool(r.get("cards_markdown")))
    checar("campo total presente",     "total" in r)
    checar("nao tem campo 'lead'",     "lead" not in r)
    return r


# ─────────────────────────────────────────────────────────────
# T05 — buscar_veiculo (Fase 4 — sem resultado)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_sem_resultado():
    print(f"\n{SEP}")
    print("T05 — buscar_veiculo (consulta improvavel — Fase 4)")
    print(SEP)
    r = await buscar_veiculo(consulta="marcaxyzimpossivelzz")
    print(f"  total    : {r.get('total')}")
    print(f"  markdown : {r.get('cards_markdown', '')[:200]}...")

    checar("cards_markdown presente",        bool(r.get("cards_markdown")))
    checar("mensagem de fallback no markdown", "Não encontramos" in r.get("cards_markdown", "") or r.get("total", 0) > 0)
    return r


# ─────────────────────────────────────────────────────────────
# T06 — buscar_veiculo (sem consulta — fallback para estoque_total)
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_sem_consulta():
    print(f"\n{SEP}")
    print("T06 — buscar_veiculo (sem consulta — delega para estoque_total)")
    print(SEP)
    r = await buscar_veiculo(consulta=None)
    print(f"  chaves retornadas : {list(r.keys())}")
    print(f"  markdown          : {r.get('cards_markdown', '')[:80]}...")

    checar("cards_markdown presente",  bool(r.get("cards_markdown")))
    return r


# ─────────────────────────────────────────────────────────────
# T07 — buscar_veiculo com lead automatico de compra
# ─────────────────────────────────────────────────────────────

async def test_buscar_veiculo_lead_compra():
    print(f"\n{SEP}")
    print("T07 — buscar_veiculo (lead automatico de compra)")
    print(SEP)
    r = await buscar_veiculo(
        consulta=None,
        nome_cliente="Teste Compra T07",
        telefone_cliente="62999990007",
        email_cliente="t07@sagadatadriven.com.br",
        titulo_card="Toyota Corolla 2022",
        loja_unidade="SN GO APARECIDA",
        plate="TST0007",
        modelYear="2022",
        km="18000",
        colorName="Prata",
        preco_formatado="R$ 115.000,00",
        observacao="Teste automatico T07 — lead compra via buscar_veiculo",
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
# T08 — avaliar_veiculo (apenas proposta, sem lead)
# ─────────────────────────────────────────────────────────────

async def test_avaliar_veiculo_proposta():
    print(f"\n{SEP}")
    print("T08 — avaliar_veiculo (proposta, sem lead)")
    print("  placa=RUR9J56 | km=38000")
    print(SEP)
    r = await avaliar_veiculo(placa="RUR9J56", km="38000")
    print(f"  proposta_disponivel : {r.get('proposta_disponivel')}")
    print(f"  veiculo_descricao   : {r.get('veiculo_descricao')}")
    print(f"  preco_formatado     : {r.get('preco_formatado', 'N/A (valor zero)')}")
    print(f"  url_venda           : {r.get('url_venda')}")
    print(f"  markdown (100c)     : {r.get('proposta_markdown', '')[:100]}...")

    checar("proposta_markdown presente",  bool(r.get("proposta_markdown")))
    checar("url_venda presente",          bool(r.get("url_venda")))
    checar("nao tem campo 'lead'",        "lead" not in r,  "lead nao deve existir sem nome_cliente")
    checar("sem erro de FIPE",            "error" not in r, f"error={r.get('error')}")
    return r


# ─────────────────────────────────────────────────────────────
# T09 — avaliar_veiculo com lead automatico de venda
# ─────────────────────────────────────────────────────────────

async def test_avaliar_veiculo_lead_venda():
    print(f"\n{SEP}")
    print("T09 — avaliar_veiculo (lead automatico de venda)")
    print("  placa=RUR9J56 | km=38000 | cliente=Teste Venda T09")
    print(SEP)
    r = await avaliar_veiculo(
        placa="RUR9J56",
        km="38000",
        uf="GO",
        nome_cliente="Teste Venda T09",
        telefone_cliente="62999990009",
        email_cliente="t09@sagadatadriven.com.br",
        observacao="Teste automatico T09 — lead venda via avaliar_veiculo",
    )
    lead = r.get("lead", {})
    print(f"  proposta_disponivel : {r.get('proposta_disponivel')}")
    print(f"  lead.registrado     : {lead.get('registrado')}")
    print(f"  lead.dealer_id      : {lead.get('dealer_id')}")
    print(f"  lead.mensagem       : {lead.get('mensagem')}")
    print(f"  lead.fallback_url   : {lead.get('fallback_url')}")

    checar("proposta_markdown presente",   bool(r.get("proposta_markdown")))
    checar("campo lead presente",          "lead" in r,         "lead deve existir com nome_cliente")
    checar("lead.registrado com sucesso",  lead.get("registrado") is True, f"mensagem={lead.get('mensagem')}")
    checar("lead.dealer_id preenchido",    bool(lead.get("dealer_id")))
    checar("lead.fallback_url presente",   bool(lead.get("fallback_url")))
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
    await test_estoque_total_lead_compra()
    await test_buscar_veiculo_normal()
    await test_buscar_veiculo_sem_resultado()
    await test_buscar_veiculo_sem_consulta()
    await test_buscar_veiculo_lead_compra()
    await test_avaliar_veiculo_proposta()
    await test_avaliar_veiculo_lead_venda()
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
