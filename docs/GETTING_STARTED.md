# Getting Started

## Prerequisites

- Python 3.9+
- `uv` installed
- ESPN league access details:
  - `league_id`
  - `team_id`
  - `swid` + `espn_s2` for private leagues

## Install

```bash
uv sync
```

## Minimal CLI Run

```bash
uv run fantasy-decision-maker --league-id <LEAGUE_ID> --team-id <TEAM_ID> --year <YEAR>
```

## Config File Workflow

1. Copy a template:

```bash
cp config.template.json config.json
```

2. Edit `config.json` with league/team/year and optional cookies.

3. Run with config:

```bash
uv run fantasy-decision-maker --config config.json
```

4. Optional report-only mode:

```bash
uv run fantasy-decision-maker --config config.json --report-only
```

## Build Persistent League Context

Build local context for last 3 seasons + current season:

```bash
uv run fantasy-decision-maker --config config.json --build-context --context-lookback-seasons 3
```

Force full refresh:

```bash
uv run fantasy-decision-maker --config config.json --build-context --context-full-refresh
```

Run historical backtest using local context first:

```bash
uv run fantasy-decision-maker --config config.json --historical-backtest --use-context
```

## Probe Gateway Endpoints (Non-Prod)

Use the endpoint probe runner to score candidate sources for weather/market/odds/injury domains:

```bash
uv run gateway-probe --config config.gateway_probe.template.json --output-dir reports/gateway_probe
```

See `docs/gateway/README.md` for schemas, endpoint catalog, game-location mapping, and go-live checklist.

## Private League Cookies

For private leagues, pass cookies either in `config.json` or via CLI flags:

```bash
uv run fantasy-decision-maker \
  --league-id <LEAGUE_ID> \
  --team-id <TEAM_ID> \
  --swid "{YOUR-SWID}" \
  --espn-s2 "YOUR-ESPN-S2"
```

## External API Object Reference

If you need a quick map of `League`, `Team`, `Player`, and related upstream objects from `espn_api`, see:

- [ESPN API Reference](ESPN_API_REFERENCE.md)

## Common Troubleshooting

- Team not found:
  - Re-check `team_id` against the team URL in your ESPN league.
- Authentication failures (401/403):
  - Refresh `swid`/`espn_s2` cookie values.
- First run is slower:
  - Initial model/cache setup takes longer; subsequent runs are faster.
- Missing required arguments:
  - Provide either `--config` or the required CLI fields (`--league-id`, `--team-id`).
