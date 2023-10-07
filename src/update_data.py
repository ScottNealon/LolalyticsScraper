# Standard Library
import itertools
import json
from pathlib import Path

# Third Party
import requests
import tqdm

DATA_DIR_PATH = Path(__file__).parent.parent.joinpath("data")


def update_runes_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}.1/data/en_US/runesReforged.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)
    runes_data_path = DATA_DIR_PATH.joinpath("runes.json")
    with open(runes_data_path, "w") as file_handle:
        json.dump(data, file_handle, indent=4)


def update_item_data(patch_number: str):
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}.1/data/en_US/item.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)
    item_data_path = DATA_DIR_PATH.joinpath("items.json")
    with open(item_data_path, "w") as file_handle:
        json.dump(data, file_handle, indent=4)


def update_champion_id_map(patch_number: str) -> dict[int, str]:
    api_call = f"http://ddragon.leagueoflegends.com/cdn/{patch_number}.1/data/en_US/champion.json"
    page = requests.get(api_call)
    assert page.status_code == 200
    data = json.loads(page.text)["data"]
    champion_id_map = {key if key != "MonkeyKing" else "Wukong": int(value["key"]) for key, value in data.items()}
    champion_id_map_path = DATA_DIR_PATH.joinpath("champion_ids.json")
    with open(champion_id_map_path, "w") as file_handle:
        json.dump(champion_id_map, file_handle, indent=4)
    return champion_id_map


def update_lolalytics_champion_data(
    champion_id_map: dict[int, str],
    patch: str,
    queue: str = "420",  # Ranked, Solo/Duo
    tier: str = "gold_plus",
    region: str = "all",
) -> dict[str, dict]:
    champion_data = {}
    iterator = tqdm.tqdm(
        tuple(itertools.product(champion_id_map.items(), ["top", "jungle", "middle", "bottom", "support"]))
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
        api_call = f"https://ax.lolalytics.com/mega/?ep=champion&p=d&v=1{'&'.join(f'{key}={value}' for key, value in api_key_mapping.items() if value != None)}"
        page = requests.get(api_call)
        data = json.loads(page.text)
        assert page.status_code == 200
        champion_data.setdefault(int(champion_id), {})[role] = data
    output_path = DATA_DIR_PATH.joinpath("lolalytics_data.json")
    with open(output_path, "w") as file_handler:
        json.dump(champion_data, file_handler, indent=4)
    return champion_data


QUEUES: {
    400: "Draft 5v5",
    420: "Solo/Duo",
    430: "Blind 5v5",
    440: "Flex 5v5",
    450: "ARAM",
    700: "Clash",
    830: "Intro Bots",
    840: "Beginner Bots",
    850: "Bots",
    900: "URF",
    1020: "One for All",
    1300: "Nexus Blitz",
    1400: "Ultbook",
    2000: "Tutorial",
    2010: "Tutorial",
    2020: "Tutorial",
}


if __name__ == "__main__":
    patch = "30"  # "13.19" for regular patches. "7", "14", or "30" for fixed duration
    queue = QUEUES["Solo/Duo"]
    tier = "plat_plus"
    region = "all"

    if "." in patch:
        update_item_data(patch)
        update_runes_data(patch)
        champion_id_map = update_champion_id_map(patch)
    else:
        champion_id_map_path = DATA_DIR_PATH.joinpath("champion_ids.json")
        with open(champion_id_map_path) as file_handle:
            champion_id_map = json.load(file_handle)
    update_lolalytics_champion_data(champion_id_map, patch, queue, tier, region)
