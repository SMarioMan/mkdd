#!/usr/bin/env python3
"""Execute the built mod's actual PowerPC functions, without a renderer.

Requires `pip install unicorn==2.1.4`. This is a CPU-level integration suite;
it does not replace a Dolphin/hardware LAN synchronization playtest.
"""
import argparse
from pathlib import Path
import struct
import subprocess
import unittest

from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as reg


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/lan-battle/MarioClub_us"
NM = ROOT / "build/binutils/powerpc-eabi-nm"


class Game:
    NET = 0x81000000
    ENTRY = 0x81002000
    MANAGER = 0x81004000
    CHECKERS = 0x81005000
    RETURN = 0x817FFFF0

    def __init__(self):
        self.cpu = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        self.cpu.mem_map(0x80000000, 0x1800000)
        data = (BUILD / "main.dol").read_bytes()
        for i in range(18):
            offset = struct.unpack_from(">I", data, i * 4)[0]
            address = struct.unpack_from(">I", data, 0x48 + i * 4)[0]
            size = struct.unpack_from(">I", data, 0x90 + i * 4)[0]
            if size:
                self.cpu.mem_write(address, data[offset:offset + size])
        output = subprocess.check_output(
            [str(NM), "-P", "--defined-only", str(BUILD / "main.elf")], text=True
        )
        self.symbols = {}
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 3:
                try:
                    self.symbols[fields[0]] = int(fields[2], 16)
                except ValueError:
                    pass
        self.stubs = set()
        self.panics = {
            self.addr("OSPanic"),
            self.addr("showAssert_f__12JUTAssertionFUlPCciPCce"),
        }
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.cpu.reg_write(reg.UC_PPC_REG_MSR, 0x2000)  # enable floating point

    def addr(self, name):
        return self.symbols[name]

    def hook(self, cpu, address, size, _):
        if address in self.panics:
            raise AssertionError("Game assertion reached at 0x%08x" % address)
        if address in self.stubs:
            cpu.reg_write(reg.UC_PPC_REG_PC, cpu.reg_read(reg.UC_PPC_REG_LR))

    def call(self, name, *args):
        for i in range(32):
            self.cpu.reg_write(getattr(reg, "UC_PPC_REG_%d" % i), 0)
        self.cpu.reg_write(reg.UC_PPC_REG_1, 0x817F0000)
        self.cpu.reg_write(reg.UC_PPC_REG_2, self.addr("_SDA2_BASE_"))
        self.cpu.reg_write(reg.UC_PPC_REG_13, self.addr("_SDA_BASE_"))
        self.cpu.reg_write(reg.UC_PPC_REG_LR, self.RETURN)
        for i, value in enumerate(args, 3):
            self.cpu.reg_write(getattr(reg, "UC_PPC_REG_%d" % i), value & 0xFFFFFFFF)
        self.cpu.emu_start(self.addr(name), self.RETURN, count=2000000)
        if self.cpu.reg_read(reg.UC_PPC_REG_PC) != self.RETURN:
            raise AssertionError("Function did not return: " + name)
        return self.cpu.reg_read(reg.UC_PPC_REG_3)

    def write(self, address, data):
        self.cpu.mem_write(address, bytes(data))

    def u8(self, address, value):
        self.write(address, [value])

    def u16(self, address, value):
        self.write(address, struct.pack(">H", value & 0xFFFF))

    def u32(self, address, value):
        self.write(address, struct.pack(">I", value & 0xFFFFFFFF))

    def read(self, address, size):
        return bytes(self.cpu.mem_read(address, size))

    def read16(self, address):
        return struct.unpack(">h", self.read(address, 2))[0]

    def read32(self, address):
        return struct.unpack(">I", self.read(address, 4))[0]

    def network(self):
        self.u32(self.addr("mspNetGameMgr__10NetGameMgr"), self.NET)
        self.u16(self.NET + 0x12EC, 0x1FF)  # all shared unlocks
        self.u16(self.NET + 0x12EA, 0xFFFF)
        self.u8(self.NET + 0x12E9, 7)

    def field_offset(self, getter):
        # The ABI accessors are a single load followed by blr. Read its signed
        # displacement so fixtures use this build's layout, not host C++ layout.
        opcode = self.read32(self.addr(getter))
        assert opcode >> 26 in (32, 40, 42), hex(opcode)
        return struct.unpack(">h", struct.pack(">H", opcode & 0xFFFF))[0]


class LANBattleTests(unittest.TestCase):
    def test_bomb_pool_can_stock_both_characters_in_all_eight_karts(self):
        for count in range(2, 9):
            for bomb_battle in (False, True):
                with self.subTest(karts=count, bomb_battle=bomb_battle):
                    game = Game()
                    geography = 0x81008000
                    game.u32(game.addr("gMgr__19GeographyObjManager"), geography)
                    game.u8(geography + 0x492, int(bomb_battle))
                    game.u32(game.addr("sRaceManager__7RaceMgr"), game.MANAGER)
                    game.u32(game.MANAGER + 0x38, game.addr("gRaceInfo"))
                    game.u16(game.addr("gRaceInfo") + 0x1C, count)
                    game.call("initItemMaxNums__10ItemObjMgrFv", 0)
                    pool = max(64, count * 10 + 24) if bomb_battle else 5
                    self.assertEqual(game.read(game.addr("sMaxItemNum__24@unnamed@ItemObjMgr_cpp@") + 8, 1), bytes([pool]))
                    self.assertEqual(game.read32(game.addr("sMaxCreateItemNum__24@unnamed@ItemObjMgr_cpp@") + 8 * 4), pool)
                    self.assertEqual(game.read(game.addr("sMaxMoveItemNum__24@unnamed@ItemObjMgr_cpp@") + 8, 1), bytes([64 if bomb_battle else 2]))
                    self.assertEqual(game.read(game.addr("sMAX_TOTAL_MOVING_ITEM_NUM__24@unnamed@ItemObjMgr_cpp@"), 1), b"\x10")
                    if bomb_battle:
                        self.assertGreaterEqual(pool, count * 2 * 5 + 16)

    def test_embedded_archives_follow_relinked_addresses(self):
        game = Game()
        self.assertEqual(game.addr("_pSystemArc"), game.addr("lbl_80316680"))
        self.assertEqual(game.read(game.addr("_pSystemArc"), 4), b"RARC")
        self.assertEqual(game.addr("_pBuildtimeDat"), game.addr("lbl_803608E0"))

    def test_bomb_course_selection_preserves_modes_rng_and_arena_order(self):
        for order in (0, 1, 2):  # random, single arena, all arenas
            for arena in range(6):
                with self.subTest(order=order, arena=arena):
                    game = Game()
                    game.network()
                    info = game.addr("gLANPlayInfo")
                    game.call("init__11LANPlayInfoFv", info)
                    game.u8(info, 1)
                    game.u8(info + 2, order)
                    game.u8(info + 3, arena)
                    initial = game.read(info, 0x44)
                    expected = [game.call("getCrsID__11LANPlayInfoFv", info) for _ in range(18)]
                    expected_state = game.read(info, 0x44)
                    game.write(info, initial)
                    game.u8(info, 3)
                    actual = [game.call("getCourseID__9LANBattleFR11LANPlayInfo", info) for _ in range(18)]
                    self.assertEqual(actual, expected)
                    self.assertEqual(game.read(info, 1), b"\x03")
                    self.assertEqual(game.read(info + 1, 0x43), expected_state[1:])

    def test_existing_course_modes_unchanged(self):
        for mode in range(3):
            with self.subTest(mode=mode):
                game = Game()
                game.network()
                info = game.addr("gLANPlayInfo")
                game.call("init__11LANPlayInfoFv", info)
                game.u8(info, mode)
                initial = game.read(info, 0x44)
                expected = game.call("getCrsID__11LANPlayInfoFv", info)
                state = game.read(info, 0x44)
                game.write(info, initial)
                self.assertEqual(game.call("getCourseID__9LANBattleFR11LANPlayInfo", info), expected)
                self.assertEqual(game.read(info, 0x44), state)

    def test_lan_entry_karts_views_and_all_sixteen_controllers(self):
        # Exercise the original LANEntry implementation plus the mod's rule
        # selection. Only the final hardware pad reset is outside this fixture.
        for mode in range(4):
            for cubes in range(2, 9):
                for tag in (False, True):
                    max_views = 1 if cubes > 4 else 2 if cubes > 2 or tag else 4
                    for views in (v for v in (1, 2, 4) if v <= max_views):
                        for local in range(cubes):
                            with self.subTest(mode=mode, cubes=cubes, tag=tag, views=views, local=local):
                                game = Game()
                                game.network()
                                game.stubs.add(game.addr("resetPort__6PadMgrFv"))
                                info = game.addr("gLANPlayInfo")
                                race = game.addr("gRaceInfo")
                                game.call("init__11LANPlayInfoFv", info)
                                game.u8(info, mode)
                                game.u8(info + 6, int(tag))
                                game.u32(game.ENTRY + 4, views)
                                game.u32(game.ENTRY + 8, cubes * views)
                                game.u8(game.ENTRY + 0x10, cubes)
                                game.u8(game.ENTRY + 0x11, local)
                                game.u8(game.ENTRY + 0x14, (1 << cubes) - 1)
                                game.write(game.ENTRY + 0x15, [views] * cubes)
                                game.u8(game.ENTRY + 0x1D, int(tag))
                                game.write(game.NET + 0x1304, b"SAFE")
                                game.call("setRaceInfo__8LANEntryFv", game.ENTRY)
                                before = game.read(race, 0x2A0)
                                game.call("applyRaceInfo__9LANBattleFRC11LANPlayInfoR8RaceInfo", info, race)
                                after = game.read(race, 0x2A0)
                                self.assertEqual(game.read32(race + 8), (2, 4, 7, 6)[mode])
                                self.assertEqual(after[:8] + after[12:], before[:8] + before[12:])
                                self.assertEqual(game.read16(race + 0x1C), cubes * views)
                                self.assertEqual(game.read16(race + 0x20), views)
                                self.assertEqual(game.read(race + 1, 1), b"\x01")
                                targets = [game.read16(race + 0x114 + i * 2) for i in range(views)]
                                self.assertEqual(targets, list(range(local * views, (local + 1) * views)))
                                expected_ports = [c * 4 + port for c in range(cubes) for port in range(views * (2 if tag else 1))]
                                self.assertEqual(game.read(game.NET + 0x12F4, len(expected_ports)), bytes(expected_ports))
                                self.assertEqual(game.read(game.NET + 0x1304, 4), b"SAFE")
                                # Every active kart has its correct primary and
                                # (tag mode) secondary virtual controller pointer.
                                for kart in range(cubes * views):
                                    pad = kart * (2 if tag else 1)
                                    self.assertEqual(game.read32(race + 0x30 + kart * 0x18 + 0x04), game.read32(game.addr("gpaKartPad") + pad * 4))
                                    second = game.read32(game.addr("gpaKartPad") + (pad + 1) * 4) if tag else 0
                                    self.assertEqual(game.read32(race + 0x30 + kart * 0x18 + 0x0C), second)

    def test_all_eight_karts_participate_in_battle_end_conditions(self):
        for count in range(2, 9):
            game = Game()
            race = game.addr("gRaceInfo")
            game.u32(game.addr("sRaceManager__7RaceMgr"), game.MANAGER)
            game.u32(game.MANAGER + 0x38, race)
            game.u16(race + 0x1C, count)
            balloon = game.field_offset("getBalloonNumber__11KartCheckerCFv")
            for i in range(count):
                checker = game.CHECKERS + i * 0x100
                game.u32(game.MANAGER + 0x48 + i * 4, checker)
                game.u16(checker + balloon, 0)
            game.u16(game.CHECKERS + (count - 1) * 0x100 + balloon, 3)
            self.assertEqual(game.call("checkRaceEndForBalloonBattle__12RaceDirectorFv", 0), 1)
            game.u16(game.CHECKERS + balloon, 1)
            self.assertEqual(game.call("checkRaceEndForBalloonBattle__12RaceDirectorFv", 0), 0)

            # An attacker/winner in the final slot must count in Bob-omb Blast.
            bomb = game.field_offset("getBombPoint__11KartCheckerCFv")
            game.u16(game.addr("sBombPointFull__11KartChecker"), 4)
            self.assertEqual(game.call("checkRaceEndForBombBattle__12RaceDirectorFv", 0), 0)
            self.assertEqual(game.call("incYourBombPoint__11KartCheckerFiii", count - 1, 0, 4), 1)
            self.assertEqual(game.read16(game.CHECKERS + (count - 1) * 0x100 + bomb), 4)
            self.assertEqual(game.call("checkRaceEndForBombBattle__12RaceDirectorFv", 0), 1)
            for i in range(count - 1):
                self.assertEqual(game.read16(game.CHECKERS + i * 0x100 + bomb), 0)

            # Shine Thief ends when any kart's holding timer reaches zero,
            # including a remote kart beyond the four local HUD slots.
            timer = game.field_offset("isRabbitWinner__11KartCheckerCFv")
            for i in range(count):
                game.u16(game.CHECKERS + i * 0x100 + timer, 60)
            self.assertEqual(game.call("checkRaceEndForEscapeBattle__12RaceDirectorFv", 0), 0)
            game.u16(game.CHECKERS + (count - 1) * 0x100 + timer, 0)
            self.assertEqual(game.call("checkRaceEndForEscapeBattle__12RaceDirectorFv", 0), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=BUILD)
    parser.add_argument("--nm", type=Path, default=NM)
    args, rest = parser.parse_known_args()
    BUILD, NM = args.build.resolve(), args.nm.resolve()
    unittest.main(argv=[__file__, *rest])
