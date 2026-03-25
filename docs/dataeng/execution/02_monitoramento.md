# 🏃 Monitoramento e Alertas

## Estratégia de Monitoramento

-   **Logs:** Todos os jobs e funções geram logs estruturados em JSON e os enviam para o **AWS CloudWatch Logs**.


## Alertas

-   **Ferramenta:** AWS CloudWatch Alarms + Amazon SNS
-   **Destinatário:** As notificações são enviadas para o canal `#alerta-dataeng` no Slack.

### Alertas Configurados

1.  **Falha em Pipeline (Step Functions):**
    -   **Métrica:** `ExecutionsFailed`
    -   **Condição:** Se o número de execuções falhas for `>= 1` em 5 minutos.
    -   **Ação:** Envia notificação via SNS.
2.  **Job do Glue com Longa Duração:**
    -   **Métrica:** `glue.driver.aggregate.elapsedTime`
    -   **Condição:** Se a duração de um job exceder `[45]` minutos.
    -   **Ação:** Envia notificação via SNS.