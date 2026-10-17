// Copy to portal/config.js (ignored by git) and fill in your instance's values.
// The Firebase web config is public by design: protect the project with the API
// key restrictions and Firestore rules from the replication guide.
window.JOR_MCP_PORTAL_CONFIG = {
  firebaseConfig: {
    apiKey: "<firebase-web-api-key>",
    authDomain: "<project-id>.firebaseapp.com",
    projectId: "<project-id>",
  },
  // Public base URL of the jor-mcp server (OAUTH_SERVER_BASE_URL).
  serverBaseUrl: "http://localhost:8080",
};
