// One place for every HTTP call: a timeout on each request, and errors turned
// into a small set of kinds with messages that are safe to show a user.

const config = window.THRIFT_CONFIG ?? {};
const TIMEOUT_MS = config.timeoutMs ?? 8000;

export const RETRY_MS = config.retryMs ?? 10000;
// How often the open page re-reads both services, so it does not go stale.
export const REFRESH_MS = config.refreshMs ?? 30000;
export const LISTINGS_URL = (config.listingsUrl ?? "").replace(/\/$/, "");
export const SWAPS_URL = (config.swapsUrl ?? "").replace(/\/$/, "");

// The sign-in token, sent to both services once someone is logged in (see session.js).
let authToken = null;
let onUnauthorized = () => {};
export const setAuthToken = (token) => {
  authToken = token;
};
// Called when a service says the token is no longer valid.
export const setUnauthorizedHandler = (handler) => {
  onUnauthorized = handler;
};

export class ApiError extends Error {
  // kind: "unreachable" | "timeout" | "invalid" | "not_found" | "conflict" | "signin" | "forbidden" | "server"
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }

  // True when the service itself is the problem, not this particular request.
  get serviceDown() {
    return this.kind === "unreachable" || this.kind === "timeout" || this.kind === "server";
  }
}

// FastAPI reports validation problems as a list of {loc, msg}. Turn the first
// few into one readable sentence.
function validationMessage(data) {
  if (!Array.isArray(data?.detail)) {
    return "Some of the values are not valid. Please check the form.";
  }
  const parts = data.detail.slice(0, 3).map((problem) => {
    const field = (problem.loc ?? []).filter((part) => part !== "body").join(" ");
    const message = String(problem.msg ?? "is not valid").replace(/^Value error, /, "");
    return field ? `${field.replaceAll("_", " ")}: ${message}` : message;
  });
  return parts.join("; ") + ".";
}

async function request(baseUrl, path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response;
  let data = null;
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  try {
    response = await fetch(baseUrl + path, {
      method,
      headers: Object.keys(headers).length === 0 ? undefined : headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (response.status !== 204) {
      data = await response.json().catch(() => null);
    }
  } catch (error) {
    if (error.name === "AbortError") {
      throw new ApiError("timeout", "The service took too long to answer.");
    }
    throw new ApiError("unreachable", "The service could not be reached.");
  } finally {
    clearTimeout(timer);
  }

  if (response.ok) return data;
  const detail = typeof data?.detail === "string" ? data.detail : null;
  if (response.status === 422) throw new ApiError("invalid", validationMessage(data));
  if (response.status === 404) throw new ApiError("not_found", detail ?? "That item no longer exists.");
  if (response.status === 401) {
    // A wrong password is also a 401, and must not sign anyone out.
    if (authToken && !path.startsWith("/auth/")) onUnauthorized();
    throw new ApiError("signin", detail ?? "Please log in first.");
  }
  if (response.status === 403) throw new ApiError("forbidden", detail ?? "You are not allowed to do that.");
  if (response.status === 409) throw new ApiError("conflict", detail ?? "That was already changed by someone else.");
  // 5xx and anything unexpected: never show internals, only a fixed message.
  throw new ApiError("server", "The service had a problem. Please try again in a moment.");
}

export const listingsApi = {
  health: () => request(LISTINGS_URL, "/health"),
  list: () => request(LISTINGS_URL, "/listings"),
  create: (listing) => request(LISTINGS_URL, "/listings", { method: "POST", body: listing }),
  update: (id, listing) => request(LISTINGS_URL, `/listings/${id}`, { method: "PUT", body: listing }),
  setStatus: (id, status) => request(LISTINGS_URL, `/listings/${id}/status`, { method: "PATCH", body: { status } }),
  remove: (id) => request(LISTINGS_URL, `/listings/${id}`, { method: "DELETE" }),
};

export const authApi = {
  signUp: (credentials) => request(LISTINGS_URL, "/auth/signup", { method: "POST", body: credentials }),
  logIn: (credentials) => request(LISTINGS_URL, "/auth/login", { method: "POST", body: credentials }),
  demoAccounts: () => request(LISTINGS_URL, "/auth/demo"),
  demoLogIn: (username) => request(LISTINGS_URL, "/auth/demo", { method: "POST", body: { username } }),
};

export const swapsApi = {
  health: () => request(SWAPS_URL, "/health"),
  list: () => request(SWAPS_URL, "/swaps?limit=20"),
  propose: (proposal) => request(SWAPS_URL, "/swaps", { method: "POST", body: proposal }),
  decide: (id, status) => request(SWAPS_URL, `/swaps/${id}/status`, { method: "PATCH", body: { status } }),
};
