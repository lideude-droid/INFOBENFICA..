# Encarnado — Portal de Notícias do Benfica

Portal de notícias profissional dedicado exclusivamente ao Sport Lisboa e Benfica.
Todo o conteúdo é inserido e gerido manualmente pelo administrador.

---

## Estrutura de ficheiros

```
/index.html          → Página principal
/noticia.html        → Página de notícia individual
/favoritos.html      → Página de favoritos do utilizador
/404.html            → Página de erro 404
/sitemap.xml         → Sitemap para SEO
/robots.txt          → Diretivas para motores de pesquisa
/css/
  style.css          → Folha de estilos principal
/js/
  main.js            → Lógica do portal público
/data/
  noticias.json      → Base de dados de notícias (JSON)
/assets/
  images/            → Imagens do site
  icons/             → Ícones
/admin/
  index.html         → Painel de administração
  admin.css          → Estilos do painel
  admin.js           → Lógica do painel
```

---

## Acesso ao painel de administração

URL: `/admin/index.html`

Credenciais padrão:
- **Utilizador:** `admin`
- **Palavra-passe:** `encarnado2025`

> ⚠️ Altere as credenciais antes de colocar o site em produção.
> Edite as variáveis `ADMIN_USER` e `ADMIN_PASS` no ficheiro `/admin/admin.js`.

---

## Como publicar notícias

1. Aceda ao painel de administração em `/admin/`
2. Clique em **"Nova Notícia"**
3. Preencha todos os campos:
   - **Título** (obrigatório)
   - **Subtítulo** (resumo breve)
   - **Autor** (obrigatório)
   - **Data** (obrigatório)
   - **Categoria** (selecionar da lista)
   - **Imagem** (upload ou URL)
   - **Conteúdo** (editor de texto rico)
4. Opcionalmente, marque como **"Destaque"** para aparecer em primeiro plano na página inicial
5. Clique em **"Pré-visualizar"** para ver o resultado antes de publicar
6. Clique em **"Publicar notícia"** para tornar a notícia pública

---

## Sincronização do ficheiro JSON

O painel de administração guarda as notícias no `localStorage` do navegador.
Para que o site funcione em múltiplos dispositivos ou num servidor real:

1. No painel, clique em **"Exportar JSON"** (barra lateral)
2. Guarde o ficheiro `noticias.json` descarregado
3. Copie-o para a pasta `/data/` do servidor

---

## Modo escuro

O utilizador pode alternar entre modo claro e escuro clicando no botão "Escuro/Claro" no header.
A preferência é guardada automaticamente no navegador.

---

## Favoritos

Os utilizadores podem guardar notícias nos favoritos clicando no ícone ♡ em cada notícia.
Os favoritos são guardados localmente no navegador (localStorage).

---

## SEO

- Meta tags automáticas em cada página
- Open Graph para partilha em redes sociais
- Sitemap em `/sitemap.xml` (atualizar com o domínio real)
- Robots.txt com bloqueio do `/admin/`
- Substituir `https://seusite.pt` no sitemap.xml pelo domínio real

---

## Personalização

### Alterar credenciais de administrador
Editar em `/admin/admin.js`:
```js
const ADMIN_USER = 'admin';        // ← alterar
const ADMIN_PASS = 'encarnado2025'; // ← alterar
```

### Alterar nome/slogan do site
Editar em `/css/style.css` (variáveis CSS) e diretamente nos ficheiros HTML
onde aparece `Encarnado` e `O pulso do Benfica`.

### Adicionar categorias
No painel de administração → **Categorias** → Adicionar nova categoria.
Ou editar diretamente o array em `/data/noticias.json`:
```json
"categorias": ["Futebol", "Modalidades", "Mercado", "Formação", "Opinião"]
```

---

## Tecnologias utilizadas

- HTML5 semântico
- CSS3 com variáveis nativas (sem frameworks)
- JavaScript vanilla (sem dependências externas)
- Google Fonts (Playfair Display, Source Serif 4, DM Sans)
- Armazenamento: JSON + localStorage

---

## Compatibilidade

Testado e compatível com:
- Chrome / Edge (últimas versões)
- Firefox (últimas versões)
- Safari (iOS e macOS)
- Dispositivos móveis (responsivo)

---

*Site não oficial. Conteúdo inserido manualmente pela equipa editorial.*
