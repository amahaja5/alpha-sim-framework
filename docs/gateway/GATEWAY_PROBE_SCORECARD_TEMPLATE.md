# Gateway Endpoint Probe Scorecard (Template)

Generated: `<UTC timestamp>`

## Context

- league_id: `<league_id>`
- year: `<year>`
- week: `<week>`
- attempts per candidate: `<attempts>`
- timeout_seconds: `<timeout>`

## Promotions

- `weather`
  - primary: `<candidate>`
  - backup: `<candidate>`
- `market`
  - primary: `<candidate>`
  - backup: `<candidate>`
- `odds`
  - primary: `<candidate>`
  - backup: `<candidate>`
- `injury_news`
  - primary: `<candidate>`
  - backup: `<candidate>`

## Candidate Metrics

| Domain | Candidate | Success % | Schema % | Median Latency (ms) | Median Size (bytes) | Refresh Lag (s) | Score |
|---|---:|---:|---:|---:|---:|---:|---:|
| weather | openweather-current |  |  |  |  |  |  |
| weather | weatherapi-current |  |  |  |  |  |  |
| market | sleeper-players |  |  |  |  |  |  |
| market | sleeper-trending-add |  |  |  |  |  |  |
| odds | theoddsapi-nfl-odds |  |  |  |  |  |  |
| injury_news | sleeper-players-injury-status |  |  |  |  |  |  |

## Notes

- Record blocking issues (auth, quota, malformed payloads, stale updates).
- Record mapping gaps (missing `player_id` or `team_id` crosswalk entries).
- Record any game-location resolution misses for the test week.
