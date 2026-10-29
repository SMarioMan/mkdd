"""Generate a surgical override from the user's extracted game assembly.

ItemObjMgr is only partly decompiled. Preserve its original implementation and
change the bomb-pool initialization alone, rather than link unfinished stubs.
The generated assembly stays under the ignored build directory.
"""
from pathlib import Path
import re


def prepare_item_override(out_path: Path) -> None:
    source = out_path / "asm/Sato/ItemObjMgr.s"
    if not source.exists():
        if (out_path / "config.json").exists():
            raise RuntimeError("Missing extracted ItemObjMgr assembly; rerun dtk dol split")
        # Ninja extracts the game and reruns configure before compiling anything.
        return
    text = source.read_text()
    pattern = re.compile(
        r"(\.fn initItemMaxNums__10ItemObjMgrFv, global\n)(.*?)(\.endfn initItemMaxNums__10ItemObjMgrFv)",
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError("Unexpected ItemObjMgr layout: missing pool initializer")
    function = matches[0]
    body = function.group(2)
    # The supported debug executable's initializer uses r6 as the table base,
    # r7 as the moving-item limit and r8 as the allocated/available pool size.
    # For <=4 karts retain 64. For eight karts: 80 held + 16 moving + 8 spare.
    replacement = """    lwz r3, sRaceManager__7RaceMgr@sda21(r0)
    lwz r3, 0x38(r3)
    lha r8, 0x1c(r3)
    mulli r8, r8, 10
    addi r8, r8, 24
    cmplwi r8, 64
    bge .L_lan_battle_bomb_pool_ready
    li r8, 64
.L_lan_battle_bomb_pool_ready:
"""
    updated, count = re.subn(
        r"^.*\bli r8, 0x40\n", replacement, body, flags=re.MULTILINE
    )
    if count != 1 or "li r7, 0x40" not in body or "0x492(r3)" not in body:
        raise RuntimeError("Unexpected ItemObjMgr pool initializer; refusing to patch")
    output = text[:function.start(2)] + updated + text[function.end(2):]
    destination = out_path / "lan-battle-overrides/Sato/ItemObjMgr.s"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_text() != output:
        destination.write_text(output)
