// Pure rules about accepted swaps, kept apart from the page so they can be tested.

// Accepting a swap is two steps the services cannot do for each other: the Swaps
// service records the decision, then the page marks both listings as swapped. If the
// tab closed or Listings was down in between, an accepted swap can have a listing
// that is still open. This returns the ids of the listings that still need marking.
//
// A listing that was changed after the swap was decided (for example reopened on
// purpose because the swap fell through) is left alone.
export function listingsToFinish(swap, listings) {
  if (swap.status !== "accepted") return [];
  const decidedAt = Date.parse(swap.updated_at);
  const ids = [];
  for (const item of [swap.offered, swap.requested]) {
    const listing = listings.find((candidate) => candidate.id === item.listing_id);
    if (!listing || listing.status !== "open") continue;
    if (Date.parse(listing.updated_at) > decidedAt) continue;
    ids.push(listing.id);
  }
  return ids;
}
