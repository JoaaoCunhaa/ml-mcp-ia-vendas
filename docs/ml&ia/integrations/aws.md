# Integrações com AWS

Esta seção documenta como os workflows do n8n interagem com os serviços da AWS.

## Autenticação

A autenticação com a AWS é feita utilizando [Ex: IAM Role associada à instância do n8n, Credenciais IAM]. As credenciais estão salvas no n8n sob o nome `[Nome da Credencial AWS]`.

## Serviços Utilizados

### S3

- **Propósito:** [Ex: Armazenar datasets brutos e processados].
- **Buckets:**
  - `[nome-do-bucket-raw]`: Armazena os dados brutos.
  - `[nome-do-bucket-processed]`: Armazena os dados após o tratamento.
- **Permissões Necessárias:** `s3:GetObject`, `s3:PutObject`.

### Lambda

- **Propósito:** [Ex: Executar modelos de inferência ou scripts complexos].
- **Funções Invocadas:**
  - `[nome-da-funcao-lambda]`: [Descrição do que a função faz].
- **Permissões Necessárias:** `lambda:InvokeFunction`.

### Step Functions

- **Propósito:** [Ex: Orquestrar processos mais complexos que envolvem múltiplos serviços AWS].
- **State Machines Invocadas:**
  - `[arn-da-state-machine]`: [Descrição do que a máquina de estados faz].
- **Permissões Necessárias:** `states:StartExecution`.