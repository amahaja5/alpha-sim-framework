import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..alpha_types import (
    CompositeAlphaConfig,
    ExternalFeedConfig,
    ProviderRuntimeConfig,
    SignalCaps,
    SignalWeights,
)
from .feeds import InjuryNewsFeedClient, MarketFeedClient, OddsFeedClient, WeatherFeedClient


HEALTHY_STATUSES = {"NONE", "ACTIVE", ""}
OUTLIKE_STATUSES = {"OUT", "DOUBTFUL", "IR", "SUSPENSION"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _as_dict(value: Any) -> Dict[Any, Any]:
    return value if isinstance(value, dict) else {}


def _cap(value: float, bounds: Tuple[float, float]) -> float:
    low, high = bounds
    return float(np.clip(_safe_float(value), _safe_float(low), _safe_float(high)))


def _player_id(player: Any) -> Any:
    return getattr(player, "playerId", getattr(player, "name", id(player)))


def _normalize_status(status: Any) -> str:
    return str(status or "NONE").strip().upper()


def _lookup(mapping: Dict[Any, Any], key: Any, default: Any = None) -> Any:
    if key in mapping:
        return mapping[key]

    key_str = str(key)
    if key_str in mapping:
        return mapping[key_str]

    try:
        key_int = int(key)
    except Exception:
        key_int = None

    if key_int is not None:
        if key_int in mapping:
            return mapping[key_int]
        if str(key_int) in mapping:
            return mapping[str(key_int)]

    return default


def _coerce_dataclass(instance: Any, values: Dict[str, Any]) -> Any:
    if not isinstance(values, dict):
        return instance

    for key, value in values.items():
        if not hasattr(instance, key):
            continue

        current = getattr(instance, key)
        if is_dataclass(current) and isinstance(value, dict):
            _coerce_dataclass(current, value)
            continue

        if isinstance(current, tuple) and isinstance(value, (list, tuple)) and len(value) == 2:
            setattr(instance, key, (_safe_float(value[0]), _safe_float(value[1])))
            continue

        setattr(instance, key, value)

    return instance


def _to_composite_config(config: Optional[Any], kwargs: Optional[Dict[str, Any]] = None) -> CompositeAlphaConfig:
    if isinstance(config, CompositeAlphaConfig):
        payload = copy.deepcopy(config)
        return _coerce_dataclass(payload, kwargs or {})

    payload = CompositeAlphaConfig()
    if isinstance(config, dict):
        _coerce_dataclass(payload, config)
    _coerce_dataclass(payload, kwargs or {})
    return payload


def _player_recent_points(player: Any, week: int) -> List[float]:
    stats = _as_dict(getattr(player, "stats", {}))
    points = []
    for stat_week, entry in stats.items():
        entry = _as_dict(entry)
        if "points" not in entry:
            continue
        try:
            week_id = int(stat_week)
        except Exception:
            continue
        if week_id <= 0 or week_id > int(week):
            continue
        points.append((week_id, _safe_float(entry.get("points"))))

    points.sort(key=lambda item: item[0], reverse=True)
    return [value for _, value in points]


def _player_baseline(player: Any, reg_games: int) -> float:
    projected_avg = _safe_float(getattr(player, "projected_avg_points", 0.0), 0.0)
    if projected_avg > 0:
        return projected_avg

    projected_total = _safe_float(getattr(player, "projected_total_points", 0.0), 0.0)
    if projected_total > 0:
        return projected_total / max(1.0, float(reg_games))

    return _safe_float(getattr(player, "avg_points", 0.0), 0.0)


def _position(player: Any) -> str:
    return str(getattr(player, "position", "") or "").upper()


def _team_id(team_ref: Any) -> Optional[int]:
    try:
        return int(getattr(team_ref, "team_id", team_ref))
    except Exception:
        return None


class CompositeSignalProvider:
    """Online composite alpha provider with graceful degradation and signal diagnostics."""

    def __init__(self, config: Optional[Any] = None, **kwargs: Any):
        self.config = _to_composite_config(config, kwargs=kwargs)
        self._feeds = {
            "weather": WeatherFeedClient(self.config.external_feeds, self.config.runtime),
            "market": MarketFeedClient(self.config.external_feeds, self.config.runtime),
            "odds": OddsFeedClient(self.config.external_feeds, self.config.runtime),
            "injury_news": InjuryNewsFeedClient(self.config.external_feeds, self.config.runtime),
        }

        self._feed_cache: Dict[Tuple[str, int, int, int], Dict[str, Any]] = {}
        self._feed_cache_ts: Dict[Tuple[str, int, int, int], float] = {}
        self._week_cache: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        self._week_cache_ts: Dict[Tuple[int, int, int], float] = {}

        self._last_diagnostics: Dict[Any, Dict[str, Any]] = {}
        self._last_warnings: List[str] = []

    @property
    def last_diagnostics(self) -> Dict[Any, Dict[str, Any]]:
        return copy.deepcopy(self._last_diagnostics)

    @property
    def last_warnings(self) -> List[str]:
        return list(self._last_warnings)

    def get_player_adjustments(self, league: Any, week: int) -> Dict[Any, float]:
        payload = self._get_week_payload(league, week)
        return dict(payload["player_adjustments"])

    def get_injury_overrides(self, league: Any, week: int) -> Dict[Any, str]:
        payload = self._get_week_payload(league, week)
        return dict(payload["injury_overrides"])

    def get_matchup_overrides(self, league: Any, week: int) -> Dict[Any, float]:
        payload = self._get_week_payload(league, week)
        return dict(payload["matchup_overrides"])

    def _get_week_payload(self, league: Any, week: int) -> Dict[str, Any]:
        key = (
            int(getattr(league, "league_id", 0) or 0),
            int(getattr(league, "year", 0) or 0),
            int(week),
        )
        ttl = max(0, int(getattr(self.config.runtime, "cache_ttl_seconds", 300)))

        if key in self._week_cache and ttl > 0:
            age = time.time() - self._week_cache_ts.get(key, 0.0)
            if age <= ttl:
                cached = self._week_cache[key]
                self._last_diagnostics = copy.deepcopy(cached.get("diagnostics", {}))
                self._last_warnings = list(cached.get("warnings", []))
                return copy.deepcopy(cached)

        payload = self._build_week_payload(league, int(week))
        self._week_cache[key] = copy.deepcopy(payload)
        self._week_cache_ts[key] = time.time()

        self._last_diagnostics = copy.deepcopy(payload.get("diagnostics", {}))
        self._last_warnings = list(payload.get("warnings", []))
        return payload

    def _fetch_feed(self, feed_name: str, league: Any, week: int) -> Dict[str, Any]:
        key = (
            feed_name,
            int(getattr(league, "league_id", 0) or 0),
            int(getattr(league, "year", 0) or 0),
            int(week),
        )
        ttl = max(0, int(getattr(self.config.runtime, "cache_ttl_seconds", 300)))

        if key in self._feed_cache and ttl > 0:
            age = time.time() - self._feed_cache_ts.get(key, 0.0)
            if age <= ttl:
                return copy.deepcopy(self._feed_cache[key])

        client = self._feeds[feed_name]
        payload = client.fetch(league, week)
        if not isinstance(payload, dict):
            payload = {
                "data": {},
                "quality_flags": ["invalid_payload"],
                "warnings": [f"{feed_name}_payload_invalid"],
                "source_timestamp": "",
            }

        self._feed_cache[key] = copy.deepcopy(payload)
        self._feed_cache_ts[key] = time.time()
        return payload

    def _fetch_all_feeds(self, league: Any, week: int) -> Tuple[Dict[str, Any], List[str]]:
        payloads: Dict[str, Any] = {}
        warnings: List[str] = []

        with ThreadPoolExecutor(max_workers=len(self._feeds)) as pool:
            future_map = {
                pool.submit(self._fetch_feed, feed_name, league, week): feed_name
                for feed_name in self._feeds
            }
            for future in as_completed(future_map):
                feed_name = future_map[future]
                try:
                    payload = future.result()
                except Exception as exc:
                    if not bool(getattr(self.config.runtime, "degrade_gracefully", True)):
                        raise RuntimeError(f"{feed_name}_fetch_failed: {exc}") from exc
                    payload = {
                        "data": {},
                        "quality_flags": ["fetch_failed"],
                        "warnings": [f"{feed_name}_fetch_failed: {exc}"],
                        "source_timestamp": "",
                    }
                payloads[feed_name] = payload
                warnings.extend(_as_dict(payload).get("warnings", []))

        return payloads, warnings

    def _build_week_payload(self, league: Any, week: int) -> Dict[str, Any]:
        teams = list(getattr(league, "teams", []) or [])
        reg_games = max(1, int(getattr(getattr(league, "settings", None), "reg_season_count", 14) or 14))

        weights = asdict(self.config.weights)
        positive_weights = {name: max(0.0, _safe_float(value, 0.0)) for name, value in weights.items()}
        weight_sum = sum(positive_weights.values())
        if weight_sum <= 0:
            equal = 1.0 / max(1, len(positive_weights))
            positive_weights = {name: equal for name in positive_weights}
        else:
            positive_weights = {name: value / weight_sum for name, value in positive_weights.items()}

        caps: SignalCaps = self.config.caps
        cap_map = {
            "projection_residual": caps.projection_residual,
            "usage_trend": caps.usage_trend,
            "injury_opportunity": caps.injury_opportunity,
            "matchup_unit": caps.matchup_unit,
            "game_script": caps.game_script,
            "volatility_aware": caps.volatility_aware,
            "weather_venue": caps.weather_venue,
            "market_sentiment_contrarian": caps.market_sentiment_contrarian,
            "waiver_replacement_value": caps.waiver_replacement_value,
            "short_term_schedule_cluster": caps.short_term_schedule_cluster,
        }

        feeds, feed_warnings = self._fetch_all_feeds(league, week)
        weather_data = _as_dict(_as_dict(feeds.get("weather", {})).get("data", {}))
        market_data = _as_dict(_as_dict(feeds.get("market", {})).get("data", {}))
        odds_data = _as_dict(_as_dict(feeds.get("odds", {})).get("data", {}))
        injury_data = _as_dict(_as_dict(feeds.get("injury_news", {})).get("data", {}))

        market_projections = _as_dict(market_data.get("projections", {}))
        usage_trend_map = _as_dict(market_data.get("usage_trend", {}))
        sentiment_map = _as_dict(market_data.get("sentiment", {}))
        market_schedule = _as_dict(market_data.get("future_schedule_strength", {}))

        defense_vs_position = _as_dict(odds_data.get("defense_vs_position", {}))
        spread_by_team = _as_dict(odds_data.get("spread_by_team", {}))
        implied_total_by_team = _as_dict(odds_data.get("implied_total_by_team", {}))
        odds_schedule = _as_dict(odds_data.get("schedule_strength_by_team", {}))

        team_weather = _as_dict(weather_data.get("team_weather", {}))
        injury_status_map = _as_dict(injury_data.get("injury_status", {}))
        team_injuries_by_position = _as_dict(injury_data.get("team_injuries_by_position", {}))

        team_map = {_team_id(team): team for team in teams if _team_id(team) is not None}

        players_by_team: Dict[int, List[Any]] = {}
        for team in teams:
            team_id = _team_id(team)
            if team_id is None:
                continue
            players_by_team[team_id] = list(getattr(team, "roster", []) or [])

        position_values: Dict[str, List[float]] = {}
        team_starters: Dict[int, Dict[str, float]] = {}
        roster_status: Dict[Any, str] = {}
        injury_overrides: Dict[Any, str] = {}

        for team_id, roster in players_by_team.items():
            starter_map: Dict[str, float] = {}
            for player in roster:
                pid = _player_id(player)
                pos = _position(player)
                baseline = _player_baseline(player, reg_games)
                if pos:
                    position_values.setdefault(pos, []).append(baseline)
                    starter_map[pos] = max(starter_map.get(pos, 0.0), baseline)

                external_status = _lookup(injury_status_map, pid)
                if external_status is None:
                    external_status = getattr(player, "injuryStatus", "NONE")
                status = _normalize_status(external_status)
                roster_status[pid] = status
                if status not in HEALTHY_STATUSES:
                    injury_overrides[pid] = status

            team_starters[team_id] = starter_map

        replacement_by_position = {}
        for pos, values in position_values.items():
            if not values:
                replacement_by_position[pos] = 0.0
            else:
                replacement_by_position[pos] = float(np.percentile(np.array(values, dtype=float), 35))

        injured_counts: Dict[int, Dict[str, int]] = {}
        for team_id, roster in players_by_team.items():
            counts = {}
            external_team_counts = _as_dict(_lookup(team_injuries_by_position, team_id, {}))
            for pos, value in external_team_counts.items():
                counts[str(pos).upper()] = max(0, int(_safe_float(value, 0.0)))

            for player in roster:
                pid = _player_id(player)
                pos = _position(player)
                status = roster_status.get(pid, "NONE")
                if status in OUTLIKE_STATUSES:
                    counts[pos] = counts.get(pos, 0) + 1
            injured_counts[team_id] = counts

        player_adjustments: Dict[Any, float] = {}
        matchup_overrides: Dict[Any, float] = {}
        diagnostics: Dict[Any, Dict[str, Any]] = {}

        total_players = 0
        non_zero_adjustments = 0

        for team_id, roster in players_by_team.items():
            for player in roster:
                total_players += 1
                pid = _player_id(player)
                pos = _position(player)
                baseline = _player_baseline(player, reg_games)
                recent_points = _player_recent_points(player, week)
                recent_window = recent_points[:3]
                older_window = recent_points[3:6]
                recent_avg = float(np.mean(recent_window)) if recent_window else baseline
                older_avg = float(np.mean(older_window)) if older_window else baseline
                volatility = float(np.std(np.array(recent_points[:6], dtype=float), ddof=1)) if len(recent_points) >= 2 else max(2.0, baseline * 0.2)

                status = roster_status.get(pid, "NONE")
                opponent_id = None
                team_obj = team_map.get(team_id)
                if team_obj is not None:
                    schedule = list(getattr(team_obj, "schedule", []) or [])
                    if 0 < week <= len(schedule):
                        opponent_id = _team_id(schedule[week - 1])

                external_projection = _lookup(market_projections, pid)
                residual = 0.0
                if external_projection is not None:
                    residual = _safe_float(external_projection, baseline) - baseline
                projection_residual = self.config.residual_scale * residual

                usage_value = _lookup(usage_trend_map, pid)
                if usage_value is None:
                    usage_value = recent_avg - older_avg
                usage_scale = {
                    "RB": 1.15,
                    "WR": 1.10,
                    "TE": 0.90,
                    "QB": 0.85,
                    "K": 0.40,
                    "D/ST": 0.40,
                }.get(pos, 1.0)
                usage_trend = self.config.usage_scale * _safe_float(usage_value, 0.0) * usage_scale

                injury_component = {
                    "OUT": -3.0,
                    "IR": -3.0,
                    "DOUBTFUL": -1.8,
                    "QUESTIONABLE": -0.8,
                    "P": -0.4,
                    "SUSPENSION": -2.5,
                }.get(status, 0.0)
                teammate_out = max(0, injured_counts.get(team_id, {}).get(pos, 0))
                if status in OUTLIKE_STATUSES:
                    teammate_out = max(0, teammate_out - 1)
                if status in HEALTHY_STATUSES and teammate_out > 0:
                    injury_component += 0.8 * teammate_out

                dvp_map = _as_dict(_lookup(defense_vs_position, opponent_id, {}))
                dvp = _safe_float(_lookup(dvp_map, pos, 0.0), 0.0)
                matchup_unit = 0.2 * dvp
                matchup_signal_multiplier = _cap(1.0 + (0.025 * dvp), caps.matchup_signal_multiplier)

                spread = _safe_float(_lookup(spread_by_team, team_id, 0.0), 0.0)
                implied_total = _safe_float(_lookup(implied_total_by_team, team_id, 22.0), 22.0)
                favorite = spread < 0
                if pos in {"QB", "WR", "TE"}:
                    script_base = -0.30 if favorite else 0.35
                elif pos == "RB":
                    script_base = 0.40 if favorite else -0.25
                else:
                    script_base = 0.05
                game_script = script_base + (0.08 * ((implied_total - 22.0) / 3.0))

                volatility_aware = (-0.08 * volatility) + (0.25 if volatility < 4.0 else 0.0)

                weather_info = _as_dict(_lookup(team_weather, team_id, {}))
                is_dome = bool(weather_info.get("is_dome", False))
                wind_mph = _safe_float(weather_info.get("wind_mph", 0.0), 0.0)
                precip_prob = _safe_float(weather_info.get("precip_prob", 0.0), 0.0)
                weather_venue = 0.0
                if is_dome:
                    weather_venue += 0.15 if pos in {"QB", "WR", "TE"} else 0.05
                else:
                    if wind_mph >= 15:
                        weather_venue -= 0.5 if pos in {"QB", "WR", "TE", "K"} else 0.1
                    if wind_mph >= 22:
                        weather_venue -= 0.4 if pos in {"QB", "WR", "TE", "K"} else 0.1
                    if precip_prob >= 0.4:
                        weather_venue -= 0.4 if pos in {"QB", "WR", "TE", "K"} else 0.05

                sentiment_payload = _lookup(sentiment_map, pid, 0.0)
                if isinstance(sentiment_payload, dict):
                    sentiment_score = _safe_float(sentiment_payload.get("score", 0.0), 0.0)
                    start_delta = _safe_float(sentiment_payload.get("start_delta", 0.0), 0.0)
                else:
                    sentiment_score = _safe_float(sentiment_payload, 0.0)
                    start_delta = 0.0
                started_pct = _safe_float(getattr(player, "percent_started", 50.0), 50.0)
                market_sentiment_contrarian = -0.5 * sentiment_score
                if started_pct >= 75 and residual < 0:
                    market_sentiment_contrarian -= min(1.0, abs(residual) * 0.12)
                if started_pct <= 40 and residual > 0:
                    market_sentiment_contrarian += min(1.0, residual * 0.12)
                market_sentiment_contrarian -= 0.10 * start_delta

                replacement_value = _safe_float(_lookup(replacement_by_position, pos, baseline), baseline)
                starter_value = _safe_float(_lookup(team_starters.get(team_id, {}), pos, replacement_value), replacement_value)
                waiver_replacement_value = (0.03 * (baseline - replacement_value)) + (0.08 * (baseline - starter_value))

                schedule_data = _lookup(odds_schedule, team_id)
                if schedule_data is None:
                    schedule_data = _lookup(market_schedule, team_id)
                if isinstance(schedule_data, list):
                    horizon = max(1, int(self.config.schedule_horizon_weeks))
                    selected = [_safe_float(item, 0.0) for item in schedule_data[:horizon]]
                    schedule_strength = float(np.mean(selected)) if selected else 0.0
                else:
                    schedule_strength = _safe_float(schedule_data, 0.0)
                short_term_schedule_cluster = (0.25 * schedule_strength) + (0.05 * dvp)

                raw_signals = {
                    "projection_residual": projection_residual,
                    "usage_trend": usage_trend,
                    "injury_opportunity": injury_component,
                    "matchup_unit": matchup_unit,
                    "game_script": game_script,
                    "volatility_aware": volatility_aware,
                    "weather_venue": weather_venue,
                    "market_sentiment_contrarian": market_sentiment_contrarian,
                    "waiver_replacement_value": waiver_replacement_value,
                    "short_term_schedule_cluster": short_term_schedule_cluster,
                }

                clipped_signals = {
                    name: _cap(value, cap_map[name])
                    for name, value in raw_signals.items()
                }

                weighted_signals = {
                    name: clipped_signals[name] * positive_weights.get(name, 0.0)
                    for name in clipped_signals
                }

                weighted_sum = float(sum(weighted_signals.values()))
                final_adjustment = _cap(weighted_sum, caps.total_adjustment)
                if abs(final_adjustment) > 1e-9:
                    non_zero_adjustments += 1

                matchup_multiplier = matchup_signal_multiplier * (1.0 + (0.01 * clipped_signals["short_term_schedule_cluster"]))
                matchup_multiplier *= 1.0 + np.clip((clipped_signals["weather_venue"] * 0.02), -0.03, 0.03)
                matchup_multiplier = _cap(matchup_multiplier, caps.matchup_multiplier)

                player_adjustments[pid] = float(final_adjustment)
                matchup_overrides[pid] = float(matchup_multiplier)

                diagnostics[pid] = {
                    "player": getattr(player, "name", str(pid)),
                    "team_id": team_id,
                    "position": pos,
                    "signals": clipped_signals,
                    "weighted_signals": weighted_signals,
                    "weighted_sum": weighted_sum,
                    "final_adjustment": final_adjustment,
                    "matchup_multiplier": matchup_multiplier,
                    "injury_status": status,
                }

        quality_flags = set()
        for feed_name, feed_payload in feeds.items():
            for flag in _as_dict(feed_payload).get("quality_flags", []):
                quality_flags.add(f"{feed_name}:{flag}")

        warnings = list(feed_warnings)
        feed_flags = [flag for flag in quality_flags if ":" in flag]
        if feed_flags and all("fetch_failed" in flag or "endpoint_not_configured" in flag for flag in feed_flags):
            warnings.append("External feeds unavailable; provider degraded to league-only signals")

        summary = {
            "players_evaluated": total_players,
            "players_with_non_zero_alpha": non_zero_adjustments,
            "cap_hits_total_adjustment": sum(
                1
                for value in player_adjustments.values()
                if value <= caps.total_adjustment[0] + 1e-9 or value >= caps.total_adjustment[1] - 1e-9
            ),
            "quality_flags": sorted(quality_flags),
        }

        return {
            "player_adjustments": player_adjustments,
            "injury_overrides": injury_overrides,
            "matchup_overrides": matchup_overrides,
            "diagnostics": diagnostics,
            "warnings": warnings,
            "summary": summary,
        }
