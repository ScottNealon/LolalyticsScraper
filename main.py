from lolalytics_scraper.roster import Roster

roster = Roster()

# roster.graph_matchup_normalized_win_rates()

# lux = roster.get_champion_by_name("Lux", "support")
# lux.graph_pick_rate_delta_vs_normalized_matchup_win_rates()

# miss_fortune = roster.get_champion_by_name("MissFortune", "bottom")
# miss_fortune.graph_pick_rate_delta_vs_normalized_matchup_win_rates()

# jinx = roster.get_champion_by_name("Jinx", "bottom")
# jinx.graph_pick_rate_delta_vs_normalized_matchup_win_rates()

# malphite_mid = roster.get_champion_by_name("Malphite", "middle")
# malphite_mid.graph_pick_rate_delta_vs_normalized_matchup_win_rates()

# a = 1

# print(roster.get_blind_pick_win_rates())

# roster.graph_champion_matchup_comparison(
#     roster.get_champion_by_name("Vex", "middle"), roster.get_champion_by_name("Taliyah", "middle")
# )

# illoi_top = roster.get_champion_by_name("Illaoi", "top")
# blindabillity = illoi_top.blind_expected_win_rate(num_opponent_champions=5)


champion_pool = [
    roster.get_champion_by_name("AurelionSol", "middle"),
    roster.get_champion_by_name("Taliyah", "middle"),
    roster.get_champion_by_name("Swain", "middle"),
]

champion_pool_analysis, matchup_analysis = roster.analyze_champion_pool(champion_pool, log=True)
