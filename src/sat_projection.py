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

    def to_coord_2d(self, coord: Coord) -> tuple[int, int]:
        match self:
            case PlaneEnum.x:
                return coord.coord_y, coord.coord_z
            case PlaneEnum.y:
                return coord.coord_x, coord.coord_z
            case PlaneEnum.z:
                return coord.coord_x, coord.coord_y

    def to_slice(self, coord: Coord) -> Slice:
        return Slice(self, *self.to_coord_2d(coord))


class Coord:
    def __init__(self, coord_x: int, coord_y: int, coord_z: int):
        self.coord_x = coord_x
        self.coord_y = coord_y
        self.coord_z = coord_z
    
    def add(self, coord_x: int, coord_y: int, coord_z: int) -> Coord:
        return Coord(self.coord_x + coord_x, self.coord_y + coord_y, self.coord_z + coord_z)
    
    def neighbours(self) -> list[Coord]:
        return [self.add(offset_x, offset_y, offset_z)
                for offset_x, offset_y, offset_z in [(0, 0, 1), (0, 1, 0), (1, 0, 0),
                                                     (0, 0, -1), (0, -1, 0), (-1, 0, 0)]]

    def __eq__(self, other):
        if isinstance(other, Coord):
            return vars(self) == vars(other)
        return False

    def __hash__(self):
        return hash(tuple(vars(self).values()))


class Slice:
    def __init__(self, plane: PlaneEnum, coord_a: int, coord_b: int):
        self.plane = plane
        self.coord_a = coord_a
        self.coord_b = coord_b
        self.sat_bool = Bool(f'slice__{self.plane}__{self.coord_a}__{self.coord_b}')

    def add(self, coord_a: int, coord_b: int) -> Slice:
        return Slice(self.plane, self.coord_a + coord_a, self.coord_b + coord_b)

    def to_coord_3d(self, plane_coord: int) -> tuple[int, int, int]:
        match self.plane:
            case PlaneEnum.x:
                return plane_coord, self.coord_a, self.coord_b
            case PlaneEnum.y:
                return self.coord_a, plane_coord, self.coord_b
            case PlaneEnum.z:
                return self.coord_a, self.coord_b, plane_coord

    def __eq__(self, other):
        if isinstance(other, Slice):
            return vars(self) == vars(other)
        return False

    def __hash__(self):
        return hash(tuple(vars(self).values()))

    def neighbours(self) -> list[Slice]:
        return [self.add(offset_a, offset_b)
                for offset_a, offset_b in [(0, 1), (1, 0), (0, -1), (-1, 0)]]


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
budding_amethysts: set[Coord] = {Coord(x, y, z)
                                 for x, val in geode_compressed.items()
                                 for y, z in val}
# Create clusters
# NOTE: We intentionally leave in locations that already have buds because the sat solver can
# choose to enable/disable buds to optimize the total number of projected budding amethysts
amethyst_clusters: set[Coord] = {neighbour_coord
                                 for coord in budding_amethysts
                                 for neighbour_coord in coord.neighbours()}

##################################################
# Start of building up the SAT solver conditions #
##################################################

# Define budding amethysts
# The bool indicates whether they are active (true) or destroyed (false)
budding_amethysts_dict: dict[Coord, BoolRef] = {
    bud: Bool(f'budding_amethyst__{bud.coord_x}__{bud.coord_y}__{bud.coord_z}')
    for bud in budding_amethysts}
budding_amethysts_d: list[BoolRef] = list(budding_amethysts_dict.values())

# Define amethyst crystals
# The bool indicates whether they are active (true) or destroyed (false)
amethyst_clusters_dict: dict[Coord, BoolRef] = {
    cluster: Bool(f'amethyst_cluster__{cluster.coord_x}__{cluster.coord_y}__{cluster.coord_z}')
    for cluster in amethyst_clusters}
amethyst_clusters_d: list[BoolRef] = list(amethyst_clusters_dict.values())

# To make constraints about budding amethysts, amethyst clusters, and slices, we need to create dictionaries first
slice_coord_to_harvesting_coords_dict: dict[Slice, set[Coord]] = defaultdict(set)
harvesting_coords_to_slice_coords_dict: dict[Coord, set[Slice]] = defaultdict(set)
for plane in PlaneEnum:
    for coord in amethyst_clusters | budding_amethysts:
        slice_ = plane.to_slice(coord)
        slice_coord_to_harvesting_coords_dict[slice_].add(coord)
        harvesting_coords_to_slice_coords_dict[coord].add(slice_)
# Define slices
slices = list(slice_coord_to_harvesting_coords_dict.keys())
cluster_harvest_dict: dict[Coord, list[BoolRef]] = {
    coord: [slice_.sat_bool for slice_ in harvesting_coords_to_slice_coords_dict[coord]]
    for coord in budding_amethysts | amethyst_clusters}

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
                for possible_bud_coord in amethyst_coords.neighbours()    #
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
                 for neighbour_coord in bud_coord.neighbours()]))    #
    for bud_coord in budding_amethysts]

# Relation 3: Budding Amethyst xor Amethyst Cluster
bud_xor_cluster_c = [Xor(budding_amethysts_dict[coord], amethyst_clusters_dict[coord])
                     for coord in amethyst_clusters & budding_amethysts]

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
    Implies(slice_.sat_bool, Not(budding_amethysts_dict[coord]))
    for coord, slices in harvesting_coords_to_slice_coords_dict.items() if coord in budding_amethysts
    for slice_ in slices]

# When a budding amethyst is active, no slice that could harvest it is active
bud_implies_not_slices_c = [
    Implies(budding_amethysts_dict[coord], Not(slice_.sat_bool))
    for coord, slices in harvesting_coords_to_slice_coords_dict.items() if coord in budding_amethysts
    for slice_ in slices]

# Build up required structures for relations between 1x1 holes:
# Identify projections that could be 1x1 holes
potential_one_by_one_holes: set[Slice] = {
    slice_
    for slice_ in slices
    if all(neighbour in slices 
           for neighbour in slice_.neighbours())}

# Map the holes to a set of up to three projections that must be active to make it possible to power it
# The following holes allow for the projection to be active
#     B
#     B
#   AA#CC
#    #H#
#     #
# Where # is blocked, H is the hole, and A, B, or C has to be free
potential_holes_to_list_of_sets_of_required_projections: dict[Slice, list[set[BoolRef]]] = {}
for slice_ in potential_one_by_one_holes:
    if slice_.plane == PlaneEnum.y:
        continue
    potential_holes_to_list_of_sets_of_required_projections[slice_] = [
         {offset_slice.sat_bool
          for offset_a, offset_b in offset_coords
          if (offset_slice := slice_.add(offset_a, offset_b)) in slices}
         for offset_coords in [{(-2, 1), (-1, 1)}, {(0, 2), (0, 3)}, {(1, 1), (1, 2)}]]

# Set 1x1 hole prevention for the vertical (y) plane:
# A potential hole being active implies that at least one of its neighbours is also active,
# because then it's not a 1x1 hole but at least 2x1.
block_vertical_one_by_one_holes_c = [
    Implies(slice_.sat_bool,                                                  # A potential hole implies
            Or([neighbour.sat_bool                                            # that at least one neighbour
                for neighbour in slice_.neighbours()]))                       # is active
    for slice_ in potential_one_by_one_holes if slice_.plane == PlaneEnum.y]  # if the hole is vertical

# Set 1x1 hole prevention for the horizontal (x, z) planes:
# A potential hole being active while its neighbours are inactive requires at least one of the sets to be fully
# active so the original hole can be powered.
block_specific_horizontal_one_by_one_holes_c = [
    Implies(And(slice_.sat_bool,                                       # An active hole on the horizontal plane
                *[neighbour.sat_bool                                   # that is blocked in by its neighbours
                  for neighbour in slice_.neighbours()]),              # implies that
            Or([And(required_active_group)                             # at least one of the three groups required
                for required_active_group                              # to power the hole is fully active
                in potential_holes_to_list_of_sets_of_required_projections[slice_]]))
    for slice_ in potential_one_by_one_holes if slice_.plane != PlaneEnum.y]

# Determine the number of clusters that are active and are harvested by any of the slices that are active
nr_of_harvested_clusters = Int('nr_of_harvested_clusters')
nr_of_harvested_clusters_c = nr_of_harvested_clusters == Sum(
    [If(And(cluster,                                                  # If the cluster is active
            Or(cluster_harvest_dict[coord])),                         # and one of the slices harvests it,
        1, 0)                                                         # then count the cluster as 1, otherwise as 0
     for coord, cluster in amethyst_clusters_dict.items()])           #

# Determine the number of slices/projections that are active
nr_of_projections = Int('nr_of_projections')
nr_of_projections_c = nr_of_projections == Sum([If(slice_.sat_bool, 1, 0)
                                                for slice_ in slices])

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
