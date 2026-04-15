# Integrações via API

## API: Mobiauto — Estoque

- **Endpoint Base:** `https://open-api.mobiauto.com.br/api/dealer/{dealer_id}/inventory/v1.0`
- **Método de Autenticação:** Bearer Token (obtido via AWS Lambda)
- **Token:** renovado automaticamente no 401 via `MobiautoService.get_token()`
- **Endpoints Utilizados:**
  - `GET /api/dealer/{dealer_id}/inventory/v1.0` — retorna todos os veículos do dealer sem paginação
- **Timeout:** 30s (configurável via `API_TIMEOUT`)
- **Implementação:** `services/mobiauto_service.py`

---

## API: Mobiauto — CRM (Propostas)

- **Endpoint Base:** `https://open-api.mobiauto.com.br/api/proposal/v1.0`
- **Método de Autenticação:** Bearer Token (mesmo do estoque)
- **Endpoints Utilizados:**
  - `POST /api/proposal/v1.0/{dealer_id}` — cria lead/proposta no CRM Mobiauto
- **Tipos de lead:**
  - `intentionType: "BUY"` — cliente quer comprar veículo da Saga
    - Provider: `id=11, name="Site", origin="Internet"`
  - `intentionType: "SELL"` — cliente quer vender veículo para a Saga
    - Provider: `id=245, name="Primeira Mão - Avaliação", origin="Internet"`
- **groupId:** `948` (fixo para o programa Primeira Mão)
- **Timeout:** 15s
- **Implementação:** `services/mobiauto_proposal_service.py`

---

## API: FIPE Saga

- **Endpoint Base:** `{PRECIFICACAO_API_URL}/fipe`
- **Método de Autenticação:** Nenhum (API interna Saga)
- **Endpoints Utilizados:**
  - `GET /fipe?placa={placa}` — retorna dados técnicos e valor FIPE pela placa
- **Campos retornados:** `marca`, `modelo`, `versao`, `carroceria`, `combustivel`, `valor_fipe`, `codigo_fipe`, `ano_modelo`
- **Timeout:** 60s por tentativa | 3 tentativas | 2s entre tentativas
- **Implementação:** `services/fipe_service.py`

---

## API: Pricing Saga

- **Endpoint Base:** `{PRECIFICACAO_API_URL}/carro/compra`
- **Método de Autenticação:** Nenhum (API interna Saga)
- **Endpoints Utilizados:**
  - `GET /carro/compra?placa=...&valor_fipe=...&km=...&...` — retorna proposta de compra
- **Campo principal da resposta:** `Valor_proposta_compra`
- **Timeout:** 30s
- **Implementação:** `services/pricing_service.py`

---

## API: Token AWS (Mobiauto Auth)

- **Endpoint:** Configurado via variável `URL_AWS_TOKEN`
- **Método:** `GET {URL_AWS_TOKEN}{MOBI_SECRET}`
- **Uso:** Obtém o Bearer token para autenticar nas APIs Mobiauto (estoque + CRM)
- **Cache:** Token armazenado em memória por sessão; renovado automaticamente no 401

---

## Webhooks n8n (saída)

| Webhook | URL | Acionado por | Payload principal |
|---|---|---|---|
| **Compra** | `.../webhook/cliente_quer_comprar` | `_criar_lead_compra` | lead_id, nome, telefone, veículo, loja, dealer_id |
| **Venda** | `.../webhook/cliente_quer_vender` | `_criar_lead_venda` | lead_id, nome, telefone, placa, km, proposta, uf, dealer_id |

- **Timeout:** 10s
- **Comportamento:** POST aguardado antes de retornar ao LLM; falha no webhook não bloqueia o retorno do lead
- **Implementação:** `_disparar_webhook()` em `main.py`
