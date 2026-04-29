"""
Overtime_Period class for simulating NFL overtime periods drive-by-drive.
Part of the NFL Overtime Monte Carlo simulation project.
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path
from simulation.drive_selection import select_drive
from simulation.rules import game_over, overtime_length
import time
from multiprocessing import Pool, cpu_count
from config import *

drive_list = pd.read_csv(DATA_DIR / DRIVE_FILE)
ko_list = pd.read_csv(DATA_DIR / KO_FILE)
conversion_rates = pd.read_csv(DATA_DIR / CONVERSION_FILE).T[0].to_dict()
fourth_downs = pd.read_csv(DATA_DIR / FOURTH_DOWN_FILE)


class Overtime_Period:
    """
    Simulates an NFL overtime period drive-by-drive using historical play data.

    Drives are sampled from a database of historical NFL drives using weighted
    Euclidean distance across field position, time remaining, and score differential.
    Decision overrides are applied where historical drives would produce irrational
    outcomes (e.g. punting when trailing with no possessions remaining).

    Args:
        team_0: Name of the first team (kicking team)
        team_1: Name of the second team (receiving team)
        kicking_team: Name of the team kicking off to start OT
        season: NFL season year, used to apply correct overtime rules and sample
                season-appropriate kickoffs
        go_for_ties: If True, team accepts ties by kicking PAT when down 1 and
                taking a tying FG when down 3, rather than going for the win

    """

    def __init__(self, team_0: str, team_1: str, kicking_team: str, season: int = 2025, goforit_2pc = False, goforit_fg = False):
        self.teams = [team_0, team_1]
        self.score = [0, 0]
        self.season = season
        self.kicking_team = kicking_team
        self.had_possession = [False, False]
        self.poscount = [0,0]
        self.scored_TD = [False, False]
        self.scored_FG = [False, False]
        self.posresults = [[], []]
        self.posteam = self.teams.index(kicking_team)
        self.yardline = 35
        self.drive_count = [0, 0]
        self.time_remaining = overtime_length(season)
        self.summary = ""
        self.safety_scored = False
        self.goforit_2pc = goforit_2pc
        self.goforit_fg = goforit_fg

    def set_posteam(self, team_index: int):
        self.posteam = team_index

    def switch_posteam(self):
        # Toggles between index 0 and 1
        self.set_posteam(int(not self.posteam))

    def time_and_score(self):
        return (f'{self.teams[0]}: {self.score[0]}, {self.teams[1]}: {self.score[1]}. '
                f' {int(self.time_remaining) // 60}:{int(self.time_remaining) % 60:02d} Remaining\n')

    def simulate(self):
        """
        Run a full overtime period simulation from kickoff to final result.

        Returns:
            dict: Game result containing winner, scores, drive counts, and summary log.
                  See result() for full schema.
        """
        self.kickoff(self.posteam)
        while not game_over(self):
            self.summary += self.time_and_score()
            self.add_drive()
        if self.get_winner() == "TIE":
            self.summary += f'The game ends in a tie. {self.time_and_score()}'
        else:
            self.summary += f'{self.get_winner()} wins. {self.time_and_score()}'
        return self.result()

    def position_text(self):
        return f'their own {100 - self.yardline} yardline' if self.yardline > 50 \
            else f'the opponents {self.yardline} yardline'

    def kickoff(self, kickoff_team: int):
        """
        Simulate a kickoff by sampling a historical kickoff result from the same season.
        Handles kickoff return touchdowns. Sets yardline for the receiving team's drive.

        Args:
            kickoff_team: Index (0 or 1) of the team kicking off
        """
        self.posteam = kickoff_team
        ko_result = ko_list[ko_list['season'] == self.season].sample(1).iloc[0]
        self.summary += f'{self.teams[self.posteam]} kicks off. '
        self.switch_posteam()
        self.time_remaining-=ko_result.loc['time_elapsed']
        if ko_result.loc['return_touchdown'] == True:
            self.had_possession[self.posteam] = True
            self.poscount[self.posteam]+=1
            self.posresults[self.posteam].append('RETURN TOUCHDOWN')
            self.summary += f'{self.teams[self.posteam]} returns it for a touchdown.\n'
            self.score_touchdown()
        else:
            self.yardline = int(ko_result.loc['starting_field_position'])
            self.summary += '\n'

    def go_for_two(self):
        """
        Determine whether the possession team should attempt a 2-point conversion.
        Only returns True when down 1 and the 2pc go for it flag is true.
        """
        score_diff = self.score[self.posteam] - self.score[int(not self.posteam)]
        if score_diff == -1 and self.goforit_2pc:
            return True
        else:
            return False

    def score_touchdown(self):
        """Record a touchdown, attempt PAT, and kick off if the game continues."""
        self.score[self.posteam] += 6
        self.scored_TD[self.posteam] = True
        self.extra_point()
        if not game_over(self):
            self.kickoff(self.posteam)

    def score_field_goal(self):
        """Record a field goal and kick off if the game continues."""
        self.score[self.posteam] += 3
        self.scored_FG[self.posteam] = True
        if not game_over(self):
            self.kickoff(self.posteam)

    def extra_point(self):
        """Attempt a PAT or 2-point conversion based on go_for_two() logic."""
        if self.go_for_two():
            if random.random() < conversion_rates['two_point_percentage']:
                self.score[self.posteam] += 2
                self.summary += f'Two point conversion is good.\n'
            else:
                self.summary += f'Two point conversion failed.\n'
        else:
            if random.random() < conversion_rates['extra_point_percentage']:
                self.score[self.posteam] += 1
                self.summary += f'Extra point is good.\n'
            else:
                self.summary += f'Extra point failed.\n'

    def fourth_down_attempt(self, start_yardline, ydstogo):
        """
        Simulate a 4th down conversion attempt using historical 4th down play data.
        Used as an override when punting or kicking a FG would be irrational.
        Matches to the historical attempt with the closest yards-to-go.

        Args:
            start_yardline: Field position at the start of the 4th down play (1-99)
            ydstogo: Yards needed for a first down
        """
        min_diff = (fourth_downs['ydstogo'] - ydstogo).abs().min()
        attempt = fourth_downs[(fourth_downs['ydstogo'] - ydstogo).abs() == min_diff].sample(1).iloc[0]
        self.yardline = min(max(start_yardline - attempt['yards_gained'], 1), 99)

        if attempt['off_td'] == 1:
            self.summary += f'{self.teams[self.posteam]} went for it on fourth down and scored a touchdown.\n'
            self.score_touchdown()
        elif attempt['def_td'] == 1:
            self.switch_posteam()
            self.had_possession[self.posteam] = True
            self.poscount[self.posteam] += 1
            self.summary += (f'{self.teams[self.posteam]} went for it on fourth down, turned it over and '
                             f'{self.teams[int(not self.posteam)]} scored a touchdown.\n')
            self.score_touchdown()
        elif attempt['fourth_down_failed'] == 1:
            self.summary += f'{self.teams[self.posteam]} went for it and failed on fourth down.\n'
            self.switch_posteam()
        else:
            self.summary += f'{self.teams[self.posteam]} went for it and succeeded on fourth down.\n'
            # Add drive adds one to the possession count, remove one from the count here to avoid double counting
            self.poscount[self.posteam] -= 1
            self.add_drive()


    def add_drive(self):
        """
        Simulate a single offensive drive by sampling a comparable historical drive.

        Drive selection uses weighted Euclidean distance across field position,
        time remaining, and score differential. Decision overrides are applied
        for punts and field goals where the historical outcome would be irrational
        given the current game state.
        """
        self.summary += (f'{self.teams[self.posteam]} starts their drive at {self.position_text()}\n')
        self.drive_count[self.posteam] += 1
        score_diff = self.score[self.posteam] - self.score[int(not self.posteam)]

        earliest_year = max(drive_list['season'].min(), self.season - 10)
        drive, candidates = select_drive(drive_list[drive_list['season'].isin(range(earliest_year, self.season+1))],
                                         self.yardline, self.time_remaining, score_diff, self.season)
        # if (drive['drive_result'] in ['END_GAME', 'END_HALF']
        #         and not (self.had_possession[0] and self.had_possession[1])):
        #     drive = candidates[~candidates['drive_result'].isin(['END_GAME', 'END_HALF'])].sample(1).iloc[0]

        self.had_possession[self.posteam] = True
        self.poscount[self.posteam] += 1
        self.posresults[self.posteam].append(drive['drive_result'])
        self.time_remaining = max(0, self.time_remaining - drive['time_elapsed'])

        if drive['drive_result'] == 'PUNT':
            # Override: go for it if punting would end the game without a score
            if game_over(self):
                self.fourth_down_attempt(drive['last_play_yardline'], drive['last_ydstogo'])
            else:
                self.summary += f'{self.teams[self.posteam]} punts.'
                self.switch_posteam()
                if drive['defteam_TD'] == True:
                    self.summary += f'{self.teams[self.posteam]} returns it for a touchdown.\n'
                    self.score_touchdown()
                else:
                    self.yardline = drive['next_drive_start_yardline']
                    self.summary += '\n'

        elif drive['drive_result'] == 'TOUCHDOWN':
            self.summary += f'{self.teams[self.posteam]} scores a touchdown.\n'
            self.score_touchdown()

        elif drive['drive_result'] == 'FIELD_GOAL':
            fg_ties = self.score[self.posteam] + 3 == self.score[int(not self.posteam)]
            fg_loses = self.score[self.posteam] + 3 < self.score[int(not self.posteam)]

            # Override: go for it if a FG would not give the possession team the lead
            if fg_loses or (fg_ties and self.goforit_fg):
                self.fourth_down_attempt(drive['last_play_yardline'], drive['last_ydstogo'])
            else:
                self.summary += f'{self.teams[self.posteam]} kicks a field goal.\n'
                self.score_field_goal()

        elif drive['drive_result'] in ['END_GAME', 'END_HALF']:
            self.summary += 'Time runs out.\n'
            self.time_remaining = 0

        elif drive['drive_result'] in ['FUMBLE', 'INTERCEPTION', 'DOWNS', 'MISSED_FG',
                                       'BLOCKED_FG', 'BLOCKED_PUNT,_DOWNS', 'BLOCKED_FG,_DOWNS']:
            self.summary += f'{self.teams[self.posteam]} turns the ball over via {drive["drive_result"]}.'
            self.switch_posteam()
            if drive['defteam_TD'] == True:
                self.summary += f'{self.teams[self.posteam]} returns it for a touchdown.\n'
                self.switch_posteam()
                self.had_possession[self.posteam] = True
                self.poscount[self.posteam] += 1
                self.score_touchdown()
            else:
                self.yardline = drive['next_drive_start_yardline']
                self.summary += '\n'

        elif drive['drive_result'] in ['SAFETY', 'FUMBLE,_SAFETY', 'BLOCKED_PUNT,_SAFETY']:
            self.summary += (f'{self.teams[int(not self.posteam)]} scores via '
                             f'{drive["drive_result"].replace(",_", " and ")}.\n')
            self.score[int(not self.posteam)] += 2
            self.safety_scored = True



    def result(self) -> dict:
        """
        Return a dictionary summarising the overtime period result.

        Returns:
            dict with keys: Team 0, Team 1, Kicking Team, Winning Team,
            Kicking Team Won, Receiving Team Won, Tie Game, Team 0 Score,
            Team 0 Scoring, Team 1 Score, Team 1 Scoring, Team 0 Drives,
            Team 1 Drives, time_remaining, OT Summary
        """
        return {
            "Team 0": self.teams[0],
            'Team 1': self.teams[1],
            'Kicking Team': self.kicking_team,
            'Winning Team': self.get_winner(),
            'Kicking Team Won': int(self.kicking_team == self.get_winner()),
            'Receiving Team Won': int(self.kicking_team != self.get_winner() and self.get_winner() != 'TIE'),
            'Tie Game': int(self.get_winner() == 'TIE'),
            f"{self.teams[0]} Score": self.score[0],
            f"{self.teams[0]} Possession Results": self.posresults[0],
            f"{self.teams[1]} Score": self.score[1],
            f"{self.teams[1]} Possession Results": self.posresults[1],
            f"{self.teams[0]} Possessions": self.poscount[0],
            f"{self.teams[1]} Possessions": self.poscount[1],
            "Time Remaining": self.time_remaining,
            "OT Summary": self.summary,
        }

    def get_winner(self) -> str | None:
        if self.score[0] > self.score[1]:
            return self.teams[0]
        elif self.score[1] > self.score[0]:
            return self.teams[1]
        return 'TIE'
