# Gateway Endpoint Catalog

This catalog is the source of truth for candidate endpoint discovery and promotion for gateway domains.

## Internal Gateway Routes (Canonical)

- `GET /v1/feeds/weather?league_id=&year=&week=`
- `GET /v1/feeds/market?league_id=&year=&week=`
- `GET /v1/feeds/odds?league_id=&year=&week=`
- `GET /v1/feeds/injury-news?league_id=&year=&week=`
- `GET /v1/feeds/nextgenstats?league_id=&year=&week=`
- `GET /v1/meta/mappings?league_id=&year=`
- `GET /v1/meta/game-locations?league_id=&year=&week=`

All canonical feed responses use:

- `data` (dict)
- `source_timestamp` (UTC ISO8601)
- `quality_flags` (list of strings)
- `warnings` (list of strings)

## Source Selection (Free-First)

| Domain | Primary Candidate | Backup Candidate | Rationale |
|---|---|---|---|
| `weather` | OpenWeather current weather | WeatherAPI current weather | Broad free-tier support; fallback for outages or quota exhaustion. |
| `odds` | The Odds API (`sports` + `odds`) | SportsDataIO/Sportradar (phase 2) | Free/low-cost coverage first; paid SLA backup as upgrade path. |
| `market` | Sleeper players + trending add/drop | FantasyPros projections/rankings (phase 2) | Free coverage for trend/sentiment proxies. |
| `injury_news` | Sleeper player injury statuses + ESPN roster statuses | FantasyPros injury news endpoint | Free-first injury availability with optional richer paid news. |
| `nextgenstats` | Gateway-managed NGS proxy feed | SportsDataIO advanced stats (paid) | NGS-style usage/efficiency metrics are often not openly accessible as a stable public API. |
| `league_context` | ESPN via existing `espn_api` | Sleeper leagues (optional) | ESPN remains the simulation base context. |

## External Candidate Endpoints

### Weather

- OpenWeather current weather
  - `GET https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=imperial&appid={key}`
- WeatherAPI current weather
  - `GET https://api.weatherapi.com/v1/current.json?key={key}&q={lat},{lon}`

### Odds

- The Odds API sports catalog
  - `GET https://api.the-odds-api.com/v4/sports?apiKey={key}`
- The Odds API NFL odds
  - `GET https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?apiKey={key}&regions=us&markets=h2h,spreads,totals`
- The Odds API event odds
  - `GET https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/{eventId}/odds?apiKey={key}&regions=us&markets=spreads,totals`
- Extended signal keys expected in canonical odds payload:
  - `player_props_by_player[player_id] = {line_open, line_current, sharp_over_pct}`
  - `win_probability_by_team[team_id]`
  - `live_game_state_by_team[team_id] = {quarter, time_remaining_sec, score_differential}`
  - `opening_spread_by_team[team_id]`
  - `closing_spread_by_team[team_id]`

### Market Sentiment

- Sleeper players
  - `GET https://api.sleeper.app/v1/players/nfl`
- Sleeper trending adds
  - `GET https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours={h}&limit={n}`
- Sleeper trending drops
  - `GET https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours={h}&limit={n}`
- Extended signal key expected in canonical market payload:
  - `ownership_by_player[player_id]` (0-1 ownership estimate)

### Injury / News

- Sleeper players payload (`injury_status` fields)
  - `GET https://api.sleeper.app/v1/players/nfl`
- ESPN roster/player statuses through existing league object
- FantasyPros injury news (upgrade)
  - `GET https://api.fantasypros.com/v2/{format}/nfl/news?category=injury`
- Extended signal key expected in canonical injury payload:
  - `backup_projection_ratio_by_player[player_id]` (0-1)

### Next Gen Stats (Usage / Efficiency / Volatility Enrichment)

- Gateway proxy endpoint (recommended)
  - `GET /v1/feeds/nextgenstats?league_id=&year=&week=`
- Paid upgrade option (advanced metrics provider)
  - Example: SportsDataIO advanced player metrics endpoints (licensed)
- Extended signal keys expected in canonical nextgen payload:
  - `player_metrics[player_id].red_zone_touch_share`
  - `player_metrics[player_id].red_zone_touch_trend`
  - `player_metrics[player_id].snap_share`
  - `player_metrics[player_id].snap_share_trend`

## Probe Workflow

- Probe config template: `config.gateway_probe.template.json`
- Probe runner: `scripts/run_gateway_probe.py`
- Output scorecards:
  - `reports/gateway_probe/gateway_probe_scorecard.json`
  - `reports/gateway_probe/gateway_probe_scorecard.md`

## Source Links

- [OpenWeather Current Weather API](https://openweathermap.org/current)
- [WeatherAPI Docs](https://www.weatherapi.com/docs/)
- [The Odds API v4 Docs](https://the-odds-api.com/liveapi/guides/v4/)
- [Sleeper API Docs](https://docs.sleeper.com/)
- [FantasyPros API Docs](https://api.fantasypros.com/v2/docs)
- [espn-api](https://github.com/cwendt94/espn-api)
