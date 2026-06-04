/**
 * ENCARNADO — Painel de Administração
 * admin.js — Lógica do painel de administração
 */

'use strict';

/* ============================================
   CONFIGURAÇÃO
   ============================================ */

// Credenciais de administrador (alterar conforme necessário)
const ADMIN_USER = 'admin';
const ADMIN_PASS = 'encarnado2025';
const SESSAO_KEY = 'encarnado_admin_sessao';

/* ============================================
   ESTADO
   ============================================ */

const AdminEstado = {
  noticias: [],
  categorias: [],
  config: {},
  noticiaEditando: null,
  idApagar: null,
};

/* ============================================
   AUTENTICAÇÃO
   ============================================ */

const Auth = {
  verificar() {
    return sessionStorage.getItem(SESSAO_KEY) === 'ok';
  },

  login(user, pass) {
    if (user === ADMIN_USER && pass === ADMIN_PASS) {
      sessionStorage.setItem(SESSAO_KEY, 'ok');
      return true;
    }
    return false;
  },

  logout() {
    sessionStorage.removeItem(SESSAO_KEY);
    window.location.reload();
  },
};

/* ============================================
   PERSISTÊNCIA DE DADOS
   ============================================ */

const Dados = {
  /**
   * Carrega dados do localStorage (simulação de servidor)
   * Num servidor real, usaria fetch() para ler/escrever ficheiros
   */
  carregar() {
    const guardado = localStorage.getItem('encarnado_noticias');
    if (guardado) {
      try {
        const dados = JSON.parse(guardado);
        AdminEstado.noticias = dados.noticias || [];
        AdminEstado.categorias = dados.categorias || ['Futebol', 'Modalidades', 'Mercado', 'Formação', 'Opinião'];
        AdminEstado.config = dados.config || {};
        return;
      } catch (e) { /* falha silenciosa */ }
    }
    // Tentar carregar o ficheiro JSON padrão
    this.carregarFicheiro();
  },

  async carregarFicheiro() {
    try {
      const resp = await fetch('../data/noticias.json?v=' + Date.now());
      if (resp.ok) {
        const dados = await resp.json();
        AdminEstado.noticias = dados.noticias || [];
        AdminEstado.categorias = dados.categorias || ['Futebol', 'Modalidades', 'Mercado', 'Formação', 'Opinião'];
        AdminEstado.config = dados.config || {};
        this.guardar();
        Admin.renderizar();
      }
    } catch (e) {
      console.warn('Não foi possível carregar o ficheiro JSON:', e);
    }
  },

  guardar() {
    const dados = {
      noticias: AdminEstado.noticias,
      categorias: AdminEstado.categorias,
      config: { ...AdminEstado.config, ultimaAtualizacao: new Date().toISOString().split('T')[0] },
    };
    localStorage.setItem('encarnado_noticias', JSON.stringify(dados));

    // Atualizar também o ficheiro que o site lê
    // Nota: num servidor real, seria um POST ao servidor.
    // Em ficheiro local, exportamos o JSON para o utilizador copiar.
    this.sincronizarComSite();
  },

  /**
   * Sincroniza dados com o armazenamento do site público
   * (usa o mesmo localStorage, que o site principal também lê)
   */
  sincronizarComSite() {
    // O main.js do site também lê 'encarnado_noticias' como fallback
    // quando não consegue fazer fetch do ficheiro JSON
    const dados = {
      noticias: AdminEstado.noticias,
      categorias: AdminEstado.categorias,
      config: AdminEstado.config,
    };
    localStorage.setItem('encarnado_dados_site', JSON.stringify(dados));
  },

  gerarId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
  },
};

/* ============================================
   TOAST
   ============================================ */

function toast(msg, tipo = 'sucesso', duracao = 3000) {
  let el = document.getElementById('admin-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'admin-toast';
    el.className = 'admin-toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = `admin-toast admin-toast--${tipo} visivel`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('visivel'), duracao);
}

/* ============================================
   EDITOR DE CONTEÚDO
   ============================================ */

const Editor = {
  executar(cmd, valor = null) {
    document.getElementById('editor-conteudo')?.focus();
    document.execCommand(cmd, false, valor);
  },

  inserirLink() {
    const url = prompt('URL do link:');
    if (url) this.executar('createLink', url);
  },

  obterHTML() {
    return document.getElementById('editor-conteudo')?.innerHTML || '';
  },

  definirHTML(html) {
    const el = document.getElementById('editor-conteudo');
    if (el) el.innerHTML = html;
  },
};

/* ============================================
   UPLOAD DE IMAGEM
   ============================================ */

const Upload = {
  imagemBase64: null,

  configurar(inputId, previewId, areaId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    const area = document.getElementById(areaId);

    if (!input || !preview || !area) return;

    area.addEventListener('click', () => input.click());

    area.addEventListener('dragover', e => {
      e.preventDefault();
      area.classList.add('drag-over');
    });

    area.addEventListener('dragleave', () => area.classList.remove('drag-over'));

    area.addEventListener('drop', e => {
      e.preventDefault();
      area.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) this.processar(file, preview, area);
    });

    input.addEventListener('change', e => {
      const file = e.target.files[0];
      if (file) this.processar(file, preview, area);
    });
  },

  processar(file, preview, area) {
    if (!file.type.startsWith('image/')) {
      toast('Apenas imagens são permitidas.', 'erro');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast('A imagem não pode exceder 5MB.', 'erro');
      return;
    }

    const reader = new FileReader();
    reader.onload = e => {
      this.imagemBase64 = e.target.result;
      preview.innerHTML = `<img src="${e.target.result}" alt="Pré-visualização">`;
      preview.classList.add('visivel');
      area.querySelector('.upload-area__texto').textContent = file.name;
    };
    reader.readAsDataURL(file);
  },
};

/* ============================================
   MÓDULO PRINCIPAL ADMIN
   ============================================ */

const Admin = {
  secaoAtiva: 'dashboard',

  renderizar() {
    this.renderDashboard();
    this.renderListaNoticias();
  },

  /* ---- Dashboard ---- */
  renderDashboard() {
    const stats = document.getElementById('stats');
    if (!stats) return;

    const total = AdminEstado.noticias.length;
    const destaques = AdminEstado.noticias.filter(n => n.destaque).length;
    const porCategoria = AdminEstado.categorias.reduce((acc, cat) => {
      acc[cat] = AdminEstado.noticias.filter(n => n.categoria === cat).length;
      return acc;
    }, {});
    const catMaisNoticias = Object.entries(porCategoria).sort((a, b) => b[1] - a[1])[0];

    stats.innerHTML = `
      <div class="stat-card stat-card--vermelho">
        <div class="stat-card__label">Total de notícias</div>
        <div class="stat-card__valor">${total}</div>
        <div class="stat-card__sub">publicadas</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Em destaque</div>
        <div class="stat-card__valor">${destaques}</div>
        <div class="stat-card__sub">notícia${destaques !== 1 ? 's' : ''}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">Categorias</div>
        <div class="stat-card__valor">${AdminEstado.categorias.length}</div>
        <div class="stat-card__sub">disponíveis</div>
      </div>
      <div class="stat-card stat-card--verde">
        <div class="stat-card__label">Categoria + ativa</div>
        <div class="stat-card__valor" style="font-size:18px;margin-top:4px;">${catMaisNoticias ? catMaisNoticias[0] : '—'}</div>
        <div class="stat-card__sub">${catMaisNoticias ? catMaisNoticias[1] + ' notícias' : ''}</div>
      </div>
    `;

    // Últimas notícias no dashboard
    const ultimas = document.getElementById('ultimas-noticias');
    if (ultimas) {
      const recentes = [...AdminEstado.noticias]
        .sort((a, b) => new Date(b.data) - new Date(a.data))
        .slice(0, 5);

      ultimas.innerHTML = recentes.length > 0
        ? recentes.map(n => this._rowNoticia(n)).join('')
        : '<tr><td colspan="5" class="sem-noticias">Ainda não há notícias publicadas.</td></tr>';
    }
  },

  /* ---- Lista de Notícias ---- */
  renderListaNoticias(filtro = '') {
    const tbody = document.getElementById('lista-noticias-body');
    if (!tbody) return;

    let lista = [...AdminEstado.noticias].sort((a, b) => new Date(b.data) - new Date(a.data));

    if (filtro) {
      const f = filtro.toLowerCase();
      lista = lista.filter(n =>
        n.titulo.toLowerCase().includes(f) ||
        n.categoria.toLowerCase().includes(f) ||
        n.autor.toLowerCase().includes(f)
      );
    }

    tbody.innerHTML = lista.length > 0
      ? lista.map(n => this._rowNoticia(n, true)).join('')
      : '<tr><td colspan="6" class="sem-noticias">Não foram encontradas notícias.</td></tr>';
  },

  _rowNoticia(n, acoes = false) {
    const data = new Date(n.data).toLocaleDateString('pt-PT');
    const acoesHTML = acoes ? `
      <td>
        <div class="acoes-tabela">
          <button class="btn-acao btn-acao--editar" onclick="Admin.editarNoticia('${n.id}')">Editar</button>
          <button class="btn-acao btn-acao--destaque ${n.destaque ? 'ativo' : ''}" onclick="Admin.alternarDestaque('${n.id}')" title="${n.destaque ? 'Remover destaque' : 'Colocar em destaque'}">★</button>
          <button class="btn-acao btn-acao--apagar" onclick="Admin.confirmarApagar('${n.id}')">Apagar</button>
        </div>
      </td>
    ` : '';

    return `
      <tr>
        <td><span class="tabela-titulo" title="${n.titulo}">${n.titulo}</span></td>
        <td><span class="badge badge--cinza">${n.categoria}</span></td>
        <td>${n.autor}</td>
        <td>${data}</td>
        <td>${n.destaque ? '<span class="badge badge--vermelho">★ Destaque</span>' : '<span class="badge badge--cinza">Normal</span>'}</td>
        ${acoesHTML}
      </tr>
    `;
  },

  /* ---- Formulário Nova/Editar Notícia ---- */
  abrirFormulario(id = null) {
    AdminEstado.noticiaEditando = id;
    Upload.imagemBase64 = null;

    const titulo = document.getElementById('form-titulo');
    if (titulo) {
      titulo.textContent = id ? 'Editar Notícia' : 'Nova Notícia';
    }

    // Preencher categorias
    const selectCat = document.getElementById('campo-categoria');
    if (selectCat) {
      selectCat.innerHTML = AdminEstado.categorias.map(c => `<option value="${c}">${c}</option>`).join('');
    }

    if (id) {
      const noticia = AdminEstado.noticias.find(n => n.id === id);
      if (!noticia) return;

      document.getElementById('campo-titulo').value = noticia.titulo;
      document.getElementById('campo-subtitulo').value = noticia.subtitulo || '';
      document.getElementById('campo-autor').value = noticia.autor;
      document.getElementById('campo-data').value = noticia.data;
      document.getElementById('campo-categoria').value = noticia.categoria;
      document.getElementById('campo-destaque').checked = noticia.destaque;
      Editor.definirHTML(noticia.conteudo || '');

      const preview = document.getElementById('upload-preview');
      if (noticia.imagem && preview) {
        preview.innerHTML = `<img src="${noticia.imagem}" alt="Imagem atual">`;
        preview.classList.add('visivel');
        Upload.imagemBase64 = noticia.imagem;
      }
    } else {
      // Limpar formulário
      document.getElementById('campo-titulo').value = '';
      document.getElementById('campo-subtitulo').value = '';
      document.getElementById('campo-autor').value = '';
      document.getElementById('campo-data').value = new Date().toISOString().split('T')[0];
      document.getElementById('campo-destaque').checked = false;
      Editor.definirHTML('');

      const preview = document.getElementById('upload-preview');
      if (preview) { preview.innerHTML = ''; preview.classList.remove('visivel'); }
    }

    this.mostrarSecao('formulario');
  },

  guardarNoticia(previsualizacao = false) {
    const titulo = document.getElementById('campo-titulo').value.trim();
    const subtitulo = document.getElementById('campo-subtitulo').value.trim();
    const autor = document.getElementById('campo-autor').value.trim();
    const data = document.getElementById('campo-data').value;
    const categoria = document.getElementById('campo-categoria').value;
    const destaque = document.getElementById('campo-destaque').checked;
    const conteudo = Editor.obterHTML().trim();

    // Validação
    if (!titulo) { toast('O título é obrigatório.', 'erro'); return; }
    if (!autor) { toast('O autor é obrigatório.', 'erro'); return; }
    if (!data) { toast('A data é obrigatória.', 'erro'); return; }
    if (!conteudo) { toast('O conteúdo é obrigatório.', 'erro'); return; }

    const noticia = {
      id: AdminEstado.noticiaEditando || Dados.gerarId(),
      titulo,
      subtitulo,
      autor,
      data,
      categoria,
      imagem: Upload.imagemBase64 || '',
      conteudo,
      destaque,
      galeria: [],
      tags: [categoria],
      leituras: 0,
    };

    if (previsualizacao) {
      this.abrirPreview(noticia);
      return;
    }

    if (AdminEstado.noticiaEditando) {
      const idx = AdminEstado.noticias.findIndex(n => n.id === AdminEstado.noticiaEditando);
      if (idx !== -1) {
        noticia.leituras = AdminEstado.noticias[idx].leituras || 0;
        AdminEstado.noticias[idx] = noticia;
      }
      toast('Notícia atualizada com sucesso!', 'sucesso');
    } else {
      // Se é destaque, retirar de outros
      if (destaque) {
        AdminEstado.noticias.forEach(n => n.destaque = false);
      }
      AdminEstado.noticias.unshift(noticia);
      toast('Notícia publicada com sucesso!', 'sucesso');
    }

    Dados.guardar();
    this.mostrarSecao('noticias');
    this.renderListaNoticias();
    this.renderDashboard();
  },

  editarNoticia(id) {
    this.abrirFormulario(id);
  },

  alternarDestaque(id) {
    const noticia = AdminEstado.noticias.find(n => n.id === id);
    if (!noticia) return;

    if (!noticia.destaque) {
      AdminEstado.noticias.forEach(n => n.destaque = false);
    }
    noticia.destaque = !noticia.destaque;

    Dados.guardar();
    this.renderListaNoticias();
    this.renderDashboard();
    toast(noticia.destaque ? 'Definido como destaque.' : 'Destaque removido.');
  },

  confirmarApagar(id) {
    AdminEstado.idApagar = id;
    document.getElementById('modal-apagar').classList.add('visivel');
  },

  apagarNoticia() {
    const id = AdminEstado.idApagar;
    AdminEstado.noticias = AdminEstado.noticias.filter(n => n.id !== id);
    Dados.guardar();
    this.fecharModal();
    this.renderListaNoticias();
    this.renderDashboard();
    toast('Notícia apagada.', 'sucesso');
  },

  fecharModal() {
    document.getElementById('modal-apagar').classList.remove('visivel');
    AdminEstado.idApagar = null;
  },

  /* ---- Pré-visualização ---- */
  abrirPreview(noticia) {
    const overlay = document.getElementById('preview-overlay');
    const conteudo = document.getElementById('preview-conteudo');
    if (!overlay || !conteudo) return;

    conteudo.innerHTML = `
      <span class="preview-categoria">${noticia.categoria}</span>
      <h1 class="preview-titulo">${noticia.titulo}</h1>
      ${noticia.subtitulo ? `<p class="preview-subtitulo">${noticia.subtitulo}</p>` : ''}
      <div class="preview-meta">${noticia.autor} · ${new Date(noticia.data).toLocaleDateString('pt-PT', { day: 'numeric', month: 'long', year: 'numeric' })}</div>
      ${noticia.imagem ? `<img class="preview-imagem" src="${noticia.imagem}" alt="${noticia.titulo}">` : ''}
      <div class="preview-corpo">${noticia.conteudo}</div>
    `;

    overlay.classList.add('visivel');
  },

  fecharPreview() {
    document.getElementById('preview-overlay').classList.remove('visivel');
  },

  /* ---- Exportar JSON ---- */
  exportarJSON() {
    const dados = {
      noticias: AdminEstado.noticias,
      categorias: AdminEstado.categorias,
      config: { ...AdminEstado.config, ultimaAtualizacao: new Date().toISOString().split('T')[0] },
    };
    const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'noticias.json';
    a.click();
    URL.revokeObjectURL(url);
    toast('Ficheiro noticias.json exportado! Copie-o para a pasta /data/', 'sucesso', 5000);
  },

  /* ---- Importar JSON ---- */
  importarJSON(file) {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const dados = JSON.parse(e.target.result);
        if (dados.noticias) {
          AdminEstado.noticias = dados.noticias;
          AdminEstado.categorias = dados.categorias || AdminEstado.categorias;
          Dados.guardar();
          this.renderizar();
          toast(`Importado com sucesso! ${dados.noticias.length} notícias.`, 'sucesso');
        } else {
          toast('Formato inválido.', 'erro');
        }
      } catch {
        toast('Erro ao ler o ficheiro.', 'erro');
      }
    };
    reader.readAsText(file);
  },

  /* ---- Navegação entre secções ---- */
  mostrarSecao(secao) {
    this.secaoAtiva = secao;
    document.querySelectorAll('.admin-secao').forEach(el => el.style.display = 'none');
    const alvo = document.getElementById(`secao-${secao}`);
    if (alvo) alvo.style.display = 'block';

    document.querySelectorAll('.sidebar-nav__link').forEach(el => {
      el.classList.toggle('ativo', el.dataset.secao === secao);
    });

    // Atualizar título topbar
    const titulos = {
      dashboard: 'Dashboard',
      noticias: 'Gerir Notícias',
      formulario: AdminEstado.noticiaEditando ? 'Editar Notícia' : 'Nova Notícia',
      categorias: 'Gerir Categorias',
    };
    const topbarTitulo = document.getElementById('topbar-titulo');
    if (topbarTitulo) topbarTitulo.textContent = titulos[secao] || '';
  },
};

/* ============================================
   GESTÃO DE CATEGORIAS
   ============================================ */

const Categorias = {
  renderizar() {
    const lista = document.getElementById('lista-categorias');
    if (!lista) return;

    lista.innerHTML = AdminEstado.categorias.map((cat, i) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--borda);">
        <span style="font-size:14px;font-weight:500;">${cat}</span>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="badge badge--cinza">${AdminEstado.noticias.filter(n => n.categoria === cat).length} notícias</span>
          <button class="btn-acao btn-acao--apagar" onclick="Categorias.remover(${i})">Remover</button>
        </div>
      </div>
    `).join('');
  },

  adicionar() {
    const input = document.getElementById('nova-categoria');
    const nome = input.value.trim();
    if (!nome) { toast('Introduza um nome para a categoria.', 'erro'); return; }
    if (AdminEstado.categorias.includes(nome)) { toast('Esta categoria já existe.', 'erro'); return; }
    AdminEstado.categorias.push(nome);
    Dados.guardar();
    this.renderizar();
    input.value = '';
    toast(`Categoria "${nome}" adicionada.`);
  },

  remover(idx) {
    const cat = AdminEstado.categorias[idx];
    const emUso = AdminEstado.noticias.filter(n => n.categoria === cat).length;
    if (emUso > 0) {
      toast(`Não é possível remover: ${emUso} notícia(s) utilizam esta categoria.`, 'erro');
      return;
    }
    if (confirm(`Remover categoria "${cat}"?`)) {
      AdminEstado.categorias.splice(idx, 1);
      Dados.guardar();
      this.renderizar();
      toast(`Categoria "${cat}" removida.`);
    }
  },
};

/* ============================================
   INICIALIZAÇÃO
   ============================================ */

function iniciarAdmin() {
  // Verificar autenticação
  const loginWrapper = document.getElementById('login-wrapper');
  const adminWrapper = document.getElementById('admin-wrapper');

  if (!loginWrapper || !adminWrapper) return;

  if (Auth.verificar()) {
    loginWrapper.style.display = 'none';
    adminWrapper.style.display = 'grid';
    carregarAdmin();
  } else {
    loginWrapper.style.display = 'flex';
    adminWrapper.style.display = 'none';
  }

  // Formulário de login
  const formLogin = document.getElementById('form-login');
  if (formLogin) {
    formLogin.addEventListener('submit', e => {
      e.preventDefault();
      const user = document.getElementById('login-user').value;
      const pass = document.getElementById('login-pass').value;
      const erro = document.getElementById('login-erro');

      if (Auth.login(user, pass)) {
        loginWrapper.style.display = 'none';
        adminWrapper.style.display = 'grid';
        carregarAdmin();
      } else {
        erro.classList.add('visivel');
        document.getElementById('login-pass').value = '';
      }
    });
  }
}

function carregarAdmin() {
  Dados.carregar();
  Admin.renderizar();
  Admin.mostrarSecao('dashboard');

  // Upload de imagem
  Upload.configurar('upload-input', 'upload-preview', 'upload-area');

  // Pesquisa na lista
  const pesquisaLista = document.getElementById('pesquisa-lista');
  if (pesquisaLista) {
    pesquisaLista.addEventListener('input', e => Admin.renderListaNoticias(e.target.value));
  }

  // Data atual no formulário
  const campoData = document.getElementById('campo-data');
  if (campoData && !campoData.value) {
    campoData.value = new Date().toISOString().split('T')[0];
  }

  // Categorias
  Categorias.renderizar();

  // Import JSON
  const importInput = document.getElementById('import-input');
  if (importInput) {
    importInput.addEventListener('change', e => {
      if (e.target.files[0]) Admin.importarJSON(e.target.files[0]);
    });
  }
}

document.addEventListener('DOMContentLoaded', iniciarAdmin);
