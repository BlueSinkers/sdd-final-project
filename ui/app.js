// Entry point. Each part of the page loads on its own, so one service being
// down never stops the rest of the page from working.

import { initListings } from "./listings.js";
import { initSwaps } from "./swaps.js";

initSwaps();
initListings();
