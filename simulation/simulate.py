from pathlib import Path
import pandas as pd
from simulation.overtime_period import Overtime_Period
from multiprocessing import Pool, cpu_count
from config import *

def run_simulation(args):
    season, go_for_ties = args
    OT = Overtime_Period('Kicking Team', 'Receiving Team', 'Kicking Team', season, go_for_ties)
    OT.simulate()
    return OT.result()

def run_simulation_batch(args):
    season, go_for_ties, batch_size = args
    results = []
    for _ in range(batch_size):
        OT = Overtime_Period('Kicking Team', 'Receiving Team', 'Kicking Team', season, go_for_ties)
        OT.simulate()
        results.append(OT.result())
    return results

def simulate_overtimes(season, n, go_for_ties=False, write_output=False, pool=None):
    n_workers = cpu_count()
    batch_size = n // n_workers
    args = [(season, go_for_ties, batch_size)] * n_workers

    batched_results = pool.map(run_simulation_batch, args)
    results = [item for batch in batched_results for item in batch]  # flatten

    df = pd.DataFrame(results)
    if write_output:
        name = f'{season}_overtime{"_ties" if go_for_ties else ""}_{n}'
        df.to_csv(output_file(season, n, go_for_ties), index=False)
    return df

if __name__ == '__main__':

    simulations = {
        # 2011:[False],
        # 2013:[False],
        # 2015:[False],
        # 2016:[False],
        # 2017:[False],
        # 2024:[False, True],
        2025:[False, True],
    }

    n = SIM_NUM

    with Pool(cpu_count()) as pool:
        for season, flags in simulations.items():
            for flag in flags:
                simulate_overtimes(season, n, flag, write_output=True, pool=pool)

                print(f'Ran {n} simulations in the {season} season. '
                      f'{"Aggressive on ties" if not flag else "Conservative on ties"}.')
