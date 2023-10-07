import json
from pathlib import Path

DATA_DIR_PATH = Path(__file__).parent.parent.joinpath("data")

with open(DATA_DIR_PATH.joinpath("champion_ids.json"), "r") as file_handle:
    CHAMPION_IDS: dict[str, int] = json.load(file_handle)
    INVERSE_CHAMPION_IDS: dict[int, str] = {value: key for key, value in CHAMPION_IDS.items()}
with open(DATA_DIR_PATH.joinpath("lolalytics_data.json"), "r") as file_handle:
    LOLALYTICS_DATA: dict[str, dict] = {int(key): value for key, value in json.load(file_handle).items()}
with open(DATA_DIR_PATH.joinpath("runes.json"), "r") as file_handle:
    RUNE_DATA: dict[str, dict[str, str]] = json.load(file_handle)
with open(DATA_DIR_PATH.joinpath("items.json"), "r") as file_handle:
    ITEM_DATA: dict[str, dict[str, str]] = json.load(file_handle)
