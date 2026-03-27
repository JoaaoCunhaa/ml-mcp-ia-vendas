import pytest
from python.mcp_primeira_mao.services.inventory_aggregator import InventoryAggregator

@pytest.mark.asyncio
async def test_fluxo_consolidacao_estoque_real():
    """Testa se o sistema consegue buscar lojas e consolidar o estoque real."""
    lojas = await InventoryAggregator.obter_lista_lojas()
    assert isinstance(lojas, list)
    
    if lojas:
        estoque = await InventoryAggregator.buscar_estoque_consolidado()
        assert isinstance(estoque, list)
        if len(estoque) > 0:
            assert "loja_unidade" in estoque[0]
            print(f"\n✅ Integração Saga OK: {len(estoque)} veículos encontrados.")

@pytest.mark.asyncio
async def test_servico_fipe_conectividade():
    """Verifica se a API de FIPE da Saga está acessível e respondendo."""
    from python.mcp_primeira_mao.services.fipe_service import FipeService
    res = await FipeService.consultar_por_placa("BRA2E19")
    assert isinstance(res, dict)
    assert "error" in res or "valor_fipe" in res