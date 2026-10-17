<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Integração GitHub

O `search_content` pesquisa os repositórios do GitHub listados em `MCP_GITHUB_REPOS` (`src/services/github.py`, `src/tools.py`). As variáveis estão descritas em [Configuração e Variáveis de Ambiente](../../2-replicacao/configuracao-e-env.md).

## 1. Como os arquivos são encontrados e lidos

1.  **Descoberta:** em cada repositório, a Git Trees API (`/repos/{owner}/{repo}/git/trees/HEAD?recursive=1`) lista todos os arquivos da branch padrão. Um arquivo entra quando o nome corresponde a um dos padrões de `MCP_GITHUB_FILENAMES` (nomes exatos como `pt.json` ou padrões `fnmatch` como `*.csv`), em qualquer nível. A comparação diferencia maiúsculas: `*.md` não pega `README.MD`. Arquivos que correspondem a um padrão de `MCP_GITHUB_EXCLUDE` ficam de fora (por exemplo `.claude/*,CLAUDE.md` para deixar de lado a configuração de agentes de IA).
2.  **Limites:** arquivos maiores que `MCP_GITHUB_MAX_FILE_BYTES` (padrão 1 MB, o limite da Contents API) são ignorados, e no máximo `MCP_GITHUB_MAX_FILES_PER_REPO` (padrão 50) entram por repositório. Os dois registram um aviso com o repositório e o caminho, nunca com o conteúdo.
3.  **Download:** cada arquivo é baixado pela Contents API e decodificado de Base64.
4.  **Leitura por extensão:**

| Extensão | Vira | É pesquisado em |
|---|---|---|
| `.json` | o objeto ou a lista do JSON | todos os valores de texto, em qualquer nível |
| `.csv` | um dicionário por linha, com as chaves do cabeçalho | todas as células |
| `.md`, `.markdown` | `{"text": <conteúdo do arquivo>}` | o texto inteiro |

Arquivos que não podem ser lidos (JSON inválido, CSV sem cabeçalho, JSON com um valor simples na raiz) são ignorados com um aviso.

## 2. Busca e resultados

A consulta é comparada em memória, sem diferenciar maiúsculas nem acentos. Cada arquivo encontrado vira um resultado com `source: github:<owner>/<repo>`, um trecho curto em torno da primeira ocorrência e um link para o arquivo no GitHub. Os arquivos são ordenados pela quantidade de ocorrências do termo, e no máximo `MCP_GITHUB_MAX_RESULTS` (padrão 10) são devolvidos; quando há mais, um último item `notice` informa o total, para que o modelo possa refinar a busca. Links de repositórios privados só abrem para quem pode lê-los no GitHub.

## 3. Cache

Sem cache, cada busca baixaria todos os arquivos de todos os repositórios. O conteúdo consolidado fica em memória por `MCP_GITHUB_CACHE_SECONDS` (padrão 300; `0` desliga), e buscas simultâneas esperam um único download. Um resultado vazio não é guardado. Cada instância do Cloud Run tem o seu próprio cache.

## 4. Autenticação e acesso

-   Sem `MCP_GITHUB_TOKEN`, só repositórios públicos funcionam, e o GitHub permite 60 requisições por hora.
-   Para repositórios privados, use um token fine-grained limitado aos repositórios listados, só com `Contents: Read-only` e validade de até 90 dias.
-   Tudo o que está nos arquivos indexados pode ser lido por todos os usuários da allow-list e pelo provedor de IA por trás do cliente deles. Indexe só o que todos podem ler.
-   O texto dos arquivos volta ao modelo como conteúdo a ser citado. A descrição da ferramenta pede ao modelo que não siga instruções encontradas nele, então indexe só repositórios em que você confia como fonte editorial.

## 5. Decisão Arquitetural: Por que Analisar JSON?
Para microsites Next.js hospedados no GitHub, nós analisamos especificamente os arquivos `messages/*.json` pré-renderizados em vez de Markdown bruto ou arquivos React `.tsx`. Isso garante que o LLM receba conteúdo final estruturado sem alucinar sobre a lógica de interface ou variáveis não renderizadas.
