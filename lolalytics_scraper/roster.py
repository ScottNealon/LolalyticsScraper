# Standard library
import functools
import os
from typing import Union

# Third party imports
import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text
from matplotlib.ticker import PercentFormatter

# Module imports
from lolalytics_scraper import CHAMPION_IDS, LOLALYTICS_DATA
from lolalytics_scraper.champion import Champion
from lolalytics_scraper.graph_util import add_hover_annotations


class Roster:
    def __init__(self):
        if len(LOLALYTICS_DATA) == 0:
            raise ValueError(
                "Unable to initialize Roster(): Missing LOLALYTICS DATA. Run lolalytics_scraper.load_data.update_lolalytics_champion_data(...)"
            )
        self._champions: dict[int, dict[str, Champion]] = {}
        self._create_champions()

    def _create_champions(self):
        for champion_id, champion_data in LOLALYTICS_DATA.items():
            for champion_role_data in champion_data.values():
                champion = Champion(champion_id, champion_role_data, self)
                self._champions.setdefault(champion_id, {})[champion.role] = champion

    @functools.cached_property
    def champions(self):
        return tuple(champion for champion_roles in self._champions.values() for champion in champion_roles.values())

    def get_valid_champions(
        self, role: str = None, min_champion_role_assignemnt_rate: float = 0.02, min_champion_pick_rate: float = 0.005
    ):
        return tuple(
            champion
            for champion in self.champions
            if (champion.role == role or role is None)
            and champion.pick_rate >= min_champion_pick_rate
            and champion.role_assignment >= min_champion_role_assignemnt_rate
        )

    def get_valid_champion_index(
        self, role: str = None, min_champion_role_assignemnt_rate: float = 0.02, min_champion_pick_rate: float = 0.005
    ):
        valid_champions = self.get_valid_champions(role, min_champion_role_assignemnt_rate, min_champion_pick_rate)
        for champion in self.champions:
            yield champion in valid_champions

    @functools.cached_property
    def pick_rates(self):
        return pd.Series({champion: champion.pick_rate for champion in self.champions})

    @functools.cached_property
    def raw_win_rates(self):
        return pd.Series({champion: champion.raw_win_rate for champion in self.champions})

    @functools.cached_property
    def rank_normalized_win_rates(self):
        return pd.Series({champion: champion.rank_normalized_win_rate for champion in self.champions})

    @functools.cached_property
    def matchup_normalized_win_rates(self):
        return pd.Series({champion: champion.matchup_normalized_win_rate for champion in self.champions})

    def get_champion_by_id(self, champion_id: int, role: str = None) -> Union[Champion, tuple[Champion]]:
        if role:
            return self._champions[champion_id][role.lower()]
        else:
            return self._champions[champion_id]

    def get_champion_by_name(self, champion_name: str, role: str = None) -> Union[Champion, tuple[Champion]]:
        return self.get_champion_by_id(CHAMPION_IDS[champion_name], role)

    def get_normalized_matchup_win_rates(self):
        return pd.DataFrame({champion: champion.normalized_matchup_win_rates for champion in self.champions})

    def get_raw_matchup_win_rates(self):
        return pd.DataFrame([champion.raw_matchup_win_rates for champion in self.champions])

    def get_blind_pick_win_rates(self, num_opponent_champions: int = 5):
        return pd.DataFrame(
            [champion.blind_expected_win_rate(num_opponent_champions) for champion in self.champions],
            index=self.champions,
        )

    def graph_matchup_normalized_win_rates(self):
        # Create and format figure
        figure, axes = plt.subplots()
        axes.margins(0.15)  # Zoom out slightly
        axes.grid(True)
        axes.set_xlabel("Rank Normalized Win Rate")
        axes.set_ylabel("Counter Abillity Impact on Win Rate")
        axes.xaxis.set_major_formatter(PercentFormatter())
        axes.yaxis.set_major_formatter(PercentFormatter())

        # Get and filter data
        xs = 100 * self.rank_normalized_win_rates
        ys = 100 * (self.rank_normalized_win_rates - self.matchup_normalized_win_rates)
        size = self.pick_rates
        xs = xs.loc[self.get_valid_champion_index()]
        ys = ys.loc[xs.index]
        size = size.loc[xs.index]

        # Normalize size of dots to most common being size 200 points^2.
        size = size * (200 / size.max())

        # Plot data
        axes.scatter(xs, ys, s=size)

        # Add labels to 20 outliers
        labels = []
        for champion in self.get_valid_champions():
            if (ys[champion] < ys).sum() < 10 or (ys[champion] > ys).sum() < 10:
                label = axes.text(xs[champion], ys[champion], str(champion))
                labels.append(label)
        figure.draw(figure.canvas.get_renderer())
        adjust_text(labels, arrowprops=dict(arrowstyle="->", color="k", lw=0.5))

        # Show
        plt.show(block=False)

    def graph_champion_matchup_comparison(self, champion_1: Champion, champion_2: Champion, lane_only: bool = True):
        # Create data
        champion_1_matchup = champion_1.raw_matchup_win_rates - champion_1.expected_matchup_win_rates
        champion_2_matchup = champion_2.raw_matchup_win_rates - champion_2.expected_matchup_win_rates
        champions = [
            champion
            for champion in self.get_valid_champions()
            if not lane_only or champion.role == champion_1.role or champion.role == champion_2.role
        ]

        # Comparison of win rates between champions, with positive values being champion 2 favored and negative being
        # champion 1 favored relative to their base win rates
        win_rate_differences = champion_2_matchup - champion_1_matchup

        # Comparison of win rates that are favorable for both champions
        win_rate_similarities = (champion_1_matchup + champion_2_matchup) / 2

        # Create and format figure
        figure, axes = plt.subplots()
        axes.margins(0.15)  # Zoom out slightly
        axes.grid(True)
        # axes.set_xlabel(f"{champion_1.name} Win Rates")
        # axes.set_ylabel(f"{champion_2.name} Win Rates")
        axes.set_xlabel(f"<-- {champion_1} Favored | {champion_2} Favored -->")
        axes.set_ylabel(f"<-- Bad for Both | Good for Both -->")
        axes.xaxis.set_major_formatter(PercentFormatter(1))
        axes.yaxis.set_major_formatter(PercentFormatter(1))

        # Determine size
        size = self.pick_rates * (200 / self.pick_rates.max())

        # Plot data
        # axes.scatter(
        #     [champion_1_matchup[champion] for champion in champions],
        #     [champion_2_matchup[champion] for champion in champions],
        #     s=[size[champion] for champion in champions],
        # )
        scatter = axes.scatter(
            [win_rate_differences[champion] for champion in champions],
            [win_rate_similarities[champion] for champion in champions],
            s=[size[champion] for champion in champions],
        )

        # Add labels to 20 outliers
        # labels = []
        # importance = ((champion_1_matchup * champion_2_matchup).abs() * self.pick_rates)[champions].sort_values(
        #     ascending=False
        # )
        # for champion, _ in importance.iloc[:20].items():
        #     label = axes.text(champion_1_matchup[champion], champion_2_matchup[champion], str(champion))
        #     labels.append(label)
        # figure.draw(figure.canvas.get_renderer())
        # adjust_text(labels, arrowprops=dict(arrowstyle="->", color="k", lw=0.5))

        # Center axes on zero
        x_low, x_high = axes.get_xlim()
        axes.set_xlim((min(x_low, -x_high), max(x_high, -x_low)))
        y_low, y_high = axes.get_ylim()
        axes.set_ylim(min(y_low, -y_high), max(y_high, -y_low))

        # Add hover over
        champion_names = [champion.name for champion in champions]
        add_hover_annotations(scatter, axes, figure, champion_names)

        # Show
        plt.show(block=False)

    def analyze_champion_pool(self, champion_pool: list[Champion], num_opponent_champions: int = 5):
        role = champion_pool[0].role

        # Verify all champions are for the same lane
        assert all(champion.role == role for champion in champion_pool)

        # Look at all opponents in lane
        matchups = {}
        for opponent_champion in self.get_valid_champions(role):
            counterpick_pool = [champion for champion in champion_pool if champion is not opponent_champion]
            opponent_win_rates = pd.Series(
                {
                    counterpick_champion: counterpick_champion.normalized_matchup_win_rates[opponent_champion]
                    for counterpick_champion in counterpick_pool
                }
            ).sort_values(ascending=False)
            best_counterpick = opponent_win_rates.index[0]
            best_counterpick_win_rate = opponent_win_rates[best_counterpick]
            best_counterpick_N = opponent_champion.normalized_matchup_N[best_counterpick]
            if len(counterpick_pool) > 1:
                second_best_counterpick = opponent_win_rates.index[1]
                second_best_counterpick_win_rate = opponent_win_rates[second_best_counterpick]
                second_best_counterpick_N = opponent_champion.normalized_matchup_N[second_best_counterpick]
            else:
                second_best_counterpick = None
                second_best_counterpick_win_rate = pd.NA
                second_best_counterpick_N = 0
            counterpick_win_rate_improvement = best_counterpick_win_rate - second_best_counterpick_win_rate

            best_counterpick_of_them_all: Champion = (
                pd.Series(
                    {
                        champion: 1 - opponent_champion.normalized_matchup_win_rates[champion]
                        for champion in self.get_valid_champions(role)
                    }
                )
                .sort_values(ascending=False)
                .index[0]
            )
            best_counterpick_possible_win_rate = best_counterpick_of_them_all.normalized_matchup_win_rates[
                opponent_champion
            ]
            remaining_win_rate_improvement = best_counterpick_possible_win_rate - best_counterpick_win_rate
            best_counterpick_possible = (
                f"{best_counterpick_of_them_all.name}: +{100*remaining_win_rate_improvement:.2f}%"
                if remaining_win_rate_improvement > 0
                else "None"
            )

            matchups[opponent_champion] = {
                "Opponent Pick Rate": opponent_champion.pick_rate,
                "Best Counterpick": best_counterpick,
                "Best Counterpick Win Rate": best_counterpick_win_rate,
                "Best Counterpick N": best_counterpick_N,
                "Second Best Counterpick": second_best_counterpick,
                "Second Best Counterpick Win Rate": second_best_counterpick_win_rate,
                "Second Best Counterpick N": second_best_counterpick_N,
                "Counterpick Win Rate Improvement": counterpick_win_rate_improvement,
                "Remaining Possible Improvement": best_counterpick_possible,
            }

        matchups_df = pd.DataFrame(matchups).transpose()  # .sort_values(by="Opponent Pick Rate", ascending=False)
        matchups_df.index.name = "Matchup"

        # Normalize pick rate
        matchups_df["Opponent Pick Rate"] = matchups_df["Opponent Pick Rate"] / matchups_df["Opponent Pick Rate"].sum()

        # Add column for comparison of matchup against overall win rate, and sort based on it
        mean_win_rate = (matchups_df["Opponent Pick Rate"] * matchups_df["Best Counterpick Win Rate"]).sum()
        matchup_vs_baseline = (
            matchups_df["Opponent Pick Rate"] * (matchups_df["Best Counterpick Win Rate"] - mean_win_rate)
        ).sort_values()
        matchups_df["Matchup Win Rate vs Baseline Impact"] = matchup_vs_baseline
        matchups_df = matchups_df.sort_values("Matchup Win Rate vs Baseline Impact")

        champion_pool_results = {}
        for champion in champion_pool:
            counterpick_matchups = matchups_df[matchups_df["Best Counterpick"] == champion]
            # Calculate how often you pick this champion as a counterpick
            counterpick_rate = counterpick_matchups["Opponent Pick Rate"].sum()
            if counterpick_rate > 0:
                # Calculate how often you win when you counterpick this champion
                counterpick_win_rate = (
                    counterpick_matchups["Opponent Pick Rate"] * counterpick_matchups["Best Counterpick Win Rate"]
                ).sum() / counterpick_rate
                # Calculate how much more often you win because this champion is now included in your champion pool
                counterpick_matchups_with_second_pick = counterpick_matchups[
                    ~counterpick_matchups["Second Best Counterpick Win Rate"].isna()
                ]
                marginal_win_rate_improvement = (
                    (
                        counterpick_matchups_with_second_pick["Opponent Pick Rate"]
                        * (
                            counterpick_matchups_with_second_pick["Best Counterpick Win Rate"]
                            - counterpick_matchups_with_second_pick["Second Best Counterpick Win Rate"]
                        )
                    ).sum()
                    if counterpick_rate > 0
                    else pd.NA
                )
                # Calculate how much more you win Per Match becuase this champion is now included in your champion pool
                marginal_win_rate_improvement_per_match = marginal_win_rate_improvement / counterpick_rate
                # Calculate how much more you win with this champion versus the champion's default win rate
                improvement_over_base_champion_win_rate = counterpick_win_rate - champion.raw_win_rate

            else:
                counterpick_win_rate = pd.NA
                marginal_win_rate_improvement = pd.NA
                marginal_win_rate_improvement_per_match = pd.NA
                improvement_over_base_champion_win_rate = pd.NA

            # Identify how often you are within 1% of being best counterpick
            almost_counterpick_rate = matchups_df[
                matchups_df["Best Counterpick Win Rate"] - 0.01
                <= champion.normalized_matchup_win_rates[matchups_df.index]
            ]["Opponent Pick Rate"].sum()

            # Identify best bans
            base_blind_expected_win_rate = champion.blind_expected_win_rate(num_opponent_champions)
            best_bans = champion.blind_pick_ban_win_rate_improvements(num_opponent_champions)
            best_bans_list = [
                f"{champion.name}: +{100 * (best_bans[champion] - base_blind_expected_win_rate):.2f}%"
                for champion in best_bans.index[:3]
            ]

            champion_pool_results[champion] = {
                "Counterpick Rate": counterpick_rate,
                "Within 1% Counterpick Rate": almost_counterpick_rate,
                "Counterpick Win Rate": counterpick_win_rate,
                "Marginal Win Rate Improvement": marginal_win_rate_improvement,
                "Marginal Win Rate Improvement Per Match": marginal_win_rate_improvement_per_match,
                "Improvement Over Base Champion Win Rate": improvement_over_base_champion_win_rate,
                "Blind Pick Base Win Rate": base_blind_expected_win_rate,
                "Best Bans": best_bans_list,
            }

        champion_pool_results_df = (
            pd.DataFrame(champion_pool_results)
            .transpose()
            .sort_values(by="Marginal Win Rate Improvement", ascending=False)
        )
        champion_pool_results_df.index.name = "Champion Pool"

        # Determine how good adding differen champions to pool would be
        candidate_champions = {}
        for candidate_champion in self.get_valid_champions(role):
            if candidate_champion in champion_pool:
                continue

            # Identify matchups where you could outperform current champion pool
            matchup_win_rates = candidate_champion.raw_matchup_win_rates[matchups_df.index]
            improvement_matchups = matchups_df[matchup_win_rates > matchups_df["Best Counterpick Win Rate"]]
            # Identify frequency of counterpick
            improvement_pick_rate = improvement_matchups["Opponent Pick Rate"].sum()
            if improvement_pick_rate > 0:
                # Identify win rate of counterpick
                improvement_win_rate = (
                    improvement_matchups["Opponent Pick Rate"] * matchup_win_rates[improvement_matchups.index]
                ).sum() / improvement_pick_rate
                # Identify improvement of win rate overall
                marginal_win_rate_improvement = (
                    improvement_matchups["Opponent Pick Rate"]
                    * (
                        matchup_win_rates[improvement_matchups.index]
                        - improvement_matchups["Best Counterpick Win Rate"]
                    )
                ).sum()
                # Identify improvement of win rate per match picked
                marginal_win_rate_improvement_per_match = marginal_win_rate_improvement / improvement_pick_rate
                # Calculate how much more you win with this champion versus the champion's default win rate
                improvement_over_base_champion_win_rate = improvement_win_rate - candidate_champion.raw_win_rate
                # Identify opponents with the biggest improvement against
                biggest_impact_opponents = (
                    (matchup_win_rates[improvement_matchups.index] - improvement_matchups["Best Counterpick Win Rate"])
                    * improvement_matchups["Opponent Pick Rate"]
                ).sort_values(ascending=False)
                biggest_impact_opponents_list = [
                    f'{champion.name}: +{100 * (matchup_win_rates[improvement_matchups.index] - improvement_matchups["Best Counterpick Win Rate"])[champion]:.2f}%'
                    for champion in biggest_impact_opponents.index[:3]
                ]
            else:
                improvement_win_rate = 0
                marginal_win_rate_improvement = 0
                marginal_win_rate_improvement_per_match = 0
                improvement_over_base_champion_win_rate = 0
                biggest_impact_opponents_list = []
            # Identify best ban
            base_blind_expected_win_rate = candidate_champion.blind_expected_win_rate(num_opponent_champions)
            best_bans = candidate_champion.blind_pick_ban_win_rate_improvements(num_opponent_champions)
            best_bans_list = [
                f"{champion.name}: +{100 * (best_bans[champion] - base_blind_expected_win_rate):.2f}%"
                for champion in best_bans.index[:3]
            ]

            candidate_champions[candidate_champion] = {
                "Counterpick Rate": improvement_pick_rate,
                "Counterpick Win Rate": improvement_win_rate,
                "Marginal Win Rate Improvement": marginal_win_rate_improvement,
                "Marginal Win Rate Improvement Per Match": marginal_win_rate_improvement_per_match,
                "Improvement Over Base Champion Win Rate": improvement_over_base_champion_win_rate,
                "Biggest Impact Against": biggest_impact_opponents_list,
                "Blind Pick Base Win Rate": base_blind_expected_win_rate,
                "Best Bans": best_bans_list,
            }

        candidate_champions_df = (
            pd.DataFrame(candidate_champions).transpose().sort_values(by="Counterpick Rate", ascending=False)
        )
        candidate_champions_df.index.name = "Candidate Champions"

        return champion_pool_results_df, matchups_df, candidate_champions_df
