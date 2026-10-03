from dataclasses import dataclass

@dataclass(frozen=True)
class Team:
    name: str
    osrs: float
    dsrs: float

    def __str__(self) -> str:
        return self.name