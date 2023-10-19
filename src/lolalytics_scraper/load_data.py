# Standard Library
import datetime
import itertools
import json
import re
from pathlib import Path
from statistics import mode

# Third Party
import requests
import tqdm

# Packege Imports
from lolalytics_scraper import ROLES

DATA_DIR_PATH = Path(__file__).parent.joinpath("data")
RUNES_PATH = DATA_DIR_PATH.joinpath("runes.json")
ITEMS_PATH = DATA_DIR_PATH.joinpath("items.json")
CHAMPION_ID_PATH = DATA_DIR_PATH.joinpath("champion_ids.json")
LOLALYTICS_DIR_PATH = DATA_DIR_PATH.joinpath("lolalytics")
LOLALYTICS_DIR_PATH.mkdir(exist_ok=True)


def update_runes_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/runesReforged.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    rune_data = json.loads(page.text)
    with open(RUNES_PATH, "w") as file_handle:
        json.dump(rune_data, file_handle, indent=4)


def update_item_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/item.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    item_data = json.loads(page.text)
    with open(ITEMS_PATH, "w") as file_handle:
        json.dump(item_data, file_handle, indent=4)


def update_champion_id_map(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/champion.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)["data"]
    champion_ids = {key if key != "MonkeyKing" else "Wukong": int(value["key"]) for key, value in data.items()}
    with open(CHAMPION_ID_PATH, "w") as file_handle:
        json.dump(champion_ids, file_handle, indent=4)


LOLALYTICS_QUEUES_MAP = {
    "Draft 5v5": 400,
    "Solo/Duo": 420,
    "Blind 5v5": 430,
    "Flex 5v5": 440,
    "ARAM": 450,
    "Clash": 700,
    "Intro Bots": 830,
    "Beginner Bots": 840,
    "Bots": 850,
    "URF": 900,
    "One for All": 1020,
    "Nexus Blitz": 1300,
    "Ultbook": 1400,
    "Tutorial": 2000,
    "Tutorial": 2010,
    "Tutorial": 2020,
}


def update_lolalytics_champion_data(
    champion_ids: dict[str, int],
    latest_patch: str,
    patches: list[str],
    queue: str,
    tier: str,
    region: str,
    use_cache: bool,
) -> tuple[dict[str, dict], int, float]:
    # Reformat defaults
    patches = [patch if patch != "latest" else ".".join(latest_patch.split(".")[:-1]) for patch in patches]

    # Validate input
    for patch in patches:
        if patch in ["7", "14", "30"]:
            if len(patches) > 1:
                raise ValueError(f"Unable to combine {patch} day patches with any other patch.")
        elif not re.match("\d+\.\d+", patch):
            raise ValueError(f"{patch} does not follow ##.# or 7/14/30 format.")

    raw_lolalytics_data = {}

    # Identify patches that need to be updated
    patches_to_update = []
    for patch in patches:
        lolalytics_patch_path = LOLALYTICS_DIR_PATH.joinpath(f"{patch}.json")
        update = True
        if lolalytics_patch_path.exists() and use_cache:
            if patch in ["7", "14", "30"] or latest_patch.startswith(patch):
                last_updated = datetime.datetime.fromtimestamp(lolalytics_patch_path.lstat().st_mtime)
                if last_updated + datetime.timedelta(days=1) > datetime.datetime.now():
                    print(f"Cached {patch} data is less than 1 day old. Loading cached {patch} data...")
                    update = False
            else:
                print(f"Loading cached {patch} data...")
                update = False

        if update:
            patches_to_update.append(patch)
        else:
            with open(lolalytics_patch_path, "r") as file_handler:
                raw_lolalytics_data[patch] = json.load(file_handler)

    # Download data
    if len(patches_to_update) > 0:
        print(f"Scraping data from lolalytics.com...")
        str_len = (
            max([len(patch) for patch in patches])
            + max((len(champion) for champion in champion_ids.keys()))
            + len("support")
            + 6
        )
        iterator = tqdm.tqdm(tuple(itertools.product(patches_to_update, champion_ids.items(), ROLES)))
        for patch, (champion, champion_id), role in iterator:
            iterator.set_description(f"{patch}: {champion} ({role})".ljust(str_len))
            api_key_mapping = {
                "patch": patch,
                "cid": champion_id,
                "lane": role,
                "tier": tier,
                "queue": queue,
                "region": region,
            }
            api_call = f"https://ax.lolalytics.com/mega/?ep=champion&p=d&v=1&{'&'.join(f'{key}={value}' for key, value in api_key_mapping.items() if value != None)}"
            page = requests.get(api_call)
            data = json.loads(page.text)
            assert page.status_code == 200
            raw_lolalytics_data.setdefault(patch, {}).setdefault(int(champion_id), {})[role] = data

        # Save downloaded data
        print("Saving downloaded Lolalytics data...")
        for patch in patches_to_update:
            lolalytics_patch_path = LOLALYTICS_DIR_PATH.joinpath(f"{patch}.json")
            with open(lolalytics_patch_path, "w") as file_handler:
                json.dump(raw_lolalytics_data[patch], file_handler, indent=4)

    # Format data
    lolalytics_data, analyzed, rank_win_rate = format_lolalytics_data(raw_lolalytics_data)

    return lolalytics_data, analyzed, rank_win_rate


def get_total_analyzed_and_rank_win_rate(raw_lolalytics_data: dict[str, dict]) -> tuple[int, float]:
    """Across all patches, collect the total number of champions analyzed and rank win rate"""
    patch_analyzed = {
        patch: mode(
            champion_role_data.get("analysed", 0)
            for champion_data in patch_data.values()
            for champion_role_data in champion_data.values()
        )
        for patch, patch_data in raw_lolalytics_data.items()
    }
    patch_rank_win_rate = {
        patch: mode(
            champion_role_data.get("avgWinRate", 0)
            for champion_data in patch_data.values()
            for champion_role_data in champion_data.values()
        )
        / 100  # Divide by 100 to turn into 0.0 to 1.0 percentage
        for patch, patch_data in raw_lolalytics_data.items()
    }
    analyzed = sum(patch_analyzed.values())
    rank_win_rate = (
        sum(patch_analyzed[patch] * patch_rank_win_rate[patch] for patch in raw_lolalytics_data.keys()) / analyzed
    )
    return analyzed, rank_win_rate


def format_lolalytics_data(raw_lolalytics_data: dict[str, dict]) -> dict[int, dict[str, dict]]:
    analyzed, rank_win_rate = get_total_analyzed_and_rank_win_rate(raw_lolalytics_data)

    # Reformat into champion -> role -> patch structure
    lolalytics_data = {}
    for patch, patch_data in raw_lolalytics_data.items():
        for champion_id, champion_data in patch_data.items():
            for champion_role, champion_role_data in champion_data.items():
                # Reformat matchup data into dicts
                for enemy_role in ROLES:
                    if f"enemy_{enemy_role}" in champion_role_data:
                        champion_role_data[f"enemy_{enemy_role}"] = {
                            champion_id: {"matches": matches, "wins": wins, "win_rate": wins / matches}
                            for champion_id, matches, wins, _ in champion_role_data[f"enemy_{enemy_role}"]
                        }
                # Save data
                lolalytics_data.setdefault(int(champion_id), {}).setdefault(champion_role, {})[
                    patch
                ] = champion_role_data

    new_lolalytics_data = {}
    for champion_id, champion_data in lolalytics_data.items():
        for champion_role, champion_role_data in champion_data.items():
            # If multiple patches, merge data together. This could cause data loss in the future if not properly tested,
            # but I would want to know about those errors and address them here later than to have them pass though by
            # mistake.
            if len(champion_role_data.keys()) > 1:
                new_lolalytics_data.setdefault(champion_id, {})[champion_role] = {}

                for patch, patch_data in champion_role_data.items():
                    for enemy_role in ROLES:
                        if f"enemy_{enemy_role}" in patch_data:
                            for enemy_champion_id, matchup_data in patch_data[f"enemy_{enemy_role}"].items():
                                new_lolalytics_data[champion_id][champion_role].setdefault(
                                    f"enemy_{enemy_role}", {}
                                ).setdefault(enemy_champion_id, {})["matches"] = (
                                    new_lolalytics_data[champion_id][champion_role]
                                    .get(f"enemy_{enemy_role}", {})
                                    .get(enemy_champion_id, {})
                                    .get("matches", 0)
                                    + matchup_data["matches"]
                                )
                                new_lolalytics_data[champion_id][champion_role][f"enemy_{enemy_role}"][
                                    enemy_champion_id
                                ]["wins"] = (
                                    new_lolalytics_data[champion_id][champion_role][f"enemy_{enemy_role}"]
                                    .get(enemy_champion_id, {})
                                    .get("wins", 0)
                                    + matchup_data["wins"]
                                )
                # Sum up win rates
                for enemy_role in ROLES:
                    for enemy_champion_id, matchup_data in new_lolalytics_data[champion_id][champion_role][
                        f"enemy_{enemy_role}"
                    ].items():
                        matchup_data["win_rate"] = matchup_data["wins"] / matchup_data["matches"]

            else:
                new_lolalytics_data.setdefault(champion_id, {})[champion_role] = list(champion_role_data.values())[0]

    return new_lolalytics_data, analyzed, rank_win_rate


def get_latest_patch():
    api_call = "https://raw.githubusercontent.com/InFinity54/LoL_DDragon/master/latest/manifest.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)
    version: str = data["n"]["item"]
    return version


def get_latest_patch_update():
    latest_patch_update_path = DATA_DIR_PATH.joinpath("last_patch_update.txt")
    with open(latest_patch_update_path, "r") as file_handle:
        latest_patch_update = file_handle.read()
    return latest_patch_update


def update_lastest_patch(patch_number: str):
    last_patch_path = DATA_DIR_PATH.joinpath("last_patch_update.txt")
    with open(last_patch_path, "w") as file_handle:
        file_handle.write(patch_number)


def update_data(patches: list[str], queue: int, tier: str, region: str, use_cache: bool):
    latest_patch = get_latest_patch()
    latest_patch_update = get_latest_patch_update()

    if latest_patch != latest_patch_update or not use_cache:
        print(f"Updating backend data to {latest_patch}...")
        update_runes_data(latest_patch)
        update_item_data(latest_patch)
        update_item_data(latest_patch)
        update_lastest_patch(latest_patch)
        print("Done!")

    with open(CHAMPION_ID_PATH, "r") as file_handle:
        champion_ids: dict[str, int] = json.load(file_handle)
    inverse_champion_ids: dict[int, str] = {value: key for key, value in champion_ids.items()}
    with open(RUNES_PATH, "r") as file_handle:
        rune_data: dict[str, dict[str, str]] = json.load(file_handle)
    with open(ITEMS_PATH, "r") as file_handle:
        item_data: dict[str, dict[str, str]] = json.load(file_handle)

    lolalytics_data, analyzed, rank_win_rate = update_lolalytics_champion_data(
        champion_ids, latest_patch, patches, queue, tier, region, use_cache
    )

    return champion_ids, inverse_champion_ids, rune_data, item_data, lolalytics_data, analyzed, rank_win_rate
