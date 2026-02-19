from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

from .alpha_types import AlphaConfig, PlayerProjection


def _player_id(player: Any) -> Any:
    return getattr(player, "playerId", getattr(player, "name", id(player)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _projection_prior(player: Any) -> float:
    projected_avg = _safe_float(getattr(player, "projected_avg_points", 0.0), 0.0)
    if projected_avg > 0:
        return projected_avg

    projected_total = _safe_float(getattr(player, "projected_total_points", 0.0), 0.0)
    if projected_total > 0:
        return projected_total / 14.0

    return _safe_float(getattr(player, "avg_points", 0.0), 0.0)


def _recent_points(player: Any, recent_weeks: int) -> List[float]:
    stats = getattr(player, "stats", {})
    points: List[Tuple[int, float]] = []

    if isinstance(stats, dict):
        for key, entry in stats.items():
            if not isinstance(entry, dict):
                continue
            pt = entry.get("points")
            if pt is None:
                continue
            try:
                week = int(key)
            except Exception:
                continue
            if week <= 0:
                continue
            points.append((week, _safe_float(pt)))

    points.sort(key=lambda item: item[0], reverse=True)
    return [value for _, value in points[:recent_weeks]]


def _injury_factor(player: Any, config: AlphaConfig, injury_overrides: Dict[Any, str]) -> float:
    pid = _player_id(player)
    status = injury_overrides.get(pid, getattr(player, "injuryStatus", "NONE"))
    key = str(status or "NONE").upper()
    if key in config.injury_penalties:
        return config.injury_penalties[key]

    injured = bool(getattr(player, "injured", False))
    if injured:
        return config.injury_penalties.get("QUESTIONABLE", 0.85)
    return 1.0


def _matchup_factor(player: Any, config: AlphaConfig, matchup_overrides: Dict[Any, float]) -> float:
    pid = _player_id(player)
    if pid in matchup_overrides:
        return float(np.clip(_safe_float(matchup_overrides[pid], 1.0), 0.7, 1.3))

    rank = _safe_float(getattr(player, "pro_pos_rank", 0.0), 0.0)
    if rank <= 0:
        return 1.0

    centered = (rank - 17.0) / 16.0
    factor = 1.0 + (config.matchup_scale * centered)
    return float(np.clip(factor, 0.85, 1.15))


def project_player(
    player: Any,
    config: AlphaConfig,
    player_adjustments: Dict[Any, float],
    injury_overrides: Dict[Any, str],
    matchup_overrides: Dict[Any, float],
) -> PlayerProjection:
    prior = _projection_prior(player)
    recent = _recent_points(player, config.recent_weeks)
    n_recent = len(recent)
    recent_avg = float(np.mean(recent)) if recent else prior

    w_recent = n_recent / (n_recent + max(0.1, config.shrinkage_k))
    w_prior = 1.0 - w_recent

    market_adj = (_safe_float(getattr(player, "percent_started", 0.0), 0.0) - 50.0) * 0.03
    base_mu = (w_prior * prior) + (w_recent * recent_avg) + market_adj

    injury_factor = _injury_factor(player, config, injury_overrides)
    matchup_factor = _matchup_factor(player, config, matchup_overrides)

    pid = _player_id(player)
    provider_adj = _safe_float(player_adjustments.get(pid, 0.0), 0.0)

    mean = max(0.0, (base_mu + provider_adj) * injury_factor * matchup_factor)

    if len(recent) >= 2:
        std = float(np.std(recent, ddof=1))
    elif len(recent) == 1:
        std = abs(recent[0]) * 0.25
    else:
        std = max(2.0, prior * 0.35)

    std = max(2.0, std) + (2.5 if injury_factor < 1.0 else 0.0)

    confidence = float(np.clip((n_recent / max(1.0, config.recent_weeks)) * injury_factor, 0.05, 0.99))

    components = {
        "prior": prior,
        "recent": recent_avg,
        "market_adj": market_adj,
        "provider_adj": provider_adj,
        "injury_factor": injury_factor,
        "matchup_factor": matchup_factor,
        "w_recent": w_recent,
    }

    return PlayerProjection(
        player_id=pid,
        weekly_mean=mean,
        weekly_std=std,
        components=components,
        confidence=confidence,
    )


def project_players(
    players: Iterable[Any],
    config: AlphaConfig,
    player_adjustments: Dict[Any, float],
    injury_overrides: Dict[Any, str],
    matchup_overrides: Dict[Any, float],
) -> Dict[Any, PlayerProjection]:
    projections = {}
    for player in players:
        projection = project_player(player, config, player_adjustments, injury_overrides, matchup_overrides)
        projections[projection.player_id] = projection
    return projections
