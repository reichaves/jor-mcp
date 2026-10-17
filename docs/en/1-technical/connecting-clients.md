<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Connecting to LLMs

This page explains how to connect Claude Desktop, Claude Code and other MCP-compliant clients to a Jor-MCP server. There are two cases:

-   **[Ambiental Media Instance](#ambiental-media-instance):** searches Ambiental Media's content. Your Google account must be on Ambiental Media's allow-list.
-   **[Your Own Instance](#your-own-instance):** searches your newsroom's WordPress and GitHub. See [Connect Your Newsroom's Data](../2-replication/connect-your-newsroom.md) to set it up.

The connection is completed through the client and your browser: the client opens the consent portal, you sign in with Google, and the client receives its tokens.

---

## Ambiental Media Instance

Follow these steps with the corresponding interface screens to connect Claude Desktop:

### Step 1: Open Customization Menu
In Claude Desktop, click on the **"Customize"** button in the lower left corner to open the settings and options menu.

![Step 1 - Claude Customization Menu](/assets/how-to-connect-01.png)

### Step 2: Add Custom Connector
In the customization sidebar, look for the **"Connectors"** section. Click on **"Add"**, and then select **"Add Custom Connector"**.

![Step 2 - Add Custom Connector](/assets/how-to-connect-02.png)

### Step 3: Enter Connector Details
Type `jor-mcp` as the **Connector Name** and enter `https://jormcp.ambiental.media/mcp/sse` as the **Connector URL**. Once both fields are filled, click the **"Add"** button.

![Step 3 - Enter Name and URL](/assets/how-to-connect-03.png)

### Step 4: Start Connection
On the newly created connector page, click the **"Connect"** button to initiate the authorization flow.

![Step 4 - Start Connection](/assets/how-to-connect-04.png)

### Step 5: Google SSO Sign In
Claude will redirect you to the secure **Jor-MCP Consent Portal** login screen. Click the Google button and choose or enter your authorized corporate/registered Google account credentials to log in.

![Step 5 - Google Sign In](/assets/how-to-connect-05.png)

### Step 6: Grant Consent
Once logged in, review the requested access permissions on the consent card, then click **"Allow Access"** (or **"Permitir Acesso"**) to securely authorize Claude Desktop to query the Jor-MCP database.

![Step 6 - Authorize Portal](/assets/how-to-connect-06.png)

### Step 7: Connection Finalized
Your authorization is verified, and the connection is securely established. You can now close the browser window.

![Step 7 - Ready to Use](/assets/how-to-connect-07.png)

Return to Claude Desktop. You are ready to run searches, fetch articles, and analyze datasets dynamically!

---

## Your Own Instance

Replace `<your-domain>` with the public domain of your instance. The server mounts the MCP endpoint at `/mcp`; older material refers to `/mcp/sse`, so confirm the path with a signed-in client.

### Claude Desktop and claude.ai

Follow the same steps as for the Ambiental Media instance, entering `https://<your-domain>/mcp` as the **Connector URL** in Step 3. The connection starts from Anthropic's servers, so the URL must be public HTTPS.

### Claude Code

```bash
claude mcp add --transport http jor-mcp https://<your-domain>/mcp
```

For a local test instance, use `http://localhost:8080/mcp`. Claude Code opens the browser for the login and receives the callback on a loopback address.

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Choose the **Streamable HTTP** transport, enter the server URL and start the OAuth flow. The Inspector shows each OAuth step and lists the available tools, which helps when debugging a new instance.

---

## Persistent Authentication

Once the initial login is complete, your authentication is persistent. Claude Desktop automatically handles token renewal in the background using long-lived Refresh Tokens. You will not need to re-authenticate or manually re-configure your settings, even if you restart Claude Desktop daily.

---

## Tier Upgrades (Paid Plans)

On your own instance, an administrator changes the user's `tier` in `allowed_users` ([deployment guide, section 5](../2-replication/deployment-guide.md#5-manual-allow-list-management-allowed_users)).

If you have negotiated a paid plan (`Pro` tier) with Ambiental Media:
1. Your account will be upgraded by our administrators via the **Jor-MCP Admin Console**.
2. No action is required on your part; the next time you use Jor-MCP, your request limits will automatically increase to the `Pro` tier quota.
