<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Configuração e Variáveis de Ambiente

Este documento fornece uma lista abrangente de todas as variáveis de ambiente e recursos de nuvem utilizados pelo servidor Jor-MCP. Se você estiver replicando o servidor para sua própria redação, use este guia para configurar seus arquivos `.env` e as configurações de serviço do Google Cloud.

---

## 1. Principais Recursos de Nuvem Utilizados

O Jor-MCP foi projetado como uma plataforma totalmente serverless no **Google Cloud Platform (GCP)**. Os seguintes recursos principais devem ser configurados:

1.  **Google Cloud Run:** Hospeda o servidor ASGI Python `jor-mcp` baseado em containers de forma stateless.
2.  **Google Cloud Storage (GCS):** Hospeda os ativos estáticos do portal de consentimento Next.js (`jor-mcp-site`).
3.  **Google Cloud Firestore (Native mode):** Banco de dados de documentos NoSQL. Ele armazena limites de taxa mensais, clientes OAuth registrados dinamicamente (DCR), códigos de autorização temporários e a allow-list de usuários.

    > [!WARNING]
    > O banco **precisa ser criado em Firestore Native mode**, e não em Datastore mode. O servidor acessa o banco pelo cliente nativo do Firestore (`google.cloud.firestore_v1`), que não consegue ler nem gravar num banco em Datastore mode. O modo não pode ser alterado depois que há dados gravados, então escolha Native mode na criação. Se usar um banco nomeado em vez do `(default)`, defina `FIRESTORE_DATABASE_ID`.
4.  **Google Cloud Identity Platform / Firebase Auth:** Gerencia a autenticação Google SSO e emite JSON Web Tokens (JWTs) seguros.
5.  **API REST externa do WordPress:** O site CMS de destino onde os artigos editoriais são publicados.
6.  **API REST externa do GitHub:** Repositório de destino que hospeda metadados editoriais multilíngues em arquivos JSON.
7.  **Conta de Serviço IAM (`jor-mcp-runner`):** A identidade de execução dedicada e de menor privilégio anexada ao Cloud Run. Suas funções devem cobrir Firestore, segredos, observabilidade e o Firebase Admin SDK — veja o [guia de implantação, seção 2](guia-de-implantacao.md).

---

## 2. Referência de Variáveis de Ambiente

Configure estas variáveis nas configurações de ambiente do seu serviço Cloud Run ou nos arquivos `.env` locais.

> [!IMPORTANT]
> As variáveis marcadas como **obrigatórias fora da Ambiental Media** têm como padrão as URLs da própria Ambiental Media. Em qualquer outra instância, defina todas elas: caso contrário, o servidor pesquisa o WordPress da Ambiental Media e manda os seus usuários para o portal de consentimento da Ambiental Media. Fora do projeto GCP da Ambiental Media, o servidor registra um aviso na inicialização com o nome de cada uma que ainda aponte para `ambiental.media`. Veja [Conectar os Dados da Sua Redação](conectar-sua-redacao.md#2-variáveis-obrigatórias-por-cenário) para os valores por cenário.

### 2.1 Estado e Limitação de Taxa (Firestore)
-   `FIRESTORE_DATABASE_ID` (Padrão: `"(default)"`): O ID do banco de dados Firestore. Substitua se utilizar uma instância de banco de dados nomeada.
-   `RATE_LIMIT_COLLECTION` (Padrão: `"rate_limits"`): Coleção do Firestore contendo janelas mensais de contadores de usuários.
-   `RATE_LIMIT_BASIC_REQUESTS` (Padrão: `"500"`): Cota mensal para usuários do nível `basic`.
-   `RATE_LIMIT_PRO_REQUESTS` (Padrão: `"2000"`): Cota mensal para usuários do nível `pro`.

#### Limite por IP nas rotas não autenticadas
Aplica-se somente à superfície isenta de autenticação (`/.well-known/*` e `/api/oauth/*`), que
de outra forma permitiria a qualquer pessoa inundar o Firestore via `POST /api/oauth/register`.

-   `IP_RATE_LIMIT_COLLECTION` (Padrão: `"ip_rate_limits"`): Coleção do Firestore com as janelas curtas por IP. Os documentos gravam um campo `expires_at` — configure uma política de TTL do Firestore sobre ele para que janelas expiradas sejam removidas automaticamente.
-   `IP_RATE_LIMIT_REQUESTS` (Padrão: `"60"`): Requisições permitidas por IP em cada janela.
-   `IP_RATE_LIMIT_WINDOW_SECONDS` (Padrão: `"60"`): Duração da janela em segundos.
-   `IP_RATE_LIMIT_TRUSTED_PROXIES` (Padrão: `"1"`): Número de camadas de proxy confiáveis acrescentando entradas ao final de `X-Forwarded-For`. O Google Cloud Load Balancing reescreve o cabeçalho como `<valor-enviado>, <ip-do-cliente>, <ip-do-load-balancer>`, portanto o IP real do cliente é a entrada `IP_RATE_LIMIT_TRUSTED_PROXIES + 1` posições a partir da direita (isto é, a penúltima entrada, imediatamente antes do IP do load balancer). Ler a primeira entrada permitiria que qualquer chamador forjasse sua identidade. Use `"0"` quando o contêiner for acessado diretamente sem proxy.

### 2.2 Segurança e Proxy OAuth 2.1
-   `CORS_ALLOWED_ORIGINS` (Padrão: `"http://localhost:3000,https://jormcp.ambiental.media"`; **obrigatória fora da Ambiental Media** em produção): Lista de origens permitidas (CORS) separadas por vírgula.
-   `OAUTH_SERVER_BASE_URL` (Padrão: `"https://jormcp.ambiental.media"`; **obrigatória fora da Ambiental Media**): URL pública deste servidor. Utilizado para metadados de descoberta.
-   `OAUTH_PORTAL_BASE_URL` (Padrão: `"https://jormcp.ambiental.media"`; **obrigatória fora da Ambiental Media**): URL pública do portal de consentimento.
-   `OAUTH_CLIENTS_COLLECTION` (Padrão: `"oauth_clients"`): Coleção do Firestore que armazena clientes registrados.
-   `OAUTH_CODES_COLLECTION` (Padrão: `"oauth_codes"`): Coleção do Firestore que armazena códigos OAuth temporários e estado PKCE.
-   `OAUTH_CODE_TTL_SECONDS` (Padrão: `"600"`): Tempo de vida dos códigos de autorização emitidos.
-   `ALLOWED_USERS_COLLECTION` (Padrão: `"allowed_users"`): Lista branca no Firestore contendo e-mails autorizados.
-   `FIREBASE_WEB_API_KEY` (Obrigatório em produção): A Web API Key encontrada nas configurações do seu projeto Firebase, usada para a troca segura de tokens.
-   `FIREBASE_SERVICE_ACCOUNT_ID` (Padrão: vazio): Conta de serviço com a qual o Firebase Admin SDK assina os custom tokens, pelo `signBlob` do IAM. Deixe vazio no Cloud Run. Defina ao rodar localmente com Application Default Credentials impersonadas, com as quais o SDK não consegue assinar diretamente; a conta precisa de `roles/iam.serviceAccountTokenCreator` sobre ela mesma.

### 2.3 Configurações de Fontes de Conteúdo Externas
-   `WORDPRESS_API_URL` (Padrão: `"https://ambiental.media/wp-json"`; **obrigatória fora da Ambiental Media**): URL base da API do CMS WordPress de destino.
-   `MCP_GITHUB_TOKEN` (Opcional para repositórios públicos, recomendado): Token de Acesso Pessoal (PAT) para autenticação na API do GitHub.
-   `MCP_GITHUB_REPOS` (Padrão: vazio, o que desliga a fonte GitHub): Lista de repositórios do GitHub separados por vírgula (no formato `proprietario/repositorio`). Só são lidos os arquivos que correspondem a `MCP_GITHUB_FILENAMES`.
-   `MCP_GITHUB_FILENAMES` (Padrão: `"pt.json,en.json"`): Padrões de nome de arquivo, separados por vírgula, pesquisados em cada repositório e comparados com o nome do arquivo em qualquer nível: nomes exatos (`pt.json`) ou padrões `fnmatch` (`*.csv`, `dados-*.json`). Extensões aceitas: `.json`, `.csv`, `.md` e `.markdown`; as outras entradas são descartadas. Veja [Integração GitHub](../1-tecnico/integracoes/github.md) para saber como cada formato é pesquisado.
-   `MCP_GITHUB_EXCLUDE` (Padrão: vazio): Padrões `fnmatch`, separados por vírgula, de arquivos deixados de fora mesmo quando o nome corresponde. Cada padrão é comparado com o caminho completo no repositório (`.claude/*`, `docs/rascunhos/*`); um padrão sem `/` também é comparado com o nome do arquivo em qualquer nível (`CLAUDE.md`). Diferencia maiúsculas; o `*` também atravessa `/`.
-   `MCP_GITHUB_MAX_RESULTS` (Padrão: `"10"`): Número máximo de arquivos do GitHub devolvidos por busca, ordenados pela quantidade de ocorrências do termo em cada um. Quando mais arquivos correspondem, os resultados terminam com um item `notice` que informa o total. `0` devolve todos.
-   `MCP_GITHUB_MAX_FILE_BYTES` (Padrão: `"1000000"`): Maior arquivo baixado, em bytes; arquivos maiores são ignorados com um aviso. 1 MB é o limite da Contents API.
-   `MCP_GITHUB_MAX_FILES_PER_REPO` (Padrão: `"50"`): Número máximo de arquivos baixados por repositório; os demais são ignorados com um aviso.
-   `MCP_GITHUB_CACHE_SECONDS` (Padrão: `"300"`): Por quanto tempo o conteúdo baixado do GitHub é reaproveitado antes de ser baixado de novo. `0` desliga o cache. Cada instância do Cloud Run tem o seu.
-   `MCP_GITHUB_API_BASE_URL` (Padrão: `"https://api.github.com"`): Endpoint da API REST do GitHub.

### 2.4 Diagnóstico e Telemetria
-   `HTTP_TIMEOUT` (Padrão: `"10.0"`): Limite de tempo de solicitações HTTP de saída em segundos.
-   `LOG_LEVEL` (Padrão: `"INFO"`): Nível mínimo do logger raiz.
-   `OTEL_TRACES_EXPORTER` (Padrão: `"none"`): Exportador de spans — `otlp`, `console` ou `none`. A exportação é opcional por escolha explícita: definir apenas `OTEL_EXPORTER_OTLP_ENDPOINT` não surte efeito, esta variável também precisa ser definida como `otlp`. Um endpoint que recusa conexões faz cada lote tentar e falhar, inundando o log com erros transitórios — por isso o silêncio é o padrão. Os spans continuam sendo criados de qualquer forma; é deles que vem o `trace_id` presente em cada registro de log.
-   `OTEL_EXPORTER_OTLP_ENDPOINT` (Opcional): Endpoint do coletor usado quando `OTEL_TRACES_EXPORTER=otlp`.
-   `OTEL_SERVICE_NAME` (Padrão: `"jor-mcp"`): Nome do serviço registrado nos rastreamentos.
-   `GCP_PROJECT_ID` (Opcional no Cloud Run, obrigatório fora dele): ID do projeto GCP usado para vincular as entradas de log aos rastreamentos no Cloud Logging. No Cloud Run, é lido das credenciais do ambiente quando ausente. Em qualquer outro lugar precisa ser informado, caso contrário os campos de correlação são omitidos de todas as entradas de log.

---

## 3. Nota sobre a Replicação da Infraestrutura (Playbook Futuro)

Atualmente, os recursos de infraestrutura do GCP (Load Balancers, Cloud Run, coleções do Firestore e Identity Platform) são provisionados manualmente.

**Atualização Planejada:** Após a conclusão da fase inicial de replicação piloto, entregaremos um **playbook de replicação abrangente**. Isso incluirá:
-   **Infraestrutura como Código (IaC):** Scripts do Terraform para provisionar automaticamente todos os recursos necessários no GCP.
-   **Configuração como Código (CaC):** Configurações automatizadas para vincular com segurança o Identity Platform, regras do Firestore e implantação automatizada de segredos.
