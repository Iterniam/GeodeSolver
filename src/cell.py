from __future__ import annotations

from collections import defaultdict
from typing import Union

from src.Enums.geode_enum import GeodeEnum

import colorama

bad_colors = ['BLACK', 'WHITE', 'LIGHTBLACK_EX', 'RESET']
codes = vars(colorama.Back)
colors = [codes[color] for color in codes if color not in bad_colors]


class Cell:

    def __init__(self, row: int, col: int, projected_block: GeodeEnum):
        self.row = row
        self.col = col
        self.group_nr = -1
        self.projected_block = projected_block
        self.shortest_path_dict: dict[Cell, Union[int, float]] = defaultdict(lambda: float('inf'))
        self.average_block_distance: float = float('inf')
        self.reachable_pumpkins: int = 0
        self.neighbours: set[Cell] = set()

    def projected_str(self) -> str:
        return self.projected_block.pretty_print

    def group_str(self) -> str:
        color = colorama.Back.RESET if self.group_nr == -1 else colors[self.group_nr % len(colors)]
        val = self.group_nr if self.projected_block == GeodeEnum.PUMPKIN else '  '
        return f'{color}{val:02}{colorama.Back.RESET}'

    def merged_str(self) -> str:
        return self.group_str() if self.group_nr != -1 else self.projected_str()

    def distance_str(self, cell: Cell) -> str:
        color = colorama.Back.BLACK \
            if self.shortest_path_dict[cell] == float('inf') \
            else colors[self.shortest_path_dict[cell] % len(colors)]
        return f'{color}{self.shortest_path_dict[cell]:03}{colorama.Back.RESET}'

    def isolation_str(self) -> str:
        if self.projected_block in [GeodeEnum.AIR]:
            return '   '
        color = colorama.Back.BLACK \
            if self.average_block_distance == float('inf') \
            else colors[int(self.average_block_distance) % len(colors)]
        val = float('inf') if self.average_block_distance == float('inf') else int(self.average_block_distance)
        return f'{color}{val:03}{colorama.Back.RESET}'

    @property
    def has_group(self):
        return self.group_nr != -1

    @property
    def priority(self) -> tuple[Union[int, float], Cell]:
        # The priority is a tuple with cell such that given the same score, pumpkins can be given priority over
        # bridges and air
        if self.projected_block == GeodeEnum.PUMPKIN:
            return -self.average_block_distance, self

        # Otherwise, return the maximum isolation score of all the neighbours
        return -max((neighbour.average_block_distance
                     for neighbour in self.neighbours
                     if neighbour.projected_block == GeodeEnum.PUMPKIN
                     and not neighbour.has_group),
                    default=self.average_block_distance), self

    def __lt__(self, other):
        # If something is a pumpkin, we say it is smaller to give it priority over other types.
        if self.projected_block == GeodeEnum.PUMPKIN:
            return True
        elif other.projected_block == GeodeEnum.PUMPKIN:
            return False
        # In other situations we don't care
        return True
