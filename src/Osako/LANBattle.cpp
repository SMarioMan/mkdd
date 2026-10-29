#include "Osako/LANBattle.h"
#include "Osako/LANPlayInfo.h"
#include "Kaneshige/RaceInfo.h"

ECourseID LANBattle::getCourseID(LANPlayInfo &info) {
    // The original, still undecompiled selector accepts VS, balloons and shine.
    // Bob-omb Blast uses exactly the same arena/order/unlock/RNG path as balloons.
    // Restore the wire mode after selection; do not alter the shared RNG seed.
    const u8 mode = info.getGameMode();
    if (mode == Bomb) {
        info.setGameMode(Balloon);
    }
    const ECourseID course = info.getCrsID();
    info.setGameMode(mode);
    return course;
}

void LANBattle::applyRaceInfo(const LANPlayInfo &info, RaceInfo &raceInfo) {
    // LANEntry has already populated all eight karts, sixteen pad mappings and
    // the local view targets. Its original mode switch has no Bob-omb case.
    // Select the battle rules before RaceApp creates items, HUD and checkers.
    if (info.getGameMode() == Bomb) {
        raceInfo.mRaceMode = BOMB_BATTLE;
    }
}
