"""
ENCARNADO — Portal de Notícias do Benfica
server.py — Flask + PostgreSQL (Supabase/RocketAdmin)
Versão corrigida com múltiplas estratégias de conexão
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
from urllib.parse import urlparse

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR   = os.path.join(BASE_DIR, 'public', 'assets', 'images')
PUBLIC_DIR   = os.path.join(BASE_DIR, 'public')
ALLOWED_EXT  = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MIME_POR_EXT = {
    'png':  'image/png',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
    'gif':  'image/gif',
}
MAX_IMG_MB   = 8

# Conexão à base de dados PostgreSQL (RocketAdmin/Supabase)
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

# ─── Base de dados ────────────────────────────────────────────────────────────

def get_db_connection_params():
    """Extrai parâmetros de conexão da URL."""
    parsed = urlparse(DATABASE_URL)
    return {
        'dbname': parsed.path[1:],
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port or 5432,
    }

def get_db():
    """
    Obtém uma conexão com a base de dados com múltiplas estratégias.
    """
    errors = []
    
    # Estratégia 1: Conexão direta com SSL (recomendado)
    try:
        log.info("Tentando conexão com SSL...")
        conn = psycopg2.connect(
            DATABASE_URL,
            sslmode='require',
            connect_timeout=30,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        log.info("Conexão SSL estabelecida com sucesso!")
        return conn
    except Exception as e:
        errors.append(f"SSL: {str(e)}")
        log.warning(f"Falha na conexão SSL: {e}")
    
    # Estratégia 2: Tentar sem SSL (para debug)
    try:
        log.info("Tentando conexão sem SSL...")
        conn = psycopg2.connect(
            DATABASE_URL,
            sslmode='disable',
            connect_timeout=30,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        log.info("Conexão sem SSL estabelecida com sucesso!")
        return conn
    except Exception as e:
        errors.append(f"No-SSL: {str(e)}")
        log.warning(f"Falha na conexão sem SSL: {e}")
    
    # Estratégia 3: Conexão com parâmetros explícitos
    try:
        log.info("Tentando conexão com parâmetros explícitos...")
        params = get_db_connection_params()
        conn = psycopg2.connect(
            **params,
            sslmode='require',
            connect_timeout=30,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        log.info("Conexão com parâmetros explícitos estabelecida!")
        return conn
    except Exception as e:
        errors.append(f"Params: {str(e)}")
        log.warning(f"Falha com parâmetros explícitos: {e}")
    
    # Se chegamos aqui, todas as estratégias falharam
    error_msg = f"Todas as estratégias de conexão falharam: {'; '.join(errors)}"
    log.error(error_msg)
    raise Exception(error_msg)

def init_db():
    """Inicializa a base de dados com as tabelas necessárias."""
    log.info("A inicializar base de dados...")
    conn = None
    cur = None
    
    for attempt in range(3):
        try:
            log.info(f"Tentativa {attempt + 1} de inicializar base de dados...")
            conn = get_db()
            cur = conn.cursor()
            
            # Tabela de notícias
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
            
            # Tabela de categorias
            cur.execute("""
                CREATE TABLE IF NOT EXISTS categorias (
                    id    SERIAL PRIMARY KEY,
                    nome  TEXT NOT NULL UNIQUE
                );
            """)
            
            # Tabela de galeria
            cur.execute("""
                CREATE TABLE IF NOT EXISTS galeria (
                    id         SERIAL PRIMARY KEY,
                    noticia_id TEXT NOT NULL REFERENCES noticias(id) ON DELETE CASCADE,
                    imagem     TEXT NOT NULL,
                    ordem      INTEGER DEFAULT 0
                );
            """)
            
            # Tabela de imagens
            cur.execute("""
                CREATE TABLE IF NOT EXISTS imagens (
                    id         TEXT PRIMARY KEY,
                    dados      BYTEA NOT NULL,
                    mime       TEXT NOT NULL,
                    criado_em  TEXT NOT NULL
                );
            """)
            
            # Inserir categorias padrão usando transação
            categorias_padrao = ['Futebol', 'Modalidades', 'Mercado', 'Formação', 'Opinião']
            for cat in categorias_padrao:
                try:
                    cur.execute(
                        "INSERT INTO categorias (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
                        [cat]
                    )
                except Exception as e:
                    log.warning(f"Erro ao inserir categoria '{cat}': {e}")
            
            conn.commit()
            log.info("Base de dados inicializada com sucesso!")
            return True
            
        except Exception as e:
            log.error(f"Erro na tentativa {attempt + 1}: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            time.sleep(2)  # Espera 2 segundos antes de tentar novamente
        finally:
            if cur:
                try:
                    cur.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    log.error("Falha ao inicializar base de dados após 3 tentativas")
    return False

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def guardar_imagem_na_db(file_storage):
    """Guarda uma imagem na base de dados e retorna o URL público."""
    for attempt in range(3):
        try:
            ext = file_storage.filename.rsplit('.', 1)[1].lower()
            mime = MIME_POR_EXT.get(ext, file_storage.mimetype or 'application/octet-stream')
            dados = file_storage.read()
            iid = uuid.uuid4().hex
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO imagens (id, dados, mime, criado_em) VALUES (%s, %s, %s, %s)",
                [iid, psycopg2.Binary(dados), mime, datetime.now().isoformat()]
            )
            conn.commit()
            cur.close()
            conn.close()
            
            return f"/api/imagem/{iid}"
        except Exception as e:
            log.error(f"Erro ao guardar imagem (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    raise Exception("Falha ao guardar imagem após 3 tentativas")

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
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT dados, mime FROM imagens WHERE id=%s", [iid])
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if not row:
                return jsonify({'erro': 'Imagem não encontrada'}), 404
            
            dados = row['dados']
            if isinstance(dados, memoryview):
                dados = dados.tobytes()
            
            resp = Response(bytes(dados), mimetype=row['mime'])
            resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            return resp
        except Exception as e:
            log.error(f"Erro ao servir imagem (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify({'erro': 'Erro ao servir imagem'}), 500

# ─── API Auth ─────────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json() or {}
        user = data.get('utilizador', '').strip()
        pw   = data.get('senha', '')
        
        if user == ADMIN_USER and hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASS_HASH:
            session['admin'] = True
            return jsonify({'ok': True})
        
        return jsonify({'erro': 'Credenciais incorretas'}), 401
    except Exception as e:
        log.error(f"Erro no login: {e}")
        return jsonify({'erro': 'Erro interno'}), 500

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
    for attempt in range(3):
        try:
            cat = request.args.get('categoria', '').strip()
            q   = request.args.get('q', '').strip()
            lim = min(int(request.args.get('limite', 50)), 100)
            off = int(request.args.get('offset', 0))
            
            conn = get_db()
            cur = conn.cursor()
            conditions = []
            params = []
            
            if cat:
                conditions.append("categoria = %s")
                params.append(cat)
            if q:
                conditions.append("(titulo ILIKE %s OR subtitulo ILIKE %s)")
                params.extend([f'%{q}%', f'%{q}%'])
            
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            
            query = f"""
                SELECT * FROM noticias 
                {where} 
                ORDER BY destaque DESC, data DESC, criado_em DESC 
                LIMIT %s OFFSET %s
            """
            cur.execute(query, params + [lim, off])
            rows = cur.fetchall()
            
            count_query = f"SELECT COUNT(*) FROM noticias {where}"
            cur.execute(count_query, params)
            total = cur.fetchone()['count']
            
            cur.close()
            conn.close()
            
            return jsonify({
                'noticias': [dict(r) for r in rows],
                'total': total
            })
        except Exception as e:
            log.error(f"Erro ao listar notícias (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify({'noticias': [], 'total': 0}), 500

@app.route('/api/noticias/destaque')
def api_destaque():
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT * FROM noticias WHERE destaque=TRUE ORDER BY data DESC LIMIT 1")
            row = cur.fetchone()
            
            if not row:
                cur.execute("SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT 1")
                row = cur.fetchone()
            
            cur.close()
            conn.close()
            
            return jsonify(dict(row) if row else {})
        except Exception as e:
            log.error(f"Erro ao buscar destaque (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify({}), 500

@app.route('/api/noticias/recentes')
def api_recentes():
    for attempt in range(3):
        try:
            lim = min(int(request.args.get('limite', 6)), 20)
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM noticias ORDER BY data DESC, criado_em DESC LIMIT %s",
                [lim]
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify([dict(r) for r in rows])
        except Exception as e:
            log.error(f"Erro ao buscar notícias recentes (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify([]), 500

@app.route('/api/noticias/mais-lidas')
def api_mais_lidas():
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM noticias ORDER BY leituras DESC, data DESC LIMIT 5"
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify([dict(r) for r in rows])
        except Exception as e:
            log.error(f"Erro ao buscar notícias mais lidas (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify([]), 500

@app.route('/api/noticias/<nid>')
def api_noticia(nid):
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
            row = cur.fetchone()
            
            if not row:
                cur.close()
                conn.close()
                return jsonify({'erro': 'Não encontrada'}), 404
            
            cur.execute(
                "SELECT imagem FROM galeria WHERE noticia_id=%s ORDER BY ordem",
                [nid]
            )
            galeria = cur.fetchall()
            
            cur.execute(
                """
                SELECT * FROM noticias 
                WHERE categoria=%s AND id!=%s 
                ORDER BY data DESC 
                LIMIT 3
                """,
                [row['categoria'], nid]
            )
            relacionadas = cur.fetchall()
            
            cur.close()
            conn.close()
            
            result = dict(row)
            result['galeria'] = [r['imagem'] for r in galeria]
            result['relacionadas'] = [dict(r) for r in relacionadas]
            
            return jsonify(result)
        except Exception as e:
            log.error(f"Erro ao buscar notícia {nid} (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify({'erro': 'Erro ao carregar notícia'}), 500

@app.route('/api/noticias/<nid>/leitura', methods=['POST'])
def api_leitura(nid):
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "UPDATE noticias SET leituras = leituras + 1 WHERE id=%s",
                [nid]
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'ok': True})
        except Exception as e:
            log.error(f"Erro ao incrementar leituras (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify({'erro': 'Erro ao registrar leitura'}), 500

@app.route('/api/categorias')
def api_categorias():
    for attempt in range(3):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT nome FROM categorias ORDER BY nome")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify([r['nome'] for r in rows])
        except Exception as e:
            log.error(f"Erro ao buscar categorias (tentativa {attempt + 1}): {e}")
            time.sleep(1)
    
    return jsonify([]), 500

@app.route('/api/categories')
def api_categories_legacy():
    """Endpoint legacy para compatibilidade."""
    return api_categorias()

# ─── API Admin ────────────────────────────────────────────────────────────────

@app.route('/api/admin/noticias', methods=['GET'])
@login_required
def admin_listar():
    try:
        q = request.args.get('q', '').strip()
        cat = request.args.get('categoria', '').strip()
        
        conn = get_db()
        cur = conn.cursor()
        conditions = []
        params = []
        
        if q:
            conditions.append("(titulo ILIKE %s OR autor ILIKE %s)")
            params.extend([f'%{q}%', f'%{q}%'])
        if cat:
            conditions.append("categoria = %s")
            params.append(cat)
        
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM noticias {where} ORDER BY data DESC, criado_em DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log.error(f"Erro ao listar notícias admin: {e}")
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
        
        conn = get_db()
        cur = conn.cursor()
        
        if data.get('destaque'):
            cur.execute("UPDATE noticias SET destaque=FALSE")
        
        cur.execute("""
            INSERT INTO noticias (id,titulo,subtitulo,autor,data,categoria,imagem,conteudo,destaque,leituras,criado_em,editado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s)
        """, [
            nid,
            data['titulo'].strip(),
            data.get('subtitulo', '').strip(),
            data['autor'].strip(),
            data['data'].strip(),
            data.get('categoria', 'Futebol').strip(),
            data.get('imagem', '').strip(),
            data['conteudo'].strip(),
            bool(data.get('destaque')),
            agora,
            agora
        ])
        conn.commit()
        
        cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return jsonify(dict(row)), 201
    except Exception as e:
        log.error(f"Erro ao criar notícia: {e}")
        return jsonify({'erro': 'Erro ao criar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['PUT'])
@login_required
def admin_editar(nid):
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM noticias WHERE id=%s", [nid])
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'erro': 'Não encontrada'}), 404
        
        data = request.get_json() or {}
        agora = datetime.now().isoformat()
        
        if data.get('destaque'):
            cur.execute("UPDATE noticias SET destaque=FALSE WHERE id!=%s", [nid])
        
        cur.execute("""
            UPDATE noticias 
            SET titulo=%s, subtitulo=%s, autor=%s, data=%s, categoria=%s,
                imagem=%s, conteudo=%s, destaque=%s, editado_em=%s 
            WHERE id=%s
        """, [
            data.get('titulo', '').strip(),
            data.get('subtitulo', '').strip(),
            data.get('autor', '').strip(),
            data.get('data', '').strip(),
            data.get('categoria', 'Futebol').strip(),
            data.get('imagem', '').strip(),
            data.get('conteudo', '').strip(),
            bool(data.get('destaque')),
            agora,
            nid
        ])
        conn.commit()
        
        cur.execute("SELECT * FROM noticias WHERE id=%s", [nid])
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return jsonify(dict(row))
    except Exception as e:
        log.error(f"Erro ao editar notícia {nid}: {e}")
        return jsonify({'erro': 'Erro ao editar notícia'}), 500

@app.route('/api/admin/noticias/<nid>', methods=['DELETE'])
@login_required
def admin_apagar(nid):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM noticias WHERE id=%s", [nid])
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro ao apagar notícia {nid}: {e}")
        return jsonify({'erro': 'Erro ao apagar notícia'}), 500

@app.route('/api/admin/noticias/<nid>/destaque', methods=['POST'])
@login_required
def admin_destaque(nid):
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT destaque FROM noticias WHERE id=%s", [nid])
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return jsonify({'erro': 'Não encontrada'}), 404
        
        novo = not row['destaque']
        if novo:
            cur.execute("UPDATE noticias SET destaque=FALSE")
        cur.execute("UPDATE noticias SET destaque=%s WHERE id=%s", [novo, nid])
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'destaque': novo})
    except Exception as e:
        log.error(f"Erro ao alterar destaque: {e}")
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
        log.error(f"Erro no upload: {e}")
        return jsonify({'erro': 'Erro ao fazer upload'}), 500

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
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id=%s",
            [nid]
        )
        ordem = cur.fetchone()['coalesce']
        
        cur.execute(
            "INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s,%s,%s)",
            [nid, url, ordem]
        )
        conn.commit()
        
        cur.execute(
            "SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem",
            [nid]
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({'url': url, 'galeria': [dict(r) for r in rows]}), 201
    except Exception as e:
        log.error(f"Erro ao adicionar à galeria: {e}")
        return jsonify({'erro': 'Erro ao adicionar à galeria'}), 500

@app.route('/api/admin/noticias/<nid>/galeria', methods=['GET'])
@login_required
def admin_galeria_get(nid):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem",
            [nid]
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log.error(f"Erro ao listar galeria: {e}")
        return jsonify({'erro': 'Erro ao listar galeria'}), 500

@app.route('/api/admin/galeria/<int:gid>', methods=['DELETE'])
@login_required
def admin_galeria_delete(gid):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM galeria WHERE id=%s", [gid])
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro ao remover da galeria: {e}")
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
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT COALESCE(MAX(ordem),0)+1 FROM galeria WHERE noticia_id=%s",
            [nid]
        )
        ordem = cur.fetchone()['coalesce']
        
        cur.execute(
            "INSERT INTO galeria (noticia_id, imagem, ordem) VALUES (%s,%s,%s)",
            [nid, url, ordem]
        )
        conn.commit()
        
        cur.execute(
            "SELECT * FROM galeria WHERE noticia_id=%s ORDER BY ordem",
            [nid]
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({'galeria': [dict(r) for r in rows]}), 201
    except Exception as e:
        log.error(f"Erro ao adicionar URL à galeria: {e}")
        return jsonify({'erro': 'Erro ao adicionar URL à galeria'}), 500

@app.route('/api/admin/categorias', methods=['GET'])
@login_required
def admin_cats():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT nome FROM categorias ORDER BY nome")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([r['nome'] for r in rows])
    except Exception as e:
        log.error(f"Erro ao listar categorias admin: {e}")
        return jsonify({'erro': 'Erro ao listar categorias'}), 500

@app.route('/api/admin/categorias', methods=['POST'])
@login_required
def admin_criar_cat():
    try:
        data = request.get_json() or {}
        nome = data.get('nome', '').strip()
        
        if not nome:
            return jsonify({'erro': 'Nome obrigatório'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        try:
            cur.execute("INSERT INTO categorias (nome) VALUES (%s)", [nome])
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'erro': 'Categoria já existe'}), 409
        
        cur.close()
        conn.close()
        return jsonify({'ok': True, 'nome': nome}), 201
    except Exception as e:
        log.error(f"Erro ao criar categoria: {e}")
        return jsonify({'erro': 'Erro ao criar categoria'}), 500

@app.route('/api/admin/categorias/<nome>', methods=['DELETE'])
@login_required
def admin_apagar_cat(nome):
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM noticias WHERE categoria=%s", [nome])
        em_uso = cur.fetchone()['count']
        
        if em_uso:
            cur.close()
            conn.close()
            return jsonify({'erro': f'Em uso por {em_uso} notícia(s)'}), 409
        
        cur.execute("DELETE FROM categorias WHERE nome=%s", [nome])
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"Erro ao apagar categoria: {e}")
        return jsonify({'erro': 'Erro ao apagar categoria'}), 500

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM noticias")
        total = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM noticias WHERE destaque=TRUE")
        destaques = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM categorias")
        total_cats = cur.fetchone()['count']
        
        cur.execute("""
            SELECT categoria, COUNT(*) as n 
            FROM noticias 
            GROUP BY categoria 
            ORDER BY n DESC
        """)
        por_cat = cur.fetchall()
        
        cur.execute("""
            SELECT * FROM noticias 
            ORDER BY criado_em DESC 
            LIMIT 5
        """)
        recentes = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total': total,
            'destaques': destaques,
            'total_categorias': total_cats,
            'por_categoria': [dict(r) for r in por_cat],
            'recentes': [dict(r) for r in recentes],
        })
    except Exception as e:
        log.error(f"Erro ao buscar stats: {e}")
        return jsonify({'erro': 'Erro ao buscar estatísticas'}), 500

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.route('/health')
def health_check():
    """Endpoint para verificar o estado da aplicação."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({'status': 'ok', 'database': 'connected'})
    except Exception as e:
        log.error
