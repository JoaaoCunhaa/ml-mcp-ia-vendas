console.log("[vehicle-offers] JS carregado");

(function () {
  'use strict';

  var TRUSTED_ORIGINS = ['https://chatgpt.com', 'https://chat.openai.com'];

  function log() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift('[vehicle-offers]');
    console.log.apply(console, args);
  }

  function getToolOutput() {
    if (window.openai && window.openai.toolOutput)        return window.openai.toolOutput;
    if (window.openai && window.openai.toolResponse)      return window.openai.toolResponse;
    if (window.openai && window.openai.structuredContent) return { structuredContent: window.openai.structuredContent };
    return null;
  }

  function extractStructuredContent(payload) {
    if (!payload) return null;
    if (payload.type === 'vehicle_cards') return payload;
    if (payload.structuredContent && payload.structuredContent.type === 'vehicle_cards') return payload.structuredContent;
    if (payload.params && payload.params.structuredContent && payload.params.structuredContent.type === 'vehicle_cards') return payload.params.structuredContent;
    return null;
  }

  /* ── Formatters ── */

  function fmtPrice(v) {
    if (v == null) return 'Consultar';
    var n = parseFloat(String(v).replace(/[^\d,.]/g, '').replace(',', '.'));
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

  /* ── Render ── */

  function renderEmpty(message) {
    var app = document.getElementById('app');
    if (!app) return;
    app.innerHTML = '';
    var div = el('div', 'empty');
    div.appendChild(txt(message || 'Nenhum veículo encontrado.'));
    app.appendChild(div);
  }

  function buildCard(vehicle) {
    var imageUrl  = safeUrl(vehicle.imageUrl || vehicle.url_imagem || vehicle.image || vehicle.foto || '');
    var linkUrl   = safeUrl(vehicle.link || vehicle.url || '');
    var title     = vehicle.title || [vehicle.brand || vehicle.marca, vehicle.model || vehicle.modelo].filter(Boolean).join(' ') || 'Veículo';
    var brand     = vehicle.brand || vehicle.marca || '';
    var year      = vehicle.year || vehicle.model_year || '';
    var km        = vehicle.kmFormatted || fmtKm(vehicle.km);
    var location  = vehicle.location || vehicle.store || [vehicle.loja, vehicle.cidade].filter(Boolean).join(' — ') || '';

    var article = el('article', 'vehicle-card');
    article.setAttribute('role', 'listitem');

    /* Image */
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

    /* Body */
    var body = el('div', 'vehicle-body');

    if (brand) {
      var brandEl = el('span', 'vehicle-body__brand');
      brandEl.appendChild(txt(brand.toUpperCase()));
      body.appendChild(brandEl);
    }

    var titleEl = el('h3', 'vehicle-body__title');
    titleEl.appendChild(txt(title));
    body.appendChild(titleEl);

    var specParts = [year ? 'Ano: ' + year : null, km || null].filter(Boolean);
    if (specParts.length) {
      var specs = el('p', 'vehicle-body__specs');
      specs.appendChild(txt(specParts.join(' • ')));
      body.appendChild(specs);
    }

    var priceEl = el('p', 'vehicle-body__price');
    priceEl.appendChild(txt(fmtPrice(vehicle.price)));
    body.appendChild(priceEl);

    if (location) {
      var locEl = el('p', 'vehicle-body__location');
      locEl.appendChild(txt('📍 ' + location));
      body.appendChild(locEl);
    }

    article.appendChild(body);

    /* Actions */
    var actions = el('div', 'vehicle-actions');

    if (linkUrl) {
      var linkBtn = el('a', 'btn btn--secondary');
      linkBtn.setAttribute('href', linkUrl);
      linkBtn.setAttribute('target', '_blank');
      linkBtn.setAttribute('rel', 'noopener noreferrer');
      linkBtn.appendChild(txt('Ver no site'));
      actions.appendChild(linkBtn);
    }

    article.appendChild(actions);
    return article;
  }

  function render(sc) {
    log('render | type=' + sc.type + ' | vehicles=' + (sc.vehicles ? sc.vehicles.length : 0));
    var app = document.getElementById('app');
    if (!app) { log('ERRO: #app não encontrado'); return; }
    app.innerHTML = '';

    var vehicles = Array.isArray(sc.vehicles) ? sc.vehicles : (Array.isArray(sc.offers) ? sc.offers : []);
    log('vehicles array length=' + vehicles.length);

    if (!vehicles.length) {
      renderEmpty('Nenhum veículo encontrado para essa busca.');
      return;
    }

    var grid = el('div', 'vehicle-grid');
    grid.setAttribute('role', 'list');

    for (var i = 0; i < vehicles.length; i++) {
      var v = vehicles[i];
      if (!v || typeof v !== 'object') continue;
      grid.appendChild(buildCard(v));
    }

    app.appendChild(grid);
    log('renderizado | ' + vehicles.length + ' cards');
  }

  var _rendered = false;

  function tryRender(sc) {
    if (_rendered) return;
    _rendered = true;
    render(sc);
  }

  function init() {
    log('DOMContentLoaded');
    log('window.openai', window.openai);
    log('toolOutput', window.openai && window.openai.toolOutput);

    var payload = getToolOutput();
    log('payload inicial', payload);
    var sc = extractStructuredContent(payload);
    log('structuredContent inicial', sc);

    if (sc) {
      tryRender(sc);
      return;
    }

    /* postMessage — ouve mensagens do host */
    window.addEventListener('message', function (event) {
      console.log('[vehicle-offers] postMessage recebido | origin=' + event.origin, event.data);
      var scFromMessage = extractStructuredContent(event.data);
      if (scFromMessage) tryRender(scFromMessage);
    });

    /* Polling — toolOutput pode ser injetado após DOMContentLoaded */
    var attempts = 0;
    var timer = setInterval(function () {
      attempts++;
      var payload2 = getToolOutput();
      console.log('[vehicle-offers] polling', attempts, payload2);
      var sc2 = extractStructuredContent(payload2);
      if (sc2) {
        clearInterval(timer);
        tryRender(sc2);
        return;
      }
      if (attempts >= 50) {
        clearInterval(timer);
        if (!_rendered) {
          log('timeout — sem dados após 5s');
          renderEmpty('Não recebi os dados dos veículos.');
        }
      }
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
