# MCP Primeira Mão Saga

Documentação do servidor **Model Context Protocol (MCP)** do programa **Primeira Mão** do Grupo Saga — integração entre ChatGPT e o estoque de seminovos em tempo real, com widget visual interativo e criação automática de leads.

**Responsável:** João Cunha — joao.clara@gruposaga.com.br

---

## Documentação principal

| Documento | Conteúdo |
|---|---|
| [Visão Geral](01_visao_geral.md) | O que é, o que resolve, fluxos do cliente e do consultor |
| [Arquitetura](02_arquitetura.md) | Componentes, serviços, widget, rotas e deploy |
| [Fluxo de Dados](03_fluxo.md) | Sequência de cada operação com diagramas |
| [Como Testar Localmente](como_testar_localmente.md) | Rodar o servidor e visualizar o widget no navegador |

---

## ML & IA (MCP Server)

| Documento | Conteúdo |
|---|---|
| [Índice ML&IA](ml&ia/index.md) | Stack, stakeholders, acesso ao ambiente |
| [Widget](ml&ia/widget.md) | Arquitetura do iframe, modos compra/venda, bridge, CSS |
| [Fontes de Dados](ml&ia/data/data_source.md) | Lambda, Mobiauto, FIPE, Pricing, PostgreSQL |
| [Integrações](ml&ia/integrations/integration.md) | Diagrama de integrações, bridge widget→tool, detalhes de cada API |
| [Integrações API](ml&ia/integrations/api.md) | Contratos de cada API externa |
| [Workflows n8n](ml&ia/workflows/workflow.md) | Webhooks de notificação (compra e venda) |
| [Exemplo de Fluxo](ml&ia/workflows/example_flow.md) | Walkthrough completo de uma conversa de compra e venda |
| [Regras de Negócio](ml&ia/bussines_rules/rules.md) | Regras de busca, lead, paginação e rendering |
| [Monitoramento](ml&ia/monitoring.md) | Logs, métricas e alertas |
| [Boas Práticas](ml&ia/workflows/best_practices.md) | Guidelines de desenvolvimento |

---

## Infraestrutura

| Documento | Conteúdo |
|---|---|
| [AWS Overview](infra/aws/aws.md) | Catálogo de recursos AWS |
| [Lambda de Estoque](infra/aws/lambda/lambda.md) | Lambda principal + query Athena |
| [API Gateway](infra/aws/api/api.md) | Endpoints expostos |

---

## Tools disponíveis (v3.2.26)

| Tool | Descrição | Widget? |
|---|---|---|
| `buscar_veiculos` | Busca com filtros e exibe carrossel visual | Sim (compra) |
| `registrar_interesse_compra` | Lead de compra via widget | Via widget |
| `avaliar_veiculo` | Proposta FIPE + precificação interna | Não |
| `exibir_formulario_venda` | Formulário de avaliação interativo | Sim (venda) |
| `registrar_interesse_venda` | Lead de venda via widget | Via widget |
| `buscar_veiculo` | Busca textual em 4 fases (ID, placa, modelo) | Não |
| `estoque_total` | Listagem de estoque em texto | Não |
| `listar_lojas` | Lista lojas Primeira Mão | Não |
| `diagnostico_registro` | Teste de CRM (uso interno) | Não |

---

## Stack

- **Python 3.13** + **FastMCP 3.2.2**
- **httpx** (async) para APIs externas
- **Transporte:** stdio (MCP Inspector / local) | SSE (produção / Docker Swarm)
- **Widget:** Vanilla JS + CSS dark (no frameworks externos — CSP restritivo)
- **Deploy:** Docker Swarm + Traefik em `mcp-primeiramao.sagadatadriven.com.br`
