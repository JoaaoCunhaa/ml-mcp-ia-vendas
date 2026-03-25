# Exemplo de Fluxo: Processamento de Leads

Este documento descreve um exemplo de workflow padrão para ilustrar a aplicação das nossas boas práticas.

## Objetivo do Fluxo

O workflow `EXEMPLO_PROCESSA_LEADS` é acionado por um webhook, recebe dados de um novo lead, enriquece esses dados com uma API externa e os armazena em um bucket S3.

## Estrutura do Workflow

1.  **Webhook (Trigger):**
    - `Nome do Nó`: "Recebe Novo Lead via Webhook"
    - `Descrição`: Ponto de entrada para novos leads.

2.  **Set:**
    - `Nome do Nó`: "Define Variaveis Iniciais"
    - `Descrição`: Extrai e formata os dados de entrada para uso nos passos seguintes.

3.  **HTTP Request:**
    - `Nome do Nó`: "Enriquece Dados do Lead com API Externa"
    - `Descrição`: Faz uma chamada GET para a API `[Nome da API]` para obter informações adicionais.
    - `Credencial Usada`: `API_EXTERNA_CREDENTIALS`

4.  **IF:**
    - `Nome do Nó`: "Verifica se Lead foi Enriquecido"
    - `Descrição`: Valida se a chamada à API retornou dados válidos.

5.  **AWS S3:**
    - `Nome do Nó`: "Salva Lead Enriquecido no S3"
    - `Descrição`: Conecta ao S3 e salva o objeto JSON final no bucket `[nome-do-bucket]/leads`.
    - `Credencial Usada`: `AWS_CREDENTIALS`

## Tratamento de Erro

- Um nó `Error Trigger` está configurado para capturar qualquer falha no fluxo.
- Em caso de erro, um nó do Slack envia uma mensagem para o canal `#alerta-leads` com os detalhes da falha.

## JSON do Workflow (Opcional)

Você pode exportar o JSON do workflow e colá-lo aqui para facilitar a importação por outros desenvolvedores.

```json
{
  "name": "EXEMPLO_PROCESSA_LEADS",
  "nodes": [
    // ... Conteúdo JSON do workflow ...
  ],
  "connections": {
    // ... Conteúdo JSON das conexões ...
  }
}
```