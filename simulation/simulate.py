from pathlib import Path
import pandas as pd
from simulation.overtime_period import Overtime_Period
from multiprocessing import Pool, cpu_count

ROOT_DIR = r"C://Users//natel//PycharmProjects//NFL_Overtime_Model//"
output_dir = f'{ROOT_DIR}/output/'
def run_simulation(args):
    season, go_for_ties = args
    OT = Overtime_Period('Kicking Team', 'Receiving Team', 'Kicking Team', season, go_for_ties)
    OT.simulate()
    return OT.result()

def simulate_overtimes(season, n, go_for_ties = False, write_output = False):
    with Pool(cpu_count()) as pool:
        results = pool.map(run_simulation, [(season, go_for_ties)] * n)
        df = pd.DataFrame(results)
    if write_output:
        name = f'{season}_overtime{"_ties" if go_for_ties else ""}_{n}'
        if n<= 1000:
            df.to_csv(f'{output_dir}/{name}.csv', index=False)
        else:
            df.to_parquet(f'{output_dir}/{name}.parquet', index=False)
    return df


if __name__ == '__main__':

    simulations = {
        2011:[False],
        2013:[False],
        2015:[False],
        2016:[False],
        2017:[False],
        2024:[False, True],
        2025:[False, True],
    }

    n = 100

    for season in simulations.keys():
        for flag in simulations[season]:
            simulate_overtimes(season, n, flag, write_output=True)
