# Visão Geral das Integrações

## Diagrama de Integrações

```mermaid
graph TD
    subgraph "LLMs / Clientes"
        CLAUDE["Claude / ChatGPT App"]
        INSP["MCP Inspector"]
    end

    subgraph "MCP Server (Python)"
        MCP["main.py\n4 tools + funções internas de lead"]
        PROP["MobiautoProposalService\n(CRM)"]
        AGG["InventoryAggregator\n(estoque + cache)"]
        FIPE_S["FipeService\n(retry 3x)"]
        PRICE_S["PricingService"]
        MOBI_S["MobiautoService\n(token + estoque)"]
        DB["postgres_client\n(lojas)"]
    end

    subgraph "APIs Externas"
        MOBI_INV["Mobiauto\nEstoque"]
        MOBI_CRM["Mobiauto\nCRM Propostas"]
        TOKEN["AWS Token\n(auth Mobiauto)"]
        FIPE_API["API FIPE\n(Saga)"]
        PRICE_API["API Pricing\n(Saga)"]
    end

    subgraph "Automação Interna"
        N8N_C["n8n Webhook\ncliente_quer_comprar"]
        N8N_V["n8n Webhook\ncliente_quer_vender"]
    end

    subgraph "Dados Locais"
        PG[("PostgreSQL\nlojas Saga")]
        CSV["lojas_mock.csv\n(fallback)"]
    end

    CLAUDE <-->|SSE / stdio| MCP
    INSP <-->|stdio| MCP

    MCP --> PROP
    MCP --> AGG
    MCP --> FIPE_S
    MCP --> PRICE_S

    PROP --> MOBI_CRM
    PROP --> N8N_C
    PROP --> N8N_V

    AGG --> MOBI_S
    AGG --> DB

    MOBI_S --> TOKEN
    MOBI_S --> MOBI_INV

    FIPE_S --> FIPE_API
    PRICE_S --> PRICE_API

    DB --> PG
    DB --> CSV
```

## Resumo das Integrações

| Sistema | Tipo | Direção | Propósito |
|---|---|---|---|
| Mobiauto Inventory API | REST GET | Entrada | Buscar estoque de veículos por dealer |
| Mobiauto CRM Proposal API | REST POST | Saída | Criar leads de compra (BUY) e venda (SELL) |
| AWS Token (Mobiauto Auth) | REST GET | Entrada | Obter Bearer token para autenticação Mobiauto |
| API FIPE Saga | REST GET | Entrada | Dados técnicos e valor FIPE pela placa |
| API Pricing Saga | REST GET | Entrada | Proposta de compra/troca baseada em FIPE + km |
| n8n Webhook Compra | HTTP POST | Saída | Notificar consultores quando lead de compra é criado |
| n8n Webhook Venda | HTTP POST | Saída | Notificar consultores quando lead de venda é criado |
| PostgreSQL Saga | SQL | Entrada | Lista de lojas com dealer_id para o programa Primeira Mão |
| lojas_mock.csv | Arquivo local | Entrada (fallback) | Cópia local das 49 lojas — ativada quando banco indisponível |
