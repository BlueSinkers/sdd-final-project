// Entry point. Each part of the page loads on its own, so one service being
// down never stops the rest of the page from working.

import { REFRESH_MS, setUnauthorizedHandler } from "./api.js";
import { initListings, loadListings, renderListings } from "./listings.js";
import { initSession, onSessionChange, sessionExpired } from "./session.js";
import { initSwaps, loadSwaps, renderSwaps } from "./swaps.js";

// Signing in or out changes which buttons each card and swap shows.
initSession();
setUnauthorizedHandler(sessionExpired);
onSessionChange(() => {
  renderListings();
  renderSwaps();
});

initSwaps();
initListings();

// Keep an open page fresh: other people post, swap and decide while it is open.
// Nothing runs while the tab is in the background; coming back refreshes at once.
function refresh() {
  if (document.hidden) return;
  loadSwaps();
  loadListings();
}
setInterval(refresh, REFRESH_MS);
document.addEventListener("visibilitychange", refresh);
