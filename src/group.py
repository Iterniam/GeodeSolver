from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cell import Cell


class Group:

    def __init__(self):
        self.group_nr: int = -1
        self.cells: set[Cell] = set()

    def add_cell(self, cell: Cell):
        self.cells.add(cell)
        cell.group_nr = self.group_nr

    def remove_cell(self, cell: Cell):
        self.cells.remove(cell)
        cell.group_nr = -1

    def __len__(self):
        return len(self.cells)
