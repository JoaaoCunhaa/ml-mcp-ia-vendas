import asyncio
from services.mobiauto_service import MobiautoService
from database.postgres_client import get_lojas_primeira_mao
from utils.helpers import normalizar_placa
from config import logger

LOJAS_POR_PAGINA = 3

class InventoryAggregator:
    _lojas_cache: list = None
    _ultima_fonte: str = None  # "banco" | "mock" | "vazio"

    BASE_SITE = "https://www.primeiramaosaga.com.br/gradedeofertas"

    @staticmethod
    def _formatar_preco(valor: float) -> str:
        try:
            return f"R$ {valor:_.2f}".replace(".", ",").replace("_", ".")
        except Exception:
            return "R$ --"


    # Opcionais relevantes para exibição no card (por prioridade)
    _OPCIONAIS_DESTAQUE = [
        "Ar-condicionado", "Ar condicionado",
        "Direção elétrica", "Direção hidráulica", "Direção assistida",
        "Vidro elétrico", "Vidros elétricos",
        "Trava elétrica", "Travas elétricas", "Trava central",
        "Câmera de ré", "Camera de re",
        "Freios ABS", "ABS",
        "Airbag", "Airbags",
        "Sensor de estacionamento", "Sensores de estacionamento",
        "Computador de bordo",
        "Multimídia", "Central multimídia",
    ]

    @staticmethod
    def _selecionar_opcionais(features: list, max_items: int = 4) -> list:
        """Retorna até max_items opcionais priorizando os de destaque."""
        if not features:
            return []
        feat_lower = {f.lower(): f for f in features}
        selecionados = []
        for destaque in InventoryAggregator._OPCIONAIS_DESTAQUE:
            if destaque.lower() in feat_lower:
                selecionados.append(feat_lower[destaque.lower()])
            if len(selecionados) >= max_items:
                break
        # Completa com outros opcionais se necessário
        if len(selecionados) < max_items:
            for f in features:
                if f not in selecionados:
                    selecionados.append(f)
                if len(selecionados) >= max_items:
                    break
        return selecionados

    @staticmethod
    def simplificar_veiculo(v, loja_nome):
        try:
            preco = float(v.get("salePrice") or v.get("price") or 0)
        except Exception:
            preco = 0.0

        vid          = str(v.get("id") or "")
        marca        = v.get("makeName") or ""
        modelo       = v.get("modelName") or ""
        versao       = v.get("trimName") or ""
        ano          = v.get("modelYear") or ""
        km_val       = v.get("km") or ""
        cor          = v.get("colorName") or ""
        placa        = v.get("plate") or ""
        imagens      = v.get("images") or []
        carroceria   = v.get("bodystyleName") or ""
        transmissao  = v.get("transmissionName") or ""
        combustivel  = v.get("fuelName") or ""
        portas       = v.get("doors") or ""
        features_raw = v.get("featuresName") or []
        opcionais    = InventoryAggregator._selecionar_opcionais(features_raw)

        # images é lista de dicts: {'url': '...', 'id': ..., 'position': ...}
        url_imagem = imagens[0].get("url", "") if imagens else ""
        preco_fmt  = InventoryAggregator._formatar_preco(preco)

        return {
            # — dados brutos (uso interno / filtros) —
            "id":           vid,
            "makeName":     marca,
            "modelName":    modelo,
            "trimName":     versao,
            "modelYear":    ano,
            "salePrice":    preco,
            "km":           km_val,
            "colorName":    cor,
            "plate":        placa,
            "loja_unidade": loja_nome,
            # — atributos técnicos —
            "carroceria":   carroceria,
            "transmissao":  transmissao,
            "combustivel":  combustivel,
            "portas":       portas,
            "opcionais":    opcionais,
            # — campos de renderização visual —
            "url_imagem":      url_imagem,
            "preco_formatado": preco_fmt,
            "link_ofertas":    InventoryAggregator.BASE_SITE,
            "titulo_card":     f"{marca} {modelo} {versao} {ano}".strip(),
        }

    @staticmethod
    async def obter_lista_lojas():
        if InventoryAggregator._lojas_cache:
            logger.info(f"[obter_lista_lojas] Cache hit | fonte={InventoryAggregator._ultima_fonte} | {len(InventoryAggregator._lojas_cache)} lojas")
            return InventoryAggregator._lojas_cache

        retorno = get_lojas_primeira_mao()
        InventoryAggregator._ultima_fonte = retorno.get("fonte", "vazio")
        lojas_raw = retorno.get("dados", [])

        if not lojas_raw:
            logger.warning("[obter_lista_lojas] Nenhuma loja encontrada")
            return []

        res = []
        for l in lojas_raw:
            # Suporta colunas do banco (loja_nome, dealerid, uf, agente_nome)
            # e do CSV mock     (vc_empresa, nm_codigo_svm, vc_uf, vc_cidade)
            codigo  = l.get("dealerid")   or l.get("nm_codigo_svm")
            nome_raw = l.get("loja_nome") or l.get("vc_empresa") or "Loja Saga"
            # "SN GO BURITI" → "Primeira Mão GO BURITI"
            nome = ("Primeira Mão " + nome_raw.strip()[3:]) if nome_raw.strip().upper().startswith("SN ") else nome_raw.strip()
            uf      = l.get("uf")         or l.get("vc_uf")             or "N/A"
            cidade  = l.get("vc_cidade")  or "N/A"
            agente  = l.get("agente_nome")         or ""
            telefone= l.get("agente_telefone")     or ""

            if codigo:
                res.append({
                    "nome":             nome,
                    "codigo_svm":       str(codigo),
                    "uf":               uf,
                    "cidade":           cidade,
                    "agente_nome":      agente,
                    "agente_telefone":  telefone,
                })

        InventoryAggregator._lojas_cache = res
        logger.info(f"[obter_lista_lojas] {len(res)} lojas cacheadas | fonte={InventoryAggregator._ultima_fonte}")
        return res

    @staticmethod
    async def buscar_estoque_paginado(pagina: int = 1):
        """
        Busca estoque de LOJAS_POR_PAGINA lojas por vez.
        Se a página solicitada não tiver veículos, avança automaticamente até encontrar ou esgotar.
        """
        lojas = await InventoryAggregator.obter_lista_lojas()
        if not lojas:
            return {
                "veiculos": [],
                "pagina": pagina,
                "total_lojas": 0,
                "total_paginas": 0,
                "tem_mais": False,
                "fonte_lojas": InventoryAggregator._ultima_fonte or "vazio",
                "lojas_buscadas": [],
            }

        token = await MobiautoService.get_token()
        if not token:
            logger.error("[buscar_estoque_paginado] Sem token — abortando")
            return {"veiculos": [], "pagina": pagina, "total_paginas": 0, "tem_mais": False,
                    "fonte_lojas": InventoryAggregator._ultima_fonte, "lojas_buscadas": []}

        total_lojas = len(lojas)
        total_paginas = (total_lojas + LOJAS_POR_PAGINA - 1) // LOJAS_POR_PAGINA
        pagina = max(1, min(pagina, total_paginas))

        # Tenta a página solicitada e avança automaticamente se vier vazia
        tentativa = pagina
        while tentativa <= total_paginas:
            inicio = (tentativa - 1) * LOJAS_POR_PAGINA
            lojas_pagina = lojas[inicio: inicio + LOJAS_POR_PAGINA]
            nomes_lojas = [l["nome"] for l in lojas_pagina]

            logger.info(f"[buscar_estoque_paginado] tentativa={tentativa}/{total_paginas} | lojas={nomes_lojas}")

            tarefas = [MobiautoService.buscar_estoque(l["codigo_svm"], token=token, page_size=20) for l in lojas_pagina]
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)

            veiculos = []
            sem_imagem = 0
            for i, lista in enumerate(resultados):
                nome_loja = lojas_pagina[i]["nome"]
                if isinstance(lista, list):
                    for v in lista:
                        if not v.get("images"):
                            sem_imagem += 1
                            continue  # ignora veículos sem imagem
                        veiculos.append(InventoryAggregator.simplificar_veiculo(v, nome_loja))
                else:
                    logger.error(f"[buscar_estoque_paginado] Erro na loja {nome_loja}: {lista}")

            logger.info(f"[buscar_estoque_paginado] com_imagem={len(veiculos)} | sem_imagem={sem_imagem} | tentativa={tentativa}")

            if veiculos:
                tem_mais = tentativa < total_paginas
                logger.info(f"[buscar_estoque_paginado] {len(veiculos)} veículos com imagem | pagina_real={tentativa} | tem_mais={tem_mais}")
                return {
                    "veiculos": veiculos,
                    "pagina": tentativa,
                    "total_paginas": total_paginas,
                    "tem_mais": tem_mais,
                    "fonte_lojas": InventoryAggregator._ultima_fonte or "vazio",
                    "lojas_buscadas": nomes_lojas,
                }

            logger.warning(f"[buscar_estoque_paginado] Página {tentativa} vazia — avançando")
            tentativa += 1

        logger.warning("[buscar_estoque_paginado] Nenhum veículo encontrado em nenhuma loja")
        return {
            "veiculos": [],
            "pagina": pagina,
            "total_paginas": total_paginas,
            "tem_mais": False,
            "fonte_lojas": InventoryAggregator._ultima_fonte or "vazio",
            "lojas_buscadas": [],
        }

    @staticmethod
    async def buscar_estoque_por_lojas(lojas: list, limit: int = 25) -> list:
        """Busca estoque de uma lista específica de lojas. Filtra veículos sem imagem e limita ao `limit`."""
        if not lojas:
            return []

        token = await MobiautoService.get_token()
        if not token:
            logger.error("[buscar_estoque_por_lojas] Sem token — abortando")
            return []

        tarefas = [
            MobiautoService.buscar_estoque(l["codigo_svm"], token=token, page_size=50)
            for l in lojas
        ]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        veiculos = []
        erros = 0
        for i, lista in enumerate(resultados):
            nome_loja = lojas[i]["nome"]
            if isinstance(lista, list):
                for v in lista:
                    if not v.get("images"):
                        continue
                    veiculos.append(InventoryAggregator.simplificar_veiculo(v, nome_loja))
                    if len(veiculos) >= limit:
                        logger.info(f"[buscar_estoque_por_lojas] Limite de {limit} atingido")
                        return veiculos
            else:
                erros += 1
                logger.error(f"[buscar_estoque_por_lojas] Erro na loja {nome_loja}: {lista}")

        logger.info(
            f"[buscar_estoque_por_lojas] Concluído | total={len(veiculos)} "
            f"| lojas_ok={len(lojas) - erros} | lojas_erro={erros}"
        )
        return veiculos

    @staticmethod
    async def buscar_estoque_consolidado(limit: int = None):
        """Busca estoque de todas as lojas. Usado pelo search_veiculos."""
        lojas = await InventoryAggregator.obter_lista_lojas()
        if not lojas:
            logger.warning("[buscar_estoque_consolidado] Sem lojas — abortando")
            return []

        token = await MobiautoService.get_token()
        if not token:
            logger.error("[buscar_estoque_consolidado] Sem token — abortando")
            return []

        page_size = max(5, (limit // len(lojas)) + 1) if limit else 20
        logger.info(f"[buscar_estoque_consolidado] Iniciando busca em {len(lojas)} lojas em paralelo | limit={limit} | page_size={page_size}")

        tarefas = [MobiautoService.buscar_estoque(l["codigo_svm"], token=token, page_size=page_size) for l in lojas]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        estoque_global = []
        erros = 0
        for i, veiculos in enumerate(resultados):
            nome_loja = lojas[i]["nome"]
            if isinstance(veiculos, list):
                for v in veiculos:
                    estoque_global.append(InventoryAggregator.simplificar_veiculo(v, nome_loja))
                    if limit and len(estoque_global) >= limit:
                        logger.info(f"[buscar_estoque_consolidado] Limite de {limit} atingido")
                        return estoque_global
            else:
                erros += 1
                logger.error(f"[buscar_estoque_consolidado] Erro na loja {nome_loja}: {veiculos}")

        logger.info(f"[buscar_estoque_consolidado] Concluído | total_veículos={len(estoque_global)} | lojas_ok={len(lojas) - erros} | lojas_erro={erros}")
        return estoque_global

    @staticmethod
    async def buscar_veiculo_especifico(identificador: str):
        id_str = str(identificador).strip().upper()
        placa_norm = normalizar_placa(id_str)

        lojas = await InventoryAggregator.obter_lista_lojas()
        token = await MobiautoService.get_token()
        if not lojas or not token:
            return None

        # Busca em TODAS as lojas em paralelo (não mais sequencial)
        tarefas = [
            MobiautoService.buscar_estoque(l["codigo_svm"], token=token, page_size=50)
            for l in lojas
        ]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        for i, veiculos in enumerate(resultados):
            if not isinstance(veiculos, list):
                continue
            for v in veiculos:
                if str(v.get("id")) == id_str or normalizar_placa(str(v.get("plate", ""))) == placa_norm:
                    logger.info(f"[buscar_veiculo_especifico] Encontrado | id/placa={identificador} | loja={lojas[i]['nome']}")
                    return InventoryAggregator.simplificar_veiculo(v, lojas[i]["nome"])

        logger.warning(f"[buscar_veiculo_especifico] Não encontrado | id/placa={identificador}")
        return None
