import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

SERVER_URL = "https://mcp-primeiramao.sagadatadriven.com.br/sse"

async def run_full_test():
    print(f"🚀 Iniciando Full Test em: {SERVER_URL}\n")
    
    try:
        async with sse_client(SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()

                # 1. LISTAR LOJAS
                print("🔹 [1/6] Testando: listar_lojas")
                res = await session.call_tool("listar_lojas", {})
                print(f"✅ OK! Encontradas {len(json.loads(res.content[0].text))} lojas.")

                # 2. ESTOQUE TOTAL
                print("\n🔹 [2/6] Testando: estoque_total")
                res = await session.call_tool("estoque_total", {})
                print(f"✅ OK! Dados de estoque recebidos.")

                # 3. BUSCA FILTRADA
                print("\n🔹 [3/6] Testando: search_veiculos (Toyota)")
                res = await session.call_tool("search_veiculos", {"marca": "Toyota"})
                veiculos = json.loads(res.content[0].text)
                print(f"✅ OK! Encontrados {len(veiculos)} Toyotas.")
                
                # Pegar o ID do primeiro veículo para o próximo teste
                id_teste = veiculos[0].get('id') if veiculos else "28043010"

                # 4. DETALHE DO VEÍCULO (DOSSIÊ)
                print(f"\n🔹 [4/6] Testando: fetch_veiculo_detalhado (ID: {id_teste})")
                res = await session.call_tool("fetch_veiculo_detalhado", {"identificador": str(id_teste)})
                print(f"✅ OK! Dossiê recebido.")

                # 5. BUSCAR FIPE
                print("\n🔹 [5/6] Testando: buscar_fipe")
                # Testando com a placa do Corolla que veio na sua busca anterior
                res = await session.call_tool("buscar_fipe", {"placa": "SLL1H77"})
                print(f"ℹ️ Resultado FIPE: {res.content[0].text}")

                # 6. AVALIAR VEÍCULO (PRECIFICAÇÃO SAGA)
                print("\n🔹 [6/6] Testando: avaliar_veiculo")
                dados_aval = {
                    "placa": "SLL1H77",
                    "valor_fipe": "170000",
                    "marca": "Toyota",
                    "modelo": "Corolla Cross",
                    "ano_modelo": "2024",
                    "km": "23000",
                    "uf": "RO"
                }
                res = await session.call_tool("avaliar_veiculo", dados_aval)
                print(f"✅ OK! Resposta da precificação: {res.content[0].text}")

                print("\n🏆 TESTE COMPLETO FINALIZADO!")

    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    asyncio.run(run_full_test())