# Encarnado — Portal de Notícias do Benfica
### Backend Flask + Base de dados SQLite

Portal de notícias profissional com backend real. Todas as notícias são guardadas
numa base de dados SQLite e são **iguais para todos os utilizadores** que acederem
ao site, em qualquer dispositivo ou browser.

---

## Estrutura do projeto

```
encarnado/
├── server.py              ← Servidor Flask (API + rotas)
├── requirements.txt       ← Dependências Python
├── start.sh               ← Arrancar no Linux/Mac
├── start.bat              ← Arrancar no Windows
├── data/
│   └── encarnado.db       ← Base de dados SQLite (criada automaticamente)
└── public/
    ├── index.html         ← Página inicial
    ├── noticia.html       ← Página de notícia
    ├── favoritos.html     ← Favoritos
    ├── admin.html         ← Painel de administração
    ├── 404.html           ← Página de erro
    ├── css/
    │   ├── style.css      ← Estilos do portal
    │   └── admin.css      ← Estilos do painel
    ├── js/
    │   ├── main.js        ← JavaScript do portal
    │   └── admin.js       ← JavaScript do painel
    └── assets/
        └── images/        ← Imagens carregadas via upload
```

---

## Instalação e arranque

### Requisitos
- **Python 3.8+** instalado

### Linux / macOS
```bash
chmod +x start.sh
./start.sh
```

### Windows
```
Fazer duplo clique em start.bat
```

### Manual
```bash
pip install -r requirements.txt
python server.py
```

O servidor inicia em `http://localhost:5000`

---

## Acesso

| URL                              | Descrição              |
|----------------------------------|------------------------|
| `http://localhost:5000`          | Portal público         |
| `http://localhost:5000/admin`    | Painel de administração|

**Credenciais padrão:**
- Utilizador: `admin`
- Palavra-passe: `encarnado2025`

---

## Alterar credenciais de administrador

No ficheiro `server.py`, altere as linhas:
```python
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'encarnado2025')
```

Ou use variáveis de ambiente:
```bash
export ADMIN_USER=meuadmin
export ADMIN_PASS=minhapassword
python server.py
```

---

## API REST disponível

| Método | Endpoint                            | Descrição                  |
|--------|-------------------------------------|----------------------------|
| GET    | `/api/noticias`                     | Listar notícias             |
| GET    | `/api/noticias/:id`                 | Obter notícia               |
| GET    | `/api/noticias/destaque`            | Notícia em destaque         |
| GET    | `/api/noticias/recentes`            | Notícias recentes           |
| GET    | `/api/noticias/mais-lidas`          | Mais lidas                  |
| POST   | `/api/noticias/:id/leitura`         | Registar leitura            |
| GET    | `/api/categorias`                   | Listar categorias           |
| POST   | `/api/auth/login`                   | Login admin                 |
| POST   | `/api/auth/logout`                  | Logout                      |
| GET    | `/api/auth/verificar`               | Verificar sessão            |
| GET    | `/api/admin/noticias`               | Listar (admin)              |
| POST   | `/api/admin/noticias`               | Criar notícia               |
| PUT    | `/api/admin/noticias/:id`           | Editar notícia              |
| DELETE | `/api/admin/noticias/:id`           | Apagar notícia              |
| POST   | `/api/admin/noticias/:id/destaque`  | Toggle destaque             |
| POST   | `/api/admin/upload`                 | Upload de imagem            |
| GET    | `/api/admin/categorias`             | Listar categorias (admin)   |
| POST   | `/api/admin/categorias`             | Criar categoria             |
| DELETE | `/api/admin/categorias/:nome`       | Apagar categoria            |
| GET    | `/api/admin/stats`                  | Estatísticas                |

---

## Deploy em produção

### Com Gunicorn (recomendado)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 server:app
```

### Variáveis de ambiente para produção
```bash
export SECRET_KEY=chave_secreta_muito_longa_e_aleatoria
export ADMIN_USER=admin
export ADMIN_PASS=password_forte
export PORT=5000
export DEBUG=false
python server.py
```

### Com Nginx (proxy reverso)
```nginx
server {
    listen 80;
    server_name seusite.pt;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /assets/images/ {
        alias /caminho/para/encarnado/public/assets/images/;
        expires 30d;
    }
}
```

---

## Base de dados

A base de dados SQLite é criada automaticamente em `data/encarnado.db` no primeiro arranque.

**Tabelas:**
- `noticias` — todas as notícias
- `categorias` — categorias disponíveis
- `galeria` — imagens de galeria por notícia
- `config` — configurações gerais

Para fazer backup, basta copiar o ficheiro `data/encarnado.db`.

---

## Tecnologias

- **Backend:** Python 3 + Flask + SQLite3
- **Frontend:** HTML5 + CSS3 + JavaScript vanilla
- **Base de dados:** SQLite (sem instalação adicional)
- **Tipografia:** Playfair Display, Source Serif 4, DM Sans

---

*Site não oficial. Conteúdo inserido manualmente pela equipa editorial.*
