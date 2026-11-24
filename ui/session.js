// Who is signed in. The token comes from the Listings service and is sent to both
// services; it is kept in localStorage so a reload does not sign you out.

import { ApiError, authApi, setAuthToken } from "./api.js";
import { clear, el, toast } from "./dom.js";

const STORAGE_KEY = "thrift-session";
const listeners = [];
let session = null; // { username, token }

const dialog = document.getElementById("auth-dialog");
const form = document.getElementById("auth-form");
const formError = document.getElementById("auth-form-error");
const account = document.getElementById("account");
const demoBox = document.getElementById("auth-demo");
let mode = "login";
let afterSignIn = null;

export const currentUser = () => session?.username ?? null;
export const onSessionChange = (listener) => listeners.push(listener);

// Usernames compare the way the services compare them: ignoring case.
export const isMe = (name) => session !== null && String(name).trim().toLowerCase() === session.username.trim().toLowerCase();

function setSession(next) {
  session = next;
  setAuthToken(next?.token ?? null);
  try {
    if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be blocked (private mode); the session then lasts until reload.
  }
  renderAccount();
  for (const listener of listeners) listener();
}

function renderAccount() {
  clear(account);
  if (session) {
    account.append(
      el("span", { class: "account-name", text: `Signed in as ${session.username}` }),
      el("button", { class: "btn btn-small", type: "button", text: "Log out", onclick: () => signOut() }),
    );
  } else {
    account.append(el("button", { class: "btn btn-small", type: "button", text: "Log in / Sign up", onclick: () => openSignIn() }));
  }
}

export function signOut(message = "You are logged out.") {
  setSession(null);
  toast(message);
}

// The services answered 401: the token expired or is no longer valid.
export function sessionExpired() {
  if (session) signOut("Your session ended. Please log in again.");
}

function setMode(next) {
  mode = next;
  const signup = mode === "signup";
  document.getElementById("auth-dialog-title").textContent = signup ? "Create an account" : "Log in";
  document.getElementById("auth-submit").textContent = signup ? "Sign up" : "Log in";
  document.getElementById("auth-switch").textContent = signup ? "I already have an account" : "Create a new account";
  form.elements.password.autocomplete = signup ? "new-password" : "current-password";
  document.getElementById("auth-password-hint").hidden = !signup;
  formError.textContent = "";
}

// Opens the dialog. `then` runs once the person is signed in, so "Post a listing"
// can continue where it was interrupted.
export function openSignIn(then = null) {
  afterSignIn = then;
  form.reset();
  setMode("login");
  dialog.showModal();
}

function finish(next) {
  setSession(next);
  dialog.close();
  toast(`Welcome, ${next.username}.`);
  const then = afterSignIn;
  afterSignIn = null;
  if (then) then();
}

async function submit(event) {
  event.preventDefault();
  const button = document.getElementById("auth-submit");
  button.disabled = true;
  formError.textContent = "";
  const credentials = { username: form.elements.username.value, password: form.elements.password.value };
  try {
    finish(mode === "signup" ? await authApi.signUp(credentials) : await authApi.logIn(credentials));
  } catch (error) {
    formError.textContent = error instanceof ApiError ? error.message : "Something went wrong.";
  } finally {
    button.disabled = false;
  }
}

async function demoSignIn(username) {
  formError.textContent = "";
  try {
    finish(await authApi.demoLogIn(username));
  } catch (error) {
    formError.textContent = error instanceof ApiError ? error.message : "Something went wrong.";
  }
}

// One-click accounts for showing the app, offered only if the service has them switched on.
async function loadDemoAccounts() {
  try {
    const { accounts } = await authApi.demoAccounts();
    clear(demoBox);
    demoBox.hidden = accounts.length === 0;
    if (accounts.length === 0) return;
    demoBox.append(el("p", { class: "hint", text: "Demo accounts, no password needed:" }));
    const row = el("div", { class: "demo-accounts" });
    for (const name of accounts) {
      row.append(el("button", { class: "btn btn-small", type: "button", text: name, onclick: () => demoSignIn(name) }));
    }
    demoBox.append(row);
  } catch {
    demoBox.hidden = true; // Listings is down; the normal form says so when used
  }
}

export function initSession() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (stored && typeof stored.username === "string" && typeof stored.token === "string") {
      session = { username: stored.username, token: stored.token };
      setAuthToken(session.token);
    }
  } catch {
    session = null;
  }
  renderAccount();
  form.addEventListener("submit", submit);
  document.getElementById("auth-cancel").addEventListener("click", () => dialog.close());
  document.getElementById("auth-switch").addEventListener("click", () => setMode(mode === "signup" ? "login" : "signup"));
  loadDemoAccounts();
}
