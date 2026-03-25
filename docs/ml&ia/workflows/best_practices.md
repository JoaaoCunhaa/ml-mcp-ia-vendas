# Boas Práticas de Desenvolvimento

Para manter a consistência, manutenibilidade e escalabilidade dos nossos workflows, seguimos as seguintes boas práticas:

## 1. Nomenclatura

- **Workflows:** Use nomes claros e objetivos no formato `[PROJETO]_[AÇÃO]_[ENTIDADE]`. Ex: `CARTEIRA_VENDEDOR_PROCESSA_LEADS`.
- **Nós (Nodes):** Renomeie todos os nós com uma descrição da sua função. Em vez de "HTTP Request", use "Busca Dados de Clientes na API".

## 2. Modularização

- Workflows complexos devem ser quebrados em workflows menores e reutilizáveis, utilizando o nó `Execute Workflow`.
- Um workflow não deve ter mais do que `[20-30]` nós (a definir pela equipe).

## 3. Gerenciamento de Erros

- Utilize o nó `Error Trigger` para criar rotinas de tratamento de falhas.
- Sempre inclua um passo final para notificar sobre o erro (ex: via Slack) com informações contextuais (nome do workflow, passo do erro, dados de entrada).

## 4. Credenciais

- **Nunca** use credenciais diretamente nos nós (`hardcode`).
- Sempre utilize o sistema de credenciais nativo do n8n.

## 5. Documentação Interna

- Utilize o nó `Sticky Note` para adicionar comentários e explicações importantes diretamente no canvas do workflow.