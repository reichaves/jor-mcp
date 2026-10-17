<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Conectando a LLMs

Esta página explica como conectar o Claude Desktop, o Claude Code e outros clientes compatíveis com MCP a um servidor Jor-MCP. Há dois casos:

-   **[Instância da Ambiental Media](#instância-da-ambiental-media):** pesquisa o conteúdo da Ambiental Media. A sua conta Google precisa estar na allow-list da Ambiental Media.
-   **[Sua Própria Instância](#sua-própria-instância):** pesquisa o WordPress e o GitHub da sua redação. Veja [Conectar os Dados da Sua Redação](../2-replicacao/conectar-sua-redacao.md) para configurá-la.

A conexão é concluída pelo cliente e pelo seu navegador: o cliente abre o portal de consentimento, você entra com o Google e o cliente recebe os tokens.

---

## Instância da Ambiental Media

Siga estes passos com as telas de interface correspondentes para conectar o Claude Desktop:

### Passo 1: Abrir o Menu de Personalização
No Claude Desktop, clique no botão **"Customize"** no canto inferior esquerdo para abrir o menu de configurações e opções.

![Passo 1 - Menu de Personalização do Claude](/assets/how-to-connect-01.png)

### Passo 2: Adicionar Conector Personalizado
Na barra lateral de personalização, procure a seção **"Connectors"**. Clique em **"Add"** e selecione **"Add Custom Connector"**.

![Passo 2 - Adicionar Conector Personalizado](/assets/how-to-connect-02.png)

### Passo 3: Inserir Detalhes do Conector
Digite `jor-mcp` como o **Connector Name** (Nome do Conector) e digite `https://jormcp.ambiental.media/mcp/sse` como o **Connector URL** (URL do Conector). Assim que os dois campos estiverem preenchidos, clique no botão **"Add"**.

![Passo 3 - Inserir Nome e URL](/assets/how-to-connect-03.png)

### Passo 4: Iniciar Conexão
Na página do conector recém-criado, clique no botão **"Connect"** para iniciar o fluxo de autorização.

![Passo 4 - Iniciar Conexão](/assets/how-to-connect-04.png)

### Passo 5: Login via Google SSO
O Claude o redirecionará para a tela de login do portal de consentimento seguro do **Jor-MCP**. Clique no botão do Google e selecione ou insira as credenciais da sua conta do Google autorizada/cadastrada pela Ambiental Media para fazer login.

![Passo 5 - Login do Google](/assets/how-to-connect-05.png)

### Passo 6: Conceder Consentimento
Uma vez logado, revise as permissões de acesso solicitadas no cartão de consentimento e clique em **"Allow Access"** (ou **"Permitir Acesso"**) para autorizar com segurança o Claude Desktop a consultar a base de dados do Jor-MCP.

![Passo 6 - Autorizar no Portal](/assets/how-to-connect-06.png)

### Passo 7: Conexão Finalizada
Sua autorização foi verificada e a conexão está estabelecida com segurança. Você já pode fechar a janela do navegador.

![Passo 7 - Pronto para Usar](/assets/how-to-connect-07.png)

Retorne ao Claude Desktop. Você já está pronto para realizar buscas, buscar artigos e analisar conjuntos de dados de forma dinâmica!

---

## Sua Própria Instância

Troque `<seu-dominio>` pelo domínio público da sua instância. O servidor monta o endpoint MCP em `/mcp`; materiais mais antigos citam `/mcp/sse`, então confirme o caminho com um cliente já autenticado.

### Claude Desktop e claude.ai

Siga os mesmos passos da instância da Ambiental Media, informando `https://<seu-dominio>/mcp` como **URL do Conector** no Passo 3. A conexão parte dos servidores da Anthropic, então a URL precisa ser HTTPS pública.

### Claude Code

```bash
claude mcp add --transport http jor-mcp https://<seu-dominio>/mcp
```

Para uma instância local de testes, use `http://localhost:8080/mcp`. O Claude Code abre o navegador para o login e recebe o callback num endereço de loopback.

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Escolha o transporte **Streamable HTTP**, informe a URL do servidor e inicie o fluxo OAuth. O Inspector mostra cada etapa do OAuth e lista as ferramentas disponíveis, o que ajuda a depurar uma instância nova.

---

## Autenticação Persistente

Uma vez concluído o login inicial, sua autenticação é persistente. O Claude Desktop gerencia automaticamente a renovação do token em segundo plano usando *Refresh Tokens* de longa duração. Você não precisará se autenticar novamente nem reconfigurar suas configurações manualmente, mesmo se reiniciar o Claude Desktop diariamente.

---

## Upgrades de Nível (Planos Pagos)

Na sua própria instância, um administrador altera o `tier` do usuário em `allowed_users` ([guia de implantação, seção 5](../2-replicacao/guia-de-implantacao.md#5-gerenciamento-manual-da-lista-branca-allowed_users)).

Se você negociou um plano pago (nível `Pro`) com a Ambiental Media:
1. Sua conta será atualizada por nossos administradores via **Console de Administração do Jor-MCP**.
2. Nenhuma ação é necessária da sua parte; na próxima vez que você usar o Jor-MCP, seus limites de solicitação aumentarão automaticamente para a cota do nível `Pro`.
