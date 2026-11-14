# Product registry updates

The hourly workflow (minute 23 UTC; GitHub scheduling is best-effort) checks
only commits affecting `LIFX/products`'s `master:products.json`. Manual dispatch
is also supported. Conditional requests reuse the ETag in products-source.json.
The catalogue is downloaded at an immutable revision, passed to our existing
generator, formatted, linted, type-checked and tested before opening a PR.

The source marker is committed alongside generated files and acknowledged on
merge. One `automation/update-products` branch is reused. Failed checks do not
acknowledge an update. Closing without merging may result in another proposal.
Even upstream changes that do not affect generated output get a marker-only PR.
Polling coalesces intermediate edits; it does not promise delivery of every edit.

Required secrets: GADLING_APP_CLIENT_ID and GADLING_APP_PRIVATE_KEY. The App
installation requires Contents and Pull requests read/write on this repository.
Its repository-scoped token is minted only after validation. Signed, signed-off
bot commits trigger normal PR CI; no auto-merge is configured. The monitor's
offline tests run on relevant PRs and before scheduled/manual checks.

The registry header records the same pinned upstream revision as the marker.
