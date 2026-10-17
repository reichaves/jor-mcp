<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Conectar os Dados da Sua Redação

O `jor-mcp` não está preso ao conteúdo da Ambiental Media. Qualquer redação pode ter a própria instância e apontá-la para **o próprio site WordPress e os próprios repositórios no GitHub**. Este guia explica as formas de conexão, o que cada uma exige e o checklist de segurança a seguir.

---

## 1. Cenários de Conexão

| # | Cenário | Fonte dos dados | Quem pode usar | Custo e esforço |
|---|---|---|---|---|
| **A** | Usar a instância da Ambiental Media | Só o conteúdo da Ambiental Media | Usuários da allow-list da Ambiental Media | Nenhum |
| **B** | **Ter a própria instância em produção** | **O seu WordPress e o seu GitHub** | Usuários da sua allow-list | GCP com faturamento: Cloud Run, Load Balancer, um domínio e um portal de consentimento |
| **C** | Rodar localmente para testes | O seu WordPress e o seu GitHub | Só você | Grátis, uma máquina |

O cenário A não permite pesquisar o seu próprio conteúdo. Para isso, use o cenário B, e o cenário C para testar antes.

### 1.1 Cenário A: instância da Ambiental Media

Peça à Ambiental Media para incluir a sua conta Google na allow-list e siga [Conectando a LLMs](../1-tecnico/conectando-clientes.md#instância-da-ambiental-media).

### 1.2 Cenário B: a sua instância em produção

1.  **Projeto e serviços:** crie um projeto GCP, adicione o Firebase a ele e crie o banco do Firestore em **Native mode**. Ative as APIs `identitytoolkit`, `securetoken`, `firestore`, `run` e `artifactregistry`.
2.  **Autenticação:** ative o provedor de login do Google e desative E-mail/senha ([guia de implantação, seção 3](guia-de-implantacao.md#3-configuração-de-segurança-no-console-firebase-authentication)). Desative os cadastros novos só depois que cada usuário tiver entrado uma vez (veja o item 4 do checklist abaixo).
3.  **Allow-list:** crie `allowed_users/<email>` com `status: "active"` e `tier: "basic"` para cada usuário ([guia de implantação, seção 5](guia-de-implantacao.md#5-gerenciamento-manual-da-lista-branca-allowed_users)).
4.  **Conta de serviço de execução:** crie a `jor-mcp-runner` com as funções listadas no [guia de implantação, seção 2](guia-de-implantacao.md#2-permissões-de-conta-de-serviço-gcp-iam).
5.  **Token do GitHub:** crie um token fine-grained (item 7 do checklist) e guarde-o no Secret Manager como `MCP_GITHUB_TOKEN`.
6.  **Imagem e deploy:** gere a imagem, envie-a ao Artifact Registry e faça o deploy com o `service.yaml`, definindo todas as variáveis marcadas como obrigatórias para o cenário B na [seção 2](#2-variáveis-obrigatórias-por-cenário).
7.  **Portal de consentimento:** publique um portal de consentimento no GCS, atrás do mesmo Load Balancer ([configuração do Load Balancer](configuracao-load-balancer.md)). O portal da Ambiental Media é privado; use o [portal de referência](#5-portal-de-consentimento-de-referência).
8.  **Proteções do Firebase e do Firestore:** restrinja a API key, publique as regras do Firestore e configure as políticas de TTL (itens 5, 6 e 9 do checklist).
9.  **Conexão:** adicione `https://<seu-dominio>/mcp` como conector no seu cliente MCP ([seção 3](#3-clientes-mcp)).

### 1.3 Cenário C: testes locais

1.  Repita os passos 1 a 3 do cenário B num projeto de testes.
2.  Crie uma conta de serviço para uso local, por exemplo `jor-mcp-local@<project-id>.iam.gserviceaccount.com`, com `roles/datastore.user` e `roles/firebaseauth.admin`. Dê a ela `roles/iam.serviceAccountTokenCreator` sobre ela mesma, e dê à sua conta `roles/iam.serviceAccountTokenCreator` sobre ela.
3.  Use-a por impersonação, nunca com uma chave JSON baixada:

    ```bash
    gcloud auth application-default login \
      --impersonate-service-account=jor-mcp-local@<project-id>.iam.gserviceaccount.com
    ```

4.  Suba o servidor aceitando conexões só da própria máquina:

    ```bash
    uv run --env-file .env uvicorn src.server:app --host 127.0.0.1 --port 8080
    ```

5.  Sirva o [portal de referência](#52-rodar-localmente-cenário-c) em `http://localhost:3000`.
6.  Conecte pelo Claude Code:

    ```bash
    claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp
    ```

> [!NOTE]
> A configuração por impersonação dos passos 2 e 3 ainda não foi validada de ponta a ponta na troca de token (`create_custom_token`). Se o endpoint de token responder `403`, registre uma issue.

---

## 2. Variáveis Obrigatórias por Cenário

Vários valores padrão apontam para a Ambiental Media. Se você não os definir, a sua instância pesquisa o WordPress da Ambiental Media e manda os seus usuários para o portal de consentimento da Ambiental Media. Defina todas as variáveis marcadas como **obrigatórias** abaixo; o servidor registra um aviso na inicialização com o nome de cada uma que ainda aponte para `ambiental.media`. A referência completa está em [Configuração e Variáveis de Ambiente](configuracao-e-env.md).

| Variável | B (produção) | C (local) |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Definida pelo Cloud Run | **Obrigatória** |
| `FIREBASE_WEB_API_KEY` | **Obrigatória** | **Obrigatória** |
| `WORDPRESS_API_URL` | **Obrigatória** (o padrão é a Ambiental Media) | **Obrigatória** (o padrão é a Ambiental Media) |
| `MCP_GITHUB_REPOS` / `MCP_GITHUB_TOKEN` | Opcional | Opcional |
| `MCP_GITHUB_FILENAMES` | Opcional (padrão `pt.json,en.json`) | Opcional (padrão `pt.json,en.json`) |
| `OAUTH_SERVER_BASE_URL` | **Obrigatória**: `https://<seu-dominio>` | **Obrigatória**: `http://localhost:8080` |
| `OAUTH_PORTAL_BASE_URL` | **Obrigatória**: a URL do seu portal | **Obrigatória**: `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | **Obrigatória**: a origem do seu portal | O padrão já libera `http://localhost:3000` |
| `IP_RATE_LIMIT_TRUSTED_PROXIES` | `1` atrás do Load Balancer | `0` |
| `GCP_PROJECT_ID` | Opcional no Cloud Run | Opcional, necessária para correlacionar logs e traces |

---

## 3. Clientes MCP

| Cliente | Cenários | Observações |
|---|---|---|
| Claude Desktop e claude.ai (conector personalizado) | A e B | A conexão parte dos servidores da Anthropic, então a URL do servidor precisa ser HTTPS pública |
| Claude Code (`claude mcp add --transport http`) | A, B e C | Conecta a partir da sua máquina, com callback em loopback. É o caminho mais simples para o cenário C |
| MCP Inspector (`npx @modelcontextprotocol/inspector`) | A, B e C | Útil para depurar o fluxo OAuth e listar as ferramentas |
| Agentes próprios (MCP SDK) | A, B e C | Precisam implementar OAuth 2.1 com PKCE e Dynamic Client Registration (DCR) |

> [!NOTE]
> O servidor monta o endpoint MCP em `/mcp`. Materiais mais antigos citam `/mcp/sse`. Os dois respondem `401` sem token, então confirme o caminho com um cliente já autenticado na sua instância.

---

## 4. Limitações Conhecidas

-   **Portal de consentimento:** o portal de produção (`jor-mcp-site`) é um repositório privado. Para concluir o login na sua instância, você precisa de um portal que implemente a etapa de consentimento descrita em [Contratos da API](../1-tecnico/contratos-api.md). Use o [portal de referência](#5-portal-de-consentimento-de-referência) ou crie o seu.
-   **Formato dos arquivos do GitHub:** a fonte GitHub só lê arquivos JSON cujos nomes estejam em `MCP_GITHUB_FILENAMES` (padrão `pt.json` e `en.json`), em qualquer nível de cada repositório de `MCP_GITHUB_REPOS`, e pesquisa os valores de texto dentro deles. CSV, Markdown e outros formatos não são aceitos. Repositórios sem arquivos correspondentes não retornam resultados nem erro.
-   **WordPress:** a REST API do site (`/wp-json/wp/v2/posts`) precisa permitir leitura pública.

---

## 5. Portal de Consentimento de Referência

A pasta `portal/` traz uma página de consentimento mínima que implementa a etapa de consentimento dos [Contratos da API](../1-tecnico/contratos-api.md). Ela não tem etapa de build: HTML, CSS e JavaScript puros, com o Firebase SDK carregado do CDN do Google com hashes de integridade.

```text
portal/
├── authorize/
│   ├── index.html       # servido em /authorize, o endpoint anunciado pelo servidor
│   ├── authorize.js     # login com Google, POST /api/oauth/approve, redirecionamento
│   ├── consent.js       # validação do pedido e checagem do destino (sem DOM)
│   └── authorize.css
├── config.example.js    # copie para config.js (ignorado pelo git)
└── tests/               # node --test "portal/tests/*.test.js"
```

### 5.1 O que a página garante

-   Exige `client_id`, `code_challenge`, `code_challenge_method=S256` e um `redirect_uri` http(s); qualquer outra coisa mostra um erro.
-   Mostra o **domínio de destino** antes do login e um aviso quando ele não é um endereço local nem `claude.ai`.
-   Só segue o `redirect_uri` devolvido pelo `/approve`, e só se ele apontar para o domínio mostrado ao usuário. **Negar** nunca redireciona.
-   Escreve texto só com `textContent`, mantém a sessão do Firebase em memória (sem `localStorage`), declara uma Content Security Policy e uma política `no-referrer`, e se recusa a rodar dentro de um frame.

### 5.2 Rodar localmente (cenário C)

```bash
cp portal/config.example.js portal/config.js   # depois preencha a configuração web do Firebase
python3 -m http.server 3000 --bind 127.0.0.1 -d portal
```

Defina `OAUTH_PORTAL_BASE_URL=http://localhost:3000` no servidor. Rode os testes com `node --test "portal/tests/*.test.js"` (Node.js 22 ou posterior).

### 5.3 Publicar (cenário B)

1.  Crie o `portal/config.js` com a configuração web do seu Firebase e o `serverBaseUrl` igual ao seu `OAUTH_SERVER_BASE_URL`.
2.  Se o servidor não estiver na mesma origem do portal, acrescente a origem dele ao `connect-src` da Content Security Policy da página (`portal/authorize/index.html`).
3.  Envie o conteúdo de `portal/` (sem `tests/` e `package.json`) ao bucket do GCS atrás do seu Load Balancer, para que a página responda em `https://<seu-dominio>/authorize/`.
4.  Configure o backend bucket para enviar `Content-Security-Policy: frame-ancestors 'none'` como cabeçalho de resposta personalizado: essa proteção não pode ser declarada na própria página.
5.  Inclua o seu domínio em **Authentication > Settings > Authorized domains** no console do Firebase.

O portal de referência ainda não tem teste automatizado de ponta a ponta: o login com Google e a chamada ao `/approve` são conferidos à mão.

---

## 6. Checklist de Segurança para Quem Replica

Confira todos os itens antes de expor a sua instância.

-   [ ] **1. Use uma versão atual.** Use a `0.13.1` ou posterior: as versões anteriores não exigem uma claim `tier` válida em todo token.
-   [ ] **2. Rode localmente em `127.0.0.1`.** Nunca rode o servidor com `--host 0.0.0.0` na sua máquina; esse valor fica só no `Dockerfile`.
-   [ ] **3. Revogue usuários por completo.** Quando alguém sair, siga a [revogação em três passos](guia-de-implantacao.md#52-revogando-um-usuário) em vez de só editar `allowed_users`. O `scripts/revoke_user.py` executa os três passos.
-   [ ] **4. Desative os cadastros novos e mantenha só o Google como provedor.** Desativar os cadastros também bloqueia o primeiro login com Google de usuários da allow-list que nunca entraram. Por isso, desative depois do primeiro login de cada usuário e reative por um momento ao incluir alguém novo ([guia de implantação, seção 3.1](guia-de-implantacao.md#31-desativação-de-auto-cadastro)).
-   [ ] **5. Restrinja a API key do Firebase** aos domínios do seu portal (HTTP referrers) e só às APIs `identitytoolkit` e `securetoken`.
-   [ ] **6. Publique regras do Firestore que neguem todo acesso de clientes:** publique o `firestore.rules` do repositório ([guia de implantação, seção 4](guia-de-implantacao.md#4-compreendendo-o-caráter-não-secreto-das-chaves-do-firebase)). O servidor usa o Admin SDK, que não é afetado por essas regras.
-   [ ] **7. Use o mínimo de permissões.** Uma conta de serviço de execução dedicada (`jor-mcp-runner`), impersonação em vez de chaves JSON nas máquinas de desenvolvimento, e um token fine-grained do GitHub só com `Contents: read`, limitado aos repositórios de `MCP_GITHUB_REPOS`, com validade de até 90 dias.
-   [ ] **8. Indexe só o que todos os usuários podem ler.** Todo usuário da allow-list, e o provedor de IA por trás do cliente dele, consegue ler tudo nos repositórios configurados. Registre essa decisão.
-   [ ] **9. Configure TTL e HTTPS.** Políticas de TTL do Firestore em `oauth_codes.expires_at` e `ip_rate_limits.expires_at`, e HTTPS em toda URL pública.
-   [ ] **10. Faça deploy sem chaves de longa duração.** Prefira [Workload Identity Federation](guia-de-implantacao.md#83-autenticação-sem-chave-com-workload-identity-federation) ao segredo `GCP_SA_KEY` no GitHub Actions.
