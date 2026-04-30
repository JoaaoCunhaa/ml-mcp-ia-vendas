# Fontes de Dados — MCP Primeira Mão Saga

---

## Fonte 1 (primária): Lambda AWS — Estoque Primeira Mão

**Tipo:** AWS API Gateway → Lambda Python 3.11 → AWS Athena  
**Arquivo cliente:** `services/lambda_inventory_service.py`  
**Variáveis:** `LAMBDA_ESTOQUE_URL`, `LAMBDA_API_KEY`

### Autenticação
Header `x-api-key` com o valor de `LAMBDA_API_KEY`. Retorna 401 se ausente.

### Parâmetros aceitos (GET query string ou POST body)

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cidade` | string | Sim | Nome da cidade (ex: `Goiânia`) |
| `marca` | string | Não | Filtro LIKE por marca |
| `modelo` | string | Não | Filtro LIKE por modelo |
| `versao` | string | Não | Filtro LIKE por versão/trim |
| `preco_min` | number | Não | Preço mínimo em reais |
| `preco_max` | number | Não | Preço máximo em reais |
| `km_max` | number | Não | KM máximo |
| `ano_min` | number | Não | Ano modelo mínimo |
| `ano_max` | number | Não | Ano modelo máximo |
| `limit` | number | Não | Máximo de resultados (padrão 25) |

### Query Athena executada pela Lambda

```sql
SELECT
    d.id,
    dl.mobi_id        AS dealerid,
    dl."name"         AS loja,
    c."name"          AS cidade,
    c.state_id        AS uf,
    t."name"          AS versao_tabela,
    d.version         AS versao_direta,
    m."name"          AS modelo,
    mk."name"         AS marca,
    d.price,
    d.km,
    d.model_year,
    'https://www.primeiramaosaga.com.br/gradedeofertas/...' AS url,
    'https://images.primeiramaosaga.com.br/images/api/v1.0/...' AS url_imagem
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

**Filtros importantes:**
- `d.status = 1` — apenas veículos disponíveis (vendidos são excluídos)
- `INNER JOIN com pm_deal_x_image` — apenas veículos com ao menos uma imagem
- Normalização de texto: cidades comparadas sem acento e em minúsculas

### Saída normalizada

```json
[
  {
    "id": 53480,
    "titulo_card": "Honda Civic Touring 2021",
    "marca": "Honda",
    "modelo": "Civic",
    "versao": "Civic Touring CVT",
    "model_year": 2021,
    "km": 32000,
    "price": 89900.0,
    "preco_formatado": "R$ 89.900",
    "loja": "SN GO BURITI",
    "loja_unidade": "SN GO BURITI",
    "dealerid": "18405",
    "cidade": "Goiânia",
    "uf": "GO",
    "url_imagem": "https://images.primeiramaosaga.com.br/...",
    "link_ofertas": "https://www.primeiramaosaga.com.br/gradedeofertas/..."
  }
]
```

### Caching Athena
A Lambda usa `max_cache_age: 60s` via `awswrangler` — queries idênticas são cacheadas por até 60 segundos.

---

## Fonte 2 (fallback): API Mobiauto — Estoque de Veículos

**Tipo:** REST API  
**Arquivo cliente:** `services/mobiauto_service.py` + `services/inventory_aggregator.py`  
**Ativado quando:** Lambda retorna lista vazia

### Autenticação
Bearer token obtido via `URL_AWS_TOKEN` + `MOBI_SECRET`. Token cacheado em memória; renovado automaticamente em caso de HTTP 401.

### Endpoint
```
GET https://open-api.mobiauto.com.br/api/dealer/{dealer_id}/inventory/v1.0
Authorization: Bearer {token}
```

### Uso no servidor

- **`InventoryAggregator`**: busca por lista de lojas, pagina 3 lojas por vez
- **`MobiautoService.buscar_estoque()`**: busca estoque de um dealer específico

---

## Fonte 3: API FIPE Saga

**Tipo:** REST API interna  
**Arquivo cliente:** `services/fipe_service.py`  
**Usado por:** `avaliar_veiculo`  
**Timeout:** 60s, retry até 3×

### Endpoint
```
GET {FIPE_API_URL}/fipe?placa={placa}
```

### Saída
```json
{
  "placa": "ABC1D23",
  "marca": "Honda",
  "modelo": "Civic",
  "versao": "Touring CVT",
  "ano_modelo": "2021",
  "valor_fipe": 95000.00,
  "combustivel": "Flex",
  "codigo_fipe": "026013-3",
  "carroceria": "Sedan",
  "mes_referencia": "abril/2026"
}
```

---

## Fonte 4: API de Precificação Saga

**Tipo:** REST API interna  
**Arquivo cliente:** `services/pricing_service.py`  
**Usado por:** `avaliar_veiculo`  
**Timeout:** 20s (configurável via `API_TIMEOUT`)

### Endpoint
```
POST {PRECIFICACAO_API_URL}/carro/compra
Content-Type: application/json
```

### Payload enviado
```json
{
  "placa": "ABC1D23",
  "valor_fipe": 95000.00,
  "marca": "Honda",
  "modelo": "Civic",
  "versao": "Touring CVT",
  "combustivel": "Flex",
  "ano_modelo": "2021",
  "uf": "GO",
  "km": "55000.00",
  "codigo_fipe": "026013-3",
  "cor": "Preto",
  "existe_zero_km": false,
  "tipo_carroceria": "Sedan"
}
```

### Saída
```json
{ "Valor_proposta_compra": 85000.00 }
```

---

## Fonte 5: PostgreSQL — Lista de lojas

**Arquivo:** `database/postgres_client.py`  
**Tabela:** `lojas_ids_mobigestor` (quando disponível)  
**Fallback atual:** `database/lojas_mock.csv`

### Campos por loja
| Campo | Descrição |
|---|---|
| `loja_nome` | Nome da loja |
| `dealerid` | ID do dealer no Mobiauto |
| `uf` | Estado da loja |
| `agente_nome` | Nome do consultor responsável |
| `agente_telefone` | Telefone do consultor |
