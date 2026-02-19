#!/usr/bin/env python3
"""
Fantasy Football Decision Maker CLI

A comprehensive tool for making fantasy football decisions using Monte Carlo
simulation and Gaussian Mixture Models.

Usage:
    python fantasy_decision_maker.py --league-id YOUR_LEAGUE_ID --team-id YOUR_TEAM_ID

For private leagues, you'll need to provide ESPN cookies:
    python fantasy_decision_maker.py --league-id ID --team-id ID --swid "YOUR_SWID" --espn-s2 "YOUR_ESPN_S2"
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from espn_api.football import League
from .advanced_simulator import AdvancedFantasySimulator
from .league_context import build_league_context
from .monte_carlo import MonteCarloSimulator


class FantasyDecisionMaker:
    """Main class for fantasy football decision making"""

    def __init__(
        self,
        league_id: int,
        team_id: int,
        year: int,
        swid: Optional[str] = None,
        espn_s2: Optional[str] = None,
        cache_dir: str = '.cache',
        num_simulations: int = 10000,
        alpha_mode: bool = False,
    ):
        """
        Initialize decision maker

        Args:
            league_id: ESPN league ID
            team_id: Your team ID
            year: Season year
            swid: ESPN SWID cookie for private leagues
            espn_s2: ESPN S2 cookie for private leagues
            cache_dir: Directory for caching
            num_simulations: Number of Monte Carlo simulations
            alpha_mode: Enable alpha-layer season simulation output
        """
        self.league_id = league_id
        self.team_id = team_id
        self.year = year
        self.cache_dir = cache_dir
        self.num_simulations = num_simulations
        self.alpha_mode = alpha_mode

        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)

        print(f"📊 Loading league {league_id} for {year}...")
        self.league = League(
            league_id=league_id,
            year=year,
            espn_s2=espn_s2,
            swid=swid
        )

        print(f"🎯 Finding your team (ID: {team_id})...")
        self.my_team = next((t for t in self.league.teams if t.team_id == team_id), None)

        if not self.my_team:
            raise ValueError(f"Team ID {team_id} not found in league")

        print(f"✅ Found team: {self.my_team.team_name}")
        print(f"📈 Record: {self.my_team.wins}-{self.my_team.losses}")

        # Initialize simulator
        print(f"\n🔬 Initializing advanced simulator with {num_simulations:,} simulations...")
        print("   Training player performance models (this may take a minute)...")
        self.simulator = AdvancedFantasySimulator(
            league=self.league,
            num_simulations=num_simulations,
            cache_dir=cache_dir,
            use_gmm=True
        )
        print("✅ Simulator ready!\n")

        self.alpha_simulator = None
        if self.alpha_mode:
            print("🧠 Enabling alpha layer for season simulations...")
            self.alpha_simulator = MonteCarloSimulator(
                league=self.league,
                num_simulations=num_simulations,
                alpha_mode=True,
            )
            print("✅ Alpha simulator ready!\n")

    def _get_monte_carlo_simulator(self) -> MonteCarloSimulator:
        if self.alpha_simulator is None:
            self.alpha_simulator = MonteCarloSimulator(
                league=self.league,
                num_simulations=self.num_simulations,
                alpha_mode=self.alpha_mode,
            )
        return self.alpha_simulator

    def analyze_current_matchup(self):
        """Analyze current week's matchup"""
        print("=" * 80)
        print(f"📅 WEEK {self.league.current_week} MATCHUP ANALYSIS")
        print("=" * 80)

        # Find current opponent
        opponent_id = self.my_team.schedule[self.league.current_week - 1]
        if isinstance(opponent_id, int):
            opponent = next((t for t in self.league.teams if t.team_id == opponent_id), None)
        else:
            opponent = opponent_id

        if not opponent or opponent.team_id == self.my_team.team_id:
            print("❌ No matchup this week (bye week)")
            return

        print(f"\n{self.my_team.team_name} vs {opponent.team_name}")
        print(f"Your Record: {self.my_team.wins}-{self.my_team.losses}")
        print(f"Their Record: {opponent.wins}-{opponent.losses}\n")

        # Run simulation
        print(f"🎲 Running {self.num_simulations:,} matchup simulations...")
        results = self.simulator.simulate_matchup(
            self.my_team,
            opponent,
            week=self.league.current_week
        )

        # Display results
        print(f"\n📊 SIMULATION RESULTS")
        print(f"{'─' * 80}")
        print(f"\n{self.my_team.team_name}:")
        print(f"  Win Probability: {results['team1_win_probability']:.1f}%")
        print(f"  Projected Score: {results['team1_avg_score']:.1f} ± {results['team1_score_std']:.1f}")
        print(f"  Score Range (10th-90th percentile): {results['team1_score_range'][0]:.1f} - {results['team1_score_range'][1]:.1f}")

        print(f"\n{opponent.team_name}:")
        print(f"  Win Probability: {results['team2_win_probability']:.1f}%")
        print(f"  Projected Score: {results['team2_avg_score']:.1f} ± {results['team2_score_std']:.1f}")
        print(f"  Score Range (10th-90th percentile): {results['team2_score_range'][0]:.1f} - {results['team2_score_range'][1]:.1f}")

        # Recommendation
        print(f"\n💡 OUTLOOK:")
        win_prob = results['team1_win_probability']
        if win_prob > 70:
            print(f"   🟢 Strong favorite - {win_prob:.0f}% chance to win")
        elif win_prob > 55:
            print(f"   🟡 Slight favorite - {win_prob:.0f}% chance to win")
        elif win_prob > 45:
            print(f"   ⚪ Toss-up - {win_prob:.0f}% chance to win")
        else:
            print(f"   🔴 Underdog - {win_prob:.0f}% chance to win")

        print()

    def analyze_free_agents(self, top_n: int = 10):
        """Analyze and recommend free agents"""
        print("=" * 80)
        print("🆓 FREE AGENT ANALYSIS (REST OF SEASON)")
        print("=" * 80)

        print(f"\n📥 Fetching free agents...")
        free_agents = self.league.free_agents(size=100)

        print(f"🔍 Analyzing {len(free_agents)} free agents with ROS schedule awareness...\n")
        recommendations = self.simulator.recommend_free_agents(
            self.my_team,
            free_agents,
            top_n=top_n,
            use_ros=True
        )

        if not recommendations:
            print("✅ No significant free agent upgrades available")
            return

        # Create DataFrame for display
        uses_ros = recommendations[0].get('uses_ros', False) if recommendations else False
        ros_label = " (ROS)" if uses_ros else ""

        data = []
        for i, rec in enumerate(recommendations, 1):
            # Show both ROS and season avg if using ROS
            if rec.get('uses_ros', False):
                fa_display = f"{rec['fa_projected_avg']:.1f}"
                drop_display = f"{rec['drop_projected_avg']:.1f}"
                # Add season avg in parentheses if different
                if abs(rec['fa_projected_avg'] - rec['fa_season_avg']) > 0.5:
                    fa_display += f" ({rec['fa_season_avg']:.1f})"
                if rec['drop_projected_avg'] > 0 and abs(rec['drop_projected_avg'] - rec['drop_season_avg']) > 0.5:
                    drop_display += f" ({rec['drop_season_avg']:.1f})"
            else:
                fa_display = f"{rec['fa_projected_avg']:.1f}"
                drop_display = f"{rec['drop_projected_avg']:.1f}"

            data.append({
                'Rank': i,
                'Player': rec['player'].name,
                'Pos': rec['position'],
                'Value Added': f"+{rec['value_added']:.1f}",
                f'ROS Avg': fa_display,
                'Drop': rec['drop_candidate'][:20],
                f'Drop ROS': drop_display,
                'Priority': rec['priority'],
                'Own %': f"{rec['ownership_pct']:.1f}%"
            })

        df = pd.DataFrame(data)
        print(f"🎯 TOP FREE AGENT RECOMMENDATIONS{ros_label}:")
        if uses_ros:
            print("   (ROS values shown, season avg in parentheses if significantly different)\n")
        else:
            print()
        print(df.to_string(index=False))
        print()

    def analyze_trades(self, max_opportunities: int = 5):
        """Find and analyze trade opportunities"""
        print("=" * 80)
        print("🔄 TRADE OPPORTUNITY ANALYSIS (REST OF SEASON)")
        print("=" * 80)

        print(f"\n🔍 Searching for realistic trade opportunities...")
        print("   (Using ROS projections with schedule-aware matchup difficulty)\n")

        opportunities = self.simulator.find_trade_opportunities(
            self.my_team,
            min_advantage=3.0,  # Minimum 3 point advantage
            max_trades_per_team=2,
            min_acceptance_probability=30.0,  # At least 30% chance of acceptance
            use_ros=True  # Use rest of season projections
        )

        if not opportunities:
            print("❌ No favorable trade opportunities found")
            return

        print(f"✅ Found {len(opportunities)} potential trades\n")

        for i, opp in enumerate(opportunities[:max_opportunities], 1):
            print(f"{'─' * 80}")
            print(f"TRADE #{i}: with {opp['other_team']}")
            print(f"{'─' * 80}")
            print(f"\n  You Give:    {', '.join(opp['give'])}")
            print(f"  You Receive: {', '.join(opp['receive'])}")

            analysis = opp['analysis']
            ros_indicator = " (ROS)" if analysis.get('uses_ros_projections', False) else ""
            weeks_rem = analysis.get('weeks_remaining', 'N/A')

            print(f"\n  📊 Analysis{ros_indicator}:")
            print(f"     Weeks Remaining:        {weeks_rem}")
            print(f"     Your Value Change:      {analysis['my_value_change']:+.1f} pts/week")
            print(f"     Their Value Change:     {analysis['their_value_change']:+.1f} pts/week")
            print(f"     Advantage Margin:       {analysis['advantage_margin']:+.1f} pts/week")
            print(f"     Points Added Per Week:  {analysis['projected_points_added_per_week']:+.1f} pts")
            print(f"     Acceptance Probability: {analysis['acceptance_probability']:.0f}%")
            print(f"     Recommendation:         {analysis['recommendation']}")
            print(f"     Confidence:             {analysis['confidence']:.0f}%")

            # Visual indicator for acceptance probability
            accept_prob = analysis['acceptance_probability']
            if accept_prob >= 70:
                print(f"\n  🟢 REALISTIC TRADE: High chance of acceptance ({accept_prob:.0f}%)")
            elif accept_prob >= 40:
                print(f"\n  🟡 MODERATE TRADE: Fair chance of acceptance ({accept_prob:.0f}%)")
            elif accept_prob >= 20:
                print(f"\n  🟠 RISKY TRADE: Low chance of acceptance ({accept_prob:.0f}%)")
            else:
                print(f"\n  🔴 UNREALISTIC: Very unlikely to be accepted ({accept_prob:.0f}%)")

            if analysis['asymmetric_advantage'] and analysis['is_realistic']:
                print(f"  ✅ ASYMMETRIC & REALISTIC: You gain more value AND they might accept!")
            elif analysis['asymmetric_advantage']:
                print(f"  ⚠️  ASYMMETRIC BUT UNFAIR: You gain much more, unlikely to be accepted")
            print()

    def analyze_season_outlook(self):
        """Analyze rest of season outlook"""
        print("=" * 80)
        print("🏆 REST OF SEASON OUTLOOK")
        print("=" * 80)

        print(f"\n🎲 Simulating rest of season ({self.num_simulations:,} simulations)...")
        if self.alpha_mode and self.alpha_simulator:
            results = self.alpha_simulator.run_simulations(explain=True)
            meta = results.pop("_meta", {})
            print(
                f"   Alpha mode: {meta.get('alpha_mode', False)} | "
                f"Ratings source: {meta.get('ratings_source', 'unknown')}"
            )
        else:
            results = self.simulator.simulate_season_rest_of_season()

        # Create standings DataFrame
        data = []
        for team in self.league.teams:
            team_results = results[team.team_id]
            projected_wins = team_results['avg_wins'] if self.alpha_mode else team_results['projected_wins']
            data.append({
                'Team': team.team_name[:25],
                'Current': f"{team.wins}-{team.losses}",
                'Proj Wins': f"{projected_wins:.1f}",
                'Playoff %': f"{team_results['playoff_odds']:.1f}%",
                'Ship %': f"{team_results['championship_odds']:.1f}%"
            })

        # Sort by projected wins
        df = pd.DataFrame(data)
        df = df.sort_values('Proj Wins', ascending=False)

        print(f"\n📊 PROJECTED STANDINGS:\n")
        print(df.to_string(index=False))

        # Highlight my team
        my_results = results[self.team_id]
        print(f"\n{'─' * 80}")
        print(f"YOUR TEAM: {self.my_team.team_name}")
        print(f"{'─' * 80}")
        print(f"  Current Record:        {self.my_team.wins}-{self.my_team.losses}")
        if self.alpha_mode:
            print(f"  Projected Final Wins:  {my_results['avg_wins']:.1f}")
        else:
            print(f"  Projected Final Wins:  {my_results['projected_wins']:.1f}")
        print(f"  Playoff Odds:          {my_results['playoff_odds']:.1f}%")
        print(f"  Championship Odds:     {my_results['championship_odds']:.1f}%")
        print()

    def generate_weekly_report(self, output_file: Optional[str] = None):
        """Generate comprehensive weekly report"""
        # Create reports directory if it doesn't exist
        import os
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)

        if output_file is None:
            output_file = os.path.join(reports_dir, f"weekly_report_week{self.league.current_week}_{datetime.now().strftime('%Y%m%d')}.txt")

        print("=" * 80)
        print(f"📝 GENERATING WEEKLY REPORT")
        print("=" * 80)
        print()

        # Redirect output to file
        import sys
        original_stdout = sys.stdout

        with open(output_file, 'w') as f:
            sys.stdout = f

            print(f"FANTASY FOOTBALL WEEKLY REPORT")
            print(f"League: {self.league_id}")
            print(f"Team: {self.my_team.team_name}")
            print(f"Week: {self.league.current_week}")
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Simulations: {self.num_simulations:,}")
            print("\n")

            # Matchup Analysis
            self.analyze_current_matchup()

            # Season Outlook
            self.analyze_season_outlook()

            # Free Agents
            self.analyze_free_agents(top_n=10)

            # Trades
            self.analyze_trades(max_opportunities=5)

        sys.stdout = original_stdout

        print(f"✅ Report saved to: {output_file}\n")

    def analyze_historical_opponents(
        self,
        lookback_seasons: int = 3,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        include_playoffs: bool = False,
        output_json: Optional[str] = None,
        swid: Optional[str] = None,
        espn_s2: Optional[str] = None,
        context_path: Optional[str] = None,
    ) -> dict:
        print("=" * 80)
        print("📚 HISTORICAL OPPONENT TENDENCY BACKTEST")
        print("=" * 80)

        config = {
            "league_id": self.league_id,
            "team_id": self.team_id,
            "year": self.year,
            "lookback_seasons": lookback_seasons,
            "start_year": start_year,
            "end_year": end_year,
            "include_playoffs": include_playoffs,
            "swid": swid,
            "espn_s2": espn_s2,
        }
        if context_path:
            config["context_path"] = context_path

        simulator = self._get_monte_carlo_simulator()
        results = simulator.run_historical_opponent_backtest(config=config)

        window = results.get("analysis_window", {})
        print(f"\nYears Requested: {window.get('years_requested', [])}")
        print(f"Years Analyzed:  {window.get('years_analyzed', [])}")
        skipped = window.get("years_skipped", [])
        if skipped:
            print(f"Years Skipped:   {skipped}")

        opponents = results.get("opponents", [])
        print(f"\nOpponents analyzed: {len(opponents)}")
        for report in opponents[:10]:
            metrics = report.get("quant_metrics", {})
            confidence = report.get("confidence", {})
            print(
                f"- {report.get('opponent_team_name', 'Unknown')}: "
                f"games={metrics.get('games_sampled', 0)} "
                f"win_rate_vs_you={metrics.get('win_rate_vs_you', 0.0):.2f} "
                f"high_ceiling_rate={metrics.get('high_ceiling_rate', 0.0):.2f} "
                f"confidence={confidence.get('confidence_band', 'low')}"
            )
            print(f"  tags={', '.join(report.get('qualitative_tags', []))}")
            print(f"  summary={report.get('narrative_summary', '')}")

        warnings = results.get("warnings", [])
        if warnings:
            print("\nWarnings:")
            for warning in warnings[:20]:
                print(f"  - {warning}")

        if output_json:
            output_dir = os.path.dirname(output_json)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_json, "w") as file_obj:
                json.dump(results, file_obj, indent=2, sort_keys=True)
            print(f"\n✅ Historical backtest JSON saved to: {output_json}")

        print()
        return results

    def run_interactive(self):
        """Run interactive decision-making session"""
        while True:
            print("\n" + "=" * 80)
            print("🏈 FANTASY FOOTBALL DECISION MAKER")
            print("=" * 80)
            print(f"\nLeague: {self.league_id} | Team: {self.my_team.team_name} | Week: {self.league.current_week}")
            print(f"\nWhat would you like to analyze?")
            print("  1. Current Week Matchup")
            print("  2. Free Agent Recommendations")
            print("  3. Trade Opportunities")
            print("  4. Rest of Season Outlook")
            print("  5. Generate Full Weekly Report")
            print("  6. Exit")

            choice = input("\nEnter choice (1-6): ").strip()

            if choice == '1':
                self.analyze_current_matchup()
            elif choice == '2':
                self.analyze_free_agents()
            elif choice == '3':
                self.analyze_trades()
            elif choice == '4':
                self.analyze_season_outlook()
            elif choice == '5':
                self.generate_weekly_report()
            elif choice == '6':
                print("\n👋 Goodbye! Good luck this week!\n")
                break
            else:
                print("\n❌ Invalid choice. Please enter 1-6.")

            input("\nPress Enter to continue...")


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def build_context_from_cli(
    *,
    league_id: int,
    year: int,
    swid: Optional[str],
    espn_s2: Optional[str],
    context_dir: str,
    lookback_seasons: int,
    start_year: Optional[int],
    end_year: Optional[int],
    full_refresh: bool,
    output_summary_json: Optional[str] = None,
) -> dict:
    print("=" * 80)
    print("🧱 BUILDING LEAGUE CONTEXT")
    print("=" * 80)
    result = build_league_context(
        {
            "league_id": league_id,
            "year": year,
            "swid": swid,
            "espn_s2": espn_s2,
            "context_dir": context_dir,
            "lookback_seasons": lookback_seasons,
            "start_year": start_year,
            "end_year": end_year,
            "full_refresh": full_refresh,
        }
    )

    print(f"\nContext Root:      {result.get('context_root')}")
    print(f"Sync Mode:         {result.get('sync_mode')}")
    print(f"Seasons Requested: {result.get('seasons_requested')}")
    print(f"Seasons Synced:    {result.get('seasons_synced')}")
    skipped = result.get("seasons_skipped", [])
    if skipped:
        print(f"Seasons Skipped:   {skipped}")
    warnings = result.get("warnings", [])
    if warnings:
        print("\nWarnings:")
        for warning in warnings[:20]:
            print(f"  - {warning}")

    if output_summary_json:
        output_path = Path(output_summary_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True))
        print(f"\n✅ Context summary saved to: {output_summary_json}")
    print()
    return result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Fantasy Football Decision Maker - Make smarter decisions with Monte Carlo simulation and GMM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using config file
  uv run fantasy-decision-maker --config config.json

  # Public league (command line)
  uv run fantasy-decision-maker --league-id 123456 --team-id 1

  # Private league
  uv run fantasy-decision-maker --league-id 123456 --team-id 1 \\
      --swid "{YOUR-SWID-HERE}" --espn-s2 "{YOUR-ESPN-S2-HERE}"

  # Quick report generation (non-interactive)
  uv run fantasy-decision-maker --league-id 123456 --team-id 1 --report-only

  # Alpha-layer season simulation output
  uv run fantasy-decision-maker --league-id 123456 --team-id 1 --alpha-mode --report-only

  # Historical opponent tendencies
  uv run fantasy-decision-maker --league-id 123456 --team-id 1 --historical-backtest --lookback-seasons 3

  # Build persistent league context
  uv run fantasy-decision-maker --config config.json --build-context --context-lookback-seasons 3

Getting ESPN Cookies for Private Leagues:
  1. Log into ESPN Fantasy Football in your browser
  2. Open Developer Tools (F12)
  3. Go to Application/Storage > Cookies
  4. Find 'SWID' and 'espn_s2' cookies
  5. Copy their values (including curly braces for SWID)
        """
    )

    parser.add_argument('--config', type=str, default=None,
                        help='Path to config JSON file (overrides other args)')
    parser.add_argument('--league-id', type=int, default=None,
                        help='ESPN League ID')
    parser.add_argument('--team-id', type=int, default=None,
                        help='Your Team ID')
    parser.add_argument('--year', type=int, default=None,
                        help='Season year (default: current year)')
    parser.add_argument('--swid', type=str, default=None,
                        help='ESPN SWID cookie (for private leagues)')
    parser.add_argument('--espn-s2', type=str, default=None,
                        help='ESPN S2 cookie (for private leagues)')
    parser.add_argument('--simulations', type=int, default=None,
                        help='Number of Monte Carlo simulations (default: 10000)')
    parser.add_argument('--cache-dir', type=str, default=None,
                        help='Cache directory for player models (default: .cache)')
    parser.add_argument('--report-only', action='store_true',
                        help='Generate report and exit (non-interactive)')
    parser.add_argument('--alpha-mode', action='store_true',
                        help='Enable alpha-layer season simulation output')
    parser.add_argument('--historical-backtest', action='store_true',
                        help='Run historical opponent tendency backtest and exit')
    parser.add_argument('--lookback-seasons', type=int, default=3,
                        help='Historical backtest lookback (default: 3 seasons)')
    parser.add_argument('--start-year', type=int, default=None,
                        help='Historical backtest start year (inclusive)')
    parser.add_argument('--end-year', type=int, default=None,
                        help='Historical backtest end year (inclusive)')
    parser.add_argument('--include-playoffs', action='store_true',
                        help='Include playoff weeks in historical backtest')
    parser.add_argument('--historical-output-json', type=str, default=None,
                        help='Optional JSON path for historical backtest output')
    parser.add_argument('--build-context', action='store_true',
                        help='Build/update persistent league context and exit')
    parser.add_argument('--context-dir', type=str, default='data/league_context',
                        help='Root directory for league context data')
    parser.add_argument('--context-lookback-seasons', type=int, default=3,
                        help='Context lookback (prior seasons; current year included)')
    parser.add_argument('--context-start-year', type=int, default=None,
                        help='Context start year (inclusive)')
    parser.add_argument('--context-end-year', type=int, default=None,
                        help='Context end year (inclusive)')
    parser.add_argument('--context-full-refresh', action='store_true',
                        help='Force full context rebuild for selected seasons')
    parser.add_argument('--use-context', action='store_true',
                        help='Use local context store for historical backtest when available')
    parser.add_argument('--context-output-summary-json', type=str, default=None,
                        help='Optional JSON path for context build summary')

    args = parser.parse_args()

    # Load from config file if provided
    if args.config:
        if not os.path.exists(args.config):
            print(f"❌ Error: Config file not found: {args.config}")
            return 1

        try:
            config = load_config(args.config)

            # Extract values from config
            league_config = config.get('league', {})
            sim_config = config.get('simulation', {})

            # Use config values, allow CLI args to override
            league_id = args.league_id or league_config.get('league_id')
            team_id = args.team_id or league_config.get('team_id')
            year = args.year or league_config.get('year', datetime.now().year)
            swid = args.swid or league_config.get('swid')
            espn_s2 = args.espn_s2 or league_config.get('espn_s2')
            num_simulations = args.simulations or sim_config.get('num_simulations', 10000)
            cache_dir = args.cache_dir or sim_config.get('cache_dir', '.cache')
            alpha_mode = args.alpha_mode or sim_config.get('alpha_mode', False)

            print(f"📄 Loaded config from: {args.config}")

        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in config file: {e}")
            return 1
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return 1
    else:
        # Use command-line arguments
        league_id = args.league_id
        team_id = args.team_id
        year = args.year or datetime.now().year
        swid = args.swid
        espn_s2 = args.espn_s2
        num_simulations = args.simulations or 10000
        cache_dir = args.cache_dir or '.cache'
        alpha_mode = args.alpha_mode

    # Validate required parameters
    if league_id is None:
        print("❌ Error: --league-id is required (or specify --config)")
        return 1
    if team_id is None and not args.build_context:
        print("❌ Error: --team-id is required (or specify --config)")
        return 1

    if args.build_context:
        try:
            build_context_from_cli(
                league_id=league_id,
                year=year,
                swid=swid,
                espn_s2=espn_s2,
                context_dir=args.context_dir,
                lookback_seasons=args.context_lookback_seasons,
                start_year=args.context_start_year,
                end_year=args.context_end_year,
                full_refresh=args.context_full_refresh,
                output_summary_json=args.context_output_summary_json,
            )
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return 1
        return 0

    # Create decision maker
    try:
        dm = FantasyDecisionMaker(
            league_id=league_id,
            team_id=team_id,
            year=year,
            swid=swid,
            espn_s2=espn_s2,
            cache_dir=cache_dir,
            num_simulations=num_simulations,
            alpha_mode=alpha_mode,
        )

        if args.historical_backtest:
            context_path = None
            if args.use_context:
                context_path = str(Path(args.context_dir) / str(league_id))
            dm.analyze_historical_opponents(
                lookback_seasons=args.lookback_seasons,
                start_year=args.start_year,
                end_year=args.end_year,
                include_playoffs=args.include_playoffs,
                output_json=args.historical_output_json,
                swid=swid,
                espn_s2=espn_s2,
                context_path=context_path,
            )
        elif args.report_only:
            # Generate report and exit
            dm.generate_weekly_report()
        else:
            # Run interactive mode
            dm.run_interactive()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
