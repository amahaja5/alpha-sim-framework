# Game Location Resolution

This workflow defines how the gateway determines where each game is located for weather and venue-aware signals.

## Goal

For each matchup in `league_id/year/week`, produce a resolved location payload:

- `home_team_id`
- `away_team_id`
- `venue_name`
- `city`
- `state`
- `lat`
- `lon`
- `is_dome`
- `timezone`

## Resolution Pipeline

1. Build weekly matchups from ESPN league context (`team.schedule` and current week index).
2. Identify the home team for each matchup:
   - from odds event mapping (`home_team`) when available
   - fallback to ESPN schedule ordering conventions in adapter context
3. Join home team to venue registry (`/v1/meta/mappings` venue section).
   - Seed template: `docs/gateway/nfl_venue_registry.template.json`
4. If coordinates are missing, geocode venue as one-time backfill and persist.
5. Emit `/v1/meta/game-locations` payload for weather feed queries.

## Data Sources

- Primary: ESPN league schedule for matchup structure.
- Primary: internal venue registry (`team_id -> venue metadata`).
- Secondary: odds provider event data (`home_team`, kickoff time) to disambiguate neutral-site edge cases.

## Edge Cases

- Neutral-site games (international or special events):
  - override venue mapping by `event_id` in registry.
- Venue changes during season:
  - store registry with `effective_from` and `effective_to` season/week metadata.
- Missing team mapping:
  - emit warning and skip weather enrichment for impacted game.

## Canonical `game-locations` Response

```json
{
  "data": {
    "games": [
      {
        "game_key": "2025-W06-TEAM1-TEAM2",
        "home_team_id": "1",
        "away_team_id": "2",
        "venue_name": "Example Stadium",
        "city": "Example City",
        "state": "EX",
        "lat": 39.9008,
        "lon": -75.1675,
        "is_dome": false,
        "timezone": "America/New_York"
      }
    ]
  },
  "source_timestamp": "2026-02-19T00:00:00+00:00",
  "quality_flags": ["resolved_from_registry"],
  "warnings": []
}
```

## Operational Requirement

The venue registry must be validated before each season and after known relocation/renovation events.
