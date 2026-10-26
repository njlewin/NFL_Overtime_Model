import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from config import *
from simulation.rules import overtime_length


def score_bucket(diff):
    """Map score differential (offense perspective) to a situational bucket."""
    diff = np.asarray(diff)
    conditions = [diff <= -9, diff <= -4, diff <= -1, diff == 0, diff <= 3, diff <= 8]
    choices = ['down_multi', 'need_td', 'fg_ties', 'tied', 'up_fg', 'up_one_score']
    return np.select(conditions, choices, default='up_multi')

def transform_time(t, t_cap=300):
        """Log-capped time transform. Maps seconds remaining to [0, 1]."""
        t = np.minimum(np.asarray(t, dtype=float), t_cap)
        #return np.log1p(t) / np.log1p(t_cap)
        return np.sqrt(t / t_cap)

def kernel_probs(dist, h):
    """Gaussian kernel sampling probabilities for an array of distances at bandwidth h."""
    d2 = dist ** 2
    # Shift so the closest drive has weight 1; cancels on normalizing, prevents underflow.
    w = np.exp(-(d2 - d2.min()) / (2 * h ** 2))
    return w / w.sum()


def effective_n(prob):
    """Kish's effective sample size."""
    return 1 / np.sum(prob ** 2)


def bandwidth_for_neff(dist, target, iters=40):
    """Find the bandwidth h whose kernel weights give an effective sample size of `target`."""
    target = min(target, len(dist))
    lo, hi = 1e-6, max(dist.max(), 1e-6) * 10
    for _ in range(iters):
        mid = np.sqrt(lo * hi)
        if effective_n(kernel_probs(dist, mid)) < target:
            lo = mid        # too concentrated: widen
        else:
            hi = mid        # too spread out: narrow
    return hi


def choose_bandwidth(dist, h0, n_min):
    """Global bandwidth h0, widened only if it leaves fewer than n_min effective drives."""
    if effective_n(kernel_probs(dist, h0)) >= n_min:
        return h0
    return bandwidth_for_neff(dist, n_min)

def prepare_drives(drive_list):
    """Precompute situation-independent features once, before any select_drive calls."""
    d = drive_list.copy()
    d['half_time_left'] = np.where(d['start_time_left'] > 1800,
                                   d['start_time_left'] - 1800,
                                   d['start_time_left'])

    d = d[~d['start_time_left'].between(1801, 2400)]

    d['t_logcap'] = transform_time(d['start_time_left'])
    d['bucket'] = score_bucket(d['start_score_diff'])
    d.attrs['matchup_mu'] = d['matchup'].mean()
    d.attrs['matchup_sd'] = d['matchup'].std()
    d['matchup_z'] = (d['matchup'] - d.attrs['matchup_mu']) / d.attrs['matchup_sd']
    return d


def select_drive(drive_list: pd.DataFrame, yardline: float, time_remaining: float, score_diff: float, matchup = 0,
                 n = 750, h0=0.1121, n_min=30,
                 w_time = 8, w_yardline = 5.66, w_score = 100, w_matchup =  1):
    """
    Given a list of historical drives and a game situation, returns a
    randomly sampled drive from the top 5% most similar historical drives.

    Similarity is measured by weighted Euclidean distance across:
      - Field position (yardline)
      - Time remaining (non-linear — more sensitive late in game)
      - Score differential
    """

    drives = drive_list  # already prepared; no copy needed
    mu, sd = drives.attrs['matchup_mu'], drives.attrs['matchup_sd']

    dist = np.sqrt(
        w_yardline * ((drives['start_yardline'].to_numpy() - yardline) / 100) ** 2 +
        w_time * (drives['t_logcap'].to_numpy() - transform_time(time_remaining)) ** 2 +
        w_score * (drives['bucket'].to_numpy() != score_bucket(score_diff)) +
        w_matchup * (drives['matchup_z'].to_numpy() - (matchup - mu) / sd) ** 2
    )

    # n nearest drives, sorted by distance
    idx = np.argpartition(dist, n - 1)[:n]
    idx = idx[np.argsort(dist[idx])]
    candidates = drives.iloc[idx].copy()
    candidates['distance'] = dist[idx]

    dist = candidates['distance'].to_numpy()

    h = choose_bandwidth(dist, h0, n_min)
    candidates['prob'] = kernel_probs(dist, h)
    n_eff = effective_n(candidates['prob'].to_numpy())


    return candidates.sample(1, weights=candidates['prob']).iloc[0], candidates, n_eff, h


if __name__ == '__main__':

    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)


    drive_list = pd.read_csv(DATA_DIR/DRIVE_FILE)
    drive_list = drive_list[(drive_list['season']<=current_season) & (drive_list['season']>=current_season-DRIVE_LOOKBACK)]
    drive_list = prepare_drives(drive_list)
    import matplotlib.pyplot as plt

    # Compute yards gained once, on the full drive list, so every pool has it
    drive_list['yards_gained'] = np.where(drive_list['drive_result'] == 'TOUCHDOWN',
                                          drive_list['start_yardline'],
                                          drive_list['start_yardline'] - drive_list['last_play_yardline'])

    OUTCOMES = {
        'Touchdown': ['TOUCHDOWN'],
        'Field goal': ['FIELD_GOAL'],
        'Punt': ['PUNT'],
        'Turnover': ['FUMBLE', 'INTERCEPTION'],
    }


    def weighted_quantile(values, weights, q):
        """Quantile of `values` where each value counts with its sampling probability."""
        order = np.argsort(values)
        v, w = np.asarray(values)[order], np.asarray(weights)[order]
        cum = np.cumsum(w) / w.sum()
        return np.interp(q, cum, v)


    def sweep(param_name, values, fixed):
        """Run select_drive across `values` of one parameter; collect outcome rates, yards, n_eff."""
        out = {name: [] for name in OUTCOMES}
        out.update(yards_mean=[], yards_q25=[], yards_q75=[], n_eff=[])
        for v in values:
            args = {**fixed, param_name: v}
            _, c, n_eff, h = select_drive(drive_list, args['yardline'], args['time_remaining'],
                                          args['score_diff'], args['matchup'])
            p = c['prob'].to_numpy()
            for name, results in OUTCOMES.items():
                out[name].append(100 * (p * c['drive_result'].isin(results)).sum())
            yg = c['yards_gained'].to_numpy()
            ok = ~np.isnan(yg)  # skip drives with no last-play yardline
            out['yards_mean'].append(np.average(yg[ok], weights=p[ok]))
            out['yards_q25'].append(weighted_quantile(yg[ok], p[ok], 0.25))
            out['yards_q75'].append(weighted_quantile(yg[ok], p[ok], 0.75))
            out['n_eff'].append(n_eff)
        return out


    def plot_outcomes(ax, x, res, xlabel):
        for name in OUTCOMES:
            ax.plot(x, res[name], marker='o', markersize=3, label=name)
        ax.set_xlabel(xlabel)
        ax.set_ylabel('% of drives')
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc='best')


    def plot_yards(ax, x, res, xlabel):
        ax.plot(x, res['yards_mean'], color='tab:purple', marker='o', markersize=3, label='Mean')
        ax.fill_between(x, res['yards_q25'], res['yards_q75'], color='tab:purple', alpha=0.2,
                        label='25th–75th percentile')
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Yards gained')
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc='best')


    def plot_neff(ax, x, res, xlabel, n_min=30):
        ax.plot(x, res['n_eff'], color='gray', marker='o', markersize=3, label='n_eff')
        ax.axhline(n_min, color='red', linestyle='--', linewidth=1, label=f'n_min = {n_min}')
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Effective sample size')
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc='best')


    def situation_error(y, t, s, m):
        _, c, n_eff, h = select_drive(drive_list, y, t, s, m)
        p = c['prob']
        groups = {'Touchdown': ['TOUCHDOWN'], 'Field goal': ['FIELD_GOAL'],
                  'Punt': ['PUNT'], 'Turnover': ['FUMBLE', 'INTERCEPTION']}
        print(f"n_eff = {n_eff:.1f}, h = {h:.3f}")
        for name, results in groups.items():
            rate = (p * c['drive_result'].isin(results)).sum()
            se = np.sqrt(rate * (1 - rate) / n_eff)
            print(f"{name:11s} {100 * rate:5.1f}%  ± {100 * se:4.1f} (95%: ± {196 * se:4.1f})")
        print(f"time err  {(p * (c['half_time_left'].clip(upper=300) - min(t, 300)).abs()).sum():.1f} s")
        print(f"yard err  {(p * (c['start_yardline'] - y).abs()).sum():.1f} yd")
        print(f"match err {(p * (c['matchup'] - m).abs()).sum():.2f} pts")


    # --- Sweeps ---
    base = dict(yardline=65, time_remaining=600, score_diff=0, matchup=0)
    matchups = np.linspace(-12, 13, 40)
    yardlines = np.arange(20, 96, 2)  # opponent's 20 to own 5
    times = np.arange(10, 601, 15)  # 0:10 to 10:00

    by_matchup = sweep('matchup', matchups, base)
    by_yardline = sweep('yardline', yardlines, base)
    by_time = sweep('time_remaining', times, base)

    # --- Plot ---
    columns = [
        (matchups, by_matchup, 'Matchup ranking',
         f"By matchup (yardline {base['yardline']}, {base['time_remaining']}s left)"),
        (yardlines, by_yardline, 'Starting yardline (yards from opponent goal)',
         f"By starting yardline (matchup {base['matchup']}, {base['time_remaining']}s left)"),
        (times, by_time, 'Seconds remaining',
         f"By time remaining (yardline {base['yardline']}, matchup {base['matchup']})"),
    ]

    fig, axes = plt.subplots(3, 3, figsize=(21, 14), sharex='col')
    for col, (x, res, xlabel, title) in enumerate(columns):
        plot_outcomes(axes[0, col], x, res, xlabel)
        plot_yards(axes[1, col], x, res, xlabel)
        plot_neff(axes[2, col], x, res, xlabel)
        axes[0, col].set_title(title)

    fig.suptitle(f"Score diff {base['score_diff']}")
    plt.tight_layout()
    plt.show()