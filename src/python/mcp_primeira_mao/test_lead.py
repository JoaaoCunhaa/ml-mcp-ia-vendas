"""
Teste de integração: API Mobiauto (lead criação) + Webhooks internos.
Roda 4 testes independentes e imprime os resultados.

Uso:
  python test_lead.py
"""

import asyncio
import os
import sys

import httpx

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from config import logger  # noqa — dispara load_dotenv
from services.mobiauto_proposal_service import MobiautoProposalService

WH_COMPRA = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_comprar"
WH_VENDA  = "https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_vender"

SEP = "=" * 55


# ─── Testes de lead (API Mobiauto) ────────────────────────────

async def test_lead_compra() -> dict:
    print(f"\n{SEP}")
    print("TESTE 1 — Lead COMPRA via API Mobiauto (BUY)")
    print("  Loja   : SN GO BURITI  (dealer_id esperado: 18405)")
    print("  Cliente: Joao Teste MCP")
    print(SEP)

    resultado = await MobiautoProposalService.criar_lead(
        intention_type="BUY",
        nome="Joao Teste MCP",
        telefone="62999990001",
        email="teste-compra@sagadatadriven.com.br",
        loja_nome="SN GO BURITI",
        mensagem="Lead de teste — MCP PrimeiraMao COMPRA",
    )

    ok = resultado.get("success")
    print(f"  Resultado  : {'OK' if ok else 'FALHOU'}")
    print(f"  dealer_id  : {resultado.get('dealer_id')}")
    print(f"  lead_id    : {(resultado.get('response') or {}).get('id')}")
    print(f"  response   : {resultado.get('response')}")
    if not ok:
        print(f"  Erro       : {resultado.get('error')}")
        print(f"  Detalhe    : {resultado.get('detalhe', '')[:300]}")
    return resultado


async def test_lead_venda() -> dict:
    print(f"\n{SEP}")
    print("TESTE 2 — Lead VENDA via API Mobiauto (SELL)")
    print("  UF     : GO  (primeiro dealer GO sera usado)")
    print("  Cliente: Maria Teste MCP")
    print(SEP)

    resultado = await MobiautoProposalService.criar_lead(
        intention_type="SELL",
        nome="Maria Teste MCP",
        telefone="62988880002",
        email="teste-venda@sagadatadriven.com.br",
        uf_fallback="GO",
        mensagem=(
            "Lead de teste — MCP PrimeiraMao VENDA | "
            "Placa: TST1T23 | KM: 50000 | Veiculo: Honda Fit 2018"
        ),
    )

    ok = resultado.get("success")
    print(f"  Resultado  : {'OK' if ok else 'FALHOU'}")
    print(f"  dealer_id  : {resultado.get('dealer_id')}")
    print(f"  lead_id    : {(resultado.get('response') or {}).get('id')}")
    print(f"  response   : {resultado.get('response')}")
    if not ok:
        print(f"  Erro       : {resultado.get('error')}")
        print(f"  Detalhe    : {resultado.get('detalhe', '')[:300]}")
    return resultado


# ─── Testes de webhook interno ────────────────────────────────

async def _post_webhook(url: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        return {"success": resp.is_success, "status": resp.status_code, "body": resp.text[:300]}
    except Exception as exc:
        return {"success": False, "status": None, "body": str(exc)}


async def test_webhook_compra() -> dict:
    print(f"\n{SEP}")
    print("TESTE 3 — Webhook interno COMPRA")
    print(f"  URL: {WH_COMPRA}")
    print(SEP)

    payload = {
        "lead_id":         "TESTE-BUY-MCP",
        "nome_cliente":    "Joao Teste Webhook",
        "telefone_cliente": "62999990003",
        "email_cliente":   "teste-wh-compra@sagadatadriven.com.br",
        "titulo_card":     "Honda Civic Touring 2021",
        "preco_formatado": "R$ 89.900,00",
        "loja_unidade":    "SN GO BURITI",
        "plate":           "TST0001",
        "modelYear":       "2021",
        "km":              "32000",
        "colorName":       "Preto",
        "dealer_id":       "18405",
        "observacao":      "Teste de webhook interno — MCP PrimeiraMao",
    }

    resultado = await _post_webhook(WH_COMPRA, payload)
    print(f"  Status     : {resultado['status']}")
    print(f"  Resultado  : {'OK' if resultado['success'] else 'FALHOU'}")
    print(f"  Body       : {resultado['body']}")
    return resultado


async def test_webhook_venda() -> dict:
    print(f"\n{SEP}")
    print("TESTE 4 — Webhook interno VENDA")
    print(f"  URL: {WH_VENDA}")
    print(SEP)

    payload = {
        "lead_id":           "TESTE-SELL-MCP",
        "nome_cliente":      "Maria Teste Webhook",
        "telefone_cliente":  "62988880004",
        "email_cliente":     "teste-wh-venda@sagadatadriven.com.br",
        "placa":             "TST1T23",
        "km":                "50000",
        "veiculo_descricao": "Honda Fit EX 2018",
        "valor_proposta":    "28500.00",
        "preco_formatado":   "R$ 28.500,00",
        "marca":             "Honda",
        "modelo":            "Fit",
        "ano_modelo":        "2018",
        "cor":               "Prata",
        "uf":                "GO",
        "dealer_id":         "18415",
        "observacao":        "Teste de webhook interno — MCP PrimeiraMao",
    }

    resultado = await _post_webhook(WH_VENDA, payload)
    print(f"  Status     : {resultado['status']}")
    print(f"  Resultado  : {'OK' if resultado['success'] else 'FALHOU'}")
    print(f"  Body       : {resultado['body']}")
    return resultado


# ─── Main ─────────────────────────────────────────────────────

async def main():
    r1 = await test_lead_compra()
    r2 = await test_lead_venda()
    r3 = await test_webhook_compra()
    r4 = await test_webhook_venda()

    print(f"\n{SEP}")
    print("RESUMO FINAL")
    print(SEP)
    print(f"  [1] Lead  COMPRA (API)     : {'OK' if r1.get('success') else 'FALHOU'}"
          f" | dealer={r1.get('dealer_id')} | lead_id={(r1.get('response') or {}).get('id')}")
    print(f"  [2] Lead  VENDA  (API)     : {'OK' if r2.get('success') else 'FALHOU'}"
          f" | dealer={r2.get('dealer_id')} | lead_id={(r2.get('response') or {}).get('id')}")
    print(f"  [3] Webhook COMPRA (interno): {'OK' if r3.get('success') else 'FALHOU'}"
          f" | status={r3.get('status')}")
    print(f"  [4] Webhook VENDA  (interno): {'OK' if r4.get('success') else 'FALHOU'}"
          f" | status={r4.get('status')}")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
