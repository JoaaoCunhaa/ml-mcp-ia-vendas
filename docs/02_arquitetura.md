# Arquitetura — MCP Primeira Mão Saga

---

## Camadas

```
┌─────────────────────────────────────────────────────────────┐
│  Cliente                                                    │
│  ChatGPT App (iframe widget) / MCP Inspector / Claude       │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSE / stdio
┌──────────────────────────▼──────────────────────────────────┐
│  MCP Server  (FastMCP 3.2.2 · Python 3.13 · porta 8000)    │
│                                                             │
│  Resources MCP                  Tools MCP                   │
│  ├── ui://vehicle-offers        ├── buscar_veiculos          │
│  └── ui://vehicle-sell          ├── registrar_interesse_*    │
│                                 ├── avaliar_veiculo          │
│  HTTP Routes                    ├── exibir_formulario_venda  │
│  ├── /api/ofertas               ├── buscar_veiculo           │
│  ├── /ui/vehicle-offers.*       ├── estoque_total            │
│  ├── /local/test                ├── listar_lojas             │
│  ├── /local/ofertas             └── diagnostico_registro     │
│  ├── /local/formulario-venda                                 │
│  ├── /local/registrar-compra                                 │
│  └── /local/registrar-venda                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼────────────────────┐
        ▼                  ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐
│ Lambda AWS    │  │ Mobiauto      │  │ APIs Saga           │
│ → Athena      │  │ Estoque + CRM │  │ FIPE + Pricing      │
└───────────────┘  └───────────────┘  └─────────────────────┘
        ▼                  ▼
┌───────────────┐  ┌───────────────┐
│ n8n Webhooks  │  │ PostgreSQL    │
│ (notificações)│  │ (lojas mock)  │
└───────────────┘  └───────────────┘
```

---

## Componentes principais

### `main.py` (1.664 linhas)

Arquivo central do servidor. Contém:

- **Configuração de AppConfig**: associa tools a recursos MCP para o ChatGPT Apps
- **Rotas HTTP**: endpoints REST (`/api/`, `/local/`, `/ui/`, `/debug/`)
- **Resources MCP**: `ui://vehicle-offers` (compra) e `ui://vehicle-sell` (venda)
- **9 tools MCP**: ver seção Tools
- **Funções internas**: criação de lead, formatação de card, scoring de busca, webhook
- **Meta-patching**: remove metadados do framework `fastmcp` dos descritores de tools/resources

### `services/`

| Arquivo | Propósito |
|---|---|
| `lambda_inventory_service.py` | Fonte primária de estoque via AWS Lambda + Athena |
| `inventory_aggregator.py` | Estoque Mobiauto (fallback) + busca paginada por lojas |
| `fipe_service.py` | Consulta FIPE por placa com retry (3×, 60s timeout) |
| `pricing_service.py` | Calcula proposta de compra via API interna |
| `mobiauto_service.py` | Token Mobiauto com cache + consulta de estoque por dealer |
| `mobiauto_proposal_service.py` | Criação de leads no CRM Mobiauto (BUY e SELL) |

### `database/postgres_client.py`

Carrega lista de lojas. Em produção usa PostgreSQL; atualmente usa `lojas_mock.csv` como fonte padrão.

### `ui/`

| Arquivo | Propósito |
|---|---|
| `vehicle-offers.html` | Shell HTML do widget (placeholder, usado em testes estáticos) |
| `vehicle-offers.css` | Estilos do widget (design system dark, Tailwind-inspired) |
| `vehicle-offers.js` | Lógica do widget: carrossel de compra + formulário de venda |
| `test_widget.html` | Página de teste local (acessada via `/local/test`) |

---

## Widget ChatGPT Apps

### Arquitetura do widget

O ChatGPT Apps renderiza recursos MCP em iframes. O servidor mantém **dois recursos separados** para evitar race conditions entre sessões concorrentes:

| Recurso MCP | Tool associada | Payload armazenado |
|---|---|---|
| `ui://vehicle-offers` | `buscar_veiculos` | `_LAST_BUY_PAYLOAD` |
| `ui://vehicle-sell` | `exibir_formulario_venda` | `_LAST_SELL_PAYLOAD` |

### Como o widget recebe dados

1. **`toolOutput` (preferencial)**: O ChatGPT injeta `window.openai.toolOutput` com o `structured_content` da tool call mais recente. O JS polling detecta mudança de referência a cada 300ms e re-renderiza.

2. **`#vehicle-data` embutido (fallback)**: O HTML do recurso embute o payload em `<script type="application/json" id="vehicle-data">`. Usado quando `toolOutput` ainda não está disponível.

A prioridade é sempre `toolOutput` — garante que uma nova pesquisa substitua dados em cache do HTML do recurso.

### Bridge widget → tool (registro de interesse)

Quando o cliente clica em "Confirmar interesse" no carrossel, o widget chama a tool MCP diretamente:

```javascript
window.openai.callTool("registrar_interesse_compra", { ... })
```

O ChatGPT executa a tool no servidor e o resultado é exibido ao cliente. O mesmo padrão é usado para `registrar_interesse_venda` no formulário de venda.

### UX do formulário de interesse (carrossel de compra)

Clicar em "Tenho interesse" em **qualquer card** abre o formulário de contato em **todos os cards simultaneamente**. O cliente escolhe em qual card enviar. Cada card envia o lead individualmente com os dados do veículo correspondente.

---

## Tools MCP

### `buscar_veiculos`
- **Fonte**: `LambdaInventoryService.buscar()` (primária) → Mobiauto (fallback)
- **Filtros**: cidade (obrigatório), marca, modelo, versão, preço mínimo/máximo, KM máximo, ano mínimo/máximo
- **Saída**: `structured_content` com `type: "vehicle_cards"` + lista de veículos + contexto de busca
- **App**: `_APP_COMPRA` → abre widget `ui://vehicle-offers`

### `registrar_interesse_compra`
- **Chamada por**: widget via `window.openai.callTool` (não pelo LLM diretamente)
- **Ações**: cria lead BUY no Mobiauto + dispara webhook `cliente_quer_comprar` no n8n
- **Retorna**: `registrado: true/false`, `dealer_id`, `fallback_url`

### `avaliar_veiculo`
- **Etapa 1**: `FipeService.consultar_por_placa()` — obtém marca, modelo, versão, valor FIPE
- **Etapa 2**: `PricingService.calcular_compra()` — calcula proposta com KM, UF, cor, existe zero km
- **Saída**: Markdown com dados do veículo + proposta. Deve chamar `exibir_formulario_venda()` imediatamente após.

### `exibir_formulario_venda`
- **App**: `_APP_VENDA` → abre widget `ui://vehicle-sell` em modo formulário
- **Saída**: `structured_content` com `mode: "sell"` + dados da avaliação

### `registrar_interesse_venda`
- **Chamada por**: widget via `window.openai.callTool`
- **Ações**: cria lead SELL no Mobiauto + dispara webhook `cliente_quer_venda` no n8n

### `buscar_veiculo`
- Busca textual em 4 fases progressivas:
  1. Busca por ID/placa exata
  2. AND (todas as palavras-chave)
  3. OR com scoring
  4. Sugestões de fallback
- Saída: Markdown com cards

### `estoque_total`, `listar_lojas`, `diagnostico_registro`
- Funções auxiliares; sem widget; saída em Markdown ou JSON

---

## Fluxo de resolução de dealer_id

Para criar um lead no CRM Mobiauto, é necessário um `dealer_id`. A resolução segue a hierarquia:

1. Nome da loja → lookup na lista de lojas
2. UF do veículo → primeira loja do estado
3. Primeira loja da lista (fallback final)

---

## Rotas HTTP expostas

| Rota | Método | Propósito |
|---|---|---|
| `/sse` | GET | Endpoint MCP principal (SSE transport) |
| `/api/ofertas` | GET | JSON de veículos (usado pelo widget em produção) |
| `/ui/vehicle-offers.html` | GET | Shell HTML estático |
| `/ui/vehicle-offers.css` | GET | CSS do widget |
| `/ui/vehicle-offers.js` | GET | JS do widget |
| `/static/vehicle-offers.css` | GET | CSS (alias para produção) |
| `/static/vehicle-offers.js` | GET | JS (alias para produção) |
| `/local/test` | GET | Página de teste visual (localhost only) |
| `/local/ofertas` | GET | JSON de veículos (localhost only) |
| `/local/formulario-venda` | GET | JSON do formulário de venda (localhost only) |
| `/local/registrar-compra` | POST | Teste de criação de lead compra (localhost only) |
| `/local/registrar-venda` | POST | Teste de criação de lead venda (localhost only) |
| `/debug/inspect` | GET | Metadados de diagnóstico do servidor |
| `/.well-known/openai-apps-challenge` | GET | Verificação de domínio OpenAI |

---

## Cache em memória

| Dado | Onde | Duração |
|---|---|---|
| Token Mobiauto (estoque) | `mobiauto_service._token_cache` | Até 401 |
| Token Mobiauto (CRM) | `mobiauto_proposal_service._token_cache` | Até 401 |
| Lista de lojas | `inventory_aggregator._lojas_cache` | Sessão |
| Último payload de compra | `main._LAST_BUY_PAYLOAD` | Sessão |
| Último payload de venda | `main._LAST_SELL_PAYLOAD` | Sessão |

---

## Configuração de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `MCP_TRANSPORT` | Sim | `sse` (HTTP) ou `stdio` (MCP Inspector) |
| `PORT` | Não (padrão 8000) | Porta HTTP |
| `DB_HOST/NAME/USER/PASSWORD/PORT` | Sim | PostgreSQL |
| `MOBI_SECRET` | Sim | Secret para token Mobiauto |
| `URL_AWS_TOKEN` | Sim | Endpoint AWS para token |
| `PRECIFICACAO_API_URL` | Sim | URL da API de precificação |
| `LAMBDA_ESTOQUE_URL` | Sim | URL da Lambda de estoque |
| `LAMBDA_API_KEY` | Sim | Chave de autenticação da Lambda |
| `OPENAI_CHALLENGE_TOKEN` | Sim | Token de verificação de domínio OpenAI |
| `API_TIMEOUT` | Não (padrão 30s) | Timeout geral de APIs |

---

## Deploy (produção)

- **Orquestrador**: Docker Swarm
- **Imagem**: `mcp-primeira-mao:v3.2.26`
- **Nó**: `maiamanager`
- **Reverse proxy**: Traefik com TLS automático
- **Domínio**: `mcp-primeiramao.sagadatadriven.com.br`
- **SSE buffering**: desabilitado via header `X-Accel-Buffering: no` (obrigatório para SSE funcionar através do Traefik)

---

## Estrutura de arquivos

```
mcp_primeira_mao/
├── main.py                          # Servidor MCP principal
├── config.py                        # Carregamento de variáveis de ambiente
├── docker-compose.yml               # Deploy em Swarm
├── Dockerfile                       # Imagem do container
├── requirements.txt                 # Dependências Python
├── database/
│   └── postgres_client.py           # Client PostgreSQL + fallback CSV
├── services/
│   ├── lambda_inventory_service.py  # Fonte primária: Lambda AWS
│   ├── inventory_aggregator.py      # Fonte secundária: Mobiauto estoque
│   ├── fipe_service.py              # Consulta FIPE por placa
│   ├── pricing_service.py           # Cálculo de proposta de compra
│   ├── mobiauto_service.py          # Token + estoque Mobiauto
│   └── mobiauto_proposal_service.py # Criação de leads no CRM
├── ui/
│   ├── vehicle-offers.html          # Shell HTML (testes estáticos)
│   ├── vehicle-offers.css           # Estilos do widget
│   ├── vehicle-offers.js            # Lógica do widget
│   └── test_widget.html             # Página de teste local
└── utils/
    └── helpers.py                   # normalizar_placa, formatar_moeda, etc.
```
