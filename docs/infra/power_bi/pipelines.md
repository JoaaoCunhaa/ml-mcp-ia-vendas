# 🚀 Pipelines de Implantação (CI/CD)

Para automatizar e padronizar o processo de publicação de relatórios entre os ambientes, utilizamos os **Pipelines de Implantação** do Power BI.

-   **Nome do Pipeline:** `[Pipeline do Projeto Carteira Vendedor]`
-   **Link do Pipeline:** `[Link para o Pipeline no Power BI Service]`

## Estágios do Pipeline

### 1. Desenvolvimento (Development)

-   **Workspace Vinculado:** `[Nome do Projeto] - DEV`
-   **Ações:** Este é o ponto de partida. Desenvolvedores publicam seus arquivos `.pbix` neste workspace.

### 2. Teste (Test)

-   **Workspace Vinculado:** `[Nome do Projeto] - HML`
-   **Ações:**
    -   O conteúdo é **promovido** do estágio de Desenvolvimento para Teste usando o botão "Deploy to test".
    -   **Regras de Implantação:** Durante a promoção, são aplicadas regras para alterar os parâmetros da fonte de dados, fazendo com que o modelo semântico aponte para as fontes de produção.
        -   **Parâmetro:** `DatabaseName`
        -   **Valor em DEV:** `db_dev`
        -   **Valor em HML:** `db_prd`

### 3. Produção (Production)

-   **Workspace Vinculado:** `[Nome do Projeto] - PRD`
-   **realese:** 
    1.0 
-   **realese changes:**
    -   1.0 Após a validação bem-sucedida no ambiente de Teste (HML), o conteúdo é **promovido** para a Produção.
    -  1.0 Nenhuma regra adicional é necessária, pois as fontes de dados já foram ajustadas no estágio anterior.
    -  1.0 Após a implantação, o **Aplicativo** é atualizado para que os usuários finais recebam a nova versão.