# Localizações Principais no S3

Paths (prefixos) importantes dentro dos buckets S3 utilizados pelo projeto.
# Buckets S3

Lista de buckets do Amazon S3 que o projeto utiliza.

| Nome do Bucket | Propósito |
| :--- | :--- |
| `[prefixo-projeto-raw-accountid]` | Camada de dados brutos (Raw) |
| `[prefixo-projeto-trusted-accountid]`| Camada de dados confiáveis (Trusted) |
| `[prefixo-projeto-refined-accountid]`| Camada de dados refinados (Refined) |
| `[prefixo-projeto-logs-accountid]` | Logs de execução dos jobs |

### Bucket: `[prefixo-projeto-raw-accountid]`
-   **Path:** `vendas/`
    -   **Descrição:** Onde os arquivos diários de vendas são depositados.
-   **Path:** `clientes/`
    -   **Descrição:** Onde o dump da base de clientes é armazenado.

### Bucket: `[prefixo-projeto-refined-accountid]`
-   **Path:** `analytics/fato_vendas/`
    -   **Descrição:** Tabela fato de vendas em formato Parquet.