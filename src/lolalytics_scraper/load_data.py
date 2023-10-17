# Standard Library
import itertools
import json
from pathlib import Path

# Third Party
import requests
import tqdm

DATA_DIR_PATH = Path(__file__).parent.joinpath("data")

with open(DATA_DIR_PATH.joinpath("champion_ids.json"), "r") as file_handle:
    CHAMPION_IDS: dict[str, int] = json.load(file_handle)
    INVERSE_CHAMPION_IDS: dict[int, str] = {value: key for key, value in CHAMPION_IDS.items()}
with open(DATA_DIR_PATH.joinpath("lolalytics_data.json"), "r") as file_handle:
    LOLALYTICS_DATA: dict[str, dict] = {int(key): value for key, value in json.load(file_handle).items()}
with open(DATA_DIR_PATH.joinpath("runes.json"), "r") as file_handle:
    RUNE_DATA: dict[str, dict[str, str]] = json.load(file_handle)
with open(DATA_DIR_PATH.joinpath("items.json"), "r") as file_handle:
    ITEM_DATA: dict[str, dict[str, str]] = json.load(file_handle)


def update_runes_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/runesReforged.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    RUNE_DATA = json.loads(page.text)
    runes_data_path = DATA_DIR_PATH.joinpath("runes.json")
    with open(runes_data_path, "w") as file_handle:
        json.dump(RUNE_DATA, file_handle, indent=4)


def update_item_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/item.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    ITEM_DATA = json.loads(page.text)
    item_data_path = DATA_DIR_PATH.joinpath("items.json")
    with open(item_data_path, "w") as file_handle:
        json.dump(ITEM_DATA, file_handle, indent=4)


def update_champion_id_map(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}/data/en_US/champion.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)["data"]
    CHAMPION_IDS = {key if key != "MonkeyKing" else "Wukong": int(value["key"]) for key, value in data.items()}
    champion_id_map_path = DATA_DIR_PATH.joinpath("champion_ids.json")
    with open(champion_id_map_path, "w") as file_handle:
        json.dump(CHAMPION_IDS, file_handle, indent=4)


def update_lolalytics_champion_data(
    patch: str,
    queue: str = "420",  # Ranked, Solo/Duo
    tier: str = "platinum_plus",
    region: str = "all",
) -> dict[str, dict]:
    LOLALYTICS_DATA.clear()
    iterator = tqdm.tqdm(
        tuple(itertools.product(CHAMPION_IDS.items(), ["top", "jungle", "middle", "bottom", "support"]))
    )
    for (champion, champion_id), role in iterator:
        iterator.set_description(f"{champion} ({role})".ljust(25))
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
        LOLALYTICS_DATA.setdefault(int(champion_id), {})[role] = data
    output_path = DATA_DIR_PATH.joinpath("lolalytics_data.json")
    with open(output_path, "w") as file_handler:
        json.dump(LOLALYTICS_DATA, file_handler, indent=4)


QUEUES = {
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


def update_data(lolalytics_patch=30, queue=QUEUES["Solo/Duo"], tier="plat_plus", region="all"):
    latest_patch = get_latest_patch()
    latest_patch_update = get_latest_patch_update()

    if latest_patch != latest_patch_update:
        print(f"Updating backend data to {latest_patch}...")
        update_runes_data(latest_patch)
        update_item_data(latest_patch)
        update_item_data(latest_patch)
        update_lastest_patch(latest_patch)
        print("Done!")

    print(f"Scraping data from lolalytics.com...")
    update_lolalytics_champion_data(lolalytics_patch, queue, tier, region)
    print("Done!")
