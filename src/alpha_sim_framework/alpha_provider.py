from typing import Any, Dict


class NullSignalProvider:
    def get_player_adjustments(self, league: Any, week: int) -> Dict[Any, float]:
        return {}

    def get_injury_overrides(self, league: Any, week: int) -> Dict[Any, str]:
        return {}

    def get_matchup_overrides(self, league: Any, week: int) -> Dict[Any, float]:
        return {}


class SafeSignalProvider:
    def __init__(self, provider: Any):
        self.provider = provider or NullSignalProvider()

    def _call(self, method: str, league: Any, week: int) -> Dict[Any, Any]:
        fn = getattr(self.provider, method, None)
        if not callable(fn):
            return {}
        try:
            value = fn(league, week)
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def get_player_adjustments(self, league: Any, week: int) -> Dict[Any, float]:
        return self._call("get_player_adjustments", league, week)

    def get_injury_overrides(self, league: Any, week: int) -> Dict[Any, str]:
        return self._call("get_injury_overrides", league, week)

    def get_matchup_overrides(self, league: Any, week: int) -> Dict[Any, float]:
        return self._call("get_matchup_overrides", league, week)
