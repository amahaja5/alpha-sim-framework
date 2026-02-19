"""
Player Performance Modeling using Gaussian Mixture Models

This module provides player-level performance prediction using GMM
to model different player states (hot streak, cold streak, normal)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.mixture import GaussianMixture
import pickle
import os
from datetime import datetime, timedelta


class PlayerPerformanceModel:
    """Models player performance using Gaussian Mixture Models"""

    def __init__(self, n_components: int = 3, cache_dir: str = '.cache'):
        """
        Initialize player performance model

        Args:
            n_components: Number of components in GMM (default 3: hot, normal, cold)
            cache_dir: Directory to cache player models
        """
        self.n_components = n_components
        self.cache_dir = cache_dir
        self.models: Dict[int, GaussianMixture] = {}  # playerId -> GMM
        self.player_states: Dict[int, Dict] = {}  # playerId -> state info

        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, player_id: int, year: int) -> str:
        """Get cache file path for a player"""
        return os.path.join(self.cache_dir, f'player_{player_id}_{year}.pkl')

    def _is_cache_valid(self, cache_path: str, max_age_hours: int = 24) -> bool:
        """Check if cache file is still valid"""
        if not os.path.exists(cache_path):
            return False

        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        return datetime.now() - file_time < timedelta(hours=max_age_hours)

    def train_model(self, player, year: int, force_retrain: bool = False) -> Optional[GaussianMixture]:
        """
        Train GMM for a player based on historical performance

        Args:
            player: Player object with stats
            year: Current season year
            force_retrain: Force retraining even if cache exists

        Returns:
            Trained GaussianMixture model or None if insufficient data
        """
        cache_path = self._get_cache_path(player.playerId, year)

        # Check cache first
        if not force_retrain and self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    self.models[player.playerId] = cached_data['model']
                    self.player_states[player.playerId] = cached_data['state']
                    return self.models[player.playerId]
            except Exception:
                pass  # Cache load failed, retrain

        # Get historical weekly scores
        weekly_scores = []
        for week, stats in player.stats.items():
            if week == 0:  # Skip season totals
                continue
            points = stats.get('points', 0)
            if points > 0:  # Only include weeks where player played
                weekly_scores.append(points)

        # Need at least 5 weeks of data for meaningful GMM
        if len(weekly_scores) < 5:
            return None

        # Reshape for sklearn
        X = np.array(weekly_scores).reshape(-1, 1)

        # Train GMM
        try:
            gmm = GaussianMixture(
                n_components=min(self.n_components, len(weekly_scores) // 2),
                covariance_type='full',
                max_iter=100,
                random_state=42
            )
            gmm.fit(X)

            # Classify components as hot/normal/cold based on means
            component_means = gmm.means_.flatten()
            sorted_indices = np.argsort(component_means)

            # Create state mapping
            state_info = {
                'means': component_means,
                'weights': gmm.weights_,
                'covariances': gmm.covariances_,
                'cold_component': sorted_indices[0] if len(sorted_indices) > 0 else 0,
                'normal_component': sorted_indices[len(sorted_indices)//2] if len(sorted_indices) > 1 else 0,
                'hot_component': sorted_indices[-1] if len(sorted_indices) > 0 else 0,
                'recent_scores': weekly_scores[-3:],  # Last 3 weeks
                'season_avg': np.mean(weekly_scores),
                'season_std': np.std(weekly_scores)
            }

            # Determine current state based on recent performance
            if len(weekly_scores) >= 3:
                recent_avg = np.mean(weekly_scores[-3:])
                if recent_avg > state_info['season_avg'] + 0.5 * state_info['season_std']:
                    state_info['current_state'] = 'hot'
                elif recent_avg < state_info['season_avg'] - 0.5 * state_info['season_std']:
                    state_info['current_state'] = 'cold'
                else:
                    state_info['current_state'] = 'normal'
            else:
                state_info['current_state'] = 'normal'

            # Cache the model
            self.models[player.playerId] = gmm
            self.player_states[player.playerId] = state_info

            try:
                with open(cache_path, 'wb') as f:
                    pickle.dump({'model': gmm, 'state': state_info}, f)
            except Exception:
                pass  # Cache save failed, not critical

            return gmm

        except Exception:
            return None

    def predict_performance(
        self,
        player,
        n_samples: int = 1,
        use_state_bias: bool = True
    ) -> np.ndarray:
        """
        Predict player performance using GMM

        Args:
            player: Player object
            n_samples: Number of samples to generate
            use_state_bias: Weight sampling towards current state (hot/cold/normal)

        Returns:
            Array of predicted point values
        """
        # Check if model exists for this player
        if player.playerId not in self.models:
            # Fallback to simple normal distribution
            mean = player.projected_avg_points if hasattr(player, 'projected_avg_points') and player.projected_avg_points > 0 else player.avg_points
            std = mean * 0.25  # 25% standard deviation
            return np.random.normal(mean, std, n_samples)

        gmm = self.models[player.playerId]
        state = self.player_states[player.playerId]

        # Sample from GMM
        if use_state_bias and 'current_state' in state:
            # Bias sampling towards current state
            current_state = state['current_state']

            if current_state == 'hot':
                component_idx = state['hot_component']
            elif current_state == 'cold':
                component_idx = state['cold_component']
            else:
                component_idx = state['normal_component']

            # 70% from current state, 30% from other states
            n_current = int(n_samples * 0.7)
            n_other = n_samples - n_current

            # Sample from current state component
            mean = gmm.means_[component_idx][0]
            std = np.sqrt(gmm.covariances_[component_idx][0][0])
            current_samples = np.random.normal(mean, std, n_current)

            # Sample from full GMM for remaining
            other_samples, _ = gmm.sample(n_other)
            other_samples = other_samples.flatten()

            samples = np.concatenate([current_samples, other_samples])
        else:
            # Pure GMM sampling
            samples, _ = gmm.sample(n_samples)
            samples = samples.flatten()

        # Ensure non-negative predictions
        samples = np.maximum(samples, 0)

        return samples

    def get_player_variance(self, player) -> float:
        """
        Get player's performance variance

        Args:
            player: Player object

        Returns:
            Standard deviation of player performance
        """
        if player.playerId in self.player_states:
            return self.player_states[player.playerId]['season_std']

        # Fallback: estimate based on position
        mean = player.projected_avg_points if hasattr(player, 'projected_avg_points') and player.projected_avg_points > 0 else player.avg_points
        return mean * 0.25

    def get_player_state(self, player) -> Dict:
        """Get current state information for a player"""
        return self.player_states.get(player.playerId, {})

    def bulk_train(self, players: List, year: int, force_retrain: bool = False) -> Dict[int, bool]:
        """
        Train models for multiple players

        Args:
            players: List of Player objects
            year: Season year
            force_retrain: Force retraining even if cache exists

        Returns:
            Dict mapping player_id to training success
        """
        results = {}
        for player in players:
            model = self.train_model(player, year, force_retrain)
            results[player.playerId] = model is not None
        return results
