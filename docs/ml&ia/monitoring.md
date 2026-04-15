# Monitoramento — MCP Primeira Mão Saga

## Estratégia de Monitoramento

O servidor MCP usa **logging estruturado** com prefixos por serviço. Todos os logs são emitidos via `logging.INFO` / `WARNING` / `ERROR` para stdout, capturável pelo Docker ou pelo serviço de hospedagem.

- **Formato de log:** `%(asctime)s [%(levelname)s] %(message)s`
- **Prefixos de serviço:** `[listar_lojas]`, `[estoque_total]`, `[buscar_veiculo]`, `[avaliar_veiculo]`, `[_criar_lead_compra]`, `[_criar_lead_venda]`, `[webhook.nome]`, `[MobiautoService.get_token]`, `[MobiautoService.buscar_estoque]`, `[MobiautoProposalService]`, `[FipeService]`, `[PricingService]`, `[obter_lista_lojas]`, `[buscar_estoque_paginado]`, `[buscar_estoque_consolidado]`

## Métricas-Chave a Observar

| Evento | Nível | O que indica |
|---|---|---|
| `Token obtido e cacheado` | INFO | Autenticação Mobiauto bem-sucedida |
| `401` no buscar_estoque | WARNING | Token expirado — refresh automático em andamento |
| `Timeout` em FipeService | ERROR | API FIPE lenta — retry automático |
| `Erro na loja X` em gather | ERROR | Uma loja retornou exceção — continua com as demais |
| `Lead criado` | INFO | Lead registrado com sucesso no CRM Mobiauto |
| `HTTP 4xx/5xx` em proposal | ERROR | Falha no CRM — retorno com `registrado=false` ao LLM |
| `webhook enviado` | INFO | n8n notificado com sucesso |
| `webhook falha` | ERROR | n8n indisponível — lead criado no CRM, webhook não entregue |
| `Nenhuma loja encontrada` | WARNING | Banco e CSV indisponíveis |

## Alertas Recomendados

- **Falha repetida de token Mobiauto** — verificar `MOBI_SECRET` e `URL_AWS_TOKEN`
- **Timeout FIPE > 3 tentativas** — investigar disponibilidade da API de precificação
- **Webhook indisponível** — verificar instância n8n em `automatemaiawh.sagadatadriven.com.br`
- **`Nenhuma loja encontrada`** — verificar conexão com PostgreSQL ou integridade do `lojas_mock.csv`
- **`HTTP 5xx` no CRM Mobiauto** — verificar status da API `open-api.mobiauto.com.br`

## Testes de Saúde

Para verificar se todos os componentes estão operacionais:

```bash
# A partir do diretório src/python/mcp_primeira_mao/
python test_tools.py   # 38 assertions — todas as tools e funções internas
python test_lead.py    # 4 testes — API Mobiauto CRM + webhooks n8n
```

Resultado esperado: `RESUMO: 38 OK | 0 FALHOU | 38 total`
