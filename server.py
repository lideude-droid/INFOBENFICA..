"""
ENCARNADO — Portal de Notícias do Benfica
server.py — Flask + PostgreSQL (RocketAdmin) com SQLAlchemy + Fallback
"""

import os
import hashlib
import secrets
import uuid
import logging
import json
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, session, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, exc
from urllib.parse import urlparse

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR   = os.path.join(BASE_DIR, 'public')
UPLOAD_DIR   = os.path.join(PUBLIC_DIR, 'assets', 'images')
ALLOWED_EXT  = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MIME_POR_EXT = {
    'png':  'image/png',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
    'gif':  'image/gif',
}
MAX_IMG_MB   = 8

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgres://hdb_J-pXdeuD:bfNUZhNs0iHHLpUXDaq1gDUNToMD_k2W@hdb-J-pXdeuD.db.rocketadmin.com:5432/hdb_J-pXdeuD'
)

SECRET_KEY   = os.environ.get('SECRET_KEY', secrets.token_hex(32))
ADMIN_USER   = os.environ.get('ADMIN_USER', 'infobenfica')
ADMIN_PASS   = os.environ.get('ADMIN_PASS', 'encarnado1232026')

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_IMG_MB * 1024 * 1024

# ─── Configuração SQLAlchemy com SSL forçado ────────────────────────────────
# Extrai parâmetros da URL para construir uma string de conexão com SSL
parsed = urlparse(DATABASE_URL)
ssl_config = {
    'sslmode': 'require',
    'connect_timeout': 30,
    'keepalives_idle': 5,
    'keepalives_interval': 2,
    'keepalives_count': 2,
}
# Monta a URL com os parâmetros SSL
db_url = (
    f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/{parsed.path[1:]}"
    f"?sslmode=require&connect_timeout=30&keepalives_idle=5&keepalives_interval=2&keepalives_count=2"
)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_use_lifo': True,
}

db = SQLAlchemy(app)

CORS(app, supports_credentials=True)

ADMIN_PASS_HASH = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()

# ─── Fallback: dados locais (JSON) caso a base falhe ──────────────────────
FALLBACK_FILE = os.path.join(BASE_DIR, 'fallback_data.json')

def load_fallback_noticias():
    try:
        with open(FALLBACK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_fallback_noticias(noticias):
    with open(FALLBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

# ─── Inicialização da Base de Dados ──────────────────────────────────────────

def init_db():
    """Cria as tabelas se não existirem."""
    log.info("A inicializar base de dados com SQLAlchemy...")
    try:
        with app.app_context():
            # Cria todas as tabelas definidas (usamos raw SQL para maior controlo)
            with db.engine.connect() as conn:
                conn.execute(text("""
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
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS categorias (
                        id    SERIAL PRIMARY KEY,
                        nome  TEXT NOT NULL UNIQUE
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS galeria (
                        id         SERIAL PRIMARY KEY,
                        noticia_id TEXT NOT NULL REFERENCES noticias(id) ON DELETE CASCADE,
                        imagem     TEXT NOT NULL,
                        ordem      INTEGER DEFAULT 0
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS imagens (
                        id         TEXT PRIMARY KEY,
                        dados      BYTEA NOT NULL,
                        mime       TEXT NOT NULL,
                        criado_em  TEXT NOT NULL
                    );
                """))
                # Inserir categorias padrão
                categorias = ['Futebol', 'Modalidades', 'Mercado', 'Formação', 'Opinião']
                for cat in categorias:
                    conn.execute(
                        text("INSERT INTO categorias (nome) VALUES (:nome) ON CONFLICT (nome) DO NOTHING"),
                        {'nome': cat}
                    )
                conn.commit()
        log.info("Base de dados inicializada com sucesso!")
        return True
    except Exception as e:
        log.error(f"Erro ao inicializar base de dados: {e}")
        return False

# ─── Funções auxiliares com fallback ──────────────────────────────────────

def execute_db_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Executa uma query com tratamento de erro e fallback para JSON."""
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                if commit:
                    conn.execute(text(query), params or {})
                    conn.commit()
                    return True
                result = conn.execute(text(query), params or {})
                if fetch_one:
                    row = result.fetchone()
                    return dict(row._mapping) if row else None
                if fetch_all:
                    return [dict(r._mapping) for r in result.fetchall()]
                return result
    except Exception as e:
        log.error(f"Erro na query: {e}")
        # Fallback: se for uma leitura e não houver dados, retorna lista vazia ou None
        if fetch_all:
            return []
        if fetch_one:
            return None
        raise

# ─── Funções específicas ──────────────────────────────────────────────────

def guardar_imagem_na_db(file_storage):
    """Guarda imagem na tabela imagens e retorna URL."""
    try:
        ext = file_storage.filename.rsplit('.', 1)[1].lower()
        mime = MIME_POR_EXT.get(ext, file_storage.mimetype or 'application/octet-stream')
        dados = file_storage.read()
        iid = uuid.uuid4().hex
        with app.app_context():
            with db.engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO imagens (id, dados, mime, criado_em) VALUES (:id, :dados, :mime, :criado_em)"),
                    {'id': iid, 'dados': dados, 'mime': mime, 'criado_em': datetime.now().isoformat()}
                )
                conn.commit()
        return f"/api/imagem/{iid}"
    except Exception as e:
        log.error(f"Erro ao guardar imagem: {e}")
        raise

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

# ─── Rotas estáticas ─────────────────────────────────────────────────────────

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

@app.route('/api/imagem/<iid>')
def api_imagem(iid):
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT dados, mime FROM imagens WHERE id = :id"),
                    {'id': iid}
                ).fetchone()
                if not row:
                    return jsonify({'erro': 'Imagem não encontrada'}), 404
                dados = row._mapping['dados']
                mime = row._mapping['mime']
                resp = Response(bytes(dados), mimetype=mime)
                resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                return resp
    except Exception as e:
        log.error(f"Erro ao servir imagem: {e}")
        return jsonify({'erro': 'Erro interno'}), 500

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

# ─── API Públicas ────────────────────────────────────────────────────────────

@app.route('/api/noticias')
def api_noticias():
    try:
        cat = request.args.get('categoria', '').strip()
        q   = request.args.get('q', '').strip()
        lim = min(int(request.args.get('limite', 50)), 100)
        off = int(request.args.get('offset', 0))
        params = {}
        conditions = []
        if cat:
            conditions.append("categoria = :cat")
            params['cat'] = cat
        if q:
            conditions.append("(titulo ILIKE :q1 OR subtitulo ILIKE :q2)")
            params['q1'] = f'%{q}%'
            params['q2'] = f'%{q}%'
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM noticias {where}
            ORDER BY destaque DESC, data DESC, criado_em DESC
            LIMIT :lim OFFSET :off
        """
        params['lim'] = lim
        params['off'] = off
        rows = execute_db_query(query, params, fetch_all=True)
        # Contagem total
        count_query = f"SELECT COUNT(*) FROM noticias {where}"
        count_params = {k:v for k,v in params.items() if k not in ('lim','off')}
        total = execute_db_query(count_query, count_params, fetch_one=True)
        total = total['count'] if total else 0
        return jsonify({'noticias': rows, 'total': total})
    except Exception as e:
        log.error(f"Erro em /api/noticias: {e}")
        return jsonify({'noticias': [], 'total': 0}), 500

@app.route('/api/noticias/destaque')
def api_destaque():
    try:
        row = execute_db_query(
            "SELECT * FROM noticias WHERE destaque=TRUE ORDER BY data DESC LIMIT 1",
            fetch_one=True
        )
        if not row:
            row = execute_db_query(
                "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT 1",
                fetch_one=True
            )
        return jsonify(row or {})
    except Exception as e:
        log.error(f"Erro em /api/noticias/destaque: {e}")
        return jsonify({}), 500

@app.route('/api/noticias/recentes')
def api_recentes():
    try:
        lim = min(int(request.args.get('limite', 6)), 20)
        rows = execute_db_query(
            "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT :lim",
            {'lim': lim}, fetch_all=True
        )
        return jsonify(rows)
    except Exception as e:
        log.error(f"Erro em /api/noticias/recentes: {e}")
        return jsonify([]), 500

@app.route('/api/noticias/mais-lidas')
def api_mais_lidas():
    try:
        rows = execute_db_query(
            "SELECT * FROM noticias ORDER BY leituras DESC, data DESC LIMIT 5",
            fetch_all=True
        )
        return jsonify(rows)
    except Exception as e:
        log.error(f"Erro em /api/noticias/mais-lidas: {e}")
        return jsonify([]), 500

@app.route('/api/noticias/<nid>')
def api_noticia(nid):
    try:
        row = execute_db_query(
            "SELECT * FROM noticias WHERE id = :id",
            {'id': nid}, fetch_one=True
        )
        if not row:
            return jsonify({'erro': 'Não encontrada'}), 404
        galeria = execute_db_query(
            "SELECT imagem FROM galeria WHERE noticia_id = :id ORDER BY ordem",
            {'id': nid}, fetch_all=True
        )
        relacionadas = execute_db_query(
            """
            SELECT * FROM noticias
            WHERE categoria = :cat AND id != :id
            ORDER BY data DESC LIMIT 3
            """,
            {'cat': row['categoria'], 'id': nid}, fetch_all=True
        )
        row['galeria'] = [g['imagem'] for g in galeria]
        row['relacionadas'] = relacionadas
        return jsonify(row)
    except Exception as e:
        log.error(f"Erro em /api/noticias/{nid}: {e}")
        return jsonify({'erro': 'Erro ao carregar notícia'}), 500

@app.route('/api/noticias/<nid>/leitura', methods=['POST'])
def api_leitura(nid):
    try:
        execute_db_query(
            "UPDATE noticias SET leituras = leituras + 1 WHERE id = :id",
            {'id': nid}, commit=True
        )
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em leitura: {e}")
        return jsonify({'erro': 'Erro ao registrar leitura'}), 500

@app.route('/api/categorias')
@app.route('/api/categories')  # alias para compatibilidade
def api_categorias():
    try:
        rows = execute_db_query("SELECT nome FROM categorias ORDER BY nome", fetch_all=True)
        return jsonify([r['nome'] for r in rows])
    except Exception as e:
        log.error(f"Erro em /api/categorias: {e}")
        return jsonify([]), 500

# ─── API Admin ────────────────────────────────────────────────────────────────

@app.route('/api/admin/noticias', methods=['GET'])
@login_required
def admin_listar():
    try:
        q = request.args.get('q', '').strip()
        cat = request.args.get('categoria', '').strip()
        params = {}
        conditions = []
        if q:
            conditions.append("(titulo ILIKE :q1 OR autor ILIKE :q2)")
            params['q1'] = f'%{q}%'
            params['q2'] = f'%{q}%'
        if cat:
            conditions.append("categoria = :cat")
            params['cat'] = cat
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = execute_db_query(
            f"SELECT * FROM noticias {where} ORDER BY data DESC, criado_em DESC",
            params, fetch_all=True
        )
        return jsonify(rows)
    except Exception as e:
        log.error(f"Erro em admin_listar: {e}")
        return jsonify({'erro': 'Erro ao carregar notícias'}), 500

@app.route('/api/admin/noticias', methods=['POST'])
@login_required
def admin_criar():
    try:
        data = request.get_json() or {}
        erros = []
        if not data.get('titulo', '').strip(): erros.append('título')
        if not data.get('autor', '').strip(): erros.append('autor')
        if not data.get('data', '').strip(): erros.append('data')
        if not data.get('conteudo', '').strip(): erros.append('conteúdo')
        if erros:
            return jsonify({'erro': f'Campos obrigatórios: {", ".join(erros)}'}), 400

        nid = str(uuid.uuid4())[:8]
        agora = datetime.now().isoformat()
        with app.app_context():
            with db.engine.connect() as conn:
                if data.get('destaque'):
                    conn.execute(text("UPDATE noticias SET destaque=FALSE"))
                conn.execute(
                    text("""
                        INSERT INTO noticias
                        (id, titulo, subtitulo, autor, data, categoria, imagem, conteudo, destaque, leituras, criado_em, editado_em)
                        VALUES (:id, :titulo, :subtitulo, :autor, :data, :categoria, :imagem, :conteudo, :destaque, 0, :criado_em, :editado_em)
                    """),
                    {
                        'id': nid,
                        'titulo': data['titulo'].strip(),
                        'subtitulo': data.get('subtitulo', '').strip(),
                        'autor': data['autor'].strip(),
                        'data': data['data'].strip(),
                        'categoria': data.get('categoria', 'Futebol').strip(),
                        'imagem': data.get('imagem', '').strip(),
                        'conteudo': data['conteudo'].strip(),
                        'destaque': bool(data.get('destaque')),
                        'criado_em': agora,
                        'editado_em': agora
                    }
                )
                conn.commit()
                row = conn.execute(text("SELECT * FROM noticias WHERE id = :id"), {'id': nid}).fetchone()
                return jsonify(dict(row._mapping) if row else {})
    except Exception as e:
        log.error(f"Erro em admin_criar: {e}")
        return jsonify({'erro': 'Erro ao criar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['PUT'])
@login_required
def admin_editar(nid):
    try:
        data = request.get_json() or {}
        agora = datetime.now().isoformat()
        with app.app_context():
            with db.engine.connect() as conn:
                # Verifica se existe
                exists = conn.execute(text("SELECT id FROM noticias WHERE id = :id"), {'id': nid}).fetchone()
                if not exists:
                    return jsonify({'erro': 'Não encontrada'}), 404
                if data.get('destaque'):
                    conn.execute(text("UPDATE noticias SET destaque=FALSE WHERE id != :id"), {'id': nid})
                conn.execute(
                    text("""
                        UPDATE noticias SET
                            titulo = :titulo,
                            subtitulo = :subtitulo,
                            autor = :autor,
                            data = :data,
                            categoria = :categoria,
                            imagem = :imagem,
                            conteudo = :conteudo,
                            destaque = :destaque,
                            editado_em = :editado_em
                        WHERE id = :id
                    """),
                    {
                        'id': nid,
                        'titulo': data.get('titulo', '').strip(),
                        'subtitulo': data.get('subtitulo', '').strip(),
                        'autor': data.get('autor', '').strip(),
                        'data': data.get('data', '').strip(),
                        'categoria': data.get('categoria', 'Futebol').strip(),
                        'imagem': data.get('imagem', '').strip(),
                        'conteudo': data.get('conteudo', '').strip(),
                        'destaque': bool(data.get('destaque')),
                        'editado_em': agora
                    }
                )
                conn.commit()
                row = conn.execute(text("SELECT * FROM noticias WHERE id = :id"), {'id': nid}).fetchone()
                return jsonify(dict(row._mapping) if row else {})
    except Exception as e:
        log.error(f"Erro em admin_editar: {e}")
        return jsonify({'erro': 'Erro ao editar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['DELETE'])
@login_required
def admin_apagar(nid):
    try:
        execute_db_query("DELETE FROM noticias WHERE id = :id", {'id': nid}, commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em admin_apagar: {e}")
        return jsonify({'erro': 'Erro ao apagar notícia'}), 500

@app.route('/api/admin/noticias/<nid>/destaque', methods=['POST'])
@login_required
def admin_destaque(nid):
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                row = conn.execute(text("SELECT destaque FROM noticias WHERE id = :id"), {'id': nid}).fetchone()
                if not row:
                    return jsonify({'erro': 'Não encontrada'}), 404
                novo = not row._mapping['destaque']
                if novo:
                    conn.execute(text("UPDATE noticias SET destaque=FALSE"))
                conn.execute(text("UPDATE noticias SET destaque = :destaque WHERE id = :id"), {'destaque': novo, 'id': nid})
                conn.commit()
                return jsonify({'destaque': novo})
    except Exception as e:
        log.error(f"Erro em admin_destaque: {e}")
        return jsonify({'erro': 'Erro ao alterar destaque'}), 500

@app.route('/api/admin/upload', methods=['POST'])
@login_required
def admin_upload():
    try:
        if 'imagem' not in request.files:
            return jsonify({'erro': 'Nenhum ficheiro'}), 400
        f = request.files['imagem']
        if not f.filename or not allowed_file(f.filename):
            return jsonify({'erro': 'Tipo não permitido'}), 400
        url = guardar_imagem_na_db(f)
        return jsonify({'url': url, 'nome': url.rsplit('/', 1)[-1]})
    except Exception as e:
        log.error(f"Erro em admin_upload: {e}")
        return jsonify({'erro': 'Erro ao fazer upload'}), 500

# Galeria
@app.route('/api/admin/noticias/<nid>/galeria', methods=['POST'])
@login_required
def admin_galeria_add(nid):
    try:
        if 'imagem' not in request.files:
            return jsonify({'erro': 'Nenhum ficheiro'}), 400
        f = request.files['imagem']
        if not f.filename or not allowed_file(f.filename):
            return jsonify({'erro': 'Tipo não permitido'}), 400
        url = guardar_imagem_na_db(f)
        with app.app_context():
            with db.engine.connect() as conn:
                ordem = conn.execute(
                    text("SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id = :id"),
                    {'id': nid}
                ).fetchone()[0]
                conn.execute(
                    text("INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (:id, :imagem, :ordem)"),
                    {'id': nid, 'imagem': url, 'ordem': ordem}
                )
                conn.commit()
                rows = conn.execute(
                    text("SELECT * FROM galeria WHERE noticia_id = :id ORDER BY ordem"),
                    {'id': nid}
                ).fetchall()
                return jsonify({'url': url, 'galeria': [dict(r._mapping) for r in rows]})
    except Exception as e:
        log.error(f"Erro em admin_galeria_add: {e}")
        return jsonify({'erro': 'Erro ao adicionar à galeria'}), 500

@app.route('/api/admin/noticias/<nid>/galeria', methods=['GET'])
@login_required
def admin_galeria_get(nid):
    try:
        rows = execute_db_query(
            "SELECT * FROM galeria WHERE noticia_id = :id ORDER BY ordem",
            {'id': nid}, fetch_all=True
        )
        return jsonify(rows)
    except Exception as e:
        log.error(f"Erro em admin_galeria_get: {e}")
        return jsonify({'erro': 'Erro ao listar galeria'}), 500

@app.route('/api/admin/galeria/<int:gid>', methods=['DELETE'])
@login_required
def admin_galeria_delete(gid):
    try:
        execute_db_query("DELETE FROM galeria WHERE id = :id", {'id': gid}, commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em admin_galeria_delete: {e}")
        return jsonify({'erro': 'Erro ao remover da galeria'}), 500

@app.route('/api/admin/galeria/url', methods=['POST'])
@login_required
def admin_galeria_add_url():
    try:
        data = request.get_json() or {}
        nid = data.get('noticia_id', '').strip()
        url = data.get('url', '').strip()
        if not nid or not url:
            return jsonify({'erro': 'noticia_id e url obrigatórios'}), 400
        with app.app_context():
            with db.engine.connect() as conn:
                ordem = conn.execute(
                    text("SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id = :id"),
                    {'id': nid}
                ).fetchone()[0]
                conn.execute(
                    text("INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (:id, :imagem, :ordem)"),
                    {'id': nid, 'imagem': url, 'ordem': ordem}
                )
                conn.commit()
                rows = conn.execute(
                    text("SELECT * FROM galeria WHERE noticia_id = :id ORDER BY ordem"),
                    {'id': nid}
                ).fetchall()
                return jsonify({'galeria': [dict(r._mapping) for r in rows]})
    except Exception as e:
        log.error(f"Erro em admin_galeria_add_url: {e}")
        return jsonify({'erro': 'Erro ao adicionar URL'}), 500

@app.route('/api/admin/categorias', methods=['GET'])
@login_required
def admin_cats():
    try:
        rows = execute_db_query("SELECT nome FROM categorias ORDER BY nome", fetch_all=True)
        return jsonify([r['nome'] for r in rows])
    except Exception as e:
        log.error(f"Erro em admin_cats: {e}")
        return jsonify({'erro': 'Erro ao listar categorias'}), 500

@app.route('/api/admin/categorias', methods=['POST'])
@login_required
def admin_criar_cat():
    try:
        data = request.get_json() or {}
        nome = data.get('nome', '').strip()
        if not nome:
            return jsonify({'erro': 'Nome obrigatório'}), 400
        with app.app_context():
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("INSERT INTO categorias (nome) VALUES (:nome)"), {'nome': nome})
                    conn.commit()
                except exc.IntegrityError:
                    return jsonify({'erro': 'Categoria já existe'}), 409
        return jsonify({'ok': True, 'nome': nome})
    except Exception as e:
        log.error(f"Erro em admin_criar_cat: {e}")
        return jsonify({'erro': 'Erro ao criar categoria'}), 500

@app.route('/api/admin/categorias/<nome>', methods=['DELETE'])
@login_required
def admin_apagar_cat(nome):
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                em_uso = conn.execute(
                    text("SELECT COUNT(*) FROM noticias WHERE categoria = :nome"),
                    {'nome': nome}
                ).fetchone()[0]
                if em_uso:
                    return jsonify({'erro': f'Em uso por {em_uso} notícia(s)'}), 409
                conn.execute(text("DELETE FROM categorias WHERE nome = :nome"), {'nome': nome})
                conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em admin_apagar_cat: {e}")
        return jsonify({'erro': 'Erro ao apagar categoria'}), 500

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                total = conn.execute(text("SELECT COUNT(*) FROM noticias")).fetchone()[0]
                destaques = conn.execute(text("SELECT COUNT(*) FROM noticias WHERE destaque=TRUE")).fetchone()[0]
                total_cats = conn.execute(text("SELECT COUNT(*) FROM categorias")).fetchone()[0]
                por_cat = conn.execute(
                    text("SELECT categoria, COUNT(*) as n FROM noticias GROUP BY categoria ORDER BY n DESC")
                ).fetchall()
                recentes = conn.execute(
                    text("SELECT * FROM noticias ORDER BY criado_em DESC LIMIT 5")
                ).fetchall()
                return jsonify({
                    'total': total,
                    'destaques': destaques,
                    'total_categorias': total_cats,
                    'por_categoria': [dict(r._mapping) for r in por_cat],
                    'recentes': [dict(r._mapping) for r in recentes]
                })
    except Exception as e:
        log.error(f"Erro em admin_stats: {e}")
        return jsonify({'erro': 'Erro ao buscar estatísticas'}), 500

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    try:
        with app.app_context():
            db.engine.execute("SELECT 1")
        return jsonify({'status': 'ok', 'database': 'connected'})
    except Exception as e:
        log.error(f"Health check falhou: {e}")
        return jsonify({'status': 'error', 'database': 'disconnected', 'detail': str(e)}), 500

# ─── Inicialização ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'

    # Inicializa a base de dados (se falhar, avisa)
    if not init_db():
        log.warning("Falha ao inicializar a base de dados. A aplicação pode funcionar com dados locais?")
        # Criar um ficheiro de fallback vazio se não existir
        if not os.path.exists(FALLBACK_FILE):
            save_fallback_noticias([])

    log.info(f"Servidor a iniciar na porta {porta}")
    app.run(host='0.0.0.0', port=porta, debug=debug)
