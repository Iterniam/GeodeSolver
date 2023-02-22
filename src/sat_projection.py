from z3 import Int, Solver, And, If, Implies, Sum, Or, Bool, Xor, Z3Exception, Not

# While the structure of this file is garbage at best, it's an untested proof of concept for
# sat-solving the geode projection problem.
# It's untested because displaying the results in 3d is difficult.
# To test it, this file should be reimplemented in the Geodesy Minecraft mod.


def neighbours_3d(coordinate: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    # noinspection PyTypeChecker
    return list((tuple(coord_val + offset_val for coord_val, offset_val in zip(coordinate, offset_tuple))
                 for offset_tuple in [(0, 0, 1), (0, 1, 0), (1, 0, 0),
                                      (0, 0, -1), (0, -1, 0), (-1, 0, 0)]))


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
budding_amethysts: list[tuple[int, int, int]] = [(x, y, z)
                                                 for x, val in geode_compressed.items()
                                                 for y, z in val]
# Create clusters
# NOTE: We intentionally do not filter out locations where buds are present because the sat solver can
# choose to enable/disable buds to optimize the total number of projected budding amethysts
# NOTE: We make it a set and then a list to deduplicate the coordinates
amethyst_clusters = list({neighbour_coord
                          for coord in budding_amethysts
                          for neighbour_coord in neighbours_3d(coord)})

##################################################
# Start of building up the SAT solver conditions #
##################################################

# Define budding amethysts
# The bool indicates whether they are active (true) or destroyed (false)
# noinspection DuplicatedCode
budding_amethysts_d = [Bool(f'budding_amethyst__{x}__{y}__{z}')
                       for x, y, z in budding_amethysts]
budding_amethysts_dict = {(x, y, z): budding_amethysts_d[i]
                          for i, (x, y, z) in enumerate(budding_amethysts)}
budding_amethysts_dict_inv = {val: key for key, val in budding_amethysts_dict.items()}

# Define amethyst crystals
# The bool indicates whether they are active (true) or destroyed (false)
# noinspection DuplicatedCode
amethyst_clusters_d = [Bool(f'amethyst_cluster__{x}__{y}__{z}')
                       for x, y, z in amethyst_clusters]
amethyst_clusters_dict = {(x, y, z): amethyst_clusters_d[i]
                          for i, (x, y, z) in enumerate(amethyst_clusters)}
amethyst_clusters_dict_inv = {val: key for key, val in amethyst_clusters_dict.items()}

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
# Determine all possible, useful slices of size 1x1xZ, 1xYx1, Xx1x1.
# and set the relations between clusters and slices
###############################################################################################

# For each direction:
#   For all cluster coordinates:
#     Create a mapping from the 2d coordinates to a boolean indicating whether the slice should be harvested
# The mapping automatically features duplicate protection.
slices_x_d = {
    (y, z): Bool(f'slice_x__{y}__{z}')
    for _, y, z in amethyst_clusters}
slices_y_d = {
    (x, z): Bool(f'slice_y__{x}__{z}')
    for x, _, z in amethyst_clusters}
slices_z_d = {
    (x, y): Bool(f'slice_z__{x}__{y}')
    for x, y, _ in amethyst_clusters}

# Create a mapping from each amethyst bud coordinate to the slices that would harvest it
# noinspection DuplicatedCode
budding_amethyst_harvest_dict = {
    (x, y, z): (([slices_x_d[(y, z)]] if (y, z) in slices_x_d else [])
                + ([slices_y_d[(x, z)]] if (x, z) in slices_y_d else [])
                + ([slices_z_d[(x, y)]] if (x, y) in slices_z_d else []))
    for x, y, z in budding_amethysts}

# Set relations between slices and budding amethysts:
# When a slice is active, the budding amethysts that intersect with it are inactive
slice_implies_not_bud_c = [
    Implies(slice_, Not(budding_amethysts_dict[coord]))
    for coord, slices in budding_amethyst_harvest_dict.items()
    for slice_ in slices]

# Create a mapping from each cluster coordinate to the slices that would harvest it
# noinspection DuplicatedCode
cluster_harvest_dict = {
    (x, y, z): (([slices_x_d[(y, z)]] if (y, z) in slices_x_d else [])
                + ([slices_y_d[(x, z)]] if (x, z) in slices_y_d else [])
                + ([slices_z_d[(x, y)]] if (x, y) in slices_z_d else []))
    for x, y, z in amethyst_clusters}

# The score is the number of clusters that are active and are harvested by any of the slices that are active
score = Int('score')
score_c = score == Sum(
    [If(And(cluster,                                                  # If the cluster is active
            Or(cluster_harvest_dict[cluster_coords])),                # and one of the slices harvests it,
     1, 0)                                                            # then count the cluster as 1, otherwise as 0
     for cluster_coords, cluster in amethyst_clusters_dict.items()])  #

s = Solver()
s.append(cluster_implies_neighbour_bud_c)
s.append(bud_implies_possible_neighbour_cluster_c)
s.append(bud_xor_cluster_c)
s.append(slice_implies_not_bud_c)
s.append(score_c)

minimum_score = 0
while True:
    s.check(minimum_score <= score)
    try:
        model = s.model()
    except Z3Exception:
        break
    print(model[score])
    if int(str(model[score])) > minimum_score:
        minimum_score = int(str(model[score]))

    minimum_score += 1
