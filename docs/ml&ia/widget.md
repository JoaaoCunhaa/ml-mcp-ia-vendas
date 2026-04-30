# Widget ChatGPT Apps — MCP Primeira Mão Saga

O widget é a interface visual renderizada dentro do ChatGPT como um iframe. Ele exibe o carrossel de veículos (compra) ou o formulário de avaliação (venda), e permite ao cliente demonstrar interesse sem sair da conversa.

---

## Arquivos

| Arquivo | Propósito |
|---|---|
| `ui/vehicle-offers.js` | Toda a lógica do widget (575 linhas) |
| `ui/vehicle-offers.css` | Design system dark (vanilla CSS, Tailwind-inspired) |
| `ui/vehicle-offers.html` | Shell HTML estático (usado em testes externos) |
| `ui/test_widget.html` | Página de teste local (acesso via `/local/test`) |

---

## Dois recursos MCP separados

O servidor mantém dois recursos MCP distintos para evitar race conditions entre sessões concorrentes:

| Recurso | Tool | Payload em memória | Modo |
|---|---|---|---|
| `ui://vehicle-offers` | `buscar_veiculos` | `_LAST_BUY_PAYLOAD` | Carrossel de compra |
| `ui://vehicle-sell` | `exibir_formulario_venda` | `_LAST_SELL_PAYLOAD` | Formulário de venda |

Se existisse apenas um recurso, uma avaliação de venda poderia sobrescrever o payload do carrossel de compra enquanto o cliente ainda está visualizando os cards.

---

## Como o widget recebe dados

O JS (`vehicle-offers.js`) suporta três mecanismos de recepção de dados, em ordem de prioridade:

### 1. `window.openai.toolOutput` (preferencial)

O ChatGPT injeta o `structured_content` retornado pela tool call no objeto `window.openai.toolOutput`. O widget faz polling a cada **300ms** e detecta mudança de referência de objeto — quando a referência muda, significa que uma nova tool call ocorreu e o widget re-renderiza.

```javascript
var _lastToolOutput = undefined;

function renderIfChanged(out) {
  if (out === _lastToolOutput) return;   // mesma referência = sem mudança
  _lastToolOutput = out;
  var sc = extractStructuredContent(out);
  if (sc) render(sc);
}

setInterval(function () {
  renderIfChanged(window.openai && window.openai.toolOutput);
}, 300);
```

**Por que polling contínuo?** O ChatGPT Apps reutiliza o mesmo iframe entre tool calls. Sem polling contínuo, uma segunda busca (ex: troca de filtro) não seria detectada e o widget ficaria exibindo os resultados da busca anterior.

### 2. `#vehicle-data` embutido (fallback)

O HTML do recurso MCP embute o payload da última tool call em:

```html
<script type="application/json" id="vehicle-data">
  { "type": "vehicle_cards", "vehicles": [...], "searchContext": {...} }
</script>
```

Usado quando `toolOutput` ainda não está disponível no momento do `DOMContentLoaded`.

### 3. `postMessage` (debug/integração externa)

```javascript
window.postMessage({ type: 'vehicle_cards', vehicles: [...] }, '*')
```

---

## Modo carrossel (compra)

### Estrutura do payload esperado

```json
{
  "type": "vehicle_cards",
  "vehicles": [
    {
      "titulo_card": "Honda Civic Touring 2021",
      "imageUrl": "https://images.primeiramaosaga.com.br/...",
      "link": "https://www.primeiramaosaga.com.br/...",
      "brand": "Honda",
      "year": 2021,
      "kmFormatted": "32.000 km",
      "preco_formatado": "R$ 89.900",
      "location": "SN GO BURITI",
      "veiculo_id": "53480",
      "plate": "ABC1D23",
      "colorName": "Preto",
      "modelYear": "2021",
      "km": "32000"
    }
  ],
  "searchContext": {
    "city": "GOIÂNIA",
    "store": "SN GO BURITI"
  }
}
```

### UX do carrossel

- Scroll horizontal com snap em cada card
- Setas laterais (← →) para navegar
- Cabeçalho dinâmico: *"Veículos disponíveis em Goiânia"*
- Cada card exibe: foto, badge de marca, modelo, ano · KM, preço, loja

### UX do formulário de interesse

Clicar em **"Tenho interesse"** em qualquer card abre o formulário em **todos os cards simultaneamente**. O cliente escolhe em qual card enviar.

```javascript
interestBtn.addEventListener('click', function () {
  var track = article.closest('.vehicle-carousel');
  var allActions = track.querySelectorAll('.vehicle-actions');
  var allForms   = track.querySelectorAll('.interest-form');
  for (var i = 0; i < allActions.length; i++) allActions[i].style.display = 'none';
  for (var i = 0; i < allForms.length; i++)   allForms[i].style.display   = 'flex';
  iNameInput.focus();
});
```

Campos: nome completo, telefone com DDD. Ao confirmar, chama `window.openai.callTool("registrar_interesse_compra", {...})`.

---

## Modo formulário (venda)

### Estrutura do payload esperado

```json
{
  "mode": "sell",
  "evaluation": {
    "vehicleDescription": "Toyota Corolla 2.0 XEI 2019",
    "plate": "TST1T23",
    "km": "50000",
    "kmFormatted": "50.000 km",
    "proposal": "R$ 28.500,00"
  },
  "searchContext": { "city": "GOIÂNIA/GO" }
}
```

### UX do formulário

- Card centralizado verticalmente (max 420px de largura)
- Exibe: veículo, placa, KM, proposta
- Campos: nome completo, telefone
- Ao confirmar, chama `window.openai.callTool("registrar_interesse_venda", {...})`

---

## Bridge widget → tool

O ChatGPT Apps expõe `window.openai.callTool()` dentro do iframe. Isso permite que o widget registre o interesse do cliente diretamente, sem que o LLM precise interpretar uma mensagem adicional do usuário.

```javascript
// Chamada dentro do widget após o cliente confirmar
window.openai.callTool("registrar_interesse_compra", {
  nome_cliente:     iNameInput.value.trim(),
  telefone_cliente: iTelInput.value.replace(/\D/g, ''),
  titulo_veiculo:   vehicle.titulo_card,
  veiculo_id:       String(vehicle.veiculo_id || vehicle.id || ''),
  preco_formatado:  vehicle.preco_formatado || '',
  loja_unidade:     vehicle.loja_unidade || vehicle.location || '',
  plate:            vehicle.plate || '',
  modelYear:        String(vehicle.modelYear || vehicle.year || ''),
  km:               String(vehicle.km || '')
})
```

---

## Design system (CSS)

| Variável | Valor | Uso |
|---|---|---|
| `--bg` | `#0f1115` | Fundo da página |
| `--card-bg` | `#212121` | Fundo dos cards |
| `--border` | `rgba(255,255,255,0.09)` | Bordas |
| `--text-1` | `#ffffff` | Texto principal |
| `--text-2` | `#9a9a9a` | Texto secundário |
| `--text-3` | `#5a5a5a` | Texto terciário (loja, dica) |
| `--accent` | `#f2c200` | Amarelo Saga (botão principal) |
| `--accent-dk` | `#d4a800` | Amarelo hover |
| `--radius` | `14px` | Border radius dos cards |

### Componentes principais

- **`.vehicle-card`**: Card com flex-direction column, scroll-snap
- **`.vehicle-body__brand`**: Badge de marca (fundo branco, texto preto)
- **`.vehicle-body__price`**: Preço em branco, 22px, bold
- **`.btn--primary`**: Botão amarelo ("Tenho interesse")
- **`.btn--secondary`**: Botão branco ("Ver no site")
- **`.carousel-arrow`**: Setas laterais, circular, glassmorphism
- **`.sell-mode`**: Centraliza o formulário de venda via flexbox
- **`.sell-card`**: Card compacto max 420px
- **`.sell-form__input`**: Input Shadcn-inspired (fundo translúcido, borda sutil)
