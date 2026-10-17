<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Integração Firebase e Firestore

O `jor-mcp` usa o Google Cloud para três coisas: **autenticar usuários** (Firebase Auth), **guardar o estado do OAuth** (Firestore) e **contar requisições para o Rate Limiting** (Firestore). As fontes de conteúdo (WordPress e GitHub) não passam pelo Google.

Por isso, o servidor precisa de um projeto Google Cloud com Firebase Auth e Firestore ativados **mesmo quando roda localmente**.

## 1. Inicialização (`src/server.py`)

Quando o servidor sobe, o *lifespan*:

-   chama `firebase_admin.initialize_app()` sem argumentos, usando as credenciais padrão do ambiente (a conta de serviço no Cloud Run; `gcloud auth application-default login` na máquina de desenvolvimento);
-   cria um único `FirestoreAsyncClient(database=FIRESTORE_DATABASE_ID)`, compartilhado pelo resto do código por meio de `get_firestore_client()`.

## 2. Firebase Auth: quem pode chamar as ferramentas (`src/middleware/auth.py`)

O `AuthMiddleware` intercepta **todas** as requisições ao endpoint MCP:

-   lê o cabeçalho `Authorization: Bearer <token>`;
-   valida o token com `auth.verify_id_token(...)`, aceitando até 60 segundos de diferença de relógio;
-   extrai o `uid` e a claim `tier` (`basic` ou `pro`) e repassa os dois ao Rate Limiter. Não há valor padrão: um token sem `tier` válido recebe **403**;
-   se o token faltar ou for inválido, responde **401** com `WWW-Authenticate: Bearer resource_metadata=...`. É esse cabeçalho que faz o Claude Desktop abrir o navegador para o login.

Só `/health`, `/.well-known/*` e `/api/oauth/*` ficam fora dessa verificação.

## 3. Proxy OAuth 2.1 (`src/api/oauth.py`)

Clientes MCP como o Claude Desktop falam OAuth, não Firebase. O servidor faz a ponte entre os dois:

| Etapa | Endpoint | Uso do Google |
|---|---|---|
| Descoberta | `GET /.well-known/oauth-*` | nenhum (só metadados) |
| Registro do cliente (DCR) | `POST /api/oauth/register` | grava na coleção **`oauth_clients`** |
| Consentimento | portal Next.js separado (`jor-mcp-site`) | login Google SSO pelo Firebase no navegador |
| Aprovação | `POST /api/oauth/approve` | valida o token Firebase do portal, consulta **`allowed_users`**, grava o `tier` do usuário como *custom claim* (`auth.set_custom_user_claims`) e grava o código e o desafio PKCE em **`oauth_codes`** (validade de 10 minutos) |
| Troca do código | `POST /api/oauth/token` | lê e **apaga** o código (impede reuso), confere o PKCE S256, cria um *custom token* com `auth.create_custom_token(uid)` e o troca por ID token e refresh token na **Identity Toolkit API** (`accounts:signInWithCustomToken`) |
| Renovação | `POST /api/oauth/token` (`refresh_token`) | **Secure Token API** (`securetoken.googleapis.com`) e nova consulta a **`allowed_users`**: um usuário sem autorização tem os refresh tokens revogados, e um `tier` alterado é regravado na claim |

A allow-list é a coleção `allowed_users`: o ID de cada documento é um e-mail em minúsculas, e o acesso só é liberado se `status == "active"` e `tier` for `basic` ou `pro`. Ela é mantida manualmente (por exemplo, no console do Firebase).

## 4. Firestore: Rate Limiting

Os dois contadores usam Fixed Window e `firestore.Increment(1)` atômico, o que permite que várias instâncias do Cloud Run compartilhem a mesma contagem.

-   **Por usuário** (`src/middleware/rate_limit.py`): coleção `rate_limits`, um documento por `{uid}_{AAAA-MM}`. Cota mensal de 500 requisições no tier `basic` e 2000 no `pro` (`RATE_LIMIT_BASIC_REQUESTS`, `RATE_LIMIT_PRO_REQUESTS`). Acima da cota, o servidor responde **429** com `Retry-After` até o início do mês seguinte.
-   **Por IP** (`src/middleware/ip_rate_limit.py`): coleção `ip_rate_limits`. Vale só para as rotas não autenticadas (`/api/oauth/*` e `/.well-known/*`) e impede que alguém encha o Firestore de registros DCR. O padrão é 60 requisições por minuto. Os documentos têm um campo `expires_at`, pensado para uma política de TTL do Firestore.

Os dois Rate Limiters fazem **fail open** se o Firestore der erro. Uma falha no banco não derruba o serviço, mas os limites deixam de valer enquanto ela durar.

## 5. Resumo das coleções

| Coleção | Conteúdo |
|---|---|
| `allowed_users` | allow-list de e-mails |
| `oauth_clients` | clientes MCP registrados |
| `oauth_codes` | códigos de autorização temporários com PKCE |
| `rate_limits` | contadores mensais por usuário |
| `ip_rate_limits` | contadores por IP, por minuto |

Os nomes das coleções podem ser alterados por variáveis de ambiente; veja [Configuração e Variáveis de Ambiente](../../2-replicacao/configuracao-e-env.md).

## 6. Notas de operação

-   **Native mode é obrigatório.** O código usa o cliente nativo do Firestore (`google.cloud.firestore_v1`), que não funciona com um banco em Datastore mode.
-   **Liberar acesso a um usuário:** crie um documento em `allowed_users` cujo ID seja o e-mail do usuário em minúsculas, com os campos `status: "active"` e `tier: "basic"` (ou `"pro"`). Sem `tier`, o `/approve` responde **403**.
-   **Mudar o tier:** altere `tier` em `allowed_users`. O servidor copia o valor para a *custom claim* do Firebase na próxima aprovação ou renovação do token.

## Decisão Arquitetural: Por que Estado Serverless?
Contamos com o Firestore em vez de um cache em memória ou uma instância Redis provisionada para manter a ausência de estado (statelessness) nos contêineres do Cloud Run. Isso permite escalonamento horizontal a zero, maximizando a eficiência de FinOps enquanto evita burlar o limite de taxa durante picos de tráfego.

## Funções IAM de Execução para o Firebase Admin SDK
O servidor faz mais do que validar ID tokens. O `src/api/oauth.py` também emite tokens customizados, busca usuários e revoga refresh tokens, e cada uma dessas chamadas tem seu próprio requisito de IAM na conta de serviço de execução do Cloud Run:

| Operação | Chamada | Função necessária |
| :--- | :--- | :--- |
| Validar um ID token | `auth.verify_id_token` | Nenhuma — os certificados públicos de assinatura são obtidos via HTTPS. |
| Emitir um token customizado | `auth.create_custom_token` | `roles/iam.serviceAccountTokenCreator`, vinculada na própria conta de execução: no Cloud Run o Admin SDK assina pela API IAM `signBlob`. |
| Buscar um usuário | `auth.get_user` | `roles/firebaseauth.admin` |
| Revogar refresh tokens | `auth.revoke_refresh_tokens` | `roles/firebaseauth.admin` |

Veja o [guia de implantação, seção 2](../../2-replicacao/guia-de-implantacao.md) para a lista completa de funções de execução.
