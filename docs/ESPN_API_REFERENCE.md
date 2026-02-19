# ESPN API Reference (External Dependency)

This document summarizes common NFL fantasy football objects exposed by the external `espn_api` package under `espn_api.football`.
Use this as an integration reference for `alpha_sim_framework` inputs.

## Quick Start

```python
from espn_api.football import League

league = League(
    league_id=123456,
    year=2025,
    espn_s2="optional_cookie_for_private_leagues",
    swid="optional_swid_for_private_leagues",
)
```

Core exports (from `espn_api.football`):

- `League`
- `Team`
- `Matchup`
- `Player`
- `BoxPlayer`

## Object Model Overview

- `League` contains:
  - league metadata/state (`current_week`, `nfl_week`, `settings`, etc.)
  - `teams: List[Team]`
  - helpers for matchups, box scores, free agents, player lookups, and transactions
- `Team` contains:
  - season-level team stats and standings values
  - `roster: List[Player]`
  - schedule and weekly outcomes/scores
- `Player` contains:
  - identity, position/slot eligibility, injury/ownership status
  - `stats` by scoring period (actual + projected)
- `BoxPlayer` extends `Player` with matchup-week fields:
  - lineup slot, opponent context, week points/projections, game progress
- `Matchup` contains scoreboard pairing for one week (`home_team`, `away_team`, scores)
- `BoxScore` contains richer weekly matchup data with full lineups (`home_lineup`, `away_lineup`)
- `Activity` contains recent league activity messages parsed into actions (team/action/player/bid)
- `Transaction` / `TransactionItem` contain processed transaction records
- `Settings` contains league configuration (teams, playoffs, tie rules, scoring format, roster slot counts)

## `League` Reference

Source module: `espn_api.football.league`

### Constructor

```python
League(league_id: int, year: int, espn_s2=None, swid=None, fetch_league=True, debug=False)
```

### Frequently Used Attributes

- `league_id: int`
- `year: int`
- `teams: List[Team]`
- `settings: Settings`
- `current_week: int`
- `currentMatchupPeriod: int`
- `scoringPeriodId: int`
- `nfl_week: int` (latest ESPN scoring period)
- `player_map: Dict` (player id/name mapping)
- `draft: List[BasePick]`

### Common Methods

- `fetch_league() -> None`
  - refreshes league, players, teams, and draft data
- `refresh() -> None`
  - refreshes current league/team data
- `standings() -> List[Team]`
  - default standings order
- `standings_weekly(week: int) -> List[Team]`
  - recomputes standings through a given week with tie-breaker logic
- `scoreboard(week: int = None) -> List[Matchup]`
  - lightweight weekly matchup scores
- `box_scores(week: int = None) -> List[BoxScore]`
  - full matchup + lineup data (NFL seasons 2019+ only)
- `free_agents(week: int = None, size: int = 50, position: str = None, position_id: int = None) -> List[Player]`
  - free agents/waivers for a week (2019+ only)
- `player_info(name: str = None, playerId: int | list = None) -> Player | List[Player] | None`
  - player card lookup
- `recent_activity(size: int = 25, msg_type: str = None, offset: int = 0) -> List[Activity]`
  - activity feed (2019+ only)
- `transactions(scoring_period: int = None, types: Set[str] = {"FREEAGENT","WAIVER","WAIVER_ERROR"}) -> List[Transaction]`
  - transaction records filtered by type
- `message_board(msg_types: List[str] = None) -> List[dict]`
  - raw league message topics

### Utility Ranking Methods

- `top_scorer()`, `least_scorer()`, `most_points_against()`
- `top_scored_week()`, `least_scored_week()`
- `power_rankings(week: int = None)`

## `Team` Reference

Source module: `espn_api.football.team`

### Key Attributes

- identity:
  - `team_id`, `team_abbrev`, `team_name`, `logo_url`
- divisional/standing:
  - `division_id`, `division_name`, `standing`, `final_standing`
- record:
  - `wins`, `losses`, `ties`, `streak_length`, `streak_type`
- scoring:
  - `points_for`, `points_against`
- transactions:
  - `acquisitions`, `acquisition_budget_spent`, `drops`, `trades`, `move_to_ir`
- projection/meta:
  - `playoff_pct`, `draft_projected_rank`, `waiver_rank`
- containers:
  - `roster: List[Player]`
  - `schedule: List[Team]` (after league hydration)
  - `scores: List[float]`
  - `outcomes: List[str]` (`W`, `L`, `T`, `U`)
  - `mov: List[float]` (margin of victory by week)
  - `owners: List[dict]`
  - `stats: Dict[str, Any]` (mapped from ESPN stat ids)

### Helper Method

- `get_player_name(playerId: int) -> str`

## `Player` Reference

Source module: `espn_api.football.player`

### Key Attributes

- identity:
  - `name`, `playerId`, `jersey`, `proTeam`
- positional:
  - `position`, `posRank`, `eligibleSlots`, `lineupSlot`
- ownership/injury:
  - `onTeamId`, `acquisitionType`, `injuryStatus`, `injured`, `percent_owned`, `percent_started`
- availability:
  - `active_status` (`active`, `inactive`, `bye`)
- aggregated scoring:
  - `total_points`, `projected_total_points`, `avg_points`, `projected_avg_points`
- schedule:
  - `schedule[week] = {"team": opponent_abbrev, "date": datetime}` (when pro schedule passed)
- detailed stats:
  - `stats[scoring_period]` with keys including:
    - `points`, `avg_points`
    - `projected_points`, `projected_avg_points`
    - `breakdown`, `projected_breakdown`
    - `points_breakdown`, `projected_points_breakdown`

## `BoxPlayer` Reference

Source module: `espn_api.football.box_player`

`BoxPlayer` inherits `Player` and adds matchup-specific context:

- `slot_position` (lineup slot for that week)
- `pro_opponent` (NFL opponent abbreviation)
- `pro_pos_rank` (opponent rank vs player position, if available)
- `game_date`
- `game_played` (0 or 100 currently)
- `on_bye_week`
- week-scoped values:
  - `points`, `breakdown`, `points_breakdown`
  - `projected_points`, `projected_breakdown`, `projected_points_breakdown`

## `Matchup` Reference

Source module: `espn_api.football.matchup`

### Key Attributes

- `matchup_type` (e.g. playoff tier type or `NONE`)
- `is_playoff: bool`
- `_home_team_id`, `_away_team_id`
- `home_score`, `away_score`
- hydrated by `League.scoreboard(...)`:
  - `home_team: Team`
  - `away_team: Team` (may be absent on bye)

## `BoxScore` Reference

Source module: `espn_api.football.box_score`

### Key Attributes

- `matchup_type`, `is_playoff`
- `home_team`, `away_team` (team id initially, then hydrated to `Team`)
- `home_score`, `away_score`
- `home_projected`, `away_projected`
- `home_lineup: List[BoxPlayer]`
- `away_lineup: List[BoxPlayer]`

## `Activity` Reference

Source module: `espn_api.football.activity`

- `date`
- `actions: List[Tuple[Team, str, Player, int]]`
  - tuple values are `(team, action, player, bid_amount)`
  - action is mapped from ESPN `messageTypeId` (examples: `FA ADDED`, `WAIVER ADDED`, `DROPPED`, `TRADED`)

## `Transaction` Reference

Source module: `espn_api.football.transaction`

### `Transaction`

- `team: Team`
- `type`
- `status`
- `scoring_period`
- `date` (`processDate` or fallback `proposedDate`)
- `bid_amount`
- `items: List[TransactionItem]`

### `TransactionItem`

- `type`
- `player: Player | str` (from league `player_map`)

## `Settings` Reference

Source modules:

- `espn_api.base_settings`
- `espn_api.football.settings`

### Key Attributes

- season/league:
  - `name`, `team_count`, `reg_season_count`, `playoff_team_count`
  - `firstScoringPeriod`/`finalScoringPeriod` are stored on `League` (not `Settings`)
- rules:
  - `tie_rule`, `playoff_tie_rule`, `playoff_seed_tie_rule`
  - `playoff_matchup_period_length`
  - `matchup_periods`, `division_map`
- transactions:
  - `faab`, `acquisition_budget`, `veto_votes_required`, `trade_deadline`
- scoring:
  - `scoring_type`
  - `scoring_format: List[dict]` (`id`, `abbr`, `label`, `points`)
- roster:
  - `position_slot_counts: Dict[str, int]`

## Useful Constants

Source module: `espn_api.football.constant`

- `POSITION_MAP`: ESPN slot id <-> human label mapping (`QB`, `RB`, `WR`, `TE`, `D/ST`, `K`, `BE`, `IR`, etc.)
- `PRO_TEAM_MAP`: ESPN pro team id -> NFL team abbreviation
- `PLAYER_STATS_MAP`: ESPN stat id -> semantic stat name
- `ACTIVITY_MAP`: ESPN activity message ids <-> action labels

## Common Caveats

- Some endpoints are gated by year:
  - `box_scores`, `free_agents`, `recent_activity` raise for seasons before 2019.
- `League.player_map` is mixed:
  - id -> name and (first-seen) name -> id; duplicate player names can collide.
- `box_scores` and `scoreboard` return team ids first, then hydrate to `Team` objects.
- `TransactionItem.player` is sourced from `player_map`, so it may be a name string, not a full `Player` object.
