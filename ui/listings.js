// The listings board: browse, post, edit, mark swapped, delete.

import { ApiError, RETRY_MS, listingsApi } from "./api.js";
import { CONDITION_LABELS, clear, el, formatEuros, setPill, toast } from "./dom.js";

const CATEGORY_LABELS = {
  clothing: "Clothing",
  books: "Books",
  electronics: "Electronics",
  home: "Home",
  sports: "Sports",
  other: "Other",
};

const state = {
  listings: [],
  loaded: false,
  error: null,
  retryTimer: null,
};

const board = document.getElementById("listings");
const message = document.getElementById("listings-message");
const categoryFilter = document.getElementById("filter-category");
const swappedFilter = document.getElementById("filter-swapped");
const dialog = document.getElementById("listing-dialog");
const form = document.getElementById("listing-form");
const formError = document.getElementById("listing-form-error");

// Other parts of the page (the swap panel) can add buttons to each card and
// hear about changes, without this module knowing about them.
const cardActions = [];
const changeListeners = [];
export const addCardAction = (build) => cardActions.push(build);
export const onListingsChange = (listener) => changeListeners.push(listener);
export const getListings = () => state.listings;
export const listingsAvailable = () => state.loaded && state.error === null;

function notifyChange() {
  for (const listener of changeListeners) listener(state.listings);
}

export async function loadListings() {
  clearTimeout(state.retryTimer);
  if (!state.loaded) setPill("status-listings", "Listings", "unknown");
  try {
    state.listings = await listingsApi.list();
    state.loaded = true;
    state.error = null;
    setPill("status-listings", "Listings", "up");
  } catch (error) {
    state.error = error instanceof ApiError ? error : new ApiError("server", "Something went wrong.");
    setPill("status-listings", "Listings", "down");
    // Keep trying quietly: a service that was asleep answers after a few seconds.
    state.retryTimer = setTimeout(loadListings, RETRY_MS);
  }
  render();
  notifyChange();
}

function conditionDots(condition) {
  const dots = el("span", { class: "dots", "aria-hidden": "true" });
  for (let i = 1; i <= 5; i += 1) dots.append(el("span", { class: i <= condition ? "dot dot-on" : "dot" }));
  return el("span", { class: "condition" }, dots, el("span", { text: `${CONDITION_LABELS[condition]} (${condition}/5)` }));
}

function card(listing) {
  const swapped = listing.status === "swapped";
  const actions = el("div", { class: "card-actions" });
  for (const build of cardActions) {
    const button = build(listing);
    if (button) actions.append(button);
  }
  actions.append(
    el("button", { class: "btn btn-quiet", type: "button", text: "Edit", onclick: () => openDialog(listing) }),
    el("button", {
      class: "btn btn-quiet",
      type: "button",
      text: swapped ? "Reopen" : "Mark swapped",
      onclick: () => changeStatus(listing, swapped ? "open" : "swapped"),
    }),
    el("button", { class: "btn btn-quiet btn-danger", type: "button", text: "Delete", onclick: () => remove(listing) }),
  );
  return el(
    "li",
    { class: swapped ? "card card-swapped" : "card" },
    el(
      "div",
      { class: "card-top" },
      el("span", { class: "chip", text: CATEGORY_LABELS[listing.category] ?? listing.category }),
      swapped ? el("span", { class: "chip chip-swapped", text: "Swapped" }) : null,
      el("span", { class: "price", text: formatEuros(listing.estimated_value) }),
    ),
    el("h3", { text: listing.title }),
    listing.description ? el("p", { class: "description", text: listing.description }) : null,
    conditionDots(listing.condition),
    el("p", { class: "owner", text: `Posted by ${listing.owner_name}` }),
    actions,
  );
}

function render() {
  clear(message);
  if (state.error) {
    message.append(
      el(
        "div",
        { class: "notice notice-error" },
        el("strong", { text: "Listings are unavailable right now. " }),
        el("span", {
          text: state.loaded
            ? "You are looking at the last listings we loaded. We keep trying to reconnect."
            : "We could not load the board. We keep trying to reconnect.",
        }),
        el("button", { class: "btn btn-small", type: "button", text: "Try again now", onclick: loadListings }),
      ),
    );
  }
  document.getElementById("new-listing").disabled = Boolean(state.error);

  clear(board);
  if (!state.loaded) {
    if (!state.error) board.append(el("li", { class: "empty", text: "Loading listings…" }));
    return;
  }
  const category = categoryFilter.value;
  const visible = state.listings.filter(
    (listing) => (swappedFilter.checked || listing.status === "open") && (!category || listing.category === category),
  );
  if (visible.length === 0) {
    board.append(
      el("li", {
        class: "empty",
        text: state.listings.length === 0 ? "Nothing here yet. Post the first listing." : "No listings match these filters.",
      }),
    );
    return;
  }
  for (const listing of visible) board.append(card(listing));
}

function report(error) {
  toast(error instanceof ApiError ? error.message : "Something went wrong.", "error");
  // If the service itself is down, refresh so the page shows it clearly.
  if (error instanceof ApiError && error.serviceDown) loadListings();
}

async function changeStatus(listing, status) {
  try {
    await listingsApi.setStatus(listing.id, status);
    toast(status === "swapped" ? `"${listing.title}" is marked as swapped.` : `"${listing.title}" is open again.`);
    await loadListings();
  } catch (error) {
    report(error);
    if (error.kind === "not_found") loadListings();
  }
}

async function remove(listing) {
  if (!window.confirm(`Delete "${listing.title}"? This cannot be undone.`)) return;
  try {
    await listingsApi.remove(listing.id);
    toast(`"${listing.title}" was deleted.`);
  } catch (error) {
    report(error);
    if (error.kind !== "not_found") return;
  }
  await loadListings();
}

function openDialog(listing = null) {
  form.reset();
  formError.textContent = "";
  form.dataset.id = listing ? String(listing.id) : "";
  document.getElementById("listing-dialog-title").textContent = listing ? "Edit listing" : "Post a listing";
  document.getElementById("listing-submit").textContent = listing ? "Save changes" : "Post listing";
  form.elements.condition.value = "3";
  if (listing) {
    for (const name of ["title", "description", "category", "condition", "estimated_value", "owner_name"]) {
      form.elements[name].value = listing[name];
    }
  }
  dialog.showModal();
}

async function submit(event) {
  event.preventDefault();
  const fields = form.elements;
  const listing = {
    title: fields.title.value,
    description: fields.description.value,
    category: fields.category.value,
    condition: Number(fields.condition.value),
    estimated_value: Number(fields.estimated_value.value),
    owner_name: fields.owner_name.value,
  };
  const id = form.dataset.id;
  const button = document.getElementById("listing-submit");
  button.disabled = true;
  formError.textContent = "";
  try {
    if (id) await listingsApi.update(id, listing);
    else await listingsApi.create(listing);
    dialog.close();
    toast(id ? "Listing updated." : "Listing posted.");
    await loadListings();
  } catch (error) {
    // Keep the dialog open so nothing the user typed is lost.
    formError.textContent = error instanceof ApiError ? error.message : "Something went wrong.";
  } finally {
    button.disabled = false;
  }
}

export function initListings() {
  for (const [value, label] of Object.entries(CATEGORY_LABELS)) {
    categoryFilter.append(el("option", { value, text: label }));
    form.elements.category.append(el("option", { value, text: label }));
  }
  for (const [value, label] of Object.entries(CONDITION_LABELS)) {
    form.elements.condition.append(el("option", { value, text: `${value} - ${label}` }));
  }
  categoryFilter.addEventListener("change", render);
  swappedFilter.addEventListener("change", render);
  document.getElementById("new-listing").addEventListener("click", () => openDialog());
  document.getElementById("listing-cancel").addEventListener("click", () => dialog.close());
  form.addEventListener("submit", submit);
  return loadListings();
}
