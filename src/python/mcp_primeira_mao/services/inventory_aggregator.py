import asyncio
import os
import json
from services.mobiauto_service import MobiautoService
from database.postgres_client import get_lojas_primeira_mao
from utils.helpers import normalizar_placa
from config import logger

class InventoryAggregator:
    @staticmethod
    async def obter_lista_lojas():
        try:
            lojas = get_lojas_primeira_mao()
            if lojas:
                return lojas
        except Exception as e:
            logger.warning(f"Erro no banco, tentando mock: {e}")
        
        # Sobe um nível para achar a pasta database a partir de services/
        caminho_mock = os.path.join(os.path.dirname(__file__), "..", "database", "lojas_mock.csv")
        if os.path.exists(caminho_mock):
            with open(caminho_mock, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    @staticmethod
    async def buscar_estoque_consolidado():
        lojas = await InventoryAggregator.obter_lista_lojas()
        if not lojas:
            return []

        tarefas = [MobiautoService.buscar_estoque(str(loja['dealerid'])) for loja in lojas]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        
        estoque_global = []
        for i, veiculos in enumerate(resultados):
            nome_loja = lojas[i].get('loja_nome', 'Loja Desconhecida')
            if isinstance(veiculos, Exception) or not veiculos:
                continue
            
            for v in veiculos:
                v['loja_origem'] = nome_loja
                estoque_global.append(v)
        
        return estoque_global

    @staticmethod
    async def buscar_veiculo_especifico(identificador: str):
        estoque = await InventoryAggregator.buscar_estoque_consolidado()
        id_str = str(identificador).strip()
        placa_normalizada = normalizar_placa(id_str)

        for v in estoque:
            if str(v.get("id")) == id_str:
                return v
            v_placa = normalizar_placa(str(v.get("licensePlate", "")))
            if v_placa == placa_normalizada and placa_normalizada != "":
                return v
        return None