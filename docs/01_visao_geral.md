# Visão Geral: MCP Primeira Mão Saga

Servidor **Model Context Protocol (MCP)** especializado no ecossistema de seminovos do programa **Primeira Mão** do **Grupo Saga**. Atua como ponte entre modelos de LLM (Claude, ChatGPT) e o estoque real das lojas, permitindo interação em linguagem natural e registro automático de leads no CRM.

---

## Objetivos

1. **Interação natural com o estoque**: o cliente conversa com a IA para buscar veículos por qualquer critério — modelo, cor, ano, preço, placa, loja — sem precisar usar filtros de site.
2. **Avaliação de troca em tempo real**: proposta automática de compra/troca com dados FIPE consultados pela placa, sem perguntas desnecessárias ao cliente.
3. **Criação automática de leads no CRM**: quando o cliente confirma interesse, o lead é registrado direto na API Mobiauto CRM sem que o LLM precise chamar uma ferramenta extra — tudo acontece dentro da própria tool.
4. **Notificação interna via webhook**: a cada lead criado, um POST é disparado para o n8n com dados completos do cliente e do veículo, ativando o fluxo de atendimento.
5. **Renderização visual rica**: cada veículo retornado inclui imagem, preço formatado e link para o livro de ofertas em Markdown pré-renderizado.

---

## Escopo

- **4 tools ativas**: `listar_lojas`, `estoque_total`, `buscar_veiculo`, `avaliar_veiculo`
- **Lead de compra embutido**: `estoque_total` e `buscar_veiculo` aceitam `nome_cliente` + `telefone_cliente` e criam o lead internamente via `_criar_lead_compra`
- **Lead de venda embutido**: `avaliar_veiculo` aceita `nome_cliente` + `telefone_cliente` e cria o lead internamente via `_criar_lead_venda`
- **CRM Mobiauto**: criação de proposta via `POST /api/proposal/v1.0/{dealer_id}` com Bearer token compartilhado
- **Webhooks n8n**: `cliente_quer_comprar` e `cliente_quer_vender` disparados após cada lead criado
- **Busca em linguagem natural**: `buscar_veiculo` interpreta qualquer consulta via extração de palavras-chave e busca em 4 fases progressivas
- **Estoque paginado**: `estoque_total` busca 3 lojas por vez em paralelo, com avanço automático de página vazia
- **Avaliação automatizada**: `avaliar_veiculo` só pede placa e km — versão, carroceria, combustível e valor FIPE vêm automaticamente da API
- **Resiliência**: FIPE com retry automático (3 tentativas, 60s); lojas e token Mobiauto cacheados em memória; fallback de mensagem quando estoque vazio

---

## Público-Alvo

| Perfil | Como usa |
|---|---|
| **Cliente final** | Busca veículos via ChatGPT App ou Claude em linguagem natural; recebe proposta e confirma interesse sem sair do chat |
| **Consultor de vendas** | É acionado automaticamente pelo webhook quando um lead é gerado — recebe dados completos do cliente e do veículo |
| **Equipe técnica** | Mantém a integração Mobiauto → FIPE → Pricing → CRM e evolui as tools |

---

## O que está fora do escopo

- Financiamento ou assinatura de contrato (o MCP fornece link para o site Primeira Mão como fallback)
- Histórico de negociações anteriores
- Gestão de estoque (somente leitura via API Mobiauto)
