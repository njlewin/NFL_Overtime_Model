import pandas as pd
import numpy as np
import nflreadpy as nfl
import os
from config import *


def od_srs_rankings(df, season):
    teams = sorted(set(df['home_team']) | set(df['away_team']))
    col = {team: i for i, team in enumerate(teams)}
    n_teams = len(teams)
    DEF_OFFSET = n_teams          # defense columns come after offense columns
    AVG_COL = 2 * n_teams         # league scoring average
    HFA_COL = 2 * n_teams + 1     # home-field advantage (in margin points)

    # define the X and y matrixes: two rows per game, one per team's points
    X = np.zeros((2 * len(df), 2 * n_teams + 2))
    y = np.zeros(2 * len(df))
    for i, g in enumerate(df.itertuples()):
        home_row, away_row = 2 * i, 2 * i + 1
        hfa_entry = 0 if g.neutral == 1 else 0.5

        # home team's points = avg + home offense - away defense + hfa/2
        X[home_row, col[g.home_team]] = 1
        X[home_row, DEF_OFFSET + col[g.away_team]] = -1
        X[home_row, AVG_COL] = 1
        X[home_row, HFA_COL] = hfa_entry
        y[home_row] = g.home_score

        # away team's points = avg + away offense - home defense - hfa/2
        X[away_row, col[g.away_team]] = 1
        X[away_row, DEF_OFFSET + col[g.home_team]] = -1
        X[away_row, AVG_COL] = 1
        X[away_row, HFA_COL] = -hfa_entry
        y[away_row] = g.away_score

    # Solve for the minimum
    solution, *_ = np.linalg.lstsq(X, y, rcond=None)

    osrs = solution[:n_teams]
    dsrs = solution[DEF_OFFSET:DEF_OFFSET + n_teams]
    league_avg = solution[AVG_COL]
    hfa = solution[HFA_COL]

    # recenter offense and defense to average zero, moving the shifts into
    # the league average so every prediction stays the same
    league_avg += osrs.mean() - dsrs.mean()
    osrs = osrs - osrs.mean()
    dsrs = dsrs - dsrs.mean()

    result_df = pd.DataFrame({'season': season, 'team': teams,
                              'osrs': osrs, 'dsrs': dsrs})
    result_df = (result_df.assign(_srs=result_df['osrs'] + result_df['dsrs'])
                 .sort_values('_srs', ascending=False)
                 .drop(columns='_srs')
                 .reset_index(drop=True))

    # add home-field advantage and league average as extra rows.
    # HFA is split half to offense, half to defense, so the two add up
    # to the same HFA your srs_rankings function reports.
    #result_df.loc[len(result_df)] = [season, 'Homefield Advantage', hfa / 2, hfa / 2]
    #result_df.loc[len(result_df)] = [season, 'League Average', league_avg, np.nan]

    return result_df, hfa

df = nfl.load_schedules(years).to_pandas()
df = df.dropna(subset=['home_score', 'away_score'])
cols = ['season','home_team','away_team','home_score', 'away_score', 'game_type', 'result', 'location']
df = df[cols]

df['playoff'] = np.where(df['game_type']!= 'REG', 1, 0)
df['neutral'] = np.where(df['location']== 'Neutral', 1, 0)


df = df[df['playoff']==0]

srs_list = []
hfa_list = []
for year in df['season'].unique():
    df_t = df[df['season'] == year].copy()
    srs_result, hfa = od_srs_rankings(df_t, year)
    srs_list.append(srs_result)
    hfa_list.append(pd.DataFrame({'season':year, 'hfa':hfa}, index = [0]))

srs = pd.concat(srs_list).reset_index(drop=True)
hfas = pd.concat(hfa_list).reset_index(drop=True)

team_changes = {'STL': 'LA', 'OAK':'LV', 'SD': 'LAC'}

srs = srs.replace(team_changes)

srs.to_csv('srs.csv', index = False)
hfas.to_csv('hfas.csv', index = False)