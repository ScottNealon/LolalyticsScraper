import functools
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text
from matplotlib.ticker import PercentFormatter

from lolalytics_scraper import INVERSE_CHAMPION_IDS

if TYPE_CHECKING:
    from lolalytics_scraper.roster import Roster


def win_rate_to_elo(win_rate: float) -> float:
    win_rate = max(0, min(1, win_rate))
    if win_rate == 0:
        return -np.Inf
    elif win_rate == 1:
        return np.Inf
    else:
        return -400 * np.log10(1 / win_rate - 1)


def elo_to_win_rate(elo: float) -> float:
    return 1 / (1 + 10 ** (-elo / 400))


class Champion:
    def __init__(self, id: int, lolalytic_data: dict, roster: "Roster"):
        self.id = id
        self._lolalytics_data = lolalytic_data
        self._roster = roster
        self._format_lolaytic_data()

    def _format_lolaytic_data(self):
        for enemy_role in ["top", "jungle", "middle", "bottom", "support"]:
            if not (isinstance(self._lolalytics_data[f"enemy_{enemy_role}"], dict)):
                self._lolalytics_data[f"enemy_{enemy_role}"] = {
                    champion_id: {"matches": matches, "wins": wins, "win_rate": wins / matches}
                    for champion_id, matches, wins, _ in self._lolalytics_data[f"enemy_{enemy_role}"]
                }

    @property
    def name(self) -> str:
        return INVERSE_CHAMPION_IDS[self.id]

    @property
    def role(self) -> str:
        return self._lolalytics_data["header"]["lane"]

    @property
    def n(self) -> int:
        return self._lolalytics_data["header"]["n"]

    @property
    def raw_win_rate(self) -> float:
        return self._lolalytics_data["header"]["wr"] / 100

    @property
    def rank_normalized_win_rate(self) -> float:
        return self.raw_win_rate - (self._lolalytics_data["avgWinRate"] / 100 - 0.5)

    @property
    def pick_rate(self) -> float:
        """How often is this champion-role assignment picked"""
        return self._lolalytics_data["header"]["pr"] / 100

    @property
    def role_assignment(self) -> float:
        """How often, when this champion is picked, is it picked in this lane"""
        return self._lolalytics_data["nav"]["lanes"][self.role] / 100

    @functools.cached_property
    def raw_matchup_win_rates(self) -> dict["Champion" : dict[str]]:
        return pd.Series(
            {champion: self._get_raw_matchup_win_rate_by_champion(champion) for champion in self._roster.champions}
        )

    def _get_raw_matchup_win_rate_by_champion(self, champion: "Champion") -> float:
        return self._lolalytics_data[f"enemy_{champion.role}"].get(champion.id, {}).get("win_rate", np.nan)

    @functools.cached_property
    def normalized_matchup_win_rates(self) -> pd.Series:
        return pd.Series(
            {champion: self._get_normalized_matchup_by_champion(champion) for champion in self._roster.champions}
        )

    def _get_normalized_matchup_by_champion(self, champion: "Champion") -> float:
        return (
            self._get_raw_matchup_win_rate_by_champion(champion)
            + (1 - champion._get_raw_matchup_win_rate_by_champion(self))
        ) / 2

    @functools.cached_property
    def expected_matchup_win_rates(self) -> pd.Series:
        """Return naive matchup win rate based on only looking at other matchups, used for determining delta"""
        return pd.Series(
            {champion: self._get_expected_matchup_win_rate(champion) for champion in self._roster.champions}
        )

    def _get_expected_matchup_win_rate(self, champion: "Champion") -> float:
        self_base_elo = win_rate_to_elo(self._get_champion_win_rate_without_opponent(champion))
        opponent_base_elo = win_rate_to_elo(champion._get_champion_win_rate_without_opponent(self))
        matchup_elo_delta = self_base_elo - opponent_base_elo
        expected_matchup_win_rate = elo_to_win_rate(matchup_elo_delta)
        return expected_matchup_win_rate

    def _get_champion_win_rate_without_opponent(self, opponent: "Champion") -> float:
        return (
            self.rank_normalized_win_rate
            - self.normalized_matchup_win_rates[opponent] * self.matchup_pick_rates[opponent]
        ) / (1 - self.matchup_pick_rates[opponent])

    @functools.cached_property
    def matchup_normalized_win_rate(self) -> float:
        """Champion win rate if opponent pick rate is independent of selected champion"""
        roster_pick_rate = self._roster.pick_rates
        matchup_win_rates = self.normalized_matchup_win_rates
        return (matchup_win_rates * roster_pick_rate).sum() / roster_pick_rate.sum()

    @functools.cached_property
    def matchup_pick_rates(self) -> pd.Series:
        return pd.Series(
            {
                champion: self._lolalytics_data[f"enemy_{champion.role}"].get(champion.id, {}).get("matches", np.nan)
                / self.n
                for champion in self._roster.champions
            }
        )

    @functools.cached_property
    def pick_rate_delta(self) -> pd.Series:
        """Measurement of how more or less often an opponent is matched against champion compared to opponent base pick rate"""
        # Normalize roster pick rate based on the fact that a laner cannot match against themself
        roster_pick_rate = self._roster.pick_rates.copy()
        roster_pick_rate[
            self._roster.get_valid_champion_index(
                role=self.role, min_champion_role_assignemnt_rate=0, min_champion_pick_rate=0
            )
        ] = roster_pick_rate[
            self._roster.get_valid_champion_index(
                role=self.role, min_champion_role_assignemnt_rate=0, min_champion_pick_rate=0
            )
        ] / (
            1 - self.pick_rate / 2
        )
        # Calculate pick rate delta
        return self.matchup_pick_rates - (roster_pick_rate / 2)

    def blind_expected_win_rate(self, num_opponent_champions: int, _ignore_champion: "Champion" = None) -> float:
        """
        Measurement of the expected winrate of blind picking a champion assuming opponent will pick the worst matchup
        they have available.
        """

        # Sort opponent champions by matchup winrate
        opponent_champions = sorted(
            self._roster.get_valid_champions(role=self.role),
            key=lambda opponent_champion: self.raw_matchup_win_rates[opponent_champion],
        )
        if self in opponent_champions:
            opponent_champions.remove(self)
        if _ignore_champion is not None and _ignore_champion in opponent_champions:
            opponent_champions.remove(_ignore_champion)

        # Iterate through opponents
        percent_opponents_remaining = 1.0
        cumulative_win_rate = 0
        for opponent_champion in opponent_champions:
            # The probabillity that a given champion is in our opponent's champ pool is equal to 1 - the chance it is
            # not in their champ pool, which is the chance that all N of their picks are NOT the opponent champion,
            # which is not EXACTLY equal to (1 - pick_rate) ^ N but is close enough for this purpose.
            probabillity_in_opponent_champ_pool = 1 - (1 - opponent_champion.pick_rate) ** num_opponent_champions
            # Probabillity of being picked is modified by the number of players who have already picked a worse matchup
            probabillity_picked = probabillity_in_opponent_champ_pool * percent_opponents_remaining
            cumulative_win_rate += probabillity_picked * self.raw_matchup_win_rates[opponent_champion]
            percent_opponents_remaining -= probabillity_picked

        return cumulative_win_rate

    def blind_pick_ban_win_rate_improvements(self, num_opponent_champions: int = 5):
        return pd.Series(
            {
                opponent_champion: self.blind_expected_win_rate(num_opponent_champions, opponent_champion)
                for opponent_champion in self._roster.get_valid_champions(role=self.role)
                if opponent_champion is not self
            }
        ).sort_values(ascending=False)

    def best_blind_ban(self, num_opponent_champions: int = 5):
        best_ban_blind_expected_win_rate = -np.Inf
        best_ban = None

        for opponent_champion in self._roster.get_valid_champions(role=self.role):
            if opponent_champion is self:
                continue

            opponent_champion_ban_blind_expected_win_rate = self.blind_expected_win_rate(
                num_opponent_champions, _ignore_champion=opponent_champion
            )
            if opponent_champion_ban_blind_expected_win_rate > best_ban_blind_expected_win_rate:
                best_ban = opponent_champion
                best_ban_blind_expected_win_rate = opponent_champion_ban_blind_expected_win_rate

        return best_ban, best_ban_blind_expected_win_rate

    def graph_pick_rate_delta_vs_normalized_matchup_win_rates(self):
        # Create and format figure
        figure, axes = plt.subplots()
        axes.margins(0.15)  # Zoom out slightly
        axes.grid(True)
        axes.set_title(str(self))
        axes.set_xlabel(f"Matchup Win Rate Delta (Positive good for {self.name})")
        # axes.set_ylabel(f"{self.name} vs Opponent Frequency minus Opponent Frequency")
        axes.set_ylabel(f"Matchup Frequency Multiplier")
        axes.xaxis.set_major_formatter(PercentFormatter())
        axes.yaxis.set_major_formatter(PercentFormatter(decimals=0))

        # Get data
        # xs = 100 * (self.normalized_matchup_win_rates - self.expected_matchup_win_rates)
        xs = 100 * (self.normalized_matchup_win_rates - self.rank_normalized_win_rate)
        # ys = 100 * self.pick_rate_delta
        ys = 100 * ((self._roster.pick_rates + self.pick_rate_delta) / self._roster.pick_rates)
        size = self._roster.pick_rates
        # color = xs / 100 * self.pick_rate_delta
        color = (self.normalized_matchup_win_rates - self.rank_normalized_win_rate) * (
            self.matchup_pick_rates - self._roster.pick_rates / 2
        )

        # Filter data
        ys = ys.loc[self._roster.get_valid_champion_index()].dropna()
        xs = xs.loc[ys.index]
        size = size.loc[ys.index]
        color = color.loc[ys.index]

        # Normalize size of dots to most common being size 200 points^2.
        size = size * (200 / size.max())

        color_extent = max(abs(color.min()), abs(color.max()))

        # Plot data
        scatter = axes.scatter(
            xs, ys, vmin=-color_extent, vmax=color_extent, s=size, c=color, cmap="RdYlGn"
        )  # , cmap="Blues")

        # Add color bar
        color_bar = plt.colorbar(scatter, format=PercentFormatter())
        color_bar.set_label("Impact on Win Rate Delta")
        color_bar.set_ticks([])

        # Add labels to 15 most impactful
        impact = color.abs().sort_values(ascending=False)
        labels = []
        for champion in impact.index[:15]:
            label = axes.text(xs[champion], ys[champion], str(champion))
            labels.append(label)
        figure.draw(figure.canvas.get_renderer())
        adjust_text(
            labels,
            expand_points=(1.2, 1.3),
            force_points=(0.5, 0.8),
            arrowprops=dict(arrowstyle="->", color="k", lw=0.5),
        )

        # Show
        plt.show(block=False)

        a = 1

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"

    def __repr__(self) -> str:
        return f"<src.champion.Champion: {self})"
