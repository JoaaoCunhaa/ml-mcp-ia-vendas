# Fontes de Dados — MCP Primeira Mão Saga

---

## Fonte 1: API Mobiauto — Estoque de Veículos

- **Tipo:** REST API externa
- **Tecnologia:** HTTP GET / JSON
- **Local de Acesso:** `https://open-api.mobiauto.com.br/api/dealer/{dealer_id}/inventory/v1.0`
- **Frequência de Atualização:** Em tempo real — cada chamada consulta o estado atual do estoque
- **Descrição:** Retorna todos os veículos disponíveis de um dealer específico. Inclui imagens, preços, dados técnicos (marca, modelo, versão, ano, km, cor, placa).
- **Autenticação:** Bearer token obtido via Lambda AWS e cacheado em memória (`MobiautoService._token_cache`)
- **Implementação:** `services/mobiauto_service.py` → `buscar_estoque(dealer_id, token, page_size)`

---

## Fonte 2: API FIPE Saga

- **Tipo:** REST API interna Saga
- **Tecnologia:** HTTP GET / JSON
- **Local de Acesso:** `{PRECIFICACAO_API_URL}/fipe?placa={placa}`
- **Frequência de Atualização:** Em tempo real (consulta por placa)
- **Descrição:** Dados técnicos completos do veículo pela placa: marca, modelo, versão, carroceria, combustível, valor FIPE, código FIPE e ano do modelo.
- **Autenticação:** Nenhuma (API interna Saga)
- **Implementação:** `services/fipe_service.py` → `consultar_por_placa(placa)` com retry 3x / 60s

---

## Fonte 3: API de Precificação Saga

- **Tipo:** REST API interna Saga
- **Tecnologia:** HTTP GET / JSON
- **Local de Acesso:** `{PRECIFICACAO_API_URL}/carro/compra`
- **Frequência de Atualização:** Em tempo real
- **Descrição:** Calcula a proposta de compra/troca da Saga para um veículo com base em dados FIPE + km + uf + cor. Retorna `Valor_proposta_compra`.
- **Autenticação:** Nenhuma (API interna Saga)
- **Implementação:** `services/pricing_service.py` → `calcular_compra(dados_veiculo)`

---

## Fonte 4: PostgreSQL Saga — Lojas Primeira Mão

- **Tipo:** Banco de dados relacional
- **Tecnologia:** PostgreSQL
- **Local de Acesso:** Configurado via `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` no `.env`
- **Frequência de Atualização:** Estática por sessão (lista cacheada em memória após primeira consulta)
- **Descrição:** Tabela `lojas_ids_mobigestor` com as lojas cadastradas no programa Primeira Mão, incluindo `loja_nome`, `dealerid` (código SVM Mobiauto), `uf` e `agente_nome`.
- **Implementação:** `database/postgres_client.py` → `get_lojas_primeira_mao()`

---

## Fonte 5: lojas_mock.csv — Fallback local de lojas

- **Tipo:** Arquivo CSV local
- **Tecnologia:** pandas / leitura direta
- **Local de Acesso:** `database/lojas_mock.csv`
- **Frequência de Atualização:** Manual (atualizado quando há mudança nas lojas)
- **Descrição:** Cópia das 49 lojas Saga com colunas `vc_empresa` (nome), `nm_codigo_svm` (dealer_id), `vc_uf` e `vc_cidade`. Ativado automaticamente quando o PostgreSQL está indisponível.
- **Implementação:** `database/postgres_client.py` (modo mock ativado quando `USE_MOCK=true` ou banco inacessível)
