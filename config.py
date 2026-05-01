from pathlib import Path

import duckdb

# Default Simulation Count
SIM_NUM = 10000
# Simulation Count when deciding on "Go For It" Flags, needed because those decisions are relatively rare
DECISION_SIMS = 100000


# Directories to use
ROOT_DIR = Path(__file__).parent  # resolves to the directory config.py lives in
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
SIM_DIR = ROOT_DIR / "simulation"
ANALYSIS_DIR = ROOT_DIR / "analysis"
ASSET_DIR = ANALYSIS_DIR / "assets"

# File names (data dir)
DRIVE_FILE = "drive_list.csv"
KO_FILE = "ko_list.csv"
FOURTH_DOWN_FILE = "fourth_down_attempts.csv"
CONVERSION_FILE = "conversion_rates.csv"
PBP_FILE = "pbp_data.parquet"

current_season = duckdb.sql(f"""SELECT MAX(season) FROM read_parquet('{DATA_DIR/PBP_FILE}')""").fetchone()[0]


# File Names (asset dir)
HIST_COMPARISON = 'hist_comparison.csv'
POSSESSION_GRAPHS = f'possession_graphs_{current_season}.png'
HIST_ADVANTAGE_TIES = f'historical_receiving_advantage_tie_rate.png'

# File names (output dir)
def output_file(season, n = SIM_NUM, goforit_2pc = False, goforit_fg = False):
    return OUTPUT_DIR / f'{season}_overtime{"_agg2pc" if goforit_2pc else ""}{"_aggfg" if goforit_fg else ""}_{n}.csv'

OT_RESULTS = "ot_results.csv"
OT_RESULTS_DEC = f'ot_results_{current_season}_decisions.csv'
DECISION_TREE = 'decision_tree.png'

