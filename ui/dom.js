// Small helpers for building the page. Text from the services always goes in
// through textContent, never innerHTML, so a listing title cannot inject markup.

export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === false || value === null || value === undefined) continue;
    if (name === "class") node.className = value;
    else if (name === "text") node.textContent = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else if (value === true) node.setAttribute(name, "");
    else node.setAttribute(name, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  node.replaceChildren();
}

const euros = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
export const formatEuros = (value) => euros.format(value);

const dates = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const formatDate = (iso) => dates.format(new Date(iso));

export const CONDITION_LABELS = { 1: "Heavily used", 2: "Well used", 3: "Good", 4: "Very good", 5: "Like new" };

// A short message at the bottom of the page that goes away on its own.
let toastTimer;
export function toast(message, kind = "info") {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.className = `toast toast-${kind} toast-show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("toast-show"), 5000);
}

export function setPill(id, label, state) {
  const pill = document.getElementById(id);
  const words = { up: "available", down: "unavailable", unknown: "checking" };
  pill.className = `pill pill-${state}`;
  pill.textContent = `${label}: ${words[state]}`;
}
