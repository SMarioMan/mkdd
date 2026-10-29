# Eight-kart LAN battle mod

This mod targets the `MarioClub_us` debug build on the `8-player-battle`
branch. The LAN mode selector offers VS, Balloon Battle, Shine Thief and
Bob-omb Blast. Tag mode supports two controllers per kart, up to eight karts
and sixteen controllers total. Each console still renders at most four views.
Every connected console must run the same modded executable.

## Build

Provide the supported debug disc image in `orig/MarioClub_us/`, then run:

```sh
python configure.py --lan-battle --map --build-dir build/lan-battle
ninja -j 5
```

The output is `build/lan-battle/MarioClub_us/main.dol`. `--lan-battle` selects
a modified executable, so the original game's output checksum is intentionally
not the build target. It does not enable the unrelated `Equivalent` objects;
undecompiled functions continue to come from the original executable.
`--non-matching` is not required.

On this cloud machine, the pinned 32-bit wibo requires QEMU user emulation:

```sh
export PATH="/workspace/.venvs/mkdd/bin:$PATH"
python configure.py --lan-battle --map --build-dir build/lan-battle \
  --wrapper /workspace/.tools/mkdd/wibo-qemu \
  --compilers /workspace/mkdd/build/compilers \
  --binutils /workspace/mkdd/build/binutils \
  --dtk /workspace/mkdd/build/tools/dtk \
  --objdiff /workspace/mkdd/build/tools/objdiff-cli \
  --sjiswrap /workspace/mkdd/build/tools/sjiswrap.exe
ninja -j 5
```

To create a bootable disc image, keeping the original image intact:

```sh
python tools/make_lan_battle_image.py \
  orig/MarioClub_us/GM4E01.iso \
  build/lan-battle/MarioClub_us/main.dol \
  build/lan-battle/GM4E01-lan-battle.iso
```

The packaging tool verifies the original executable's SHA-1, copies the disc,
installs the rebuilt executable and relocates the file-system table into the
unused space before the first file. It refuses to overwrite an existing output
or overlap game files. Neither assets nor an original executable are included
in the repository.

## LAN setup

Connect two to eight consoles using the game's normal LAN connection flow.
Choose a battle mode, arena order and display count on the LAN mode screen.
Use Tag On for two controllers per kart.

| Connected consoles | Maximum views per console, Tag Off | Tag On |
| --- | --- | --- |
| 2 | 4 | 2 |
| 3–4 | 2 | 2 |
| 5–8 | 1 | 1 |

Eight consoles with one kart each and Tag On use sixteen controllers. Four
consoles with two karts each and Tag On also use sixteen controllers. A console
can enter fewer karts than the selected display capacity, as in the original
LAN entry screen.

## Implementation and validation

The debug game's original LAN implementation already supports eight karts,
sixteen virtual controller mappings, Balloon Battle and Shine Thief. All six
arenas have start IDs 0–7. This mod adds the missing Bob-omb Blast selection,
loads its existing label from `battlename.arc`, and selects its race rules
after LAN entry has assigned karts and controllers. Bob-omb Blast delegates
arena selection to the original battle selector and restores the transmitted
mode afterward, preserving arena unlocks, ordering and seeded randomness.

The original 64-bomb pool cannot hold five bombs for each of sixteen characters
plus bombs already in flight. The mod uses `max(64, 10 * kart_count + 24)`, up to
104 bombs: 80 held, 16 moving and eight spare. The active-bomb limit stays at
16. Since ItemObjMgr is incompletely decompiled, `tools/lan_battle.py` generates
an assembly override from the user's extracted game, changing only this pool
initializer. No extracted assembly is committed to the repository.

The linker template now resolves the embedded system archive and build date
through their symbols. Fixed addresses work for the original matching build
but point at the wrong bytes when added code moves the embedded resources.

Run the CPU integration suite against the built PowerPC executable:

```sh
python -m pip install unicorn==2.1.4
python tests/lan_battle_ppc.py -v
```

The suite executes game instructions for every supported console/view/tag
layout and local console index, checks controller pointers and all sixteen pad
conversion slots, verifies course selection and RNG progression, and exercises
all three modes' win conditions through kart eight. It also checks the embedded
archive aliases. These tests do not emulate the Ethernet adapter or rendering.
The six tests pass, including the larger bomb pool with both characters in all
eight karts holding five bombs each.

Dolphin boot testing confirmed the four LAN mode labels and a two-kart,
split-screen Bob-omb Blast arena startup. That startup used the build before
the bomb-pool increase. The final packaged image also boots in eight Dolphin
instances, and its embedded executable matches the built DOL. A complete
eight-console network match has not been verified; the local test harness has
not reliably delivered menu input to all instances. Booting eight instances
alone does not establish network synchronization or sixteen-controller play.

The original, unmodded build must still pass `ninja build/MarioClub_us/ok`
after configuring without `--lan-battle`.

Before describing the mod as fully validated, complete a live LAN playtest:

- Start and finish each battle mode on all six arenas with eight karts.
- Exercise both eight-console/one-view and four-console/two-view Tag On layouts.
- Verify remote hits, balloon loss/stealing and elimination, Bob-omb points,
  shine transfers/timer expiry, and winner/result screens on every console.
- Swap drivers using both controllers and verify input reaches the correct kart.
- Return to the lobby and start another round; check all arena-order choices.
- Include a spectator console and partially filled entry layouts.
- Check frame synchronization and disconnect/reconnect behavior under real LAN
  timing. CPU integration tests cannot establish these properties.
