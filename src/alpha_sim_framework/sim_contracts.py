from typing import Any, List, Protocol


class LeagueLike(Protocol):
    teams: List[Any]
    current_week: int
    settings: Any

    def box_scores(self, week: int = None):
        ...

    def free_agents(self, week: int = None, size: int = 50, position: str = None, position_id: int = None):
        ...
