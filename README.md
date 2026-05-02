# NFL Overtime Model

**Nate Lewin**
FTMBA Class of 2027, UC Berkeley Haas
[linkedin.com/in/njlewin/](https://linkedin.com/in/njlewin/) | [github.com/njlewin/](https://github.com/njlewin/)

---

## Summary
In 2025 the NFL introduced new overtime rules and the optimal strategy between kicking and receiving is still unknown. Previously, the consensus opinion was that the receiving team was at an advantage; the game was sudden-death (or a modified sudden-death) and the receiving team had the opportunity to end the game outright on their first offensive possession. Under the new rules which guarantee both teams at least one possession, the advantage is less clear. After one full season with the new rules, NFL coaches remain split on the decision, and, with only 17 games played under the rule, the sample size is too small to determine the correct outcome. In order to determine the optimal decision, thousands of overtimes were simulated under the new ruleset in order to determine the long-run average result between kicking and receiving.

The results found that the receiving team has a 7.5% win rate advantage over the kicking team. The core reason for this is after the two guaranteed possessions each possession is less likely than the last. 56.3% of overtimes end in two possessions, 22.1% of overtimes end on the third possession, 11.6% end on the fourth possession. 6.4% on the fifth, and so on. Games that end in two possessions slightly favor the kicking team, as they have the advantage of knowing what the receiving accomplished on their first possession and can plan appropriately. However, games that last at least three possessions overwhelmingly favor the receiving team, as they have the first chance to end the game once it is effectively sudden-death.

The kicking team has several decision points where they can optimize their play. Going for two point conversions when the kicking team scores a touchdown to match the receiving team reduces the advantage by 2%, as the conversion rate on a two point attempt is better than their win rate on overtimes that go to a third possession. Though they should play conservatively on game tying field goals, as their odds of winning or tying after a field goal are better than the odds of converting a fourth down attempt and subsequently scoring a touchdown.

## Project Structure

```
NFL_Overtime_Model/
├── NFL_Overtime_Model.ipynb   # Main write-up and results
├── config.py                  # Paths, file names, and simulation parameters
├── simulation/
│   ├── drive_selection.py     # Algorithm to match to simulated game state to historical drives
│   ├── overtime_period.py     # Core overtime simulation logic
│   ├── rules.py               # Overtime ruleset implementations
│   └── simulate.py            # Batch simulation runner
├── analysis/
│   ├── analysis.ipynb         # Supporting analysis and figure generation
│   └── assets/                # Charts and data used in the write-up
├── data/                      # Raw play-by-play data, data processing scripts, and processed data
└── output/                    # Simulation result CSVs
```
### Data

NFL play-by-play data pulled using [nfl_daya_py](https://pypi.org/project/nfl-data-py/) package. 