import json
from unittest import TestCase, mock

from alpha_sim_framework.alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from alpha_sim_framework.feed_contracts import validate_canonical_feed
from alpha_sim_framework.providers.feeds.common import JSONFeedClient


class _FakePlayer:
    def __init__(self, player_id, position, projected, started_pct=50.0, injury_status="NONE", pro_team="PHI"):
        self.playerId = player_id
        self.position = position
        self.projected_avg_points = projected
        self.projected_total_points = projected * 14.0
        self.avg_points = projected
        self.percent_started = started_pct
        self.injuryStatus = injury_status
        self.proTeam = pro_team
        self.stats = {
            1: {"points": projected - 1.0},
            2: {"points": projected + 1.5},
            3: {"points": projected - 0.5},
        }


class _FakeTeam:
    def __init__(self, team_id, wins, roster):
        self.team_id = team_id
        self.wins = wins
        self.roster = roster
        self.schedule = []


class _FakeLeague:
    def __init__(self, teams):
        self.league_id = 123
        self.year = 2025
        self.current_week = 3
        self.teams = teams


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _league():
    team1 = _FakeTeam(
        1,
        2,
        [
            _FakePlayer(101, "QB", 21.0, started_pct=72.0, pro_team="ATL"),
            _FakePlayer(102, "RB", 15.0, started_pct=66.0, pro_team="PHI"),
            _FakePlayer(103, "WR", 14.0, started_pct=51.0, pro_team="KC"),
        ],
    )
    team2 = _FakeTeam(
        2,
        1,
        [
            _FakePlayer(201, "QB", 18.0, started_pct=60.0, pro_team="DAL"),
            _FakePlayer(202, "RB", 13.0, started_pct=45.0, pro_team="BUF"),
            _FakePlayer(203, "WR", 12.5, started_pct=38.0, injury_status="QUESTIONABLE", pro_team="SF"),
        ],
    )
    team1.schedule = [team2, team2, team2]
    team2.schedule = [team1, team1, team1]
    return _FakeLeague([team1, team2])


def _free_config():
    return ExternalFeedConfig(
        enabled=True,
        endpoints={
            "weather": "free://weather",
            "market": "free://market",
            "odds": "free://odds",
            "injury_news": "free://injury_news",
            "nextgenstats": "free://nextgenstats",
            "weather_forecast": "https://api.open-meteo.com/v1/forecast",
            "market_players": "https://api.sleeper.app/v1/players/nfl",
            "market_trending_add": "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=200",
            "market_trending_drop": "https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours=24&limit=200",
            "injury_players": "https://api.sleeper.app/v1/players/nfl",
        },
    )


class FreeFeedModeTest(TestCase):
    def test_free_mode_returns_canonical_payloads(self):
        league = _league()
        config = _free_config()
        runtime = ProviderRuntimeConfig(timeout_seconds=0.1, retries=0)

        sleeper_players = {
            "101": {"injury_status": "Questionable"},
            "102": {"injury_status": "Healthy"},
            "201": {"injury_status": "Out"},
            "203": {"injury_status": "Questionable"},
        }
        add_rows = [{"player_id": "101", "count": 40}, {"player_id": "203", "count": 25}]
        drop_rows = [{"player_id": "201", "count": 30}]
        weather = {"current": {"wind_speed_10m": 17.0, "precipitation_probability": 35}}

        def _fake_urlopen(request, timeout=0):
            url = request.full_url
            if "open-meteo.com" in url:
                return _Resp(weather)
            if "/players/nfl/trending/add" in url:
                return _Resp(add_rows)
            if "/players/nfl/trending/drop" in url:
                return _Resp(drop_rows)
            if "/players/nfl" in url:
                return _Resp(sleeper_players)
            raise RuntimeError(f"unexpected_url:{url}")

        with mock.patch("alpha_sim_framework.providers.feeds.free_api.urllib.request.urlopen", side_effect=_fake_urlopen):
            weather_payload = JSONFeedClient("weather", config, runtime).fetch(league, week=3)
            market_payload = JSONFeedClient("market", config, runtime).fetch(league, week=3)
            odds_payload = JSONFeedClient("odds", config, runtime).fetch(league, week=3)
            injury_payload = JSONFeedClient("injury_news", config, runtime).fetch(league, week=3)
            nextgen_payload = JSONFeedClient("nextgenstats", config, runtime).fetch(league, week=3)

        self.assertEqual(validate_canonical_feed("weather", weather_payload), [])
        self.assertEqual(validate_canonical_feed("market", market_payload), [])
        self.assertEqual(validate_canonical_feed("odds", odds_payload), [])
        self.assertEqual(validate_canonical_feed("injury_news", injury_payload), [])
        self.assertEqual(validate_canonical_feed("nextgenstats", nextgen_payload), [])

        usage_trend = market_payload["data"]["usage_trend"]
        self.assertGreater(usage_trend["101"], usage_trend["201"])
        self.assertIn("101", injury_payload["data"]["injury_status"])
        self.assertIn("201", injury_payload["data"]["injury_status"])
