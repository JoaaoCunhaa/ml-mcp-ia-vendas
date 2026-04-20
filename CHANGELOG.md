# Changelog

## [Não lançado]

### 2026-04-20

#### Alterado
- `estoque_total`, `buscar_veiculo` e `avaliar_veiculo` passaram a retornar string pura em vez de dict JSON — evita que o LLM reformate o conteúdo ao exibir para o cliente
- Removidos parâmetros de lead embutidos (`nome_cliente`, `telefone_cliente`, etc.) de `estoque_total` e `buscar_veiculo` — responsabilidade delegada para as tools explícitas abaixo
- Removidas constantes `_PROXIMA_ACAO_COMPRA` e `_PROXIMA_ACAO_VENDA` dos retornos (instruções mantidas nos docstrings)
- Nomes de lojas normalizados: "SN X" → "Primeira Mão X"
- CTA após cards atualizado: consultor como opção principal com menção explícita a contato via **WhatsApp**
- Mensagem de sucesso do lead atualizada: "Um consultor da Saga entrará em contato com você em breve via WhatsApp"
- Docstrings de todas as tools com instrução imperativa: `CHAME ESTA FERRAMENTA IMEDIATAMENTE` quando cliente fornecer nome e telefone
- Logs de entrada das tools `registrar_interesse_compra` e `registrar_interesse_venda` elevados para `WARNING` com prefixo `>>> TOOL CHAMADA` para facilitar diagnóstico em prod
- Logs do webhook com prefixo `>>> DISPARANDO` / `<<< OK` / `<<< FALHOU` para rastreabilidade

#### Adicionado
- Tool `registrar_interesse_compra`: registra lead de compra no CRM e dispara webhook n8n
- Tool `registrar_interesse_venda`: registra lead de venda no CRM e dispara webhook n8n
- Método `InventoryAggregator.buscar_estoque_por_lojas(lojas, limit=25)`: busca estoque de lista específica de lojas filtrando veículos sem imagem
- Filtro por cidade em `estoque_total` e `buscar_veiculo` via `_filtrar_lojas_por_cidade`

#### Corrigido
- `estoque_total` não aceita mais parâmetro `pagina` — substituído por `cidade`
- Veículos sem imagem excluídos de todos os retornos de estoque
