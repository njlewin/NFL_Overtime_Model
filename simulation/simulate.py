from pathlib import Path
import pandas as pd
from simulation.overtime_period import OvertimePeriod
from multiprocessing import Pool, cpu_count
from config import *
import time


def run_simulation(args):
    season, goforit_2pc, goforit_fg,  = args
    ot = OvertimePeriod('Kicking Team', 'Receiving Team', 'Kicking Team', season, goforit_2pc, goforit_fg)
    ot.simulate()
    return ot.result()

def run_simulation_batch(args):
    season, goforit_2pc, goforit_fg, batch_size = args
    results = []
    for _ in range(batch_size):
        ot = OvertimePeriod('Kicking Team', 'Receiving Team', 'Kicking Team', season, goforit_2pc, goforit_fg)
        ot.simulate()
        results.append(ot.result())
    return results

def simulate_overtimes(season, n, goforit_2pc=False, goforit_fg =False, write_output=False, pool=None):
    n_workers = cpu_count()
    batch_size = n // n_workers
    args = [(season, goforit_2pc, goforit_fg, batch_size)] * n_workers

    batched_results = pool.map(run_simulation_batch, args)
    results = [item for batch in batched_results for item in batch]  # flatten

    df = pd.DataFrame(results)
    if write_output:
        name = f'{season}_overtime{"_agg2pc" if goforit_2pc else ""}{"_aggfg" if goforit_fg else ""}_{n}'
        df.to_csv(output_file(season, n, goforit_2pc, goforit_fg), index=False)
    return df

if __name__ == '__main__':
    start = time.time()

    # Part 1: Run simulations across years with only conservative decisions

    seasons = [2011, 2013, 2016, 2021, 2024, current_season]
    #seasons = [current_season]
    n1 = SIM_NUM
    with Pool(cpu_count()) as pool:
        dfs1 = []
        for season in seasons:
                df = simulate_overtimes(season, n1, False, False, write_output=True, pool=pool)
                print(f'Ran {n1} simulations in the {season} season.')

                df_t = pd.DataFrame(df['Winning Team'].value_counts(normalize=True)).T
                df_t['season'] = season
                df_t['games'] = n1
                df_t['Receiving Team Advantage'] = df_t['Receiving Team'] - df_t['Kicking Team']

                df_t = df_t[['season','games', 'Receiving Team', 'Kicking Team', 'TIE','Receiving Team Advantage']]
                dfs1.append(df_t)


        result = pd.concat(dfs1, ignore_index=True)
        result.to_csv(OUTPUT_DIR / 'OT_results.csv', index = False)



    # Part 2: Run various decision flags in the most recent season
    dfs2 = []
    flag_combos =  [[False, False], [True, False], [False, True]]
    n2 = DECISION_SIMS
    with Pool(cpu_count()) as pool:
        for flags in flag_combos:
            goforit_2pc = flags[0]
            goforit_fg = flags[1]

            df = simulate_overtimes(current_season, n2, goforit_2pc, goforit_fg, write_output=True, pool=pool)
            print(f'Ran {n2} simulations in the {season} season. '
                  f'{"Going for 2pc" if goforit_2pc else "Kicking extra points on matching TDs"}. '
                  f'{"Going for it on FG attempts" if goforit_fg else "Kicking tying field goals"}.')

            df_t = pd.DataFrame(df['Winning Team'].value_counts(normalize=True)).T
            df_t['season'] = season
            df_t['games'] = n2
            df_t['Go For It on Extra Points'] = goforit_2pc
            df_t['Go For It on FG attempts'] = goforit_fg
            df_t['Receiving Team Advantage'] = df_t['Receiving Team'] - df_t['Kicking Team']

            df_t = df_t[['season', 'Go For It on Extra Points', 'Go For It on FG attempts','games',
                         'Receiving Team', 'Kicking Team', 'TIE', 'Receiving Team Advantage']]

            dfs2.append(df_t)


        result = pd.concat(dfs2, ignore_index=True).rename(columns={
            'Receiving Team':'% Receiving Team Won',
            'Kicking Team':'% Kicking Team Won',
            'TIE': '% Tie'
        })

        result.to_csv(OUTPUT_DIR / f'OT_results_{current_season}_decisions.csv', index = False)
        print('Done')