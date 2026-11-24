// Tests for ui/api.js: every kind of failure becomes a fixed, safe message.
// Run with: node --test ui/tests   (no dependencies, no browser)

import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";

globalThis.window = { THRIFT_CONFIG: { listingsUrl: "http://l.test/", swapsUrl: "http://s.test", timeoutMs: 50, retryMs: 1234 } };
const { ApiError, LISTINGS_URL, RETRY_MS, SWAPS_URL, listingsApi, swapsApi } = await import("../api.js");

const realFetch = globalThis.fetch;
let calls;

function answer(status, body) {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => {
        if (body === undefined) throw new Error("no body");
        return body;
      },
    };
  };
}

beforeEach(() => {
  calls = [];
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

describe("configuration", () => {
  test("reads the service addresses and drops a trailing slash", () => {
    assert.equal(LISTINGS_URL, "http://l.test");
    assert.equal(SWAPS_URL, "http://s.test");
    assert.equal(RETRY_MS, 1234);
  });
});

describe("requests", () => {
  test("sends JSON bodies with the right method and path", async () => {
    answer(201, { id: 1 });
    await listingsApi.create({ title: "Lamp" });
    assert.equal(calls[0].url, "http://l.test/listings");
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers["Content-Type"], "application/json");
    assert.equal(calls[0].options.body, '{"title":"Lamp"}');
  });

  test("status changes are PATCH requests", async () => {
    answer(200, {});
    await listingsApi.setStatus(7, "swapped");
    await swapsApi.decide(3, "accepted");
    assert.equal(calls[0].url, "http://l.test/listings/7/status");
    assert.equal(calls[0].options.method, "PATCH");
    assert.equal(calls[0].options.body, '{"status":"swapped"}');
    assert.equal(calls[1].url, "http://s.test/swaps/3/status");
  });

  test("the proposals list asks for 20 swaps", async () => {
    answer(200, []);
    await swapsApi.list();
    assert.equal(calls[0].url, "http://s.test/swaps?limit=20");
  });

  test("a 204 answer has no body to read", async () => {
    answer(204);
    assert.equal(await listingsApi.remove(1), null);
  });
});

describe("failures", () => {
  async function failure(call) {
    try {
      await call();
    } catch (error) {
      assert.ok(error instanceof ApiError, "expected an ApiError");
      return error;
    }
    assert.fail("expected the call to fail");
  }

  test("422 becomes one readable sentence", async () => {
    answer(422, {
      detail: [
        { loc: ["body", "estimated_value"], msg: "Input should be greater than 0" },
        { loc: ["body", "title"], msg: "Value error, too long" },
      ],
    });
    const error = await failure(() => listingsApi.create({}));
    assert.equal(error.kind, "invalid");
    assert.equal(error.message, "estimated value: Input should be greater than 0; title: too long.");
    assert.equal(error.serviceDown, false);
  });

  test("422 without a detail list still gives a safe message", async () => {
    answer(422, { detail: "Those values were not accepted." });
    const error = await failure(() => listingsApi.create({}));
    assert.equal(error.message, "Some of the values are not valid. Please check the form.");
  });

  test("404 and 409 keep the service's own sentence", async () => {
    answer(404, { detail: "Swap not found." });
    assert.equal((await failure(() => swapsApi.decide(1, "accepted"))).kind, "not_found");
    answer(409, { detail: "This swap was already accepted or declined." });
    const conflict = await failure(() => swapsApi.decide(1, "accepted"));
    assert.equal(conflict.kind, "conflict");
    assert.equal(conflict.message, "This swap was already accepted or declined.");
  });

  test("a 500 never shows what the server said", async () => {
    answer(500, { detail: "Traceback (most recent call last): secret" });
    const error = await failure(() => listingsApi.list());
    assert.equal(error.kind, "server");
    assert.ok(!error.message.includes("Traceback"));
    assert.equal(error.serviceDown, true);
  });

  test("a stopped service is 'unreachable'", async () => {
    globalThis.fetch = async () => {
      throw new TypeError("fetch failed");
    };
    const error = await failure(() => listingsApi.list());
    assert.equal(error.kind, "unreachable");
    assert.equal(error.serviceDown, true);
  });

  test("a service that never answers times out instead of hanging", async () => {
    globalThis.fetch = (url, options) =>
      new Promise((resolve, reject) => {
        options.signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
      });
    const error = await failure(() => swapsApi.list());
    assert.equal(error.kind, "timeout");
    assert.equal(error.serviceDown, true);
  });
});
