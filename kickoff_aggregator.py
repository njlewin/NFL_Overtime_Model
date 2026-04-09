import duckdb
import pandas as pd
import nfl_data_py as nfl
import os


most_recent_season = 2025
look_back = 10
# Import nfl play by play data for the last 10 years.
file_name ='pbp_data.pkl'
if not os.path.isfile(file_name):
    df = nfl.import_pbp_data(years = [most_recent_season- i for i in range(look_back)], downcast = True)
    df.to_pickle(file_name)
    print("Wrote pbp file")
else:
    df = pd.read_pickle(file_name)
    print("Loaded pbp data")


