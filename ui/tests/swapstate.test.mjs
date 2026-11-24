// The rule behind the "Mark as swapped" repair button on accepted swaps.

import assert from "node:assert/strict";
import { test } from "node:test";

import { listingsToFinish } from "../swapstate.js";

const swap = (status = "accepted") => ({
  status,
  updated_at: "2026-11-24T10:00:00Z",
  offered: { listing_id: 1 },
  requested: { listing_id: 2 },
});
const listing = (id, status, updated_at = "2026-11-20T09:00:00Z") => ({ id, status, updated_at });

test("an accepted swap with both listings still open needs both marked", () => {
  assert.deepEqual(listingsToFinish(swap(), [listing(1, "open"), listing(2, "open")]), [1, 2]);
});

test("only the listing that is still open is returned", () => {
  assert.deepEqual(listingsToFinish(swap(), [listing(1, "swapped"), listing(2, "open")]), [2]);
});

test("nothing to do when both listings are already swapped", () => {
  assert.deepEqual(listingsToFinish(swap(), [listing(1, "swapped"), listing(2, "swapped")]), []);
});

test("a proposed or declined swap never changes listings", () => {
  const open = [listing(1, "open"), listing(2, "open")];
  assert.deepEqual(listingsToFinish(swap("proposed"), open), []);
  assert.deepEqual(listingsToFinish(swap("declined"), open), []);
});

test("a listing reopened after the swap was decided is left alone", () => {
  const reopened = listing(1, "open", "2026-11-24T11:00:00Z");
  assert.deepEqual(listingsToFinish(swap(), [reopened, listing(2, "open")]), [2]);
});

test("a listing that was deleted is skipped", () => {
  assert.deepEqual(listingsToFinish(swap(), [listing(2, "open")]), [2]);
});
