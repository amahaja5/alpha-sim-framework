import copy
from typing import Any, Dict, List, Optional

import numpy as np

from .alpha_backtest import run_backtest
from .historical_backtest import run_historical_backtest
from .league_context import build_league_context, load_league_context
from .alpha_model import project_players
from .alpha_provider import SafeSignalProvider
from .alpha_snapshot import build_week_snapshot
from .sim_contracts import LeagueLike
from .alpha_types import AlphaConfig


class MonteCarloSimulator:
    def __init__(
        self,
        league: LeagueLike,
        num_simulations: int = 1000,
        preseason: bool = False,
        seed: Optional[int] = None,
        ratings_blend: float = 0.65,
        alpha_mode: bool = False,
        alpha_config: Optional[Dict[str, Any]] = None,
        provider: Optional[Any] = None,
    ):
        """Initialize Monte Carlo simulator for season predictions.

        Args:
            league: League instance to simulate.
            num_simulations: Number of season simulations to run.
            preseason: If True, simulate from week 1.
            seed: Optional random seed for reproducible simulations.
            ratings_blend: Weight for observed in-season performance vs preseason prior.
            alpha_mode: If True, use alpha projection model for lineup/move analysis.
            alpha_config: Optional alpha configuration overrides.
            provider: Optional external signal provider.
        """
        self.league = league
        self.num_simulations = num_simulations
        self.preseason = preseason
        self.ratings_blend = max(0.0, min(1.0, ratings_blend))
        self.rng = np.random.default_rng(seed)

        self.teams = league.teams
        self._validate_nfl_league_shape()
        self._team_map = {team.team_id: team for team in self.teams}
        self.schedule = self._get_remaining_schedule()
        self.team_ratings = self._get_team_ratings()
        self.draft_rankings = {}

        self.alpha_mode = bool(alpha_mode)
        self.alpha_config = self._build_alpha_config(alpha_config)
        self.signal_provider = SafeSignalProvider(provider)
        self._alpha_projection_cache: Optional[Dict[Any, Any]] = None
        self._alpha_week_cache: Optional[int] = None

    def _validate_nfl_league_shape(self) -> None:
        """Fail fast when a non-football league shape is passed in."""
        for team in self.teams:
            if not hasattr(team, "outcomes") or not hasattr(team, "scores"):
                raise ValueError("MonteCarloSimulator currently supports NFL league objects only")

            schedule = getattr(team, "schedule", [])
            if schedule:
                sample = schedule[0]
                # Other sports store matchup objects with week/home/away fields.
                if hasattr(sample, "week") and (hasattr(sample, "home_team") or hasattr(sample, "away_team")):
                    raise ValueError("MonteCarloSimulator currently supports NFL league objects only")

    def _build_alpha_config(self, alpha_config: Optional[Dict[str, Any]]) -> AlphaConfig:
        if alpha_config is None:
            return AlphaConfig()
        if isinstance(alpha_config, AlphaConfig):
            return alpha_config

        config = AlphaConfig()
        for key, value in alpha_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def _get_remaining_schedule(self) -> List[Dict]:
        """Build the remaining game list using football team schedules.

        Each game has: week, team1_id, team2_id.
        """
        schedule = []
        seen = set()
        start_week = 1 if self.preseason else max(1, getattr(self.league, "current_week", 1))

        for team in self.teams:
            outcomes = getattr(team, "outcomes", [])
            for idx, opponent in enumerate(getattr(team, "schedule", [])):
                week = idx + 1
                if week < start_week:
                    continue

                outcome = outcomes[idx] if idx < len(outcomes) else "U"
                if not self.preseason and outcome != "U":
                    continue

                opponent_id = getattr(opponent, "team_id", opponent)
                if opponent_id is None or opponent_id == team.team_id:
                    continue

                if opponent_id not in self._team_map:
                    continue

                game_key = (week, min(team.team_id, opponent_id), max(team.team_id, opponent_id))
                if game_key in seen:
                    continue
                seen.add(game_key)

                schedule.append(
                    {
                        "week": week,
                        "team1_id": team.team_id,
                        "team2_id": opponent_id,
                    }
                )

        return sorted(schedule, key=lambda game: game["week"])

    def _get_player_projection(self, player) -> float:
        reg_games = max(1, getattr(self.league.settings, "reg_season_count", 14))

        projected_total = float(getattr(player, "projected_total_points", 0) or 0)
        if projected_total > 0:
            return projected_total

        projected_avg = float(getattr(player, "projected_avg_points", 0) or 0)
        if projected_avg > 0:
            return projected_avg * reg_games

        avg_points = float(getattr(player, "avg_points", 0) or 0)
        if avg_points > 0:
            return avg_points * reg_games

        return 0.0

    def _get_preseason_projection(self, team) -> float:
        return sum(self._get_player_projection(player) for player in getattr(team, "roster", []))

    def _observed_scores(self, team) -> List[float]:
        observed = []
        outcomes = getattr(team, "outcomes", [])
        for idx, score in enumerate(getattr(team, "scores", [])):
            if score is None:
                continue
            outcome = outcomes[idx] if idx < len(outcomes) else "U"
            if outcome == "U":
                continue
            observed.append(float(score))
        return observed

    def _get_team_ratings(self) -> Dict[int, Dict]:
        """Get team ratings based on projections and past performance."""
        ratings = {}
        reg_games = max(1, getattr(self.league.settings, "reg_season_count", 14))

        for team in self.teams:
            preseason_total = self._get_preseason_projection(team)
            prior_weekly = preseason_total / reg_games if preseason_total > 0 else 0.0

            observed = self._observed_scores(team)
            observed_weekly = float(np.mean(observed)) if observed else 0.0

            if self.preseason:
                weekly_mean = prior_weekly if prior_weekly > 0 else observed_weekly
            else:
                if observed and prior_weekly > 0:
                    weekly_mean = (self.ratings_blend * observed_weekly) + ((1 - self.ratings_blend) * prior_weekly)
                elif observed:
                    weekly_mean = observed_weekly
                else:
                    weekly_mean = prior_weekly

            if weekly_mean <= 0:
                weekly_mean = float(getattr(team, "points_for", 0) or 0)
                completed_games = max(1, len(observed))
                weekly_mean = weekly_mean / completed_games if weekly_mean > 0 else 90.0

            if len(observed) >= 2:
                std_dev = float(np.std(observed, ddof=1))
            elif len(observed) == 1:
                std_dev = abs(observed[0]) * 0.2
            else:
                std_dev = weekly_mean * 0.15

            std_dev = max(7.5, std_dev)

            ratings[team.team_id] = {
                "mean": weekly_mean,
                "std": std_dev,
                "roster_value": self._calculate_roster_value(team),
            }

        return ratings

    def _calculate_roster_value(self, team) -> float:
        """Calculate overall roster value considering positional importance."""
        value = 0.0
        position_weights = {
            "QB": 1.2,
            "RB": 1.1,
            "WR": 1.1,
            "TE": 0.8,
            "K": 0.5,
            "D/ST": 0.7,
        }

        for player in getattr(team, "roster", []):
            pos = getattr(player, "position", "")
            points = self._get_player_projection(player)
            value += points * position_weights.get(pos, 1.0)

        return value

    def _get_roster_composition(self, roster: List) -> Dict[str, float]:
        composition = {"QB": 0.0, "RB": 0.0, "WR": 0.0, "TE": 0.0, "K": 0.0, "D/ST": 0.0}
        total_value = 0.0

        for player in roster:
            pos = getattr(player, "position", "")
            if pos not in composition:
                continue
            value = self._get_player_projection(player)
            if value <= 0:
                continue
            composition[pos] += value
            total_value += value

        if total_value > 0:
            for pos in composition:
                composition[pos] /= total_value

        return composition

    def _sort_teams_by_wins(self, season_wins: Dict[int, int]) -> List:
        tie_break = {team_id: float(self.rng.random()) for team_id in season_wins.keys()}
        return sorted(season_wins.items(), key=lambda pair: (pair[1], tie_break[pair[0]]), reverse=True)

    def _apply_strategy_weights(self, weights: Dict[str, float]) -> Dict[int, Dict]:
        """Apply strategy weights to a copy of team ratings."""
        modified_ratings = {team_id: copy.deepcopy(data) for team_id, data in self.team_ratings.items()}

        for team_id in modified_ratings:
            team = self._team_map[team_id]
            roster_comp = self._get_roster_composition(getattr(team, "roster", []))
            strategy_match = sum(weights.get(pos, 0.0) * pct for pos, pct in roster_comp.items())

            # Keep adjustments bounded to avoid unrealistic blowups.
            factor = 0.75 + (0.5 * strategy_match)
            modified_ratings[team_id]["mean"] *= factor

        return modified_ratings

    def _analyze_championship_rosters(self, rosters: List[List]) -> List[Dict]:
        """Analyze characteristics of championship rosters."""
        analysis = []

        for roster in rosters:
            comp = self._get_roster_composition(roster)
            projections = [self._get_player_projection(player) for player in roster]
            projections = [projection for projection in projections if projection > 0]

            if projections:
                mean_projection = float(np.mean(projections))
                std_projection = float(np.std(projections))
                star_cutoff = mean_projection + std_projection
                star_players = sum(1 for player in roster if self._get_player_projection(player) > star_cutoff)
                total_projection = float(sum(projections))
            else:
                star_players = 0
                total_projection = 0.0

            analysis.append(
                {
                    "composition": comp,
                    "star_players": star_players,
                    "total_projection": total_projection,
                }
            )

        return analysis

    def _alpha_player_id(self, player: Any) -> Any:
        return getattr(player, "playerId", getattr(player, "name", id(player)))

    def _get_alpha_projection_map(self, week: Optional[int] = None, extra_players: Optional[List[Any]] = None) -> Dict[Any, Any]:
        target_week = week or max(1, int(getattr(self.league, "current_week", 1)))
        if self._alpha_projection_cache is not None and self._alpha_week_cache == target_week and not extra_players:
            return self._alpha_projection_cache

        snapshot = build_week_snapshot(
            self.league,
            week=target_week,
            candidate_pool_size=int(self.alpha_config.candidate_pool_size),
        )

        players = []
        for team in snapshot["teams"]:
            players.extend(getattr(team, "roster", []))
        players.extend(snapshot.get("free_agents", []))

        player_adj = self.signal_provider.get_player_adjustments(self.league, target_week)
        injury_overrides = self.signal_provider.get_injury_overrides(self.league, target_week)
        matchup_overrides = self.signal_provider.get_matchup_overrides(self.league, target_week)

        projection_map = project_players(
            players,
            self.alpha_config,
            player_adj,
            injury_overrides,
            matchup_overrides,
        )
        if extra_players:
            projection_map.update(
                project_players(
                    extra_players,
                    self.alpha_config,
                    player_adj,
                    injury_overrides,
                    matchup_overrides,
                )
            )

        self._alpha_projection_cache = projection_map
        self._alpha_week_cache = target_week
        return projection_map

    def _projection_for_player(self, player: Any, week: Optional[int] = None):
        projection_map = self._get_alpha_projection_map(week=week)
        return projection_map.get(self._alpha_player_id(player))

    def _lineup_slot(self, player: Any) -> str:
        return str(getattr(player, "lineupSlot", getattr(player, "slot_position", "")) or "").upper()

    def _is_current_starter(self, player: Any) -> bool:
        slot = self._lineup_slot(player)
        return slot not in {"", "BE", "BENCH", "IR", "FA"}

    def _default_lineup_slots(self) -> List[str]:
        return ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "D/ST"]

    def _eligible_for_slot(self, player: Any, slot: str) -> bool:
        pos = str(getattr(player, "position", "") or "")
        if slot == "FLEX":
            return pos in {"RB", "WR", "TE"}
        if pos == slot:
            return True

        eligible = getattr(player, "eligibleSlots", None)
        if isinstance(eligible, list):
            return slot in {str(value).upper() for value in eligible}
        return False

    def _risk_adjusted_score(self, player: Any, week: Optional[int] = None) -> float:
        if not self.alpha_mode:
            return self._get_player_projection(player) / max(1, getattr(self.league.settings, "reg_season_count", 14))

        projection = self._projection_for_player(player, week=week)
        if projection is None:
            return 0.0
        return projection.weekly_mean - (0.15 * projection.weekly_std)

    def _current_lineup(self, team: Any, week: Optional[int] = None) -> List[Any]:
        starters = [player for player in getattr(team, "roster", []) if self._is_current_starter(player)]
        if starters:
            return starters
        return self._optimize_lineup(team, week=week)

    def _optimize_lineup(self, team: Any, week: Optional[int] = None) -> List[Any]:
        roster = list(getattr(team, "roster", []))
        selected = []
        used = set()

        for slot in self._default_lineup_slots():
            candidates = [
                player
                for player in roster
                if self._alpha_player_id(player) not in used and self._eligible_for_slot(player, slot)
            ]
            if not candidates:
                continue
            best = max(candidates, key=lambda player: self._risk_adjusted_score(player, week=week))
            selected.append(best)
            used.add(self._alpha_player_id(best))

        return selected

    def _lineup_score(self, lineup: List[Any], week: Optional[int] = None) -> Dict[str, float]:
        if not self.alpha_mode:
            weekly = sum(
                self._get_player_projection(player) / max(1, getattr(self.league.settings, "reg_season_count", 14))
                for player in lineup
            )
            return {"mean": weekly, "std": max(6.0, weekly * 0.18)}

        means = []
        variances = []
        for player in lineup:
            projection = self._projection_for_player(player, week=week)
            if projection is None:
                continue
            means.append(projection.weekly_mean)
            variances.append(projection.weekly_std**2)

        mean = float(sum(means)) if means else 0.0
        std = float(np.sqrt(sum(variances))) if variances else max(6.0, mean * 0.2)
        return {"mean": mean, "std": max(6.0, std)}

    def _alpha_team_ratings_for_sim(self) -> Dict[int, Dict]:
        if not self.alpha_mode:
            return self.team_ratings

        ratings = {team_id: copy.deepcopy(data) for team_id, data in self.team_ratings.items()}
        blend = float(np.clip(getattr(self.alpha_config, "alpha_blend", 0.35), 0.0, 1.0))

        for team in self.teams:
            lineup = self._optimize_lineup(team)
            lineup_score = self._lineup_score(lineup)
            team_data = ratings[team.team_id]

            team_data["mean"] = (blend * lineup_score["mean"]) + ((1 - blend) * team_data["mean"])
            team_data["std"] = max(6.0, (blend * lineup_score["std"]) + ((1 - blend) * team_data["std"]))

        return ratings

    def _format_confidence_band(self, projection: Any) -> Dict[str, float]:
        if projection is None:
            return {"low": 0.0, "mid": 0.0, "high": 0.0}

        low = max(0.0, projection.weekly_mean - projection.weekly_std)
        high = max(low, projection.weekly_mean + projection.weekly_std)
        return {
            "low": float(low),
            "mid": float(projection.weekly_mean),
            "high": float(high),
        }

    def _compact_factors(self, projection: Any) -> List[str]:
        if projection is None:
            return ["No alpha projection available"]

        components = projection.components
        factors = []

        if components.get("recent", 0) > components.get("prior", 0):
            factors.append("Recent form above preseason prior")
        if components.get("matchup_factor", 1.0) > 1.0:
            factors.append("Favorable matchup")
        if components.get("injury_factor", 1.0) < 1.0:
            factors.append("Injury risk discount applied")
        if components.get("provider_adj", 0.0) != 0.0:
            factors.append("External signal adjustment applied")

        if not factors:
            factors.append("Projection mostly driven by baseline prior")
        return factors[:3]

    def simulate_game(self, team1_id: int, team2_id: int, ratings: Optional[Dict[int, Dict]] = None) -> int:
        """Simulate a single game.

        Returns:
            1 if team1 wins, 2 if team2 wins.
        """
        game_ratings = ratings or self.team_ratings
        team1_score = self.rng.normal(game_ratings[team1_id]["mean"], game_ratings[team1_id]["std"])
        team2_score = self.rng.normal(game_ratings[team2_id]["mean"], game_ratings[team2_id]["std"])
        return 1 if team1_score > team2_score else 2

    def simulate_season(self, ratings: Optional[Dict[int, Dict]] = None) -> Dict[int, int]:
        """Simulate one complete season from the current point."""
        wins = {team.team_id: (0 if self.preseason else team.wins) for team in self.teams}

        for game in self.schedule:
            winner = self.simulate_game(game["team1_id"], game["team2_id"], ratings=ratings)
            if winner == 1:
                wins[game["team1_id"]] += 1
            else:
                wins[game["team2_id"]] += 1

        return wins

    def simulate_playoffs(self, playoff_teams: List[int], ratings: Optional[Dict[int, Dict]] = None) -> int:
        """Simulate playoff bracket to determine champion."""
        teams = playoff_teams.copy()

        while len(teams) > 1:
            winners = []
            for idx in range(0, len(teams), 2):
                if idx + 1 >= len(teams):
                    winners.append(teams[idx])
                    continue
                winner = self.simulate_game(teams[idx], teams[idx + 1], ratings=ratings)
                winners.append(teams[idx] if winner == 1 else teams[idx + 1])
            teams = winners

        return teams[0]

    def run_simulations(self, explain: bool = False, ratings: Optional[Dict[int, Dict]] = None) -> Dict[int, Dict]:
        """Run multiple season simulations and return aggregate odds."""
        results = {
            team.team_id: {
                "wins": 0,
                "playoffs": 0,
                "division": 0,
                "championship": 0,
            }
            for team in self.teams
        }

        active_ratings = ratings
        if active_ratings is None and self.alpha_mode:
            active_ratings = self._alpha_team_ratings_for_sim()

        playoff_spots = max(1, getattr(self.league.settings, "playoff_team_count", 4))

        for _ in range(self.num_simulations):
            season = self.simulate_season(ratings=active_ratings)
            sorted_teams = self._sort_teams_by_wins(season)

            for team_id, wins in season.items():
                results[team_id]["wins"] += wins

            playoff_teams = sorted_teams[:playoff_spots]
            for team_id, _ in playoff_teams:
                results[team_id]["playoffs"] += 1

            if len(playoff_teams) >= 2:
                champ_id = self.simulate_playoffs([team_id for team_id, _ in playoff_teams], ratings=active_ratings)
                results[champ_id]["championship"] += 1

        for team_id in results:
            results[team_id]["avg_wins"] = results[team_id]["wins"] / self.num_simulations
            results[team_id]["playoff_odds"] = (results[team_id]["playoffs"] / self.num_simulations) * 100
            results[team_id]["championship_odds"] = (results[team_id]["championship"] / self.num_simulations) * 100

        if explain:
            results["_meta"] = {
                "alpha_mode": self.alpha_mode,
                "num_simulations": self.num_simulations,
                "ratings_source": "alpha" if self.alpha_mode and ratings is None else "baseline",
            }

        return results

    def recommend_lineup(self, team_id: int, week: int = None, explain: bool = False) -> Dict[str, Any]:
        team = self._team_map[team_id]
        target_week = week or max(1, int(getattr(self.league, "current_week", 1)))

        if self.alpha_mode:
            self._get_alpha_projection_map(week=target_week)

        current_lineup = self._current_lineup(team, week=target_week)
        optimized_lineup = self._optimize_lineup(team, week=target_week)

        current_score = self._lineup_score(current_lineup, week=target_week)
        optimized_score = self._lineup_score(optimized_lineup, week=target_week)

        payload = {
            "team_id": team_id,
            "current_lineup": [getattr(player, "name", str(player)) for player in current_lineup],
            "recommended_lineup": [getattr(player, "name", str(player)) for player in optimized_lineup],
            "projected_delta": optimized_score["mean"] - current_score["mean"],
            "expected_points": optimized_score["mean"],
        }

        if explain and self.alpha_mode:
            details = []
            for player in optimized_lineup:
                projection = self._projection_for_player(player, week=target_week)
                details.append(
                    {
                        "player": getattr(player, "name", str(player)),
                        "factors": self._compact_factors(projection),
                        "confidence_band": self._format_confidence_band(projection),
                    }
                )
            payload["details"] = details
        elif explain:
            payload["details"] = [
                {
                    "player": getattr(player, "name", str(player)),
                    "factors": ["Alpha mode disabled; using baseline projection"],
                    "confidence_band": {"low": 0.0, "mid": 0.0, "high": 0.0},
                }
                for player in optimized_lineup
            ]

        return payload

    def analyze_draft_strategy(self) -> Dict[str, List[Dict]]:
        """Analyze different draft strategies through simulation."""
        if not self.preseason:
            raise ValueError("Draft strategy analysis only available in preseason mode")

        strategies = {
            "Zero RB": {"RB": 0.1, "WR": 0.4, "TE": 0.2, "QB": 0.2, "K": 0.05, "D/ST": 0.05},
            "RB Heavy": {"RB": 0.4, "WR": 0.2, "TE": 0.1, "QB": 0.2, "K": 0.05, "D/ST": 0.05},
            "Balanced": {"RB": 0.25, "WR": 0.25, "TE": 0.15, "QB": 0.25, "K": 0.05, "D/ST": 0.05},
        }

        results = {strategy: [] for strategy in strategies}
        iterations = max(1, self.num_simulations // 10)
        playoff_spots = max(1, getattr(self.league.settings, "playoff_team_count", 4))

        for strategy, weights in strategies.items():
            championship_rosters = []

            for _ in range(iterations):
                modified_ratings = self._apply_strategy_weights(weights)
                season = self.simulate_season(ratings=modified_ratings)
                sorted_teams = self._sort_teams_by_wins(season)
                playoff_teams = [team_id for team_id, _ in sorted_teams[:playoff_spots]]

                if len(playoff_teams) < 2:
                    continue

                champ_id = self.simulate_playoffs(playoff_teams, ratings=modified_ratings)
                champ_team = self._team_map.get(champ_id)
                if champ_team:
                    championship_rosters.append(list(getattr(champ_team, "roster", [])))

            results[strategy] = self._analyze_championship_rosters(championship_rosters)

        return results

    def _get_current_starter(self, team, position: str):
        """Get current starter at position based on highest projection."""
        pos_players = [player for player in getattr(team, "roster", []) if getattr(player, "position", "") == position]
        if not pos_players:
            return None

        if self.alpha_mode:
            return max(pos_players, key=self._risk_adjusted_score)
        return max(pos_players, key=self._get_player_projection)

    def _calculate_player_value(self, player, team) -> float:
        """Calculate projected season value added for a player."""
        position = getattr(player, "position", "")
        current_starter = self._get_current_starter(team, position)

        player_projection = self._get_player_projection(player)
        starter_projection = self._get_player_projection(current_starter) if current_starter else 0.0

        return player_projection - starter_projection

    def _calculate_player_alpha_value(self, player, team, week: Optional[int] = None) -> float:
        projection = self._projection_for_player(player, week=week)
        if projection is None:
            return 0.0

        position = getattr(player, "position", "")
        baseline = self._get_current_starter(team, position)
        baseline_projection = self._projection_for_player(baseline, week=week) if baseline else None

        base_mean = baseline_projection.weekly_mean if baseline_projection else 0.0
        return projection.weekly_mean - base_mean

    def get_optimal_moves(self, team_id: int, free_agents: List = None, explain: bool = False) -> List[Dict]:
        """Get recommended roster moves based on projected value added."""
        team = self._team_map[team_id]
        current_value = self.team_ratings[team_id]["roster_value"]

        if self.alpha_mode:
            self._get_alpha_projection_map(extra_players=free_agents or [])

        recommendations = []

        for other_team in self.teams:
            if other_team.team_id == team_id:
                continue

            for player in getattr(other_team, "roster", []):
                value_added = (
                    self._calculate_player_alpha_value(player, team)
                    if self.alpha_mode
                    else self._calculate_player_value(player, team)
                )
                if value_added > 0:
                    recommendation = {
                        "type": "trade",
                        "player": player,
                        "target_team": other_team.team_name,
                        "value_added": value_added,
                        "priority": "high" if value_added > current_value * 0.1 else "medium",
                    }
                    if explain and self.alpha_mode:
                        projection = self._projection_for_player(player)
                        recommendation["factors"] = self._compact_factors(projection)
                        recommendation["confidence_band"] = self._format_confidence_band(projection)
                    recommendations.append(recommendation)

        if free_agents:
            sorted_free_agents = list(free_agents)
            if self.alpha_mode:
                sorted_free_agents = sorted(
                    sorted_free_agents,
                    key=lambda player: self._risk_adjusted_score(player),
                    reverse=True,
                )[: int(self.alpha_config.candidate_pool_size)]

            for player in sorted_free_agents:
                value_added = (
                    self._calculate_player_alpha_value(player, team)
                    if self.alpha_mode
                    else self._calculate_player_value(player, team)
                )
                if value_added > 0:
                    recommendation = {
                        "type": "add",
                        "player": player,
                        "value_added": value_added,
                        "priority": "high" if value_added > current_value * 0.05 else "medium",
                    }
                    if explain and self.alpha_mode:
                        projection = self._projection_for_player(player)
                        recommendation["factors"] = self._compact_factors(projection)
                        recommendation["confidence_band"] = self._format_confidence_band(projection)
                    recommendations.append(recommendation)

        recommendations.sort(key=lambda recommendation: recommendation["value_added"], reverse=True)
        return recommendations[:5]

    def backtest_alpha(self, config: Optional[dict] = None) -> Dict[str, Any]:
        if not self.alpha_mode:
            raise ValueError("backtest_alpha requires alpha_mode=True")
        return run_backtest(self, config=config)

    def run_historical_opponent_backtest(self, config: Optional[dict] = None) -> Dict[str, Any]:
        return run_historical_backtest(self, config=config)

    def build_league_context(self, config: Optional[dict] = None) -> Dict[str, Any]:
        payload = dict(config or {})
        payload.setdefault("league_id", getattr(self.league, "league_id", None))
        payload.setdefault("year", getattr(self.league, "year", None))
        if payload.get("league_id") is None or payload.get("year") is None:
            raise ValueError("build_league_context requires league_id and year in config or simulator league")
        return build_league_context(payload)

    def load_league_context(self, path: str) -> Dict[str, Any]:
        return load_league_context(path)
