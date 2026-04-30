# MCP Primeira Mão Saga — ML & IA

## Visão Geral do Projeto

O **MCP Primeira Mão Saga** é um servidor **Model Context Protocol (MCP)** que integra o ChatGPT ao ecossistema de seminovos do Grupo Saga. A solução resolve dois problemas centrais:

1. **Busca visual de estoque** — o cliente conversa em linguagem natural e recebe um carrossel interativo com fotos, preços e botão de interesse, diretamente no chat.
2. **Qualificação e registro automático de leads** — quando o cliente confirma interesse (compra ou venda), o lead é registrado no CRM Mobiauto e o consultor é notificado pelo n8n automaticamente.

---

## Stakeholders

| Nome | Área | Papel |
|---|---|---|
| João Cunha | Data & IA | Tech Lead / Desenvolvedor |
| Equipe Primeira Mão | Vendas Seminovos | Product Owner |
| Consultores Saga | Vendas | Receptores dos leads gerados |

---

## Tecnologias

| Categoria | Tecnologia |
|---|---|
| Protocolo | Model Context Protocol (MCP) via FastMCP 3.2.2 |
| Linguagem | Python 3.13 |
| HTTP | httpx (async) |
| Transporte | stdio (local) e SSE (produção) |
| Widget | Vanilla JS + CSS (sem frameworks externos — CSP restritivo) |
| Automação | n8n (webhooks de notificação) |
| CRM | Mobiauto Open API |
| Estoque | Lambda AWS → Athena (`modelled.pm_*`) |
| Pricing | API interna Saga (FIPE + proposta de compra) |
| Banco de dados | PostgreSQL Saga + CSV fallback |

---

## Acesso ao ambiente

| Ambiente | Como acessar |
|---|---|
| **Local (teste visual)** | `$env:MCP_TRANSPORT = "sse"; python main.py` → `http://localhost:8000/local/test` |
| **Local (MCP Inspector)** | `npx @modelcontextprotocol/inspector python main.py` |
| **Produção (ChatGPT)** | Configurado no ChatGPT Apps via SSE `https://mcp-primeiramao.sagadatadriven.com.br/sse` |

Ver [Como Testar Localmente](../../como_testar_localmente.md) para guia completo.

---

## Documentação desta seção

| Documento | Conteúdo |
|---|---|
| [Widget](widget.md) | Arquitetura do iframe, modos, bridge, CSS |
| [Fontes de Dados](data/data_source.md) | Lambda, Mobiauto, FIPE, Pricing, PostgreSQL |
| [Integrações](integrations/integration.md) | Diagrama e detalhes de cada API |
| [Workflows n8n](workflows/workflow.md) | Webhooks de notificação |
| [Exemplo de Fluxo](workflows/example_flow.md) | Walkthrough completo |
| [Regras de Negócio](bussines_rules/rules.md) | Regras de busca, lead e rendering |
| [Monitoramento](monitoring.md) | Logs, métricas e alertas |
| [Boas Práticas](workflows/best_practices.md) | Guidelines de desenvolvimento |

---

!!! warning "Credenciais"
    Todos os segredos (token Mobiauto, chave Lambda, URL de precificação) são carregados via `.env` e nunca devem ser expostos no código ou versionados.
