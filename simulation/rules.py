from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from overtime_period import OvertimePeriod  # only imported for type hints, not at runtime


def game_over(ot: OvertimePeriod):
    if ot.time_remaining <= 0:
        return True
    elif ot.safety_scored:
        return True
    if ot.season >= 2025:
        return game_over_post2025(ot)
    elif ot.season >= 2012:
        return game_over_2012_2024(ot)
    elif ot.season < 2012:
        return game_over_pre2012(ot)
    else: return ot.time_remaining <=0

def game_over_post2025(ot: OvertimePeriod):
    if all(ot.had_possession) and ot.score[0] != ot.score[1]:
        return True
    else:
        return False

def game_over_2012_2024(ot) -> bool:
    # TD on first possession wins immediately
    if any(ot.scored_TD):
        return True
    # After both possess, any score difference wins
    elif all(ot.had_possession) and ot.score[0] != ot.score[1]:
        return True
    else:
        return False

def game_over_pre2012(ot) -> bool:
    if ot.score[0] != ot.score[1]:
        return True
    else:
        return False

def overtime_length(year):
    if year <=2016:
        return 60*15
    else:
        return 60*10
