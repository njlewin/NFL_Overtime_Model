import pandas as pd

class Overtime_Period:

    time_dict = {'post2025':600}

    def __init__(self, team_a: str, team_b: str, kicking_team: str, rule: str = "post2025"):
        self.teams = [team_a, team_b]
        self.score = {team_a: 0, team_b: 0}
        self.had_possession = [team_a == kicking_team, team_b == kicking_team]
        self.scored_TD = [False, False]
        self.scored_FG = [False, False]
        self.rule = rule
        self.posteam = self.teams.index(kicking_team)
        self.yardline = 35
        self.drive_count = 0
        self.time_remaining = self.time_dict['post2025']
        self.drive_list = pd.read_csv("drive_list.csv")

    def switch_posteam(self):
        # Flip possession to whichever team does not currently have the ball
        current_index = self.teams.index(self.posteam)
        self.posteam = self.teams[1 - current_index]

    def simulate(self):
        self.kickoff(kickoff_team=self.posteam)
        while not self.game_over():
            self.add_drive()
        return self.result()

    def kickoff(self, kickoff_team: str):
        # TODO: look up kick result and set self.yardline to kick result
        # TODO: handle kickoff touchdown situations (e.g. kicking team scores, return TD)
        self.switch_posteam()
        self.add_drive()

    def add_drive(self):
        self.drive_count += 1
        # TODO: look up drive with similar game state
        #       (score differential, time remaining, starting yardline)
        # TODO: append drive result to drive log table

        if not self.game_over():
            # TODO: if drive ended in touchdown:
            #           go for one or two depending on self.for2 and game situation
            #           call self.kickoff()
            # TODO: if drive ended in field goal:
            #           kick (PAT or field goal attempt)
            # TODO: if drive ended in interception, fumble, punt, or turnover on downs:
            #           self.switch_posteam()
            #           self.add_drive()
            pass

    def game_over(self) -> bool:
        if self.rule == "post2025":
            # TODO: check if game has finished based on 2025 overtime rules
            pass
        elif self.rule == "2022_to_2024":
            # TODO: check if game has finished based on 2022-2024 overtime rules
            pass
        elif self.rule == "pre2022":
            # TODO: check if game has finished based on pre-2022 overtime rules
            pass

    def result(self) -> dict:
        return {
            "winner": self.get_winner(),
            "score": self.score,
            "drives": self.drive_log,
            "time_remaining": self.time_remaining
        }

    def get_winner(self) -> str | None:
        if self.score[0] > self.score[1]:
            return self.teams[0]
        elif self.score[1] > self.score[0]:
            return self.teams[1]
        return 'T'