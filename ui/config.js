// Where the browser finds the two services. This file is for local runs
// (docker compose publishes Listings on 8001 and Swaps on 8002). The deploy
// pipeline overwrites it with the Azure Container Apps URLs before publishing
// the UI to Azure Static Web Apps. Nothing here is a secret.
window.THRIFT_CONFIG = {
  listingsUrl: "http://localhost:8001",
  swapsUrl: "http://localhost:8002",
  // Every request gives up after this long, so a slow or stopped service
  // never leaves the page waiting.
  timeoutMs: 8000,
  // While a service is unreachable the page tries again this often.
  retryMs: 10000,
  // While the page is open and visible it re-reads both services this often.
  refreshMs: 30000,
};
