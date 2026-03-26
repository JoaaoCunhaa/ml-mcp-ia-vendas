import os
from fastmcp import FastMCP
from config import MCP_TRANSPORT, logger
from services.mobiauto_service import MobiautoService
from services.fipe_service import FipeService
from services.pricing_service import PricingService
from services.inventory_aggregator import InventoryAggregator
from database.postgres_client import get_lojas_primeira_mao
from utils.helpers import formatar_moeda, normalizar_placa

mcp = FastMCP("PrimeiraMaoSaga")

# TOOLS 

@mcp.tool()
def listar_lojas():
    """Retorna a lista de todas as lojas 'Primeira Mão' e seus Dealer IDs."""
    return get_lojas_primeira_mao()

@mcp.tool()
async def search_veiculos(marca: str = None, modelo: str = None, cidade: str = None, preco_max: float = None):
    """Busca veículos em TODO o estoque consolidado da rede."""
    estoque = await InventoryAggregator.buscar_estoque_consolidado()
    res = estoque
    if marca: res = [v for v in res if marca.lower() in str(v.get('brand','')).lower()]
    if modelo: res = [v for v in res if modelo.lower() in str(v.get('model','')).lower()]
    if cidade: res = [v for v in res if cidade.lower() in str(v.get('city','')).lower()]
    if preco_max: res = [v for v in res if float(v.get('sellingPrice', 0)) <= preco_max]
    return [{
        "id": str(v.get("id")),
        "veiculo": f"{v.get('brand')} {v.get('model')} {v.get('modelYear')}",
        "valor": formatar_moeda(v.get("sellingPrice")),
        "loja": v.get("loja_origem"),
        "cidade": v.get("city")
    } for v in res[:20]]

@mcp.tool()
async def fetch_veiculo_detalhado(veiculo_id: str):
    """Retorna detalhes completos e fotos de um veículo específico pelo ID."""
    estoque = await InventoryAggregator.buscar_estoque_consolidado()
    veiculo = next((v for v in estoque if str(v.get("id")) == veiculo_id), None)
    return veiculo if veiculo else {"error": "Veículo não encontrado."}

@mcp.tool()
async def buscar_fipe(placa: str):
    """Consulta o valor da Tabela FIPE pela placa."""
    return await FipeService.consultar_por_placa(normalizar_placa(placa))

@mcp.tool()
async def avaliar_veiculo(placa:str, valor_fipe:str, marca:str, modelo:str, ano_modelo:str, km:str, uf:str="GO"):
    """Calcula a oferta de compra da loja."""
    dados = {
        "placa": normalizar_placa(placa),
        "valor_fipe": formatar_moeda(valor_fipe),
        "marca": marca, "modelo": modelo, "ano_modelo": ano_modelo,
        "km": km, "uf": uf
    }
    return await PricingService.calcular(dados)

if __name__ == "__main__":
    if os.getenv("MCP_TRANSPORT") == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()