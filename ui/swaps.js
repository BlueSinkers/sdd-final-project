// Swap proposals: propose a swap, see how fair it is, accept or decline.
// The fairness score always comes from the Swaps service, never from this page.

import { ApiError, RETRY_MS, listingsApi, swapsApi } from "./api.js";
import { CONDITION_LABELS, clear, el, formatDate, formatEuros, setPill, toast } from "./dom.js";
import { addCardAction, getListings, listingsLoaded, loadListings, onListingsChange, renderListings } from "./listings.js";

const VERDICT_CLASS = { "Fair trade": "verdict-fair", Lopsided: "verdict-lopsided", "Very uneven": "verdict-uneven" };
const VERDICT_EXPLANATION = {
  "Fair trade": "Both sides are worth about the same.",
  Lopsided: "One side is worth clearly more than the other.",
  "Very uneven": "One side is worth less than half of the other.",
};
const STATUS_LABELS = { proposed: "Waiting for an answer", accepted: "Accepted", declined: "Declined" };

const state = {
  swaps: [],
  loaded: false,
  error: null,
  retryTimer: null,
  requested: null,
  // Counts load attempts, so an older answer never overwrites a newer one.
  loadNumber: 0,
  // Ids of swaps with an accept or decline request in flight.
  deciding: new Set(),
};

const list = document.getElementById("swaps");
const message = document.getElementById("swaps-message");
const dialog = document.getElementById("swap-dialog");
const form = document.getElementById("swap-form");
const formError = document.getElementById("swap-form-error");
const result = document.getElementById("swap-result");

const available = () => state.loaded && state.error === null;

export async function loadSwaps() {
  clearTimeout(state.retryTimer);
  state.loadNumber += 1;
  const thisLoad = state.loadNumber;
  if (!state.loaded) setPill("status-swaps", "Swap checker", "unknown");
  const wasAvailable = available();
  try {
    const swaps = await swapsApi.list();
    if (thisLoad !== state.loadNumber) return; // a newer load is already on its way
    state.swaps = swaps;
    state.loaded = true;
    state.error = null;
    setPill("status-swaps", "Swap checker", "up");
  } catch (error) {
    if (thisLoad !== state.loadNumber) return;
    state.error = error instanceof ApiError ? error : new ApiError("server", "Something went wrong.");
    setPill("status-swaps", "Swap checker", "down");
    // Keep trying quietly: a service that was asleep answers after a few seconds.
    state.retryTimer = setTimeout(loadSwaps, RETRY_MS);
  }
  render();
  // The "Propose swap" buttons on the listing cards depend on this service.
  if (wasAvailable !== available()) renderListings();
}

function verdictBadge(swap) {
  return el(
    "span",
    { class: `verdict ${VERDICT_CLASS[swap.verdict] ?? ""}` },
    swap.verdict,
    el("span", { class: "verdict-score", text: `${Math.floor(swap.fairness_score * 100 + 1e-9)}%` }),
  );
}

function side(label, item) {
  return el(
    "div",
    { class: "side" },
    el("span", { class: "side-label", text: label }),
    el("strong", { text: item.title }),
    el("span", {
      class: "side-detail",
      text: `${item.owner_name} · ${formatEuros(item.estimated_value)} · ${CONDITION_LABELS[item.condition]}`,
    }),
    el("span", { class: "side-detail", text: `Counts as ${formatEuros(item.adjusted_value)} after condition` }),
  );
}

// Why a proposed swap can no longer be accepted, or null if it still can. An item
// that was already swapped or deleted must not be traded a second time. While the
// board has not loaded we cannot know, so we do not block.
function blockedReason(swap) {
  if (!listingsLoaded()) return null;
  for (const item of [swap.offered, swap.requested]) {
    const listing = getListings().find((candidate) => candidate.id === item.listing_id);
    if (!listing) return `“${item.title}” is no longer on the board.`;
    if (listing.status !== "open") return `“${item.title}” has already been swapped.`;
  }
  return null;
}

function row(swap) {
  const actions = el("div", { class: "swap-actions" });
  if (swap.status === "proposed") {
    const busy = state.deciding.has(swap.id);
    const blocked = blockedReason(swap);
    const names = `${swap.offered.title} for ${swap.requested.title}`;
    if (blocked) {
      actions.append(el("span", { class: "swap-blocked", text: `Cannot be accepted: ${blocked}` }));
    } else {
      actions.append(
        el("button", {
          class: "btn btn-small",
          type: "button",
          text: "Accept",
          "aria-label": `Accept swap: ${names}`,
          disabled: busy,
          onclick: () => decide(swap, "accepted"),
        }),
      );
    }
    actions.append(
      el("button", {
        class: "btn btn-small",
        type: "button",
        text: "Decline",
        "aria-label": `Decline swap: ${names}`,
        disabled: busy,
        onclick: () => decide(swap, "declined"),
      }),
    );
  }
  return el(
    "li",
    { class: "swap" },
    el(
      "div",
      { class: "swap-head" },
      verdictBadge(swap),
      el("span", { class: `swap-status swap-status-${swap.status}`, text: STATUS_LABELS[swap.status] }),
      el("span", { class: "swap-date", text: `${swap.proposer_name} · ${formatDate(swap.created_at)}` }),
    ),
    el("div", { class: "swap-sides" }, side("Offers", swap.offered), el("span", { class: "swap-arrow", text: "⇄" }), side("For", swap.requested)),
    swap.message ? el("p", { class: "swap-message", text: `“${swap.message}”` }) : null,
    actions,
  );
}

function render() {
  clear(message);
  clear(list);
  if (state.error) {
    message.append(
      el(
        "div",
        { class: "notice notice-warning" },
        el("strong", { text: "Swap checker unavailable. " }),
        el("span", { text: "You can still browse and post listings. Proposing swaps will work again as soon as it is back." }),
        el("button", { class: "btn btn-small", type: "button", text: "Try again now", onclick: loadSwaps }),
      ),
    );
    if (!state.loaded) return;
  }
  if (!state.loaded) {
    list.append(el("li", { class: "empty", text: "Loading swap proposals…" }));
    return;
  }
  if (state.swaps.length === 0) {
    list.append(el("li", { class: "empty", text: "No swaps proposed yet. Pick a listing and press “Propose swap”." }));
    return;
  }
  for (const swap of state.swaps) list.append(row(swap));
}

async function decide(swap, status) {
  // One request per swap at a time: a double click must not send two.
  if (state.deciding.has(swap.id)) return;
  state.deciding.add(swap.id);
  render();
  try {
    await swapsApi.decide(swap.id, status);
  } catch (error) {
    toast(error instanceof ApiError ? error.message : "Something went wrong.", "error");
    state.deciding.delete(swap.id);
    await loadSwaps();
    return;
  }
  state.deciding.delete(swap.id);
  if (status === "declined") {
    toast("Swap declined.");
    await loadSwaps();
    return;
  }
  // The two services never call each other, so the page marks both listings
  // as swapped. If Listings is down the swap still counts as accepted.
  const marked = await Promise.allSettled([
    listingsApi.setStatus(swap.offered.listing_id, "swapped"),
    listingsApi.setStatus(swap.requested.listing_id, "swapped"),
  ]);
  if (marked.every((outcome) => outcome.status === "fulfilled")) {
    toast("Swap accepted. Both listings are marked as swapped.");
  } else {
    toast("Swap accepted, but a listing could not be marked as swapped. Mark it on the board yourself.", "error");
  }
  await Promise.all([loadSwaps(), loadListings()]);
}

const snapshot = (listing) => ({
  listing_id: listing.id,
  title: listing.title,
  owner_name: listing.owner_name,
  condition: listing.condition,
  estimated_value: listing.estimated_value,
});

function openDialog(requested) {
  const offers = getListings().filter((listing) => listing.status === "open" && listing.id !== requested.id);
  state.requested = requested;
  form.reset();
  form.hidden = false;
  result.hidden = true;
  formError.textContent = "";
  document.getElementById("swap-requested").textContent =
    `${requested.title} (${requested.owner_name}, ${formatEuros(requested.estimated_value)}, ${CONDITION_LABELS[requested.condition].toLowerCase()})`;
  const select = form.elements.offered;
  clear(select);
  for (const listing of offers) {
    select.append(
      el("option", {
        value: listing.id,
        text: `${listing.title} (${listing.owner_name}, ${formatEuros(listing.estimated_value)}, ${CONDITION_LABELS[listing.condition].toLowerCase()})`,
      }),
    );
  }
  const none = offers.length === 0;
  document.getElementById("swap-submit").disabled = none;
  if (none) formError.textContent = "There is no other open listing to offer. Post one of your own first.";
  else syncProposer();
  dialog.showModal();
}

// The person proposing is normally the owner of the item being offered.
function syncProposer() {
  const offered = getListings().find((listing) => String(listing.id) === form.elements.offered.value);
  if (offered) form.elements.proposer_name.value = offered.owner_name;
}

function showResult(swap) {
  clear(result);
  result.append(
    el("h2", { text: "Swap proposed" }),
    el("p", { class: "result-verdict" }, verdictBadge(swap)),
    el("p", { text: VERDICT_EXPLANATION[swap.verdict] ?? "" }),
    el("div", { class: "swap-sides" }, side("You offer", swap.offered), el("span", { class: "swap-arrow", text: "⇄" }), side("You get", swap.requested)),
    el(
      "p",
      { class: "hint" },
      "The score is the lower adjusted value divided by the higher one. 80% or more is a fair trade, 50% to 79% is lopsided, below 50% is very uneven.",
    ),
    el("div", { class: "dialog-actions" }, el("button", { class: "btn btn-primary", type: "button", text: "Done", onclick: () => dialog.close() })),
  );
  form.hidden = true;
  result.hidden = false;
}

async function submit(event) {
  event.preventDefault();
  const offered = getListings().find((listing) => String(listing.id) === form.elements.offered.value);
  if (!offered || !state.requested) return;
  const button = document.getElementById("swap-submit");
  button.disabled = true;
  formError.textContent = "";
  try {
    const swap = await swapsApi.propose({
      proposer_name: form.elements.proposer_name.value,
      message: form.elements.message.value,
      offered: snapshot(offered),
      requested: snapshot(state.requested),
    });
    showResult(swap);
    loadSwaps();
  } catch (error) {
    if (error instanceof ApiError && error.serviceDown) {
      formError.textContent = "Swap checker unavailable. Your listings are safe; please try again in a moment.";
      loadSwaps();
    } else {
      formError.textContent = error instanceof ApiError ? error.message : "Something went wrong.";
    }
  } finally {
    button.disabled = false;
  }
}

export function initSwaps() {
  addCardAction((listing) => {
    if (listing.status !== "open") return null;
    const up = available();
    return el("button", {
      class: "btn btn-quiet btn-propose",
      type: "button",
      text: "Propose swap",
      disabled: !up,
      title: up ? null : "Swap checker unavailable",
      onclick: () => openDialog(listing),
    });
  });
  form.elements.offered.addEventListener("change", syncProposer);
  form.addEventListener("submit", submit);
  document.getElementById("swap-cancel").addEventListener("click", () => dialog.close());
  // Whether a proposal can still be accepted depends on the listings' status.
  onListingsChange(render);
  return loadSwaps();
}
