# 📊 Introdução à Infraestrutura do Power BI

## Estratégia de Workspaces

Para garantir um ciclo de vida de desenvolvimento (ALM) seguro e organizado, utilizamos uma estratégia de múltiplos workspaces no Power BI Service.

-   **Licenciamento:** Os workspaces deste projeto estão em uma capacidade **[Premium (PPU ou por capacidade) ou Pro]**.

### 1. Workspace de Desenvolvimento (DEV)

-   **Nome:** `[Nome do Projeto] - DEV`
-   **Link:** `[Link para o workspace de DEV]`
-   **Propósito:** Ambiente exclusivo para os desenvolvedores de BI. Aqui, os relatórios e modelos semânticos são publicados pela primeira vez para testes iniciais. As fontes de dados apontam para ambientes de desenvolvimento ou staging.

### 2. Workspace de Homologação (HML/UAT)

-   **Nome:** `[Nome do Projeto] - HML`
-   **Link:** `[Link para o workspace de HML]`
-   **Propósito:** Ambiente para validação dos stakeholders e key users. Após a aprovação em DEV, o conteúdo é promovido para este workspace. As fontes de dados são configuradas para apontar para o ambiente de produção.

### 3. Workspace de Produção (PRD)

-   **Nome:** `[Nome do Projeto] - PRD`
-   **Link:** `[Link para o workspace de PRD]`
-   **Propósito:** Ambiente final, acessado pelos consumidores do relatório através do Aplicativo do Power BI. O conteúdo aqui é estável e validado.