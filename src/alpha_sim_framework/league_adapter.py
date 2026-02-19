from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AdapterPlayer:
    playerId: Any
    name: str = ""
    position: str = ""
    lineupSlot: str = "BE"
    slot_position: str = "BE"
    eligibleSlots: List[str] = field(default_factory=list)
    projected_total_points: float = 0.0
    projected_avg_points: float = 0.0
    avg_points: float = 0.0
    stats: Dict[Any, Dict[str, Any]] = field(default_factory=dict)
    injuryStatus: str = "NONE"
    injured: bool = False
    percent_started: float = 0.0
    pro_pos_rank: float = 0.0


@dataclass
class AdapterTeam:
    team_id: int
    team_name: str = ""
    wins: int = 0
    scores: List[Optional[float]] = field(default_factory=list)
    outcomes: List[str] = field(default_factory=list)
    schedule: List[Any] = field(default_factory=list)
    points_for: float = 0.0
    roster: List[AdapterPlayer] = field(default_factory=list)


@dataclass
class AdapterLeague:
    teams: List[AdapterTeam]
    current_week: int
    reg_season_count: int = 14
    playoff_team_count: int = 4
    _box_scores_fn: Optional[Callable[..., List[Any]]] = None
    _free_agents_fn: Optional[Callable[..., List[Any]]] = None

    @property
    def settings(self):
        return SimpleNamespace(
            reg_season_count=self.reg_season_count,
            playoff_team_count=self.playoff_team_count,
        )

    def box_scores(self, week: int = None):
        if self._box_scores_fn is None:
            return []
        return self._box_scores_fn(week=week)

    def free_agents(self, week: int = None, size: int = 50, position: str = None, position_id: int = None):
        if self._free_agents_fn is None:
            return []
        return self._free_agents_fn(week=week, size=size, position=position, position_id=position_id)


def from_espn_league(league: Any) -> AdapterLeague:
    """Convert an espn_api.football.League into a stable LeagueLike adapter object."""
    teams: List[AdapterTeam] = []

    for team in getattr(league, "teams", []):
        players: List[AdapterPlayer] = []
        for player in getattr(team, "roster", []):
            players.append(
                AdapterPlayer(
                    playerId=getattr(player, "playerId", getattr(player, "name", id(player))),
                    name=str(getattr(player, "name", "")),
                    position=str(getattr(player, "position", "")),
                    lineupSlot=str(getattr(player, "lineupSlot", "BE")),
                    slot_position=str(getattr(player, "slot_position", getattr(player, "lineupSlot", "BE"))),
                    eligibleSlots=list(getattr(player, "eligibleSlots", []) or []),
                    projected_total_points=float(getattr(player, "projected_total_points", 0.0) or 0.0),
                    projected_avg_points=float(getattr(player, "projected_avg_points", 0.0) or 0.0),
                    avg_points=float(getattr(player, "avg_points", 0.0) or 0.0),
                    stats=dict(getattr(player, "stats", {}) or {}),
                    injuryStatus=str(getattr(player, "injuryStatus", "NONE") or "NONE"),
                    injured=bool(getattr(player, "injured", False)),
                    percent_started=float(getattr(player, "percent_started", 0.0) or 0.0),
                    pro_pos_rank=float(getattr(player, "pro_pos_rank", 0.0) or 0.0),
                )
            )

        schedule = []
        for opponent in getattr(team, "schedule", []):
            schedule.append(getattr(opponent, "team_id", opponent))

        points_for = float(getattr(team, "points_for", 0.0) or 0.0)
        if points_for <= 0:
            points_for = float(sum(score for score in getattr(team, "scores", []) if score is not None))

        teams.append(
            AdapterTeam(
                team_id=int(getattr(team, "team_id")),
                team_name=str(getattr(team, "team_name", "")),
                wins=int(getattr(team, "wins", 0) or 0),
                scores=list(getattr(team, "scores", []) or []),
                outcomes=list(getattr(team, "outcomes", []) or []),
                schedule=schedule,
                points_for=points_for,
                roster=players,
            )
        )

    settings = getattr(league, "settings", None)
    reg_season_count = int(getattr(settings, "reg_season_count", 14) or 14)
    playoff_team_count = int(getattr(settings, "playoff_team_count", 4) or 4)
    current_week = int(getattr(league, "current_week", 1) or 1)

    return AdapterLeague(
        teams=teams,
        current_week=current_week,
        reg_season_count=reg_season_count,
        playoff_team_count=playoff_team_count,
        _box_scores_fn=getattr(league, "box_scores", None),
        _free_agents_fn=getattr(league, "free_agents", None),
    )
