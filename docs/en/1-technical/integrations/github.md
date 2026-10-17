<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# GitHub Integration

`search_content` searches the GitHub repositories listed in `MCP_GITHUB_REPOS` (`src/services/github.py`, `src/tools.py`). The variables are described in [Configuration and Environment](../../2-replication/configuration-and-env.md).

## 1. How files are found and read

1.  **Discovery:** for each repository, the Git Trees API (`/repos/{owner}/{repo}/git/trees/HEAD?recursive=1`) lists every file of the default branch. A file is kept when its name matches one of the `MCP_GITHUB_FILENAMES` patterns (exact names such as `pt.json` or `fnmatch` patterns such as `*.csv`), at any depth. Matching is case-sensitive: `*.md` does not match `README.MD`.
2.  **Limits:** files larger than `MCP_GITHUB_MAX_FILE_BYTES` (default 1 MB, the Contents API limit) are skipped, and at most `MCP_GITHUB_MAX_FILES_PER_REPO` (default 50) are kept per repository. Both log a warning with the repository and path, never the content.
3.  **Download:** each file is fetched through the Contents API and decoded from Base64.
4.  **Parsing by extension:**

| Extension | Becomes | Searched as |
|---|---|---|
| `.json` | the JSON object or array | every string value, at any depth |
| `.csv` | one dictionary per row, keyed by the header row | every cell |
| `.md`, `.markdown` | `{"text": <file content>}` | the whole text |

Files that cannot be parsed (invalid JSON, a CSV without a header, a JSON scalar) are skipped with a warning.

## 2. Search and results

The query is matched in memory, ignoring case and accents. Each matching file becomes one result with `source: github:<owner>/<repo>`, a short excerpt around the first match and a link to the file on GitHub. Links to private repositories only open for people who can read them on GitHub.

## 3. Cache

Every search would otherwise download every matching file of every repository. The consolidated content is kept in memory for `MCP_GITHUB_CACHE_SECONDS` (default 300; `0` disables it), and concurrent searches wait for a single download. An empty result is not cached. Each Cloud Run instance keeps its own cache.

## 4. Authentication and access

-   Without `MCP_GITHUB_TOKEN`, only public repositories work and GitHub allows 60 requests per hour.
-   For private repositories, use a fine-grained token limited to the listed repositories with `Contents: Read-only`, expiring in 90 days or less.
-   Everything in the indexed files can be read by every allow-listed user and by the AI provider behind their client. Index only what all of them may read.
-   The text of the files is returned to the model as content to cite. The tool description tells the model not to follow instructions found in it, so index only repositories you trust as editorial sources.

## 5. Architectural Decision: Why Parse JSON?
For Next.js microsites hosted on GitHub, we specifically parse the pre-rendered `messages/*.json` files rather than raw Markdown or React `.tsx` files. This ensures the LLM receives structured, final content without hallucinating over UI logic or unrendered variables.
