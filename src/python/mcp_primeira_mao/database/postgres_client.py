# import psycopg2                        # ← descomentar ao reativar banco
import pandas as pd
import os
# from psycopg2.extras import RealDictCursor  # ← descomentar ao reativar banco
from config import DB_CONFIG, logger    # DB_CONFIG ainda importado para quando reativar

def get_lojas_primeira_mao() -> dict:
    """
    Retorna as lojas Primeira Mão com 'dados' (lista) e 'fonte' ("banco" | "mock" | "vazio").

    MODO ATUAL: lendo do lojas_mock.csv (banco comentado).
    Para reativar o banco: descomentar o bloco marcado com [BANCO] abaixo
    e comentar o bloco [MOCK DIRETO].
    """

    # ─────────────────────────────────────────────────────────
    # [BANCO] Bloco desativado — descomentar para usar Postgres
    # ─────────────────────────────────────────────────────────
    # query = """
    #     SELECT loja_nome, dealerid, uf, agente_nome, agente_telefone
    #     FROM public.loja_ids_mobigestor
    #     WHERE loja_nome LIKE %s
    #       AND loja_nome NOT LIKE %s
    #       AND loja_nome NOT LIKE %s
    #     ORDER BY loja_nome;
    # """
    # filtro_seguro = ('%prim%', '%desativad%', '%totem%')
    #
    # try:
    #     with psycopg2.connect(**DB_CONFIG) as conn:
    #         with conn.cursor(cursor_factory=RealDictCursor) as cur:
    #             cur.execute(query, filtro_seguro)
    #             res = list(cur.fetchall())
    #             if res:
    #                 logger.info(f"[postgres_client] {len(res)} lojas encontradas via Postgres.")
    #                 return {"dados": res, "fonte": "banco"}
    # except Exception as e:
    #     logger.error(f"[postgres_client] Erro ao consultar Postgres: {e}")
    # ─────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────
    # [MOCK DIRETO] Lendo do CSV sem tentar o banco
    # ─────────────────────────────────────────────────────────
    logger.info("[postgres_client] Modo mock ativo — lendo lojas_mock.csv diretamente.")
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(base_path, 'lojas_mock.csv')

        if not os.path.exists(csv_path):
            csv_path = os.path.join(os.path.dirname(base_path), 'lojas_mock.csv')

        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            logger.info(f"[postgres_client] {len(df)} lojas carregadas do mock CSV.")
            return {"dados": df.to_dict(orient='records'), "fonte": "mock"}
        else:
            logger.error(f"[postgres_client] Arquivo mock não encontrado: {csv_path}")
    except Exception as e:
        logger.error(f"[postgres_client] Erro ao ler mock CSV: {e}")
    # ─────────────────────────────────────────────────────────

    return {"dados": [], "fonte": "vazio"}
