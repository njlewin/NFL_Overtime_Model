import pandas as pd
import numpy as np

def select_drive(drive_list: pd.DataFrame, yardline: float, time_remaining: float, score_diff: float) -> pd.Series:
    """
    Given a list of historical drives and a game situation, returns a
    randomly sampled drive from the top 5% most similar historical drives.

    Similarity is measured by weighted Euclidean distance across:
      - Field position (yardline)
      - Time remaining (non-linear — more sensitive late in game)
      - Score differential
    """

    df = drive_list.copy()
    # --- Normalization constants ---
    MAX_YARDLINE = 99.0
    MAX_TIME = 600.0  # 10 min OT period
    MAX_SCORE_DIFF = 7.0
    TIME_LAMBDA = 0.004  # controls how aggressively late-game time is weighted

    # --- Weights ---
    W_YARDLINE = 0.45
    W_TIME = 0.1
    W_SCORE = 0.45

    RETURN_COUNT = 15

    # --- Compute deltas (normalized) ---
    d_yardline = (df["start_yardline"] - yardline) / MAX_YARDLINE
    d_time = (df["start_time_left"] - time_remaining) / MAX_TIME
    d_score = (df["start_score_diff"] - score_diff) / MAX_SCORE_DIFF

    # --- Non-linear time sensitivity ---
    # Grows exponentially as time_remaining approaches 0
    time_sensitivity = np.exp(TIME_LAMBDA * (MAX_TIME - time_remaining))

    # --- Weighted Euclidean distance ---
    df["_distance"] = np.sqrt(
        W_YARDLINE * d_yardline ** 2 +
        W_TIME * time_sensitivity * d_time ** 2 +
        W_SCORE * d_score ** 2
    )

    # --- Select top 1 closest drives and sample ---
    candidates = df.nsmallest(RETURN_COUNT, "_distance")

    # --- Random sample from candidates ---
    return candidates.drop(columns="_distance").sample(n=1).iloc[0]
