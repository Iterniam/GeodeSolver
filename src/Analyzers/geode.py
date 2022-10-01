from typing import Callable

from src.Enums.geode_enum import GeodeEnum
from src.Utils.collections.queue_extensions import PrioritySet
from src.cell import Cell
from src.group import Group

MAX_GROUP_SIZE = 12


class Geode:

    def __init__(self, geode_grid: list[list[GeodeEnum]]):
        self.grid: list[list[Cell]] = geode_grid
        self.cells: set[Cell] = {self.grid[row][col]
                                 for row in range(len(self.grid))
                                 for col in range(len(self.grid[0]))}
        self.__init_neighbours__()
        self.groups: dict[int, Group] = {}
        self.clusters: set[frozenset[Cell]] = set()
        self.populate_bridges()

    def __init_neighbours__(self):
        for cell in self.cells:
            row_len = len(self.grid)
            col_len = len(self.grid[0])

            cell.neighbours = [self.grid[cell.row + row_][cell.col + col_]
                               for row_, col_ in [(-1, 0), (0, -1), (1, 0), (0, 1)]
                               if 0 <= cell.row + row_ < row_len and 0 <= cell.col + col_ < col_len]

    def populate_bridges(self):
        # Replace air blocks that connect to at least two pumpkins with a bridge
        for cell in self.cells:
            if (cell.projected_block == GeodeEnum.AIR and
                sum((1
                     for neighbour in cell.neighbours
                     if neighbour.projected_block == GeodeEnum.PUMPKIN)) >= 2):
                cell.projected_block = GeodeEnum.BRIDGE

    def reset_groups(self):
        # Reset groups
        for block in self.cells:
            block.group_nr = -1
        self.groups.clear()

    def compute_clusters(self):
        # Returns a list of the clusters of pumpkins that already can naturally reach each other.
        # If every pumpkin can reach every pumpkin, then there's only one cluster
        # If there's also a 1x1 group that can't reach any other pumpkin, then there are two, etc.
        # Each cluster has at least one pumpkin
        undiscovered_pumpkins = set(cell for cell in self.cells
                                    if cell.projected_block == GeodeEnum.PUMPKIN and not cell.has_group)

        clusters = set()

        while len(undiscovered_pumpkins) > 0:
            # Pick an arbitrary cell - can't be done in a for loop because we decrease it during the loop
            source_cell = next(iter(undiscovered_pumpkins))
            visited_cells = set()
            current_cells = {source_cell}

            while len(current_cells) > 0:
                visited_cells |= current_cells

                # BFS
                current_cells = {cell
                                 for edge in current_cells
                                 for cell in edge.neighbours
                                 if cell not in visited_cells
                                 and cell.projected_block in [GeodeEnum.PUMPKIN, GeodeEnum.BRIDGE]
                                 and not cell.has_group}
            undiscovered_pumpkins -= visited_cells
            clusters.add(frozenset(visited_cells))
        self.clusters = clusters

    def average_isolation(self, frontier: set[Cell] = None):
        """
        Computes the isolation metric for the frontier, which mostly comes down to the average distance to all other
        reachable pumpkins
        :param frontier: The cells to compute the metric for. Defaults to all cells
        """
        # The caller does not expect frontier to change, so we use cells to potentially modify the frontier
        cells = set()
        if frontier is not None:
            extended_frontier = {neighbour
                                 for cell in frontier
                                 if cell.projected_block == GeodeEnum.BRIDGE
                                 for neighbour in cell.neighbours
                                 if neighbour.projected_block in [GeodeEnum.PUMPKIN] and not neighbour.has_group}
            cells = frontier | extended_frontier
        else:
            cells = set(self.cells)

        for cell in cells:
            if cell.projected_block in [GeodeEnum.OBSIDIAN, GeodeEnum.AIR] or cell.has_group:
                cell.average_block_distance = float('inf')
                continue

            # Breadth first search, not storing any distances but just the average distance
            total_distance = 0.0
            visited_cells = set()
            cell.reachable_pumpkins = 0

            current_distance = 0
            current_cells = {cell}

            while len(current_cells) > 0:
                total_distance += current_distance * len([cell for cell in current_cells
                                                          if cell.projected_block == GeodeEnum.PUMPKIN
                                                          and not cell.has_group])
                cell.reachable_pumpkins += len([cell for cell in current_cells
                                                if cell.projected_block == GeodeEnum.PUMPKIN
                                                and not cell.has_group])
                visited_cells |= current_cells

                new_cells = {cell
                             for edge in current_cells
                             for cell in edge.neighbours
                             if cell not in visited_cells
                             and cell.projected_block not in [GeodeEnum.OBSIDIAN, GeodeEnum.AIR]
                             and not cell.has_group}

                current_cells = new_cells
                current_distance += 1
            try:
                cell.average_block_distance = total_distance / cell.reachable_pumpkins
            except ZeroDivisionError:
                cell.average_block_distance = float('inf')
            # If it only visited less than MAX range blocks, increase the score so the algorithm has to get it
            if cell.reachable_pumpkins <= MAX_GROUP_SIZE:
                cell.average_block_distance = 60 - cell.reachable_pumpkins

    def handle_cluster_splitting(self,
                                 cell: Cell,
                                 group: Group,
                                 old_clusters: set[frozenset[Cell]],
                                 new_clusters: set[frozenset[Cell]],
                                 visited_blocks: set[Cell]) -> bool:
        # We take the difference between the old set of clusters and the new set of clusters:
        # original - new = the cluster that was split up
        # new - original = the clusters it was split up into
        unchanged_clusters = old_clusters & new_clusters
        changed_new_clusters = new_clusters - unchanged_clusters

        # There should be no scenario in which this method is called and there are not at least two clusters
        largest_new_cluster = max(changed_new_clusters, key=lambda cluster: len(cluster))
        second_largest_new_cluster = max(changed_new_clusters - {largest_new_cluster}, key=lambda cluster: len(cluster))
        if len(largest_new_cluster) == len(second_largest_new_cluster):
            # If the largest clusters are equally large, we don't exclude the largest cluster anymore.
            # For the block to end up being placed, it will have to absorb all clusters
            smallest_changed_new_clusters = changed_new_clusters
        else:
            smallest_changed_new_clusters = changed_new_clusters - {largest_new_cluster}

        # For the neighbours of the newly added block, we check if entire clusters can be added to the
        # current group
        # To do this, we first make a cheap check:
        #   if the number of blocks that can still be added to the current group is larger than or equal
        #   to the total size of the smallest changed new clusters, then we commit to placing the block
        #   and all blocks in these clusters
        if (MAX_GROUP_SIZE - len(group) >=
                sum((len(cluster) for cluster in smallest_changed_new_clusters))):
            # To add the cluster, we create frontier, i.e. the set of neighbours of the current group.
            frontier = {neighbour
                        for group_block in group.cells
                        for neighbour in group_block.neighbours
                        if neighbour not in group.cells}
            # We compute the set of blocks that should be absorbed
            absorption_target_set = {block
                                     for cluster in smallest_changed_new_clusters
                                     if any((True for block in cluster if block.projected_block == GeodeEnum.PUMPKIN))
                                     for block in cluster}
            self.populate_group(group, frontier, visited_blocks, absorption_target_set=absorption_target_set)
            commit_block = True

        # Further possible algorithms to refine the check are listed below, but they are not the immediate priority
        # as there are more pressing issues with the heuristic to solve.

        # If that's not the case, we have to check how many blocks it takes to reach all pumpkins in the clusters.
        # This is because there may be bridges that are not needed to reach all pumpkins
        # If all bridges in the new clusters are reachable within the remaining group size, we also commit
        # to placing the block.

        #
        # If not all bridges can be reached, then the refined number of required blocks to reach all pumpkin
        # blocks per cluster has to be considered.
        # If the total number of required blocks is less than the group size, we decide not to place the block
        # and instead make a group of the entire old cluster.
        # If the total number of required blocks is more than the group size, we determine whether it's possible
        # to add all pumpkins from a cluster to the current group such that the other cluster can form its own
        # group if its size is less than the MAX_GROUP_SIZE.
        # If that's not possible, and one of the clusters requires more than MAX_GROUP_SIZE blocks to reach
        # all pumpkins, we can add some of those blocks to the current group to hopefully reduce the required
        # number of blocks to equal or below MAX_GROUP_SIZE
        # If none of these conditions apply, there is nothing that can be done to improve the situation

        # To check how many blocks it takes to reach all pumpkins in a cluster, we have to eliminate useless
        # bridges.
        # To check if a bridge is useless (i.e. all pumpkins that were reachable are still reachable after
        # disabling the bridge), we can run BFS with one bridge disabled each time and see if all pumpkins
        # are still reachable
        # Before running BFS for all bridges, we can instead make some optimizations that are faster to compute.

        # 1. For all pumpkins with only one neighbour where the neighbour is a bridge, the bridge is mandatory
        # 2. For all bridges with only one neighbour, the bridge is useless
        # 3. For the newly created clusters, if only one of the neighbours of the added block is part of the
        #    cluster, then trace a path from that neighbour until it branches or until all pumpkins are found.
        #    All bridges on this path are mandatory.
        #    # Optimization: For the 'forced' path, you can always explore pumpkins before bridges
        #                    If BFS runs end up being necessary you run those starting from the first
        #                    branching point.

        # If there are still bridges for which the state is undetermined, then you first run a BFS from the
        # final block of the mandatory path to determine the distances to all remaining pumpkins.
        # Then, for all undetermined bridges, you mark the bridge as unnecessary, run the BFS again from the
        # final block. If the distance to any of the pumpkins increases (possibly to infinite), the bridge
        # is necessary.
        # This doesn't necessarily achieve the optimal layout but can't massively mess up
        # Over-optimization: You can make subclusters while determining the distance to the remaining
        #                    pumpkins to decrease the BFS search space

        # Finally, if no other options are left, we roll back the block
        else:
            group.remove_cell(cell)
            commit_block = False
        return commit_block

    def populate_group(self,
                       group: Group,
                       frontier: set[Cell],
                       visited_blocks: set[Cell], *,
                       absorption_target_set: set[Cell] = None):
        """
        Populate a group until it is full or no more useful blocks can be added to it
        :param group: The group to populate
        :param frontier: A set of cells that has yet to be explored
        :param visited_blocks: The blocks that have already been visited while adding blocks to this group
        :param absorption_target_set: The blocks that the group should attempt to absorb
        :return:
        """
        absorb_cluster_mode_enabled = absorption_target_set is not None

        while len(group) < MAX_GROUP_SIZE:
            commit_block = True
            q = PrioritySet()

            if absorb_cluster_mode_enabled:
                # If absorb_cluster_mode_enabled is active, the blocks in the queue are not guaranteed to be neighbours
                # of the current group, so we should only add blocks to the queue that are both in the frontier and in
                # the set of blocks that is to be absorbed
                for cell in frontier & absorption_target_set:
                    q.add(cell, cell.priority)
            else:
                # absorb_cluster_mode_enabled is inactive, we need to recompute the isolation metric for the
                # frontier, then add the blocks to the queue
                self.average_isolation(frontier)
                for cell in frontier:
                    q.add(cell, cell.priority)

            try:  # Select the cell for this iteration
                cell: Cell = q.get()
                # If there's only one node left to add, don't add bridges
                if MAX_GROUP_SIZE - len(group) == 1:
                    while cell.projected_block == GeodeEnum.BRIDGE:
                        visited_blocks.add(cell)
                        frontier.remove(cell)
                        cell = q.get()
            except IndexError:
                break

            # If a bridge doesn't have any ungrouped pumpkins or bridges as neighbours, we skip the bridge
            if (cell.projected_block == GeodeEnum.BRIDGE
                    and not any((not neighbour.has_group
                                 and neighbour.projected_block in [GeodeEnum.PUMPKIN, GeodeEnum.BRIDGE]
                                 for neighbour in cell.neighbours))):
                visited_blocks.add(cell)
                frontier.remove(cell)
                continue

            group.add_cell(cell)
            visited_blocks.add(cell)
            frontier.remove(cell)

            # During the computation of the isolation metric we also make a set of clusters consisting of blocks
            # that can all reach each other without traversing bedrock and blocks with groups
            # When placing a block, if it leads to n new clusters, we know that the block breaks up
            # an existing cluster into 1 + n clusters
            # Splitting up clusters like this is only possible when not absorbing clusters
            if not absorb_cluster_mode_enabled:
                # Store the old clusters before we recompute them
                old_clusters = self.clusters
                self.compute_clusters()
                if len(self.clusters) > len(old_clusters):
                    commit_block = self.handle_cluster_splitting(cell, group, old_clusters,
                                                                 self.clusters, visited_blocks)
                    # If the block is rolled back, we also roll back the clusters
                    if commit_block:
                        self.compute_clusters()
                    else:  # If a cluster is added, we recompute the clusters so the next run is accurate.
                        self.clusters = old_clusters

            if commit_block:
                # We add new neighbours to the frontier
                frontier |= {neighbour for neighbour in cell.neighbours
                             if neighbour.projected_block in [GeodeEnum.PUMPKIN, GeodeEnum.BRIDGE]
                             and not neighbour.has_group
                             and neighbour not in visited_blocks}

    def heuristic_placement(self):
        self.reset_groups()

        while any(not block.has_group
                  for block in self.cells
                  if block.projected_block == GeodeEnum.PUMPKIN):
            # Before populating a new group, we should always update the isolation score for all blocks
            # and compute clusters
            self.average_isolation()
            self.compute_clusters()

            source_block = min((block for block in self.cells
                                if block.projected_block == GeodeEnum.PUMPKIN and not block.has_group),
                               key=lambda x: x.priority)
            frontier = {source_block}
            visited_blocks = set()
            # Instantiate the group (looks weird because of default dicts)
            group = Group()
            group.group_nr = len(self.groups)
            self.groups[group.group_nr] = group

            self.populate_group(group, frontier, visited_blocks)

    def isolated_pumpkins(self) -> list[Cell]:
        return [cell
                for cell in self.cells
                if cell.average_block_distance >= 50
                and cell.projected_block == GeodeEnum.PUMPKIN]

    def _pretty_print_grid(self, str_func: Callable[[Cell], str]):
        for row_val in self.grid:
            print(''.join((str_func(cell))
                          for cell in row_val))

    def pretty_print_group_grid(self):
        self._pretty_print_grid(Cell.group_str)

    def pretty_print_projection(self):
        self._pretty_print_grid(Cell.projected_str)

    def pretty_print_merged(self):
        self._pretty_print_grid(Cell.merged_str)

    def pretty_print_shortest_distance(self, cell: Cell):
        self._pretty_print_grid(lambda cell2: cell.distance_str(cell2))

    def pretty_print_average_distance(self):
        self._pretty_print_grid(Cell.isolation_str)
