import time

from src.Enums.flying_machine_enum import FlyingMachineEnum
from src.Enums.geode_enum import GeodeEnum
from src.grid_reader import geode_generator
import colorama
colorama.init()

from src.sat_pumpkin_solver import parse_input

# Contains 93 pumpkins
# This is the main direction in Ilmango's tutorial video
input_grid = '''00000000000000000
00000000p00000000
0000000pop0000000
000000pooop0p0000
00000ppoop0pop000
000ppoppopppop000
00popppoopoppp000
00poooppp0p0pop00
0poopppoppop0pop0
0poopppp00p0pop00
00ppooop0pp00p000
00popppppooppp000
000p00poppppoop00
0000000ppoppop000
000000ppppopop000
00000poooopop0000
000000ppoopp00000
00000000pp0000000
00000000000000000'''

# start = time.time()
# parse_input(input_grid)
# print(f'Took {time.time() - start} seconds')


gen = geode_generator()
for i, geode in enumerate(gen):
    start = time.time()  # Doesn't include geode instantiation but that should be negligible
    geode.pretty_print_merged()
    geode.heuristic_placement()
    print(f'Geode {i} took {(time.time() - start):3.2f} seconds')
    print('Group sizes:')
    print('\n'.join((f'{group.group_nr:02}: {len(group.cells)}' for group in geode.groups.values())))
    geode.pretty_print_merged()
    # geode.pretty_print_projection()
    # geode.pretty_print_group_grid()
    # geode.pretty_print_merged()
    # geode.populate_bridges()
    print('Placing flying machines')
    geode.populate_flying_machines({FlyingMachineEnum.MANGO_MACHINE})
    geode.pretty_print_machine_str()
        # exit()
