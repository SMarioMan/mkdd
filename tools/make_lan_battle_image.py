#!/usr/bin/env python3
"""Install a rebuilt DOL into a copy of the supported debug disc image.

Only the boot header, main executable and relocated file-system table change.
No game data is downloaded or included in this tool.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct


ORIGINAL_SHA1 = "db87a9ec1a34275efc45d965dcdcb1a9eb131885"


def dol_size(header):
    if len(header) < 0x100:
        raise ValueError("Truncated DOL header")
    ends = []
    for index in range(18):
        offset = struct.unpack_from(">I", header, index * 4)[0]
        size = struct.unpack_from(">I", header, 0x90 + index * 4)[0]
        if size:
            if offset < 0x100:
                raise ValueError("DOL section overlaps its header")
            ends.append(offset + size)
    if not ends:
        raise ValueError("DOL contains no sections")
    return max(ends)


def make_image(original, executable, output):
    if output.resolve() in (original.resolve(), executable.resolve()):
        raise ValueError("Output must be separate from both input files")
    if output.exists():
        raise ValueError("Output already exists; choose a new path")
    replacement = executable.read_bytes()
    if dol_size(replacement) != len(replacement):
        raise ValueError("Replacement DOL section sizes do not match its length")
    with original.open("rb") as source:
        header = source.read(0x440)
        if header[:6] != b"GM4E01" or header[0x1C:0x20] != bytes.fromhex("c2339f3d"):
            raise ValueError("Expected a GM4E01 GameCube image")
        dol_offset, fst_offset, fst_size = struct.unpack_from(">III", header, 0x420)
        source.seek(dol_offset)
        size = dol_size(source.read(0x100))
        source.seek(dol_offset)
        if hashlib.sha1(source.read(size)).hexdigest() != ORIGINAL_SHA1:
            raise ValueError("Original executable does not match MarioClub_us")
        source.seek(fst_offset)
        fst = source.read(fst_size)
        if len(fst) != fst_size or fst_size < 12:
            raise ValueError("Truncated file-system table")
        entries = struct.unpack_from(">I", fst, 8)[0]
        if entries < 1 or entries * 12 > len(fst):
            raise ValueError("Invalid file-system table")
        files = []
        for i in range(1, entries):
            kind, offset, length = struct.unpack_from(">III", fst, i * 12)
            if kind >> 24 == 0:
                if offset + length > original.stat().st_size:
                    raise ValueError("File lies outside the original image")
                files.append(offset)
        if not files:
            raise ValueError("Image contains no files")
        # The debug image has ample padding between its executable/FST and
        # first file. Relocate the FST into that gap; all file offsets stay put.
        new_fst_offset = (dol_offset + len(replacement) + 0x1F) & ~0x1F
        if new_fst_offset + fst_size > min(files):
            raise ValueError("Rebuilt executable would overlap game files")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(original, output)
        with output.open("r+b") as target:
            target.seek(dol_offset)
            target.write(replacement)
            target.seek(new_fst_offset)
            target.write(fst)
            target.seek(0x424)
            target.write(struct.pack(">I", new_fst_offset))
    except BaseException:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        make_image(args.original, args.executable, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, "Image creation failed: %s\n" % error)
    print("Created %s" % args.output)
