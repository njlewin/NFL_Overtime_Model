from pathlib import Path

ROOT_DIR = Path(__file__).parent  # resolves to the directory config.py lives in
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
SIM_DIR = ROOT_DIR / "simulation"

DRIVE_FILE = "drive_list.csv"
KO_FILE = "ko_list.csv"
FOURTH_DOWN_FILE = "fourth_down_attempts.csv"
CONVERSION_FILE = "conversion_rates.csv"
PBP_FILE = "pbp_data.parquet"

SIM_NUM = 10000


def output_file(season, n = SIM_NUM, go_for_ties = False):
    return OUTPUT_DIR / f'{season}_overtime{"_ties" if go_for_ties else ""}_{n}.csv'