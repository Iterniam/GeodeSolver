from __future__ import annotations
from enum import Enum
from types import MappingProxyType

from src.Enums.data_annotations import DataPrimitive


class Axis(Enum):
    Horizontal = 0,
    Vertical = 1,


class _FlyingMachineDP(DataPrimitive):

    @staticmethod
    def new(name: str,
            *,
            axes: list[Axis],
            uses_qc: bool,
            tileable: bool,
            length: int,
            trigger_delay: int,
            engine_footprint: list[list[bool]],
            pushed_blocks_footprints: dict[int, list[list[bool]]] = None,
            pushed_blocks: dict[int, int] = None,
            attached_blocks_footprints: dict[int, list[list[bool]]] = None,
            attached_blocks: dict[int, int] = None,
            pulled_blocks_footprints: dict[int, list[list[bool]]] = None,
            pulled_blocks: dict[int, int] = None):
        return ()


class FlyingMachineEnum(Enum):
    pushed_blocks: MappingProxyType[int, int]
    attached_blocks: MappingProxyType[int, int]
    pulled_blocks: MappingProxyType[int, int]
    pushed_blocks_footprints: MappingProxyType[int, tuple[tuple[bool, ...], ...]]
    attached_blocks_footprints: MappingProxyType[int, tuple[tuple[bool, ...], ...]]
    pulled_blocks_footprints: MappingProxyType[int, tuple[tuple[bool, ...], ...]]

    @_FlyingMachineDP
    def __new__(cls,
                name: str,
                *,
                axes: list[Axis],
                uses_qc: bool,
                tileable: bool,
                length: int,
                trigger_delay: int,  # Game ticks, not redstone ticks
                engine_footprint: list[list[bool]],
                pushed_blocks_footprints: dict[int, list[list[bool]]] = None,
                pushed_blocks: dict[int, int] = None,
                attached_blocks_footprints: dict[int, list[list[bool]]] = None,
                attached_blocks: dict[int, int] = None,
                pulled_blocks_footprints: dict[int, list[list[bool]]] = None,
                pulled_blocks: dict[int, int] = None):

        obj = object.__new__(cls)
        obj._value_ = name
        obj.canon_name = name
        obj.axes = tuple(axes)
        obj.uses_qc = uses_qc
        obj.tileable = tileable
        obj.length = length
        obj.trigger_delay = trigger_delay
        obj.engine_footprint = engine_footprint
        # All transformations here just make the arguments immutable
        obj.pushed_blocks = (MappingProxyType({}) if pushed_blocks is None
                             else MappingProxyType({key: val for key, val in pushed_blocks.items()}))
        obj.attached_blocks = (MappingProxyType({}) if attached_blocks is None
                               else MappingProxyType({key: val for key, val in attached_blocks.items()}))
        obj.pulled_blocks = (MappingProxyType({}) if pulled_blocks is None
                             else MappingProxyType({key: val for key, val in pulled_blocks.items()}))
        obj.pushed_blocks_footprints = (MappingProxyType({}) if pushed_blocks_footprints is None
                                        else MappingProxyType({key: tuple(tuple(bool_list) for bool_list in val)
                                                               for key, val in pushed_blocks_footprints.items()}))
        obj.attached_blocks_footprints = (MappingProxyType({}) if attached_blocks_footprints is None
                                          else MappingProxyType({key: tuple(tuple(bool_list) for bool_list in val)
                                                                 for key, val in attached_blocks_footprints.items()}))
        obj.pulled_blocks_footprints = (MappingProxyType({}) if pulled_blocks_footprints is None
                                        else MappingProxyType({key: tuple(tuple(bool_list) for bool_list in val)
                                                               for key, val in pulled_blocks_footprints.items()}))

        return obj

    MANGO_MACHINE = _FlyingMachineDP.new(
        name='MangoMachine',
        axes=[Axis.Horizontal, Axis.Vertical],
        uses_qc=False,
        tileable=True,
        length=8,
        trigger_delay=0,
        engine_footprint=[[True, True]],
        pushed_blocks_footprints={1: [[True, True]]},
        pushed_blocks={1: 2},
        attached_blocks_footprints={1: [[False, True]]},
        attached_blocks={1: 6},
    )
    MANGO_MACHINE_ATTACHED = _FlyingMachineDP.new(
        name='MangoMachineAttached',
        axes=[Axis.Horizontal, Axis.Vertical],
        uses_qc=False,
        tileable=True,
        length=8,
        trigger_delay=0,
        engine_footprint=[[True, True]],
        attached_blocks_footprints={1: [[True, False]],
                                    2: [[False, True]]},
        attached_blocks={1: 2, 2: 6},
    )
    L_SHAPE_DOUBLE_PUSHER = _FlyingMachineDP.new(
        name='LShapeDoublePusher',
        axes=[Axis.Horizontal, Axis.Vertical],
        uses_qc=True,
        tileable=False,
        length=9,
        trigger_delay=0,
        engine_footprint=[[True, True],
                          [False, True]],
        pushed_blocks_footprints={1: [[False, True],
                                      [False, False]],
                                  2: [[False, False],
                                      [False, True]]},
        pushed_blocks={1: 11, 2: 11},
        attached_blocks_footprints={1: [[True, False],
                                        [False, False]],
                                    2: [[False, True],
                                        [False, True]]},
        attached_blocks={1: 6, 2: 1},
    )
    SINGLE_COLUMN_PUSHER = _FlyingMachineDP.new(
        name='SingleColumnPusher',
        axes=[Axis.Horizontal],
        uses_qc=True,
        tileable=False,  # Technically it is tileable, but it's beyond stupid to use the machine in that scenario
        length=10,
        trigger_delay=6,
        engine_footprint=[[True],
                          [True],
                          [False],
                          [True]],
        attached_blocks_footprints={1: [[True],
                                        [False],
                                        [False],
                                        [False]]},  # It can technically have attachments here, but doing so is stupid
        attached_blocks={1: 2},
    )
    SINGLE_COLUMN_PUSHER_SIDEWAYS = _FlyingMachineDP.new(
        name='SingleColumnPusherSideways',
        axes=[Axis.Horizontal],
        uses_qc=True,
        tileable=True,  # For this machine, if you mirror it, there are scenarios where tiling is not stupid
        length=10,
        trigger_delay=6,
        engine_footprint=[[False, True, True],
                          [True, False, False]],
        attached_blocks_footprints={1: [[False, False, True],
                                        [False, False, False]]},
        attached_blocks={1: 2},
    )
