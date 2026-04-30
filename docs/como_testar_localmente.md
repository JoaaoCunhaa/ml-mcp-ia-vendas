# Como Testar Localmente

Guia para rodar o servidor MCP e visualizar o widget no navegador sem precisar subir para produção.

---

## Pré-requisitos

1. Python 3.11+ com venv ativado
2. Arquivo `.env` preenchido em `src/python/mcp_primeira_mao/.env`

Variáveis mínimas para teste com estoque real:

```env
MCP_TRANSPORT=sse
LAMBDA_ESTOQUE_URL=https://<api-gateway>.execute-api.us-east-1.amazonaws.com/prod/mcp_veiculos
LAMBDA_API_KEY=<chave>
MOBI_SECRET=<secret>
URL_AWS_TOKEN=<url>
PRECIFICACAO_API_URL=<url>
```

---

## Iniciar o servidor

No PowerShell, a partir da raiz do projeto:

```powershell
cd src/python/mcp_primeira_mao
$env:MCP_TRANSPORT = "sse"; python main.py
```

O servidor sobe em `http://localhost:8000`. Você verá no terminal:

```
INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Testar o widget visualmente

Abra no navegador:

```
http://localhost:8000/local/test
```

A página de teste (`ui/test_widget.html`) é servida pelo próprio servidor — sem problemas de CORS.

### Interface de teste

- **Modo "Compra (carrossel)"**: escolha cidade e filtro opcional, clique em **Carregar**
- **Modo "Venda (formulário)"**: preencha veículo, placa, KM e proposta, clique em **Carregar**
- **Status**: indica se o JSON carregou com sucesso e se o widget renderizou
- **Reload frame**: recarrega o iframe sem buscar novos dados (útil para testar CSS/JS)

---

## Testar os endpoints diretamente

### Estoque (JSON bruto)

```
GET http://localhost:8000/local/ofertas?cidade=Goiânia
GET http://localhost:8000/local/ofertas?cidade=Goiânia&consulta=honda+civic
```

### Formulário de venda (JSON bruto)

```
GET http://localhost:8000/local/formulario-venda?veiculo=Honda+Civic+2021&placa=ABC1D23&km=32000&proposta=89900
```

### Registrar interesse de compra

```bash
POST http://localhost:8000/local/registrar-compra
Content-Type: application/json

{
  "nome_cliente": "João Teste",
  "telefone_cliente": "62999990001",
  "titulo_veiculo": "Honda Civic Touring 2021",
  "veiculo_id": "53480",
  "preco_formatado": "R$ 89.900",
  "loja_unidade": "SN GO BURITI",
  "plate": "ABC1D23",
  "modelYear": "2021",
  "km": "32000"
}
```

### Registrar interesse de venda

```bash
POST http://localhost:8000/local/registrar-venda
Content-Type: application/json

{
  "nome_cliente": "Maria Teste",
  "telefone_cliente": "62988880002",
  "placa": "TST1T23",
  "km": "50000",
  "veiculo_descricao": "Toyota Corolla 2019",
  "valor_proposta": "28500"
}
```

---

## Diagnóstico do servidor

```
GET http://localhost:8000/debug/inspect
```

Retorna metadados do servidor: status de JS/CSS, preview do payload de compra/venda, status da Lambda, etc.

---

## Testar com MCP Inspector (stdio)

Para testar as tools diretamente sem o ChatGPT:

```powershell
# Sem $env:MCP_TRANSPORT — usa stdio por padrão
python main.py
```

Em outro terminal, conecte o MCP Inspector:

```
npx @modelcontextprotocol/inspector python main.py
```

---

## Observações

- As rotas `/local/*` são bloqueadas para requisições de fora de localhost (HTTP 403)
- O `/local/test` serve o HTML sem CSP restritivo — o widget roda com scripts inline
- O estoque retornado é o real (Lambda AWS); use `consulta=` para filtrar por modelo
- O widget no `/local/test` usa o campo `#vehicle-data` como fonte de dados (equivalente ao fallback de produção); o comportamento do `toolOutput` só ocorre dentro do ChatGPT

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| Widget mostra "Carregando ofertas..." | JSON sem `type: "vehicle_cards"` | Verificar retorno do endpoint `/local/ofertas` |
| Status "Erro: HTTP 403" | Servidor não está em localhost | Garantir que acessa via `localhost:8000` |
| Status "Erro: Failed to fetch" | Servidor não está rodando | Verificar terminal do servidor |
| Cards aparecem sem imagem | Veículo sem `url_imagem` | Normal — Lambda filtra apenas veículos com imagem |
| Formulário de venda em branco | Payload sem `mode: "sell"` | Verificar retorno do `/local/formulario-venda` |
