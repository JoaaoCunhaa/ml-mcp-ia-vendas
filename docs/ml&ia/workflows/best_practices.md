# Boas Práticas — MCP Primeira Mão Saga

## 1. Tools MCP

- **Nunca expor funções internas como tools.** Funções de lead (`_criar_lead_compra`, `_criar_lead_venda`) são internas e não devem ser decoradas com `@mcp.tool`. O LLM re-chama a mesma tool com os parâmetros de lead — não chama uma tool separada.
- **Parâmetros de lead são opcionais.** Tools como `buscar_veiculo` e `estoque_total` funcionam normalmente sem eles — a criação de lead é acionada apenas quando `nome_cliente` + `telefone_cliente` estão presentes.
- **docstrings são instruções para o LLM.** Mantenha-as claras, curtas e orientadas ao comportamento esperado (quando chamar, o que passar, o que exibir).

## 2. Renderização de conteúdo

- **Pré-renderize Markdown no servidor.** Cards de veículos e propostas de avaliação devem ser gerados em Python e entregues prontos nos campos `cards_markdown` e `proposta_markdown`. O LLM não deve montar templates ou inferir formatação.
- **Nunca exiba o bloco `_meta`.** Esse campo é para uso interno (logging, debug) e não deve aparecer na resposta ao cliente.
- **Fallback sempre presente.** Toda tool retorna uma mensagem útil mesmo quando o resultado é vazio (estoque indisponível, veículo não encontrado, lead com falha).

## 3. APIs e resiliência

- **Timeouts configurados por serviço:**
  - FIPE: 60s por tentativa, 3 retries, 2s entre tentativas
  - Mobiauto estoque e CRM: 30s e 15s respectivamente
  - Webhook n8n: 10s
- **Token Mobiauto:** Cacheado em memória; renovado automaticamente no 401. Nunca hard-code token no código.
- **Lista de lojas:** Cacheada por sessão. Para forçar recarga, reiniciar o servidor.
- **Webhook não bloqueia lead.** Falha no POST do webhook é logada como warning, mas não impede o retorno do lead ao LLM.

## 4. Logs

- Formato: `[NomeServico.metodo]` no início de cada linha de log
- Logs de início e conclusão em toda operação relevante (`Iniciando`, `Concluído`)
- Campos obrigatórios no log de lead: `success`, `dealer_id`, `cliente`, `tel`
- Erros logados com `logger.error` / `logger.exception`; avisos com `logger.warning`

## 5. Testes

- **`test_tools.py`**: suite completa — executa todas as tools, funções internas e webhooks
- **`test_lead.py`**: testes focados na API Mobiauto CRM e webhooks n8n
- Rode os testes após qualquer alteração nas tools ou nos serviços de lead
- Testes de lead **criam registros reais** no CRM Mobiauto — use dados claramente identificados como teste (ex: `"Teste Automatico T01"`, email `@sagadatadriven.com.br`)

## 6. Segredos e variáveis de ambiente

- Todos os segredos em `.env` (não versionado)
- Variáveis obrigatórias: `MOBI_SECRET`, `URL_AWS_TOKEN`, `PRECIFICACAO_API_URL`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- Variáveis opcionais: `MCP_TRANSPORT` (padrão: `stdio`), `PORT` (padrão: 8000), `API_TIMEOUT` (padrão: 30), `FIPE_TIMEOUT` (padrão: 60)
