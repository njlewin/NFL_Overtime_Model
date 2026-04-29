from pathlib import Path

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

# File Names (asset dir)
HIST_COMPARISON= 'hist_comparison.csv'

# Default Simulation Count
SIM_NUM = 10000

CURRENT_SEASON = 2025

DECISION_SIMS = 100000

# File names (output dir)
def output_file(season, n = SIM_NUM, goforit_2pc = False, goforit_fg = False):
    return OUTPUT_DIR / f'{season}_overtime{"_agg2pc" if goforit_2pc else ""}{"_aggfg" if goforit_fg else ""}_{n}.csv'

OT_RESULTS = "ot_results.csv"
OT_RESULTS_DEC = f'ot_results_{CURRENT_SEASON}_decisions.csv'
