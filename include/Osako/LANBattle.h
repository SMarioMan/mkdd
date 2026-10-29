#ifndef LANBATTLE_H
#define LANBATTLE_H

#include "kartEnums.h"

class LANPlayInfo;
class RaceInfo;

// The first three values are part of the original LAN settings packet.
// Keep their meaning so course order, saved settings and tag controls work.
namespace LANBattle {
enum Mode {
    Versus = 0,
    Balloon = 1,
    Shine = 2,
    Bomb = 3,
    ModeCount = 4
};

ECourseID getCourseID(LANPlayInfo &info);
void applyRaceInfo(const LANPlayInfo &info, RaceInfo &raceInfo);
}

#endif
