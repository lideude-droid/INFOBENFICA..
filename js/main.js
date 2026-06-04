/**
 * ENCARNADO — Portal de Notícias do Benfica
 * main.js — Lógica principal do portal
 */

'use strict';

/* ============================================
   ESTADO GLOBAL
   ============================================ */

const Estado = {
  noticias: [],
  categorias: [],
  config: {},
  favoritos: JSON.parse(localStorage.getItem('encarnado_favoritos') || '[]'),
  tema: localStorage.getItem('encarnado_tema') || 'claro',
  filtroAtivo: 'Todos',
};

/* ============================================
   UTILITÁRIOS
   ============================================ */

const Utils = {
  /**
   * Formata data para pt-PT
   */
  formatarData(dataStr) {
    if (!dataStr) return '';
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-PT', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  },

  /**
   * Formata data curta
   */
  formatarDataCurta(dataStr) {
    if (!dataStr) return '';
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  },

  /**
   * Trunca texto
   */
  truncar(texto, max) {
    if (!texto) return '';
    const semHtml = texto.replace(/<[^>]*>/g, '');
    if (semHtml.length <= max) return semHtml;
    return semHtml.substring(0, max).trimEnd() + '…';
  },

  /**
   * Gera URL amigável a partir do título
   */
  slugify(texto) {
    return texto
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-');
  },

  /**
   * Mostra toast de notificação
   */
  toast(mensagem, duracao = 3000) {
    let el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = mensagem;
    el.classList.add('visivel');
    clearTimeout(el._timeout);
    el._timeout = setTimeout(() => el.classList.remove('visivel'), duracao);
  },

  /**
   * Placeholder SVG para imagens
   */
  placeholderSVG() {
    return `<div class="img-placeholder">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
      </svg>
    </div>`;
  },
};

/* ============================================
   CARREGAMENTO DE DADOS
   ============================================ */

async function carregarDados() {
  // 1. Tentar ler dados guardados pelo painel de administração (localStorage)
  const guardado = localStorage.getItem('encarnado_noticias');
  if (guardado) {
    try {
      const dados = JSON.parse(guardado);
      Estado.noticias = dados.noticias || [];
      Estado.categorias = dados.categorias || [];
      Estado.config = dados.config || {};
      return true;
    } catch (e) { /* continua para o fetch */ }
  }

  // 2. Fallback: carregar do ficheiro JSON estático
  try {
    const resp = await fetch('data/noticias.json?v=' + Date.now());
    if (!resp.ok) throw new Error('Erro ao carregar dados');
    const dados = await resp.json();
    Estado.noticias = dados.noticias || [];
    Estado.categorias = dados.categorias || [];
    Estado.config = dados.config || {};
    // Guardar no localStorage para próximas visitas
    localStorage.setItem('encarnado_noticias', JSON.stringify(dados));
    return true;
  } catch (e) {
    console.warn('Não foi possível carregar noticias.json:', e);
    Estado.noticias = [];
    return false;
  }
}

/* ============================================
   TEMA CLARO / ESCURO
   ============================================ */

function aplicarTema(tema) {
  document.documentElement.setAttribute('data-tema', tema);
  Estado.tema = tema;
  localStorage.setItem('encarnado_tema', tema);
  const btn = document.getElementById('btn-tema');
  if (btn) {
    btn.innerHTML = tema === 'escuro'
      ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg> Claro`
      : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> Escuro`;
  }
}

function alternarTema() {
  const novoTema = Estado.tema === 'claro' ? 'escuro' : 'claro';
  aplicarTema(novoTema);
}

/* ============================================
   FAVORITOS
   ============================================ */

const Favoritos = {
  adicionar(id) {
    if (!Estado.favoritos.includes(id)) {
      Estado.favoritos.push(id);
      this.guardar();
      Utils.toast('Adicionado aos favoritos ♥');
    }
  },

  remover(id) {
    Estado.favoritos = Estado.favoritos.filter(f => f !== id);
    this.guardar();
    Utils.toast('Removido dos favoritos');
  },

  alternar(id) {
    if (this.tem(id)) this.remover(id);
    else this.adicionar(id);
    this.atualizarBotoes(id);
    this.atualizarContador();
  },

  tem(id) {
    return Estado.favoritos.includes(id);
  },

  guardar() {
    localStorage.setItem('encarnado_favoritos', JSON.stringify(Estado.favoritos));
  },

  atualizarBotoes(id) {
    document.querySelectorAll(`[data-fav-id="${id}"]`).forEach(btn => {
      btn.classList.toggle('ativo', this.tem(id));
      btn.setAttribute('aria-label', this.tem(id) ? 'Remover dos favoritos' : 'Guardar nos favoritos');
    });
  },

  atualizarContador() {
    const cont = document.getElementById('favoritos-contador');
    if (cont) {
      cont.textContent = Estado.favoritos.length > 0 ? ` (${Estado.favoritos.length})` : '';
    }
  },
};

/* ============================================
   PESQUISA
   ============================================ */

const Pesquisa = {
  timeout: null,

  pesquisar(termo) {
    clearTimeout(this.timeout);
    const container = document.getElementById('pesquisa-resultados');
    if (!container) return;

    if (!termo || termo.length < 2) {
      container.classList.remove('visivel');
      return;
    }

    this.timeout = setTimeout(() => {
      const termoLower = termo.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      const resultados = Estado.noticias.filter(n => {
        const titulo = n.titulo.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        const subtitulo = (n.subtitulo || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        return titulo.includes(termoLower) || subtitulo.includes(termoLower);
      }).slice(0, 5);

      this.renderResultados(container, resultados, termo);
    }, 250);
  },

  renderResultados(container, resultados, termo) {
    if (resultados.length === 0) {
      container.innerHTML = `
        <div class="pesquisa-resultados__titulo">Resultados para "${termo}"</div>
        <div class="pesquisa-sem-resultados">Nenhuma notícia encontrada.</div>
      `;
    } else {
      container.innerHTML = `
        <div class="pesquisa-resultados__titulo">${resultados.length} resultado${resultados.length !== 1 ? 's' : ''}</div>
        ${resultados.map(n => `
          <div class="pesquisa-resultado-item" onclick="abrirNoticia('${n.id}')">
            ${n.imagem
              ? `<img src="${n.imagem}" alt="${n.titulo}" loading="lazy" onerror="this.style.display='none'">`
              : ''
            }
            <div class="pesquisa-resultado-item__info">
              <h4>${n.titulo}</h4>
              <span>${n.categoria} · ${Utils.formatarDataCurta(n.data)}</span>
            </div>
          </div>
        `).join('')}
      `;
    }
    container.classList.add('visivel');
  },

  fechar() {
    const container = document.getElementById('pesquisa-resultados');
    if (container) container.classList.remove('visivel');
  },
};

/* ============================================
   NAVEGAÇÃO
   ============================================ */

function abrirNoticia(id) {
  // Incrementa leituras
  const noticia = Estado.noticias.find(n => n.id === id);
  if (noticia) {
    const leituras = JSON.parse(localStorage.getItem('encarnado_leituras') || '{}');
    leituras[id] = (leituras[id] || 0) + 1;
    localStorage.setItem('encarnado_leituras', JSON.stringify(leituras));
  }
  window.location.href = `noticia.html?id=${id}`;
}

function abrirCategoria(cat) {
  window.location.href = `index.html?categoria=${encodeURIComponent(cat)}`;
}

/* ============================================
   RENDER COMPONENTES
   ============================================ */

function renderCartaoNoticia(noticia) {
  const eFavorito = Favoritos.tem(noticia.id);
  return `
    <article class="noticia-card fade-in" data-id="${noticia.id}">
      <div class="noticia-card__imagem-wrapper" onclick="abrirNoticia('${noticia.id}')">
        ${noticia.imagem
          ? `<img class="noticia-card__imagem" src="${noticia.imagem}" alt="${noticia.titulo}" loading="lazy" onerror="this.parentElement.innerHTML='${Utils.placeholderSVG().replace(/'/g, "\\'")}';">`
          : Utils.placeholderSVG()
        }
        <span class="noticia-card__categoria">${noticia.categoria}</span>
      </div>
      <div class="noticia-card__corpo">
        <h2 class="noticia-card__titulo" onclick="abrirNoticia('${noticia.id}')">${noticia.titulo}</h2>
        ${noticia.subtitulo ? `<p class="noticia-card__subtitulo">${Utils.truncar(noticia.subtitulo, 100)}</p>` : ''}
        <div class="noticia-card__meta">
          <div>
            <span class="noticia-card__autor">${noticia.autor}</span>
            <span class="noticia-card__data"> · ${Utils.formatarDataCurta(noticia.data)}</span>
          </div>
          <button class="noticia-card__fav ${eFavorito ? 'ativo' : ''}"
            data-fav-id="${noticia.id}"
            aria-label="${eFavorito ? 'Remover dos favoritos' : 'Guardar nos favoritos'}"
            onclick="event.stopPropagation(); Favoritos.alternar('${noticia.id}')">
            ${eFavorito ? '♥' : '♡'}
          </button>
        </div>
      </div>
    </article>
  `;
}

function renderItemLista(noticia) {
  return `
    <article class="noticia-lista-item fade-in" onclick="abrirNoticia('${noticia.id}')">
      ${noticia.imagem
        ? `<img class="noticia-lista-item__imagem" src="${noticia.imagem}" alt="${noticia.titulo}" loading="lazy">`
        : `<div class="noticia-lista-item__imagem" style="background:var(--cinza-claro)"></div>`
      }
      <div>
        <span class="noticia-lista-item__categoria">${noticia.categoria}</span>
        <h3 class="noticia-lista-item__titulo">${noticia.titulo}</h3>
        <span class="noticia-lista-item__meta">${noticia.autor} · ${Utils.formatarDataCurta(noticia.data)}</span>
      </div>
    </article>
  `;
}

/* ============================================
   PÁGINA INICIAL
   ============================================ */

function renderPaginaInicial(categoriafiltro) {
  const destaque = Estado.noticias.find(n => n.destaque) || Estado.noticias[0];
  const noticiasRestantes = Estado.noticias.filter(n => n !== destaque);
  const destaquesSec = noticiasRestantes.slice(0, 3);

  // Bloco destaque principal
  const secDestaque = document.getElementById('sec-destaque');
  if (secDestaque && destaque) {
    const semSec = noticiasRestantes.filter(n => !destaquesSec.includes(n));
    secDestaque.innerHTML = `
      <div class="secao-destaque__inner">
        <div class="destaque-principal" onclick="abrirNoticia('${destaque.id}')">
          ${destaque.imagem
            ? `<img class="destaque-principal__imagem" src="${destaque.imagem}" alt="${destaque.titulo}" loading="lazy">`
            : `<div style="width:100%;height:100%;background:var(--cinza-claro)"></div>`
          }
          <div class="destaque-principal__overlay">
            <span class="destaque-principal__categoria">${destaque.categoria}</span>
            <h1 class="destaque-principal__titulo">${destaque.titulo}</h1>
            <span class="destaque-principal__meta">${destaque.autor} · ${Utils.formatarData(destaque.data)}</span>
          </div>
        </div>
        <aside class="destaques-secundarios">
          ${destaquesSec.map(n => `
            <article class="destaque-secundario" onclick="abrirNoticia('${n.id}')">
              ${n.imagem
                ? `<img class="destaque-secundario__imagem" src="${n.imagem}" alt="${n.titulo}" loading="lazy">`
                : `<div class="destaque-secundario__imagem" style="background:var(--cinza-claro)"></div>`
              }
              <div class="destaque-secundario__conteudo">
                <span class="destaque-secundario__categoria">${n.categoria}</span>
                <h3 class="destaque-secundario__titulo">${n.titulo}</h3>
                <span class="destaque-secundario__meta">${Utils.formatarDataCurta(n.data)}</span>
              </div>
            </article>
          `).join('')}
          ${destaquesSec.length === 0 ? '<p style="font-family:var(--fonte-ui);font-size:13px;color:var(--cinza-texto);padding:16px;">Sem outras notícias em destaque.</p>' : ''}
        </aside>
      </div>
    `;
  }

  // Grelha de notícias
  const secNoticias = document.getElementById('sec-noticias');
  if (secNoticias) {
    let lista = noticiasRestantes;

    if (categoriafiltro && categoriafiltro !== 'Todos') {
      lista = Estado.noticias.filter(n => n.categoria === categoriafiltro);
    }

    // Filtros de categoria
    const categorias = ['Todos', ...Estado.categorias];
    const filtrosHTML = `
      <div class="filtro-categorias">
        ${categorias.map(c => `
          <button class="filtro-btn ${(Estado.filtroAtivo === c) ? 'ativo' : ''}"
            onclick="filtrarCategoria('${c}')">
            ${c}
          </button>
        `).join('')}
      </div>
    `;

    secNoticias.innerHTML = `
      <div class="secao-cabecalho">
        <span class="secao-cabecalho__titulo">Últimas <span>Notícias</span></span>
        <span class="secao-cabecalho__ver-mais">Ver todas →</span>
      </div>
      ${filtrosHTML}
      <div class="noticias-grelha" id="grelha-noticias">
        ${lista.length > 0
          ? lista.slice(0, 9).map(renderCartaoNoticia).join('')
          : '<p style="font-family:var(--fonte-ui);font-size:14px;color:var(--cinza-texto);grid-column:1/-1;padding:32px 0;">Não existem notícias nesta categoria.</p>'
        }
      </div>
    `;

    // Ativar animações
    setTimeout(ativarFadeIn, 100);
  }

  // Mais lidas
  renderMaisLidas();
}

function filtrarCategoria(cat) {
  Estado.filtroAtivo = cat;
  const lista = cat === 'Todos'
    ? Estado.noticias
    : Estado.noticias.filter(n => n.categoria === cat);

  const grelha = document.getElementById('grelha-noticias');
  if (grelha) {
    grelha.innerHTML = lista.length > 0
      ? lista.slice(0, 9).map(renderCartaoNoticia).join('')
      : '<p style="font-family:var(--fonte-ui);font-size:14px;color:var(--cinza-texto);grid-column:1/-1;padding:32px 0;">Não existem notícias nesta categoria.</p>';
    setTimeout(ativarFadeIn, 50);
  }

  // Atualiza botões filtro
  document.querySelectorAll('.filtro-btn').forEach(btn => {
    btn.classList.toggle('ativo', btn.textContent.trim() === cat);
  });
}

function renderMaisLidas() {
  const container = document.getElementById('mais-lidas');
  if (!container) return;

  const leituras = JSON.parse(localStorage.getItem('encarnado_leituras') || '{}');

  const ordenadas = [...Estado.noticias]
    .sort((a, b) => (leituras[b.id] || 0) - (leituras[a.id] || 0))
    .slice(0, 5);

  container.innerHTML = `
    <div class="secao-cabecalho">
      <span class="secao-cabecalho__titulo">Mais <span>Lidas</span></span>
    </div>
    <div class="mais-lidas-lista">
      ${ordenadas.map((n, i) => `
        <article class="mais-lida-item" onclick="abrirNoticia('${n.id}')">
          <span class="mais-lida-item__numero">${String(i + 1).padStart(2, '0')}</span>
          <div>
            <span class="mais-lida-item__categoria">${n.categoria}</span>
            <h3 class="mais-lida-item__titulo">${n.titulo}</h3>
          </div>
        </article>
      `).join('')}
    </div>
  `;
}

/* ============================================
   PÁGINA DE NOTÍCIA
   ============================================ */

function renderPaginaNoticia(id) {
  const noticia = Estado.noticias.find(n => n.id === id);
  const container = document.getElementById('conteudo-noticia');
  if (!container) return;

  if (!noticia) {
    container.innerHTML = `
      <div class="pagina-404">
        <div class="pagina-404__codigo">404</div>
        <h1 class="pagina-404__titulo">Notícia não encontrada</h1>
        <p class="pagina-404__texto">Esta notícia não existe ou foi removida.</p>
        <a href="index.html" class="btn-voltar">Voltar ao início</a>
      </div>
    `;
    return;
  }

  // SEO
  document.title = `${noticia.titulo} — Encarnado`;
  document.querySelector('meta[name="description"]')?.setAttribute('content', noticia.subtitulo || noticia.titulo);
  document.querySelector('meta[property="og:title"]')?.setAttribute('content', noticia.titulo);
  document.querySelector('meta[property="og:description"]')?.setAttribute('content', noticia.subtitulo || '');
  if (noticia.imagem) {
    document.querySelector('meta[property="og:image"]')?.setAttribute('content', noticia.imagem);
  }

  const eFavorito = Favoritos.tem(noticia.id);
  const galeriaHTML = noticia.galeria && noticia.galeria.length > 0 ? `
    <div class="noticia-galeria">
      <div class="noticia-galeria__titulo">Galeria de imagens</div>
      <div class="noticia-galeria__grelha">
        ${noticia.galeria.map(img => `
          <img class="noticia-galeria__imagem" src="${img}" alt="Fotografia" loading="lazy">
        `).join('')}
      </div>
    </div>
  ` : '';

  container.innerHTML = `
    <div class="pagina-noticia">
      <nav class="noticia-breadcrumb" aria-label="Caminho de navegação">
        <a href="index.html">Início</a>
        <span class="noticia-breadcrumb__sep">/</span>
        <a href="index.html?categoria=${encodeURIComponent(noticia.categoria)}">${noticia.categoria}</a>
        <span class="noticia-breadcrumb__sep">/</span>
        <span>${Utils.truncar(noticia.titulo, 40)}</span>
      </nav>

      <header class="noticia-cabecalho">
        <span class="noticia-categoria-tag">${noticia.categoria}</span>
        <h1 class="noticia-titulo">${noticia.titulo}</h1>
        ${noticia.subtitulo ? `<p class="noticia-subtitulo">${noticia.subtitulo}</p>` : ''}
        <div class="noticia-meta-barra">
          <div class="noticia-meta-barra__esquerda">
            <span class="noticia-autor">${noticia.autor}</span>
            <span class="noticia-data">${Utils.formatarData(noticia.data)}</span>
          </div>
          <div class="botoes-partilha">
            <button class="btn-partilha btn-partilha--copiar" onclick="copiarLink()">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
              Copiar link
            </button>
            <button class="btn-partilha noticia-card__fav ${eFavorito ? 'ativo' : ''}"
              data-fav-id="${noticia.id}"
              onclick="Favoritos.alternar('${noticia.id}')">
              ${eFavorito ? '♥' : '♡'} Favorito
            </button>
          </div>
        </div>
      </header>

      ${noticia.imagem ? `
        <img class="noticia-imagem-principal" src="${noticia.imagem}" alt="${noticia.titulo}">
        <p class="noticia-imagem-legenda">Imagem: ${noticia.titulo}</p>
      ` : ''}

      <div class="noticia-corpo">
        ${noticia.conteudo}
      </div>

      ${galeriaHTML}

      <div class="noticia-partilha-inferior">
        <span class="noticia-partilha-inferior__label">Partilhar</span>
        <div class="botoes-partilha">
          <button class="btn-partilha" onclick="partilharFacebook()">Facebook</button>
          <button class="btn-partilha" onclick="partilharTwitter()">X / Twitter</button>
          <button class="btn-partilha btn-partilha--copiar" onclick="copiarLink()">Copiar link</button>
        </div>
      </div>
    </div>
  `;

  // Notícias relacionadas
  renderRelacionadas(noticia);
}

function renderRelacionadas(noticia) {
  const container = document.getElementById('noticias-relacionadas');
  if (!container) return;

  const relacionadas = Estado.noticias
    .filter(n => n.id !== noticia.id && n.categoria === noticia.categoria)
    .slice(0, 3);

  if (relacionadas.length === 0) return;

  container.innerHTML = `
    <div class="noticias-relacionadas">
      <div class="secao-cabecalho">
        <span class="secao-cabecalho__titulo">Notícias <span>Relacionadas</span></span>
      </div>
      <div class="noticias-grelha" style="grid-template-columns:repeat(3,1fr)">
        ${relacionadas.map(renderCartaoNoticia).join('')}
      </div>
    </div>
  `;

  setTimeout(ativarFadeIn, 100);
}

/* ============================================
   PARTILHA
   ============================================ */

function copiarLink() {
  navigator.clipboard.writeText(window.location.href)
    .then(() => Utils.toast('Link copiado para a área de transferência'))
    .catch(() => Utils.toast('Não foi possível copiar o link'));
}

function partilharFacebook() {
  const url = encodeURIComponent(window.location.href);
  window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, '_blank', 'width=600,height=400');
}

function partilharTwitter() {
  const url = encodeURIComponent(window.location.href);
  const texto = encodeURIComponent(document.title);
  window.open(`https://twitter.com/intent/tweet?url=${url}&text=${texto}`, '_blank', 'width=600,height=400');
}

/* ============================================
   ANIMAÇÕES SCROLL
   ============================================ */

function ativarFadeIn() {
  const observador = new IntersectionObserver((entradas) => {
    entradas.forEach(entrada => {
      if (entrada.isIntersecting) {
        entrada.target.classList.add('visivel');
        observador.unobserve(entrada.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in:not(.visivel)').forEach(el => {
    observador.observe(el);
  });
}

/* ============================================
   HEADER COMPORTAMENTO
   ============================================ */

function iniciarHeader() {
  const header = document.querySelector('.site-header');
  if (!header) return;

  // Sombra no scroll
  window.addEventListener('scroll', () => {
    header.classList.toggle('com-sombra', window.scrollY > 10);
  }, { passive: true });

  // Menu mobile
  const btnMenu = document.getElementById('btn-menu-mobile');
  const nav = document.getElementById('nav-principal');
  if (btnMenu && nav) {
    btnMenu.addEventListener('click', () => {
      nav.classList.toggle('aberto');
      btnMenu.setAttribute('aria-expanded', nav.classList.contains('aberto'));
    });
  }

  // Fechar menu ao clicar fora
  document.addEventListener('click', e => {
    if (nav && !nav.contains(e.target) && !btnMenu?.contains(e.target)) {
      nav.classList.remove('aberto');
    }
  });

  // Pesquisa
  const inputPesquisa = document.getElementById('input-pesquisa');
  if (inputPesquisa) {
    inputPesquisa.addEventListener('input', e => Pesquisa.pesquisar(e.target.value));
    inputPesquisa.addEventListener('keydown', e => {
      if (e.key === 'Escape') Pesquisa.fechar();
    });
  }

  document.addEventListener('click', e => {
    const pesquisaArea = document.querySelector('.pesquisa-form');
    const resultados = document.getElementById('pesquisa-resultados');
    if (resultados && !pesquisaArea?.contains(e.target)) {
      Pesquisa.fechar();
    }
  });

  // Ativo no nav
  const paginaAtual = window.location.pathname.split('/').pop() || 'index.html';
  const params = new URLSearchParams(window.location.search);
  const catAtual = params.get('categoria');

  document.querySelectorAll('.nav-principal__link').forEach(link => {
    const href = link.getAttribute('href') || '';
    const catLink = new URLSearchParams(href.split('?')[1] || '').get('categoria');

    if (href.includes(paginaAtual) || (catAtual && catLink === catAtual)) {
      link.classList.add('ativo');
    }
  });

  // Data no header topo
  const dataEl = document.getElementById('header-data');
  if (dataEl) {
    dataEl.textContent = new Date().toLocaleDateString('pt-PT', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    });
  }
}

/* ============================================
   INICIALIZAÇÃO
   ============================================ */

async function iniciar() {
  // Aplicar tema guardado
  aplicarTema(Estado.tema);

  // Carregar dados
  await carregarDados();

  // Iniciar header
  iniciarHeader();

  // Favoritos contador
  Favoritos.atualizarContador();

  // Determinar página
  const pagina = window.location.pathname.split('/').pop() || 'index.html';
  const params = new URLSearchParams(window.location.search);

  if (pagina === 'index.html' || pagina === '' || pagina === '/') {
    const catFiltro = params.get('categoria');
    if (catFiltro) Estado.filtroAtivo = catFiltro;
    renderPaginaInicial(catFiltro);
  } else if (pagina === 'noticia.html') {
    const id = params.get('id');
    if (id) renderPaginaNoticia(id);
  } else if (pagina === 'favoritos.html') {
    renderPaginaFavoritos();
  }

  // Lazy load imagens
  if ('IntersectionObserver' in window) {
    const imgObserver = new IntersectionObserver(entradas => {
      entradas.forEach(e => {
        if (e.isIntersecting) {
          const img = e.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            imgObserver.unobserve(img);
          }
        }
      });
    });
    document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));
  }

  // Animações iniciais
  setTimeout(ativarFadeIn, 200);
}

/* ============================================
   PÁGINA DE FAVORITOS
   ============================================ */

function renderPaginaFavoritos() {
  const container = document.getElementById('conteudo-favoritos');
  if (!container) return;

  const lista = Estado.noticias.filter(n => Estado.favoritos.includes(n.id));

  if (lista.length === 0) {
    container.innerHTML = `
      <div class="favoritos-vazio">
        <div class="favoritos-vazio__icone">♡</div>
        <p class="favoritos-vazio__texto">Ainda não guardou nenhuma notícia nos favoritos.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="noticias-grelha">
      ${lista.map(renderCartaoNoticia).join('')}
    </div>
  `;

  setTimeout(ativarFadeIn, 100);
}

/* ============================================
   ARRANQUE
   ============================================ */

document.addEventListener('DOMContentLoaded', iniciar);
