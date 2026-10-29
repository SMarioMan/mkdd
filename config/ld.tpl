MEMORY
{
    text : origin = $ORIGIN
}

SECTIONS
{
    GROUP:
    {
        $SECTIONS
        .stack ALIGN(0x100):{}
    } > text

    _stack_addr = (_f_sbss2 + SIZEOF(.sbss2) + 65536 + 0x7) & ~0x7;
    _stack_end = _f_sbss2 + SIZEOF(.sbss2);
    _db_stack_addr = (_stack_addr + 0x2000);
    _db_stack_end = _stack_addr;
    __ArenaLo = (_db_stack_addr + 0x1f) & ~0x1f;
    __ArenaHi = $ARENAHI;
    _pSystemArc = lbl_80316680;
    _pBuildtimeDat = lbl_803608E0;
}

FORCEACTIVE
{
    $FORCEACTIVE
}
