import os
import sys
from typing import Optional
from fastmcp import FastMCP
from services.inventory_aggregator import InventoryAggregator
from services.fipe_service import FipeService
from services.pricing_service import PricingService
from utils.helpers import normalizar_placa
from config import logger

mcp = FastMCP("PrimeiraMaoSaga")

@mcp.tool()
async def listar_lojas():
    """Lista as lojas configuradas no banco de dados ou no arquivo de fallback (lojas_mock.csv)."""
    return await InventoryAggregator.obter_lista_lojas()

@mcp.tool()
async def estoque_total():
    """Retorna o estoque completo de todas as unidades mapeadas do Grupo Saga."""
    return await InventoryAggregator.buscar_estoque_consolidado()

@mcp.tool()
async def search_veiculos(
    marca: Optional[str] = None, 
    modelo: Optional[str] = None, 
    preco_max: Optional[float] = None
):
    """
    Busca inteligente no estoque. Todos os campos são opcionais.
    Resolve erros de validação permitindo valores nulos da interface.
    """
    estoque = await InventoryAggregator.buscar_estoque_consolidado()
    
    if marca is None and modelo is None and preco_max is None:
        return estoque[:20]

    res = []
    for v in estoque:
        match_marca = not marca or str(marca).lower() in str(v.get('makeName', '')).lower()
        match_modelo = not modelo or str(modelo).lower() in str(v.get('modelName', '')).lower()
        
        valor_veiculo = float(v.get('salePrice') or v.get('price') or 0)
        match_preco = preco_max is None or valor_veiculo <= preco_max
        
        if match_marca and match_modelo and match_preco:
            res.append(v)
        
    return res[:40]

@mcp.tool()
async def fetch_veiculo_detalhado(identificador: str):
    """
    Retorna o dossiê completo de um veículo (fotos, opcionais e dados técnicos).
    Aceita ID da Mobiauto ou Placa como identificador.
    """
    return await InventoryAggregator.buscar_veiculo_especifico(identificador)

@mcp.tool()
async def buscar_fipe(placa: str):
    """Consulta o valor atualizado da Tabela FIPE e dados técnicos via placa."""
    return await FipeService.consultar_por_placa(normalizar_placa(placa))

@mcp.tool()
async def avaliar_veiculo(
    placa: str,
    km: str,
    uf: str,
    cor: str,
    tipo: str,
    versao: Optional[str] = "não",
    existe_zero_km: Optional[str] = "não",
    tipo_carroceria: Optional[str] = "não",
):
    """
    Calcula a proposta de compra/troca do veículo.

    Fluxo interno:
      1. Consulta a FIPE pela placa para obter marca, modelo, ano, valor FIPE, código FIPE e combustível.
      2. Combina com os dados informados pelo cliente.
      3. Envia tudo para a API de precificação do Grupo Saga.

    Peça ao cliente APENAS: placa, km, uf, cor, tipo (ex: HATCH/SEDAN/SUV).
    versao, existe_zero_km e tipo_carroceria são opcionais — use "não" se não informados.
    """
    placa_limpa = normalizar_placa(placa)

    # Passo 1: busca FIPE para preencher automaticamente os campos técnicos
    fipe = await FipeService.consultar_por_placa(placa_limpa)

    if "error" in fipe:
        return {
            "error": "Não foi possível consultar a FIPE.",
            "detalhe": fipe,
            "mensagem": "Verifique a placa informada e tente novamente."
        }

    # Passo 2: monta o payload combinando dados da FIPE + dados do cliente
    dados = {
        "placa": placa_limpa,
        "valor_fipe": str(fipe.get("valor_fipe") or 0),
        "marca": fipe.get("marca") or "Não Informada",
        "modelo": fipe.get("modelo") or "Não Informado",
        "versao": versao or "não",
        "tipo_combustivel": fipe.get("combustivel") or "Flex",
        "ano_modelo": str(fipe.get("ano_modelo") or ""),
        "codigo_fipe": fipe.get("codigo_fipe") or "",
        "uf": uf,
        "tipo": tipo,
        "km": km,
        "cor": cor,
        "existe_zero_km": existe_zero_km or "não",
        "tipo_carroceria": tipo_carroceria or "não",
    }

    logger.info(f"Avaliação iniciada | Placa: {placa_limpa} | FIPE: R${dados['valor_fipe']}")

    # Passo 3: chama a API de precificação
    return await PricingService.calcular_compra(dados)

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    
    if transport == "sse":
        port = int(os.getenv("PORT", 8000))
        logger.info(f"Iniciando MCP em modo SSE na porta {port}")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")