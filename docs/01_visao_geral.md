# Visão Geral: MCP Primeira Mão Saga

Servidor **Model Context Protocol (MCP)** especializado no ecossistema de seminovos do programa **Primeira Mão** do **Grupo Saga**. Atua como ponte entre modelos de LLM (Claude, ChatGPT) e o estoque real das lojas, permitindo interação por linguagem natural.

---

## Objetivos

1. **Interação natural com o estoque**: o cliente conversa com a IA para buscar veículos por qualquer critério — modelo, cor, ano, preço, placa, loja — sem precisar usar filtros de site.
2. **Avaliação de troca em tempo real**: proposta automática de compra/troca com dados FIPE consultados pela placa, sem perguntas desnecessárias ao cliente.
3. **Renderização visual rica**: cada veículo retornado inclui imagem, preço formatado e link para o livro de ofertas, para que o LLM monte cards visuais diretamente no chat.

---

## Escopo

- **4 tools ativas**: `listar_lojas`, `estoque_total`, `buscar_veiculo`, `avaliar_veiculo`
- **Busca em linguagem natural**: a tool `buscar_veiculo` interpreta qualquer consulta ("quero um corolla branco 2019") via extração de palavras-chave e busca em 4 fases progressivas
- **Estoque paginado**: `estoque_total` busca 3 lojas por vez em paralelo, com avanço automático de página
- **Avaliação automatizada**: `avaliar_veiculo` só pede placa e km — versão, carroceria, combustível e valor FIPE vêm automaticamente da API
- **Resiliência**: FIPE com retry automático (3 tentativas, 60s de timeout cada); lojas e token Mobiauto cacheados em memória
- **Fallback de lojas**: PostgreSQL Saga como fonte primária; CSV local (`lojas_mock.csv`) como fallback

---

## Público-Alvo

| Perfil | Como usa |
|---|---|
| **Cliente final** | Busca veículos via ChatGPT App ou Claude em linguagem natural |
| **Consultor de vendas** | Usa o MCP para encontrar rapidamente opções que batem com o perfil do lead |
| **Equipe técnica** | Mantém a integração Mobiauto → FIPE → Pricing e evolui as tools |

---

## O que está fora do escopo

- Finalização de venda ou financiamento (o MCP redireciona para o site Primeira Mão)
- Histórico de negociações ou CRM
- Gestão de estoque (somente leitura)
