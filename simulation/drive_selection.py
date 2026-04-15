import pandas as pd
import numpy as np

from simulation.rules import overtime_length


def select_drive(drive_list: pd.DataFrame, yardline: float, time_remaining: float, score_diff: float, season) :
    """
    Given a list of historical drives and a game situation, returns a
    randomly sampled drive from the top 5% most similar historical drives.

    Similarity is measured by weighted Euclidean distance across:
      - Field position (yardline)
      - Time remaining (non-linear — more sensitive late in game)
      - Score differential
    """

    # --- Normalization constants ---
    MAX_YARDLINE = 99.0
    MAX_TIME = overtime_length(season)
    OT_LENGTH = overtime_length(season)  # 10 min OT period
    MAX_SCORE_DIFF = 7.0
    TIME_LAMBDA = 0.004  # controls how aggressively late-game time is weighted

    # --- Weights ---
    W_YARDLINE = 0.4
    W_TIME = 0.4
    W_SCORE = 0.2

    RETURN_COUNT = 100

    # --- Compute deltas (normalized) ---
    d_yardline = (drive_list["start_yardline"] - yardline) / drive_list["start_yardline"].std()
    d_time = (drive_list["start_time_left"] - time_remaining) / drive_list["start_time_left"].std()
    d_score = (drive_list["start_score_diff"] - score_diff) / MAX_SCORE_DIFF

    # --- Non-linear time sensitivity ---
    # Grows exponentially as time_remaining approaches 0
    time_sensitivity =1# np.exp(TIME_LAMBDA * (OT_LENGTH - time_remaining))

    # --- Weighted Euclidean distance ---
    distances = np.sqrt(
        W_YARDLINE * d_yardline ** 2 +
        W_TIME * time_sensitivity * d_time ** 2 +
        W_SCORE * d_score ** 2
    )

    # --- Select top closest drives and sample ---
    top_idx = distances.nsmallest(RETURN_COUNT).index

    candidates = drive_list.loc[top_idx]
    # --- Random sample from candidates ---
    return candidates.sample(1).iloc[0], candidates


if __name__ == "__main__":
    DATA_DIR = r"C://Users//natel//PycharmProjects//NFL_Overtime_Model//data"
    drive_list = pd.read_csv(f'{DATA_DIR}//drive_list.csv', index_col=0)

    result, candidates = select_drive(drive_list, 25, 30, 0, 2011)
    print(result)
