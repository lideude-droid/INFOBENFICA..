/**
 * ENCARNADO — admin.js
 * Painel de administração conectado à API
 */

'use strict';

/* ── API ─────────────────────────────────────────────────── */

const API = {
  async req(method, path, body, isForm) {
    const opts = { method, credentials: 'include' };
    if (isForm) { opts.body = body; }
    else if (body) { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.erro || `Erro ${r.status}`);
    return data;
  },
  get:    (p)       => API.req('GET', p),
  post:   (p, b)    => API.req('POST', p, b),
  put:    (p, b)    => API.req('PUT', p, b),
  del:    (p)       => API.req('DELETE', p),
  upload: (p, form) => API.req('POST', p, form, true),
};

/* ── Estado ──────────────────────────────────────────────── */

const S = { editId: null, deleteId: null };

/* ── Toast ───────────────────────────────────────────────── */

function toast(msg, type = 'ok') {
  let el = document.getElementById('admin-toast');
  if (!el) { el = document.createElement('div'); el.id = 'admin-toast'; el.className = 'a-toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.className = `a-toast a-toast--${type} show`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3200);
}

/* ── Auth ────────────────────────────────────────────────── */

async function checkAuth() {
  try {
    const d = await API.get('/api/auth/verificar');
    return d.autenticado;
  } catch { return false; }
}

async function doLogin(e) {
  e.preventDefault();
  const user = document.getElementById('l-user').value.trim();
  const pass = document.getElementById('l-pass').value;
  const err  = document.getElementById('l-err');
  err.style.display = 'none';
  try {
    await API.post('/api/auth/login', { utilizador: user, senha: pass });
    showAdmin();
  } catch {
    err.style.display = 'block';
    document.getElementById('l-pass').value = '';
  }
}

async function doLogout() {
  await API.post('/api/auth/logout', {}).catch(() => {});
  location.reload();
}

/* ── Layout ──────────────────────────────────────────────── */

function showAdmin() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('admin-screen').style.display = 'flex';
  loadStats();
  showSection('dashboard');
}

function showSection(id) {
  document.querySelectorAll('.a-section').forEach(s => s.style.display = 'none');
  const el = document.getElementById(`sec-${id}`);
  if (el) el.style.display = 'block';
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.sec === id));
  const titles = { dashboard: 'Dashboard', noticias: 'Gerir Notícias', form: S.editId ? 'Editar Notícia' : 'Nova Notícia', categorias: 'Categorias' };
  const tb = document.getElementById('topbar-title');
  if (tb) tb.textContent = titles[id] || '';
  if (id === 'noticias') loadNoticias();
  if (id === 'categorias') loadCategorias();
}

/* ── Dashboard ───────────────────────────────────────────── */

async function loadStats() {
  try {
    const d = await API.get('/api/admin/stats');
    const el = document.getElementById('stats-grid');
    if (el) el.innerHTML = `
      <div class="a-stat"><div class="a-stat__label">Total</div><div class="a-stat__val red">${d.total}</div><div class="a-stat__sub">notícias</div></div>
      <div class="a-stat"><div class="a-stat__label">Destaque</div><div class="a-stat__val">${d.destaques}</div><div class="a-stat__sub">em destaque</div></div>
      <div class="a-stat"><div class="a-stat__label">Categorias</div><div class="a-stat__val">${d.total_categorias}</div><div class="a-stat__sub">activas</div></div>
      <div class="a-stat"><div class="a-stat__label">Mais activa</div><div class="a-stat__val sm">${d.por_categoria[0]?.categoria || '—'}</div><div class="a-stat__sub">${d.por_categoria[0] ? d.por_categoria[0].n + ' notícias' : ''}</div></div>
    `;
    const tb = document.getElementById('recent-tbody');
    if (tb) tb.innerHTML = d.recentes.map(n => rowHTML(n, false)).join('') || '<tr><td colspan="5" class="empty-td">Sem notícias.</td></tr>';
  } catch (e) { console.error(e); }
}

/* ── Lista de notícias ───────────────────────────────────── */

async function loadNoticias(q = '', cat = '') {
  const tb = document.getElementById('noticias-tbody');
  if (!tb) return;
  tb.innerHTML = '<tr><td colspan="6" class="empty-td">A carregar…</td></tr>';
  try {
    const params = new URLSearchParams();
    if (q)   params.set('q', q);
    if (cat) params.set('categoria', cat);
    const list = await API.get(`/api/admin/noticias?${params}`);
    tb.innerHTML = list.length
      ? list.map(n => rowHTML(n, true)).join('')
      : '<tr><td colspan="6" class="empty-td">Nenhuma notícia encontrada.</td></tr>';
  } catch { tb.innerHTML = '<tr><td colspan="6" class="empty-td">Erro ao carregar.</td></tr>'; }
}

function rowHTML(n, actions) {
  const d = new Date(n.data).toLocaleDateString('pt-PT');
  return `
    <tr>
      <td><span class="t-title" title="${n.titulo}">${n.titulo}</span></td>
      <td><span class="badge badge-gray">${n.categoria}</span></td>
      <td>${n.autor}</td>
      <td>${d}</td>
      <td>${n.destaque ? '<span class="badge badge-red">★ Destaque</span>' : '<span class="badge badge-gray">Normal</span>'}</td>
      ${actions ? `<td><div class="row-actions">
        <button class="a-btn a-btn-sm" onclick="openForm('${n.id}')">Editar</button>
        <button class="a-btn a-btn-sm ${n.destaque ? 'active' : ''}" onclick="toggleDestaque('${n.id}')" title="${n.destaque ? 'Remover destaque' : 'Destacar'}">★</button>
        <button class="a-btn a-btn-sm a-btn-del" onclick="confirmDelete('${n.id}')">Apagar</button>
      </div></td>` : ''}
    </tr>`;
}

/* ── Destaque ────────────────────────────────────────────── */

async function toggleDestaque(id) {
  try {
    const d = await API.post(`/api/admin/noticias/${id}/destaque`, {});
    toast(d.destaque ? 'Definido como destaque.' : 'Destaque removido.');
    loadNoticias();
    loadStats();
  } catch (e) { toast(e.message, 'err'); }
}

/* ── Formulário ──────────────────────────────────────────── */

async function openForm(id = null) {
  S.editId = id;
  Upload.clear();

  // Carregar categorias
  try {
    const cats = await API.get('/api/categorias');
    const sel  = document.getElementById('f-categoria');
    if (sel) sel.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
  } catch {}

  if (id) {
    try {
      const n = await API.get(`/api/noticias/${id}`);
      document.getElementById('f-titulo').value     = n.titulo;
      document.getElementById('f-subtitulo').value  = n.subtitulo || '';
      document.getElementById('f-autor').value      = n.autor;
      document.getElementById('f-data').value       = n.data;
      document.getElementById('f-categoria').value  = n.categoria;
      document.getElementById('f-destaque').checked = !!n.destaque;
      document.getElementById('f-img-url').value    = n.imagem || '';
      Editor.set(n.conteudo || '');
      if (n.imagem) Upload.previewURL(n.imagem);
    } catch (e) { toast(e.message, 'err'); return; }
  } else {
    document.getElementById('f-titulo').value     = '';
    document.getElementById('f-subtitulo').value  = '';
    document.getElementById('f-autor').value      = '';
    document.getElementById('f-data').value       = new Date().toISOString().split('T')[0];
    document.getElementById('f-destaque').checked = false;
    document.getElementById('f-img-url').value    = '';
    Editor.set('');
  }
  showSection('form');
}

async function saveNoticia(preview = false) {
  const titulo    = document.getElementById('f-titulo').value.trim();
  const subtitulo = document.getElementById('f-subtitulo').value.trim();
  const autor     = document.getElementById('f-autor').value.trim();
  const data      = document.getElementById('f-data').value;
  const categoria = document.getElementById('f-categoria').value;
  const destaque  = document.getElementById('f-destaque').checked;
  const conteudo  = Editor.get();
  const imagem    = Upload.url || document.getElementById('f-img-url').value.trim();

  if (!titulo)    { toast('Título obrigatório.', 'err'); return; }
  if (!autor)     { toast('Autor obrigatório.', 'err'); return; }
  if (!data)      { toast('Data obrigatória.', 'err'); return; }
  if (!conteudo.trim()) { toast('Conteúdo obrigatório.', 'err'); return; }

  const body = { titulo, subtitulo, autor, data, categoria, destaque, conteudo, imagem };

  if (preview) { openPreview(body); return; }

  try {
    if (S.editId) {
      await API.put(`/api/admin/noticias/${S.editId}`, body);
      toast('Notícia atualizada! ✓');
    } else {
      await API.post('/api/admin/noticias', body);
      toast('Notícia publicada! ✓');
    }
    S.editId = null;
    showSection('noticias');
    loadStats();
  } catch (e) { toast(e.message, 'err'); }
}

/* ── Apagar ──────────────────────────────────────────────── */

function confirmDelete(id) {
  S.deleteId = id;
  document.getElementById('modal-delete').classList.add('open');
}
function closeModal() {
  document.getElementById('modal-delete').classList.remove('open');
  S.deleteId = null;
}
async function doDelete() {
  try {
    await API.del(`/api/admin/noticias/${S.deleteId}`);
    toast('Notícia apagada.');
    closeModal();
    loadNoticias();
    loadStats();
  } catch (e) { toast(e.message, 'err'); closeModal(); }
}

/* ── Upload imagem ───────────────────────────────────────── */

const Upload = {
  url: null,

  init() {
    const area  = document.getElementById('upload-area');
    const input = document.getElementById('upload-input');
    if (!area || !input) return;

    area.addEventListener('click', () => input.click());
    area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('drag'); });
    area.addEventListener('dragleave', () => area.classList.remove('drag'));
    area.addEventListener('drop', e => { e.preventDefault(); area.classList.remove('drag'); const f = e.dataTransfer.files[0]; if (f) this.upload(f); });
    input.addEventListener('change', e => { const f = e.target.files[0]; if (f) this.upload(f); });
  },

  async upload(file) {
    if (!file.type.startsWith('image/')) { toast('Apenas imagens.', 'err'); return; }
    if (file.size > 8 * 1024 * 1024) { toast('Imagem demasiado grande (max 8MB).', 'err'); return; }

    const form = new FormData();
    form.append('imagem', file);

    const area = document.getElementById('upload-area');
    if (area) area.querySelector('.u-text').textContent = 'A enviar…';

    try {
      const d = await API.upload('/api/admin/upload', form);
      this.url = d.url;
      this.previewURL(d.url);
      document.getElementById('f-img-url').value = d.url;
      toast('Imagem carregada ✓');
    } catch (e) {
      toast('Erro no upload: ' + e.message, 'err');
      if (area) area.querySelector('.u-text').textContent = 'Clique ou arraste uma imagem';
    }
  },

  previewURL(url) {
    const prev = document.getElementById('upload-preview');
    if (prev) { prev.innerHTML = `<img src="${url}" alt="Preview">`; prev.style.display = 'block'; }
    const area = document.getElementById('upload-area');
    if (area) area.querySelector('.u-text').textContent = 'Imagem carregada';
    this.url = url;
  },

  clear() {
    this.url = null;
    const prev = document.getElementById('upload-preview');
    if (prev) { prev.innerHTML = ''; prev.style.display = 'none'; }
    const area = document.getElementById('upload-area');
    if (area) area.querySelector('.u-text').textContent = 'Clique ou arraste uma imagem';
    const input = document.getElementById('upload-input');
    if (input) input.value = '';
  },
};

/* ── Editor rico ─────────────────────────────────────────── */

const Editor = {
  el() { return document.getElementById('f-conteudo'); },
  get() { return this.el()?.innerHTML || ''; },
  set(html) { const e = this.el(); if (e) e.innerHTML = html; },
  cmd(c, v = null) { this.el()?.focus(); document.execCommand(c, false, v); },
  link() { const u = prompt('URL:'); if (u) this.cmd('createLink', u); },
};

/* ── Pré-visualização ────────────────────────────────────── */

function openPreview(n) {
  const box = document.getElementById('preview-body');
  if (!box) return;
  box.innerHTML = `
    <span style="display:inline-block;background:#c8102e;color:#fff;font-family:sans-serif;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;margin-bottom:14px">${n.categoria}</span>
    <h1 style="font-family:Georgia,serif;font-size:32px;font-weight:700;line-height:1.2;margin-bottom:12px;color:#0d0d0d">${n.titulo}</h1>
    ${n.subtitulo ? `<p style="font-family:Georgia,serif;font-size:18px;font-style:italic;color:#666;margin-bottom:16px">${n.subtitulo}</p>` : ''}
    <div style="font-family:sans-serif;font-size:12px;color:#888;padding:10px 0;border-top:1px solid #ddd;border-bottom:1px solid #ddd;margin-bottom:22px">${n.autor} · ${new Date(n.data).toLocaleDateString('pt-PT', {day:'numeric',month:'long',year:'numeric'})}</div>
    ${n.imagem ? `<img src="${n.imagem}" style="width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:2px;margin-bottom:22px">` : ''}
    <div style="font-family:Georgia,serif;font-size:17px;line-height:1.8;color:#2a2a2a">${n.conteudo}</div>
  `;
  document.getElementById('preview-overlay').classList.add('open');
}
function closePreview() { document.getElementById('preview-overlay').classList.remove('open'); }

/* ── Categorias ──────────────────────────────────────────── */

async function loadCategorias() {
  const list = document.getElementById('cat-list');
  if (!list) return;
  try {
    const cats = await API.get('/api/admin/categorias');
    list.innerHTML = cats.map(c => `
      <div class="cat-row">
        <span>${c}</span>
        <button class="a-btn a-btn-sm a-btn-del" onclick="deleteCategoria('${c}')">Remover</button>
      </div>
    `).join('') || '<p style="padding:16px;font-size:13px;color:#888">Sem categorias.</p>';
  } catch {}
}

async function addCategoria() {
  const inp  = document.getElementById('new-cat');
  const nome = inp.value.trim();
  if (!nome) { toast('Nome obrigatório.', 'err'); return; }
  try {
    await API.post('/api/admin/categorias', { nome });
    toast(`Categoria "${nome}" criada.`);
    inp.value = '';
    loadCategorias();
  } catch (e) { toast(e.message, 'err'); }
}

async function deleteCategoria(nome) {
  if (!confirm(`Remover categoria "${nome}"?`)) return;
  try {
    await API.del(`/api/admin/categorias/${encodeURIComponent(nome)}`);
    toast(`Categoria "${nome}" removida.`);
    loadCategorias();
  } catch (e) { toast(e.message, 'err'); }
}

/* ── Pesquisa na lista ───────────────────────────────────── */

let searchTimer = null;
function onSearchList(v) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadNoticias(v), 280);
}

/* ── Arranque ────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', async () => {
  const isAuth = await checkAuth();
  if (isAuth) { showAdmin(); }
  else {
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('admin-screen').style.display = 'none';
  }

  document.getElementById('login-form')?.addEventListener('submit', doLogin);
  Upload.init();

  // Data default
  const fd = document.getElementById('f-data');
  if (fd && !fd.value) fd.value = new Date().toISOString().split('T')[0];
});
