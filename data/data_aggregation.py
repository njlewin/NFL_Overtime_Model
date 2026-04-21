import pandas as pd
import nfl_data_py as nfl
import os
from config import *


def aggregate_drives(pbp_df):
    # Filter plays
    df = pbp_df[
        pbp_df['play_type'].isin(['run', 'pass', 'punt', 'no_play', 'field_goal', 'extra_point', 'qb_spike', 'qb_kneel']) &
        pbp_df['drive'].notna()
    ].copy()

    # Filter any remaining drives that are only an extra point (IE After a kick return TD)
    df = df[~df.groupby(['game_id', 'drive'])['play_type']
    .transform(lambda x: (x == 'extra_point').all())]

    cols_needed = [
        'game_id', 'drive', 'play_id', 'play_type',
        'yardline_100', 'game_seconds_remaining', 'play_duration',
        'posteam_score', 'defteam_score',
        'posteam_score_post', 'defteam_score_post',
        'drive_end_transition', 'ydstogo'
    ]
    df = df[cols_needed]

    # Sort once so idxmin/idxmax on play_id are just first/last rows
    df = df.sort_values(['game_id', 'drive', 'play_id'])

    group = df.groupby(['game_id', 'drive'])

    # First and last play of each drive
    first = group.first().add_prefix('first_')
    last  = group.last().add_prefix('last_')
    drives = pd.concat([first, last], axis=1).reset_index()

    # Build the drive-level columns
    drives['drive_id']              = drives['game_id'] + '_' + drives['drive'].astype(int).astype(str)
    drives['season']                = drives['drive_id'].str[:4].astype(int)
    drives['start_yardline']        = drives['first_yardline_100'].astype(int)
    drives['start_time_left']       = drives['first_game_seconds_remaining']
    drives['start_posteam_score']   = drives['first_posteam_score']
    drives['start_defteam_score']   = drives['first_defteam_score']
    drives['start_score_diff']      = drives['first_posteam_score'] - drives['start_defteam_score']
    drives['drive_result']          = drives['first_drive_end_transition']
    drives['defteam_TD']            = drives['first_defteam_score'] != drives['last_defteam_score']
    drives['posteam_score_change']  = drives['last_posteam_score_post']  - drives['first_posteam_score']
    drives['defteam_score_change']  = drives['last_defteam_score_post']  - drives['first_defteam_score']
    drives['last_play_yardline']    = drives['last_yardline_100']
    drives['last_play_ydstogo']   = drives['last_ydstogo']
    # get the yard line from the next drive to record what the next starting yardline is
    drives = drives.sort_values(['game_id', 'drive'])
    drives['time_elapsed'] = (drives['first_game_seconds_remaining'] - drives['last_game_seconds_remaining']+
                              drives['last_play_duration'])
    drives['next_drive_start_yardline'] = (
        drives.groupby('game_id')['first_yardline_100'].shift(-1)
    )
    # For the last drive of each game, fall back to that drive's last yardline (matches original logic)
    mask = drives['next_drive_start_yardline'].isna()
    drives.loc[mask, 'next_drive_start_yardline'] = drives.loc[mask, 'last_yardline_100']

    # Keep only the output columns
    output_cols = [
        'drive_id', 'season', 'start_yardline', 'start_time_left',
        'start_posteam_score', 'start_defteam_score', 'start_score_diff', 'drive_result',
        'time_elapsed', 'defteam_TD','posteam_score_change', 'defteam_score_change', 'last_play_yardline',
        'last_ydstogo', 'next_drive_start_yardline'
    ]
    drives[output_cols].to_csv(DRIVE_FILE, index=False)
    print('Drives aggregated')
    return df

def aggregate_kos(pbp_df):
    kickoff_mask = pbp_df['play_type'] == 'kickoff'
    kickoff_i = pbp_df.index[kickoff_mask]
    next_indices = kickoff_i + 1

    # Filter to valid indices only (avoid going out of bounds)
    valid_kick = kickoff_i[next_indices < len(pbp_df)]
    valid_next = next_indices[next_indices < len(pbp_df)]

    # Build the result DataFrame
    kickoff_results = pd.DataFrame({
        'game_id': pbp_df.loc[valid_kick, 'game_id'],
        'play_id': pbp_df.loc[valid_kick, 'play_id'].astype(str),
        'season': pbp_df.loc[valid_kick, 'game_id'].str[:4],
        'return_touchdown': pbp_df.loc[valid_kick, 'return_touchdown'].values,
        'starting_field_position': pbp_df.loc[valid_next, 'yardline_100'].values,
        'time_elapsed':pbp_df.loc[valid_kick, 'play_duration'].values,
    }).dropna()

    kickoff_results.to_csv(KO_FILE, index=False)
    print('Kickoffs aggregated')
    return kickoff_results

def aggregate_conversions(pbp_df):
    eps = pbp_df['extra_point_result'].value_counts()
    tpcs = pbp_df['two_point_conv_result'].value_counts()
    pd.DataFrame({
        'extra_point_percentage': [eps['good']/sum(eps)],
        'two_point_percentage':[tpcs['success']/sum(tpcs)],
    }).to_csv('conversion_rates.csv', index=False)

    print('Aggregated extra-point and two-point conversion rates.')

def import_pbp_data (most_recent_season = 2025, look_back = 10, force_refresh = False):
    # Import nfl play by play data.
    if not os.path.isfile(PBP_FILE) or force_refresh:
        pbp_df = nfl.import_pbp_data(years=[most_recent_season - i for i in range(look_back)], downcast=True).copy()
        pbp_df = pbp_df.sort_values(['game_id', 'game_seconds_remaining','play_id'], ascending=[True, False, True])
        pbp_df['play_duration'] = pbp_df.groupby('game_id')['game_seconds_remaining'].diff(-1)
        pbp_df.to_parquet(PBP_FILE)
        print("Wrote pbp file")
    else:
        pbp_df = pd.read_parquet(PBP_FILE)
        print("Loaded pbp data")
    return pbp_df

def aggregate_fourth_down_attempts(pbp_df):
    df = pbp_df[(pbp_df['fourth_down_converted']==1) | (pbp_df['fourth_down_failed'] ==1)].copy()
    df['off_td'] = df['posteam'] == df['td_team']
    df['def_td'] = df['defteam'] == df['td_team']
    cols = ['fourth_down_converted', 'fourth_down_failed', 'yardline_100','ydstogo', 'yards_gained', 'off_td', 'def_td']

    df[cols].to_csv(FOURTH_DOWN_FILE, index=False)

    print('Fourth down attempts aggregated')

if __name__ == "__main__":
    pbp_df = import_pbp_data(most_recent_season = 2025, look_back = 25, force_refresh = False)
    aggregate_drives(pbp_df)
    aggregate_kos(pbp_df)
    aggregate_conversions(pbp_df)
    aggregate_fourth_down_attempts(pbp_df)
