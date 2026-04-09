# MCP Primeira Mão Saga

Documentação técnica do servidor **Model Context Protocol (MCP)** do programa **Primeira Mão** do Grupo Saga — integração entre LLMs e o estoque de seminovos em tempo real.

**Responsável:** João Cunha

---

## Navegação

| Documento | Conteúdo |
|---|---|
| [Visão Geral](01_visao_geral.md) | Objetivos, escopo e público-alvo |
| [Arquitetura](02_arquitetura.md) | Componentes, serviços e diagrama |
| [Fluxo de Dados](03_fluxo.md) | Ciclo de vida de uma requisição |

---

## Tools disponíveis (v atual)

| Tool | Parâmetros | Descrição |
|---|---|---|
| `listar_lojas` | — | Lista todas as lojas Primeira Mão com cidade e UF |
| `estoque_total` | `pagina` (opcional) | Estoque paginado — 3 lojas por vez, com "ver mais" |
| `buscar_veiculo` | `consulta` (texto livre) | Busca curinga por qualquer termo: placa, ID, cor, modelo, ano, loja |
| `avaliar_veiculo` | `placa`, `km` | Proposta de compra/troca via FIPE + API de precificação Saga |

---

## Stack

- **Python 3.13** + **FastMCP**
- **httpx** (async) para chamadas às APIs externas
- **asyncio.gather** para busca paralela em todas as lojas
- Transporte: **stdio** (MCP Inspector / local) e **SSE** (produção / Docker)
