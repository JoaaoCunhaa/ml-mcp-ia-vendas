# ➡️ Fontes e Destinos de Dados

## Fontes de Dados

Esta seção detalha de onde os dados são extraídos.

### Fonte 1: [Nome da Fonte, ex: API de Vendas]

-   **Sistema de Origem:** [Ex: Salesforce, API interna]
-   **Método de Extração:** [Ex: Requisição GET em API REST, Leitura de arquivo via SFTP]
-   **Frequência de Extração:** [Ex: Diária, a cada 1 hora, em tempo real via streaming]
-   **Entidades/Tabelas Extraídas:** `Vendas`, `Clientes`, `Produtos`.
-   **Contato Responsável:** [Nome ou equipe responsável pelo sistema de origem].

### Fonte 2: [Nome da Fonte, ex: Banco de Dados do ERP]

-   **Sistema de Origem:** [Ex: SAP, Oracle EBS]
-   **Método de Extração:** [Ex: Captura de dados via CDC (Change Data Capture), Query direta no banco]
-   **Frequência de Extração:** [Ex: A cada 15 minutos].
-   **Entidades/Tabelas Extraídas:** `Estoque`, `Notas Fiscais`.
-   **Contato Responsável:** [Nome ou equipe].

## Destinos dos Dados

Esta seção detalha para onde os dados processados são entregues.

### Destino 1: Camada Refinada do Data Lake

-   **Tecnologia:** [Ex: AWS S3 + Glue Catalog]
-   **Formato:** [Ex: Parquet]
-   **Propósito:** Servir como a fonte principal para consumo analítico.
-   **Consumidores Principais:** Equipes de Analytics (Power BI) e Ciência de Dados (SageMaker).

### Destino 2: [Nome do Destino, ex: Data Warehouse]

-   **Tecnologia:** [Ex: Amazon Redshift, Snowflake]
-   **Propósito:** [Ex: Servir dashboards de baixa latência para a diretoria].
-   **Consumidores Principais:** [Ex: Executivos, Liderança].