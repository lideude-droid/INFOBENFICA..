/**
 * ENCARNADO — main.js
 * Frontend conectado à API Flask/SQLite
 */

'use strict';

/* ── API helper ──────────────────────────────────────────── */

const API = {
  base: '',

  async get(path) {
    const r = await fetch(this.base + path);
    if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
    return r.json();
  },

  async post(path, body) {
    const r = await fetch(this.base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return r.json();
  },
};

/* ── Estado ──────────────────────────────────────────────── */

const S = {
  noticias:   [],
  categorias: [],
  favoritos:  JSON.parse(localStorage.getItem('enc_favs') || '[]'),
  tema:       localStorage.getItem('enc_tema') || 'claro',
  filtro:     'Todos',
};

/* ── Utilitários ─────────────────────────────────────────── */

function fmtData(s) {
  if (!s) return '';
  return new Date(s).toLocaleDateString('pt-PT', { day: 'numeric', month: 'long', year: 'numeric' });
}
function fmtDataCurta(s) {
  if (!s) return '';
  return new Date(s).toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
function truncar(t, n) {
  if (!t) return '';
  const s = t.replace(/<[^>]*>/g, '');
  return s.length > n ? s.slice(0, n).trimEnd() + '…' : s;
}

function toast(msg, ms = 3000) {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast'; el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), ms);
}

function loading(on) {
  let bar = document.getElementById('loading-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'loading-bar'; bar.className = 'loading-bar';
    document.body.prepend(bar);
  }
  if (on) { bar.style.width = '70%'; bar.style.opacity = '1'; bar.classList.remove('done'); }
  else     { bar.style.width = '100%'; setTimeout(() => bar.classList.add('done'), 200); }
}

function placeholder() {
  return `<div class="hero-placeholder">⬜</div>`;
}

/* ── Tema ────────────────────────────────────────────────── */

function setTema(t) {
  S.tema = t;
  document.documentElement.setAttribute('data-tema', t);
  localStorage.setItem('enc_tema', t);
  const btn = document.getElementById('btn-tema');
  if (btn) btn.textContent = t === 'escuro' ? '☀ Claro' : '☾ Escuro';
}
function toggleTema() { setTema(S.tema === 'claro' ? 'escuro' : 'claro'); }

/* ── Favoritos ───────────────────────────────────────────── */

const Favs = {
  has(id) { return S.favoritos.includes(id); },
  toggle(id) {
    if (this.has(id)) {
      S.favoritos = S.favoritos.filter(f => f !== id);
      toast('Removido dos favoritos');
    } else {
      S.favoritos.push(id);
      toast('Guardado nos favoritos ♥');
    }
    localStorage.setItem('enc_favs', JSON.stringify(S.favoritos));
    this.updateUI(id);
    this.updateCount();
  },
  updateUI(id) {
    document.querySelectorAll(`[data-fav="${id}"]`).forEach(el => {
      el.classList.toggle('on', this.has(id));
      el.textContent = this.has(id) ? '♥' : '♡';
    });
  },
  updateCount() {
    const el = document.getElementById('fav-count');
    if (el) el.textContent = S.favoritos.length > 0 ? ` (${S.favoritos.length})` : '';
  },
};

/* ── Pesquisa ────────────────────────────────────────────── */

let searchTimer = null;

async function doSearch(q) {
  clearTimeout(searchTimer);
  const box = document.getElementById('search-results');
  if (!box) return;

  if (!q || q.length < 2) { box.classList.remove('open'); return; }

  searchTimer = setTimeout(async () => {
    try {
      const data = await API.get(`/api/noticias?q=${encodeURIComponent(q)}&limite=5`);
      renderSearchResults(box, data.noticias, q);
    } catch { box.classList.remove('open'); }
  }, 240);
}

function renderSearchResults(box, results, q) {
  if (!results.length) {
    box.innerHTML = `<div class="search-results__head">Pesquisa: "${q}"</div><div class="search-empty">Nenhum resultado encontrado.</div>`;
  } else {
    box.innerHTML = `
      <div class="search-results__head">${results.length} resultado${results.length !== 1 ? 's' : ''}</div>
      ${results.map(n => `
        <div class="search-result-item" onclick="goto('/noticia?id=${n.id}')">
          ${n.imagem ? `<img src="${n.imagem}" alt="${n.titulo}" loading="lazy">` : '<div style="width:56px;height:42px;background:var(--cinza-claro);border-radius:2px;flex-shrink:0"></div>'}
          <div>
            <h4>${n.titulo}</h4>
            <span>${n.categoria} · ${fmtDataCurta(n.data)}</span>
          </div>
        </div>
      `).join('')}
    `;
  }
  box.classList.add('open');
}

/* ── Navegação ───────────────────────────────────────────── */

function goto(url) { window.location.href = url; }

async function regLeitura(id) {
  try { await API.post(`/api/noticias/${id}/leitura`, {}); } catch {}
}

/* ── Render cartão ───────────────────────────────────────── */

function cardHTML(n) {
  return `
    <article class="news-card fade-in" onclick="goto('/noticia?id=${n.id}')">
      <div class="news-card__thumb">
        ${n.imagem
          ? `<img src="${n.imagem}" alt="${n.titulo}" loading="lazy" onerror="this.style.display='none'">`
          : `<div style="width:100%;height:100%;background:var(--cinza-claro)"></div>`}
        <span class="news-card__cat">${n.categoria}</span>
      </div>
      <div class="news-card__body">
        <h2 class="news-card__title">${n.titulo}</h2>
        ${n.subtitulo ? `<p class="news-card__sub">${truncar(n.subtitulo, 100)}</p>` : ''}
        <div class="news-card__meta">
          <span>${n.autor} · ${fmtDataCurta(n.data)}</span>
          <button class="news-card__fav ${Favs.has(n.id) ? 'on' : ''}"
            data-fav="${n.id}"
            onclick="event.stopPropagation(); Favs.toggle('${n.id}')"
            aria-label="Favorito">
            ${Favs.has(n.id) ? '♥' : '♡'}
          </button>
        </div>
      </div>
    </article>
  `;
}

/* ── Página Inicial ──────────────────────────────────────── */

async function initHome() {
  loading(true);
  try {
    const [cats, destaque, recentes, maisLidas] = await Promise.all([
      API.get('/api/categorias'),
      API.get('/api/noticias/destaque'),
      API.get('/api/noticias/recentes?limite=9'),
      API.get('/api/noticias/mais-lidas'),
    ]);
    S.categorias = cats;
    renderHero(destaque, recentes);
    renderGrid(recentes, cats);
    renderMaisLidas(maisLidas);
  } catch (e) {
    console.error(e);
  }
  loading(false);
  setTimeout(activateFadeIn, 120);
  Favs.updateCount();
}

function renderHero(destaque, recentes) {
  const sec = document.getElementById('hero-section');
  if (!sec) return;

  const secundarias = recentes.filter(n => n.id !== destaque?.id).slice(0, 4);

  sec.innerHTML = `
    <div class="hero-grid">
      <div class="hero-main" onclick="goto('/noticia?id=${destaque?.id}')">
        ${destaque?.imagem
          ? `<img src="${destaque.imagem}" alt="${destaque.titulo}" loading="lazy">`
          : `<div class="hero-placeholder">📰</div>`}
        ${destaque ? `
        <div class="hero-main__overlay">
          <span class="hero-main__cat">${destaque.categoria}</span>
          <h1 class="hero-main__title">${destaque.titulo}</h1>
          <span class="hero-main__meta">${destaque.autor} · ${fmtData(destaque.data)}</span>
        </div>` : '<div style="padding:24px;color:#888;font-family:var(--fonte-ui)">Sem notícias ainda.</div>'}
      </div>
      <aside class="hero-secondary">
        ${secundarias.length ? secundarias.map(n => `
          <article class="hero-card" onclick="goto('/noticia?id=${n.id}')">
            ${n.imagem ? `<img src="${n.imagem}" alt="${n.titulo}" loading="lazy">` : `<div style="width:104px;height:70px;background:var(--cinza-claro);border-radius:2px"></div>`}
            <div>
              <div class="hero-card__cat">${n.categoria}</div>
              <h3 class="hero-card__title">${n.titulo}</h3>
              <span class="hero-card__meta">${fmtDataCurta(n.data)}</span>
            </div>
          </article>
        `).join('') : '<p style="font-family:var(--fonte-ui);font-size:13px;color:var(--cinza-texto);padding:16px">Sem notícias secundárias.</p>'}
      </aside>
    </div>
  `;
}

function renderGrid(noticias, cats, filtro = 'Todos') {
  const sec = document.getElementById('news-section');
  if (!sec) return;

  const lista = filtro === 'Todos' ? noticias : noticias.filter(n => n.categoria === filtro);
  const catList = ['Todos', ...cats];

  sec.innerHTML = `
    <div class="section-head">
      <span class="section-head__title">Últimas <em>Notícias</em></span>
    </div>
    <div class="cat-filters">
      ${catList.map(c => `
        <button class="cat-btn ${S.filtro === c ? 'active' : ''}"
          onclick="filterCat('${c}')">
          ${c}
        </button>
      `).join('')}
    </div>
    <div class="news-grid" id="news-grid">
      ${lista.length
        ? lista.map(cardHTML).join('')
        : '<p style="font-family:var(--fonte-ui);font-size:13px;color:var(--cinza-texto);grid-column:1/-1;padding:28px 0">Sem notícias nesta categoria.</p>'}
    </div>
  `;
  setTimeout(activateFadeIn, 50);
}

async function filterCat(cat) {
  S.filtro = cat;
  loading(true);
  try {
    const data = await API.get(`/api/noticias${cat !== 'Todos' ? `?categoria=${encodeURIComponent(cat)}` : '?limite=9'}`);
    const grid = document.getElementById('news-grid');
    if (grid) {
      grid.innerHTML = data.noticias.length
        ? data.noticias.map(cardHTML).join('')
        : '<p style="font-family:var(--fonte-ui);font-size:13px;color:var(--cinza-texto);grid-column:1/-1;padding:28px 0">Sem notícias nesta categoria.</p>';
    }
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.toggle('active', b.textContent.trim() === cat));
    setTimeout(activateFadeIn, 50);
  } catch {}
  loading(false);
}

function renderMaisLidas(lista) {
  const sec = document.getElementById('most-read');
  if (!sec) return;
  sec.innerHTML = `
    <div class="section-head"><span class="section-head__title">Mais <em>Lidas</em></span></div>
    <div class="top-reads">
      ${lista.map((n, i) => `
        <article class="top-read-item" onclick="goto('/noticia?id=${n.id}')">
          <span class="top-read-item__num">${String(i + 1).padStart(2, '0')}</span>
          <div>
            <div class="top-read-item__cat">${n.categoria}</div>
            <h3 class="top-read-item__title">${n.titulo}</h3>
          </div>
        </article>
      `).join('')}
    </div>
  `;
}

/* ── Página de Notícia ───────────────────────────────────── */

async function initNoticia() {
  const id = new URLSearchParams(location.search).get('id');
  const wrap = document.getElementById('article-wrap');
  if (!id || !wrap) return;

  loading(true);
  try {
    const n = await API.get(`/api/noticias/${id}`);
    await regLeitura(id);
    renderNoticia(n, wrap);
    renderRelacionadas(n.relacionadas || []);

    // SEO dinâmico
    document.title = `${n.titulo} — Encarnado`;
    setMeta('description', n.subtitulo || n.titulo);
    setMeta('og:title', n.titulo, true);
    setMeta('og:description', n.subtitulo || '', true);
    if (n.imagem) setMeta('og:image', n.imagem, true);
  } catch {
    wrap.innerHTML = `
      <div class="page-404">
        <div class="page-404__code">404</div>
        <h1 class="page-404__title">Notícia não encontrada</h1>
        <p class="page-404__text">Esta notícia não existe ou foi removida.</p>
        <a href="/" class="btn-back">← Voltar ao início</a>
      </div>
    `;
  }
  loading(false);
  Favs.updateCount();
}

function setMeta(name, content, og = false) {
  const sel = og ? `meta[property="${name}"]` : `meta[name="${name}"]`;
  document.querySelector(sel)?.setAttribute('content', content);
}

function renderNoticia(n, wrap) {
  const isFav = Favs.has(n.id);
  const galeriaHTML = n.galeria?.length ? `
    <div style="margin:28px 0">
      <div style="font-family:var(--fonte-ui);font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--cinza-texto);margin-bottom:10px">Galeria</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px">
        ${n.galeria.map(img => `<img src="${img}" style="aspect-ratio:4/3;object-fit:cover;border-radius:2px;cursor:pointer" loading="lazy">`).join('')}
      </div>
    </div>
  ` : '';

  wrap.innerHTML = `
    <div class="article-wrap">
      <nav class="article-breadcrumb">
        <a href="/">Início</a>
        <span class="article-breadcrumb__sep">/</span>
        <a href="/?categoria=${encodeURIComponent(n.categoria)}">${n.categoria}</a>
        <span class="article-breadcrumb__sep">/</span>
        <span>${truncar(n.titulo, 42)}</span>
      </nav>

      <span class="article-cat">${n.categoria}</span>
      <h1 class="article-title">${n.titulo}</h1>
      ${n.subtitulo ? `<p class="article-sub">${n.subtitulo}</p>` : ''}

      <div class="article-meta">
        <div class="article-meta__left">
          <span class="article-author">${n.autor}</span>
          <span class="article-date">${fmtData(n.data)}</span>
        </div>
        <div class="share-btns">
          <button class="share-btn" onclick="copyLink()">🔗 Copiar link</button>
          <button class="share-btn fav-btn ${isFav ? 'on' : ''}"
            data-fav="${n.id}"
            onclick="Favs.toggle('${n.id}')">
            ${isFav ? '♥' : '♡'} Favorito
          </button>
        </div>
      </div>

      ${n.imagem ? `<img class="article-img" src="${n.imagem}" alt="${n.titulo}">
        <p class="article-img-caption">${n.titulo}</p>` : ''}

      <div class="article-body">${n.conteudo}</div>

      ${galeriaHTML}

      <div class="article-share-bottom">
        <span class="article-share-bottom__label">Partilhar</span>
        <div class="share-btns">
          <button class="share-btn" onclick="shareFB()">Facebook</button>
          <button class="share-btn" onclick="shareTW()">X / Twitter</button>
          <button class="share-btn" onclick="copyLink()">Copiar link</button>
        </div>
      </div>
    </div>
  `;
}

function renderRelacionadas(lista) {
  const sec = document.getElementById('related-section');
  if (!sec || !lista.length) return;
  sec.innerHTML = `
    <div class="related-section">
      <div class="section-head"><span class="section-head__title">Notícias <em>Relacionadas</em></span></div>
      <div class="news-grid">${lista.map(cardHTML).join('')}</div>
    </div>
  `;
  setTimeout(activateFadeIn, 80);
}

function copyLink() {
  navigator.clipboard.writeText(location.href)
    .then(() => toast('Link copiado ✓'))
    .catch(() => toast('Não foi possível copiar'));
}
function shareFB() { window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(location.href)}`, '_blank', 'width=600,height=400'); }
function shareTW() { window.open(`https://twitter.com/intent/tweet?url=${encodeURIComponent(location.href)}&text=${encodeURIComponent(document.title)}`, '_blank', 'width=600,height=400'); }

/* ── Página Favoritos ────────────────────────────────────── */

async function initFavs() {
  const wrap = document.getElementById('favs-wrap');
  if (!wrap) return;
  if (!S.favoritos.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state__icon">♡</div><p>Ainda não guardou nenhuma notícia.</p></div>`;
    return;
  }
  loading(true);
  try {
    // Buscar cada notícia individualmente (podem ser poucas)
    const promises = S.favoritos.map(id => API.get(`/api/noticias/${id}`).catch(() => null));
    const results  = (await Promise.all(promises)).filter(Boolean);
    wrap.innerHTML = results.length
      ? `<div class="news-grid">${results.map(cardHTML).join('')}</div>`
      : `<div class="empty-state"><div class="empty-state__icon">♡</div><p>Notícias não encontradas.</p></div>`;
    setTimeout(activateFadeIn, 80);
  } catch {}
  loading(false);
}

/* ── Header comportamento ────────────────────────────────── */

function initHeader() {
  // Scroll shadow
  window.addEventListener('scroll', () => {
    document.querySelector('.site-header')?.classList.toggle('scrolled', scrollY > 8);
  }, { passive: true });

  // Menu mobile
  const btnMenu = document.getElementById('btn-menu');
  const nav     = document.getElementById('site-nav');
  btnMenu?.addEventListener('click', () => {
    nav?.classList.toggle('open');
    btnMenu.setAttribute('aria-expanded', nav?.classList.contains('open'));
  });

  // Pesquisa
  const inp = document.getElementById('search-input');
  inp?.addEventListener('input', e => doSearch(e.target.value));
  inp?.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('search-results')?.classList.remove('open');
  });

  // Fechar dropdown ao clicar fora
  document.addEventListener('click', e => {
    const sf = document.querySelector('.search-form');
    const sr = document.getElementById('search-results');
    if (sr && !sf?.contains(e.target)) sr.classList.remove('open');
    if (nav && !nav.contains(e.target) && !btnMenu?.contains(e.target)) nav.classList.remove('open');
  });

  // Data
  const dateEl = document.getElementById('header-date');
  if (dateEl) dateEl.textContent = new Date().toLocaleDateString('pt-PT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  // Nav activo
  const page = location.pathname;
  const cat  = new URLSearchParams(location.search).get('categoria');
  document.querySelectorAll('.site-nav__link').forEach(a => {
    const href   = a.getAttribute('href') || '';
    const catA   = new URLSearchParams(href.split('?')[1] || '').get('categoria');
    const isHome = (page === '/' || page === '/index.html') && !cat && !href.includes('categoria');
    a.classList.toggle('active', isHome ? href === '/' : (cat && catA === cat));
  });

  Favs.updateCount();
}

/* ── Fade-in scroll ─────────────────────────────────────── */

function activateFadeIn() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); obs.unobserve(e.target); } });
  }, { threshold: 0.08 });
  document.querySelectorAll('.fade-in:not(.in)').forEach(el => obs.observe(el));
}

/* ── Arranque ────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', async () => {
  setTema(S.tema);
  initHeader();

  const path = location.pathname;
  if (path === '/' || path === '/index.html' || path === '') {
    // Verificar filtro de categoria via querystring
    const cat = new URLSearchParams(location.search).get('categoria');
    if (cat) S.filtro = cat;
    await initHome();
    if (cat) filterCat(cat);
  } else if (path === '/noticia' || path === '/noticia.html') {
    await initNoticia();
  } else if (path === '/favoritos' || path === '/favoritos.html') {
    await initFavs();
  }

  setTimeout(activateFadeIn, 300);
});
