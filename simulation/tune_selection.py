"""
Tune drive-selection parameters.

Stage 1 - feature weights (w_time, w_yardline), with every situation held at the
          n_min variety floor so all settings are compared at equal variety.
          Ranked by worst-case REGRET: each situation's combined error divided by
          the best that situation achieves anywhere in the search. A situation
          with little data is judged against its own best, so it can't dictate
          the result. Coarse grid first, then a finer grid around the winner.

Stage 2 - global bandwidth h0, at the chosen weights: the largest h0 whose
          errors stay within SLACK * TOL of the floor-only errors in every
          situation. Coarse grid to find the boundary, then bisection to refine it.

Fixed by design, not searched:
  w_matchup = 1  (anchor: at equal variety only weight RATIOS matter)
  w_score        (only needs to be large enough that bucket_match stays 1.0)
  n_min          (variety floor: a judgment call about acceptable outcome noise;
                  error-based tuning would always choose the smallest value)
"""
from itertools import product

import numpy as np
import pandas as pd

from config import *
from simulation.drive_selection import select_drive, score_bucket, prepare_drives

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# (yardline, seconds left, score diff, matchup): OT-realistic, offense tied or trailing
# (yardline, seconds left, score diff, matchup)
# Yardline is yards from the opponent's goal line: 65 = own 35, 90 = own 10.
SITUATIONS = [
    # First possession, typical starts
    (65, 600, 0, 0),     # touchback at own 35, full clock
    (70, 600, 0, -4),    # own 30, weaker offense
    (75, 600, 0, 4),     # own 25, stronger offense

    # Answering a FG (down 3)
    (65, 420, -3, 2),    # own 35, 7:00 left
    (75, 240, -3, -2),   # own 25, 4:00 left
    (70, 90, -3, 0),     # own 30, 1:30 left

    # Answering a TD (down 7)
    (65, 360, -7, 0),    # own 35, 6:00 left
    (75, 150, -7, 3),    # own 25, 2:30 left
    (70, 45, -7, -2),    # own 30, 0:45 left

    # Sudden death (tied, after matching scores or punts)
    (80, 300, 0, -3),    # own 20 after a punt, 5:00 left
    (60, 180, 0, 5),     # own 40 after a good punt return, 3:00 left

    # Field-position extremes
    (90, 420, 0, 0),     # backed up at own 10
    (40, 300, 0, 1),     # short field after a turnover (opponent's 40)

    # Midfield: short punts, returns, and turnovers
    (50, 540, 0, 0),     # midfield, early OT
    (55, 330, -3, -1),   # own 45, answering a FG
    (45, 210, 0, 2),     # opponent's 45 after a turnover, sudden death
    (50, 120, -7, 4),    # midfield, answering a TD, 2:00 left
    (58, 60, -3, -3),    # own 42, answering a FG, 1:00 left
]

# Random neutral-field situations (seeded so the test set stays the same between runs)
_rng = np.random.default_rng(42)
for _ in range(5):
    SITUATIONS.append((
        int(_rng.integers(40, 61)),                # opponent's 40 to own 40
        int(_rng.integers(30, 601)),               # 0:30 to 10:00 left
        int(_rng.choice([0, -3, -7])),             # tied, down 3, or down 7
        round(float(_rng.normal(0, 4)), 1),        # matchup, typical spread
    ))

SIT_COLS = [str(s) for s in SITUATIONS]

ERRORS = ['time_err', 'yard_err', 'match_err']
# What one "unit" of error means for each feature (your judgment call).
TOL = pd.Series({'time_err': 20, 'yard_err': 10, 'match_err': 1.0})

N_MIN = 30             # variety floor (effective number of drives)
POOL = 750              # candidate pool size
W_SCORE = 100            # bucket-mismatch penalty
W_MATCHUP = 1           # anchor weight
H0_FLOOR_ONLY = 1e-6    # an h0 this small puts every situation on the n_min floor
SLACK = 0.5             # Stage 2: errors may grow by at most SLACK * TOL above floor-only

W_TIME_COARSE = [4, 8, 16, 32, 64, 128, 256]
W_YARD_COARSE = [1, 2, 4, 8, 16, 32, 64]
FINE_FACTORS = [2 ** -0.5, 1, 2 ** 0.5]     # refine around the coarse winner

H0_COARSE = list(np.geomspace(0.01, 3.2, 12))
H0_BISECT_STEPS = 6


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(drive_list, **params):
    """Run every test situation with one parameter setting; return per-situation metrics."""
    rows = []
    for y, t, s, m in SITUATIONS:
        _, c, n_eff, h = select_drive(drive_list, y, t, s, m, **params)
        p = c['prob']
        rows.append(dict(
            situation=str((y, t, s, m)),
            time_err=(p * (c['half_time_left'].clip(upper=300) - min(t, 300)).abs()).sum(),
            yard_err=(p * (c['start_yardline'] - y).abs()).sum(),
            match_err=(p * (c['matchup'] - m).abs()).sum(),
            bucket_match=(p * (score_bucket(c['start_score_diff']) == score_bucket(s))).sum(),
            n_eff=n_eff,
            h=h,
            hit_floor=h > params['h0'],   # True if the bandwidth widened to reach n_min
        ))
    return pd.DataFrame(rows).set_index('situation')


def combined_error(per_sit):
    """Sum of tolerance-scaled errors, per situation."""
    return (per_sit[ERRORS] / TOL).sum(axis=1)


# ---------------------------------------------------------------------------
# Stage 1: weights
# ---------------------------------------------------------------------------

def run_weights(drive_list, pairs):
    """Evaluate (w_time, w_yardline) pairs at the variety floor."""
    rows = []
    for w_time, w_yard in pairs:
        per_sit = evaluate(drive_list, n=POOL, h0=H0_FLOOR_ONLY, n_min=N_MIN, w_score=W_SCORE,
                           w_time=w_time, w_yardline=w_yard, w_matchup=W_MATCHUP)
        row = dict(w_time=w_time, w_yardline=w_yard,
                   min_bucket=per_sit['bucket_match'].min())
        row.update(combined_error(per_sit).to_dict())
        rows.append(row)
    return pd.DataFrame(rows)


def rank_by_regret(res):
    """Add regret columns and sort, best first. Regret is relative to every setting in `res`."""
    res = res.drop_duplicates(['w_time', 'w_yardline'])
    res = res[res['min_bucket'] >= 0.99].copy()
    regret = res[SIT_COLS] / res[SIT_COLS].min()
    res['worst_regret'] = regret.max(axis=1)
    res['worst_regret_situation'] = regret.idxmax(axis=1)
    res['mean_regret'] = regret.mean(axis=1)
    return res.sort_values(['worst_regret', 'mean_regret'])


def tune_weights(drive_list):
    # Coarse pass
    coarse = run_weights(drive_list, product(W_TIME_COARSE, W_YARD_COARSE))
    best = rank_by_regret(coarse).iloc[0]

    # Fine pass around the coarse winner
    fine_pairs = [(round(best['w_time'] * a, 2), round(best['w_yardline'] * b, 2))
                  for a, b in product(FINE_FACTORS, FINE_FACTORS)]
    fine = run_weights(drive_list, fine_pairs)

    # Rank everything together, so regret is measured against the best seen anywhere
    ranked = rank_by_regret(pd.concat([coarse, fine], ignore_index=True))
    return ranked, ranked.iloc[0]


# ---------------------------------------------------------------------------
# Stage 2: global bandwidth
# ---------------------------------------------------------------------------

def tune_h0(drive_list, weights):
    base = dict(n=POOL, n_min=N_MIN, w_score=W_SCORE, w_matchup=W_MATCHUP, **weights)
    allowed = evaluate(drive_list, h0=H0_FLOOR_ONLY, **base)[ERRORS] + SLACK * TOL

    log = []

    def test(h0):
        per_sit = evaluate(drive_list, h0=h0, **base)
        ok = bool((per_sit[ERRORS] <= allowed).all().all())
        log.append(dict(h0=h0, all_within=ok,
                        n_situations_on_floor=int(per_sit['hit_floor'].sum()),
                        min_n_eff=per_sit['n_eff'].min(),
                        median_n_eff=per_sit['n_eff'].median(),
                        max_n_eff=per_sit['n_eff'].max()))
        return ok

    # Coarse pass: find the last passing and first failing h0.
    # Assumes errors grow with h0, so once a value fails, larger ones do too.
    last_pass, first_fail = None, None
    for h0 in H0_COARSE:
        if test(h0):
            last_pass = h0
        else:
            first_fail = h0
            break

    if last_pass is None:          # even the smallest h0 loosens matches too much
        best_h0 = H0_FLOOR_ONLY
    elif first_fail is None:       # everything passed: take the largest tested
        best_h0 = last_pass
    else:                          # bisect (in log space) between pass and fail
        lo, hi = last_pass, first_fail
        for _ in range(H0_BISECT_STEPS):
            mid = np.sqrt(lo * hi)
            if test(mid):
                lo = mid
            else:
                hi = mid
        best_h0 = lo

    return pd.DataFrame(log).sort_values('h0'), float(best_h0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 220)

    drive_list = pd.read_csv(DATA_DIR / DRIVE_FILE)
    drive_list = drive_list[(drive_list['season'] <= current_season) &
                            (drive_list['season'] >= current_season - DRIVE_LOOKBACK)]
    drive_list = prepare_drives(drive_list)
    # Stage 1
    ranked, best_w = tune_weights(drive_list)
    print("Stage 1: weights, top 10 by worst-case regret "
          "(situation columns are combined error at the n_min floor)\n")
    print(ranked.head(10).round(2).to_string(index=False))
    weights = dict(w_time=float(best_w['w_time']), w_yardline=float(best_w['w_yardline']))
    print("\nChosen weights:", weights)

    # Stage 2
    h0_log, best_h0 = tune_h0(drive_list, weights)
    print("\nStage 2: global bandwidth h0\n")
    print(h0_log.round(3).to_string(index=False))
    print(f"\nChosen h0: {best_h0:.4f}")

    # Final check
    final = dict(n=POOL, h0=round(best_h0, 4), n_min=N_MIN, w_score=W_SCORE,
                 w_matchup=W_MATCHUP, **weights)
    per_sit = evaluate(drive_list, **final)
    print("\nFinal setting by situation:\n")
    print(per_sit.round(2).to_string())
    if per_sit['bucket_match'].min() < 0.99:
        print("\nWARNING: wrong-bucket drives are being sampled; raise W_SCORE.")

    print("\nParameters to use as select_drive defaults:\n", final)