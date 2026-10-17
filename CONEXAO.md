# CONEXAO.md: como usar o jor-mcp com os dados de outra redação

## Resumo para não especialistas

O jor-mcp é um programa que deixa assistentes de inteligência artificial, como o Claude, pesquisarem no acervo de uma redação: as matérias publicadas no site e os arquivos de dados guardados no GitHub. Ele foi criado pela Ambiental Media e é de código aberto, então qualquer veículo pode instalar uma cópia e ligá-la ao próprio conteúdo. Este documento é um plano para deixar isso claro, porque hoje quem chega ao projeto entende que ele só funciona com os dados da Ambiental.

Essa impressão tem motivos concretos. O endereço da Ambiental aparece fixo nas instruções, e várias configurações apontam para o site dela quando ninguém as altera. Com isso, uma instalação nova pode acabar buscando as matérias da Ambiental sem que ninguém perceba. A página de login fica num repositório privado, e sem ela uma outra redação não consegue terminar a instalação. A busca no GitHub só entende arquivos num formato específico, usado nos sites da Ambiental. E o arquivo que publica o programa na nuvem traz configurações que pertencem à conta da Ambiental.

O plano descreve três formas de uso. Na primeira, a pessoa usa o serviço da Ambiental e só tem acesso ao conteúdo dela. Na segunda, que é o objetivo principal, a redação tem a sua cópia na nuvem do Google, ligada ao próprio site e aos próprios arquivos, e decide quem da equipe pode entrar. Na terceira, o programa roda num computador apenas para testes. As melhorias propostas são:
- guias novos, em português e inglês, com o passo a passo de cada forma de uso;
- um aviso automático quando alguma configuração ainda aponta para a Ambiental;
- liberdade para escolher quais arquivos do GitHub entram na busca;
- um arquivo de publicação na nuvem sem dados da Ambiental;
- uma página de login simples que qualquer redação possa usar;
- uma ferramenta para tirar de uma vez o acesso de quem sai da equipe.

A revisão de segurança encontrou riscos. O mais grave: na versão instalada neste computador, que está desatualizada, qualquer pessoa com uma conta Google poderia entrar, mesmo fora da lista de autorizados. Além disso, o programa estava aberto para qualquer aparelho conectado ao mesmo Wi-Fi. Também foram encontrados riscos menores:
- dois riscos que também afetam o serviço da Ambiental, descritos aqui só de forma resumida até ela corrigi-los;
- a publicação automática na nuvem usa uma senha de longa duração guardada no GitHub;
- o programa roda com mais permissões do que precisa;
- conteúdo privado dos repositórios pode ser visto por todos os autorizados e pelo serviço de inteligência artificial.

Para cada risco, o plano propõe uma regra de proteção. O primeiro passo é atualizar para a versão mais nova da Ambiental, que já corrige o problema mais grave, e deixar o programa acessível só no próprio computador. Esse passo foi feito em 2026-10-17; faltam dois ajustes no painel do Firebase, descritos na Fase 0. Algumas falhas também afetam o serviço da Ambiental, e o plano recomenda avisá-la em particular antes de divulgá-las. Todo o trabalho foi dividido em etapas: cada uma tem testes para confirmar que funcionou, um jeito de desfazer o que foi feito e só começa com autorização.

---

> **Situação:** plano revisado, versão 4, de 2026-10-17.
> Fase 0 executada em 2026-10-17; os passos 2 e 6 foram feitos pelo usuário. Fases 1 a 4 executadas em 2026-10-17. PRs no fork: #8 (sincronização), #9 (este plano), #10, #11, #12 e #13 (Fases 1 a 4, empilhados nessa ordem). Veja o resultado de cada uma na própria fase. As outras fases continuam aguardando aprovação, uma de cada vez.
>
> **Mudanças da versão 4:** o original chegou à 0.13.1, que inclui a conta de serviço dedicada do #70 (§2.1, A3, S12, R7, R18); S1 e S2 fechados; S3 e S4 resumidos nesta versão pública (§3.1).
>
> Como os itens foram verificados:
> - **[código]:** pela leitura do código local ou do original.
> - **[API]:** consultando o projeto `jor-mcp-m78bp5-8e56c` pela API, só para leitura.
> - **[inferido]:** a confirmar na fase indicada.

---

## 1. Contexto

O jor-mcp se apresenta como fácil de replicar ("Easily Forkable"), mas quem chega ao repositório entende que ele serve só aos dados da Ambiental Media. Os motivos:

1. **Guia de conexão.** `docs/pt-br/1-tecnico/conectando-clientes.md` traz o endereço fixo `https://jormcp.ambiental.media/mcp/sse` e diz que a conta é "cadastrada pela Ambiental Media".
2. **Valores padrão.** Em `src/config.py`, o WordPress, o domínio OAuth e o CORS apontam para `ambiental.media`.
3. **Portal de login privado.** O `jor-mcp-site` é privado, então quem replica não consegue completar o login. A documentação não avisa.
4. **Deploy preso à Ambiental.** O `service.yaml` usa a conta de serviço da Ambiental e não define as URLs de OAuth.

**Objetivo:** deixar claro, com documentação e mudanças pequenas e testadas, que qualquer redação pode apontar o jor-mcp para o **próprio WordPress e os próprios repositórios no GitHub**. Também deixar claro **de quais formas se conectar** e **quais regras de segurança seguir**.

**Fora do escopo:**
- reescrever o portal Next.js (`jor-mcp-site`);
- novas fontes de dados além de WordPress e GitHub;
- Terraform/IaC, que já consta no roadmap da Ambiental;
- mudar o comportamento da produção da Ambiental.

---

## 2. Diagnóstico

### 2.1 Este computador comparado ao repositório original

| | Local (`reichaves/jor-mcp`) | Original (`ambiental-media/jor-mcp`) |
|---|---|---|
| Versão | 0.10.0 em `main`; **0.13.1** na branch `chore/sync-upstream-0.13.1` (commit `1d33164`, ainda sem merge em `main`) | **0.13.1** (publicada em 2026-10-12) |
| Commits após `5a2e8ce` (0.10.0) | 7 commits seus: docs (#1 a #7), rastros de sessão e urllib3 2.8.0 | 9 commits: papéis e limites de uso (#72), nova checagem da lista a cada renovação do token (#73), logs em JSON e OTel opcional (#76), 1Gi no Cloud Run (#77), **conta de serviço dedicada `jor-mcp-runner` (#70)** e os commits de versão |
| Relação | Fork no GitHub de `ambiental-media/jor-mcp`, sem remote `upstream` configurado localmente. Na Fase 0, o original foi buscado pela URL (`git fetch https://github.com/ambiental-media/jor-mcp.git main`), sem adicionar remote | — |
| Ambiente | Antes: servidor em `*:8080`, 287 testes. Depois da Fase 0: `127.0.0.1:8080` com o projeto `jor-mcp-m78bp5-8e56c`, 331 testes passando, cobertura de 100% | Produção em `jormcp.ambiental.media` |

**Arquivos alterados nos dois lados**, onde a atualização deve ter conflitos [código]:
- `pyproject.toml` e `uv.lock`: os dois mudaram versão e dependências;
- `service.yaml`;
- `docs/{pt-br,en}/2-replicacao|2-replication/configuracao-e-env|configuration-and-env.md`;
- `docs/{pt-br,en}/2-replicacao|2-replication/guia-de-implantacao|deployment-guide.md`.

**Mudanças da 0.13.x que afetam a replicação** [código]:
- **`allowed_users` agora exige `tier`** com valor `basic` ou `pro` (`TIER_QUOTAS` em `src/config.py`). Sem esse campo, o `/approve` responde `403`. Hoje o guia de implantação local (§5.1) diz que o `tier` é "Opcional", o que fica errado depois da atualização.
- O `/approve` grava o `tier` no cadastro do usuário no Firebase (`auth.set_custom_user_claims`), o que **exige a permissão `Firebase Authentication Admin`**.
- O `AuthMiddleware` recusa com `403` qualquer token sem `tier` válido.
- A renovação do token (`refresh_token`) consulta a lista de novo.
- Variáveis novas: `OTEL_TRACES_EXPORTER` (padrão `none`), `LOG_LEVEL` e `K_SERVICE`.
- **#70 (0.13.1):** o `service.yaml` passa a usar `jor-mcp-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com`, e o `cd.yml` exige e substitui `GCP_PROJECT_ID`. O guia de implantação §2 lista as permissões da conta: `datastore.user`, `secretmanager.secretAccessor`, `cloudtrace.agent`, `logging.logWriter`, `monitoring.metricWriter`, `firebaseauth.admin` e, só sobre a própria conta, `iam.serviceAccountTokenCreator` (para o `create_custom_token`).

### 2.2 O que já é genérico e o que depende da Ambiental

**Genérico** [código]:

| Peça | Como funciona |
|---|---|
| WordPress | Usa a API REST padrão (`/wp/v2/posts`, `src/services/wordpress.py:287,378`). Funciona com qualquer WordPress cuja API esteja pública |
| `get_full_article` | Aceita ID, slug ou URL de qualquer domínio: usa só o último trecho do caminho (`_extract_slug`, `wordpress.py:196`) |
| GitHub | Aceita qualquer `owner/repo` em `MCP_GITHUB_REPOS`, e `MCP_GITHUB_API_BASE_URL` permite usar um GitHub Enterprise |
| Descrições das ferramentas | `src/tools.py` fala em "a organização" e não cita a Ambiental |
| Projeto Firebase/Firestore | Vem das credenciais (`GOOGLE_CLOUD_PROJECT`) |

**Depende da Ambiental:**

| # | O quê | Onde | Efeito para quem replica |
|---|---|---|---|
| A1 | Valores padrão `ambiental.media` | `src/config.py:57,73,82,139` | Se você esquecer uma variável, o servidor busca o WordPress da Ambiental e **manda os usuários para o portal de login da Ambiental** |
| A2 | `service.yaml` não define `OAUTH_SERVER_BASE_URL`, `OAUTH_PORTAL_BASE_URL` e `CORS_ALLOWED_ORIGINS` | `service.yaml` | Um deploy feito do jeito que está anuncia o domínio da Ambiental, e o login quebra |
| A3 | ~~`serviceAccountName: 959918358302-compute@...` fixo~~ **Resolvido na 0.13.1 (#70)** | `service.yaml` | Antes apontava para a conta padrão do Compute da Ambiental (perfil Editor). Agora usa `jor-mcp-runner` no projeto de quem faz o deploy |
| A4 | O GitHub só lê `pt.json` e `en.json` | `src/services/github.py:31` (`_I18N_FILENAMES`) | Repositórios com outro formato retornam vazio, sem erro |
| A5 | Portal privado | `jor-mcp-site` (o GitHub responde 404) | **É impossível completar o login sem ele** |
| A6 | Guia de conexão com o endereço da Ambiental | `docs/*/conectando-clientes.md` / `connecting-clients.md` | Leva a crer que existe uma única instância |
| A7 | Textos que dizem "curada pela Ambiental Media" | `src/config.py:104`, `src/api/oauth.py:192`, `contratos-api.md` | Reforça a mesma impressão |
| A8 | `GCP_PROJECT_NUMBER` de exemplo é o da Ambiental (`959918358302`) | `guia-de-implantacao.md` §8.1 | Gera confusão |

### 2.3 Revisão da resposta anterior sobre o portal

| Afirmação | Avaliação |
|---|---|
| "O portal não guarda dados" | **Confirmada** [código]: `contratos-api.md` §4.2 e `src/api/oauth.py:290`. O portal só envia o token do Firebase e os parâmetros do PKCE |
| "O Firebase é configurado por variáveis (`NEXT_PUBLIC_FIREBASE_API_KEY`)" | **Provável** [inferido]: o código é privado |
| "Dá para fazer uma página HTML simples" | **Confirmada** [código]: o contrato tem três passos, e o CORS padrão já libera `http://localhost:3000` (`config.py:57`) |
| "`create_custom_token` deve falhar com as credenciais pessoais" | **Confirmada na Fase 4.** Com credenciais impersonadas também falha (`key_id`); a correção é `FIREBASE_SERVICE_ACCOUNT_ID` |
| Faltava dizer | Na 0.13.x, o `set_custom_user_claims` também exige `Firebase Authentication Admin`. A tabela de IAM do original (`firebase-and-firestore.md`) não lista essa chamada, mas a permissão já está incluída por causa do `get_user` |

---

## 3. Segurança

### 3.1 Achados

| # | Risco | Evidência | Gravidade |
|---|---|---|---|
| **S1** | **A lista de autorizados pode ser contornada na 0.10.0.** O `AuthMiddleware` (`src/middleware/auth.py`) só chama `verify_id_token`. Se o `tier` não vier, assume `basic`. Qualquer conta Google pode entrar direto no Firebase (`signInWithIdp`) usando a apiKey, que é pública, e chamar o `/mcp` sem passar pelo `/approve`. A 0.13.0 corrige: o token precisa trazer o `tier`, que só o `/approve` grava | [código] + [API]: `client.permissions: {}`, ou seja, cadastro aberto. **Não fiz o ataque** | ~~Alta~~ **Fechado na Fase 0**: na 0.13.1, `src/middleware/auth.py:89` responde `403` a token sem `tier` válido [código] |
| **S2** | **O servidor local aceita conexões de toda a rede** (`*:8080`). O README recomenda `--host 0.0.0.0` | [API]: `lsof` | ~~Alta~~ **Fechado na Fase 0**: `127.0.0.1:8080`, conexão pelo IP da rede recusada [API] |
| **S3** | **Risco na revogação de acesso:** remover alguém de `allowed_users` pode não encerrar o acesso tão rápido quanto o guia do original indica. Detalhes comunicados em privado à Ambiental; serão publicados depois da correção | [código]. **Não testado** | Média |
| **S4** | **Risco no cadastro de clientes OAuth** (`/api/oauth/register`), que pode ser usado contra usuários autorizados. Detalhes comunicados em privado à Ambiental; serão publicados depois da correção | [código] | Média |
| **S5** | **Portal de referência mal feito:** XSS e redirecionamento aberto. O roadmap cita que essas falhas foram corrigidas no `jor-mcp-site` | [inferido] | Média |
| **S6** | **apiKey sem restrições** (a API de chaves nem está ativada) | [API] | Baixa |
| **S7** | **Regras do Firestore nunca publicadas.** Hoje o acesso pelo navegador é negado (testei: `403`), mas por omissão | [API] | Baixa |
| **S8** | **Cadastro aberto e provedores extras:** e-mail/senha e anônimo não estão ativos agora, mas nada impede que alguém ative | [API] | Baixa |
| **S9** | **Exposição de dados de terceiros.** Repositórios privados ficam visíveis para todos os autorizados e passam pelo provedor de IA. O token do GitHub pode ter permissões demais | [inferido] | Depende da redação |
| **S10** | **Prompt injection indireto** pelo texto das matérias e dos JSONs | [inferido] | Baixa: só leitura |
| **S11** | **O deploy automático usa uma chave JSON** (`GCP_SA_KEY`, guia §8.1), uma credencial de longa duração guardada no GitHub | [código] | Média |
| **S12** | **O Cloud Run usa a conta de serviço padrão do Compute** (A3), com perfil Editor no projeto | [código] | ~~Média~~ **Resolvido na 0.13.1 (#70)** para quem segue o guia §2 |
| **S13** | **Túnel para testar o Claude Desktop** (cenário C) publica o servidor local | [inferido] | Média enquanto o S1 existir |

### 3.2 Regras de segurança

| Regra | O que fazer | Fecha | Fase |
|---|---|---|---|
| **R1** | Atualizar para a 0.13.1 ou superior antes de expor o servidor de qualquer forma. **Feito na Fase 0** | S1 | 0 |
| **R2** | Usar `--host 127.0.0.1` em toda execução local, inclusive nos exemplos do README e dos guias. O `0.0.0.0` fica só no `Dockerfile` | S2 | 0 e 1 |
| **R3** | Revogar um usuário em três passos: (a) `status: "disabled"` em `allowed_users`, (b) `set_custom_user_claims(uid, None)`, (c) `revoke_refresh_tokens(uid)`. Automatizar com `scripts/revoke_user.py` | S3 | 2 |
| **R4** | Desativar cadastros novos (*User actions → Enable create*) e manter **só o Google** como provedor. Isso já está no guia §3; falta incluir no checklist e aplicar no seu projeto. **Cuidado com a ordem:** com o cadastro desativado, o Firebase recusa a criação da conta no primeiro login com Google, inclusive de quem está em `allowed_users`. Desativar só depois que cada usuário tiver entrado uma vez, e reativar por um momento a cada pessoa nova da equipe | S1 e S8 | 0, 1 e 4 |
| **R5** | Restringir a apiKey: domínios (referrers) do portal e somente as APIs `identitytoolkit` e `securetoken` | S6 | 1 |
| **R6** | Publicar `firestore.rules` com `allow read, write: if false;`. O backend usa o Admin SDK, que não é afetado por essas regras | S7 | 1 e 2 |
| **R7** | Conta de serviço própria, com o mínimo de permissões. Na produção, seguir o guia §2 da 0.13.1 (`jor-mcp-runner`, #70). Localmente, usar `roles/datastore.user` e `roles/firebaseauth.admin` com **impersonação**, nunca uma chave JSON baixada | S12 | 1 e 4 |
| **R8** | Token do GitHub fine-grained, só `Contents: read`, limitado aos repositórios de `MCP_GITHUB_REPOS`, com validade de até 90 dias | S9 | 1 |
| **R9** | Governança: só indexar o que todos os autorizados e o provedor de IA podem ler, e registrar essa decisão | S9 | 1 |
| **R10** | TTL do Firestore em `oauth_codes.expires_at` e `ip_rate_limits.expires_at`, e HTTPS obrigatório na produção | — | 1 |
| **R11** | Túnel só temporário, com a 0.13.1 já aplicada, e desligado ao final do teste | S13 | 4 |
| **R12** | Portal: redirecionar **somente** para o `redirect_uri` da resposta do `/approve`, nunca para o parâmetro da URL | S5 | 3 |
| **R13** | Portal: nada de `innerHTML`, só `textContent`. CSP via `<meta>` com `default-src 'self'`, mais `apis.google.com`, `*.firebaseapp.com`, `identitytoolkit.googleapis.com`, `securetoken.googleapis.com` e o CDN. SRI nos scripts do CDN | S5 | 3 |
| **R14** | Portal: mostrar o **domínio de destino** (host do `redirect_uri`) e o `client_name`. Exibir um alerta quando o destino não for loopback nem o callback conhecido do Claude | S4 | 3 |
| **R15** | Portal: `config.js` fora do git e nenhum token no `localStorage` | — | 3 |
| **R16** | Código, opcional: `OAUTH_ALLOWED_REDIRECT_HOSTS` no `/register`, com padrão `localhost` e `claude.ai`. Ajustável por instância | S4 | 2 |
| **R17** | Deploy automático sem chave: **Workload Identity Federation** (`google-github-actions/auth` com `workload_identity_provider`) no lugar de `GCP_SA_KEY` | S11 | 1, só documentação |
| **R18** | `service.yaml` com variáveis no lugar de valores fixos: `${OAUTH_SERVER_BASE_URL}`, `${OAUTH_PORTAL_BASE_URL}` e `${CORS_ALLOWED_ORIGINS}`, incluídas na lista do `envsubst` do `cd.yml`. A conta de serviço já foi parametrizada no #70 | A2 | 2 |

---

## 4. Formas de conexão

### 4.1 Cenários

| # | Cenário | De onde vêm os dados | Quem pode usar | Custo e esforço |
|---|---|---|---|---|
| **A** | Usar a instância da Ambiental | Somente a Ambiental | Quem está na lista da Ambiental | Nenhum |
| **B** | **Ter a própria instância em produção** | **WordPress e GitHub da sua redação** | Os usuários da sua lista | GCP com faturamento: Cloud Run, Load Balancer, domínio e portal |
| **C** | Rodar localmente para testes | Os seus dados | Só você | Grátis, uma máquina |

**Cenário A:** Claude Desktop → Customize → Connectors → Add custom connector, com o endereço da Ambiental. Os passos estão em `conectando-clientes.md`.

**Cenário B**, passo a passo para o guia novo:
1. **Projeto e serviços:** criar o projeto GCP, ativar o Firebase e criar o Firestore em modo **Native**. Ativar `identitytoolkit`, `securetoken`, `firestore`, `run` e `artifactregistry`.
2. **Autenticação:** ativar o login pelo Google e desativar e-mail/senha. Desativar cadastros novos (R4) só depois do primeiro login de cada usuário (passo 9).
3. **Lista de autorizados:** criar `allowed_users/<email>` com `status: "active"` e `tier: "basic"`.
4. **Conta de serviço** `jor-mcp-runner` com o mínimo de permissões, conforme o guia §2 da 0.13.1 (R7).
5. **Token do GitHub** fine-grained (R8), guardado no Secret Manager.
6. **Imagem e deploy:** gerar a imagem, publicar no Artifact Registry e fazer o deploy com o `service.yaml` parametrizado (R18) e todas as variáveis (§4.3).
7. **Portal:** publicar o portal (`jor-mcp-site` ou o de referência da Fase 3) no GCS, atrás do mesmo Load Balancer (`configuracao-load-balancer.md`).
8. **Proteções do Firebase e do Firestore:** restringir a apiKey (R5), publicar as regras do Firestore (R6) e configurar o TTL (R10).
9. **Conexão:** conectar o Claude com `https://<seu-dominio>/mcp`.

**Cenário C**, passo a passo para o guia novo:
1. Repetir os passos 1 a 3 do cenário B. Já feito no projeto `jor-mcp-m78bp5-8e56c`, menos o `tier` e os cadastros novos.
2. Criar a conta de serviço `jor-mcp-local@<projeto>.iam.gserviceaccount.com` com `roles/datastore.user` e `roles/firebaseauth.admin`. Dar à sua conta o papel `roles/iam.serviceAccountTokenCreator` sobre ela.
3. Rodar `gcloud auth application-default login --impersonate-service-account=jor-mcp-local@...`.
4. Subir o servidor: `uv run --env-file .env uvicorn src.server:app --host 127.0.0.1 --port 8080`.
5. Subir o portal: `python -m http.server 3000 --bind 127.0.0.1 -d portal`.
6. Conectar com `claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp`.

### 4.2 Clientes

| Cliente | Funciona com | Observação |
|---|---|---|
| Claude Desktop e claude.ai (conector personalizado) | A e B | A conexão parte dos servidores da Anthropic, então o endereço precisa ser HTTPS público. O callback provável é `https://claude.ai/api/mcp/auth_callback` [inferido]. Precisa estar na lista do R16 |
| Claude Code (`claude mcp add --transport http`) | A, B e C | Conecta da sua máquina, com callback em loopback (`http://localhost:<porta>/callback`). É o caminho mais simples para o cenário C |
| MCP Inspector (`npx @modelcontextprotocol/inspector`) | A, B e C | Bom para depurar o OAuth e listar as ferramentas |
| Agentes próprios (SDK MCP) | A, B e C | Precisam implementar OAuth 2.1 com PKCE e cadastro dinâmico de cliente (DCR) |

**Endereço do MCP:** o código monta o `http_app()` do FastMCP 3 em `/`, o que dá `/mcp` [código]. A documentação de conexão diz `/mcp/sse`. Os dois respondem `401` sem token, porque o `AuthMiddleware` roda antes das rotas, então **a confirmação exige um token válido** (Fase 4).

### 4.3 Variáveis obrigatórias por cenário

| Variável | A | B | C |
|---|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | — | obrigatória | obrigatória |
| `FIREBASE_WEB_API_KEY` | — | obrigatória | obrigatória |
| `WORDPRESS_API_URL` | — | **obrigatória** (o padrão é a Ambiental) | **obrigatória** |
| `MCP_GITHUB_REPOS` / `MCP_GITHUB_TOKEN` | — | opcional | opcional |
| `OAUTH_SERVER_BASE_URL` | — | **obrigatória** (`https://<dominio>`) | `http://localhost:8080` |
| `OAUTH_PORTAL_BASE_URL` | — | **obrigatória** | `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | — | **obrigatória** (o domínio do portal) | o padrão já serve |
| `IP_RATE_LIMIT_TRUSTED_PROXIES` | — | `1`, atrás do Load Balancer | `0` |
| `MCP_GITHUB_FILENAMES` (nova, Fase 2) | — | opcional | opcional |
| `OAUTH_ALLOWED_REDIRECT_HOSTS` (nova, R16) | — | opcional | opcional |

---

## 5. Fases de execução

Cada fase termina com testes passando e um commit próprio (Conventional Commits, conforme o `CONTRIBUTING.md`), numa branch a partir de `main`.

### Fase 0: segurança imediata e atualização com o original
**Objetivo:** fechar o S1 e o S2 e alinhar com a 0.13.0.

1. Parar o servidor atual e subir de novo com `--host 127.0.0.1` (R2).
2. No Firebase do projeto `jor-mcp-m78bp5-8e56c`, desativar cadastros novos (R4). Pode exigir a atualização gratuita para o Identity Platform; se for o caso, pergunto antes.
3. Rodar `git remote add upstream https://github.com/ambiental-media/jor-mcp.git` e `git fetch upstream`.
4. Criar a branch `chore/sync-upstream-0.13.0` e fazer `git merge upstream/main`.
5. Resolver os conflitos:
   - `pyproject.toml`: versão `0.13.0` e manter `urllib3>=2.8.0`.
   - `uv.lock`: aceitar a versão do original e rodar `uv lock --upgrade-package urllib3`.
   - `service.yaml`: aceitar a versão do original (1Gi).
   - Os quatro documentos de replicação: unir as mudanças, mantendo as suas correções de formatação.
6. Gravar `tier: "basic"` em `allowed_users/reichaves@gmail.com`.
7. Rodar `uv sync`, `make check-lint check-format check-types check-tests` e reiniciar o servidor.

**Aceite:** testes verdes; `lsof` mostra `127.0.0.1:8080`; `/health` responde `200`.
**Para desfazer:** `git merge --abort` ou apagar a branch.

**Resultado (2026-10-17):**

| Passo | Situação |
|---|---|
| 1 | Feito. `lsof` mostra `127.0.0.1:8080`; `/health` responde `200`; `/mcp` sem token responde `401`; a conexão pelo IP da rede é recusada |
| 2 | **Feito pelo usuário** com `curl` (`PATCH .../config?updateMask=client.permissions.disabledUserSignup`), depois que a mesma chamada foi bloqueada para o Claude Code. Conferido: `client.permissions: {disabledUserSignup: true}`. **Não exigiu o Identity Platform**: o projeto continua `FIREBASE_AUTH`. Ficou um problema de ordem (R4): `reichaves@gmail.com` **ainda não existe no Firebase Auth** (`accounts:lookup`), então o primeiro login será recusado até o cadastro ser reativado por um momento (Fase 4, passo 3) |
| 3 | Feito de outro jeito: adicionar o remote `upstream` foi bloqueado, então o original foi buscado pela URL, sem remote |
| 4 | Feito na branch `chore/sync-upstream-0.13.1`, porque o original já estava na 0.13.1 |
| 5 | Feito. `pyproject.toml` em 0.13.1 com `urllib3>=2.8.0`. `uv.lock` difere do original só na versão e no `urllib3`, e `uv lock --locked` confirma. `service.yaml` mesclou sozinho: sem `JWT_SECRET`, 1Gi e `jor-mcp-runner`. Os documentos ficaram com o texto do original, com listas em hífen, sem `JWT_SECRET` e com a nota sobre o Native mode. Nos documentos do Firebase, a sua reescrita foi mantida, com a seção de IAM do original e o comportamento do `tier` atualizado |
| 6 | **Feito pelo usuário** com `curl` (`PATCH` no Firestore com `updateMask.fieldPaths=tier`). Conferido: `status: "active"` e `tier: "basic"` |
| 7 | Feito. Lint, formatação e tipos sem erros; 331 testes passando, cobertura de 100% |

Um incidente: a leitura da configuração do Firebase pela API imprimiu o `signIn.hashConfig.signerKey` na saída da sessão. O login por e-mail e senha está desativado, então o risco é baixo. **Apagar essa chave antes de exportar esta sessão para `traces/`.**

### Fase 1: documentação, sem mudar código
1. **Guias novos:** `docs/pt-br/2-replicacao/conectar-sua-redacao.md` e `docs/en/2-replication/connect-your-newsroom.md`, com:
   - a tabela de cenários A/B/C (§4.1) e os passos dos cenários B e C;
   - a tabela de variáveis por cenário (§4.3) e a tabela de clientes (§4.2);
   - o formato esperado pelo GitHub (só `pt.json`/`en.json` até a Fase 2) e as limitações (portal privado);
   - o **Checklist de segurança para quem replica**, com R2 a R10, R17 e um item marcável para cada.
2. **`README.md` / `README_pt-br.md`:**
   - seção "Usar com os dados da sua redação" depois de "Sobre", com 3 linhas e link para o guia;
   - `--host 127.0.0.1` no exemplo de execução a partir do código (R2).
3. **`conectando-clientes.md` / `connecting-clients.md`:**
   - separar "Instância da Ambiental" de "Sua instância";
   - acrescentar o Claude Code e o MCP Inspector;
   - deixar a correção do endereço `/mcp` × `/mcp/sse` para a Fase 4.
4. **`configuracao-e-env.md` / `configuration-and-env.md`:**
   - marcar quais variáveis são obrigatórias fora da Ambiental;
   - `OTEL_TRACES_EXPORTER` e `LOG_LEVEL` já vieram documentados com a 0.13.1.
5. **`guia-de-implantacao.md` / `deployment-guide.md`:**
   - §5.1: o `tier` obrigatório e a permissão `roles/firebaseauth.admin` (§2) já vieram com a 0.13.1;
   - §5.1, "Propagação e revogação": apontar para a revogação completa da §5.2;
   - nova §5.2 com a revogação em três passos (R3);
   - §8.1: Workload Identity Federation (R17) e exemplo de número de projeto genérico (A8).
6. **Textos:** trocar "curada pela Ambiental Media" por "curada pelos administradores da instância" em `config.py:104`, `oauth.py:192` e `contratos-api.md` (A7).

**Aceite:** todos os links internos funcionam e o `CONTRIBUTING.md` é respeitado (formatação e as duas línguas sincronizadas).

**Resultado (2026-10-17):** commit `4507998`, na branch `docs/phase1-connect-newsroom`, criada a partir de `chore/sync-upstream-0.13.1` (#8) porque a documentação nova depende da 0.13.1. PR #10, com base no #8.

| Item | Situação |
|---|---|
| 1 | Feito. `connect-your-newsroom.md` / `conectar-sua-redacao.md` com os cenários A/B/C, os passos de B e C, as variáveis por cenário, os clientes, as limitações e um checklist de segurança com 10 itens marcáveis. O R4 entrou com o cuidado sobre a ordem (desativar cadastros só depois do primeiro login de cada usuário) |
| 2 | Feito. Seção "Use It with Your Newsroom's Data" / "Usar com os Dados da Sua Redação" e `--host 127.0.0.1` no exemplo de execução. O índice de `docs/` também aponta para o guia novo |
| 3 | Feito. "Instância da Ambiental Media" separada de "Sua Própria Instância", com Claude Code e MCP Inspector. O endereço `/mcp` × `/mcp/sse` continua para a Fase 4 |
| 4 | Feito. As quatro variáveis com padrão `ambiental.media` estão marcadas como obrigatórias fora da Ambiental, com um aviso no topo. Correção extra: `MCP_GITHUB_REPOS` aparecia como obrigatória, mas o padrão vazio só desliga a fonte GitHub |
| 5 | Feito. §3.1 com o cuidado sobre a ordem, nova §5.2 com a revogação em três passos (R3), nova §8.3 com Workload Identity Federation (R17) e `123456789012` como número de projeto nos exemplos (A8). O `tier` obrigatório e o `roles/firebaseauth.admin` já tinham vindo com a 0.13.1 |
| 6 | Feito, só em docstrings e documentação: "administradores da instância" em `src/config.py`, `src/api/oauth.py` e `api-contracts.md` / `contratos-api.md` |

**Aceite conferido:**
- **Links:** 0 links internos quebrados nos arquivos alterados, conferidos por um script que calcula as âncoras como o GitHub. Para isso, três âncoras que já estavam quebradas foram corrigidas: o selo do Docker nos dois README e o link do CI no guia em português.
- **`CONTRIBUTING.md`:** listas com hífen, blocos de código com linguagem, nenhum link absoluto e as duas línguas sincronizadas.
- **Código:** lint, formatação e tipos sem erros; 331 testes passando, com cobertura de 100%.
- **Pendências para a Fase 4:** o guia do cenário C avisa que a impersonação ainda não foi validada de ponta a ponta na troca de token.

### Fase 2: código pequeno, com testes
1. **Aviso na inicialização** (A1), em `src/server.py`, no `server_lifespan`:
   - registrar `logger.warning` quando `WP_API_BASE_URL`, `OAUTH_SERVER_BASE_URL` ou `OAUTH_PORTAL_BASE_URL` contiverem `ambiental.media` **e** o `GCP_PROJECT_ID` não for o da Ambiental;
   - o comportamento da produção da Ambiental não muda;
   - teste em `tests/test_server.py`.
2. **Arquivos do GitHub configuráveis** (A4):
   - `src/config.py`: nova variável `MCP_GITHUB_FILENAMES`, padrão `"pt.json,en.json"`, que vira um `frozenset`;
   - `src/services/github.py:31`: `_I18N_FILENAMES` passa a vir da configuração;
   - continua aceitando só `.json`, porque `_collect_strings` (`src/tools.py:82`) percorre JSON; CSV e Markdown ficam fora do escopo;
   - testes em `tests/test_github_service.py`, com o padrão `patch` e `_make_response` já usado lá.
3. **`scripts/revoke_user.py`** (R3):
   - uso: `uv run python scripts/revoke_user.py <email>`;
   - executa os três passos e informa o que fez; com `--dry-run`, só mostra;
   - teste com o Firebase e o Firestore simulados (`tests/conftest.py`).
4. **`firestore.rules`** (R6): regras que negam todo acesso, mais as instruções de publicação no guia.
5. **`service.yaml` parametrizado** (R18), com as variáveis da §4.3.
6. **Opcional, R16:** `OAUTH_ALLOWED_REDIRECT_HOSTS` em `src/config.py`, validado em `ClientRegistrationRequest.validate_redirect_uris` (`oauth.py:90`):
   - o padrão aceita qualquer loopback e `claude.ai`;
   - testes em `tests/test_oauth_router.py` para loopback, `claude.ai` e um domínio recusado (`400 invalid_client_metadata`).

**Aceite:** `make check` verde, com cobertura de 90% ou mais e Bandit sem achados novos.

**Resultado (2026-10-17):** commit `59c1766`, na branch `feat/phase2-replication-hardening`, criada a partir de `docs/phase1-connect-newsroom`. PR #11, com base no #10.

| Item | Situação |
|---|---|
| 1 | Feito. `_warn_on_ambiental_defaults` em `src/server.py`, chamado no `server_lifespan` com o projeto resolvido por `_resolve_gcp_project_id()` da telemetria. No projeto `jor-mcp` (o da Ambiental, conforme o `cd.yml`) não há aviso. A comparação é pelo domínio exato, então `notambiental.media` não dispara. 4 testes em `tests/test_server.py` |
| 2 | Feito. `MCP_GITHUB_FILENAMES` em `src/config.py` (`parse_github_filenames`, padrão `"pt.json,en.json"`) substitui `_I18N_FILENAMES` em `src/services/github.py`. Nomes sem `.json` são descartados; uma lista vazia pula o GitHub com aviso. A variável não entrou no `service.yaml`, porque um valor vazio desligaria a fonte. 6 testes em `tests/test_github_service.py` |
| 3 | Feito. `scripts/revoke_user.py <email> [--dry-run]`, com o e-mail em minúsculas como no servidor; se não houver conta no Firebase, só informa. 4 testes em `tests/test_revoke_user.py` |
| 4 | Feito. `firestore.rules` nega todo acesso de clientes. O guia de implantação (§4, item 2) explica a publicação pelo console ou pelo CLI e lembra que um banco nomeado tem regras próprias |
| 5 | Feito. `OAUTH_SERVER_BASE_URL`, `OAUTH_PORTAL_BASE_URL` e `CORS_ALLOWED_ORIGINS` no `service.yaml`, vindos de variáveis do repositório no `cd.yml`. O deploy é interrompido se alguma estiver vazia, porque um valor vazio substitui o padrão em vez de cair nele. **Efeito:** quem usa o `cd.yml`, inclusive a Ambiental se a mudança for proposta na Fase 5, precisa criar essas três variáveis antes do próximo deploy |
| 6 | **Não feito.** O R16 continua dependendo da decisão 2 da §8 |

**Aceite conferido:**
- **Código:** lint, formatação e tipos sem erros; 345 testes passando (eram 331), cobertura de 100%.
- **Bandit:** sem achados em `src/` e em `scripts/revoke_user.py`. Os avisos de `nosec` são de código anterior em `oauth.py`.
- **Documentação:** 0 links internos quebrados; inglês e português sincronizados.
- **Testes reais, só leitura:**
  - Uma instância temporária em `127.0.0.1:8081`, com `OAUTH_PORTAL_BASE_URL` da Ambiental, registrou o aviso com `["WORDPRESS_API_URL", "OAUTH_PORTAL_BASE_URL"]`. O WordPress apareceu porque o `.env` local ainda usa o site da Ambiental, por falta de outro site para testar.
  - `revoke_user.py --dry-run` no projeto `jor-mcp-m78bp5-8e56c` informou o que faria e confirmou que a conta de teste ainda não existe no Firebase Auth.
  - A renderização do `service.yaml` com o `envsubst` do `cd.yml` não deixou nenhum `${...}`, e o deploy para quando falta o `CORS_ALLOWED_ORIGINS`.
- **Não passou:** o `check-deps` acusou a CVE-2026-59951 no `mcp` 1.29.1, que chega pelo `fastmcp` e é anterior a esta fase (o lock é o mesmo do original). A correção é `uv lock --upgrade-package mcp`, num PR separado (decisão 6 da §8).
- **Não rodou:** o `check-container`, porque o `docker` e o `trivy` não estão instalados nesta máquina.

### Fase 3: portal de login de referência
**Arquivos:** `portal/authorize.html`, `portal/authorize.js`, `portal/config.example.js` e, no `.gitignore`, a linha `portal/config.js`.

**Fluxo:**
1. Ler `client_id`, `code_challenge`, `code_challenge_method`, `redirect_uri` e `state` da URL. Rejeitar se faltar `client_id` ou `code_challenge`, ou se o método não for `S256`.
2. Mostrar o `client_name` e o **host do `redirect_uri`** (R14), usando `textContent` (R13).
3. Botão "Entrar com Google": `signInWithPopup(GoogleAuthProvider)` pelo Firebase JS SDK, carregado do CDN com SRI.
4. Botão "Permitir": `POST {OAUTH_SERVER_BASE_URL}/api/oauth/approve` com `Authorization: Bearer <idToken>`.
5. Redirecionar para `response.redirect_uri` (R12). Em caso de `403`, mostrar "conta não autorizada".
6. Nenhum `localStorage` (R15). `config.js` define `firebaseConfig` e `serverBaseUrl`.

**Avisos visíveis no próprio HTML:** "Referência para testes e replicação. Em produção, sirva por HTTPS e aplique o checklist de segurança."

**Aceite:** os testes manuais da §7 (itens 10 e 11) passam.

**Resultado (2026-10-17):** commit `a90cd3b`, na branch `feat/phase3-reference-portal`, criada a partir de `feat/phase2-replication-hardening`. PR #12, com base no #11.

**Desvios do plano:**
- **Arquivos:** o discovery anuncia `{OAUTH_PORTAL_BASE_URL}/authorize`, então a página ficou em `portal/authorize/index.html` (com `authorize.js`, `consent.js` e `authorize.css`), e não em `portal/authorize.html`. Assim a rota funciona no `http.server` local, que redireciona `/authorize` para `/authorize/` mantendo os parâmetros, e no GCS.
- **Sem `client_name`:** nenhuma rota do servidor o fornece, e a resposta do `/approve` também não. A página mostra o `client_id` e, como sinal confiável, o domínio de destino. Mostrar o `client_name` exigiria uma rota nova no servidor.
- **`redirect_uri` obrigatório no portal:** o servidor aceita o pedido sem ele, mas aí o usuário não veria o destino.

| Passo do fluxo | Situação |
|---|---|
| 1 | Feito. `parseAuthorizeParams` em `consent.js` exige `client_id`, `code_challenge`, `code_challenge_method=S256` e um `redirect_uri` http(s); aceita `response_type` ausente ou `code` |
| 2 | Feito, com o `client_id` no lugar do `client_name`. O domínio de destino aparece em destaque, com aviso quando não é loopback nem `claude.ai` (R14). Só `textContent` (R13) |
| 3 | Feito. Firebase compat SDK `10.14.1` do `www.gstatic.com`, com SRI `sha384` e `crossorigin="anonymous"` |
| 4 | Feito. `POST {serverBaseUrl}/api/oauth/approve` com `Authorization: Bearer <idToken>` e `credentials: "omit"` |
| 5 | Feito. `safeRedirectTarget` só segue o `redirect_uri` da resposta, se for http(s) e do mesmo domínio mostrado (R12). `403` mostra "conta não autorizada"; `400`, `401` e `429` também têm mensagens. "Negar" não redireciona |
| 6 | Feito. Sessão do Firebase só em memória (`Persistence.NONE`), sem `localStorage` (R15). `config.js` no `.gitignore` |

**Proteções além do plano:** CSP sem `unsafe-inline`, `<meta name="referrer" content="no-referrer">`, bloqueio quando a página roda dentro de um frame, e mensagem de erro para qualquer falha inesperada.

**Aceite conferido:**
- **Testes do portal:** `make check-portal` (`node --test`), 23 passando. Cobrem a validação, o aviso de destino, as checagens de redirecionamento e a segurança da página: nenhum `innerHTML` nem armazenamento, SRI em todo script externo, CSP sem `unsafe-inline`.
- **Chrome headless**, com o portal em `127.0.0.1:3000` e um `config.js` local fora do git:
  - pedido válido: etapa de login, destino `localhost`, sem aviso;
  - `redirect_uri=https://evil.example/cb`: aviso visível;
  - `client_id=<img src=x onerror=alert(1)>`: texto literal, nenhum `<img>` no DOM (§7, item 11);
  - sem `code_challenge`: erro;
  - `redirect_uri=javascript:...`: erro.
  O Firebase carregou, o que confirma os hashes SRI, e nenhuma violação de CSP foi registrada.
- **Defeito encontrado e corrigido no teste real:** a primeira versão ficava presa em "Loading…" esperando o `setPersistence` do Firebase. Agora a página renderiza na hora, e a persistência é aguardada só no clique de login.
- **Python:** sem mudança; 345 testes, cobertura de 100%, Bandit sem achados.
- **Pendente para a Fase 4:** o login com Google e a chamada real ao `/approve`, incluindo o item 10 da §7 (redirecionamento recusado com `redirect_uri` de outro domínio).
- **Limites conhecidos:** o `frame-ancestors` não pode ser declarado em `<meta>` e precisa vir de um cabeçalho do Load Balancer em produção; o `apis.google.com/js/api.js`, inserido pelo próprio Firebase, carrega sem SRI; os testes do portal não rodam no CI, que só prepara o ambiente Python.
- **Correção extra (A7):** "curated manually by Ambiental Media" ainda aparecia na regra da allow-list em `api-contracts.md` / `contratos-api.md`, e foi corrigido.

### Fase 4: teste de ponta a ponta local (cenário C)
1. Criar a conta de serviço e as permissões (§4.1, cenário C, passos 2 e 3).
2. Subir o servidor e o portal em `127.0.0.1`.
3. Reativar o cadastro por um momento (`disabledUserSignup: false`), porque a conta ainda não existe no Firebase Auth (R4). Rodar `claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp`, fazer o login e conferir:
   - o documento em `oauth_clients`;
   - o documento em `oauth_codes`, apagado depois da troca;
   - a troca devolve os tokens, o que confirma ou descarta o problema do `create_custom_token`.
4. Confirmar o endereço do MCP (`/mcp` ou `/mcp/sse`) e corrigir os documentos da Fase 1.
5. Chamar `list_latest_news`, `search_content` e `get_full_article` pelo Claude Code.
6. Com o primeiro login feito, desativar o cadastro de novo (`disabledUserSignup: true`) e confirmar que o login seguinte continua funcionando.
7. Opcional: túnel temporário para testar o Claude Desktop (R11).

**Resultado (2026-10-17):** commit `abe6c82`, na branch `fix/phase4-e2e-local`, criada a partir de `feat/phase3-reference-portal`. PR #13, com base no #12.

**Achado principal:** o cenário C, como a Fase 1 o documentou, não completava o login. Com credenciais impersonadas (`gcloud auth application-default login --impersonate-service-account`), o Firebase Admin SDK usa as credenciais como assinante direto e o `create_custom_token` falha com `'Credentials' object has no attribute 'key_id'`; com as credenciais pessoais, falha com "Failed to determine service account". A correção é a variável opcional `FIREBASE_SERVICE_ACCOUNT_ID`, repassada como `serviceAccountId` no `initialize_app`, para que o SDK assine pelo IAM `signBlob`. O `FIREBASE_CONFIG` não aceita essa opção. O Cloud Run não muda. Há 2 testes novos.

| Passo | Situação |
|---|---|
| 1 | Feito pelo usuário com um script revisado: APIs IAM e IAM Credentials ativadas; conta `jor-mcp-local` com `roles/datastore.user` e `roles/firebaseauth.admin`; `roles/iam.serviceAccountTokenCreator` sobre ela para ela mesma e para o usuário; ADC impersonando a conta |
| 2 | Feito. Servidor e portal em `127.0.0.1`, com `FIREBASE_SERVICE_ACCOUNT_ID` definido. O aviso da Fase 2 listou só o `WORDPRESS_API_URL` |
| 3 | Feito com um cliente MCP em script (descoberta, DCR, PKCE, callback em loopback): registro `201`, `/approve` `200`, troca `200` (Bearer de 3600 s e refresh token), **reuso do código `400 invalid_grant`**. No Firestore: cliente em `oauth_clients`, `oauth_codes` vazio depois da troca. No Firebase Auth: conta criada só com `google.com` e claim `{"tier": "basic"}` |
| 4 | Feito. **O endereço é `/mcp`**; `GET /mcp/sse` com token válido responde `404`. Guias corrigidos |
| 5 | Feito. `initialize`, `tools/list` e as três ferramentas (`list_latest_news`, `search_content`, `get_full_article`) responderam com conteúdo real. Depois, pelo **Claude Code** (`claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp`, autenticação pelo `/mcp`), `list_latest_news` respondeu dentro da sessão |
| 6 | Feito. Cadastro desativado pelo usuário (`disabledUserSignup: true`) e novo login com `200`. Ressalva: a configuração do Firebase não registra a hora da mudança, então a ordem (cadastro fechado antes do login) segue o combinado, sem prova nos registros |
| 7 | Não feito (opcional) |

**Testes da §7 feitos nesta fase:**
- **Item 10:** com `redirect_uri=https://evil.example/cb` e um cliente registrado para loopback, o `/approve` respondeu `400`, nenhum código foi emitido e o portal mostrou "The authorization request is invalid" sem redirecionar.
- **Revogação (§7, item 6):** `scripts/revoke_user.py` na conta de teste. Antes: renovação `200`, claim `{"tier": "basic"}`. Depois: **todas as tentativas de renovar o token foram recusadas**, a claim ficou vazia e a allow-list ficou `disabled`. O ID token já emitido continuou aceito até expirar (no máximo uma hora), como diz a §5.2 do guia. O acesso foi restaurado em seguida (`status: active`).
- **Item 13 (ponta a ponta):** passou, com o WordPress configurado no `.env` local, que ainda é o da Ambiental por falta de outro site.

**Aceite conferido:** lint, formatação e tipos sem erros; 347 testes, cobertura de 100%; Bandit sem achados; portal 23 testes; 0 links quebrados.

**Ainda não testado:** o item 4 da §7 (uma conta Google fora da lista deve receber `403`), que exige uma segunda conta.

**O que ficou ativo no ambiente local:** a conta `jor-mcp-local` e as permissões dela no projeto de testes; as credenciais de aplicação impersonando essa conta (para voltar: `gcloud auth application-default login`); o servidor `jor-mcp-local` na configuração do Claude Code deste projeto (para remover: `claude mcp remove jor-mcp-local -s local`).

### Fase 5: contribuição com o original (opcional)
- Abrir um PR em `ambiental-media/jor-mcp` com as Fases 1 e 2 e, se a Ambiental quiser, a Fase 3, seguindo o `.github/PULL_REQUEST_TEMPLATE.md` e o `make check`.
- Mencionar os achados S1 (já resolvido na 0.13.0), S3, S4 e S11. O S12 já foi resolvido pela própria Ambiental no #70. **S3 e S4 devem ser comunicados em privado antes**, porque afetam a produção da Ambiental.

---

## 6. Arquivos afetados

| Tipo | Arquivos |
|---|---|
| Documentação | `README.md`, `README_pt-br.md`, `docs/{pt-br,en}/1-*/conectando-clientes.md`/`connecting-clients.md`, `contratos-api.md`/`api-contracts.md`, `docs/{pt-br,en}/2-*/configuracao-e-env.md`/`configuration-and-env.md`, `guia-de-implantacao.md`/`deployment-guide.md`, **novos** `conectar-sua-redacao.md`/`connect-your-newsroom.md` e `CONEXAO.md` |
| Código | `src/config.py`, `src/server.py`, `src/services/github.py` e, opcionalmente, `src/api/oauth.py` |
| Testes | `tests/test_server.py`, `tests/test_github_service.py`, novo `tests/test_revoke_user.py` e, opcionalmente, `tests/test_oauth_router.py` |
| Infra | `service.yaml`, novo `firestore.rules` e `.gitignore` |
| Scripts e portal | novos `scripts/revoke_user.py` e `portal/*` |

---

## 7. Verificação

| # | O quê | Como | Resultado esperado |
|---|---|---|---|
| 1 | Qualidade | `make check-lint check-format check-types check-tests` | Verde, cobertura de 90% ou mais |
| 2 | Segurança estática | `make check-sast check-deps` | Sem achados novos |
| 3 | S2 fechado | `lsof -nP -iTCP:8080 -sTCP:LISTEN` | `127.0.0.1:8080` |
| 4 | S1 fechado | Conta Google de teste **fora** da lista: login direto no Firebase e chamada ao `/mcp` com o token | `403` (ou recusa no cadastro, se o R4 estiver ativo) |
| 5 | Lista na 0.13.x | Documento sem `tier` / com `tier: basic` | `403` / acesso liberado |
| 6 | Revogação (R3) | `revoke_user.py` em conta de teste; depois tentar usar a conta de todas as formas possíveis | Todas recusadas |
| 7 | Aviso (A1) | Remover `WORDPRESS_API_URL` do `.env` | Aviso no log de inicialização |
| 8 | Arquivos do GitHub (A4) | `MCP_GITHUB_FILENAMES=data.json` com um repositório público de teste | `search_content` retorna `source: github:<repo>` |
| 9 | Restrição de domínios (R16) | `POST /api/oauth/register` com um domínio fora da lista | `400` |
| 10 | Portal (R12) | `authorize.html?redirect_uri=https://evil.example&...` com cliente registrado para loopback | Sem redirecionamento para `evil.example` (`/approve` responde `400`) |
| 11 | Portal (R13 e R14) | `client_name` com `<img onerror>`; `redirect_uri` de outro domínio | Texto aparece literal; alerta de domínio visível |
| 12 | Regras do Firestore (R6) | `curl` no Firestore só com a apiKey | `403` |
| 13 | Ponta a ponta | Fase 4, passos 3 a 5 | As três ferramentas respondem com dados do WordPress configurado |

---

## 8. Decisões pendentes (suas)

1. **Portal:** fazer o de referência (Fase 3) ou pedir à Ambiental acesso ao `jor-mcp-site`?
2. **R16** (lista de domínios no `/register`): implementar aqui ou só propor à Ambiental?
3. **Fase 5:** contribuir com o original? Se sim, comunicar S3 e S4 em privado primeiro.
4. **Faturamento:** o cenário B exige faturamento no GCP (Cloud Run e Load Balancer). O cenário C não exige.
5. **Fase 0:** decidir se a branch `chore/sync-upstream-0.13.1` vai para `main` por PR no fork.
6. **CVE-2026-59951 no `mcp`:** atualizar para a 1.30.0 ou superior (`uv lock --upgrade-package mcp`) num PR separado, como foi feito com o `urllib3`.
7. **Limpeza do ambiente de testes:** manter ou remover a conta `jor-mcp-local`, a impersonação nas credenciais de aplicação e o `jor-mcp-local` no Claude Code (resultado da Fase 4).
