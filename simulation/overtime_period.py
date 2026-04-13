import pandas as pd
import numpy as np
import random
from pathlib import Path
from drive_selection import select_drive
from rules import game_over, overtime_length

DATA_DIR = Path(r"C:\Users\natel\PycharmProjects\NFL_Overtime_Model\data")
drive_list = pd.read_csv(DATA_DIR / "drive_list.csv")
ko_list = pd.read_csv(DATA_DIR / "ko_list.csv")
conversion_rates = pd.read_csv(DATA_DIR / "conversion_rates.csv").T[0].to_dict()
fourth_downs = pd.read_csv(DATA_DIR / "fourth_down_attempts.csv")

class Overtime_Period:
    def __init__(self, team_0: str, team_1: str, kicking_team: str, season: int = 2025):
        self.teams = [team_0, team_1]
        self.score = [0,0]
        self.season = season
        self.kicking_team = kicking_team
        self.had_possession = [False, False]
        self.scored_TD = [False, False]
        self.scored_FG = [False, False]
        self.scores = [[],[]]
        self.posteam = self.teams.index(kicking_team)
        self.yardline = 35
        self.drive_count = [0,0]
        self.time_remaining = overtime_length(season)
        self.summary = ""
        self.safety_scored = False

    def set_posteam(self, team_index: int):
        self.posteam = team_index

    def switch_posteam(self):
        # Flip possession t2o whichever team does not currently have the ball
        self.set_posteam(int(not self.posteam))

    def time_and_score(self):
        return (f'{self.teams[0]}: {self.score[0]}, {self.teams[1]}: {self.score[1]}. '
                  f' {int(self.time_remaining)//60}:{int(self.time_remaining)%60:02d} Remaining\n')
    def simulate(self):
        self.kickoff(self.posteam)
        while not game_over(self):
            self.summary+= self.time_and_score()
            self.add_drive()
        if self.get_winner() == "TIE":
            self.summary+= f'The game ends in a tie. {self.time_and_score()}'
        else:
            self.summary+=f'{self.get_winner()} wins. {self.time_and_score()}'
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
            self.summary += f'{self.teams[self.posteam]} returns it for a touchdown.'
            self.extra_point()
            if not game_over(self):
                self.kickoff(kickoff_team)
        else:
            self.yardline = int(ko_result.loc['starting_field_position'])
            self.summary+='\n'
            starting_position = self.position_text()
            self.switch_posteam()

    def go_for_two(self):
        score_diff = self.score[self.posteam] - self.score[int(not self.posteam)]
        if score_diff == -1:
            return True
        else:
            return False
    def score_touchdown(self):
        self.score[self.posteam] += 6
        self.scores[self.posteam].append('TD')
        self.scored_TD[self.posteam] = True
        self.extra_point()
        if not game_over(self):
            self.kickoff(self.posteam)

    def score_field_goal(self):
        self.score[self.posteam] += 3
        self.scores[self.posteam].append('FG')
        self.scored_FG[self.posteam] = True
        if not game_over(self):
            self.kickoff(self.posteam)

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

    def fourth_down_attempt(self, start_yardline, ydstogo):
        min_diff = (fourth_downs['ydstogo'] - ydstogo).abs().min()
        attempt = fourth_downs[(fourth_downs['ydstogo'] - ydstogo).abs() == min_diff].sample(1).iloc[0]
        self.yardline = min(max(start_yardline + attempt['yards_gained'], 1), 99)
        if attempt['off_td'] == 1:
            self.score_touchdown()
            self.summary+=f'{self.teams[self.posteam]} went for it on fourth down and scored a touchdown.\n'
        elif attempt['def_td'] ==1:
            self.switch_posteam()
            self.score_touchdown()
            self.summary+=(f'{self.teams[self.posteam]} went for it on fourth down, turned it over and the '
                           f'{self.teams[int(not self.posteam)]} scored a touchdown.\n')
        if attempt['fourth_down_failed'] == 1:
            self.summary+=f'{self.teams[self.posteam]} went for it and failed on fourth down.\n'
            self.switch_posteam()
        else:
            self.summary+=f'{self.teams[self.posteam]} went for it and succeeded on fourth down.\n'
            self.add_drive()

    def add_drive(self):
        self.summary+=(f'{self.teams[self.posteam]} starts their drive at {self.position_text()}\n')
        self.had_possession[self.posteam] = True
        self.drive_count[self.posteam] += 1
        score_diff = self.score[self.posteam] - self.score[int (not self.posteam)]
        drive = select_drive(drive_list, self.yardline, self.time_remaining, score_diff, self.season)

        self.time_remaining = max(0, self.time_remaining - drive['time_elapsed'])
        if drive['drive_result'] == 'PUNT':
            # IF the game would be over, the team needs to go for it on fourth down
            if game_over(self):
                self.fourth_down_attempt(drive['last_play_yardline'], drive['last_ydstogo'])
            else:
                self.summary+=f'{self.teams[self.posteam]} punts.'
                self.switch_posteam()
                if drive['defteam_TD'] == True:
                    self.summary+= f'{self.teams[self.posteam]} returns it for a touchdown.\n'
                    self.score_touchdown()
                else:
                    self.yardline = drive['next_drive_start_yardline']
                    self.summary += '\n'
        elif drive['drive_result'] == 'TOUCHDOWN':
            self.summary+=f'{self.teams[self.posteam]} scores a touchdown.\n'
            self.score_touchdown()
        elif drive['drive_result'] == 'FIELD_GOAL':
            if self.score[self.posteam] + 3 < self.score[int(not self.posteam)] and game_over(self):
                self.fourth_down_attempt(drive['last_play_yardline'], drive['last_ydstogo'])
            else:
                self.summary += f'{self.teams[self.posteam]} kicks a field goal.\n'
                self.score_field_goal()

        elif drive['drive_result'] in ['END_GAME','END_HALF']:
            self.summary += 'Time runs out.\n'
            self.time_remaining = 0
        elif drive['drive_result'] in ['FUMBLE', 'INTERCEPTION','DOWNS', 'MISSED_FG',
                                       'BLOCKED_FG','BLOCKED_FG', 'BLOCKED_PUNT,_DOWNS','BLOCKED_FG,_DOWNS']:
            self.had_possession[int(not self.posteam)] = True
            self.summary += f'{self.teams[self.posteam]} turns the ball over via {drive["drive_result"]}.'
            self.switch_posteam()
            if drive['defteam_TD'] == True:
                self.summary += f'{self.teams[self.posteam]} returns it for a touchdown.\n'
                self.score_touchdown()
            else:
                self.yardline = drive['next_drive_start_yardline']
                self.summary += '\n'
        elif drive['drive_result'] in ['SAFETY', 'FUMBLE,_SAFETY', 'BLOCKED_PUNT,_SAFETY']:
            self.summary += (f'{self.teams[int (not self.posteam)]} scores via '
                             f'{drive["drive_result"].replace(',_', ' and ')}.\n')
            self.switch_posteam()
            self.score[self.posteam]+=2
            self.safety_scored = True
            self.scores[self.posteam].append('SFTY')
            if not game_over(self):
                self.kickoff(self.posteam)

    def result(self) -> dict:
        return {
            "Team 0": self.teams[0],
            'Team 1': self.teams[1],
            'Kicking Team': self.kicking_team,
            'Winning Team': self.get_winner(),
            'Kicking Team Won': self.kicking_team == self.get_winner(),
            'Receiving Team Won': self.kicking_team != self.get_winner() and self.get_winner() != 'TIE',
            'Tie Game': self.get_winner() == 'TIE',
            "Team 0 Score": self.score[0],
            "Team 0 Scoring": self.scores[0],
            "Team 1 Score": self.score[1],
            "Team 1 Scoring": self.scores[1],
            "Team 0 Drives": self.drive_count[0],
            "Team 1 Drives": self.drive_count[1],
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
    n = 10000

    results = []
    for i in range(n):
        OT = Overtime_Period('Kicking Team', 'Receiving Team', 'Kicking Team', 2025)
        OT.simulate()
        results.append(OT.result())
    result_df = pd.DataFrame(results)
    result_df.to_csv('overtime.csv')
    print(result_df['Winning Team'].value_counts())