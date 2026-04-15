# MCP Primeira Mão Saga

Documentação técnica do servidor **Model Context Protocol (MCP)** do programa **Primeira Mão** do Grupo Saga — integração entre LLMs e o estoque de seminovos em tempo real.

**Responsável:** João Cunha

---

## Navegação

| Documento | Conteúdo |
|---|---|
| [Visão Geral](01_visao_geral.md) | Objetivos, escopo e público-alvo |
| [Arquitetura](02_arquitetura.md) | Componentes, serviços e diagrama |
| [Fluxo de Dados](03_fluxo.md) | Ciclo de vida de uma requisição e criação de leads |

---

## Tools disponíveis (v atual)

| Tool | Parâmetros obrigatórios | Parâmetros de lead (opcionais) | Descrição |
|---|---|---|---|
| `listar_lojas` | — | — | Lista todas as lojas Primeira Mão com cidade e UF |
| `estoque_total` | `pagina` (padrão 1) | `nome_cliente`, `telefone_cliente` + dados do veículo | Estoque paginado — 3 lojas por vez. Quando cliente e veículo informados, cria lead de compra automaticamente |
| `buscar_veiculo` | `consulta` (texto livre) | `nome_cliente`, `telefone_cliente` + dados do veículo | Busca curinga em 4 fases. Quando cliente e veículo informados, cria lead de compra automaticamente |
| `avaliar_veiculo` | `placa`, `km` | `nome_cliente`, `telefone_cliente` | Proposta de compra/troca via FIPE + Pricing. Quando cliente informado, cria lead de venda automaticamente |

> **Lead automático**: o LLM **não** chama nenhuma ferramenta separada para criar leads.
> Basta re-chamar a mesma tool com `nome_cliente` + `telefone_cliente`.
> A criação de lead no CRM Mobiauto e o disparo do webhook interno acontecem dentro da própria tool.

---

## Funções internas (não expostas como tools)

| Função | Tipo de lead | Acionada por |
|---|---|---|
| `_criar_lead_compra` | BUY — cliente quer comprar | `estoque_total`, `buscar_veiculo` |
| `_criar_lead_venda` | SELL — cliente quer vender | `avaliar_veiculo` |
| `_disparar_webhook` | POST para n8n | `_criar_lead_compra`, `_criar_lead_venda` |

---

## Stack

- **Python 3.13** + **FastMCP**
- **httpx** (async) para chamadas às APIs externas
- **asyncio.gather** para busca paralela em todas as lojas
- Transporte: **stdio** (MCP Inspector / local) e **SSE** (produção / Docker)
