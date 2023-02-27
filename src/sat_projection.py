from __future__ import annotations

from collections import defaultdict
from enum import Enum

from z3 import Int, Solver, And, If, Implies, Sum, Or, Bool, Xor, Z3Exception, Not, BoolRef


# While the structure of this file is garbage at best, it's an untested proof of concept for
# sat-solving the geode projection problem.
# It's untested because displaying the results in 3d is difficult.
# To test it, this file should be reimplemented in the Geodesy Minecraft mod.


class PlaneEnum(Enum):
    x = 'X',
    y = 'Y',
    z = 'Z',

    def to_coord_2d(self, x: int, y: int, z: int):
        match self:
            case PlaneEnum.x:
                return y, z
            case PlaneEnum.y:
                return x, z
            case PlaneEnum.z:
                return x, y

    def to_slice_coord(self, x: int, y: int, z: int):
        return (self,) + self.to_coord_2d(x, y, z)


def slice_neighbours(slice_coord: tuple[PlaneEnum, int, int]) -> list[tuple[PlaneEnum, int, int]]:
    plane, a, b = slice_coord
    return list((plane, a + offset_a, b + offset_b)
                for offset_a, offset_b in [(0, 1), (1, 0), (0, -1), (-1, 0)])


def neighbours_3d(coordinate: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    x, y, z = coordinate
    return list((x + offset_x, y + offset_y, z + offset_z)
                for offset_x, offset_y, offset_z in [(0, 0, 1), (0, 1, 0), (1, 0, 0),
                                                     (0, 0, -1), (0, -1, 0), (-1, 0, 0)])


# Compressed formats describing only the coordinates of the budding amethysts
geode_compressed: dict[int, list[tuple[int, int]]] = {
    0: [],
    1: [(10, 9), (7, 6)],
    2: [(13, 8), (12, 4), (11, 9), (9, 9), (8, 11), (8, 9), (7, 9), (7, 6), (6, 9), (5, 4)],
    3: [(14, 8), (11, 3), (10, 12), (9, 11), (9, 4), (9, 2), (7, 12), (7, 10), (6, 12), (6, 5), (5, 8), (4, 9), (3, 8)],
    4: [(13, 4), (9, 2), (5, 12), (3, 5), (2, 4)],
    5: [(14, 11), (13, 11), (5, 11), (5, 3), (4, 10), (3, 4)],
    6: [(15, 11), (13, 12), (11, 1), (9, 14), (6, 0), (3, 7), (3, 3), (2, 9)],
    7: [(13, 13), (13, 12), (13, 2), (7, 14), (4, 10), (1, 5)],
    8: [(16, 10), (1, 6), (1, 5)],
    9: [(15, 9), (15, 5), (15, 4), (14, 4), (3, 6), (1, 3)],
    10: [(15, 8), (15, 4), (14, 6), (13, 12), (10, 2), (5, 13)],
    11: [(15, 8), (14, 10), (14, 7), (14, 5), (14, 4), (12, 11), (4, 11), (4, 9)],
    12: [(12, 11), (6, 11), (4, 6)],
    13: [(12, 6), (8, 8), (8, 6), (7, 8), (5, 7)],
    14: [(9, 7)],
    15: [],
}

# Decompress list, create buds
budding_amethysts: set[tuple[int, int, int]] = {(x, y, z)
                                                for x, val in geode_compressed.items()
                                                for y, z in val}
# Create clusters
# NOTE: We intentionally leave in locations that already have buds because the sat solver can
# choose to enable/disable buds to optimize the total number of projected budding amethysts
amethyst_clusters = {neighbour_coord
                     for coord in budding_amethysts
                     for neighbour_coord in neighbours_3d(coord)}

##################################################
# Start of building up the SAT solver conditions #
##################################################

# Define budding amethysts
# The bool indicates whether they are active (true) or destroyed (false)
budding_amethysts_dict: dict[tuple[int, int, int], BoolRef] = {
    (x, y, z): Bool(f'budding_amethyst__{x}__{y}__{z}')
    for x, y, z in budding_amethysts}
budding_amethysts_d: list[BoolRef] = list(budding_amethysts_dict.values())

# Define amethyst crystals
# The bool indicates whether they are active (true) or destroyed (false)
amethyst_clusters_dict: dict[tuple[int, int, int], BoolRef] = {
    (x, y, z): Bool(f'amethyst_cluster__{x}__{y}__{z}')
    for x, y, z in amethyst_clusters}
amethyst_clusters_d: list[BoolRef] = list(amethyst_clusters_dict.values())

# To make constraints about budding amethysts, amethyst clusters, and slices, we need to create dictionaries first
slice_coord_to_harvesting_coords_dict: dict[tuple[PlaneEnum, int, int], set[tuple[int, int, int]]] = defaultdict(set)
harvesting_coords_to_slice_coords_dict: dict[tuple[int, int, int], set[tuple[PlaneEnum, int, int]]] = defaultdict(set)
for plane in PlaneEnum:
    for x, y, z in amethyst_clusters | budding_amethysts:
        coord_2d = plane.to_slice_coord(x, y, z)
        slice_coord_to_harvesting_coords_dict[coord_2d].add((x, y, z))
        harvesting_coords_to_slice_coords_dict[(x, y, z)].add(coord_2d)
# Define slices
slices_dict: dict[tuple[PlaneEnum, int, int], BoolRef] = {
    (plane, a, b): Bool(f'slice__{plane}__{a}__{b}')
    for plane, a, b in slice_coord_to_harvesting_coords_dict.keys()}
cluster_harvest_dict: dict[tuple[int, int, int], list[BoolRef]] = {
    coord_3d: [slices_dict[coord_2d] for coord_2d in harvesting_coords_to_slice_coords_dict[coord_3d]]
    for coord_3d in budding_amethysts | amethyst_clusters}
slices_d: list[BoolRef] = list(slices_dict.values())

########################################################################################################
# Set relations between amethyst clusters and budding amethysts                                        #
# We have three relations to define:                                                                   #
# Relation 1: Amethyst Cluster is true -> one of the neighbouring Budding Amethysts is true            #
# Relation 2: Budding Amethyst is true                                                                 #
#   -> all neighbours either (have no bud possibility and have a crystal) or (have a bud or a crystal) #
# Relation 3: Budding Amethyst xor Amethyst Cluster                                                    #
########################################################################################################

# Relation 1: Amethyst Cluster is true -> one of the neighbouring Budding Amethysts is true
cluster_implies_neighbour_bud_c = [
    Implies(amethyst_clusters_dict[amethyst_coords],                      # Amethyst coords imply that
            Or([budding_amethysts_dict[possible_bud_coord]                # One or more neighbouring buds are true
                for possible_bud_coord in neighbours_3d(amethyst_coords)  #
                if possible_bud_coord in budding_amethysts_dict]))        # We exclude buds coords that don't exist
    for amethyst_coords in amethyst_clusters]

# Relation 2: Budding Amethyst is true
#   -> all neighbours either (have no bud possibility and have a crystal) or (have a bud or a crystal)
bud_implies_possible_neighbour_cluster_c = [
    Implies(budding_amethysts_dict[bud_coord],                       # Bud coords imply that
            And([Or(budding_amethysts_dict[neighbour_coord],         # For all neighbours, if a bud can exist,
                    amethyst_clusters_dict[neighbour_coord])         # the coord either has a bud or a crystal,
                 if neighbour_coord in budding_amethysts_dict        #
                 else amethyst_clusters_dict[neighbour_coord]        # otherwise, it has a crystal
                 for neighbour_coord in neighbours_3d(bud_coord)]))  #
    for bud_coord in budding_amethysts]

# Relation 3: Budding Amethyst xor Amethyst Cluster
bud_xor_cluster_c = [Xor(budding_amethysts_dict[coord], amethyst_clusters_dict[coord])
                     for coord in amethyst_clusters_dict.keys() & budding_amethysts_dict.keys()]

###############################################################################################
# Set projection relations
# We have four relations to define:
# Relation 1: Active slices lead to inactive budding amethysts
# Relation 2: Active buds lead to inactive slices
# Relation 3: 1x1 holes in the vertical (y) axis cannot exist.
# Relation 4: 1x1 holes in the horizontal (x, z) axes can exist in specific scenarios
###############################################################################################

# Set relations between slices and budding amethysts:
# When a slice is active, the budding amethysts that intersect with it are inactive
slice_implies_not_bud_c = [
    Implies(slices_dict[slice_coords], Not(budding_amethysts_dict[coord_3d]))
    for coord_3d, slices_coords in harvesting_coords_to_slice_coords_dict.items() if coord_3d in budding_amethysts
    for slice_coords in slices_coords]

# When a budding amethyst is active, no slice that could harvest it is active
bud_implies_not_slices_c = [
    Implies(budding_amethysts_dict[coord_3d], Not(slices_dict[slice_coords]))
    for coord_3d, slices_coords in harvesting_coords_to_slice_coords_dict.items() if coord_3d in budding_amethysts
    for slice_coords in slices_coords]

# Build up required structures for relations between 1x1 holes:
# Identify projections that could be 1x1 holes
potential_one_by_one_holes: set[tuple[PlaneEnum, int, int]] = {
    slice_
    for slice_ in slices_dict.keys()
    if all(neighbour in slices_dict for neighbour in slice_neighbours(slice_))}

# Map the holes to a set of up to three projections that must be active to make it possible to power it
# The following holes allow for the projection to be active
#     B
#     B
#   AA#CC
#    #H#
#     #
# Where # is blocked, H is the hole, and A, B, or C has to be free
potential_holes_to_list_of_sets_of_required_projections: dict[tuple[PlaneEnum, int, int], list[set[BoolRef]]] = {}
for plane, a, b in potential_one_by_one_holes:
    if plane == PlaneEnum.y:
        continue
    potential_holes_to_list_of_sets_of_required_projections[(plane, a, b)] = [
         {slices_dict[offset_coord]
          for offset_a, offset_b in offset_coords
          if (offset_coord := (plane, a + offset_a, b + offset_b)) in slice_coord_to_harvesting_coords_dict.keys()}
         for offset_coords in [{(-2, 1), (-1, 1)}, {(0, 2), (0, 3)}, {(1, 1), (1, 2)}]]

# Set 1x1 hole prevention for the vertical (y) plane:
# A potential hole being active implies that at least one of its neighbours is also active,
# because then it's not a 1x1 hole but at least 2x1.
block_vertical_one_by_one_holes_c = [
    Implies(slices_dict[(plane, a, b)],                                     # A potential hole implies
            Or([slices_dict[neighbour]                                      # that at least one neighbour
                for neighbour in slice_neighbours((plane, a, b))]))         # is active
    for plane, a, b in potential_one_by_one_holes if plane == PlaneEnum.y]  # if the hole is vertical

# Set 1x1 hole prevention for the horizontal (x, z) planes:
# A potential hole being active while its neighbours are inactive requires at least one of the sets to be fully
# active so the original hole can be powered.
block_specific_horizontal_one_by_one_holes_c = [
    Implies(And(slices_dict[(plane, a, b)],                            # An active hole on the horizontal plane
                *[slices_dict[neighbour]                               # that is blocked in by its neighbours
                  for neighbour in slice_neighbours((plane, a, b))]),  # implies that
            Or([And(required_active_group)                             # at least one of the three groups required
                for required_active_group                              # to power the hole is fully active
                in potential_holes_to_list_of_sets_of_required_projections[(plane, a, b)]]))
    for plane, a, b in potential_one_by_one_holes if plane != PlaneEnum.y]

# Determine the number of clusters that are active and are harvested by any of the slices that are active
nr_of_harvested_clusters = Int('nr_of_harvested_clusters')
nr_of_harvested_clusters_c = nr_of_harvested_clusters == Sum(
    [If(And(cluster,                                                  # If the cluster is active
            Or(cluster_harvest_dict[cluster_coords])),                # and one of the slices harvests it,
        1, 0)                                                         # then count the cluster as 1, otherwise as 0
     for cluster_coords, cluster in amethyst_clusters_dict.items()])  #

# Determine the number of slices/projections that are active
nr_of_projections = Int('nr_of_projections')
nr_of_projections_c = nr_of_projections == Sum([If(slice_, 1, 0)
                                                for slice_ in slices_d])

score = Int('score')
score_c = score == nr_of_harvested_clusters  # * 10 + (len(amethyst_clusters) - nr_of_projections)

s = Solver()
s.append(cluster_implies_neighbour_bud_c)
s.append(bud_implies_possible_neighbour_cluster_c)
s.append(bud_xor_cluster_c)
s.append(slice_implies_not_bud_c)
s.append(bud_implies_not_slices_c)
s.append(block_vertical_one_by_one_holes_c)
s.append(block_specific_horizontal_one_by_one_holes_c)
s.append(nr_of_harvested_clusters_c)
s.append(nr_of_projections_c)
s.append(score_c)

minimum_score = 300
while True:
    s.check(minimum_score <= score)
    try:
        model = s.model()
    except Z3Exception:
        break
    print(f'Score: {model[score]}')
    print(f'nr_of_harvested_clusters: {model[nr_of_harvested_clusters]}')
    print(f'nr_of_projections: {model[nr_of_projections]}')
    if int(str(model[score])) > minimum_score:
        minimum_score = int(str(model[score]))

    minimum_score += 1
