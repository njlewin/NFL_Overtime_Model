import pandas as pd
import numpy as np
import random
from pathlib import Path
from drive_selection import select_drive

DATA_DIR = Path(r"C:\Users\natel\PycharmProjects\NFL_Overtime_Model\data")
drive_list = pd.read_csv(DATA_DIR / "drive_list.csv")
ko_list = pd.read_csv(DATA_DIR / "ko_list.csv")
conversion_rates = pd.read_csv(DATA_DIR / "conversion_rates.csv").T[0].to_dict()

class Overtime_Period:
    def __init__(self, team_0: str, team_1: str, kicking_team: str, season: int = 2025):
        self.teams = [team_0, team_1]
        self.score = [0,0]
        self.season = season
        self.had_possession = [False, False]
        self.scored_TD = [False, False]
        self.scored_FG = [False, False]
        self.posteam = self.teams.index(kicking_team)
        self.yardline = 35
        self.drive_count = 0
        self.time_remaining = 600
        self.summary = ""
        self.safety_scored = False

    def set_posteam(self, team_index: int):
        self.posteam = team_index

    def switch_posteam(self):
        # Flip possession t2o whichever team does not currently have the ball
        self.set_posteam(int(not self.posteam))

    def simulate(self):
        self.kickoff(self.posteam)
        while not self.game_over():
            self.summary+=(f'{self.teams[0]}: {self.score[0]}, {self.teams[1]}: {self.score[1]}. '
                  f' {int(self.time_remaining)//60}:{int(self.time_remaining)%60:02d} Remaining\n')
            self.add_drive()
        if self.get_winner() == "TIE":
            self.summary+= 'The game ends in a tie.'
        else:
            self.summary+=f'{self.get_winner()} wins.'
        return self.result()

    def position_text(self):
        return f'their own {100-self.yardline} yardline' if self.yardline > 50 \
                else f'the opponents {self.yardline}'

    def kickoff(self, kickoff_team: int):
        self.posteam = kickoff_team
        ko_result = ko_list[ko_list['season'] == self.season].sample(1).iloc[0]
        self.summary += f'{self.teams[self.posteam]} kicks off. '
        if(ko_result.loc['return_touchdown'] == True):
            self.switch_posteam()
            self.score[self.posteam] += 6
            self.summary += f'{self.teams[int (not self.posteam)]} returns it for a touchdown.'
            self.extra_point()
            if not self.game_over():
                self.kickoff(kickoff_team)
        else:
            self.yardline = int(ko_result.loc['starting_field_position'])
            self.summary+='\n'
            starting_position = self.position_text()
            self.switch_posteam()

    def go_for_two(self):
        score_diff = self.score[self.posteam] - self.score[int(not self.posteam)]
        if score_diff == 2:
            return True
        else:
            return False

    def extra_point(self):
        if self.go_for_two():
            if random.random() < conversion_rates['two_point_percentage']:
                self.score[self.posteam] += 2
                self.summary+= f'Two point conversion is good.\n'
            else:
                self.summary+= f'Two point conversion failed.\n'
        else:
            if random.random() < conversion_rates['extra_point_percentage']:
                self.score[self.posteam] += 1
                self.summary+= f'Extra point is good.\n'
            else:
                self.summary+= f'Extra point failed.\n'

    def add_drive(self):
        self.summary+=(f'{self.teams[self.posteam]} starts their drive at {self.position_text()}\n')
        self.had_possession[self.posteam] = True
        self.drive_count += 1
        score_diff = self.score[self.posteam] - self.score[int (not self.posteam)]
        drive = select_drive(drive_list, self.yardline, self.time_remaining, score_diff)

        self.time_remaining -= drive['time_elapsed']
        if drive['drive_result'] == 'PUNT':
            self.summary+=f'{self.teams[self.posteam]} punts.\n'
            self.switch_posteam()
            self.yardline = drive['next_drive_start_yardline']
        elif drive['drive_result'] == 'TOUCHDOWN':
            self.summary+=f'{self.teams[self.posteam]} scores a touchdown.\n'
            self.scored_TD[self.posteam] = True
            self.score[self.posteam] += 6
            self.extra_point()
            self.kickoff(self.posteam)
        elif drive['drive_result'] == 'FIELD_GOAL':
            self.summary += f'{self.teams[self.posteam]} kicks a field goal.\n'
            self.scored_FG[self.posteam] = True
            self.score[self.posteam] += 3
            self.kickoff(self.posteam)
        elif drive['drive_result'] in ['END_GAME','END_HALF']:
            self.summary += 'Time runs out.\n'
            self.time_remaining = 0
        elif drive['drive_result'] in ['FUMBLE', 'INTERCEPTION','DOWNS', 'MISSED_FG',
                                       'BLOCKED_FG','BLOCKED_FG', 'BLOCKED_PUNT,_DOWNS','BLOCKED_FG,_DOWNS']:
            self.summary += f'{self.teams[self.posteam]} turns the ball over via {drive["drive_result"]}.\n'
            self.yardline = drive['next_drive_start_yardline']
            self.switch_posteam()
        elif drive['drive_result'] in ['SAFETY', 'FUMBLE,_SAFETY', 'BLOCKED_PUNT,_SAFETY']:
            self.summary += (f'{self.teams[int (not self.posteam)]} scores via '
                             f'{drive["drive_result"].replace(',_', ' and ')}.\n')
            self.safety_scored = True
            self.kickoff(self.posteam)

    def game_over(self) -> bool:
        if self.time_remaining <= 0:
            return True
        else:
            return False

    def result(self) -> dict:
        return {
            "winner": self.get_winner(),
            "score": self.score,
            "time_remaining": self.time_remaining,
            "OT Summary": self.summary,
        }

    def get_winner(self) -> str | None:
        if self.score[0] > self.score[1]:
            return self.teams[0]
        elif self.score[1] > self.score[0]:
            return self.teams[1]
        return 'TIE'


if __name__ == '__main__':
    OT = Overtime_Period('Team A', 'Team B', 'Team A')
    OT.simulate()
    print(OT.summary)