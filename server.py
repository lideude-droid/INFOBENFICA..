"""
ENCARNADO — Portal de Notícias do Benfica
server.py — Flask + PostgreSQL (Supabase)
"""

import os
import hashlib
import secrets
import uuid
import logging
from datetime import datetime
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR   = os.path.join(BASE_DIR, 'public', 'assets', 'images')
PUBLIC_DIR   = os.path.join(BASE_DIR, 'public')
ALLOWED_EXT  = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMG_MB   = 8

DATABASE_URL = os.environ.get('DATABASE_URL', '')
SECRET_KEY   = os.environ.get('SECRET_KEY', secrets.token_hex(32))
ADMIN_USER   = os.environ.get('ADMIN_USER', 'infobenfica')
ADMIN_PASS   = os.environ.get('ADMIN_PASS', 'encarnado1232026')

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_IMG_MB * 1024 * 1024
CORS(app, supports_credentials=True)

ADMIN_PASS_HASH = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()

# ─── Base de dados ────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    log.info("A inicializar base de dados...")
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS noticias (
            id          TEXT PRIMARY KEY,
            titulo      TEXT NOT NULL,
            subtitulo   TEXT DEFAULT '',
            autor       TEXT NOT NULL,
            data        TEXT NOT NULL,
            categoria   TEXT NOT NULL,
            imagem      TEXT DEFAULT '',
            conteudo    TEXT NOT NULL DEFAULT '',
            destaque    BOOLEAN DEFAULT FALSE,
            leituras    INTEGER DEFAULT 0,
            criado_em   TEXT NOT NULL,
            editado_em  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id    SERIAL PRIMARY KEY,
            nome  TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS galeria (
            id         SERIAL PRIMARY KEY,
            noticia_id TEXT NOT NULL REFERENCES noticias(id) ON DELETE CASCADE,
            imagem     TEXT NOT NULL,
            ordem      INTEGER DEFAULT 0
        );

        INSERT INTO categorias (nome)
        VALUES ('Futebol'), ('Modalidades'), ('Mercado'), ('Formação'), ('Opinião')
        ON CONFLICT (nome) DO NOTHING;
    """)
    conn.commit()
    cur.close()
    conn.close()
    log.info("Base de dados inicializada com sucesso!")

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXT

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'erro': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated

# ─── Estáticos ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(PUBLIC_DIR, 'index.html')

@app.route('/noticia')
def noticia_page():
    return send_from_directory(PUBLIC_DIR, 'noticia.html')

@app.route('/favoritos')
def favoritos_page():
    return send_from_directory(PUBLIC_DIR, 'favoritos.html')

@app.route('/admin')
@app.route('/admin/')
def admin_page():
    return send_from_directory(PUBLIC_DIR, 'admin.html')

@app.route('/css/<path:path>')
def static_css(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'css'), path)

@app.route('/js/<path:path>')
def static_js(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'js'), path)

@app.route('/assets/<path:path>')
def static_assets(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'assets'), path)

# ─── API Auth ─────────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    user = data.get('utilizador', '').strip()
    pw   = data.get('senha', '')
    if user == ADMIN_USER and hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASS_HASH:
        session['admin'] = True
        return jsonify({'ok': True})
    return jsonify({'erro': 'Credenciais incorretas'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/auth/verificar')
def api_verificar():
    return jsonify({'autenticado': bool(session.get('admin'))})

# ─── API Notícias (público) ───────────────────────────────────────────────────

@app.route('/api/noticias')
def api_noticias():
    cat = request.args.get('categoria', '').strip()
    q   = request.args.get('q', '').strip()
    lim = min(int(request.args.get('limite', 50)), 100)
    off = int(request.args.get('offset', 0))

    conn = get_db(); cur = conn.cursor()
    conditions = []; params = []

    if cat:
        conditions.append("categoria = %s")
        params.append(cat)
    if q:
        conditions.append("(titulo ILIKE %s OR subtitulo ILIKE %s)")
        params += [f'%{q}%', f'%{q}%']

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"SELECT * FROM noticias {where} ORDER BY destaque DESC, data DESC, criado_em DESC LIMIT %s OFFSET %s", params + [lim, off])
    rows = cur.fetchall()
    cur.execute(f"SELECT COUNT(*) FROM noticias {where}", params)
    total = cur.fetchone()['count']
    cur.close(); conn.close()
    return jsonify({'noticias': [dict(r) for r in rows], 'total': total})

@app.route('/api/noticias/destaque')
def api_destaque():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM noticias WHERE destaque=TRUE ORDER BY data DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT 1")
        row = cur.fetchone()
    cur.close(); conn.close()
    return jsonify(dict(row) if row else {})

@app.route('/api/noticias/recentes')
def api_recentes():
    lim = min(int(request.args.get('limite', 6)), 20)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT %s", [lim])
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/noticias/mais-lidas')
def api_mais_lidas():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM noticias ORDER BY leituras DESC, data DESC LIMIT 5")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/noticias/<nid>')
def api_noticia(nid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({'erro': 'Não encontrada'}), 404
    cur.execute("SELECT imagem FROM galeria WHERE noticia_id=%s ORDER BY ordem", [nid])
    galeria = cur.fetchall()
    cur.execute("SELECT * FROM noticias WHERE categoria=%s AND id!=%s ORDER BY data DESC LIMIT 3", [row['categoria'], nid])
    relacionadas = cur.fetchall()
    cur.close(); conn.close()
    result = dict(row)
    result['galeria']      = [r['imagem'] for r in galeria]
    result['relacionadas'] = [dict(r) for r in relacionadas]
    return jsonify(result)

@app.route('/api/noticias/<nid>/leitura', methods=['POST'])
def api_leitura(nid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE noticias SET leituras = leituras+1 WHERE id=%s", [nid])
    conn.commit(); cur.close(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/categorias')
def api_categorias():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nome FROM categorias ORDER BY nome")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([r['nome'] for r in rows])

# ─── API Admin ────────────────────────────────────────────────────────────────

@app.route('/api/admin/noticias', methods=['GET'])
@login_required
def admin_listar():
    q = request.args.get('q', '').strip()
    cat = request.args.get('categoria', '').strip()
    conn = get_db(); cur = conn.cursor()
    conditions = []; params = []
    if q:
        conditions.append("(titulo ILIKE %s OR autor ILIKE %s)")
        params += [f'%{q}%', f'%{q}%']
    if cat:
        conditions.append("categoria = %s")
        params.append(cat)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"SELECT * FROM noticias {where} ORDER BY data DESC, criado_em DESC", params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/noticias', methods=['POST'])
@login_required
def admin_criar():
    data = request.get_json() or {}
    erros = []
    if not data.get('titulo', '').strip():   erros.append('título')
    if not data.get('autor', '').strip():    erros.append('autor')
    if not data.get('data', '').strip():     erros.append('data')
    if not data.get('conteudo', '').strip(): erros.append('conteúdo')
    if erros:
        return jsonify({'erro': f'Campos obrigatórios: {", ".join(erros)}'}), 400

    nid = str(uuid.uuid4())[:8]
    agora = datetime.now().isoformat()
    conn = get_db(); cur = conn.cursor()
    if data.get('destaque'):
        cur.execute("UPDATE noticias SET destaque=FALSE")
    cur.execute("""
        INSERT INTO noticias (id,titulo,subtitulo,autor,data,categoria,imagem,conteudo,destaque,leituras,criado_em,editado_em)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s)
    """, [nid, data['titulo'].strip(), data.get('subtitulo','').strip(), data['autor'].strip(),
          data['data'].strip(), data.get('categoria','Futebol').strip(), data.get('imagem','').strip(),
          data['conteudo'].strip(), bool(data.get('destaque')), agora, agora])
    conn.commit()
    cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
    row = cur.fetchone()
    cur.close(); conn.close()
    return jsonify(dict(row)), 201

@app.route('/api/admin/noticias/<nid>', methods=['PUT'])
@login_required
def admin_editar(nid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id FROM noticias WHERE id=%s", [nid])
    if not cur.fetchone():
        cur.close(); conn.close()
        return jsonify({'erro': 'Não encontrada'}), 404
    data = request.get_json() or {}
    agora = datetime.now().isoformat()
    if data.get('destaque'):
        cur.execute("UPDATE noticias SET destaque=FALSE WHERE id!=%s", [nid])
    cur.execute("""
        UPDATE noticias SET titulo=%s,subtitulo=%s,autor=%s,data=%s,categoria=%s,
        imagem=%s,conteudo=%s,destaque=%s,editado_em=%s WHERE id=%s
    """, [data.get('titulo','').strip(), data.get('subtitulo','').strip(), data.get('autor','').strip(),
          data.get('data','').strip(), data.get('categoria','Futebol').strip(), data.get('imagem','').strip(),
          data.get('conteudo','').strip(), bool(data.get('destaque')), agora, nid])
    conn.commit()
    cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
    row = cur.fetchone()
    cur.close(); conn.close()
    return jsonify(dict(row))

@app.route('/api/admin/noticias/<nid>', methods=['DELETE'])
@login_required
def admin_apagar(nid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM noticias WHERE id=%s", [nid])
    conn.commit(); cur.close(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/noticias/<nid>/destaque', methods=['POST'])
@login_required
def admin_destaque(nid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT destaque FROM noticias WHERE id=%s", [nid])
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({'erro': 'Não encontrada'}), 404
    novo = not row['destaque']
    if novo:
        cur.execute("UPDATE noticias SET destaque=FALSE")
    cur.execute("UPDATE noticias SET destaque=%s WHERE id=%s", [novo, nid])
    conn.commit(); cur.close(); conn.close()
    return jsonify({'destaque': novo})

@app.route('/api/admin/upload', methods=['POST'])
@login_required
def admin_upload():
    if 'imagem' not in request.files:
        return jsonify({'erro': 'Nenhum ficheiro'}), 400
    f = request.files['imagem']
    if not f.filename or not allowed_file(f.filename):
        return jsonify({'erro': 'Tipo não permitido'}), 400
    ext = f.filename.rsplit('.', 1)[1].lower()
    nome = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, nome))
    return jsonify({'url': f"/assets/images/{nome}", 'nome': nome})


@app.route('/api/admin/noticias/<nid>/galeria', methods=['POST'])
@login_required
def admin_galeria_add(nid):
    """Adiciona imagem à galeria de uma notícia."""
    if 'imagem' not in request.files:
        return jsonify({'erro': 'Nenhum ficheiro'}), 400
    f = request.files['imagem']
    if not f.filename or not allowed_file(f.filename):
        return jsonify({'erro': 'Tipo não permitido'}), 400
    ext  = f.filename.rsplit('.', 1)[1].lower()
    nome = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, nome))
    url  = f"/assets/images/{nome}"
    conn = get_db(); cur = conn.cursor()
    # Verificar ordem máxima
    cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id=%s", [nid])
    ordem = cur.fetchone()['coalesce']
    cur.execute("INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s,%s,%s)", [nid, url, ordem])
    conn.commit()
    cur.execute("SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem", [nid])
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'url': url, 'galeria': [dict(r) for r in rows]}), 201

@app.route('/api/admin/noticias/<nid>/galeria', methods=['GET'])
@login_required
def admin_galeria_get(nid):
    """Lista imagens da galeria de uma notícia."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem", [nid])
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/galeria/<int:gid>', methods=['DELETE'])
@login_required
def admin_galeria_delete(gid):
    """Remove imagem da galeria."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM galeria WHERE id=%s", [gid])
    conn.commit(); cur.close(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/galeria/url', methods=['POST'])
@login_required
def admin_galeria_add_url():
    """Adiciona imagem à galeria via URL."""
    data = request.get_json() or {}
    nid  = data.get('noticia_id', '').strip()
    url  = data.get('url', '').strip()
    if not nid or not url:
        return jsonify({'erro': 'noticia_id e url obrigatórios'}), 400
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id=%s", [nid])
    ordem = cur.fetchone()['coalesce']
    cur.execute("INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s,%s,%s)", [nid, url, ordem])
    conn.commit()
    cur.execute("SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem", [nid])
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'galeria': [dict(r) for r in rows]}), 201

@app.route('/api/admin/categorias', methods=['GET'])
@login_required
def admin_cats():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nome FROM categorias ORDER BY nome")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([r['nome'] for r in rows])

@app.route('/api/admin/categorias', methods=['POST'])
@login_required
def admin_criar_cat():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categorias (nome) VALUES (%s)", [nome])
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback(); cur.close(); conn.close()
        return jsonify({'erro': 'Categoria já existe'}), 409
    cur.close(); conn.close()
    return jsonify({'ok': True, 'nome': nome}), 201

@app.route('/api/admin/categorias/<nome>', methods=['DELETE'])
@login_required
def admin_apagar_cat(nome):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM noticias WHERE categoria=%s", [nome])
    em_uso = cur.fetchone()['count']
    if em_uso:
        cur.close(); conn.close()
        return jsonify({'erro': f'Em uso por {em_uso} notícia(s)'}), 409
    cur.execute("DELETE FROM categorias WHERE nome=%s", [nome])
    conn.commit(); cur.close(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM noticias")
    total = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM noticias WHERE destaque=TRUE")
    destaques = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM categorias")
    total_cats = cur.fetchone()['count']
    cur.execute("SELECT categoria, COUNT(*) as n FROM noticias GROUP BY categoria ORDER BY n DESC")
    por_cat = cur.fetchall()
    cur.execute("SELECT * FROM noticias ORDER BY criado_em DESC LIMIT 5")
    recentes = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({
        'total': total, 'destaques': destaques, 'total_categorias': total_cats,
        'por_categoria': [dict(r) for r in por_cat],
        'recentes': [dict(r) for r in recentes],
    })

# ─── Inicialização ────────────────────────────────────────────────────────────

if DATABASE_URL:
    try:
        init_db()
        log.info("DATABASE OK — Supabase/PostgreSQL ligado")
    except Exception as e:
        log.error(f"ERRO DATABASE: {e}")
else:
    log.warning("DATABASE_URL nao definida!")

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'
    log.info(f"Servidor a iniciar na porta {porta}")
    app.run(host='0.0.0.0', port=porta, debug=debug)
