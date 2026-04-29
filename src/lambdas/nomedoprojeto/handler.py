import awswrangler as wr  # type: ignore
import json
import os
import pandas as pd  # noqa: F401
from utils import log, dumps

LAMBDA_API_KEY = os.environ.get('LAMBDA_API_KEY', '')

SELECT_BASE = """
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
        d.km,
        d.model_year,
        'https://www.primeiramaosaga.com.br/gradedeofertas/' ||
        CAST(mk."name" AS VARCHAR) || '-' ||
        CAST(m."name" AS VARCHAR) || '-' ||
        REGEXP_REPLACE(CAST(t."name" AS VARCHAR), ' ', '-') ||
        '/detalhes/' ||
        CAST(d.id AS VARCHAR) AS url,
        'https://images.primeiramaosaga.com.br/images/api/v1.0/' ||
        CAST(img.min_image_id AS VARCHAR) ||
        '/transform/2Cw_638,q_80' AS url_imagem
    FROM modelled.pm_deal AS d
    LEFT JOIN modelled.pm_trim AS t ON d.trim_id = t.id
    LEFT JOIN modelled.pm_model AS m ON t.model_id = m.id
    LEFT JOIN modelled.pm_make AS mk ON m.make_id = mk.id
    LEFT JOIN modelled.pm_dealer AS dl ON d.dealer_id = dl.id
    LEFT JOIN modelled.pm_city AS c ON dl.city_id = c.id
    INNER JOIN (
        SELECT deal_id, MIN(image_id) as min_image_id
        FROM modelled.pm_deal_x_image
        GROUP BY deal_id
    ) AS img ON d.id = img.deal_id
"""


def _sanitize(value: str) -> str:
    """Remove caracteres perigosos para evitar SQL injection."""
    return value.replace("'", "''").replace(";", "").replace("--", "")


_ACENTOS = "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ"
_SIMPLES = (
    "a" * 5 + "e" * 4 + "i" * 4 + "o" * 5 + "u" * 4 + "c" +
    "A" * 5 + "E" * 4 + "I" * 4 + "O" * 5 + "U" * 4 + "C"
)

def _norm_sql(col: str) -> str:
    """Expressão SQL que remove acentos e coloca em minúsculo (Athena/Presto)."""
    return f"LOWER(TRANSLATE({col}, '{_ACENTOS}', '{_SIMPLES}'))"

def _norm_val(val: str) -> str:
    """Normaliza valor Python da mesma forma para comparar com _norm_sql."""
    table = str.maketrans(_ACENTOS, _SIMPLES)
    return val.translate(table).lower()


def _build_query(params: dict) -> str:
    cidade    = params.get('cidade', 'Goiânia')
    marca     = params.get('marca')
    modelo    = params.get('modelo')
    versao    = params.get('versao')
    preco_min = params.get('preco_min')
    preco_max = params.get('preco_max')
    km_max    = params.get('km_max')
    ano_min   = params.get('ano_min')
    ano_max   = params.get('ano_max')
    limit     = int(params.get('limit', 25))

    cidade_norm = _sanitize(_norm_val(cidade))
    filters = [
        f"{_norm_sql('c.\"name\"')} = '{cidade_norm}'",
        "d.status = 1",
    ]

    if marca:
        filters.append(f"{_norm_sql('mk.\"name\"')} LIKE '%{_sanitize(_norm_val(marca))}%'")
    if modelo:
        filters.append(f"{_norm_sql('m.\"name\"')} LIKE '%{_sanitize(_norm_val(modelo))}%'")
    if versao:
        filters.append(f"{_norm_sql('t.\"name\"')} LIKE '%{_sanitize(_norm_val(versao))}%'")
    if preco_min:
        filters.append(f"d.price >= {float(preco_min)}")
    if preco_max:
        filters.append(f"d.price <= {float(preco_max)}")
    if km_max:
        filters.append(f"d.km <= {int(km_max)}")
    if ano_min:
        filters.append(f"d.model_year >= {int(ano_min)}")
    if ano_max:
        filters.append(f"d.model_year <= {int(ano_max)}")

    where = "WHERE " + "\n        AND ".join(filters)
    return f"{SELECT_BASE}\n    {where}\n    LIMIT {limit};"


def lambda_handler(event, context):
    # Validação do x-api-key
    headers = event.get('headers') or {}
    provided_key = headers.get('x-api-key') or headers.get('X-Api-Key', '')
    if not LAMBDA_API_KEY or provided_key != LAMBDA_API_KEY:
        log("Acesso negado: x-api-key inválida ou ausente", level='WARNING')
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': dumps({'error': 'Unauthorized'})
        }

    # Extrai parâmetros do query string (GET) ou body (POST)
    try:
        qs = event.get('queryStringParameters') or {}
        if not qs:
            body = event.get('body', {})
            if isinstance(body, str):
                body = json.loads(body)
            qs = body if isinstance(body, dict) else {}

        cidade = qs.get('cidade') or 'Goiânia'
        params = {
            'cidade':    cidade,
            'marca':     qs.get('marca'),
            'modelo':    qs.get('modelo'),
            'versao':    qs.get('versao'),
            'preco_min': qs.get('preco_min'),
            'preco_max': qs.get('preco_max'),
            'km_max':    qs.get('km_max'),
            'ano_min':   qs.get('ano_min'),
            'ano_max':   qs.get('ano_max'),
            'limit':     qs.get('limit', 25),
        }
        log(f"Parâmetros recebidos: {params}", level='INFO')

    except Exception as e:
        log(f"Erro ao processar parâmetros: {e}", level='ERROR')
        params = {'cidade': 'Goiânia'}

    try:
        query = _build_query(params)
        log(f"Query gerada:\n{query}", level='INFO')

        df = wr.athena.read_sql_query(
            sql=query,
            database="modelled",
            ctas_approach=False,
            athena_cache_settings={"max_cache_age": 60}
        )

        result = df.to_dict(orient="records")
        log(f"{len(result)} veículos retornados", level='INFO')

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': dumps(result)
        }

    except Exception as e:
        log(f'Erro ao executar query: {e}', level='ERROR')
        return {
            'statusCode': 500,
            'body': dumps({'error': 'Erro interno', 'details': str(e)})
        }
