from typing import Any, Dict, List

from .sim_contracts import LeagueLike


def _lineup_slot(player: Any) -> str:
    return str(getattr(player, "lineupSlot", getattr(player, "slot_position", "")) or "").upper()


def _starter_from_slot(player: Any) -> bool:
    slot = _lineup_slot(player)
    return slot not in {"BE", "BENCH", "IR", "", "FA"}


def build_week_snapshot(league: LeagueLike, week: int = None, candidate_pool_size: int = 30) -> Dict[str, Any]:
    current_week = week or max(1, int(getattr(league, "current_week", 1)))
    teams = list(getattr(league, "teams", []))

    current_lineups: Dict[int, List[Any]] = {team.team_id: [] for team in teams}
    try:
        box_scores = league.box_scores(week=current_week)
    except Exception:
        box_scores = []

    if box_scores:
        for matchup in box_scores:
            for side in ("home", "away"):
                team = getattr(matchup, f"{side}_team", None)
                lineup = getattr(matchup, f"{side}_lineup", [])
                team_id = getattr(team, "team_id", team)
                if team_id in current_lineups:
                    current_lineups[team_id] = [player for player in lineup if _starter_from_slot(player)]

    for team in teams:
        if not current_lineups.get(team.team_id):
            current_lineups[team.team_id] = [player for player in getattr(team, "roster", []) if _starter_from_slot(player)]

    try:
        free_agents = list(league.free_agents(week=current_week, size=candidate_pool_size))
    except Exception:
        free_agents = []

    return {
        "week": current_week,
        "teams": teams,
        "lineups": current_lineups,
        "free_agents": free_agents,
    }
