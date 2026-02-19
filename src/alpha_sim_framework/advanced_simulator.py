"""
Advanced Fantasy Football Simulator with Player-Level GMM and Matchup Analysis

This module provides enhanced Monte Carlo simulation with:
- Player-level performance modeling using GMM
- Matchup-specific simulations
- Trade analysis with asymmetric value detection
- Free agent recommendations
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from .player_performance import PlayerPerformanceModel


class AdvancedFantasySimulator:
    """Advanced fantasy football simulator with player-level modeling"""

    def __init__(
        self,
        league,
        num_simulations: int = 10000,
        cache_dir: str = '.cache',
        use_gmm: bool = True
    ):
        """
        Initialize advanced simulator

        Args:
            league: League instance
            num_simulations: Number of simulations to run
            cache_dir: Cache directory for player models
            use_gmm: Use Gaussian Mixture Models for player prediction
        """
        self.league = league
        self.num_simulations = num_simulations
        self.use_gmm = use_gmm

        # Initialize player performance model
        self.player_model = PlayerPerformanceModel(cache_dir=cache_dir)

        # Train models for all players in the league
        if use_gmm:
            self._train_all_players()

    def _train_all_players(self):
        """Train GMM models for all players in the league"""
        all_players = []

        # Collect all players from teams
        for team in self.league.teams:
            all_players.extend(team.roster)

        # Bulk train
        self.player_model.bulk_train(all_players, self.league.year)

    def simulate_roster_score(
        self,
        team,
        week: Optional[int] = None,
        opponent_defense_rating: float = 1.0
    ) -> float:
        """
        Simulate a team's score for a given week using player-level prediction

        Args:
            team: Team object
            week: Week number (None for generic simulation)
            opponent_defense_rating: Defensive strength multiplier (1.0 = average)

        Returns:
            Simulated team score
        """
        total_score = 0.0

        # Get starting lineup (or all players if no lineup info)
        starters = [p for p in team.roster if hasattr(p, 'lineupSlot') and p.lineupSlot not in ['BE', 'IR', '']]

        if not starters:
            # Fallback: use projected starters based on position slots
            starters = self._get_optimal_lineup(team.roster)

        # Simulate each starter's performance
        for player in starters:
            if self.use_gmm and player.playerId in self.player_model.models:
                # Use GMM prediction
                predicted_score = self.player_model.predict_performance(player, n_samples=1)[0]
            else:
                # Fallback to normal distribution
                mean = player.projected_avg_points if hasattr(player, 'projected_avg_points') and player.projected_avg_points > 0 else player.avg_points
                std = mean * 0.25
                predicted_score = np.random.normal(mean, std)

            # Apply opponent defense adjustment
            predicted_score *= opponent_defense_rating

            # Ensure non-negative
            predicted_score = max(0, predicted_score)

            total_score += predicted_score

        return total_score

    def _get_optimal_lineup(self, roster: List) -> List:
        """
        Get optimal starting lineup based on projections

        Args:
            roster: List of players

        Returns:
            List of starting players
        """
        # Standard fantasy football lineup: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 D/ST
        lineup = []
        remaining = roster.copy()

        # Helper to get best player at position
        def get_best(pos, count=1):
            available = [p for p in remaining if p.position == pos]
            available.sort(
                key=lambda x: getattr(x, 'projected_avg_points', 0) or getattr(x, 'avg_points', 0),
                reverse=True
            )
            selected = available[:count]
            for p in selected:
                remaining.remove(p)
            return selected

        # Fill required positions
        lineup.extend(get_best('QB', 1))
        lineup.extend(get_best('RB', 2))
        lineup.extend(get_best('WR', 2))
        lineup.extend(get_best('TE', 1))
        lineup.extend(get_best('K', 1))
        lineup.extend(get_best('D/ST', 1))

        # FLEX (best remaining RB/WR/TE)
        flex_eligible = [p for p in remaining if p.position in ['RB', 'WR', 'TE']]
        if flex_eligible:
            flex = max(
                flex_eligible,
                key=lambda x: getattr(x, 'projected_avg_points', 0) or getattr(x, 'avg_points', 0)
            )
            lineup.append(flex)

        return lineup

    def simulate_matchup(
        self,
        team1,
        team2,
        week: Optional[int] = None,
        n_simulations: Optional[int] = None
    ) -> Dict:
        """
        Simulate a specific matchup between two teams

        Args:
            team1: First team
            team2: Second team
            week: Week number
            n_simulations: Number of simulations (default: self.num_simulations)

        Returns:
            Dict with simulation results
        """
        if n_simulations is None:
            n_simulations = self.num_simulations

        team1_wins = 0
        team1_scores = []
        team2_scores = []

        for _ in range(n_simulations):
            team1_score = self.simulate_roster_score(team1, week)
            team2_score = self.simulate_roster_score(team2, week)

            team1_scores.append(team1_score)
            team2_scores.append(team2_score)

            if team1_score > team2_score:
                team1_wins += 1

        return {
            'team1_win_probability': team1_wins / n_simulations * 100,
            'team2_win_probability': (n_simulations - team1_wins) / n_simulations * 100,
            'team1_avg_score': np.mean(team1_scores),
            'team1_score_std': np.std(team1_scores),
            'team1_score_range': (np.percentile(team1_scores, 10), np.percentile(team1_scores, 90)),
            'team2_avg_score': np.mean(team2_scores),
            'team2_score_std': np.std(team2_scores),
            'team2_score_range': (np.percentile(team2_scores, 10), np.percentile(team2_scores, 90)),
            'team1_scores': team1_scores,
            'team2_scores': team2_scores
        }

    def analyze_trade(
        self,
        my_team,
        other_team,
        my_players: List,
        their_players: List,
        weeks_remaining: int = 10,
        use_ros: bool = True
    ) -> Dict:
        """
        Analyze a potential trade using Rest of Season (ROS) projections

        Args:
            my_team: Your team object
            other_team: Other team object
            my_players: Players you're giving up
            their_players: Players you're receiving
            weeks_remaining: Weeks remaining in season
            use_ros: Use ROS projections with schedule awareness (default True)

        Returns:
            Trade analysis with value estimates
        """
        # Calculate current week and end week
        current_week = self.league.current_week
        end_week = current_week + weeks_remaining - 1

        # Calculate value before trade (ROS or season avg)
        if use_ros:
            my_current_value = self._calculate_roster_value_ros(
                my_team.roster, current_week, end_week, consider_schedule=True
            )
            their_current_value = self._calculate_roster_value_ros(
                other_team.roster, current_week, end_week, consider_schedule=True
            )
        else:
            my_current_value = self._calculate_team_value(my_team)
            their_current_value = self._calculate_team_value(other_team)

        # Simulate rosters after trade
        my_roster_after = [p for p in my_team.roster if p not in my_players] + their_players
        their_roster_after = [p for p in other_team.roster if p not in their_players] + my_players

        # Calculate value after trade (ROS or season avg)
        if use_ros:
            my_value_after = self._calculate_roster_value_ros(
                my_roster_after, current_week, end_week, consider_schedule=True
            )
            their_value_after = self._calculate_roster_value_ros(
                their_roster_after, current_week, end_week, consider_schedule=True
            )
        else:
            my_value_after = self._calculate_roster_value(my_roster_after)
            their_value_after = self._calculate_roster_value(their_roster_after)

        # Calculate net value change
        my_value_change = my_value_after - my_current_value
        their_value_change = their_value_after - their_current_value

        # Determine if trade is asymmetric (you gain more relative value)
        asymmetric_advantage = my_value_change > their_value_change

        # Project wins added
        avg_points_per_week = my_value_change / weeks_remaining if weeks_remaining > 0 else 0

        # Calculate trade fairness/acceptance probability
        # Trade is more likely to be accepted if both sides gain (or loss is minimal)
        if my_value_change > 0 and their_value_change > 0:
            # Both sides win - high acceptance probability
            acceptance_prob = min(95, 70 + (their_value_change / abs(my_value_change)) * 25)
        elif my_value_change > 0 and their_value_change < 0:
            # You win, they lose - acceptance based on how much they lose
            loss_pct = abs(their_value_change) / their_current_value if their_current_value > 0 else 1.0
            if loss_pct < 0.02:  # Less than 2% loss
                acceptance_prob = 60
            elif loss_pct < 0.05:  # Less than 5% loss
                acceptance_prob = 40
            elif loss_pct < 0.10:  # Less than 10% loss
                acceptance_prob = 20
            else:  # More than 10% loss
                acceptance_prob = 5
        elif my_value_change < 0 and their_value_change > 0:
            # You lose, they win - low probability you'd accept
            acceptance_prob = 10
        else:
            # Both lose - very unlikely
            acceptance_prob = 5

        # Adjust for extreme imbalance
        if abs(my_value_change - their_value_change) > 15:
            acceptance_prob = min(acceptance_prob, 10)

        # Determine if trade is realistic (>30% acceptance probability)
        is_realistic = acceptance_prob > 30

        return {
            'my_value_change': my_value_change,
            'their_value_change': their_value_change,
            'asymmetric_advantage': asymmetric_advantage,
            'advantage_margin': my_value_change - their_value_change,
            'projected_points_added_per_week': avg_points_per_week,
            'total_projected_points_added': my_value_change,
            'acceptance_probability': acceptance_prob,
            'is_realistic': is_realistic,
            'recommendation': 'ACCEPT' if my_value_change > 0 and acceptance_prob > 20 else 'REJECT',
            'confidence': min(100, abs(my_value_change) / (my_current_value / 10)) if my_current_value > 0 else 0,
            'uses_ros_projections': use_ros,
            'weeks_remaining': weeks_remaining
        }

    def _calculate_team_value(self, team) -> float:
        """Calculate total value of a team's roster"""
        return self._calculate_roster_value(team.roster)

    def _calculate_roster_value(self, roster: List) -> float:
        """
        Calculate roster value considering starters and bench depth

        Args:
            roster: List of players

        Returns:
            Total roster value
        """
        # Get optimal lineup
        starters = self._get_optimal_lineup(roster)

        # Calculate starter value (weighted higher)
        starter_value = 0
        for player in starters:
            if self.use_gmm and player.playerId in self.player_model.player_states:
                # Use GMM mean
                state = self.player_model.player_states[player.playerId]
                value = state['season_avg']
            else:
                # Use projections
                value = getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)

            starter_value += value

        # Calculate bench value (weighted lower - 30% of starter value)
        bench = [p for p in roster if p not in starters]
        bench_value = 0
        for player in bench:
            if self.use_gmm and player.playerId in self.player_model.player_states:
                state = self.player_model.player_states[player.playerId]
                value = state['season_avg'] * 0.3
            else:
                value = (getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)) * 0.3

            bench_value += value

        return starter_value + bench_value

    def _calculate_opponent_strength(self, position: str, opponent_team: str) -> float:
        """
        Calculate opponent strength multiplier for a position

        Args:
            position: Player position (RB, WR, QB, TE)
            opponent_team: Opponent team abbreviation

        Returns:
            Multiplier (1.0 = average, >1.0 = favorable, <1.0 = unfavorable)
        """
        # Calculate points allowed by each team to each position
        position_rankings = {}

        for team in self.league.teams:
            team_abbrev = team.team_abbrev if hasattr(team, 'team_abbrev') else team.team_name[:3].upper()

            # Calculate average points allowed to each position
            for player in team.roster:
                if player.position not in ['QB', 'RB', 'WR', 'TE']:
                    continue

                # Get opponent's points scored against this team
                points = getattr(player, 'avg_points', 0) or 0

                if player.position not in position_rankings:
                    position_rankings[player.position] = {}
                if team_abbrev not in position_rankings[player.position]:
                    position_rankings[player.position][team_abbrev] = []

                position_rankings[player.position][team_abbrev].append(points)

        # Calculate average for the position
        if position not in position_rankings or not position_rankings[position]:
            return 1.0  # Default to average if no data

        # Get league average for this position
        all_points = []
        for team_points in position_rankings[position].values():
            all_points.extend(team_points)

        if not all_points:
            return 1.0

        league_avg = np.mean(all_points)

        # Get opponent's average points allowed
        opponent_points = position_rankings[position].get(opponent_team, [])
        if not opponent_points:
            return 1.0  # Default to average

        opponent_avg = np.mean(opponent_points)

        # Return multiplier (higher = easier matchup)
        # If opponent allows 20 ppg and league avg is 15, multiplier = 20/15 = 1.33
        if league_avg > 0:
            return opponent_avg / league_avg
        return 1.0

    def _calculate_roster_value_ros(
        self,
        roster: List,
        current_week: int,
        end_week: int,
        consider_schedule: bool = True
    ) -> float:
        """
        Calculate roster value for rest of season with schedule awareness

        Args:
            roster: List of players
            current_week: Current week number
            end_week: Final week to consider (regular season or playoff end)
            consider_schedule: Whether to adjust for matchup difficulty

        Returns:
            Average weekly roster value for ROS
        """
        weeks_remaining = max(1, end_week - current_week + 1)
        total_ros_value = 0

        # Get optimal lineup for this roster
        starters = self._get_optimal_lineup(roster)

        # Calculate starter ROS value
        for player in starters:
            player_ros_value = 0
            weeks_with_data = 0

            # Project each remaining week
            for week in range(current_week, end_week + 1):
                # Get base projection
                if self.use_gmm and player.playerId in self.player_model.player_states:
                    # Use GMM prediction (accounts for hot/cold state)
                    base_projection = self.player_model.predict_performance(
                        player,
                        n_samples=1,
                        use_state_bias=True
                    )[0]
                else:
                    # Fall back to projected points
                    base_projection = getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)

                # Adjust for matchup difficulty if schedule data available
                week_projection = base_projection
                if consider_schedule and hasattr(player, 'schedule') and week in player.schedule:
                    opponent = player.schedule[week].get('team', '')
                    if opponent and player.position in ['QB', 'RB', 'WR', 'TE']:
                        matchup_multiplier = self._calculate_opponent_strength(player.position, opponent)
                        week_projection = base_projection * matchup_multiplier

                player_ros_value += week_projection
                weeks_with_data += 1

            # Average over weeks and add to total
            if weeks_with_data > 0:
                total_ros_value += player_ros_value / weeks_with_data

        # Calculate bench value (30% weight)
        bench = [p for p in roster if p not in starters]
        for player in bench:
            player_ros_value = 0
            weeks_with_data = 0

            for week in range(current_week, end_week + 1):
                if self.use_gmm and player.playerId in self.player_model.player_states:
                    base_projection = self.player_model.predict_performance(
                        player,
                        n_samples=1,
                        use_state_bias=True
                    )[0]
                else:
                    base_projection = getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)

                # Adjust for matchup if available
                week_projection = base_projection
                if consider_schedule and hasattr(player, 'schedule') and week in player.schedule:
                    opponent = player.schedule[week].get('team', '')
                    if opponent and player.position in ['QB', 'RB', 'WR', 'TE']:
                        matchup_multiplier = self._calculate_opponent_strength(player.position, opponent)
                        week_projection = base_projection * matchup_multiplier

                player_ros_value += week_projection
                weeks_with_data += 1

            # Bench value weighted at 30%
            if weeks_with_data > 0:
                total_ros_value += (player_ros_value / weeks_with_data) * 0.3

        return total_ros_value

    def _calculate_player_ros_value(
        self,
        player,
        current_week: int,
        end_week: int,
        consider_schedule: bool = True
    ) -> float:
        """
        Calculate a single player's ROS value with schedule awareness

        Args:
            player: Player object
            current_week: Current week number
            end_week: Final week to consider
            consider_schedule: Whether to adjust for matchup difficulty

        Returns:
            Average weekly ROS value for this player
        """
        player_ros_value = 0
        weeks_with_data = 0

        # Project each remaining week
        for week in range(current_week, end_week + 1):
            # Get base projection
            if self.use_gmm and player.playerId in self.player_model.player_states:
                # Use GMM prediction (accounts for hot/cold state)
                base_projection = self.player_model.predict_performance(
                    player,
                    n_samples=1,
                    use_state_bias=True
                )[0]
            else:
                # Fall back to projected points
                base_projection = getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)

            # Adjust for matchup difficulty if schedule data available
            week_projection = base_projection
            if consider_schedule and hasattr(player, 'schedule') and week in player.schedule:
                opponent = player.schedule[week].get('team', '')
                if opponent and player.position in ['QB', 'RB', 'WR', 'TE']:
                    matchup_multiplier = self._calculate_opponent_strength(player.position, opponent)
                    week_projection = base_projection * matchup_multiplier

            player_ros_value += week_projection
            weeks_with_data += 1

        # Return average weekly value
        if weeks_with_data > 0:
            return player_ros_value / weeks_with_data
        else:
            # Fallback to season average
            return getattr(player, 'projected_avg_points', 0) or getattr(player, 'avg_points', 0)

    def find_trade_opportunities(
        self,
        my_team,
        min_advantage: float = 5.0,
        max_trades_per_team: int = 3,
        min_acceptance_probability: float = 30.0,
        use_ros: bool = True
    ) -> List[Dict]:
        """
        Find potential trade opportunities with asymmetric value using ROS projections

        Args:
            my_team: Your team
            min_advantage: Minimum point advantage to consider
            max_trades_per_team: Max trade suggestions per opponent
            min_acceptance_probability: Minimum acceptance probability (default 30%)
            use_ros: Use rest of season projections with schedule awareness (default True)

        Returns:
            List of trade opportunities
        """
        # Calculate weeks remaining for ROS calculations
        current_week = self.league.current_week
        reg_season_end = self.league.settings.reg_season_count
        weeks_remaining = max(1, reg_season_end - current_week + 1)

        opportunities = []

        for other_team in self.league.teams:
            if other_team.team_id == my_team.team_id:
                continue

            # Analyze each combination of players
            team_trades = []

            # Try 1-for-1 trades
            for my_player in my_team.roster:
                for their_player in other_team.roster:
                    # Skip if same position and similar value (boring trade)
                    if my_player.position == their_player.position:
                        my_val = getattr(my_player, 'projected_avg_points', 0) or getattr(my_player, 'avg_points', 0)
                        their_val = getattr(their_player, 'projected_avg_points', 0) or getattr(their_player, 'avg_points', 0)
                        if abs(my_val - their_val) < 1.0:
                            continue

                    analysis = self.analyze_trade(
                        my_team, other_team,
                        [my_player], [their_player],
                        weeks_remaining=weeks_remaining,
                        use_ros=use_ros
                    )

                    # Only suggest trades that are realistic (high enough acceptance probability)
                    if (analysis['my_value_change'] > min_advantage and
                        analysis['asymmetric_advantage'] and
                        analysis['acceptance_probability'] >= min_acceptance_probability):
                        team_trades.append({
                            'other_team': other_team.team_name,
                            'give': [my_player.name],
                            'receive': [their_player.name],
                            'analysis': analysis
                        })

            # Try 2-for-1 trades (giving 2 for 1 upgrade)
            for their_player in other_team.roster:
                for i, my_player1 in enumerate(my_team.roster):
                    for my_player2 in my_team.roster[i+1:]:
                        analysis = self.analyze_trade(
                            my_team, other_team,
                            [my_player1, my_player2], [their_player],
                            weeks_remaining=weeks_remaining,
                            use_ros=use_ros
                        )

                        # Only suggest realistic trades
                        if (analysis['my_value_change'] > min_advantage and
                            analysis['asymmetric_advantage'] and
                            analysis['acceptance_probability'] >= min_acceptance_probability):
                            team_trades.append({
                                'other_team': other_team.team_name,
                                'give': [my_player1.name, my_player2.name],
                                'receive': [their_player.name],
                                'analysis': analysis
                            })

            # Sort by advantage and keep top trades
            team_trades.sort(key=lambda x: x['analysis']['advantage_margin'], reverse=True)
            opportunities.extend(team_trades[:max_trades_per_team])

        # Sort all opportunities by advantage
        opportunities.sort(key=lambda x: x['analysis']['advantage_margin'], reverse=True)

        return opportunities

    def recommend_free_agents(
        self,
        my_team,
        free_agents: List,
        top_n: int = 10,
        positions: Optional[List[str]] = None,
        exclude_injured: bool = True,
        use_ros: bool = True
    ) -> List[Dict]:
        """
        Recommend free agent pickups with ROS schedule awareness

        Args:
            my_team: Your team
            free_agents: List of available free agents
            top_n: Number of recommendations
            positions: Filter by positions (None for all)
            exclude_injured: Exclude players with injury designations (default True)
            use_ros: Use rest of season projections with schedule awareness (default True)

        Returns:
            List of free agent recommendations
        """
        # Calculate weeks remaining for ROS
        current_week = self.league.current_week
        reg_season_end = self.league.settings.reg_season_count
        end_week = reg_season_end

        recommendations = []

        for fa in free_agents:
            # Filter by position if specified
            if positions and fa.position not in positions:
                continue

            # Filter out injured players
            if exclude_injured:
                injury_status = getattr(fa, 'injuryStatus', None) or getattr(fa, 'injury_status', None)
                # ESPN uses: OUT, QUESTIONABLE, DOUBTFUL, INJURY_RESERVE, DAY_TO_DAY
                # Healthy players have: ACTIVE or NORMAL
                if injury_status and injury_status.upper() not in ['ACTIVE', 'NORMAL', '', None]:
                    continue

            # Find weakest player at this position on my team
            position_players = [p for p in my_team.roster if p.position == fa.position]

            if not position_players:
                # New position, lower priority
                priority_multiplier = 0.5
                drop_candidate = None
            else:
                # Find worst player at position using ROS or season avg
                if use_ros:
                    drop_candidate = min(
                        position_players,
                        key=lambda x: self._calculate_player_ros_value(x, current_week, end_week, consider_schedule=True)
                    )
                else:
                    drop_candidate = min(
                        position_players,
                        key=lambda x: getattr(x, 'projected_avg_points', 0) or getattr(x, 'avg_points', 0)
                    )
                priority_multiplier = 1.0

            # Calculate value added using ROS or season avg
            if use_ros:
                fa_value = self._calculate_player_ros_value(fa, current_week, end_week, consider_schedule=True)
                fa_season_avg = getattr(fa, 'projected_avg_points', 0) or getattr(fa, 'avg_points', 0)
            else:
                fa_value = getattr(fa, 'projected_avg_points', 0) or getattr(fa, 'avg_points', 0)
                fa_season_avg = fa_value

            if drop_candidate:
                if use_ros:
                    drop_value = self._calculate_player_ros_value(drop_candidate, current_week, end_week, consider_schedule=True)
                    drop_season_avg = getattr(drop_candidate, 'projected_avg_points', 0) or getattr(drop_candidate, 'avg_points', 0)
                else:
                    drop_value = getattr(drop_candidate, 'projected_avg_points', 0) or getattr(drop_candidate, 'avg_points', 0)
                    drop_season_avg = drop_value
                value_added = (fa_value - drop_value) * priority_multiplier
            else:
                value_added = fa_value * priority_multiplier
                drop_season_avg = 0

            if value_added > 0:
                recommendations.append({
                    'player': fa,
                    'position': fa.position,
                    'value_added': value_added,
                    'drop_candidate': drop_candidate.name if drop_candidate else 'None (roster expansion)',
                    'fa_projected_avg': fa_value,
                    'fa_season_avg': fa_season_avg,
                    'drop_projected_avg': drop_value if drop_candidate else 0,
                    'drop_season_avg': drop_season_avg,
                    'priority': 'HIGH' if value_added > 3 else 'MEDIUM' if value_added > 1 else 'LOW',
                    'ownership_pct': getattr(fa, 'percent_owned', 0),
                    'uses_ros': use_ros
                })

        # Sort by value added
        recommendations.sort(key=lambda x: x['value_added'], reverse=True)

        return recommendations[:top_n]

    def simulate_season_rest_of_season(self) -> Dict[int, Dict]:
        """
        Simulate rest of season for all teams

        Returns:
            Dict mapping team_id to season projections
        """
        results = {team.team_id: {
            'current_wins': team.wins,
            'projected_wins': 0,
            'playoff_odds': 0,
            'championship_odds': 0
        } for team in self.league.teams}

        for _ in range(self.num_simulations):
            # Simulate remaining matchups for each week
            season_wins = {team.team_id: team.wins for team in self.league.teams}

            # Get remaining schedule
            for team in self.league.teams:
                for week_idx, opponent in enumerate(team.schedule[self.league.current_week:]):
                    if isinstance(opponent, int):
                        # Find opponent team
                        opponent_team = next((t for t in self.league.teams if t.team_id == opponent), None)
                    else:
                        opponent_team = opponent

                    if opponent_team and opponent_team.team_id != team.team_id:
                        # Simulate game
                        team_score = self.simulate_roster_score(team)
                        opp_score = self.simulate_roster_score(opponent_team)

                        if team_score > opp_score:
                            season_wins[team.team_id] += 1

            # Determine playoff teams
            sorted_teams = sorted(season_wins.items(), key=lambda x: x[1], reverse=True)
            playoff_teams = [tid for tid, _ in sorted_teams[:self.league.settings.playoff_team_count]]

            # Record wins
            for team_id, wins in season_wins.items():
                results[team_id]['projected_wins'] += wins

            # Record playoff appearances
            for team_id in playoff_teams:
                results[team_id]['playoff_odds'] += 1

            # Simulate playoffs
            if len(playoff_teams) >= 2:
                champ_id = self._simulate_playoff_bracket(playoff_teams)
                results[champ_id]['championship_odds'] += 1

        # Convert to averages and percentages
        for team_id in results:
            results[team_id]['projected_wins'] /= self.num_simulations
            results[team_id]['playoff_odds'] = results[team_id]['playoff_odds'] / self.num_simulations * 100
            results[team_id]['championship_odds'] = results[team_id]['championship_odds'] / self.num_simulations * 100

        return results

    def _simulate_playoff_bracket(self, playoff_team_ids: List[int]) -> int:
        """Simulate playoff bracket"""
        teams = playoff_team_ids.copy()

        while len(teams) > 1:
            winners = []
            for i in range(0, len(teams), 2):
                if i + 1 >= len(teams):
                    winners.append(teams[i])
                    continue

                team1 = next(t for t in self.league.teams if t.team_id == teams[i])
                team2 = next(t for t in self.league.teams if t.team_id == teams[i+1])

                score1 = self.simulate_roster_score(team1)
                score2 = self.simulate_roster_score(team2)

                winner = teams[i] if score1 > score2 else teams[i+1]
                winners.append(winner)

            teams = winners

        return teams[0]
