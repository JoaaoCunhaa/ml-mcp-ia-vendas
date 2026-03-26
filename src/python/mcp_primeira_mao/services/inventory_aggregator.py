import asyncio
from services.mobiauto_service import MobiautoService
from database.postgres_client import get_lojas_primeira_mao

class InventoryAggregator:
    @staticmethod
    async def buscar_estoque_consolidado():
        """Percorre todas as lojas e consolida os veículos em uma única lista."""
        lojas = get_lojas_primeira_mao()
        if not lojas:
            return []

        tarefas = [MobiautoService.buscar_estoque(str(loja['dealerid'])) for loja in lojas]
        resultados = await asyncio.gather(*tarefas)
        
        estoque_global = []
        for i, veiculos in enumerate(resultados):
            nome_loja = lojas[i].get('loja_nome', 'Loja Desconhecida')
            for v in veiculos:
                v['loja_origem'] = nome_loja
                estoque_global.append(v)
                
        return estoque_global