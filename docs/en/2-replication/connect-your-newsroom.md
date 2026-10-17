<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Connect Your Newsroom's Data

`jor-mcp` is not tied to Ambiental Media's content. Any newsroom can run its own instance and point it at **its own WordPress site and its own GitHub repositories**. This guide explains the ways to connect, what each one requires, and the security checklist to follow.

---

## 1. Connection Scenarios

| # | Scenario | Data source | Who can use it | Cost and effort |
|---|---|---|---|---|
| **A** | Use Ambiental Media's instance | Ambiental Media content only | Users on Ambiental Media's allow-list | None |
| **B** | **Run your own production instance** | **Your WordPress and GitHub** | Users on your allow-list | GCP with billing: Cloud Run, Load Balancer, a domain and a consent portal |
| **C** | Run locally for testing | Your WordPress and GitHub | Only you | Free, one machine |

Scenario A does not let you search your own content. To do that, use scenario B, and scenario C to try it out first.

### 1.1 Scenario A: Ambiental Media's instance

Ask Ambiental Media to add your Google account to their allow-list, then follow [Connecting to LLMs](../1-technical/connecting-clients.md#ambiental-media-instance).

### 1.2 Scenario B: your own production instance

1.  **Project and services:** create a GCP project, add Firebase to it and create the Firestore database in **Native mode**. Enable the `identitytoolkit`, `securetoken`, `firestore`, `run` and `artifactregistry` APIs.
2.  **Authentication:** enable the Google sign-in provider and disable Email/Password ([deployment guide, section 3](deployment-guide.md#3-firebase-console-security--authentication-configuration)). Disable sign-up only after each user has signed in once (see item 4 of the checklist below).
3.  **Allow-list:** create `allowed_users/<email>` with `status: "active"` and `tier: "basic"` for each user ([deployment guide, section 5](deployment-guide.md#5-manual-allow-list-management-allowed_users)).
4.  **Runtime service account:** create `jor-mcp-runner` with the roles listed in the [deployment guide, section 2](deployment-guide.md#2-gcp-iam-service-account-permissions).
5.  **GitHub token:** create a fine-grained token (checklist item 7) and store it in Secret Manager as `MCP_GITHUB_TOKEN`.
6.  **Image and deploy:** build the image, push it to Artifact Registry and deploy with `service.yaml`, setting every variable marked as required for scenario B in [section 2](#2-required-variables-by-scenario).
7.  **Consent portal:** publish a consent portal on GCS behind the same Load Balancer ([Load Balancer configuration](load-balancer-config.md)). See [section 4](#4-known-limitations): Ambiental Media's portal is private.
8.  **Firebase and Firestore protections:** restrict the API key, deploy the Firestore rules and configure the TTL policies (checklist items 5, 6 and 9).
9.  **Connect:** add `https://<your-domain>/mcp` as a connector in your MCP client ([section 3](#3-mcp-clients)).

### 1.3 Scenario C: local testing

1.  Repeat steps 1 to 3 of scenario B in a test project.
2.  Create a service account for local use, e.g. `jor-mcp-local@<project-id>.iam.gserviceaccount.com`, with `roles/datastore.user` and `roles/firebaseauth.admin`. Grant it `roles/iam.serviceAccountTokenCreator` on itself, and grant your own account `roles/iam.serviceAccountTokenCreator` on it.
3.  Use it through impersonation, never through a downloaded JSON key:

    ```bash
    gcloud auth application-default login \
      --impersonate-service-account=jor-mcp-local@<project-id>.iam.gserviceaccount.com
    ```

4.  Start the server bound to localhost only:

    ```bash
    uv run --env-file .env uvicorn src.server:app --host 127.0.0.1 --port 8080
    ```

5.  Serve a consent portal on `http://localhost:3000` (see [section 4](#4-known-limitations)).
6.  Connect with Claude Code:

    ```bash
    claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp
    ```

> [!NOTE]
> The impersonation setup in steps 2 and 3 has not yet been validated end to end against the token exchange (`create_custom_token`). Report any `403` from the token endpoint as an issue.

---

## 2. Required Variables by Scenario

Several defaults point to Ambiental Media. If you leave them unset, your instance searches Ambiental Media's WordPress and sends your users to Ambiental Media's consent portal. Set every variable marked **required** below. The full reference is in [Configuration and Environment](configuration-and-env.md).

| Variable | B (production) | C (local) |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Set by Cloud Run | **Required** |
| `FIREBASE_WEB_API_KEY` | **Required** | **Required** |
| `WORDPRESS_API_URL` | **Required** (default is Ambiental Media) | **Required** (default is Ambiental Media) |
| `MCP_GITHUB_REPOS` / `MCP_GITHUB_TOKEN` | Optional | Optional |
| `OAUTH_SERVER_BASE_URL` | **Required**: `https://<your-domain>` | **Required**: `http://localhost:8080` |
| `OAUTH_PORTAL_BASE_URL` | **Required**: your portal URL | **Required**: `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | **Required**: your portal origin | The default already allows `http://localhost:3000` |
| `IP_RATE_LIMIT_TRUSTED_PROXIES` | `1` behind the Load Balancer | `0` |
| `GCP_PROJECT_ID` | Optional on Cloud Run | Optional, needed for log and trace correlation |

---

## 3. MCP Clients

| Client | Scenarios | Notes |
|---|---|---|
| Claude Desktop and claude.ai (custom connector) | A and B | The connection starts from Anthropic's servers, so the server URL must be public HTTPS |
| Claude Code (`claude mcp add --transport http`) | A, B and C | Connects from your machine with a loopback callback. The simplest path for scenario C |
| MCP Inspector (`npx @modelcontextprotocol/inspector`) | A, B and C | Useful to debug the OAuth flow and list the tools |
| Custom agents (MCP SDK) | A, B and C | Must implement OAuth 2.1 with PKCE and Dynamic Client Registration (DCR) |

> [!NOTE]
> The server mounts the MCP endpoint at `/mcp`. Older material refers to `/mcp/sse`. Both answer `401` without a token, so confirm the path with a signed-in client on your instance.

---

## 4. Known Limitations

-   **Consent portal:** the production portal (`jor-mcp-site`) is a private repository. To complete the login flow on your own instance, you need a portal that implements the consent step described in [API Contracts](../1-technical/api-contracts.md). A minimal reference portal is planned.
-   **GitHub file format:** the GitHub source only reads files named `pt.json` or `en.json`, at any depth of each repository in `MCP_GITHUB_REPOS`, and searches the string values inside them. Repositories without those files return no results and no error.
-   **WordPress:** the site's REST API (`/wp-json/wp/v2/posts`) must be publicly readable.

---

## 5. Security Checklist for Replicators

Check every item before exposing your instance.

-   [ ] **1. Run a current release.** Use `0.13.1` or later: earlier releases do not require a valid `tier` claim on every token.
-   [ ] **2. Bind locally to `127.0.0.1`.** Never run the server with `--host 0.0.0.0` on your machine; that value belongs only in the `Dockerfile`.
-   [ ] **3. Revoke users completely.** When someone leaves, follow the [three-step revocation](deployment-guide.md#52-revoking-a-user) instead of only editing `allowed_users`.
-   [ ] **4. Disable sign-up and keep Google as the only provider.** Disabling sign-up also blocks the first Google login of allow-listed users who have never signed in, so disable it after each user's first login and re-enable it briefly when onboarding someone new ([deployment guide, section 3.1](deployment-guide.md#31-disabling-self-registration)).
-   [ ] **5. Restrict the Firebase API key** to your portal's domains (HTTP referrers) and to the `identitytoolkit` and `securetoken` APIs only.
-   [ ] **6. Deploy Firestore rules that deny all client access** (`allow read, write: if false;`). The server uses the Admin SDK, which these rules do not affect.
-   [ ] **7. Use least privilege.** A dedicated runtime service account (`jor-mcp-runner`), impersonation instead of JSON keys on developer machines, and a fine-grained GitHub token with `Contents: read` only, limited to the repositories in `MCP_GITHUB_REPOS`, expiring in 90 days or less.
-   [ ] **8. Index only what every user may read.** Every allow-listed user, and the AI provider behind their client, can read everything in the configured repositories. Record this decision.
-   [ ] **9. Configure TTL and HTTPS.** Firestore TTL policies on `oauth_codes.expires_at` and `ip_rate_limits.expires_at`, and HTTPS on every public URL.
-   [ ] **10. Deploy without long-lived keys.** Prefer [Workload Identity Federation](deployment-guide.md#83-keyless-authentication-with-workload-identity-federation) over the `GCP_SA_KEY` secret in GitHub Actions.
