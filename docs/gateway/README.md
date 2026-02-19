# Gateway Discovery Docs

These docs describe endpoint discovery, contracts, and operating standards.
This repository does not implement a gateway server; runtime behavior here is
provider-client ingestion plus canonical contract validation/degradation.

- Endpoint catalog: `docs/gateway/GATEWAY_ENDPOINT_CATALOG.md`
- Game location resolution: `docs/gateway/GAME_LOCATION_RESOLUTION.md`
- Venue registry template: `docs/gateway/nfl_venue_registry.template.json`
- ID crosswalk spec: `docs/gateway/ID_CROSSWALK_SPEC.md`
- Probe scorecard template: `docs/gateway/GATEWAY_PROBE_SCORECARD_TEMPLATE.md`
- Go-live checklist: `docs/gateway/GO_LIVE_CHECKLIST.md`

Canonical JSON schemas:

- `docs/gateway/schemas/feed_envelope.schema.json`
- `docs/gateway/schemas/weather_feed.schema.json`
- `docs/gateway/schemas/market_feed.schema.json`
- `docs/gateway/schemas/odds_feed.schema.json`
- `docs/gateway/schemas/injury_news_feed.schema.json`
- `docs/gateway/schemas/nextgenstats_feed.schema.json`
