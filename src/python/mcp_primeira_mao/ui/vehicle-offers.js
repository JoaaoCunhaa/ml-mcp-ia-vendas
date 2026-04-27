/**
 * vehicle-offers.js — Lógica do widget de ofertas Saga
 *
 * SEGURANÇA:
 *  - Nenhum innerHTML com dados externos. Todo DOM via API (createElement, textContent).
 *  - Inputs validados e sanitizados antes de qualquer uso.
 *  - Rate limiting por card e global contra spam de tool calls.
 *  - Anti-double-submit: botão desabilitado após primeiro clique.
 *  - Origin whitelist rígida no listener postMessage.
 *  - URLs de imagem validadas para esquema https: apenas.
 *  - _meta permanece em memória — nunca renderizado no DOM.
 *  - Mensagens de erro genéricas ao usuário; detalhes ficam no console (dev).
 *  - Nenhum dado sensível (placa, dealer_id) exposto no DOM.
 */

(function () {
  'use strict';

  /* ════════════════════════════════════════════════════════════════════
     CONSTANTES DE SEGURANÇA
     ════════════════════════════════════════════════════════════════════ */

  /** Origens confiáveis para postMessage. */
  var TRUSTED_ORIGINS = Object.freeze([
    'https://chatgpt.com',
    'https://chat.openai.com',
  ]);

  /** Millisegundos de bloqueio por card após submissão bem-sucedida. */
  var RATE_LIMIT_PER_CARD_MS = 30000;

  /** Máximo de tool calls simultâneos pendentes. */
  var MAX_PENDING_CALLS = 3;

  /** Timeout de cada tool call em ms. */
  var TOOL_CALL_TIMEOUT_MS = 15000;

  /** Máximo de tentativas de inicialização por polling. */
  var MAX_POLL_ATTEMPTS = 50;

  /** Intervalo de polling para dados iniciais (ms). */
  var POLL_INTERVAL_MS = 180;

  /** Timeout total para aguardar dados iniciais (ms). */
  var INIT_TIMEOUT_MS = 9000;

  /** Tamanho máximo permitido para nome (chars). */
  var MAX_NOME_LEN = 100;

  /** Tamanho mínimo para nome (chars). */
  var MIN_NOME_LEN = 2;

  /** Ativa painel de debug quando ?debug=1 está na URL. */
  var DBG = /[?&]debug=1/.test(window.location.search);

  /** Modo local: mostra erro real do servidor no card (além do painel de debug). */
  var LOCAL = /[?&]local=1/.test(window.location.search) || DBG;

  /* ════════════════════════════════════════════════════════════════════
     DEBUG — painel de logs visível apenas com ?debug=1
     ════════════════════════════════════════════════════════════════════ */

  function dbgInit() {
    if (!DBG) return;
    var panel = document.getElementById('dbg');
    if (panel) panel.hidden = false;
    var closeBtn = document.getElementById('dbg-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        var p = document.getElementById('dbg');
        if (p) p.hidden = true;
      });
    }
    var clearBtn = document.getElementById('dbg-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        var body = document.getElementById('dbg-body');
        if (body) while (body.firstChild) body.removeChild(body.firstChild);
      });
    }
  }

  /**
   * Adiciona uma linha ao painel de debug.
   * Usa textContent — nenhum dado externo via innerHTML.
   */
  function dbgLog(tag, data) {
    if (!DBG) return;
    var body = document.getElementById('dbg-body');
    if (!body) return;
    var ts   = new Date().toTimeString().slice(0, 8);
    var text;
    try { text = (typeof data === 'object') ? JSON.stringify(data) : String(data); }
    catch (_) { text = String(data); }

    var line = document.createElement('div');
    var cls  = 'dbg-line';
    if (tag.indexOf('→') !== -1)      cls += ' dbg-out';
    else if (tag.indexOf('←') !== -1)  cls += ' dbg-in';
    else if (tag.toLowerCase().indexOf('err') !== -1) cls += ' dbg-err';
    else                               cls += ' dbg-inf';
    line.className = cls;
    line.textContent = '[' + ts + '] ' + tag + '  ' + text;

    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
  }

  /* ════════════════════════════════════════════════════════════════════
     ESTADO DA APLICAÇÃO — em memória, nunca no DOM
     ════════════════════════════════════════════════════════════════════ */

  var APP = {
    data:         null,   // structuredContent do MCP
    meta:         null,   // _meta do MCP (IDs internos — não vão para o DOM)
    pendingCalls: 0,      // contador de calls em andamento
    rateMap:      {},     // { cardId: timestamp da última submissão }
    submittedIds: {},     // { offerId: true } — impede replay no mesmo ciclo
  };

  /* ════════════════════════════════════════════════════════════════════
     HELPERS DE DOM — NUNCA usam innerHTML com dados externos
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Cria um elemento HTML com atributos e filhos de forma segura.
   * Não usa innerHTML. Strings são tratadas como TextNodes.
   *
   * @param {string}  tag
   * @param {Object}  attrs  — { class, id, type, role, aria-*, data-*, text, ... }
   * @param {...(HTMLElement|string|null)} children
   */
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      var keys = Object.keys(attrs);
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var v = attrs[k];
        if (v == null) continue;
        if (k === 'class') { el.className = String(v); continue; }
        if (k === 'id')    { el.id = String(v); continue; }
        if (k === 'text')  { el.textContent = String(v); continue; }
        el.setAttribute(k, String(v));
      }
    }
    for (var c = 2; c < arguments.length; c++) {
      var child = arguments[c];
      if (child == null) continue;
      if (typeof child === 'string') {
        el.appendChild(document.createTextNode(child));
      } else {
        el.appendChild(child);
      }
    }
    return el;
  }

  /**
   * Cria um elemento <svg><use href="#ic-ID"/></svg> usando o sprite do HTML.
   * Seguro: usa createElementNS — sem innerHTML.
   */
  function icon(id, w, ht) {
    var NS  = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width',        String(w  || 13));
    svg.setAttribute('height',       String(ht || 13));
    svg.setAttribute('aria-hidden',  'true');
    svg.setAttribute('focusable',    'false');
    var use = document.createElementNS(NS, 'use');
    use.setAttribute('href', '#ic-' + id);
    svg.appendChild(use);
    return svg;
  }

  /** Seleciona o ícone correto pelo texto do atributo. */
  function featureIcon(feature) {
    var f = (typeof feature === 'string' ? feature : '').toLowerCase();
    if (f.indexOf('porta')     !== -1) return icon('door');
    if (f.indexOf('ar')        !== -1 || f.indexOf('condic') !== -1) return icon('ac');
    if (f.indexOf('vidro')     !== -1) return icon('window');
    if (f.indexOf('trava')     !== -1) return icon('lock');
    return icon('check');
  }

  /** Cria o elemento de fallback quando a imagem falha. */
  function createFallback() {
    return h('div', { class: 'img-fallback', 'aria-hidden': 'true' }, '🚗');
  }

  /* ════════════════════════════════════════════════════════════════════
     VALIDAÇÃO E SANITIZAÇÃO DE DADOS DE ENTRADA
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Valida nome: 2-100 chars, apenas letras Unicode, espaços, hífen e apóstrofo.
   * Retorna string de erro ou null se válido.
   */
  function validateNome(v) {
    if (!v || typeof v !== 'string') return 'Nome é obrigatório.';
    var s = v.trim();
    if (s.length < MIN_NOME_LEN) return 'Informe seu nome completo.';
    if (s.length > MAX_NOME_LEN) return 'Nome muito longo.';
    /* Permitir letras Unicode (incluindo acentuadas), espaços, hífen, apóstrofo */
    if (!/^[\p{L}\s'\-]+$/u.test(s)) return 'Nome contém caracteres inválidos.';
    return null;
  }

  /**
   * Valida telefone: 10-11 dígitos com DDD.
   * Retorna string de erro ou null se válido.
   */
  function validateTelefone(v) {
    if (!v || typeof v !== 'string') return 'Telefone é obrigatório.';
    var digits = v.replace(/\D/g, '');
    if (digits.length < 10 || digits.length > 11) {
      return 'Informe um telefone com DDD (10 ou 11 dígitos).';
    }
    return null;
  }

  /**
   * Valida e sanitiza URL de imagem — aceita apenas https:.
   * Retorna a URL original se válida, ou null.
   * Previne protocol injection (javascript:, data:, etc).
   */
  function safeImageUrl(url) {
    if (!url || typeof url !== 'string') return null;
    try {
      var u = new URL(url);
      if (u.protocol !== 'https:') return null;
      return url;
    } catch (_) {
      return null;
    }
  }

  /**
   * Valida URL de link externo — aceita apenas https:.
   */
  function safeLinkUrl(url) {
    if (!url || typeof url !== 'string') return null;
    try {
      var u = new URL(url);
      if (u.protocol !== 'https:') return null;
      return url;
    } catch (_) {
      return null;
    }
  }

  /**
   * Máscara de telefone BR: (XX) X XXXX-XXXX ou (XX) XXXX-XXXX.
   * Só remove não-dígitos e formata — sem lógica de negócio.
   */
  function maskTel(v) {
    var d = v.replace(/\D/g, '').slice(0, 11);
    if (d.length <= 2)  return '(' + d;
    if (d.length <= 6)  return '(' + d.slice(0,2) + ') ' + d.slice(2);
    if (d.length <= 10) return '(' + d.slice(0,2) + ') ' + d.slice(2,6) + '-' + d.slice(6);
    return '(' + d.slice(0,2) + ') ' + d.slice(2,7) + '-' + d.slice(7);
  }

  /**
   * Formata preço de venda como "R$ 89.900,00".
   * Aceita número (89900), decimal ("89900.00") ou PT-BR ("89.900,00").
   */
  function fmtPriceVenda(v) {
    if (v == null) return 'Consultar';
    var raw = String(v).replace(/[^\d,\.]/g, '');
    var n;
    if (raw.indexOf(',') !== -1 && raw.indexOf('.') !== -1) {
      n = parseFloat(raw.replace(/\./g, '').replace(',', '.'));
    } else if (raw.indexOf(',') !== -1) {
      n = parseFloat(raw.replace(',', '.'));
    } else {
      n = parseFloat(raw);
    }
    if (isNaN(n) || n <= 0) return 'Consultar';
    var parts = n.toFixed(2).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return 'R$ ' + parts[0] + ',' + parts[1];
  }

  /** Formata quilometragem: 45000 → "45.000 km". */
  function fmtKm(v) {
    if (v == null || v === '') return '';
    var n = parseInt(String(v).replace(/\D/g, ''), 10);
    if (isNaN(n)) return '';
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' km';
  }

  /**
   * Retorna todos os candidatos de URL de imagem https: de um veículo,
   * deduplificados e em ordem de prioridade.
   * O widget tentará cada URL e descartará fotos de pessoa/banner pela proporção.
   */
  function getVehicleImageUrls(vehicle) {
    if (!vehicle || typeof vehicle !== 'object') return [];
    var seen = {};
    var urls = [];

    function add(raw) {
      var u = safeImageUrl(raw);
      if (u && !seen[u]) { seen[u] = true; urls.push(u); }
    }

    /* imageUrl / foto / campos alternativos */
    add(vehicle.imageUrl);
    add(vehicle.image);
    add(vehicle.photo);
    add(vehicle.foto);
    add(vehicle.urlImagem);
    add(vehicle.url_imagem);

    /* images[] — array do contrato (ex: [{url: '...', position: 0}, ...]) */
    if (Array.isArray(vehicle.images)) {
      vehicle.images.forEach(function (img) {
        add(typeof img === 'string' ? img : (img && img.url ? img.url : null));
      });
    }

    /* photos[] e imagens[] — campos alternativos */
    if (Array.isArray(vehicle.photos)) {
      vehicle.photos.forEach(function (p) { add(typeof p === 'string' ? p : null); });
    }
    if (Array.isArray(vehicle.imagens)) {
      vehicle.imagens.forEach(function (p) { add(typeof p === 'string' ? p : null); });
    }

    return urls;
  }

  /**
   * Extrai a primeira URL de imagem https: válida (para compatibilidade).
   */
  function getVehicleImage(vehicle) {
    var urls = getVehicleImageUrls(vehicle);
    return urls.length ? urls[0] : null;
  }

  /** Retorna true se o veículo possui ao menos uma URL de imagem https: válida. */
  function hasValidImage(vehicle) {
    return getVehicleImageUrls(vehicle).length > 0;
  }

  /**
   * Extrai conteúdo estruturado de uma resposta de callTool.
   * FastMCP retorna dicts como JSON text em content[0].text;
   * structuredContent pode estar ausente dependendo da versão do bridge.
   */
  function extractStructuredContent(res) {
    if (res && res.structuredContent && typeof res.structuredContent === 'object') {
      return res.structuredContent;
    }
    try {
      var ct = res && res.content && Array.isArray(res.content) && res.content[0];
      if (ct && ct.type === 'text' && ct.text) {
        return JSON.parse(ct.text);
      }
    } catch (_) {}
    return res || {};
  }

  /* ════════════════════════════════════════════════════════════════════
     RATE LIMITING — previne spam de ações
     ════════════════════════════════════════════════════════════════════ */

  function isRateLimited(cardId) {
    var t = APP.rateMap[cardId];
    return t && (Date.now() - t < RATE_LIMIT_PER_CARD_MS);
  }

  function setRateLimit(cardId) {
    APP.rateMap[cardId] = Date.now();
  }

  function canCallTool() {
    return APP.pendingCalls < MAX_PENDING_CALLS;
  }

  /* ════════════════════════════════════════════════════════════════════
     ACESSO A DADOS — lê de variáveis de janela injetadas pelo host
     _meta permanece em APP.meta (memória), nunca vai para o DOM
     ════════════════════════════════════════════════════════════════════ */

  function getData() {
    /* Padrão MCP Apps → fallback genérico → URL param (dev) */
    if (window.__MCP_STRUCTURED_CONTENT__) return window.__MCP_STRUCTURED_CONTENT__;
    if (window.__INITIAL_DATA__)           return window.__INITIAL_DATA__;
    if (window.__TOOL_RESULT__ && window.__TOOL_RESULT__.structuredContent)
      return window.__TOOL_RESULT__.structuredContent;
    try {
      var p = new URLSearchParams(window.location.search).get('data');
      if (p) return JSON.parse(decodeURIComponent(p));
    } catch (_) {}
    return null;
  }

  function getMeta() {
    if (window.__MCP_META__) return window.__MCP_META__;
    if (window.__TOOL_RESULT__ && window.__TOOL_RESULT__._meta)
      return window.__TOOL_RESULT__._meta;
    try {
      var p = new URLSearchParams(window.location.search).get('meta');
      if (p) return JSON.parse(decodeURIComponent(p));
    } catch (_) {}
    return {};
  }

  /* ════════════════════════════════════════════════════════════════════
     BRIDGE MCP — chamada de tools via host
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Chama um tool MCP via bridge disponível.
   * Nunca expõe detalhes do erro de rede ao usuário.
   * Aplica timeout para evitar hangs.
   *
   * @param {string} toolName
   * @param {Object} args — deve conter apenas dados já validados
   * @returns {Promise}
   */
  function callTool(toolName, args) {
    if (!canCallTool()) {
      return Promise.reject(new Error('RATE_LIMITED'));
    }

    APP.pendingCalls++;

    var callPromise;

    /* 0 — Localhost: chama o servidor MCP direto via HTTP */
    var _isLocal = (
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1'
    );
    var _localEndpoints = {
      'registrar_interesse_compra': '/local/registrar-compra',
      'registrar_interesse_venda':  '/local/registrar-venda',
    };
    if (_isLocal && _localEndpoints[toolName]) {
      callPromise = fetch(_localEndpoints[toolName], {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(args),
      })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        return { structuredContent: data };
      });

    /* 1 — MCP Apps Bridge (padrão, preferido) */
    } else if (window.mcpBridge && typeof window.mcpBridge.callTool === 'function') {
      callPromise = Promise.resolve(window.mcpBridge.callTool(toolName, args));

    /* 2 — ChatGPT fallback */
    } else if (window.openai && typeof window.openai.callTool === 'function') {
      callPromise = Promise.resolve(window.openai.callTool(toolName, args));

    /* 3 — postMessage fallback */
    } else {
      callPromise = new Promise(function (resolve, reject) {
        var callId = 'v' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);

        var tid = setTimeout(function () {
          window.removeEventListener('message', handler);
          reject(new Error('TIMEOUT'));
        }, TOOL_CALL_TIMEOUT_MS);

        function handler(ev) {
          /* Valida origem antes de qualquer processamento */
          if (!isTrustedOrigin(ev.origin)) return;
          if (!ev.data || ev.data.callId !== callId) return;

          clearTimeout(tid);
          window.removeEventListener('message', handler);

          if (ev.data.error) reject(new Error('TOOL_ERROR'));
          else resolve(ev.data.result);
        }

        window.addEventListener('message', handler);
        window.parent.postMessage({
          type:   'MCP_CALL_TOOL',
          callId: callId,
          tool:   toolName,
          args:   args,
        }, '*');
      });
    }

    /* Aplica timeout e decrementa contador em qualquer desfecho */
    var timeoutId;
    var withTimeout = new Promise(function (resolve, reject) {
      timeoutId = setTimeout(function () {
        reject(new Error('TIMEOUT'));
      }, TOOL_CALL_TIMEOUT_MS);
      callPromise.then(resolve, reject);
    });

    withTimeout.then(
      function () { clearTimeout(timeoutId); APP.pendingCalls = Math.max(0, APP.pendingCalls - 1); },
      function () { clearTimeout(timeoutId); APP.pendingCalls = Math.max(0, APP.pendingCalls - 1); }
    );

    return withTimeout;
  }

  /* ════════════════════════════════════════════════════════════════════
     VALIDAÇÃO DE ORIGEM
     ════════════════════════════════════════════════════════════════════ */

  function isTrustedOrigin(origin) {
    if (origin === window.location.origin) return true;
    for (var i = 0; i < TRUSTED_ORIGINS.length; i++) {
      if (TRUSTED_ORIGINS[i] === origin) return true;
    }
    return false;
  }

  /* ════════════════════════════════════════════════════════════════════
     GESTÃO DE ESTADOS
     ════════════════════════════════════════════════════════════════════ */

  var elLoad = document.getElementById('s-load');
  var elErr  = document.getElementById('s-err');
  var elEmp  = document.getElementById('s-empty');
  var elMain = document.getElementById('s-main');
  var elSell = document.getElementById('s-sell');

  function showState(name) {
    elLoad.hidden = true;
    elErr.hidden  = true;
    elEmp.hidden  = true;
    elMain.hidden = true;
    if (elSell) elSell.hidden = true;
    if (name === 'load') elLoad.hidden = false;
    if (name === 'err')  elErr.hidden  = false;
    if (name === 'emp')  elEmp.hidden  = false;
    if (name === 'main') elMain.hidden = false;
    if (name === 'sell' && elSell) elSell.hidden = false;
  }

  /**
   * Exibe erro genérico ao usuário.
   * NUNCA expõe stack trace, detalhes de rede ou informações internas.
   */
  function showError(userMessage) {
    var msgEl = document.getElementById('err-msg');
    if (msgEl) msgEl.textContent = userMessage || 'Tente novamente em instantes.';
    showState('err');
  }

  /* ════════════════════════════════════════════════════════════════════
     CONSTRUÇÃO DE CARDS — DOM API exclusivamente
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Cria DOM de um card de veículo seminovo sem nenhum uso de innerHTML.
   * Dados colocados via textContent ou setAttribute.
   * IDs internos (_meta) nunca são renderizados no DOM.
   */
  function buildCard(vehicle, index) {
    /* ID de UI apenas — não é o ID interno do veículo */
    var cid = 'card-' + index;

    var card = h('div', {
      class: 'card',
      role:  'listitem',
      id:    cid,
      'aria-label': vehicle.title || ('Veículo ' + (index + 1)),
    });

    /* ── Imagem ──────────────────────────────────────────────────── */
    var imgUrls = getVehicleImageUrls(vehicle);

    /*
     * Sem nenhuma URL de imagem → descarta o card imediatamente.
     * Não usamos fallback/emoji: apenas veículos com foto real são exibidos.
     */
    if (!imgUrls.length) {
      card.hidden = true;
      return card;
    }

    var imgSection = h('div', { class: 'card-img' });
    var img = document.createElement('img');
    img.setAttribute('alt',      vehicle.title || 'Veículo');
    img.setAttribute('loading',  'lazy');
    img.setAttribute('decoding', 'async');
    imgSection.appendChild(img);
    card.appendChild(imgSection);

    var imgIdx  = 0;
    var imgDone = false;

    /* Esgotou todas as URLs sem imagem válida → descarta o card */
    function tryNextImg() {
      if (imgDone) return;
      if (imgIdx >= imgUrls.length) {
        imgDone = true;
        card.hidden = true;
        return;
      }
      img.src = imgUrls[imgIdx];
      imgIdx++;
    }

    /*
     * Critérios de validação — foto real de veículo:
     *
     *   ratio < 1.05  → retrato / quadrado (pessoa, selfie, ícone) ✗
     *   ratio > 1.90  → banner horizontal muito largo ✗
     *   w   < 200 px  → miniatura / ícone / placeholder ✗
     *   h   < 120 px  → miniatura / ícone / placeholder ✗
     *
     * Faixa válida: 1.05–1.90 (4:3 ≈1.33 · 3:2 ≈1.50 · 16:9 ≈1.78)
     * Resolução mínima: 200 × 120 px
     *
     * LIMITAÇÃO CONHECIDA: validação geométrica não detecta conteúdo
     * (ex.: pessoa em pé fotografada em paisagem). Fotos de veículos
     * profissionais do CDN Saga passam normalmente nessa faixa.
     */
    img.addEventListener('load', function () {
      if (imgDone) return;
      var w = this.naturalWidth, h = this.naturalHeight;
      if (w > 0 && h > 0) {
        if (w < 200 || h < 120)       { tryNextImg(); return; } /* muito pequena */
        var ratio = w / h;
        if (ratio < 1.05 || ratio > 1.90) { tryNextImg(); return; } /* proporção inválida */
        imgDone = true; /* aceita */
      } else {
        imgDone = true; /* dimensões indisponíveis — aceita */
      }
    });

    img.addEventListener('error', function () {
      if (imgDone) return;
      tryNextImg();
    });

    tryNextImg();

    /* ── Corpo ───────────────────────────────────────────────────── */
    var body = h('div', { class: 'card-body' });

    /* Marca (categoria) */
    if (vehicle.brand && typeof vehicle.brand === 'string') {
      body.appendChild(h('div', { class: 'card-category', text: vehicle.brand.toUpperCase() }));
    }

    /* Título */
    body.appendChild(h('div', {
      class: 'card-title',
      text:  vehicle.title || 'Veículo disponível',
    }));

    /* Especificações: linha única "Ano: X • km: Y • câmbio • combustível" */
    var kmVal = vehicle.kmFormatted || fmtKm(vehicle.km);
    var specParts = [
      vehicle.year      ? 'Ano veículo: ' + vehicle.year : null,
      kmVal             ? 'km: '          + kmVal        : null,
      vehicle.transmission || null,
      vehicle.fuel         || null,
    ].filter(function (v) { return v && String(v).trim(); });

    if (specParts.length) {
      body.appendChild(h('div', { class: 'vehicle-specs', text: specParts.join(' • ') }));
    }

    /* Preço — formatado pelo cliente; nunca exibe string bruta do backend */
    var priceSection = h('div', { class: 'price-section' });
    priceSection.appendChild(h('div', { class: 'price-label', text: 'Preço' }));
    priceSection.appendChild(h('div', { class: 'price-value', text: fmtPriceVenda(vehicle.price) }));
    body.appendChild(priceSection);

    /* Botão CTA */
    var ctaBtn = h('button', {
      class:        'btn-cta',
      type:         'button',
      'data-cid':   cid,
      'aria-label': 'Falar com consultor sobre ' + (vehicle.title || ''),
    });
    ctaBtn.appendChild(document.createTextNode('Falar com consultor'));
    body.appendChild(ctaBtn);

    /* Botão "Ver no site" — apenas se link https: válido existir */
    var siteUrl = safeLinkUrl(vehicle.link);
    if (siteUrl) {
      var siteBtn = h('a', {
        class:  'btn-site',
        href:   siteUrl,
        target: '_blank',
        rel:    'noopener noreferrer',
        'aria-label': 'Ver ' + (vehicle.title || 'veículo') + ' no site',
      });
      siteBtn.appendChild(icon('external', 13, 13));
      siteBtn.appendChild(document.createTextNode(' Ver no site'));
      body.appendChild(siteBtn);
    }

    /* Formulário de lead (recolhido) */
    body.appendChild(buildLeadForm(cid, vehicle, index));

    /* Feedback (sucesso/erro) */
    body.appendChild(h('div', {
      class:      'card-feedback',
      id:         'fb-' + cid,
      role:       'status',
      'aria-live': 'polite',
    }));

    /* Localização */
    if (vehicle.location && typeof vehicle.location === 'string') {
      var loc = h('div', { class: 'card-loc' });
      loc.appendChild(icon('pin', 11, 11));
      loc.appendChild(h('span', { text: vehicle.location }));
      body.appendChild(loc);
    }

    card.appendChild(body);
    return card;
  }

  /**
   * Cria o formulário de lead inline do card.
   * Usa apenas textContent e setAttribute — sem innerHTML.
   * O atributo data-index armazena o índice para lookup em APP.data.offers[].
   * Nenhum ID interno do veículo é colocado no DOM.
   */
  function buildLeadForm(cid, offer, index) {
    var wrap = h('div', { class: 'lead-wrap', id: 'fw-' + cid });
    var form = h('div', {
      class: 'lead-form',
      role:  'group',
      'aria-label': 'Formulário de interesse',
    });

    form.appendChild(h('p', { class: 'lead-hint', text: '📲 Um consultor entrará em contato via WhatsApp' }));

    /* Nome */
    var nomeInp = h('input', {
      class:          'form-inp',
      id:             'nm-' + cid,
      type:           'text',
      placeholder:    'Seu nome completo',
      autocomplete:   'name',
      maxlength:      String(MAX_NOME_LEN),
      'aria-label':   'Nome completo',
      'aria-required': 'true',
    });
    form.appendChild(nomeInp);
    form.appendChild(h('div', {
      class: 'field-err',
      id:    'en-' + cid,
      role:  'alert',
    }));

    /* Telefone */
    var telInp = h('input', {
      class:          'form-inp',
      id:             'tl-' + cid,
      type:           'tel',
      placeholder:    'Telefone com DDD',
      autocomplete:   'tel',
      maxlength:      '16',
      'aria-label':   'Telefone com DDD',
      'aria-required': 'true',
    });
    form.appendChild(telInp);
    form.appendChild(h('div', {
      class: 'field-err',
      id:    'et-' + cid,
      role:  'alert',
    }));

    /* Botões */
    var btns = h('div', { class: 'form-btns' });

    var cancelBtn = h('button', {
      class:     'btn-cancel',
      type:      'button',
      'data-cid': cid,
    }, 'Cancelar');

    /* data-index = posição em APP.data.offers[] — não é o ID interno do veículo */
    var confirmBtn = h('button', {
      class:        'btn-confirm',
      type:         'button',
      'data-cid':   cid,
      'data-index': String(index),
    }, 'Confirmar');

    btns.appendChild(cancelBtn);
    btns.appendChild(confirmBtn);
    form.appendChild(btns);
    wrap.appendChild(form);
    return wrap;
  }

  /* ════════════════════════════════════════════════════════════════════
     CONTROLE DO FORMULÁRIO
     ════════════════════════════════════════════════════════════════════ */

  function openForm(cid) {
    /* Fecha qualquer outro formulário aberto */
    var opens = document.querySelectorAll('.lead-wrap.open');
    for (var i = 0; i < opens.length; i++) {
      if (opens[i].id !== 'fw-' + cid) {
        closes(opens[i].id.replace('fw-', ''));
      }
    }
    var wrap = document.getElementById('fw-' + cid);
    if (!wrap) return;
    wrap.classList.add('open');
    var cardEl = document.getElementById(cid);
    if (cardEl) cardEl.classList.add('form-open');
    var nm = document.getElementById('nm-' + cid);
    if (nm) setTimeout(function () { nm.focus(); }, 320);
  }

  function closes(cid) {
    var wrap = document.getElementById('fw-' + cid);
    if (wrap) wrap.classList.remove('open');
    var cardEl = document.getElementById(cid);
    if (cardEl) cardEl.classList.remove('form-open');

    /* Limpa campos e erros */
    var nm  = document.getElementById('nm-' + cid);
    var tl  = document.getElementById('tl-' + cid);
    var en  = document.getElementById('en-' + cid);
    var et  = document.getElementById('et-' + cid);
    if (nm) { nm.value = ''; nm.removeAttribute('aria-invalid'); }
    if (tl) { tl.value = ''; tl.removeAttribute('aria-invalid'); }
    if (en) en.textContent = '';
    if (et) et.textContent = '';
  }

  /* ════════════════════════════════════════════════════════════════════
     FEEDBACK NO CARD
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Exibe feedback de sucesso ou erro no card.
   * NUNCA usa innerHTML com dados externos.
   * fallbackUrl é validado como https: antes de ser usado em href.
   */
  function showCardFeedback(cid, type, title, desc, fallbackUrl) {
    var fb = document.getElementById('fb-' + cid);
    if (!fb) return;

    /* Limpa estado anterior */
    while (fb.firstChild) fb.removeChild(fb.firstChild);

    var emojiMap = { success: '✅', error: '❌', info: 'ℹ️' };
    fb.appendChild(h('span', { class: 'fb-icon', 'aria-hidden': 'true' }, emojiMap[type] || 'ℹ️'));
    if (title) fb.appendChild(h('span', { class: 'fb-title', text: title }));
    if (desc)  fb.appendChild(h('span', { class: 'fb-desc',  text: desc }));

    /* Link de fallback — validado para https: */
    var safeUrl = safeLinkUrl(fallbackUrl);
    if (safeUrl) {
      var lnk = h('a', {
        class:  'fb-link',
        href:   safeUrl,
        target: '_blank',
        rel:    'noopener noreferrer',
        text:   'Acesse o site',
      });
      fb.appendChild(lnk);
    }

    fb.classList.add('visible');

    /* Em sucesso: oculta botão CTA e formulário */
    if (type === 'success') {
      var card    = document.getElementById(cid);
      if (!card) return;
      var ctaBtn  = card.querySelector('.btn-cta');
      var leadWrap = document.getElementById('fw-' + cid);
      var prcSec  = card.querySelector('.price-section');
      if (ctaBtn)   ctaBtn.hidden   = true;
      if (leadWrap) leadWrap.hidden = true;
      if (prcSec)   prcSec.hidden   = true;
    }
  }

  /* ════════════════════════════════════════════════════════════════════
     SUBMISSÃO DO LEAD
     ════════════════════════════════════════════════════════════════════ */

  /**
   * Submete o formulário de interesse de compra.
   *
   * SEGURANÇA:
   * - Valida inputs antes de qualquer uso.
   * - Aplica rate limiting por card.
   * - Anti-double-submit via disabled no botão.
   * - Impede replay via APP.submittedIds.
   * - Dados internos (veiculo_id, dealer_id) vêm de APP.meta — nunca do DOM.
   * - Mensagem de erro ao usuário é sempre genérica.
   */
  function submitLead(cid, offerIndex) {
    var idx = parseInt(offerIndex, 10);
    if (isNaN(idx) || idx < 0) return;

    /* Suporta lista filtrada (_vehicles), vehicles ou offers (compat) */
    var vehicles = APP.data && (APP.data._vehicles || APP.data.vehicles || APP.data.offers);
    if (!Array.isArray(vehicles) || idx >= vehicles.length) return;

    var vehicle = vehicles[idx];
    if (!vehicle) return;

    /* Previne replay no mesmo ciclo de vida da UI */
    var vehicleId = String(vehicle.id != null ? vehicle.id : idx);
    if (APP.submittedIds[vehicleId]) return;

    /* Rate limiting */
    if (isRateLimited(cid)) {
      showCardFeedback(cid, 'error',
        'Aguarde antes de tentar novamente.',
        'Por segurança, aguarde ' + Math.ceil(RATE_LIMIT_PER_CARD_MS / 1000) + ' segundos.');
      return;
    }

    /* Lê e valida inputs do formulário */
    var nomeEl = document.getElementById('nm-' + cid);
    var telEl  = document.getElementById('tl-' + cid);
    var enEl   = document.getElementById('en-' + cid);
    var etEl   = document.getElementById('et-' + cid);
    if (!nomeEl || !telEl) return;

    var nome = nomeEl.value.trim();
    var tel  = telEl.value.trim();

    /* Reset de erros */
    if (enEl) enEl.textContent = '';
    if (etEl) etEl.textContent = '';
    nomeEl.removeAttribute('aria-invalid');
    telEl.removeAttribute('aria-invalid');

    var erroNome = validateNome(nome);
    var erroTel  = validateTelefone(tel);

    if (erroNome) {
      if (enEl) enEl.textContent = erroNome;
      nomeEl.setAttribute('aria-invalid', 'true');
      nomeEl.focus();
      return;
    }
    if (erroTel) {
      if (etEl) etEl.textContent = erroTel;
      telEl.setAttribute('aria-invalid', 'true');
      telEl.focus();
      return;
    }

    /* Verifica capacidade de call */
    if (!canCallTool()) {
      showCardFeedback(cid, 'error', 'Sistema ocupado.', 'Tente novamente em instantes.');
      return;
    }

    /* Desabilita botão — anti-double-submit */
    var card      = document.getElementById(cid);
    var confirmBtn = card && card.querySelector('.btn-confirm');
    if (confirmBtn) {
      confirmBtn.disabled    = true;
      confirmBtn.textContent = 'Aguarde…';
    }

    /*
     * Busca IDs internos em APP.meta (em memória) — NUNCA do DOM.
     * Isso previne IDOR: o cliente não pode manipular IDs no DOM para
     * submeter um lead com dados de outro veículo.
     */
    var metaIds     = (APP.meta && (APP.meta.vehicles_ids || APP.meta.offers_ids)) || {};
    var vehicleMeta = metaIds[vehicleId] || {};

    /* Payload mínimo — apenas o necessário para o tool no servidor */
    var toolArgs = {
      nome_cliente:     nome,
      telefone_cliente: tel,
      titulo_veiculo:   typeof vehicle.title    === 'string' ? vehicle.title    : '',
      loja_unidade:     typeof vehicle.location === 'string' ? vehicle.location : (vehicleMeta.loja || ''),
      preco_formatado:  fmtPriceVenda(vehicle.price),
      /* veiculo_id vem de _meta (servidor), não do DOM — previne IDOR */
      veiculo_id:       vehicleMeta.veiculo_id ? String(vehicleMeta.veiculo_id) : vehicleId,
    };

    dbgLog('→ call', { tool: 'registrar_interesse_compra', args: toolArgs });

    callTool('registrar_interesse_compra', toolArgs)
      .then(function (res) {
        dbgLog('← resp', res);

        /* Tool retornou erro de protocolo (ex: parâmetro inválido) */
        if (res && res.isError) {
          if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar'; }
          dbgLog('← isError', res);
          showCardFeedback(cid, 'error', 'Não foi possível registrar.', 'Tente novamente em instantes.');
          return;
        }

        var sc  = extractStructuredContent(res);
        dbgLog('← sc', sc);
        var ok  = sc.registrado === true;

        if (ok) {
          /* Marca como submetido para prevenir replay */
          APP.submittedIds[vehicleId] = true;
          setRateLimit(cid);

          var primeiroNome = nome.split(/\s+/)[0] || nome;
          showCardFeedback(
            cid, 'success',
            'Pronto, ' + primeiroNome + '!',
            'Em breve um consultor da Saga entrará em contato via WhatsApp.'
          );
        } else {
          /* Reabilita botão para nova tentativa */
          if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar'; }

          /* Em modo local/debug: mostra erro real do servidor no card */
          var errDesc = 'Tente novamente ou acesse o site.';
          if (LOCAL && sc._debug_error) {
            var de = sc._debug_error;
            errDesc = '[DEBUG] mobi=' + de.mobi_error + ' | wh=' + de.wh_ok +
                      (de.mobi_detail ? ' | ' + String(de.mobi_detail).slice(0, 120) : '');
          }
          showCardFeedback(cid, 'error', 'Não foi possível registrar.', errDesc, sc.fallback_url || null);
        }
      })
      .catch(function (err) {
        /* Reabilita botão */
        if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar'; }

        if (typeof console !== 'undefined' && console.error) {
          console.error('[vehicle-offers] callTool error:', err && err.message);
        }

        var isTimeout = err && err.message === 'TIMEOUT';
        var errMsg = isTimeout ? 'Tempo esgotado.' : 'Não foi possível registrar.';
        var errDesc2 = LOCAL ? ('[DEBUG] bridge error: ' + (err && err.message)) : 'Tente novamente em instantes.';
        showCardFeedback(cid, 'error', errMsg, errDesc2);
      });
  }

  /* ════════════════════════════════════════════════════════════════════
     CARROSSEL
     ════════════════════════════════════════════════════════════════════ */

  function setupCarousel(track) {
    var prevBtn = document.getElementById('btn-prev');
    var nextBtn = document.getElementById('btn-next');
    var dotsBar = document.getElementById('dots-bar');
    var idx = 0;

    /* Retorna apenas os cards visíveis (não-ocultos pela validação de imagem) */
    function visCards() {
      return Array.prototype.slice.call(track.querySelectorAll('.card:not([hidden])'));
    }

    /* Passo = largura real do card + gap definido no CSS */
    function cardStep() {
      var cs = visCards();
      if (!cs.length) return 296;
      var gap = parseInt(window.getComputedStyle(track).columnGap, 10) || 16;
      return cs[0].offsetWidth + gap;
    }

    function syncUI(cs) {
      if (!cs) cs = visCards();
      if (prevBtn) prevBtn.disabled = idx <= 0;
      if (nextBtn) nextBtn.disabled = cs.length === 0 || idx >= cs.length - 1;
      var dots = dotsBar ? dotsBar.querySelectorAll('.dot') : [];
      for (var d = 0; d < dots.length; d++) dots[d].classList.toggle('active', d === idx);
    }

    /*
     * Rola o TRACK (container overflow) pelo número de cards necessário.
     * scrollIntoView() rola a página — não funciona dentro de overflow.
     * scrollBy() opera diretamente sobre o scrollLeft do track.
     */
    function goTo(n) {
      var cs = visCards();
      if (!cs.length) return;
      var prev = idx;
      idx = Math.max(0, Math.min(n, cs.length - 1));
      var diff = idx - prev;
      if (diff !== 0) {
        track.scrollBy({ left: diff * cardStep(), behavior: 'smooth' });
      }
      syncUI(cs);
    }

    if (prevBtn) prevBtn.addEventListener('click', function () { goTo(idx - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { goTo(idx + 1); });

    /* Sincroniza índice quando o usuário arrasta o carrossel manualmente */
    track.addEventListener('scroll', function () {
      var cs = visCards();
      if (!cs.length) return;
      var maxScroll = track.scrollWidth - track.clientWidth;
      var pct = maxScroll > 0 ? track.scrollLeft / maxScroll : 0;
      var newIdx = Math.min(Math.round(pct * (cs.length - 1)), cs.length - 1);
      if (newIdx !== idx) { idx = newIdx; syncUI(cs); }
    }, { passive: true });

    /*
     * Após a validação de imagens (assíncrona via load event), alguns cards
     * podem ter sido ocultados. Reconstrói os dots com o count real de cards visíveis.
     */
    setTimeout(function () {
      var cs = visCards();
      if (!dotsBar) return;
      while (dotsBar.firstChild) dotsBar.removeChild(dotsBar.firstChild);
      var n = Math.min(cs.length, 10);
      for (var i = 0; i < n; i++) {
        dotsBar.appendChild(h('div', { class: 'dot' + (i === 0 ? ' active' : '') }));
      }
      idx = 0;
      syncUI(cs);
    }, 1500);

    syncUI();
  }

  function buildDots(n) {
    var bar = document.getElementById('dots-bar');
    if (!bar) return;
    /* Remove dots existentes — sem innerHTML */
    while (bar.firstChild) bar.removeChild(bar.firstChild);
    var cnt = Math.min(n, 10);
    for (var i = 0; i < cnt; i++) {
      bar.appendChild(h('div', { class: 'dot' + (i === 0 ? ' active' : '') }));
    }
  }

  /* ════════════════════════════════════════════════════════════════════
     RENDERIZAÇÃO PRINCIPAL
     ════════════════════════════════════════════════════════════════════ */

  function render(data, meta) {
    dbgLog('render data', data);
    dbgLog('render meta', meta);

    APP.data = data;
    APP.meta = meta || {};

    /* Modo venda — widget de avaliação de veículo */
    if (data.mode === 'sell') {
      renderSell(data);
      return;
    }

    /* Suporta ambas as chaves: vehicles (contrato novo) e offers (compat) */
    var rawVehicles = Array.isArray(data.vehicles)
      ? data.vehicles
      : (Array.isArray(data.offers) ? data.offers : []);

    /* Filtra apenas veículos com imagem https: válida */
    var vehicles = rawVehicles.filter(hasValidImage);

    if (!vehicles.length) {
      showState('emp');
      return;
    }

    /* Armazena lista filtrada para lookup em submitLead */
    APP.data._vehicles = vehicles;

    /* Cabeçalho — apenas textContent */
    var ctx    = (data.searchContext && typeof data.searchContext === 'object') ? data.searchContext : {};
    var period = document.getElementById('hdr-period');
    var agency = document.getElementById('hdr-agency');

    if (period) {
      var parts = [ctx.store, ctx.city].filter(function (v) { return v && typeof v === 'string'; });
      period.textContent = parts.join(' · ') || 'Veículos disponíveis';
    }
    if (agency && typeof ctx.agency === 'string') {
      agency.textContent = ctx.agency;
    }

    /* Contador */
    var cbar = document.getElementById('count-bar');
    if (cbar) {
      cbar.textContent = vehicles.length === 1
        ? '1 veículo encontrado'
        : vehicles.length + ' veículos encontrados';
    }

    /* Cards — DOM API, sem innerHTML */
    var track = document.getElementById('track');
    while (track.firstChild) track.removeChild(track.firstChild);

    vehicles.forEach(function (vehicle, idx) {
      track.appendChild(buildCard(vehicle, idx));
    });

    buildDots(vehicles.length);
    setupCarousel(track);
    showState('main');
  }

  /* ════════════════════════════════════════════════════════════════════
     MODO VENDA — avaliação de veículo + formulário de contato
     ════════════════════════════════════════════════════════════════════ */

  function renderSell(data) {
    var eval_ = (data.evaluation && typeof data.evaluation === 'object') ? data.evaluation : {};
    var ctx   = (data.searchContext && typeof data.searchContext === 'object') ? data.searchContext : {};

    var period = document.getElementById('sell-period');
    var agency = document.getElementById('sell-agency');
    if (period) period.textContent = ctx.city || 'Avaliação de veículo';
    if (agency) agency.textContent = 'Primeira Mão Saga';

    var body = document.getElementById('sell-body');
    if (!body) { showState('err'); return; }
    while (body.firstChild) body.removeChild(body.firstChild);

    body.appendChild(buildSellCard(eval_));
    showState('sell');
  }

  function buildSellCard(eval_) {
    var cid  = 'sell-card';
    var card = h('div', {
      class:       'card',
      role:        'region',
      id:          cid,
      'aria-label': 'Avaliação do seu veículo',
    });

    /* Placeholder de imagem */
    var imgSection = h('div', { class: 'card-img' });
    imgSection.appendChild(h('div', { class: 'img-fallback', 'aria-hidden': 'true' }, '🚗'));
    card.appendChild(imgSection);

    var body = h('div', { class: 'card-body' });

    body.appendChild(h('div', { class: 'card-category', text: 'AVALIAÇÃO' }));
    body.appendChild(h('div', {
      class: 'card-title',
      text:  eval_.vehicleDescription || 'Seu veículo',
    }));

    /* Placa + KM em linha única */
    var sellSpecs = [
      eval_.plate,
      eval_.kmFormatted || fmtKm(eval_.km),
    ].filter(function (v) { return v && String(v).trim(); });

    if (sellSpecs.length) {
      body.appendChild(h('div', { class: 'vehicle-specs', text: sellSpecs.join(' • ') }));
    }

    /* Proposta de compra */
    if (eval_.proposal) {
      var priceSection = h('div', { class: 'price-section', id: 'pr-' + cid });
      priceSection.appendChild(h('div', { class: 'price-label', text: 'Proposta Saga' }));
      priceSection.appendChild(h('div', { class: 'price-value', text: eval_.proposal }));
      body.appendChild(priceSection);
    }

    /* Botão "Ver no site" — sempre visível como alternativa ao formulário */
    var sellSiteBtn = h('a', {
      class:  'btn-site',
      href:   'https://www.primeiramaosaga.com.br/vender/avaliar-veiculo/cliente',
      target: '_blank',
      rel:    'noopener noreferrer',
      'aria-label': 'Fazer avaliação do veículo no site',
    });
    sellSiteBtn.appendChild(icon('external', 13, 13));
    sellSiteBtn.appendChild(document.createTextNode(' Ver avaliação no site'));
    body.appendChild(sellSiteBtn);

    /* Formulário sempre visível */
    var formWrap = h('div', { class: 'lead-wrap open', id: 'fw-' + cid });
    var form = h('div', {
      class:       'lead-form',
      role:        'group',
      'aria-label': 'Formulário de interesse em venda',
    });

    form.appendChild(h('p', { class: 'lead-hint', text: '📲 Um consultor entrará em contato via WhatsApp' }));

    var nomeInp = h('input', {
      class: 'form-inp', id: 'nm-' + cid, type: 'text',
      placeholder: 'Seu nome completo', autocomplete: 'name',
      maxlength: String(MAX_NOME_LEN),
      'aria-label': 'Nome completo', 'aria-required': 'true',
    });
    form.appendChild(nomeInp);
    form.appendChild(h('div', { class: 'field-err', id: 'en-' + cid, role: 'alert' }));

    var telInp = h('input', {
      class: 'form-inp', id: 'tl-' + cid, type: 'tel',
      placeholder: 'Telefone com DDD', autocomplete: 'tel',
      maxlength: '16',
      'aria-label': 'Telefone com DDD', 'aria-required': 'true',
    });
    form.appendChild(telInp);
    form.appendChild(h('div', { class: 'field-err', id: 'et-' + cid, role: 'alert' }));

    /* Botões — grade 1fr 1fr para reaproveitar .form-btns; no CSS sell-mode sobrescreve para 1fr */
    var btns = h('div', { class: 'form-btns' });
    var confirmBtn = h('button', {
      class: 'btn-confirm', type: 'button',
      'data-cid': cid, 'data-mode': 'sell',
    }, 'Confirmar interesse');
    btns.appendChild(confirmBtn);
    form.appendChild(btns);

    formWrap.appendChild(form);
    body.appendChild(formWrap);

    /* Área de feedback */
    body.appendChild(h('div', {
      class: 'card-feedback', id: 'fb-' + cid,
      role: 'status', 'aria-live': 'polite',
    }));

    card.appendChild(body);
    return card;
  }

  function submitSellLead(cid) {
    var eval_ = (APP.data && APP.data.evaluation) || {};

    var nomeEl = document.getElementById('nm-' + cid);
    var telEl  = document.getElementById('tl-' + cid);
    var enEl   = document.getElementById('en-' + cid);
    var etEl   = document.getElementById('et-' + cid);
    if (!nomeEl || !telEl) return;

    var nome = nomeEl.value.trim();
    var tel  = telEl.value.trim();

    if (enEl) enEl.textContent = '';
    if (etEl) etEl.textContent = '';
    nomeEl.removeAttribute('aria-invalid');
    telEl.removeAttribute('aria-invalid');

    var erroNome = validateNome(nome);
    var erroTel  = validateTelefone(tel);

    if (erroNome) {
      if (enEl) enEl.textContent = erroNome;
      nomeEl.setAttribute('aria-invalid', 'true');
      nomeEl.focus();
      return;
    }
    if (erroTel) {
      if (etEl) etEl.textContent = erroTel;
      telEl.setAttribute('aria-invalid', 'true');
      telEl.focus();
      return;
    }

    if (!canCallTool()) {
      showCardFeedback(cid, 'error', 'Sistema ocupado.', 'Tente novamente em instantes.');
      return;
    }

    var card       = document.getElementById(cid);
    var confirmBtn = card && card.querySelector('[data-mode="sell"]');
    if (confirmBtn) {
      confirmBtn.disabled    = true;
      confirmBtn.textContent = 'Aguarde…';
    }

    var toolArgs = {
      nome_cliente:      nome,
      telefone_cliente:  tel,
      veiculo_descricao: typeof eval_.vehicleDescription === 'string' ? eval_.vehicleDescription : '',
      placa:             typeof eval_.plate    === 'string' ? eval_.plate    : '',
      km:                typeof eval_.km       === 'string' ? eval_.km       : '',
      valor_proposta:    typeof eval_.proposal === 'string' ? eval_.proposal : '',
    };

    dbgLog('→ call (venda)', { tool: 'registrar_interesse_venda', args: toolArgs });

    callTool('registrar_interesse_venda', toolArgs)
      .then(function (res) {
        dbgLog('← resp (venda)', res);

        if (res && res.isError) {
          if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar interesse'; }
          dbgLog('← isError (venda)', res);
          showCardFeedback(cid, 'error', 'Não foi possível registrar.', 'Tente novamente em instantes.');
          return;
        }

        var sc = extractStructuredContent(res);
        dbgLog('← sc (venda)', sc);
        var ok = sc.registrado === true;

        if (ok) {
          var primeiroNome = nome.split(/\s+/)[0] || nome;
          showCardFeedback(cid, 'success',
            'Pronto, ' + primeiroNome + '!',
            'Em breve um consultor da Saga entrará em contato via WhatsApp.');
        } else {
          if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar interesse'; }

          var errDescSell = 'Tente novamente ou acesse o site.';
          if (LOCAL && sc._debug_error) {
            var des = sc._debug_error;
            errDescSell = '[DEBUG] mobi=' + des.mobi_error + ' | wh=' + des.wh_ok +
                          (des.mobi_detail ? ' | ' + String(des.mobi_detail).slice(0, 120) : '');
          }
          showCardFeedback(cid, 'error', 'Não foi possível registrar.', errDescSell, sc.fallback_url || null);
        }
      })
      .catch(function (err) {
        if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Confirmar interesse'; }
        if (typeof console !== 'undefined' && console.error) {
          console.error('[vehicle-offers] callTool venda error:', err && err.message);
        }
        var isTimeout = err && err.message === 'TIMEOUT';
        var errMsgSell = isTimeout ? 'Tempo esgotado.' : 'Não foi possível registrar.';
        var errDescSell2 = LOCAL ? ('[DEBUG] bridge error: ' + (err && err.message)) : 'Tente novamente em instantes.';
        showCardFeedback(cid, 'error', errMsgSell, errDescSell2);
      });
  }

  /* ════════════════════════════════════════════════════════════════════
     DELEGAÇÃO DE EVENTOS
     ════════════════════════════════════════════════════════════════════ */

  document.addEventListener('click', function (e) {
    var t = e.target;

    /* Botão CTA: abre formulário */
    var cta = t.closest('.btn-cta');
    if (cta) {
      var cid = cta.getAttribute('data-cid');
      if (cid) openForm(cid);
      return;
    }

    /* Cancelar */
    var cn = t.closest('.btn-cancel');
    if (cn) {
      var cid2 = cn.getAttribute('data-cid');
      if (cid2) closes(cid2);
      return;
    }

    /* Confirmar — não executa se desabilitado */
    var cf = t.closest('.btn-confirm');
    if (cf && !cf.disabled) {
      var cid3  = cf.getAttribute('data-cid');
      var mode3 = cf.getAttribute('data-mode');
      if (mode3 === 'sell') {
        if (cid3) submitSellLead(cid3);
      } else {
        var idx = cf.getAttribute('data-index');
        if (cid3 && idx != null) submitLead(cid3, idx);
      }
      return;
    }

    /* Tentar novamente */
    if (t.id === 'btn-retry') {
      showState('load');
      init();
      return;
    }
  });

  /* Máscara de telefone — aplica apenas em campos do widget */
  document.addEventListener('input', function (e) {
    if (e.target.type === 'tel' && e.target.closest('#app')) {
      e.target.value = maskTel(e.target.value);
    }
  });

  /* Teclado: Enter confirma, Escape cancela */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var lf = e.target.closest('.lead-form');
      if (lf) {
        var cf2 = lf.querySelector('.btn-confirm') || lf.querySelector('.btn-cta[data-mode="sell"]');
        if (cf2 && !cf2.disabled) cf2.click();
      }
      return;
    }
    if (e.key === 'Escape') {
      var lw = e.target.closest('.lead-wrap');
      if (lw) closes(lw.id.replace('fw-', ''));
    }
  });

  /* ════════════════════════════════════════════════════════════════════
     LISTENER postMessage — com validação de origem obrigatória
     ════════════════════════════════════════════════════════════════════ */

  window.addEventListener('message', function (ev) {
    /* Rejeita qualquer mensagem de origem não confiável */
    if (!isTrustedOrigin(ev.origin)) return;
    if (!ev.data || typeof ev.data !== 'object') return;

    var type = ev.data.type;

    if (type === 'MCP_INITIAL_DATA' && ev.data.data && typeof ev.data.data === 'object') {
      render(ev.data.data, ev.data.meta || {});
      return;
    }

    if (type === 'MCP_ERROR') {
      /* Mensagem genérica — nunca expõe detalhes do servidor */
      showError('Não foi possível carregar as ofertas.');
      return;
    }
  });

  /* ════════════════════════════════════════════════════════════════════
     INICIALIZAÇÃO
     ════════════════════════════════════════════════════════════════════ */

  function init() {
    dbgInit();

    /* Reset de estado */
    APP.submittedIds = {};
    APP.rateMap      = {};
    APP.pendingCalls = 0;

    try {
      var d = getData();
      dbgLog('init data', d);
      if (d && typeof d === 'object') {
        render(d, getMeta());
        return;
      }
      waitForData();
    } catch (_) {
      showError('Não foi possível inicializar o widget.');
    }
  }

  function waitForData() {
    var done     = false;
    var attempts = 0;

    var timeout = setTimeout(function () {
      if (!done) showError('Tempo esgotado ao carregar as ofertas.');
    }, INIT_TIMEOUT_MS);

    /* Busca dados direto da API do servidor MCP (local e produção) */
    var isLocal = (
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1'
    );
    var params   = new URLSearchParams(window.location.search);
    var isSell   = params.get('mode') === 'sell';
    var apiUrl;

    if (isSell && isLocal) {
      /* Formulário de venda: apenas local */
      apiUrl = '/local/formulario-venda';
      var sellQ = [];
      if (params.get('veiculo'))  sellQ.push('veiculo='  + encodeURIComponent(params.get('veiculo')));
      if (params.get('placa'))    sellQ.push('placa='    + encodeURIComponent(params.get('placa')));
      if (params.get('km'))       sellQ.push('km='       + encodeURIComponent(params.get('km')));
      if (params.get('proposta')) sellQ.push('proposta=' + encodeURIComponent(params.get('proposta')));
      if (sellQ.length) apiUrl += '?' + sellQ.join('&');
    } else if (!isSell) {
      /* Carrossel de compra — funciona local e produção */
      var cidade   = params.get('cidade')  || 'Goiânia';
      var consulta = params.get('consulta') || '';
      var baseEndpoint = isLocal ? '/local/ofertas' : '/api/ofertas';
      apiUrl = baseEndpoint + '?cidade=' + encodeURIComponent(cidade);
      if (consulta) apiUrl += '&consulta=' + encodeURIComponent(consulta);
    }

    if (apiUrl) {
      fetch(apiUrl)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          if (!done) {
            done = true;
            clearTimeout(timeout);
            clearInterval(poll);
            render(data, {});
          }
        })
        .catch(function (err) {
          if (!done) showError('Erro ao buscar ofertas: ' + err.message);
        });
    }

    /* Polling — alguns hosts injetam dados de forma assíncrona */
    var poll = setInterval(function () {
      attempts++;
      var d = getData();
      if (d && typeof d === 'object') {
        done = true;
        clearTimeout(timeout);
        clearInterval(poll);
        render(d, getMeta());
        return;
      }
      if (attempts >= MAX_POLL_ATTEMPTS) clearInterval(poll);
    }, POLL_INTERVAL_MS);

    /* Escuta postMessage inicial (uma vez) */
    window.addEventListener('message', function onceMsg(ev) {
      if (!isTrustedOrigin(ev.origin)) return;
      if (ev.data && ev.data.type === 'MCP_INITIAL_DATA' && ev.data.data) {
        done = true;
        clearTimeout(timeout);
        clearInterval(poll);
        window.removeEventListener('message', onceMsg);
        render(ev.data.data, ev.data.meta || {});
      }
    });
  }

  /* Inicia */
  init();

})();
