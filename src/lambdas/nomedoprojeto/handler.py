import awswrangler as wr  # type: ignore
import json
import os
import pandas as pd
from utils import log, dumps

API_KEY = os.environ.get('API_KEY', '')

def lambda_handler(event, context):
    # Validação do x-api-key
    headers = event.get('headers') or {}
    provided_key = headers.get('x-api-key') or headers.get('X-Api-Key', '')
    if not API_KEY or provided_key != API_KEY:
        log("Acesso negado: x-api-key inválida ou ausente", level='WARNING')
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': dumps({'error': 'Unauthorized'})
        }

    # 1. Tratamento do evento para extrair 'cidade' (query string > body)
    try:
        qs = event.get('queryStringParameters') or {}
        cidade_param = qs.get('cidade')

        if not cidade_param:
            body = event.get('body', {})
            if isinstance(body, str):
                body = json.loads(body)
            if not isinstance(body, dict):
                body = event
            cidade_param = body.get('cidade', 'Goiânia')

        log(f"Iniciando busca para a cidade: {cidade_param}", level='INFO')
        
    except Exception as e:
        log(f"Erro ao processar parâmetros de entrada: {e}", level='ERROR')
        cidade_param = 'Goiânia'

    try:
        query = f"""
        SELECT 
            d.id,
            dl.mobi_id AS dealerid,
            dl."name" AS loja,
            c."name" AS cidade,
            c.state_id AS uf,
            t."name" AS versao_tabela,
            d.version AS versao_direta,
            m."name" AS modelo,
            mk."name" AS marca,
            d.price,
            d.km,              -- Nova coluna adicionada
            d.model_year,
            -- URL do Veículo
            'https://www.primeiramaosaga.com.br/gradedeofertas/' || 
            CAST(mk."name" AS VARCHAR) || '-' || 
            CAST(m."name" AS VARCHAR) || '-' || 
            REGEXP_REPLACE(CAST(t."name" AS VARCHAR), ' ', '-') || 
            '/detalhes/' || 
            CAST(d.id AS VARCHAR) AS url,
            -- URL da Imagem
            'https://images.primeiramaosaga.com.br/images/api/v1.0/' || 
            CAST(img.min_image_id AS VARCHAR) || 
            '/transform/2Cw_638,q_80' AS url_imagem
        FROM modelled.pm_deal AS d
        LEFT JOIN modelled.pm_trim AS t ON d.trim_id = t.id 
        LEFT JOIN modelled.pm_model AS m ON t.model_id = m.id
        LEFT JOIN modelled.pm_make AS mk ON m.make_id = mk.id
        LEFT JOIN modelled.pm_dealer AS dl ON d.dealer_id = dl.id
        LEFT JOIN modelled.pm_city AS c ON dl.city_id = c.id
        -- Subquery para pegar a imagem de menor posição
        INNER JOIN (
            SELECT deal_id, MIN(image_id) as min_image_id
            FROM modelled.pm_deal_x_image
            GROUP BY deal_id
        ) AS img ON d.id = img.deal_id
        WHERE d.status = 1
            AND c."name" = '{cidade_param}'
        LIMIT 25;
        """

        # 3. Execução no Athena com otimizações
        # ctas_approach=False resolve o erro de GlueEncryption/DeleteTable
        df = wr.athena.read_sql_query(
            sql=query, 
            database="modelled",
            ctas_approach=False,
            athena_cache_settings={"max_cache_age": 60} # Opcional: cache de 60s para velocidade
        )
        
        # Converte o DataFrame para o formato de dicionário
        result = df.to_dict(orient="records")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': dumps(result)
        }

    except Exception as e:
        log(f'Erro ao executar query no Athena: {e}', level='ERROR')
        return {
            'statusCode': 500,
            'body': dumps({
                'error': 'Erro interno ao processar a consulta',
                'details': str(e)
            })
        }