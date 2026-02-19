# ID Crosswalk Spec

This document defines canonical IDs and source mappings for gateway normalization.

## Canonical Keys

- `player_id`: ESPN `playerId` string
- `team_id`: ESPN `team_id` string

## Crosswalk Table Shape

Crosswalk objects returned by `GET /v1/meta/mappings?league_id=&year=`:

```json
{
  "data": {
    "players": {
      "ESPN_PLAYER_ID": {
        "espn_player_id": "ESPN_PLAYER_ID",
        "sleeper_player_id": "SLEEPER_PLAYER_ID",
        "odds_player_ref": "OPTIONAL_VENDOR_PLAYER_REF"
      }
    },
    "teams": {
      "ESPN_TEAM_ID": {
        "espn_team_id": "ESPN_TEAM_ID",
        "espn_team_name": "Team Name",
        "sleeper_team_ref": "OPTIONAL",
        "odds_team_name": "OPTIONAL"
      }
    },
    "venues": {
      "ESPN_TEAM_ID": {
        "venue_name": "Stadium Name",
        "city": "City",
        "state": "ST",
        "lat": 0.0,
        "lon": 0.0,
        "is_dome": false,
        "timezone": "America/New_York"
      }
    }
  },
  "source_timestamp": "2026-02-19T00:00:00+00:00",
  "quality_flags": [],
  "warnings": []
}
```

## Mapping Rules

1. Prefer exact key matches by source-native ID.
2. If source ID missing, use normalized name match fallback.
3. Record confidence level per mapping (exact, fuzzy, manual_override).
4. Never silently remap collisions; emit warning and require manual override.

## Required Validation

- Player map uniqueness across all source IDs.
- Team map uniqueness and no duplicate canonical keys.
- Venue entries present for every active ESPN team in league context.

## Versioning

- Store `schema_version` in mapping payload.
- Increment minor when adding optional fields.
- Increment major when changing canonical key semantics.
