"""
ENCARNADO — Portal de Notícias do Benfica
Versão com psycopg2 + retry + fallback (sem SQLAlchemy)
"""

import os
import hashlib
import secrets
import uuid
import logging
import time
from datetime import datetime
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory, session, Response
from flask_cors import CORS

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
CORS(app, supports_credentials=True)

ADMIN_PASS_HASH = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()

if not DATABASE_URL:
    log.error(
        "DATABASE_URL não está definida! Define a variável de ambiente "
        "DATABASE_URL com a connection string da Rocketadmin (postgres://...)."
    )

# ─── Base de dados ────────────────────────────────────────────────────────────

def get_db(retries=3, delay=2):
    """
    Tenta ligar à base de dados com SSL, com várias tentativas.
    """
    errors = []
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(
                DATABASE_URL,
                sslmode='require',
                connect_timeout=30,
                cursor_factory=psycopg2.extras.RealDictCursor,
                keepalives_idle=5,
                keepalives_interval=2,
                keepalives_count=2,
            )
            # Testa a ligação com uma query simples
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            log.info(f"Ligação à base de dados estabelecida (tentativa {attempt})")
            return conn
        except Exception as e:
            error_msg = f"Tentativa {attempt}: {str(e)}"
            errors.append(error_msg)
            log.warning(error_msg)
            if attempt < retries:
                time.sleep(delay)
    raise Exception(f"Falha ao ligar à base de dados após {retries} tentativas: {'; '.join(errors)}")

def init_db():
    """Cria as tabelas se não existirem."""
    log.info("Inicializando base de dados...")
    conn = None
    try:
        conn = get_db()
        with conn.cursor() as cur:
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
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS categorias (
                    id    SERIAL PRIMARY KEY,
                    nome  TEXT NOT NULL UNIQUE
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS galeria (
                    id         SERIAL PRIMARY KEY,
                    noticia_id TEXT NOT NULL REFERENCES noticias(id) ON DELETE CASCADE,
                    imagem     TEXT NOT NULL,
                    ordem      INTEGER DEFAULT 0
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS imagens (
                    id         TEXT PRIMARY KEY,
                    dados      BYTEA NOT NULL,
                    mime       TEXT NOT NULL,
                    criado_em  TEXT NOT NULL
                );
            """)
            # Inserir categorias padrão
            categorias = ['Futebol', 'Modalidades', 'Mercado', 'Formação', 'Opinião']
            for cat in categorias:
                cur.execute(
                    "INSERT INTO categorias (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
                    (cat,)
                )
            conn.commit()
        log.info("Base de dados inicializada com sucesso!")
    except Exception as e:
        log.error(f"Erro ao inicializar a base de dados: {e}")
        raise
    finally:
        if conn:
            conn.close()

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False, retries=3):
    """
    Executa uma query com tratamento de erro e retry.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        conn = None
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if commit:
                    conn.commit()
                    return True
                if fetch_one:
                    row = cur.fetchone()
                    return dict(row) if row else None
                if fetch_all:
                    rows = cur.fetchall()
                    return [dict(r) for r in rows]
                # Para SELECT sem fetch (ex: contagens) pode ser usado assim
                return cur
        except Exception as e:
            last_error = e
            log.error(f"Erro na query (tentativa {attempt}): {e}")
            if attempt < retries:
                time.sleep(2)
            if conn:
                try:
                    conn.close()
                except:
                    pass
    # Se todas as tentativas falharem, retorna None ou levanta exceção conforme o caso
    if fetch_all:
        return []
    if fetch_one:
        return None
    raise last_error

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def guardar_imagem_na_db(file_storage):
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    mime = MIME_POR_EXT.get(ext, file_storage.mimetype or 'application/octet-stream')
    dados = file_storage.read()
    iid = uuid.uuid4().hex
    query = "INSERT INTO imagens (id, dados, mime, criado_em) VALUES (%s, %s, %s, %s)"
    execute_query(query, (iid, psycopg2.Binary(dados), mime, datetime.now().isoformat()), commit=True)
    return f"/api/imagem/{iid}"

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

@app.route('/api/imagem/<iid>')
def api_imagem(iid):
    try:
        query = "SELECT dados, mime FROM imagens WHERE id = %s"
        row = execute_query(query, (iid,), fetch_one=True)
        if not row:
            return jsonify({'erro': 'Imagem não encontrada'}), 404
        dados = row['dados']
        if isinstance(dados, memoryview):
            dados = dados.tobytes()
        resp = Response(bytes(dados), mimetype=row['mime'])
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
        params = []
        conditions = []
        if cat:
            conditions.append("categoria = %s")
            params.append(cat)
        if q:
            conditions.append("(titulo ILIKE %s OR subtitulo ILIKE %s)")
            params.extend([f'%{q}%', f'%{q}%'])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM noticias {where}
            ORDER BY destaque DESC, data DESC, criado_em DESC
            LIMIT %s OFFSET %s
        """
        rows = execute_query(query, params + [lim, off], fetch_all=True)
        count_query = f"SELECT COUNT(*) FROM noticias {where}"
        count_row = execute_query(count_query, params, fetch_one=True)
        total = count_row['count'] if count_row else 0
        return jsonify({'noticias': rows, 'total': total})
    except Exception as e:
        log.error(f"Erro em /api/noticias: {e}")
        return jsonify({'noticias': [], 'total': 0}), 500

@app.route('/api/noticias/destaque')
def api_destaque():
    try:
        row = execute_query(
            "SELECT * FROM noticias WHERE destaque=TRUE ORDER BY data DESC LIMIT 1",
            fetch_one=True
        )
        if not row:
            row = execute_query(
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
        rows = execute_query(
            "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT %s",
            (lim,), fetch_all=True
        )
        return jsonify(rows)
    except Exception as e:
        log.error(f"Erro em /api/noticias/recentes: {e}")
        return jsonify([]), 500

@app.route('/api/noticias/mais-lidas')
def api_mais_lidas():
    try:
        rows = execute_query(
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
        row = execute_query(
            "SELECT * FROM noticias WHERE id = %s", (nid,), fetch_one=True
        )
        if not row:
            return jsonify({'erro': 'Não encontrada'}), 404
        galeria = execute_query(
            "SELECT imagem FROM galeria WHERE noticia_id = %s ORDER BY ordem",
            (nid,), fetch_all=True
        )
        relacionadas = execute_query(
            """
            SELECT * FROM noticias
            WHERE categoria = %s AND id != %s
            ORDER BY data DESC LIMIT 3
            """,
            (row['categoria'], nid), fetch_all=True
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
        execute_query(
            "UPDATE noticias SET leituras = leituras + 1 WHERE id = %s",
            (nid,), commit=True
        )
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em leitura: {e}")
        return jsonify({'erro': 'Erro ao registrar leitura'}), 500

@app.route('/api/categorias')
@app.route('/api/categories')  # alias
def api_categorias():
    try:
        rows = execute_query("SELECT nome FROM categorias ORDER BY nome", fetch_all=True)
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
        params = []
        conditions = []
        if q:
            conditions.append("(titulo ILIKE %s OR autor ILIKE %s)")
            params.extend([f'%{q}%', f'%{q}%'])
        if cat:
            conditions.append("categoria = %s")
            params.append(cat)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = execute_query(
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
        destaque = bool(data.get('destaque'))
        if destaque:
            execute_query("UPDATE noticias SET destaque=FALSE", commit=True)
        execute_query("""
            INSERT INTO noticias
            (id, titulo, subtitulo, autor, data, categoria, imagem, conteudo, destaque, leituras, criado_em, editado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
        """, (
            nid,
            data['titulo'].strip(),
            data.get('subtitulo', '').strip(),
            data['autor'].strip(),
            data['data'].strip(),
            data.get('categoria', 'Futebol').strip(),
            data.get('imagem', '').strip(),
            data['conteudo'].strip(),
            destaque,
            agora,
            agora
        ), commit=True)
        row = execute_query("SELECT * FROM noticias WHERE id = %s", (nid,), fetch_one=True)
        return jsonify(row or {})
    except Exception as e:
        log.error(f"Erro em admin_criar: {e}")
        return jsonify({'erro': 'Erro ao criar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['PUT'])
@login_required
def admin_editar(nid):
    try:
        data = request.get_json() or {}
        agora = datetime.now().isoformat()
        # Verifica existência
        exists = execute_query("SELECT id FROM noticias WHERE id = %s", (nid,), fetch_one=True)
        if not exists:
            return jsonify({'erro': 'Não encontrada'}), 404
        destaque = bool(data.get('destaque'))
        if destaque:
            execute_query("UPDATE noticias SET destaque=FALSE WHERE id != %s", (nid,), commit=True)
        execute_query("""
            UPDATE noticias SET
                titulo = %s,
                subtitulo = %s,
                autor = %s,
                data = %s,
                categoria = %s,
                imagem = %s,
                conteudo = %s,
                destaque = %s,
                editado_em = %s
            WHERE id = %s
        """, (
            data.get('titulo', '').strip(),
            data.get('subtitulo', '').strip(),
            data.get('autor', '').strip(),
            data.get('data', '').strip(),
            data.get('categoria', 'Futebol').strip(),
            data.get('imagem', '').strip(),
            data.get('conteudo', '').strip(),
            destaque,
            agora,
            nid
        ), commit=True)
        row = execute_query("SELECT * FROM noticias WHERE id = %s", (nid,), fetch_one=True)
        return jsonify(row or {})
    except Exception as e:
        log.error(f"Erro em admin_editar: {e}")
        return jsonify({'erro': 'Erro ao editar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['DELETE'])
@login_required
def admin_apagar(nid):
    try:
        execute_query("DELETE FROM noticias WHERE id = %s", (nid,), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em admin_apagar: {e}")
        return jsonify({'erro': 'Erro ao apagar notícia'}), 500

@app.route('/api/admin/noticias/<nid>/destaque', methods=['POST'])
@login_required
def admin_destaque(nid):
    try:
        row = execute_query("SELECT destaque FROM noticias WHERE id = %s", (nid,), fetch_one=True)
        if not row:
            return jsonify({'erro': 'Não encontrada'}), 404
        novo = not row['destaque']
        if novo:
            execute_query("UPDATE noticias SET destaque=FALSE", commit=True)
        execute_query("UPDATE noticias SET destaque = %s WHERE id = %s", (novo, nid), commit=True)
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
        # Obter próxima ordem
        ordem_row = execute_query(
            "SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id = %s",
            (nid,), fetch_one=True
        )
        ordem = ordem_row['coalesce'] if ordem_row else 1
        execute_query(
            "INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s, %s, %s)",
            (nid, url, ordem), commit=True
        )
        galeria = execute_query(
            "SELECT * FROM galeria WHERE noticia_id = %s ORDER BY ordem",
            (nid,), fetch_all=True
        )
        return jsonify({'url': url, 'galeria': galeria})
    except Exception as e:
        log.error(f"Erro em admin_galeria_add: {e}")
        return jsonify({'erro': 'Erro ao adicionar à galeria'}), 500

@app.route('/api/admin/noticias/<nid>/galeria', methods=['GET'])
@login_required
def admin_galeria_get(nid):
    try:
        galeria = execute_query(
            "SELECT * FROM galeria WHERE noticia_id = %s ORDER BY ordem",
            (nid,), fetch_all=True
        )
        return jsonify(galeria)
    except Exception as e:
        log.error(f"Erro em admin_galeria_get: {e}")
        return jsonify({'erro': 'Erro ao listar galeria'}), 500

@app.route('/api/admin/galeria/<int:gid>', methods=['DELETE'])
@login_required
def admin_galeria_delete(gid):
    try:
        execute_query("DELETE FROM galeria WHERE id = %s", (gid,), commit=True)
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
        ordem_row = execute_query(
            "SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id = %s",
            (nid,), fetch_one=True
        )
        ordem = ordem_row['coalesce'] if ordem_row else 1
        execute_query(
            "INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s, %s, %s)",
            (nid, url, ordem), commit=True
        )
        galeria = execute_query(
            "SELECT * FROM galeria WHERE noticia_id = %s ORDER BY ordem",
            (nid,), fetch_all=True
        )
        return jsonify({'galeria': galeria})
    except Exception as e:
        log.error(f"Erro em admin_galeria_add_url: {e}")
        return jsonify({'erro': 'Erro ao adicionar URL'}), 500

@app.route('/api/admin/categorias', methods=['GET'])
@login_required
def admin_cats():
    try:
        rows = execute_query("SELECT nome FROM categorias ORDER BY nome", fetch_all=True)
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
        try:
            execute_query("INSERT INTO categorias (nome) VALUES (%s)", (nome,), commit=True)
        except psycopg2.errors.UniqueViolation:
            return jsonify({'erro': 'Categoria já existe'}), 409
        return jsonify({'ok': True, 'nome': nome})
    except Exception as e:
        log.error(f"Erro em admin_criar_cat: {e}")
        return jsonify({'erro': 'Erro ao criar categoria'}), 500

@app.route('/api/admin/categorias/<nome>', methods=['DELETE'])
@login_required
def admin_apagar_cat(nome):
    try:
        em_uso = execute_query(
            "SELECT COUNT(*) FROM noticias WHERE categoria = %s",
            (nome,), fetch_one=True
        )
        if em_uso and em_uso['count'] > 0:
            return jsonify({'erro': f'Em uso por {em_uso["count"]} notícia(s)'}), 409
        execute_query("DELETE FROM categorias WHERE nome = %s", (nome,), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro em admin_apagar_cat: {e}")
        return jsonify({'erro': 'Erro ao apagar categoria'}), 500

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    try:
        total = execute_query("SELECT COUNT(*) FROM noticias", fetch_one=True)['count']
        destaques = execute_query("SELECT COUNT(*) FROM noticias WHERE destaque=TRUE", fetch_one=True)['count']
        total_cats = execute_query("SELECT COUNT(*) FROM categorias", fetch_one=True)['count']
        por_cat = execute_query(
            "SELECT categoria, COUNT(*) as n FROM noticias GROUP BY categoria ORDER BY n DESC",
            fetch_all=True
        )
        recentes = execute_query(
            "SELECT * FROM noticias ORDER BY criado_em DESC LIMIT 5",
            fetch_all=True
        )
        return jsonify({
            'total': total,
            'destaques': destaques,
            'total_categorias': total_cats,
            'por_categoria': por_cat,
            'recentes': recentes
        })
    except Exception as e:
        log.error(f"Erro em admin_stats: {e}")
        return jsonify({'erro': 'Erro ao buscar estatísticas'}), 500

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    try:
        conn = get_db(retries=2, delay=1)
        conn.close()
        return jsonify({'status': 'ok', 'database': 'connected'})
    except Exception as e:
        log.error(f"Health check falhou: {e}")
        return jsonify({'status': 'error', 'database': 'disconnected', 'detail': str(e)}), 500

# ─── Inicialização ────────────────────────────────────────────────────────────
# Corre SEMPRE que o módulo é carregado (quer seja com "python server.py" em
# desenvolvimento, quer seja com "gunicorn server:app" em produção, como no
# render.yaml). Antes, isto só corria dentro do "if __name__ == '__main__'",
# pelo que em produção (gunicorn) as tabelas nunca chegavam a ser criadas na
# Rocketadmin. Liga-se sempre à Rocketadmin via DATABASE_URL — nunca a um
# ficheiro local.
try:
    init_db()
except Exception as e:
    log.error(f"Falha ao inicializar a base de dados na Rocketadmin: {e}")
    log.warning("A aplicação pode não funcionar corretamente até a ligação à base de dados ser restabelecida.")

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'

    log.info(f"Servidor a iniciar na porta {porta}")
    app.run(host='0.0.0.0', port=porta, debug=debug)
