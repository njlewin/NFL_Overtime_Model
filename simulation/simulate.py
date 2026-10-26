from pathlib import Path
import pandas as pd
from simulation.overtime_period import OvertimePeriod
from multiprocessing import Pool, cpu_count
from config import *
import time

from simulation.team import Team


def run_simulation(args):
    home_team, away_team, kicking_team, season, use_hfa, goforit_2pc, goforit_fg,  = args
    ot = OvertimePeriod(home_team, away_team, kicking_team, season, goforit_2pc, goforit_fg)
    ot.simulate()
    return ot.result()

def run_simulation_batch(args):
    home_team, away_team, kicking_team, season,use_hfa, goforit_2pc, goforit_fg, batch_size = args
    results = []
    for _ in range(batch_size):
        ot = OvertimePeriod(home_team, away_team, kicking_team, season, use_hfa, goforit_2pc, goforit_fg)
        ot.simulate()
        results.append(ot.result())
    return results

def simulate_overtimes(n, home_team, away_team, kicking_team, season, apply_hfa, goforit_2pc=False, goforit_fg =False, write_output=False, pool=None):
    n_workers = cpu_count()
    batch_size = n // n_workers
    args = [(home_team, away_team, kicking_team, season, apply_hfa, goforit_2pc, goforit_fg, batch_size)] * n_workers

    batched_results = pool.map(run_simulation_batch, args)
    results = [item for batch in batched_results for item in batch]  # flatten

    df = pd.DataFrame(results)
    # if write_output:
    #     name = f'{season}_overtime{"_agg2pc" if goforit_2pc else ""}{"_aggfg" if goforit_fg else ""}_{n}'
    #     df.to_csv(output_file(season, n, goforit_2pc, goforit_fg), index=False)
    return df

def run_neutral(n, season, write_output = False, pool = None):
    team1 = Team('team1', 0, 0)
    team2 = Team('team2', 0, 0)
    df = simulate_overtimes(n, team1, team2, team1, season, apply_hfa=False, goforit_fg=False, write_output=True, pool = pool)
    if write_output:
        df.to_csv(OUTPUT_DIR /f'neutral_OT_{season}_{n}.csv', index = False)
    return df

def run_hfa(n, season, write_output = False, pool = None):
    team1 = Team('home_team', 0, 0)
    team2 = Team('away_team', 0, 0)
    df_home_kicks = simulate_overtimes(n//2, team1, team2, team1, season, apply_hfa=True, goforit_fg=False, write_output=True, pool = pool)
    df_away_kicks = simulate_overtimes(n//2, team1, team2, team2, season, apply_hfa=True, goforit_fg=False, write_output=True, pool = pool)
    df = pd.concat([df_home_kicks, df_away_kicks], ignore_index=True)
    if write_output:
        df.to_csv(OUTPUT_DIR/f'hfa_OT_{season}_{n}.csv', index=False)
    return df

srs_levels = {'much worse': -4, 'worse': -2, 'neutral': 0, 'better': 2, 'much better': 4}

def run_srs_grid(n, season, levels=srs_levels, write_output=False, pool=None):
    """Vary team 1's OSRS and DSRS over `levels` (team 2 neutral, no HFA); n sims per combination."""
    frames = []
    for o_label, osrs in levels.items():
        for d_label, dsrs in levels.items():
            print(f'Running {o_label} offense & {d_label} defense')
            team1 = Team('team1', osrs, dsrs)
            team2 = Team('team2', 0, 0)
            for kicker in (team1, team2):       # balance who receives
                df = simulate_overtimes(n // 2, team1, team2, kicker, season,
                                        apply_hfa=False, pool=pool)
                df['osrs'], df['dsrs'] = osrs, dsrs
                df['off_level'], df['def_level'] = o_label, d_label
                df['kicking_team'] = kicker.name
                frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    if write_output:
        out.to_csv(OUTPUT_DIR / f'srs_grid_OT_{season}_{n}.csv', index=False)
    return out

if __name__ == '__main__':
    start = time.time()
    n = 20000
    with Pool  (cpu_count()) as pool:
        run_srs_grid(n, 2025, write_output=True, pool = pool)
    elapsed = time.time() - start
    print(f'Ran {n} simulations in {elapsed:.2f} seconds')