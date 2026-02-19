# Gateway Go-Live Checklist

## Source Readiness

- [ ] Primary + backup candidate selected for each domain (`weather`, `market`, `odds`, `injury_news`).
- [ ] API keys configured for production and non-production environments.
- [ ] Rate-limit and quota budgets documented per source.

## Schema / Normalization

- [ ] Canonical schema validation passes for all domains.
- [ ] Unit conversion checks pass (wind mph, precip probability, spread, totals).
- [ ] `source_timestamp` UTC conversion validated.
- [ ] Game-location mapping returns venue coordinates for all weekly games.

## Reliability

- [ ] Timeout/retry policies configured and tested.
- [ ] Graceful degradation behavior verified when each feed fails independently.
- [ ] Primary-to-backup failover behavior verified.

## Quality Monitoring

- [ ] Alerts configured for:
  - [ ] success rate drops
  - [ ] schema conformity drops
  - [ ] stale data thresholds (`staleness_seconds`)
- [ ] Weekly scorecard report generated and reviewed.

## Compliance / Attribution

- [ ] Sleeper attribution requirement reviewed and surfaced where required.
- [ ] Third-party ToS usage constraints documented.
- [ ] PII/security review completed for stored payloads.

## Operational Runbooks

- [ ] Incident runbook for source outage.
- [ ] Mapping conflict runbook for player/team ID collisions.
- [ ] Season rollover checklist for venue and team mapping refresh.
