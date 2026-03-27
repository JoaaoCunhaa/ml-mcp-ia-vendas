import pytest
from python.mcp_primeira_mao.utils.helpers import normalizar_placa, formatar_moeda
from python.mcp_primeira_mao.services.inventory_aggregator import InventoryAggregator

def test_normalizar_placa_padronizacao():
    """Valida se a placa é limpa corretamente para consultas FIPE/Mobiauto."""
    assert normalizar_placa("abc-1234") == "ABC1234"
    assert normalizar_placa("  bra 2e19  ") == "BRA2E19"
    assert normalizar_placa(None) == ""

def test_formatar_moeda_resiliencia():
    """Garante que strings de preço sejam convertidas em float sem quebrar o sistema."""
    assert formatar_moeda("R$ 50.000,50") == "50000.50"
    assert formatar_moeda("1500") == "1500.00"
    assert formatar_moeda("texto_invalido") == "0.00"

def test_mapeamento_simplificar_veiculo():
    """Verifica se o simplificador lida com campos ausentes ou nulos."""
    veiculo_mock = {
        "id": 1010,
        "makeName": "Volkswagen",
        "modelName": "Nivus",
        "salePrice": None,
        "plate": "SGA2026"
    }
    res = InventoryAggregator.simplificar_veiculo(veiculo_mock, "Saga Park Sul")
    assert res["salePrice"] == 0.0
    assert res["loja_unidade"] == "Saga Park Sul"