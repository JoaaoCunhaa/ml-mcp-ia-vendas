# MCP IA de Vendas — Primeira Mão Saga

## Visão Geral do Projeto

O **MCP Primeira Mão Saga** é um servidor **Model Context Protocol (MCP)** que integra modelos de linguagem (Claude, ChatGPT) ao ecossistema de seminovos do Grupo Saga. A solução resolve dois problemas de negócio centrais:

1. **Busca de estoque em linguagem natural** — o cliente não precisa usar filtros; conversa com a IA e recebe cards visuais com imagem, preço e link direto para o livro de ofertas.
2. **Qualificação e registro automático de leads** — quando o cliente confirma interesse (compra ou venda), o lead é registrado direto no CRM Mobiauto e o consultor responsável é notificado pelo n8n, tudo dentro da mesma chamada de ferramenta.

## Stakeholders

| Nome | Área | Papel no Projeto |
|---|---|---|
| João Cunha | Data & IA | Tech Lead / Desenvolvedor |
| Equipe Primeira Mão | Vendas Seminovos | Product Owner / Usuário final |
| Consultores Saga | Vendas | Receptores dos leads gerados |

## Tecnologias Utilizadas

- **Protocolo:** Model Context Protocol (MCP) via FastMCP
- **Linguagem:** Python 3.13
- **HTTP:** httpx (async) + asyncio.gather para chamadas paralelas
- **Transporte:** stdio (local / MCP Inspector) e SSE (produção / Docker)
- **Automação:** n8n (webhooks de notificação interna)
- **CRM:** Mobiauto Open API
- **Pricing:** API interna Saga (FIPE + proposta de compra)
- **Banco de dados:** PostgreSQL Saga + CSV fallback

## Acesso ao Ambiente

- **Servidor MCP (SSE):** Porta 8000, configurado via `MCP_TRANSPORT=sse` e `PORT=8000`
- **MCP Inspector (local):** `npx @modelcontextprotocol/inspector python main.py`
- **Variáveis de ambiente:** `.env` na raiz do módulo (não versionado)

!!! warning "Credenciais"
    Todos os segredos (token Mobiauto, senha do banco, URL de precificação) são carregados via `.env` e nunca devem ser expostos no código ou versionados.
