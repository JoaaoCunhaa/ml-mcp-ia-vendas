console.log("[vehicle-offers] inline JS carregado");

(function () {
  'use strict';

  function log() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift('[vehicle-offers]');
    console.log.apply(console, args);
  }

  /* ── extractStructuredContent: aceita TODOS os formatos ── */

  function extractStructuredContent(payload) {
    if (!payload) return null;

    if (payload.type === 'vehicle_cards' && Array.isArray(payload.vehicles)) return payload;
    if (payload.mode === 'sell') return payload;

    var sc = payload.structuredContent;
    if (sc) {
      if (sc.type === 'vehicle_cards' && Array.isArray(sc.vehicles)) return sc;
      if (sc.mode === 'sell') return sc;
    }

    var to = payload.toolOutput;
    if (to) {
      if (to.type === 'vehicle_cards' && Array.isArray(to.vehicles)) return to;
      if (to.mode === 'sell') return to;
      var tosc = to.structuredContent;
      if (tosc) {
        if (tosc.type === 'vehicle_cards' && Array.isArray(tosc.vehicles)) return tosc;
        if (tosc.mode === 'sell') return tosc;
      }
    }

    if (payload.params) {
      var psc = payload.params.structuredContent;
      if (psc) {
        if (psc.type === 'vehicle_cards' && Array.isArray(psc.vehicles)) return psc;
        if (psc.mode === 'sell') return psc;
      }
      var pto = payload.params.toolOutput;
      if (pto) {
        if (pto.type === 'vehicle_cards' && Array.isArray(pto.vehicles)) return pto;
        if (pto.mode === 'sell') return pto;
        var ptosc = pto.structuredContent;
        if (ptosc) {
          if (ptosc.type === 'vehicle_cards' && Array.isArray(ptosc.vehicles)) return ptosc;
          if (ptosc.mode === 'sell') return ptosc;
        }
      }
    }

    return null;
  }

  /* ── Formatters ── */

  function fmtPrice(v) {
    if (v == null) return 'Consultar';
    var s = String(v).trim();
    if (!s) return 'Consultar';

    // Remove símbolo de moeda e espaços para detectar o formato numérico
    var clean = s.replace(/[R$\s]/g, '');
    if (!clean) return 'Consultar';

    var lastDot   = clean.lastIndexOf('.');
    var lastComma = clean.lastIndexOf(',');

    var n;
    if (lastComma > lastDot) {
      // Formato brasileiro: 49.990,00 — vírgula é separador decimal
      n = parseFloat(clean.replace(/\./g, '').replace(',', '.'));
    } else {
      // Número puro ou formato US: 49990 ou 49990.50
      n = parseFloat(clean.replace(/,/g, ''));
    }

    if (isNaN(n) || n <= 0) return 'Consultar';
    var parts = n.toFixed(2).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return 'R$ ' + parts[0] + ',' + parts[1];
  }

  function fmtKm(v) {
    if (v == null || v === '') return '';
    var n = parseInt(String(v).replace(/\D/g, ''), 10);
    if (isNaN(n)) return '';
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' km';
  }

  function maskTel(v) {
    var d = v.replace(/\D/g, '').slice(0, 11);
    if (d.length <= 2)  return '(' + d;
    if (d.length <= 6)  return '(' + d.slice(0,2) + ') ' + d.slice(2);
    if (d.length <= 10) return '(' + d.slice(0,2) + ') ' + d.slice(2,6) + '-' + d.slice(6);
    return '(' + d.slice(0,2) + ') ' + d.slice(2,7) + '-' + d.slice(7);
  }

  function safeUrl(url) {
    if (!url || typeof url !== 'string') return null;
    try {
      var u = new URL(url);
      return u.protocol === 'https:' ? url : null;
    } catch (_) { return null; }
  }

  /* ── DOM helpers ── */

  function el(tag, cls) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  function txt(str) {
    return document.createTextNode(str == null ? '' : String(str));
  }

  /* ── Bridge: chama tool MCP via host ── */

  function callTool(name, args) {
    if (window.openai && typeof window.openai.callTool === 'function') {
      return Promise.resolve(window.openai.callTool(name, args));
    }
    if (window.mcpBridge && typeof window.mcpBridge.callTool === 'function') {
      return Promise.resolve(window.mcpBridge.callTool(name, args));
    }
    return Promise.reject(new Error('BRIDGE_UNAVAILABLE'));
  }

  /* ── Render: modo venda ── */

  function renderSell(sc) {
    log('renderSell', sc);
    var app = document.getElementById('app');
    if (!app) { log('ERRO: #app não encontrado'); return; }
    app.innerHTML = '';

    /* Centraliza o card compacto na viewport */
    app.className = 'sell-mode';

    var card = el('article', 'sell-card');

    /* Badge "AVALIAÇÃO" — branco com texto preto (igual ao badge de marca) */
    var badge = el('span', 'vehicle-body__brand');
    badge.appendChild(txt('AVALIAÇÃO'));
    card.appendChild(badge);

    /* Nome do veículo em branco puro */
    var titleEl = el('h3', 'vehicle-body__title');
    titleEl.appendChild(txt(sc.veiculo || 'Seu veículo'));
    card.appendChild(titleEl);

    /* Dados sem rótulo "Placa:" — apenas os valores em cinza */
    var specParts = [];
    if (sc.placa) specParts.push(sc.placa);
    var kmStr = sc.km_fmt || fmtKm(sc.km) || '';
    if (kmStr) specParts.push(kmStr);
    if (specParts.length) {
      var specs = el('p', 'vehicle-body__specs');
      specs.appendChild(txt(specParts.join(' • ')));
      card.appendChild(specs);
    }

    if (sc.proposta) {
      var propLabel = el('p', 'sell-card__label');
      propLabel.appendChild(txt('Proposta Saga'));
      card.appendChild(propLabel);
      var price = el('p', 'vehicle-body__price');
      price.appendChild(txt(sc.proposta));
      card.appendChild(price);
    }

    /* Texto informativo em cinza discreto */
    var hint = el('p', 'sell-card__hint');
    hint.appendChild(txt('📲 Informe seus dados — um consultor entra em contato via WhatsApp'));
    card.appendChild(hint);

    var nameInput = el('input', 'sell-form__input');
    nameInput.setAttribute('type', 'text');
    nameInput.setAttribute('placeholder', 'Seu nome completo');
    nameInput.setAttribute('maxlength', '100');
    nameInput.setAttribute('autocomplete', 'name');
    card.appendChild(nameInput);

    var nameErr = el('p', 'sell-form__error');
    card.appendChild(nameErr);

    var telInput = el('input', 'sell-form__input');
    telInput.setAttribute('type', 'tel');
    telInput.setAttribute('placeholder', 'Telefone com DDD');
    telInput.setAttribute('maxlength', '16');
    telInput.setAttribute('autocomplete', 'tel');
    card.appendChild(telInput);

    var telErr = el('p', 'sell-form__error');
    card.appendChild(telErr);

    telInput.addEventListener('input', function () {
      this.value = maskTel(this.value);
    });

    var feedback = el('div', 'sell-card__feedback');
    card.appendChild(feedback);

    var btn = el('button', 'btn btn--primary sell-form__btn');
    btn.setAttribute('type', 'button');
    btn.appendChild(txt('Confirmar contato via WhatsApp'));

    btn.addEventListener('click', function () {
      var nome = nameInput.value.trim();
      var tel  = telInput.value.replace(/\D/g, '');

      nameErr.textContent = '';
      telErr.textContent  = '';

      if (!nome || nome.length < 2) {
        nameErr.textContent = 'Informe seu nome completo.';
        nameInput.focus();
        return;
      }
      if (tel.length < 10) {
        telErr.textContent = 'Informe um telefone com DDD (10 ou 11 dígitos).';
        telInput.focus();
        return;
      }

      btn.disabled    = true;
      btn.textContent = 'Aguarde...';

      callTool('registrar_interesse_venda', {
        nome_cliente:      nome,
        telefone_cliente:  tel,
        veiculo_descricao: sc.veiculo  || '',
        placa:             sc.placa    || '',
        km:                sc.km       || '',
        valor_proposta:    sc.proposta || '',
      })
      .then(function () {
        btn.textContent = 'Enviado ✓';
        feedback.textContent = 'Pronto, ' + nome.split(' ')[0] + '! Um consultor da Saga entrará em contato em breve via WhatsApp.';
        feedback.className = 'sell-card__feedback sell-card__feedback--ok';
      })
      .catch(function (err) {
        btn.disabled    = false;
        btn.textContent = 'Confirmar contato via WhatsApp';
        log('callTool error:', err && err.message);
        feedback.textContent = 'Não foi possível registrar agora. Tente novamente ou acesse primeiramaosaga.com.br.';
        feedback.className = 'sell-card__feedback sell-card__feedback--err';
      });
    });

    card.appendChild(btn);
    app.appendChild(card);
  }

  /* ── Render: modo compra ── */

  function renderEmpty(message) {
    var app = document.getElementById('app');
    if (!app) return;
    app.innerHTML = '';
    var div = el('div', 'empty');
    div.appendChild(txt(message || 'Nenhum veículo encontrado.'));
    app.appendChild(div);
  }

  function renderLoading(message) {
    renderEmpty(message || 'Carregando ofertas...');
  }

  function toTitleCase(s) {
    return String(s || '').toLowerCase().replace(/(?:^|\s)\S/g, function (c) { return c.toUpperCase(); });
  }

  function buildCard(vehicle) {
    var imageUrl = safeUrl(vehicle.imageUrl || vehicle.url_imagem || vehicle.image || vehicle.foto || '');
    var linkUrl  = safeUrl(vehicle.link || vehicle.url || '');
    var brand    = vehicle.brand || vehicle.marca || '';
    var model    = vehicle.model || vehicle.modelo || '';
    var title    = toTitleCase(model) || toTitleCase(brand) || vehicle.title || 'Veículo';
    var year     = vehicle.year || vehicle.model_year || '';
    var km       = fmtKm(vehicle.kmFormatted || vehicle.km);
    var location = vehicle.location || vehicle.store || [vehicle.loja, vehicle.cidade].filter(Boolean).join(' — ') || '';

    var article = el('article', 'vehicle-card');
    article.setAttribute('role', 'listitem');

    /* ── Imagem ── */
    var imgWrap = el('div', 'vehicle-image');
    if (imageUrl) {
      var img = document.createElement('img');
      img.setAttribute('alt', title);
      img.setAttribute('loading', 'lazy');
      img.setAttribute('decoding', 'async');
      img.src = imageUrl;
      imgWrap.appendChild(img);
    } else {
      var placeholder = el('div', 'vehicle-image__placeholder');
      placeholder.appendChild(txt('🚗'));
      imgWrap.appendChild(placeholder);
    }
    article.appendChild(imgWrap);

    /* ── Corpo ── */
    var body = el('div', 'vehicle-body');

    if (brand) {
      var brandEl = el('span', 'vehicle-body__brand');
      brandEl.appendChild(txt(brand.toUpperCase()));
      body.appendChild(brandEl);
    }

    var titleEl = el('h3', 'vehicle-body__title');
    titleEl.appendChild(txt(title));
    body.appendChild(titleEl);

    /* Linha única: ano • km | loja */
    var infoLeft = [year || null, km || null].filter(Boolean).join(' • ');
    var infoStr  = infoLeft && location ? infoLeft + ' | ' + location
                 : infoLeft || location || '';
    if (infoStr) {
      var specs = el('p', 'vehicle-body__specs');
      specs.appendChild(txt(infoStr));
      body.appendChild(specs);
    }

    var priceEl = el('p', 'vehicle-body__price');
    priceEl.appendChild(txt(fmtPrice(vehicle.price)));
    body.appendChild(priceEl);

    article.appendChild(body);

    /* ── Botões de ação (ocultados quando o formulário abre) ── */
    var actions = el('div', 'vehicle-actions');

    if (linkUrl) {
      var linkBtn = el('a', 'btn btn--secondary');
      linkBtn.setAttribute('href', linkUrl);
      linkBtn.setAttribute('target', '_blank');
      linkBtn.setAttribute('rel', 'noopener noreferrer');
      linkBtn.appendChild(txt('Ver no site'));
      actions.appendChild(linkBtn);
    }

    var interestBtn = el('button', 'btn btn--primary');
    interestBtn.setAttribute('type', 'button');
    interestBtn.appendChild(txt('Tenho interesse'));
    actions.appendChild(interestBtn);

    article.appendChild(actions);

    /* ── Formulário de interesse — substitui os botões neste card apenas ── */
    var interestForm = el('div', 'interest-form');

    var iNameInput = el('input', 'sell-form__input');
    iNameInput.setAttribute('type', 'text');
    iNameInput.setAttribute('placeholder', 'Seu nome completo');
    iNameInput.setAttribute('maxlength', '100');
    iNameInput.setAttribute('autocomplete', 'name');

    var iNameErr = el('p', 'sell-form__error');

    var iTelInput = el('input', 'sell-form__input');
    iTelInput.setAttribute('type', 'tel');
    iTelInput.setAttribute('placeholder', 'Telefone com DDD');
    iTelInput.setAttribute('maxlength', '16');
    iTelInput.setAttribute('autocomplete', 'tel');

    var iTelErr = el('p', 'sell-form__error');

    iTelInput.addEventListener('input', function () {
      this.value = maskTel(this.value);
    });

    var iFeedback = el('div', 'sell-card__feedback');

    var iSubmit = el('button', 'btn btn--primary sell-form__btn');
    iSubmit.setAttribute('type', 'button');
    iSubmit.appendChild(txt('Confirmar via WhatsApp'));

    interestForm.appendChild(iNameInput);
    interestForm.appendChild(iNameErr);
    interestForm.appendChild(iTelInput);
    interestForm.appendChild(iTelErr);
    interestForm.appendChild(iFeedback);
    interestForm.appendChild(iSubmit);

    /* Clique em "Tenho interesse": abre o form em TODOS os cards do carrossel */
    interestBtn.addEventListener('click', function () {
      var track = article.closest('.vehicle-carousel') || article.parentNode;
      var allActions = track.querySelectorAll('.vehicle-actions');
      var allForms   = track.querySelectorAll('.interest-form');
      for (var i = 0; i < allActions.length; i++) allActions[i].style.display = 'none';
      for (var i = 0; i < allForms.length; i++)   allForms[i].style.display   = 'flex';
      iNameInput.focus();
    });

    iSubmit.addEventListener('click', function () {
      var nome = iNameInput.value.trim();
      var tel  = iTelInput.value.replace(/\D/g, '');

      iNameErr.textContent = '';
      iTelErr.textContent  = '';

      if (!nome || nome.length < 2) {
        iNameErr.textContent = 'Informe seu nome completo.';
        iNameInput.focus();
        return;
      }
      if (tel.length < 10) {
        iTelErr.textContent = 'Informe um telefone com DDD.';
        iTelInput.focus();
        return;
      }

      iSubmit.disabled    = true;
      iSubmit.textContent = 'Aguarde...';

      callTool('registrar_interesse_compra', {
        nome_cliente:     nome,
        telefone_cliente: tel,
        titulo_veiculo:   title,
        loja_unidade:     location,
        preco_formatado:  vehicle.price ? String(vehicle.price) : '',
        veiculo_id:       String(vehicle.id || ''),
      })
      .then(function () {
        iSubmit.textContent = 'Enviado ✓';
        iFeedback.textContent = 'Pronto, ' + nome.split(' ')[0] + '! Um consultor entrará em contato via WhatsApp.';
        iFeedback.className = 'sell-card__feedback sell-card__feedback--ok';
      })
      .catch(function (err) {
        iSubmit.disabled    = false;
        iSubmit.textContent = 'Confirmar via WhatsApp';
        log('callTool error:', err && err.message);
        iFeedback.textContent = 'Não foi possível registrar. Tente novamente.';
        iFeedback.className = 'sell-card__feedback sell-card__feedback--err';
      });
    });

    article.appendChild(interestForm);
    return article;
  }

  function render(sc) {
    if (sc.mode === 'sell') { renderSell(sc); return; }

    log('render | vehicles=' + (sc.vehicles ? sc.vehicles.length : 0));
    var app = document.getElementById('app');
    if (!app) { log('ERRO: #app não encontrado'); return; }
    app.innerHTML = '';

    var vehicles = Array.isArray(sc.vehicles) ? sc.vehicles : (Array.isArray(sc.offers) ? sc.offers : []);
    if (!vehicles.length) { renderEmpty('Nenhum veículo encontrado para essa busca.'); return; }

    /* Cabeçalho dinâmico: "Veículos disponíveis em {cidade}" */
    var cityRaw = sc.searchContext && sc.searchContext.city ? sc.searchContext.city : '';
    if (cityRaw) {
      var header = el('div', 'carousel-header');
      header.appendChild(txt('Veículos disponíveis em ' + toTitleCase(cityRaw)));
      app.appendChild(header);
    }

    var wrap = el('div', 'vehicle-carousel-wrap');

    var track = el('div', 'vehicle-carousel');
    track.setAttribute('role', 'list');
    for (var i = 0; i < vehicles.length; i++) {
      if (vehicles[i] && typeof vehicles[i] === 'object') track.appendChild(buildCard(vehicles[i]));
    }
    wrap.appendChild(track);

    /* Setas laterais sobrepostas */
    function updateArrows() {
      var atStart = track.scrollLeft <= 2;
      var atEnd   = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      prevBtn.style.display = atStart ? 'none' : 'flex';
      nextBtn.style.display = atEnd   ? 'none' : 'flex';
    }

    var prevBtn = el('button', 'carousel-arrow carousel-arrow--prev');
    prevBtn.setAttribute('type', 'button');
    prevBtn.setAttribute('aria-label', 'Anterior');
    prevBtn.innerHTML = '&#8592;';
    prevBtn.addEventListener('click', function () {
      track.scrollBy({ left: -300, behavior: 'smooth' });
    });

    var nextBtn = el('button', 'carousel-arrow carousel-arrow--next');
    nextBtn.setAttribute('type', 'button');
    nextBtn.setAttribute('aria-label', 'Próximo');
    nextBtn.innerHTML = '&#8594;';
    nextBtn.addEventListener('click', function () {
      track.scrollBy({ left: 300, behavior: 'smooth' });
    });

    /* Prev começa sempre oculto (carrossel inicia no início) */
    prevBtn.style.display = 'none';

    wrap.appendChild(prevBtn);
    wrap.appendChild(nextBtn);
    app.appendChild(wrap);

    /* Aguarda o browser calcular layout antes de verificar o estado */
    requestAnimationFrame(function () { requestAnimationFrame(updateArrows); });
    track.addEventListener('scroll', updateArrows);
    log('renderizado | ' + vehicles.length + ' cards');
  }

  /* ── Init ── */

  /* Rastreia a referência do último toolOutput processado.
     Quando o ChatGPT reutiliza o mesmo iframe para uma nova consulta,
     ele injeta um novo objeto toolOutput — a referência muda e o re-render ocorre. */
  var _lastToolOutput = undefined;
  var _hasRendered    = false;

  function renderIfChanged(out) {
    if (out === _lastToolOutput) return;
    _lastToolOutput = out;
    if (!out) return;
    var sc = extractStructuredContent(out);
    if (sc) { render(sc); _hasRendered = true; }
  }

  function init() {
    log('DOMContentLoaded');
    log('window.openai', window.openai);

    /* 1. toolOutput imediato — SEMPRE preferir sobre dados embutidos.
          toolOutput é injetado pelo ChatGPT com o structured_content da chamada atual,
          garantindo que o widget renderize o payload correto mesmo quando o HTML do
          recurso está em cache com dados de uma chamada anterior. */
    renderIfChanged(window.openai && window.openai.toolOutput);

    /* 2. Dados embutidos — fallback quando toolOutput não disponível ainda */
    if (!_hasRendered) {
      var dataEl = document.getElementById('vehicle-data');
      if (dataEl) {
        try {
          var embedded = JSON.parse(dataEl.textContent || dataEl.innerHTML || 'null');
          log('embedded data', embedded);
          var scEmbed = extractStructuredContent(embedded);
          if (scEmbed) { render(scEmbed); _hasRendered = true; }
        } catch (e) {
          log('embedded data parse error', e);
        }
      }
      if (!_hasRendered) { renderLoading('Carregando ofertas...'); }
    }

    /* 3. Watcher contínuo — detecta toolOutput inicial (se ainda não chegou)
          E novas consultas na mesma sessão quando o ChatGPT reutiliza o iframe.
          Roda indefinidamente para capturar qualquer nova chamada de ferramenta. */
    setInterval(function () {
      renderIfChanged(window.openai && window.openai.toolOutput);
    }, 300);

    /* 4. postMessage listener */
    window.addEventListener('message', function (event) {
      log('raw message', event.data);
      var sc2 = extractStructuredContent(event.data);
      if (sc2) render(sc2);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
