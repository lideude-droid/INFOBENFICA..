"""
ENCARNADO — Portal de Notícias do Benfica
server.py — Servidor Flask + SQLite
"""

import os
import sqlite3
import hashlib
import secrets
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, jsonify, send_from_directory,
    session, abort
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ─── Configuração ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, 'data', 'encarnado.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'public', 'assets', 'images')
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMG_MB    = 8
SECRET_KEY    = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Credenciais de administrador (alterar aqui ou via variáveis de ambiente)
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'encarnado2025')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_IMG_MB * 1024 * 1024
CORS(app, supports_credentials=True)

# ─── Base de dados ───────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS noticias (
            id          TEXT PRIMARY KEY,
            titulo      TEXT NOT NULL,
            subtitulo   TEXT DEFAULT '',
            autor       TEXT NOT NULL,
            data        TEXT NOT NULL,
            categoria   TEXT NOT NULL,
            imagem      TEXT DEFAULT '',
            conteudo    TEXT NOT NULL DEFAULT '',
            destaque    INTEGER DEFAULT 0,
            leituras    INTEGER DEFAULT 0,
            criado_em   TEXT NOT NULL,
            editado_em  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS galeria (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            noticia_id  TEXT NOT NULL REFERENCES noticias(id) ON DELETE CASCADE,
            imagem      TEXT NOT NULL,
            ordem       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        INSERT OR IGNORE INTO categorias (nome) VALUES
            ('Futebol'), ('Modalidades'), ('Mercado'),
            ('Formação'), ('Opinião');

        INSERT OR IGNORE INTO config (chave, valor) VALUES
            ('site_nome', 'Encarnado'),
            ('site_slogan', 'O pulso do Benfica'),
            ('versao', '1.0');
    """)
    db.commit()
    db.close()

def hash_pass(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

ADMIN_PASS_HASH = hash_pass(ADMIN_PASS)

# ─── Auth helpers ────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'erro': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ─── Rotas estáticas ─────────────────────────────────────────────

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

@app.route('/404')
def pagina_404():
    return send_from_directory(PUBLIC_DIR, '404.html'), 404

# Ficheiros estáticos (css, js, imagens)
@app.route('/css/<path:path>')
def static_css(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'css'), path)

@app.route('/js/<path:path>')
def static_js(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'js'), path)

@app.route('/assets/<path:path>')
def static_assets(path):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'assets'), path)

# ─── API: Autenticação ───────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    user = data.get('utilizador', '').strip()
    pw   = data.get('senha', '')
    if user == ADMIN_USER and hash_pass(pw) == ADMIN_PASS_HASH:
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

# ─── API: Notícias (público) ─────────────────────────────────────

@app.route('/api/noticias')
def api_noticias():
    db  = get_db()
    cat = request.args.get('categoria', '').strip()
    q   = request.args.get('q', '').strip()
    lim = min(int(request.args.get('limite', 50)), 100)
    off = int(request.args.get('offset', 0))

    sql    = "SELECT * FROM noticias WHERE 1=1"
    params = []

    if cat:
        sql += " AND categoria = ?"
        params.append(cat)
    if q:
        sql += " AND (titulo LIKE ? OR subtitulo LIKE ?)"
        params += [f'%{q}%', f'%{q}%']

    sql += " ORDER BY destaque DESC, data DESC, criado_em DESC LIMIT ? OFFSET ?"
    params += [lim, off]

    rows = db.execute(sql, params).fetchall()
    total = db.execute(
        "SELECT COUNT(*) FROM noticias" +
        (" WHERE categoria=?" if cat else ""),
        [cat] if cat else []
    ).fetchone()[0]
    db.close()
    return jsonify({'noticias': rows_to_list(rows), 'total': total})

@app.route('/api/noticias/destaque')
def api_destaque():
    db  = get_db()
    row = db.execute(
        "SELECT * FROM noticias WHERE destaque=1 ORDER BY data DESC LIMIT 1"
    ).fetchone()
    if not row:
        row = db.execute(
            "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT 1"
        ).fetchone()
    db.close()
    return jsonify(row_to_dict(row))

@app.route('/api/noticias/recentes')
def api_recentes():
    lim = min(int(request.args.get('limite', 6)), 20)
    db  = get_db()
    rows = db.execute(
        "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT ?", [lim]
    ).fetchall()
    db.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/noticias/mais-lidas')
def api_mais_lidas():
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM noticias ORDER BY leituras DESC, data DESC LIMIT 5"
    ).fetchall()
    db.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/noticias/<nid>')
def api_noticia(nid):
    db  = get_db()
    row = db.execute("SELECT * FROM noticias WHERE id=?", [nid]).fetchone()
    if not row:
        db.close()
        return jsonify({'erro': 'Não encontrada'}), 404
    # Galeria
    galeria = db.execute(
        "SELECT imagem FROM galeria WHERE noticia_id=? ORDER BY ordem", [nid]
    ).fetchall()
    # Relacionadas
    relacionadas = db.execute(
        "SELECT * FROM noticias WHERE categoria=? AND id!=? ORDER BY data DESC LIMIT 3",
        [row['categoria'], nid]
    ).fetchall()
    db.close()
    result = row_to_dict(row)
    result['galeria']     = [r['imagem'] for r in galeria]
    result['relacionadas'] = rows_to_list(relacionadas)
    return jsonify(result)

@app.route('/api/noticias/<nid>/leitura', methods=['POST'])
def api_registar_leitura(nid):
    db = get_db()
    db.execute("UPDATE noticias SET leituras = leituras+1 WHERE id=?", [nid])
    db.commit()
    db.close()
    return jsonify({'ok': True})

# ─── API: Categorias (público) ───────────────────────────────────

@app.route('/api/categorias')
def api_categorias():
    db   = get_db()
    rows = db.execute("SELECT nome FROM categorias ORDER BY nome").fetchall()
    db.close()
    return jsonify([r['nome'] for r in rows])

# ─── API: Admin — Notícias ───────────────────────────────────────

@app.route('/api/admin/noticias', methods=['GET'])
@login_required
def admin_listar_noticias():
    db   = get_db()
    q    = request.args.get('q', '').strip()
    cat  = request.args.get('categoria', '').strip()
    sql  = "SELECT * FROM noticias WHERE 1=1"
    params = []
    if q:
        sql += " AND (titulo LIKE ? OR autor LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if cat:
        sql += " AND categoria=?"
        params.append(cat)
    sql  += " ORDER BY data DESC, criado_em DESC"
    rows  = db.execute(sql, params).fetchall()
    db.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/admin/noticias', methods=['POST'])
@login_required
def admin_criar_noticia():
    data = request.get_json() or {}
    erros = []
    if not data.get('titulo', '').strip():  erros.append('título')
    if not data.get('autor', '').strip():   erros.append('autor')
    if not data.get('data', '').strip():    erros.append('data')
    if not data.get('conteudo', '').strip(): erros.append('conteúdo')
    if erros:
        return jsonify({'erro': f'Campos obrigatórios: {", ".join(erros)}'}), 400

    nid = str(uuid.uuid4())[:8]
    agora = datetime.now().isoformat()

    db = get_db()
    # Se é destaque, limpar outros
    if data.get('destaque'):
        db.execute("UPDATE noticias SET destaque=0")

    db.execute("""
        INSERT INTO noticias
            (id, titulo, subtitulo, autor, data, categoria, imagem,
             conteudo, destaque, leituras, criado_em, editado_em)
        VALUES (?,?,?,?,?,?,?,?,?,0,?,?)
    """, [
        nid,
        data['titulo'].strip(),
        data.get('subtitulo', '').strip(),
        data['autor'].strip(),
        data['data'].strip(),
        data.get('categoria', 'Futebol').strip(),
        data.get('imagem', '').strip(),
        data['conteudo'].strip(),
        1 if data.get('destaque') else 0,
        agora, agora,
    ])
    db.commit()
    row = db.execute("SELECT * FROM noticias WHERE id=?", [nid]).fetchone()
    db.close()
    return jsonify(row_to_dict(row)), 201

@app.route('/api/admin/noticias/<nid>', methods=['PUT'])
@login_required
def admin_editar_noticia(nid):
    db  = get_db()
    row = db.execute("SELECT id FROM noticias WHERE id=?", [nid]).fetchone()
    if not row:
        db.close()
        return jsonify({'erro': 'Não encontrada'}), 404

    data  = request.get_json() or {}
    agora = datetime.now().isoformat()

    if data.get('destaque'):
        db.execute("UPDATE noticias SET destaque=0 WHERE id!=?", [nid])

    db.execute("""
        UPDATE noticias SET
            titulo=?, subtitulo=?, autor=?, data=?, categoria=?,
            imagem=?, conteudo=?, destaque=?, editado_em=?
        WHERE id=?
    """, [
        data.get('titulo', '').strip(),
        data.get('subtitulo', '').strip(),
        data.get('autor', '').strip(),
        data.get('data', '').strip(),
        data.get('categoria', 'Futebol').strip(),
        data.get('imagem', '').strip(),
        data.get('conteudo', '').strip(),
        1 if data.get('destaque') else 0,
        agora, nid,
    ])
    db.commit()
    row = db.execute("SELECT * FROM noticias WHERE id=?", [nid]).fetchone()
    db.close()
    return jsonify(row_to_dict(row))

@app.route('/api/admin/noticias/<nid>', methods=['DELETE'])
@login_required
def admin_apagar_noticia(nid):
    db = get_db()
    db.execute("DELETE FROM noticias WHERE id=?", [nid])
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/api/admin/noticias/<nid>/destaque', methods=['POST'])
@login_required
def admin_toggle_destaque(nid):
    db  = get_db()
    row = db.execute("SELECT destaque FROM noticias WHERE id=?", [nid]).fetchone()
    if not row:
        db.close()
        return jsonify({'erro': 'Não encontrada'}), 404
    novo = 0 if row['destaque'] else 1
    if novo:
        db.execute("UPDATE noticias SET destaque=0")
    db.execute("UPDATE noticias SET destaque=? WHERE id=?", [novo, nid])
    db.commit()
    db.close()
    return jsonify({'destaque': bool(novo)})

# ─── API: Admin — Upload de imagem ───────────────────────────────

@app.route('/api/admin/upload', methods=['POST'])
@login_required
def admin_upload():
    if 'imagem' not in request.files:
        return jsonify({'erro': 'Nenhum ficheiro enviado'}), 400
    f = request.files['imagem']
    if not f.filename or not allowed_file(f.filename):
        return jsonify({'erro': 'Tipo de ficheiro não permitido'}), 400

    ext      = f.filename.rsplit('.', 1)[1].lower()
    nome     = f"{uuid.uuid4().hex}.{ext}"
    caminho  = os.path.join(UPLOAD_DIR, nome)
    f.save(caminho)
    url = f"/assets/images/{nome}"
    return jsonify({'url': url, 'nome': nome})

# ─── API: Admin — Categorias ─────────────────────────────────────

@app.route('/api/admin/categorias', methods=['GET'])
@login_required
def admin_listar_categorias():
    db   = get_db()
    rows = db.execute("SELECT nome FROM categorias ORDER BY nome").fetchall()
    db.close()
    return jsonify([r['nome'] for r in rows])

@app.route('/api/admin/categorias', methods=['POST'])
@login_required
def admin_criar_categoria():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO categorias (nome) VALUES (?)", [nome])
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({'erro': 'Categoria já existe'}), 409
    db.close()
    return jsonify({'ok': True, 'nome': nome}), 201

@app.route('/api/admin/categorias/<nome>', methods=['DELETE'])
@login_required
def admin_apagar_categoria(nome):
    db  = get_db()
    em_uso = db.execute(
        "SELECT COUNT(*) FROM noticias WHERE categoria=?", [nome]
    ).fetchone()[0]
    if em_uso:
        db.close()
        return jsonify({'erro': f'Categoria em uso por {em_uso} notícia(s)'}), 409
    db.execute("DELETE FROM categorias WHERE nome=?", [nome])
    db.commit()
    db.close()
    return jsonify({'ok': True})

# ─── API: Estatísticas admin ─────────────────────────────────────

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    db = get_db()
    total      = db.execute("SELECT COUNT(*) FROM noticias").fetchone()[0]
    destaques  = db.execute("SELECT COUNT(*) FROM noticias WHERE destaque=1").fetchone()[0]
    total_cats = db.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]
    por_cat    = db.execute(
        "SELECT categoria, COUNT(*) as n FROM noticias GROUP BY categoria ORDER BY n DESC"
    ).fetchall()
    recentes   = db.execute(
        "SELECT * FROM noticias ORDER BY criado_em DESC LIMIT 5"
    ).fetchall()
    db.close()
    return jsonify({
        'total': total,
        'destaques': destaques,
        'total_categorias': total_cats,
        'por_categoria': rows_to_list(por_cat),
        'recentes': rows_to_list(recentes),
    })

# ─── Arranque ────────────────────────────────────────────────────

# Garantir pastas no arranque (importante para Render/cloud)
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Inicializar DB sempre que o módulo é importado (para Gunicorn/Render)
init_db()

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'
    print(f"""
╔══════════════════════════════════════════╗
║   ENCARNADO — Portal do Benfica          ║
║   http://localhost:{porta:<5}                  ║
║   Admin: http://localhost:{porta}/admin       ║
║   User: {ADMIN_USER:<10}  Pass: {ADMIN_PASS:<12}   ║
╚══════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=porta, debug=debug)
