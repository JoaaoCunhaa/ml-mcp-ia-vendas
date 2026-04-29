# Funções Lambda — MCP Primeira Mão Saga

Lista de funções AWS Lambda utilizadas pelo projeto.

| Nome da Função | Runtime | Propósito |
| :--- | :--- | :--- |
| Lambda de Estoque (`LAMBDA_ESTOQUE_URL`) | Python 3.11 | Consulta Athena e retorna veículos ativos filtrados |

---

## Lambda de Estoque

### Visão geral

Função exposta via **API Gateway** que executa uma query SQL no **AWS Athena** sobre as tabelas `modelled.pm_*` e retorna veículos ativos do estoque Primeira Mão Saga.

É a **fonte primária** para a tool `buscar_veiculos` do servidor MCP.

### Localização do código

```
src/lambdas/nomedoprojeto/
├── handler.py    # Lógica principal: validação, query builder, chamada Athena
└── utils.py      # Helpers: log(), dumps() (serialização JSON segura)
```

### Autenticação

Requer header `x-api-key` com o valor de `LAMBDA_API_KEY`. Retorna `401 Unauthorized` se ausente ou incorreto.

### Entrada

Aceita parâmetros via **query string** (GET) ou **body JSON** (POST):

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cidade` | string | Sim | Nome da cidade (ex: `Goiânia`). Default: `Goiânia` |
| `marca` | string | Não | Filtro por marca (LIKE, sem acento) |
| `modelo` | string | Não | Filtro por modelo (LIKE, sem acento) |
| `versao` | string | Não | Filtro por versão/trim (LIKE, sem acento) |
| `preco_min` | number | Não | Preço mínimo em reais |
| `preco_max` | number | Não | Preço máximo em reais |
| `km_max` | number | Não | KM máximo |
| `ano_min` | number | Não | Ano mínimo do modelo |
| `ano_max` | number | Não | Ano máximo do modelo |
| `limit` | number | Não | Máximo de resultados. Default: `25` |

### Query Athena gerada

A Lambda monta uma query dinâmica sobre as tabelas do schema `modelled`:

```sql
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
    'https://www.primeiramaosaga.com.br/gradedeofertas/' || ... AS url,
    'https://images.primeiramaosaga.com.br/images/api/v1.0/' || ... AS url_imagem
FROM modelled.pm_deal AS d
LEFT JOIN modelled.pm_trim   AS t   ON d.trim_id   = t.id
LEFT JOIN modelled.pm_model  AS m   ON t.model_id  = m.id
LEFT JOIN modelled.pm_make   AS mk  ON m.make_id   = mk.id
LEFT JOIN modelled.pm_dealer AS dl  ON d.dealer_id = dl.id
LEFT JOIN modelled.pm_city   AS c   ON dl.city_id  = c.id
INNER JOIN (
    SELECT deal_id, MIN(image_id) as min_image_id
    FROM modelled.pm_deal_x_image
    GROUP BY deal_id
) AS img ON d.id = img.deal_id
WHERE LOWER(TRANSLATE(c."name", ...)) = '{cidade_norm}'
  AND d.status = 1
  [AND filtros opcionais...]
LIMIT {limit};
```

Filtros importantes:
- **`d.status = 1`**: garante que apenas veículos **disponíveis** aparecem (vendidos são excluídos).
- **Normalização de texto**: cidades e strings de filtro são normalizadas (sem acento, minúsculas) via `TRANSLATE` no Athena para comparação segura.
- **INNER JOIN com pm_deal_x_image**: garante que apenas veículos com ao menos uma imagem são retornados.

### Saída

Array JSON com os campos:

```json
[
  {
    "id": 53480,
    "dealerid": "18405",
    "loja": "SN GO BURITI",
    "cidade": "Goiânia",
    "uf": "GO",
    "versao_tabela": "Civic Touring CVT",
    "versao_direta": "Touring",
    "modelo": "Civic",
    "marca": "Honda",
    "price": 89900.00,
    "km": 32000,
    "model_year": 2021,
    "url": "https://www.primeiramaosaga.com.br/gradedeofertas/Honda-Civic-Civic-Touring-CVT/detalhes/53480",
    "url_imagem": "https://images.primeiramaosaga.com.br/images/api/v1.0/12345/transform/2Cw_638,q_80"
  }
]
```

### Caching Athena

A Lambda usa `athena_cache_settings={"max_cache_age": 60}` via `awswrangler` — resultados são cacheados por até 60 segundos no Athena para evitar reprocessamento de queries idênticas.

### Configuração no servidor MCP

```
LAMBDA_ESTOQUE_URL=https://<api-gateway-id>.execute-api.<region>.amazonaws.com/<stage>/
LAMBDA_API_KEY=<chave-secreta>
```

O serviço `LambdaInventoryService` (`services/lambda_inventory_service.py`) é o cliente HTTP que chama esta Lambda, normaliza a resposta para o contrato do widget e é usado por `buscar_veiculos` em `main.py`.
